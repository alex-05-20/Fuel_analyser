"""Read-only, bounded-memory quality audit of complete historical tables."""
from collections import Counter
import pandas as pd
import pyarrow.parquet as pq

FLAGS = ['invalid_price','invalid_date','unknown_fuel','suspect_price','outside_archive_year','duplicate_price','conflicting_price']
BASE = ['station_id','fuel','price_raw','date_raw','price_eur_l','price_reported_at','source_archive','source_station_index','source_price_index']
STATION = ['source_station_index','station_id','postal_code','latitude','longitude','latitude_raw','longitude_raw']


def audit_year(path, sample_size=10):
    counts = {}; examples = {flag: [] for flag in FLAGS}; sample_counts=Counter(); stations={}
    columns = list(dict.fromkeys(BASE + STATION + FLAGS + ['no_price']))
    total=0; placeholders=0
    for batch in pq.ParquetFile(path).iter_batches(batch_size=100000, columns=columns):
        frame=batch.to_pandas(); total+=len(frame); placeholders+=int(frame['no_price'].sum())
        for row in frame[STATION].drop_duplicates('source_station_index').to_dict('records'):
            stations.setdefault(row['source_station_index'],row)
        declarations=frame.loc[~frame['no_price']].copy()
        declarations['fuel']=declarations['fuel'].fillna('(absent)')
        for fuel,group in declarations.groupby('fuel'):
            counter=counts.setdefault(fuel,Counter())
            counter['declarations']+=len(group)
            counter['au_moins_un_signalement']+=int(group[FLAGS].any(axis=1).sum())
            for flag in FLAGS:counter[flag]+=int(group[flag].sum())
        for flag in FLAGS:
            room=sample_size-sample_counts[flag]
            if room>0:
                sample=frame.loc[frame[flag],BASE+[flag]].head(room)
                examples[flag].append(sample);sample_counts[flag]+=len(sample)
    summary=pd.DataFrame.from_dict(counts,orient='index').rename_axis('fuel').reset_index()
    for flag in FLAGS+['au_moins_un_signalement']:
        summary[flag+'_pct']=summary[flag]/summary['declarations']*100 if not summary.empty else pd.Series(dtype=float)
    station_frame=pd.DataFrame(stations.values())
    station_frame['code_postal_a_verifier']=~station_frame['postal_code'].astype('string').str.fullmatch(r'[0-9]{5}',na=False)
    station_frame['coordonnees_absentes']=station_frame[['latitude','longitude']].isna().any(axis=1)
    station_frame['coordonnees_zero']=station_frame['latitude'].eq(0)|station_frame['longitude'].eq(0)
    station_frame['identifiant_absent_ou_repete']=station_frame['station_id'].isna()|station_frame['station_id'].duplicated(keep=False)
    return {'rows':total,'no_price':placeholders,'summary':summary,'stations':station_frame,
            'examples':{flag:pd.concat(parts,ignore_index=True) if parts else pd.DataFrame(columns=BASE+[flag]) for flag,parts in examples.items()}}
