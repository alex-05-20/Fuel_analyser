"""Prepare local overview caches. No download and no source changes."""
from pathlib import Path
from src.analytics.overview_data import load_year

def main():
    root=Path(__file__).resolve().parents[1]
    for path in sorted((root/'data/cleaned/historical').glob('[0-9][0-9][0-9][0-9].parquet')):
        load_year(root,path)
        print(f'{path.stem} : syntheses pretes',flush=True)

if __name__=='__main__': main()
