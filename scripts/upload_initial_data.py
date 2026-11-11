from pathlib import Path

from huggingface_hub import CommitOperationAdd

from src.storage.huggingface import connect_dataset
from src.storage.locking import publication_lock


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    api, repo_id = connect_dataset(root)
    api.auth_check(repo_id=repo_id, repo_type="dataset", write=True)
    with publication_lock(root / "data/processed/publication.lock"):
        info = api.repo_info(repo_id, repo_type="dataset")
        remote_paths = {item.rfilename for item in info.siblings}
        # This command bootstraps storage; later updates must load remote history.
        if any(name.startswith("data/") for name in remote_paths):
            print("Le dépôt contient déjà des données. Le premier envoi a déjà été effectué.")
            return
        paths = [
            root / "data/processed/prices_current.csv",
            root / "data/historical/prices_history.csv",
            *sorted((root / "data/raw/archives").glob("*.csv")),
        ]
        if len(paths) < 3 or any(not path.is_file() for path in paths):
            raise ValueError("Préparez les prix, l'historique et une archive avant l'envoi.")
        operations = [
            CommitOperationAdd(
                path_in_repo=path.relative_to(root).as_posix(), path_or_fileobj=path
            ) for path in paths
        ]
        commit = api.create_commit(
            repo_id=repo_id, repo_type="dataset", operations=operations,
            commit_message="Initialisation des données Fuel Analyser",
            parent_commit=info.sha,
        )
        remote = api.repo_info(repo_id, repo_type="dataset", revision=commit.oid, files_metadata=True)
        sizes = {item.rfilename: item.size for item in remote.siblings}
        for path in paths:
            if sizes.get(path.relative_to(root).as_posix()) != path.stat().st_size:
                raise RuntimeError("La vérification de la taille d'un fichier a échoué.")
    print(f"{len(paths)} fichiers publiés et vérifiés sur {repo_id}.")
    print(commit.commit_url)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        status = getattr(getattr(error, "response", None), "status_code", None)
        print(f"Envoi échoué ({type(error).__name__}, HTTP {status}).")
        raise SystemExit(1) from None
