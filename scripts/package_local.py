"""Build an explicit allowlist package; never include credentials or cloud tools."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


def main():
    root = Path(__file__).resolve().parents[1]
    names = ["notebooks/analyses.ipynb", "notebooks/exploration_annuelle.ipynb", "notebooks/audit_qualite.ipynb", "README.md", "requirements.txt", "requirements-notebook.txt", "src/__init__.py", "src/pipeline.py", "app.py", ".streamlit/config.toml", "assets/maps/regions_france.geojson", "assets/maps/SOURCE.md"]
    names += [f"scripts/{name}.py" for name in ("refresh_prices", "prepare_prices", "download_annual", "prepare_annual", "update_local", "prepare_dashboard", "package_local")]
    for folder in ("src/ingestion", "src/processing", "src/storage", "src/analytics", "tests"):
        names += [p.relative_to(root).as_posix() for p in (root / folder).glob("*.py") if p.name != "huggingface.py"]
    for folder in ("data/raw/annual", "data/raw/snapshots", "data/raw/legacy_collections", "data/cleaned", "data/quality"):
        names += [p.relative_to(root).as_posix() for p in (root / folder).rglob("*") if p.is_file() and p.suffix in (".zip", ".csv", ".parquet", ".json")]
    names += [name for name in ("data/last_update.json") if (root / name).exists()]
    names = sorted(set(names))
    for source in (root / "data/raw/annual").glob("*.zip"):
        if f"data/cleaned/historical/{source.stem}.parquet" not in names:
            raise ValueError(f"Historique nettoyé manquant : {source.stem}")
    out = root / "dist"
    out.mkdir(exist_ok=True)
    target = out / "Fuel_analyser_local.zip"
    temporary = out / "Fuel_analyser_local.zip.tmp"
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "status": "architecture locale, tables complètes", "files": []}
    with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for name in names:
            source = root / name
            with source.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            destination = name
            archive.write(source, "Fuel_analyser/" + destination)
            manifest["files"].append({"path": destination, "bytes": source.stat().st_size, "sha256": digest})
        extras = {"scripts/__init__.py": ""}
        for name, content in extras.items():
            archive.writestr("Fuel_analyser/" + name, content)
            manifest["files"].append({"path": name, "bytes": len(content.encode()), "sha256": hashlib.sha256(content.encode()).hexdigest()})
        archive.writestr("Fuel_analyser/LIVRAISON.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    with ZipFile(temporary) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"Fichier ZIP invalide : {bad}")
    temporary.replace(target)
    print(f"{target} — {target.stat().st_size / 1_000_000:.1f} Mo, {len(names)} fichiers sources")


if __name__ == "__main__":
    main()
