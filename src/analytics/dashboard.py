"""Local-only historical daily aggregates for the dashboard."""
import pandas as pd


def department(postal):
    code = postal.astype("string").str.strip()
    result = code.str[:2].where(code.str.fullmatch(r"[0-9]{5}", na=False))
    return result.mask(code.str.startswith(("97", "98"), na=False), code.str[:3])


def prepare(prices, stations, start, end):
    frame = prices.copy()
    invalid = frame["suspect_price"] | frame["outside_archive_year"] | frame.duplicated(["station_id", "price_reported_at"], keep=False)
    frame.loc[invalid, "price_eur_l"] = -1.0
    frame["day"] = frame["price_reported_at"].dt.normalize()
    frame = frame.sort_values("price_reported_at").drop_duplicates(["station_id", "day"], keep="last")
    dates = pd.date_range(pd.Timestamp(start), end)
    wide = frame.pivot(index="day", columns="station_id", values="price_eur_l").reindex(dates)
    wide = wide.loc[pd.Timestamp(start):].where(lambda x: x > 0)
    # Last-date map uses exactly the same eligibility as the daily calculations.
    latest = frame.loc[frame["day"].le(pd.Timestamp(end))].drop_duplicates("station_id", keep="last")
    latest = latest[["station_id", "price_reported_at"]]
    points = wide.iloc[-1].dropna().rename("Prix (€/L)").rename_axis("station_id").reset_index()
    points = points.merge(stations, on="station_id", validate="one_to_one").merge(latest, on="station_id", validate="one_to_one")
    return wide, points


def summarize(wide):
    return pd.DataFrame({"Date":wide.index, "Prix moyen (€/L)":wide.mean(axis=1).values, "Stations":wide.count(axis=1).values})
