"""Optional official-source refresh, staged before changing local data."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from scripts.download_annual import fetch_year
from scripts.prepare_annual import prepare_year
from scripts.refresh_prices import download_snapshot
from src.pipeline import publish_snapshot
from src.storage.locking import publication_lock


def install_files(staged, root, backup):
    """Rollback already installed files on a handled publication error."""
    changed = []
    try:
        for source in sorted(staged.rglob("*")):
            if not source.is_file() or source.suffix == ".lock":
                continue
            relative = source.relative_to(staged)
            target = root / relative
            saved = backup / relative
            existed = target.exists()
            if existed:
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
            target.parent.mkdir(parents=True, exist_ok=True)
            source.replace(target)
            changed.append((target, saved, existed))
    except Exception:
        for target, saved, existed in reversed(changed):
            if existed:
                saved.replace(target)
            else:
                target.unlink(missing_ok=True)
        raise


def update(root):
    root = Path(root)
    with publication_lock(root / "data/update.lock"):
        with publication_lock(root / "data/processed/publication.lock"):
            with TemporaryDirectory(dir=root, prefix=".update-") as temp:
                staging = Path(temp) / "staging"
                raw = staging / "data/raw/annual"
                raw.mkdir(parents=True)
                current_year = datetime.now(timezone.utc).year
                manifest_path = root / "data/raw/annual/manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"archives": []}
                reports = {entry["year"]: entry for entry in manifest["archives"]}
                for year in range(2007, current_year + 1):
                    prepared = root / f"data/processed/annual/{year}"
                    complete = all((prepared / name).exists() for name in ("prices.parquet", "stations.parquet", "interruptions.parquet", "quality.json"))
                    if year < current_year - 1 and complete and (root / f"data/raw/annual/{year}.zip").exists():
                        continue
                    print(f"Actualisation de {year}…", flush=True)
                    reports[year] = fetch_year(year, current_year, raw)
                    prepare_year(raw / f"{year}.zip", staging / f"data/processed/annual/{year}")
                (raw / "manifest.json").write_text(json.dumps({"archives": sorted(reports.values(), key=lambda r: r["year"]), "failed_years": []}, indent=2), encoding="utf-8")
                for relative in ("data/processed/prices_current.csv", "data/historical/prices_history.csv"):
                    source = root / relative
                    if source.exists():
                        destination = staging / relative
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, destination)
                snapshot = Path(temp) / "snapshot.csv"
                download_snapshot(snapshot)
                result = publish_snapshot(snapshot, staging)
                (staging / "data/last_update.json").write_text(json.dumps({"completed_at_utc": datetime.now(timezone.utc).isoformat(), "stations": result[0], "current_rows": result[1], "new_history_rows": result[2]}, indent=2), encoding="utf-8")
                install_files(staging, root, Path(temp) / "backup")
                return result


def main():
    try:
        stations, rows, added = update(Path(__file__).resolve().parents[1])
    except Exception as error:
        print(f"Mise à jour non terminée ({type(error).__name__}). Les téléchargements sont préparés séparément ; les fichiers précédents restent utilisables en cas d’échec réseau.")
        raise SystemExit(1)
    print(f"Mise à jour réussie : {stations} stations, {rows} prix actuels, {added} nouvelles observations.")


if __name__ == "__main__":
    main()
