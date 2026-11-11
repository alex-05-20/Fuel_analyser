from pathlib import Path

from src.storage.huggingface import connect_dataset


def main() -> None:
    try:
        api, repo_id = connect_dataset(Path(__file__).resolve().parents[1])
        api.auth_check(repo_id=repo_id, repo_type="dataset", write=True)
        info = api.repo_info(repo_id=repo_id, repo_type="dataset")
    except Exception as error:
        # Keep credentials and server response bodies out of console output.
        status = getattr(getattr(error, "response", None), "status_code", None)
        print(f"Connexion échouée ({type(error).__name__}, HTTP {status}). Vérifiez la configuration et les droits du jeton.")
        raise SystemExit(1) from None
    print(f"Connexion réussie à {repo_id}. Lecture et écriture autorisées.")
    print(f"Dépôt privé : {info.private}. Accès sur demande : {info.gated}.")


if __name__ == "__main__":
    main()
