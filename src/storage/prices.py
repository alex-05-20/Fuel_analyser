from pathlib import Path
import pandas as pd
from tempfile import NamedTemporaryFile


def save_prices(prices: pd.DataFrame, path: Path) -> None:
    """Publish a complete CSV, preserving the previous file if writing fails."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, suffix=".csv", delete=False) as file:
        temporary = Path(file.name)
    try:
        prices.to_csv(temporary, index=False, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_prices(path: Path) -> pd.DataFrame:
    prices = pd.read_csv(
        path,
        dtype={"station_id": "string", "postal_code": "string"},
        float_precision="round_trip",
    )
    for column in ("price_reported_at", "outage_started_at"):
        prices[column] = pd.to_datetime(prices[column], utc=True, format="ISO8601")
    return prices
