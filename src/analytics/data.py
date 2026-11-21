"""Analytical views derived in memory from the complete cleaned historical table."""
import pandas as pd
from src.processing.quality_rules import analytical_events, clean_station_view
STATION_COLUMNS=['station_id','postal_code','city','address','road_type','latitude','longitude']
PRICE_COLUMNS=['station_id','fuel','price_eur_l','price_reported_at','suspect_price','outside_archive_year','invalid_price','invalid_date','unknown_fuel','no_price','conflicting_price','fuel_code','archive_year']


def read_stations(path):
    return clean_station_view(pd.read_parquet(path,columns=STATION_COLUMNS).drop_duplicates())


def read_prices(path,fuel):
    frame=pd.read_parquet(path,columns=PRICE_COLUMNS,filters=[('fuel','==',fuel)])
    return analytical_events(frame)
