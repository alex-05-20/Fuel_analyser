from datetime import datetime, timezone
from pathlib import Path
import shutil
from uuid import uuid4

from src.ingestion.prices import read_prices_csv
from src.processing.prices import normalize_prices
from src.storage.history import extend_history
from src.storage.prices import save_prices
from src.storage.locking import publication_lock


def publish_snapshot(source: Path, root: Path) -> tuple[int, int, int]:
    snapshot = read_prices_csv(source)
    prices = normalize_prices(snapshot)
    if snapshot.empty or prices.empty:
        raise ValueError("Le flux est vide : les fichiers précédents sont conservés.")
    current = root / "data/processed/prices_current.csv"
    historical = root / "data/historical/prices_history.csv"
    with publication_lock(root / "data/processed/publication.lock"):
        now = datetime.now(timezone.utc)
        filename = f"prices_{now:%Y%m%dT%H%M%S%fZ}_{uuid4().hex[:8]}.csv"
        archive = root / "data/raw/archives" / filename
        archive.parent.mkdir(parents=True, exist_ok=True)
        history, added = extend_history(
            prices, historical, current, now, archive.relative_to(root).as_posix()
        )
        # Publish the complete archive before the history references it.
        temporary = archive.with_suffix(".tmp")
        try:
            shutil.copyfile(source, temporary)
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)
        save_prices(history, historical)
        save_prices(prices, current)
    return len(snapshot), len(prices), added
