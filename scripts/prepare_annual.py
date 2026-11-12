import argparse
from collections import Counter
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

FUELS = {"1": "Gazole", "2": "SP95", "3": "E85", "4": "GPLc", "5": "E10", "6": "SP98"}
SCHEMA = pa.schema([
    ("station_id", pa.string()), ("fuel", pa.string()),
    ("price_reported_at", pa.timestamp("us")), ("price_eur_l", pa.float64()),
    ("suspect_price", pa.bool_()), ("outside_archive_year", pa.bool_()),
])


def prepare_year(archive_path: Path, destination: Path) -> dict:
    year = int(archive_path.stem)
    divisor = 1000 if year <= 2021 else 1
    counts = Counter()
    fuels = Counter()
    stations = []
    interruptions = []
    seen_stations = set()
    bounds = []
    destination.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(dir=destination) as temporary:
        staging = Path(temporary)
        with pq.ParquetWriter(staging / "prices.parquet", SCHEMA, compression="zstd") as writer:
            rows = []

            def flush():
                if not rows:
                    return
                frame = pd.DataFrame(rows, columns=["station_id", "fuel", "date_raw", "price_raw"])
                frame["price_reported_at"] = pd.to_datetime(frame.pop("date_raw"), format="mixed", errors="coerce")
                frame["price_eur_l"] = pd.to_numeric(frame.pop("price_raw"), errors="coerce") / divisor
                invalid = (
                    frame["fuel"].isna() | frame["price_reported_at"].isna()
                    | frame["price_eur_l"].isna() | frame["price_eur_l"].le(0)
                    | frame["price_eur_l"].eq(float("inf"))
                )
                counts["invalid_rows"] += int(invalid.sum())
                frame = frame.loc[~invalid].copy()
                duplicate = frame.duplicated(["station_id", "fuel", "price_reported_at", "price_eur_l"])
                counts["exact_duplicates_removed"] += int(duplicate.sum())
                frame = frame.loc[~duplicate].copy()
                counts["conflicting_timestamp_rows"] += int(frame.duplicated(
                    ["station_id", "fuel", "price_reported_at"], keep=False
                ).sum())
                frame["suspect_price"] = ~frame["price_eur_l"].between(0.2, 5)
                frame["outside_archive_year"] = frame["price_reported_at"].dt.year.ne(year)
                counts["suspect_price_rows"] += int(frame["suspect_price"].sum())
                counts["outside_archive_year_rows"] += int(frame["outside_archive_year"].sum())
                counts["retained_rows"] += len(frame)
                fuels.update(frame["fuel"].value_counts().to_dict())
                if not frame.empty:
                    bounds.extend([frame["price_reported_at"].min(), frame["price_reported_at"].max()])
                writer.write_table(pa.Table.from_pandas(frame, schema=SCHEMA, preserve_index=False))
                rows.clear()

            with ZipFile(archive_path) as archive:
                xml_name = next(name for name in archive.namelist() if name.lower().endswith(".xml"))
                with archive.open(xml_name) as source:
                    context = ET.iterparse(source, events=("start", "end"))
                    _, root = next(context)
                    for event, node in context:
                        if event != "end" or node.tag != "pdv":
                            continue
                        station_id = node.get("id")
                        if not station_id or station_id in seen_stations:
                            raise ValueError("Identifiant station absent ou répété dans l'archive.")
                        seen_stations.add(station_id)
                        stations.append({
                            "station_id": station_id, "postal_code": node.get("cp"),
                            "city": node.findtext("ville"), "address": node.findtext("adresse"),
                            "road_type": node.get("pop"),
                            "latitude_raw": node.get("latitude"), "longitude_raw": node.get("longitude"),
                        })
                        for price in node.findall("prix"):
                            counts["source_price_elements"] += 1
                            rows.append((station_id, FUELS.get(price.get("id")), price.get("maj"), price.get("valeur")))
                        for kind in ("rupture", "fermeture"):
                            for item in node.findall(kind):
                                interruptions.append({
                                    "station_id": station_id, "kind": kind,
                                    "fuel": FUELS.get(item.get("id")),
                                    "type": item.get("type"), "start_raw": item.get("debut"),
                                    "end_raw": item.get("fin"),
                                })
                        # A station's full history stays in one batch for duplicate detection.
                        if len(rows) >= 100_000:
                            flush()
                        node.clear()
                        root.clear()
            flush()

        station_frame = pd.DataFrame(stations)
        for coordinate, limit in (("latitude", 90), ("longitude", 180)):
            values = pd.to_numeric(station_frame.pop(coordinate + "_raw"), errors="coerce") / 100_000
            station_frame[coordinate] = values.where(values.between(-limit, limit))
        counts["stations_without_coordinates"] = int(
            station_frame[["latitude", "longitude"]].isna().any(axis=1).sum()
        )
        station_frame.to_parquet(staging / "stations.parquet", index=False)
        interval_frame = pd.DataFrame(interruptions, columns=[
            "station_id", "kind", "fuel", "type", "start_raw", "end_raw",
        ])
        # Retain original interval strings, including open-ended or malformed dates.
        interval_frame.to_parquet(staging / "interruptions.parquet", index=False)
        report = {
            "year": year, "price_divisor": divisor, "station_count": len(stations),
            "interruption_count": len(interruptions), **dict(counts),
            "fuel_counts": dict(fuels),
            "first_price_date": str(min(bounds)) if bounds else None,
            "last_price_date": str(max(bounds)) if bounds else None,
            "date_convention": "Source timestamps preserved without timezone assignment.",
            "suspect_price_rule": "Below 0.2 or above 5 EUR/L, retained and flagged.",
        }
        (staging / "quality.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        for name in ("prices.parquet", "stations.parquet", "interruptions.parquet", "quality.json"):
            (staging / name).replace(destination / name)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Préparer les archives annuelles pour l'analyse.")
    parser.add_argument("--year", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    archives = sorted((root / "data/raw/annual").glob("*.zip"))
    if args.year:
        archives = [path for path in archives if path.stem == str(args.year)]
    if not archives:
        parser.error("Aucune archive correspondante.")
    for archive in archives:
        report = prepare_year(archive, root / "data/processed/annual" / archive.stem)
        print(
            f"{archive.stem} : {report['retained_rows']} prix, "
            f"{report['invalid_rows']} invalides, {report['exact_duplicates_removed']} doublons retirés.",
            flush=True,
        )


if __name__ == "__main__":
    main()
