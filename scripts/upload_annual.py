import hashlib
import logging
import json
from pathlib import Path

from huggingface_hub import CommitOperationAdd
from huggingface_hub.utils import disable_progress_bars

from src.storage.huggingface import connect_dataset


def main() -> None:
    disable_progress_bars()
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    root = Path(__file__).resolve().parents[1]
    api, repo_id = connect_dataset(root)
    api.auth_check(repo_id=repo_id, repo_type="dataset", write=True)
    manifest_path = root / "data/raw/annual/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["failed_years"]:
        raise ValueError("Certaines archives ont échoué à la vérification.")
    paths = [manifest_path]
    fuel_counts = {}
    rows = 0
    for item in manifest["archives"]:
        year = str(item["year"])
        archive = root / "data/raw/annual" / f"{year}.zip"
        with archive.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != item["sha256"]:
                raise ValueError(f"L'archive {year} a changé depuis sa vérification.")
        paths.append(archive)
        folder = root / "data/processed/annual" / year
        report = json.loads((folder / "quality.json").read_text(encoding="utf-8"))
        rows += report["retained_rows"]
        for fuel, count in report["fuel_counts"].items():
            fuel_counts[fuel] = fuel_counts.get(fuel, 0) + count
        paths.extend(folder / name for name in (
            "prices.parquet", "stations.parquet", "interruptions.parquet", "quality.json",
        ))
    digests = {}
    for path in paths:
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        git_hash = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                git_hash.update(chunk)
        digests[path.relative_to(root).as_posix()] = (digest, git_hash.hexdigest())
    head = api.repo_info(repo_id, repo_type="dataset").sha
    print(f"Envoi de {len(paths)} fichiers, {sum(p.stat().st_size for p in paths) / 1_000_000:.1f} Mo.", flush=True)
    print(f"{rows} observations. Carburants : {', '.join(sorted(fuel_counts))}.", flush=True)
    commit = api.create_commit(
        repo_id=repo_id, repo_type="dataset",
        operations=[CommitOperationAdd(
            path_in_repo=path.relative_to(root).as_posix(), path_or_fileobj=path
        ) for path in paths],
        commit_message="Archives annuelles 2007–2026 et données préparées, tous carburants",
        parent_commit=head,
    )
    info = api.repo_info(repo_id, repo_type="dataset", revision=commit.oid, files_metadata=True)
    remote = {item.rfilename: item for item in info.siblings}
    for path in paths:
        name = path.relative_to(root).as_posix()
        item = remote.get(name)
        if item is None or item.size != path.stat().st_size:
            raise RuntimeError(f"Taille incorrecte : {name}")
        sha256, git_hash = digests[name]
        if item.lfs:
            if item.lfs.sha256 != sha256:
                raise RuntimeError(f"Empreinte incorrecte : {name}")
        elif item.blob_id != git_hash:
            raise RuntimeError(f"Empreinte Git incorrecte : {name}")
    print(f"{len(paths)} fichiers vérifiés par taille et empreinte.", flush=True)
    print(commit.commit_url, flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Publication interrompue ({type(error).__name__}).", flush=True)
        raise SystemExit(1) from None

