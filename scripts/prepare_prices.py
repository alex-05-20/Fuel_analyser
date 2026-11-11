from pathlib import Path
import argparse

from src.pipeline import publish_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Préparer et historiser les prix.")
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    stations, rows, added = publish_snapshot(args.source, root)
    print(f"{stations} stations, {rows} lignes actuelles, {added} nouvelles observations historiques.")


if __name__ == "__main__":
    main()
