"""Versioned quality decisions; complete source tables are never overwritten here."""
import json
import numpy as np
import pandas as pd

POLICY_VERSION = "2026-11-17.1"
FUELS = {"1":"Gazole", "2":"SP95", "3":"E85", "4":"GPLc", "5":"E10", "6":"SP98"}
CANONICAL = {value.casefold():value for value in FUELS.values()}
BLOCKING = ["dq_no_price", "dq_invalid_id", "dq_invalid_fuel", "dq_fuel_mismatch", "dq_invalid_date", "dq_outside_year", "dq_invalid_price", "dq_atypical_price", "dq_conflict"]


def assess_prices(frame):
    """Annotate an analytical copy, keeping invalid last-day events as barriers."""
    out = frame.copy()
    out['station_id'] = out['station_id'].astype('string').str.strip()
    out['fuel'] = out['fuel'].astype('string').str.strip().str.casefold().map(CANONICAL).astype('string')
    out['dq_invalid_id'] = ~out['station_id'].str.fullmatch(r'[0-9]+', na=False)
    out['dq_invalid_fuel'] = out['fuel'].isna()
    out['dq_fuel_mismatch'] = False
    if 'fuel_code' in out:
        expected = out['fuel_code'].astype('string').str.strip().map(FUELS)
        out['dq_fuel_mismatch'] = expected.notna() & out['fuel'].notna() & expected.ne(out['fuel'])
    out['dq_no_price'] = out.get('no_price',pd.Series(False,index=out.index)).fillna(False).astype(bool)
    out['dq_invalid_date'] = out['price_reported_at'].isna()
    out['dq_outside_year'] = False
    if 'archive_year' in out:
        out['dq_outside_year'] = out['price_reported_at'].notna() & out['price_reported_at'].dt.year.ne(out['archive_year'])
    else:
        out['dq_outside_year'] = out.get('outside_archive_year',False)
    number = pd.to_numeric(out['price_eur_l'],errors='coerce')
    out['price_eur_l'] = number
    out['dq_invalid_price'] = number.isna() | ~np.isfinite(number) | number.le(0)
    out['dq_atypical_price'] = ~out['dq_invalid_price'] & ~number.between(.2,5)
    keys = ['station_id','fuel','price_reported_at']
    usable_key = ~out[['dq_invalid_id','dq_invalid_fuel','dq_invalid_date']].any(axis=1)
    out['dq_conflict'] = False
    # Numeric equivalence matters: 1.50 and 1.500 are not conflicting prices.
    conflicts = out.loc[usable_key].groupby(keys,dropna=False)['price_eur_l'].transform('nunique',dropna=False).gt(1)
    out.loc[usable_key,'dq_conflict'] = conflicts
    out['dq_duplicate'] = usable_key & out.duplicated(keys+['price_eur_l'],keep='first')
    out['analysis_eligible'] = ~out[BLOCKING+['dq_duplicate']].any(axis=1)
    return out


def analytical_events(frame):
    out=assess_prices(frame)
    # Without identity/date, an event cannot be assigned to a daily station series.
    out=out.loc[~out[['dq_no_price','dq_invalid_id','dq_invalid_fuel','dq_invalid_date','dq_outside_year','dq_duplicate']].any(axis=1)].copy()
    # Keep an invalid/conflicting final event so an earlier same-day price is not revived.
    out['suspect_price'] = ~out['analysis_eligible']
    out['outside_archive_year'] = out['dq_outside_year']
    return out


def clean_station_view(frame):
    out=frame.copy()
    out['station_id']=out['station_id'].astype('string').str.strip()
    out=out.loc[out['station_id'].str.fullmatch(r'[0-9]+',na=False)]
    for name in ['city','address','postal_code','road_type']:
        if name in out:out[name]=out[name].astype('string').str.strip().replace('',pd.NA)
    if 'postal_code' in out:
        # Do not invent missing digits from a malformed code.
        out['postal_code']=out['postal_code'].where(out['postal_code'].str.fullmatch(r'[0-9]{5}',na=False))
    if 'road_type' in out:
        out['road_type']=out['road_type'].str.upper().where(out['road_type'].str.upper().isin(['R','A']))
    lat=pd.to_numeric(out['latitude'],errors='coerce');lon=pd.to_numeric(out['longitude'],errors='coerce')
    bad=~lat.between(-90,90)|~lon.between(-180,180)|(lat.eq(0)&lon.eq(0))
    out['map_eligible']=~bad
    out.loc[bad,['latitude','longitude']]=float('nan')
    # A source ID with contradictory station metadata is not resolved by taking the last row.
    unique=out.drop_duplicates()
    conflicting=unique['station_id'].duplicated(keep=False)
    if not conflicting.any(): return unique
    ambiguous = unique.loc[conflicting].drop_duplicates('station_id').copy()
    for name in ['postal_code','city','address','road_type','latitude','longitude']:
        if name in ambiguous: ambiguous[name] = None
    ambiguous['map_eligible'] = False
    return pd.concat([unique.loc[~conflicting], ambiguous], ignore_index=True)


def parse_intervals(value):
    """Classify source intervals; no inference of missing end dates or timezones."""
    records=[]
    if value is None or pd.isna(value):return pd.DataFrame()
    try:
        elements = json.loads(value)
        if not isinstance(elements, list): raise ValueError('Expected list')
    except (ValueError, TypeError):
        return pd.DataFrame([{'invalid_json': True, 'interval_eligible': False}])
    for element in elements:
        if not isinstance(element, dict):
            records.append({'invalid_json': True, 'interval_eligible': False})
            continue
        attrs=element.get('attributes',{})
        row={'kind':element.get('tag'),**attrs}
        for source,target in [('debut','start'),('fin','end')]:
            text=attrs.get(source)
            row[target+'_absent']=text is None or not str(text).strip()
            try:parsed=pd.Timestamp(text) if not row[target+'_absent'] else pd.NaT
            except (ValueError,TypeError,OverflowError):parsed=pd.NaT
            row[target]=parsed
            row[target+'_invalid']=not row[target+'_absent'] and pd.isna(parsed)
        row['end_before_start']=False;row['timezone_mismatch']=False
        if pd.notna(row['start']) and pd.notna(row['end']):
            try:row['end_before_start']=row['end']<row['start']
            except TypeError:row['timezone_mismatch']=True
        row['interval_eligible']=not (row['start_absent'] or row['start_invalid'] or row['end_invalid'] or row['end_before_start'] or row['timezone_mismatch'])
        records.append(row)
    return pd.DataFrame(records)
