from datetime import datetime
from pathlib import Path

import pandas as pd

from src.storage.prices import load_prices

KEYS = ["station_id", "fuel"]


def extend_history(prices: pd.DataFrame, history_path: Path, current_path: Path,
                   observed_at: datetime, archive: str) -> tuple[pd.DataFrame, int]:
    """Append observations that differ from the latest known state of each fuel."""
    columns = list(prices.columns)
    if history_path.exists():
        history = load_prices(history_path)
    elif current_path.exists():
        # The earlier pipeline did not record collection timestamps.
        history = load_prices(current_path).assign(observed_at=pd.NA, source_archive=pd.NA)
    else:
        history = prices.iloc[:0].assign(observed_at=pd.NA, source_archive=pd.NA)

    previous = history.drop_duplicates(KEYS, keep="last").set_index(KEYS)
    incoming = prices.set_index(KEYS)
    previous = previous.reindex(incoming.index)
    values = [column for column in columns if column not in KEYS]
    same = (
        incoming[values].eq(previous[values])
        | (incoming[values].isna() & previous[values].isna())
    ).fillna(False).all(axis=1)
    added = incoming.loc[~same].reset_index()[columns]
    added = added.assign(observed_at=observed_at.isoformat(), source_archive=archive)
    if added.empty:
        return history, 0
    if history.empty:
        return added, len(added)
    for column in ("observed_at", "source_archive"):
        history[column] = history[column].astype("string")
        added[column] = added[column].astype("string")
    return pd.concat([history, added], ignore_index=True), len(added)

