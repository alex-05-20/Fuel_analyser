import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from tempfile import NamedTemporaryFile
import time
from urllib.request import urlopen
import xml.etree.ElementTree as ET
from zipfile import ZipFile


def inspect_archive(path: Path) -> dict:
    stations = 0
    prices = 0
    empty_prices = 0
    with ZipFile(path) as archive:
        xml_files = [name for name in archive.namelist() if name.lower().endswith(".xml")]
        if len(xml_files) != 1:
            raise ValueError("Un fichier XML unique est attendu.")
        with archive.open(xml_files[0]) as source:
            context = ET.iterparse(source, events=("start", "end"))
            _, root = next(context)
            if root.tag != "pdv_liste":
                raise ValueError("Racine XML inattendue.")
            for event, node in context:
                if event == "end" and node.tag == "pdv":
                    stations += 1
                    for price in node.findall("prix"):
                        prices += 1
                        empty_prices += not bool(price.attrib)
                    node.clear()
                    root.clear()
    if stations == 0 or prices == 0:
        raise ValueError("Archive sans stations ou sans prix.")
    with path.open("rb") as source:
        checksum = hashlib.file_digest(source, "sha256").hexdigest()
    return {
        "bytes": path.stat().st_size, "sha256": checksum,
        "station_entries": stations, "price_elements": prices,
        "empty_price_elements": empty_prices, "xml_file": xml_files[0],
    }


def fetch_year(year: int, current_year: int, folder: Path) -> dict:
    url = "https://donnees.roulez-eco.fr/opendata/annee"
    if year != current_year:
        url += f"/{year}"
    destination = folder / f"{year}.zip"
    if destination.exists() and year != current_year:
        report = inspect_archive(destination)
    else:
        for attempt in range(3):
            with NamedTemporaryFile(dir=folder, suffix=".download", delete=False) as file:
                temporary = Path(file.name)
            try:
                with urlopen(url, timeout=120) as response, temporary.open("wb") as output:
                    shutil.copyfileobj(response, output)
                report = inspect_archive(temporary)
                temporary.replace(destination)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
            finally:
                temporary.unlink(missing_ok=True)
    return {
        "year": year, "source": url, "partial_year": year == current_year,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(), **report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Télécharger et vérifier les archives officielles.")
    parser.add_argument("--through-year", type=int, default=datetime.now(timezone.utc).year)
    args = parser.parse_args()
    current_year = datetime.now(timezone.utc).year
    if not 2007 <= args.through_year <= current_year:
        parser.error("L'année doit être comprise entre 2007 et l'année courante.")
    folder = Path(__file__).resolve().parents[1] / "data/raw/annual"
    folder.mkdir(parents=True, exist_ok=True)
    reports = []
    failures = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(fetch_year, year, current_year, folder): year
            for year in range(2007, args.through_year + 1)
        }
        for future in as_completed(futures):
            year = futures[future]
            try:
                report = future.result()
                reports.append(report)
                print(f"{year} vérifié : {report['station_entries']} stations, {report['price_elements']} éléments de prix.", flush=True)
            except Exception as error:
                failures.append(year)
                print(f"{year} en échec : {type(error).__name__}", flush=True)
    manifest = {"archives": sorted(reports, key=lambda item: item["year"]), "failed_years": failures}
    temporary = folder / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(folder / "manifest.json")
    print(f"{len(reports)} archives vérifiées, {sum(item['bytes'] for item in reports) / 1_000_000:.1f} Mo.", flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
