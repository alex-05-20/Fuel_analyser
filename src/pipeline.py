from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from uuid import uuid4
from src.ingestion.prices import read_prices_csv
from src.processing.prices import clean_snapshot
from src.storage.locking import publication_lock


def publish_snapshot(source: Path, root: Path):
    raw=read_prices_csv(source)
    if raw.empty:raise ValueError('Source vide')
    cleaned,report=clean_snapshot(raw)
    with publication_lock(root/'data/cleaned/publication.lock'):
        folder=root/'data/cleaned';folder.mkdir(parents=True,exist_ok=True)
        raw_folder=root/'data/raw/snapshots';raw_folder.mkdir(parents=True,exist_ok=True)
        name=f"prices_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}_{uuid4().hex[:8]}.csv"
        with TemporaryDirectory(dir=folder) as temp:
            p=Path(temp)
            cleaned.to_parquet(p/'current.parquet',index=False,compression='zstd')
            report.update(source_archive=f'data/raw/snapshots/{name}',cleaned_at_utc=datetime.now(timezone.utc).isoformat())
            (p/'current.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            shutil.copy2(source,raw_folder/name)
            (p/'current.parquet').replace(folder/'current.parquet')
            quality=root/'data/quality';quality.mkdir(parents=True,exist_ok=True)
            (p/'current.json').replace(quality/'current.json')
    return len(raw),len(cleaned),len(report['issues'])
