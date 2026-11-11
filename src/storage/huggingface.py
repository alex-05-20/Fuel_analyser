import os
from pathlib import Path

from dotenv import dotenv_values
from huggingface_hub import HfApi


def connect_dataset(root: Path) -> tuple[HfApi, str]:
    """Load local credentials, with environment variables taking precedence."""
    settings = {**dotenv_values(root / ".env"), **os.environ}
    token = (settings.get("HF_TOKEN") or "").strip()
    repo_id = (settings.get("HF_REPO_ID") or "").strip()
    if not token or not repo_id:
        raise ValueError("HF_TOKEN et HF_REPO_ID doivent être configurés.")
    api = HfApi(endpoint="https://huggingface.co", token=token)
    return api, repo_id
