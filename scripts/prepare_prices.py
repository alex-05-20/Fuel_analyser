from pathlib import Path
import argparse

from src.pipeline import publish_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Nettoyer l’instantané complet et archiver sa source.")
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    stations, rows, added = publish_snapshot(args.source, root)
    print(f"{stations} stations, {rows} lignes à 47 colonnes, {added} anomalies signalées.")


if __name__ == "__main__":
    main()
