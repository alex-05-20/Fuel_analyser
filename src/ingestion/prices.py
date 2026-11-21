from pathlib import Path

import pandas as pd


def read_prices_csv(path: str | Path) -> pd.DataFrame:
    """Read the official snapshot while preserving identifiers and postal codes."""
    return pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype="string", keep_default_na=False)
