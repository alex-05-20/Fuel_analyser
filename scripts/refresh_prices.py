import json
import gzip
import io
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen

from src.pipeline import publish_snapshot



DATASET_URL = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "prix-des-carburants-en-france-flux-instantane-v2-amelioree/"
)


def download_snapshot(destination: Path) -> None:
    """Download the CSV resource advertised by the official dataset."""
    with urlopen(Request(DATASET_URL, headers={"User-Agent": "FuelAnalyser/1.0"}), timeout=60) as response:
        dataset = json.load(response)
    resources = [
        resource for resource in dataset["resources"]
        if resource.get("format", "").lower() == "csv"
    ]
    if len(resources) != 1:
        raise ValueError("Impossible d'identifier une ressource CSV unique.")
    request = Request(resources[0]["url"], headers={"User-Agent": "FuelAnalyser/1.0"})
    with urlopen(request, timeout=120) as response, destination.open("wb") as output:
        with io.BufferedReader(response) as stream:
            if stream.peek(2)[:2] == b"\x1f\x8b":
                with gzip.GzipFile(fileobj=stream) as decoded:
                    shutil.copyfileobj(decoded, output)
            else:
                shutil.copyfileobj(stream, output)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    raw = root / "data/raw"
    raw.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=raw) as temporary:
        downloaded = Path(temporary) / "prices_download.csv"
        download_snapshot(downloaded)
        stations, rows, added = publish_snapshot(downloaded, root)
    print(f"{stations} stations téléchargées, {rows} lignes à 47 colonnes, {added} anomalies signalées.")

if __name__ == "__main__":
    main()


