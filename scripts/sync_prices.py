from pathlib import Path
from tempfile import TemporaryDirectory
import shutil

from huggingface_hub import CommitOperationAdd, hf_hub_download
from huggingface_hub.utils import disable_progress_bars

from scripts.refresh_prices import download_snapshot
from src.pipeline import publish_snapshot
from src.storage.huggingface import connect_dataset
from src.storage.locking import publication_lock
from src.storage.prices import load_prices, save_prices

CURRENT = "data/processed/prices_current.csv"
HISTORY = "data/historical/prices_history.csv"


def sync_prices(root: Path) -> tuple[int, int, int]:
    api, repo_id = connect_dataset(root)
    api.auth_check(repo_id=repo_id, repo_type="dataset", write=True)
    with publication_lock(root / "data/processed/publication.lock"):
        head = api.repo_info(repo_id, repo_type="dataset").sha
        with TemporaryDirectory() as temporary:
            staging = Path(temporary)
            for filename in (CURRENT, HISTORY):
                hf_hub_download(
                    repo_id=repo_id, repo_type="dataset", filename=filename,
                    revision=head, token=api.token, local_dir=staging,
                )
            downloaded = staging / "download.csv"
            download_snapshot(downloaded)
            result = publish_snapshot(downloaded, staging)
            archives = sorted((staging / "data/raw/archives").glob("*.csv"))
            paths = [staging / CURRENT, staging / HISTORY, *archives]
            commit = api.create_commit(
                repo_id=repo_id, repo_type="dataset",
                operations=[
                    CommitOperationAdd(
                        path_in_repo=path.relative_to(staging).as_posix(),
                        path_or_fileobj=path,
                    ) for path in paths
                ],
                commit_message=f"Collecte carburants : {result[2]} nouvelles observations",
                parent_commit=head,
            )
            # A competing publication causes a conflict instead of overwriting its history.
            remote = api.repo_info(
                repo_id, repo_type="dataset", revision=commit.oid, files_metadata=True
            )
            sizes = {item.rfilename: item.size for item in remote.siblings}
            for path in paths:
                relative = path.relative_to(staging)
                if sizes.get(relative.as_posix()) != path.stat().st_size:
                    raise RuntimeError("La vérification des fichiers publiés a échoué.")
            for archive in archives:
                target = root / archive.relative_to(staging)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(archive, target)
            save_prices(load_prices(staging / HISTORY), root / HISTORY)
            save_prices(load_prices(staging / CURRENT), root / CURRENT)
    return result


def main() -> None:
    disable_progress_bars()
    try:
        stations, rows, added = sync_prices(Path(__file__).resolve().parents[1])
    except Exception as error:
        status = getattr(getattr(error, "response", None), "status_code", None)
        print(f"Synchronisation échouée ({type(error).__name__}, HTTP {status}).")
        print("Après résolution du problème, relancez la commande pour repartir de la dernière version cloud.")
        raise SystemExit(1) from None
    print(f"{stations} stations, {rows} lignes actuelles, {added} nouvelles observations historiques.")
    print("Publication Hugging Face vérifiée et fichiers locaux actualisés.")


if __name__ == "__main__":
    main()
