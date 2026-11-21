import argparse
from pathlib import Path
from src.processing.annual import prepare_year


def main():
    parser=argparse.ArgumentParser(description="Extraire les historiques complets sans suppression de lignes")
    parser.add_argument('--year',type=int)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    archives=sorted((root/'data/raw/annual').glob('*.zip'))
    if args.year:archives=[p for p in archives if p.stem==str(args.year)]
    if not archives:parser.error('Aucune archive correspondante')
    for archive in archives:
        r=prepare_year(archive,root/'data/cleaned/historical'/f'{archive.stem}.parquet')
        print(f"{archive.stem}: {r['retained_rows']} lignes conservées, aucune suppression",flush=True)


if __name__=='__main__':main()
