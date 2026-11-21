"""Small, versioned local aggregates for the overview; source history is unchanged."""
from pathlib import Path
import hashlib
import json
import os
import uuid
import numpy as np
import pandas as pd
from matplotlib.path import Path as PolygonPath
from src.analytics.data import read_prices, read_stations
from src.processing.quality_rules import FUELS, POLICY_VERSION

FUELS_ORDER = ['Gazole','SP95','SP98','E10','E85','GPLc']

def polygons(feature):
    g = feature['geometry']
    return [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']

def attach_regions(stations, regions):
    points = stations[['longitude','latitude']].to_numpy(dtype=float, na_value=np.nan)
    matches = np.zeros(len(stations), dtype=int)
    codes = np.full(len(stations), None, dtype=object)
    for region in regions:
        inside = np.zeros(len(stations), dtype=bool)
        for rings in polygons(region):
            exterior = np.asarray(rings[0])
            candidates = (np.isfinite(points).all(axis=1) &
                (points[:,0] >= exterior[:,0].min()) & (points[:,0] <= exterior[:,0].max()) &
                (points[:,1] >= exterior[:,1].min()) & (points[:,1] <= exterior[:,1].max()))
            idx = np.flatnonzero(candidates)
            hit = PolygonPath(exterior).contains_points(points[idx])
            for hole in rings[1:]:
                hit &= ~PolygonPath(hole).contains_points(points[idx])
            inside[idx] |= hit
        matches += inside
        codes[inside] = region['properties']['code']
    codes[matches != 1] = None
    return pd.DataFrame({'station_id':stations['station_id'].to_numpy(), 'region':codes})


def signature(root, path):
    dependencies = [path, root/'data/quality'/f'{path.stem}.json',
                    root/'assets/maps/regions_france.geojson', Path(__file__),
                    root/'src/processing/quality_rules.py', root/'src/analytics/data.py']
    return hashlib.sha256((POLICY_VERSION + repr([(str(p.relative_to(root)),p.stat().st_size,p.stat().st_mtime_ns) for p in dependencies])).encode()).hexdigest()


def load_year(root, path):
    root, path = Path(root), Path(path)
    fingerprint = signature(root,path)
    cache = root/'data/analytics'/f'{path.stem}.json'
    if cache.exists():
        try:
            payload=json.loads(cache.read_text(encoding='utf-8'))
            if payload['signature']==fingerprint:
                return payload
        except (ValueError, KeyError): pass
    geometry=json.loads((root/'assets/maps/regions_france.geojson').read_text(encoding='utf-8'))
    regions=[f for f in geometry['features'] if len(f['properties']['code'])==2]
    mapping=attach_regions(read_stations(path),regions)
    report=json.loads((root/'data/quality'/f'{path.stem}.json').read_text(encoding='utf-8'))
    year=int(path.stem)
    cutoff=min(pd.Timestamp(report['last_price_date']).normalize(),pd.Timestamp(f'{year}-12-31'))
    dates=pd.date_range(f'{year}-01-01',cutoff)
    month_parts, region_parts=[],[]
    for fuel in FUELS_ORDER:
        events=read_prices(path,fuel)
        events['day']=events['price_reported_at'].dt.normalize()
        last=events.sort_values('price_reported_at').drop_duplicates(['station_id','day'],keep='last')
        valid=last.loc[last['analysis_eligible'],['station_id','day','price_eur_l']]
        daily=valid.groupby('day').agg(price=('price_eur_l','mean'),stations=('station_id','nunique')).reindex(dates)
        daily['stations']=daily['stations'].fillna(0)
        monthly=daily.resample('MS').agg(price=('price','mean'),days=('price','count'),stations=('stations','mean'))
        monthly['partial']=daily.resample('MS').size()<monthly.index.days_in_month
        monthly['fuel']=fuel
        month_parts.append(monthly.rename_axis('month').reset_index())
        located=valid.merge(mapping.dropna(subset=['region']),on='station_id',validate='many_to_one')
        daily_region=located.groupby(['region','day']).agg(price=('price_eur_l','mean'),stations=('station_id','nunique')).reset_index()
        summary=daily_region.groupby('region').agg(total_daily_price=('price','sum'),days=('price','count'),station_days=('stations','sum'),first_date=('day','min'),last_date=('day','max')).reset_index()
        summary['fuel']=fuel
        region_parts.append(summary)
    payload={'signature':fingerprint,'year':year,'last_date':str(cutoff.date()),
             'unmapped_stations':int(mapping.region.isna().sum()),
             'monthly':json.loads(pd.concat(month_parts).to_json(orient='records',date_format='iso')),
             'regional':json.loads(pd.concat(region_parts).to_json(orient='records',date_format='iso'))}
    if signature(root,path)!=fingerprint: raise RuntimeError('Les sources ont changé pendant le calcul. Relancer après la mise à jour.')
    cache.parent.mkdir(parents=True,exist_ok=True)
    temporary=cache.with_name(cache.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        os.replace(temporary,cache)
    finally:
        if temporary.exists():temporary.unlink()
    return payload


def combine(payloads):
    monthly=pd.DataFrame([r for p in payloads for r in p['monthly']])
    monthly['month']=pd.to_datetime(monthly['month'])
    rows=pd.DataFrame([r for p in payloads for r in p['regional']])
    if rows.empty:
        return monthly,pd.DataFrame(columns=['region','fuel','price','days','stations','first_date','last_date'])
    regional=rows.groupby(['region','fuel']).agg(total_daily_price=('total_daily_price','sum'),days=('days','sum'),station_days=('station_days','sum'),first_date=('first_date','min'),last_date=('last_date','max')).reset_index()
    regional['price']=regional.total_daily_price/regional.days
    regional['stations']=regional.station_days/regional.days
    return monthly,regional
