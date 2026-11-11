import pandas as pd


FUELS = ("Gazole", "SP95", "E85", "GPLc", "E10", "SP98")
STATION_COLUMNS = {
    "id": "station_id",
    "Ville": "city",
    "Code postal": "postal_code",
    "latitude": "latitude",
    "longitude": "longitude",
}


def normalize_prices(snapshot: pd.DataFrame) -> pd.DataFrame:
    """Return one row per station and reported fuel."""
    fuel_columns = [
        column
        for fuel in FUELS
        for column in (
            f"Prix {fuel}",
            f"Prix {fuel} mis à jour le",
            f"Type rupture {fuel if fuel == 'GPLc' else fuel.lower()}",
            f"Début rupture {fuel if fuel == 'GPLc' else fuel.lower()} (si temporaire)",
        )
    ]
    required = [*STATION_COLUMNS, "Carburants disponibles", *fuel_columns]
    missing = [column for column in required if column not in snapshot]
    if missing:
        raise ValueError(f"Colonnes manquantes dans le CSV : {', '.join(missing)}")

    stations = snapshot[list(STATION_COLUMNS)].rename(columns=STATION_COLUMNS)
    if stations["station_id"].isna().any() or stations["station_id"].duplicated().any():
        raise ValueError("Le CSV doit contenir un identifiant unique par station.")

    for column in ("latitude", "longitude"):
        stations[column] = pd.to_numeric(stations[column], errors="coerce")

    available_fuels = snapshot["Carburants disponibles"].fillna("").str.split(r"\s*[,;]\s*", regex=True)
    rows = []
    for fuel in FUELS:
        suffix = fuel if fuel == "GPLc" else fuel.lower()
        prices = pd.to_numeric(snapshot[f"Prix {fuel}"], errors="coerce")
        rupture = snapshot[f"Type rupture {suffix}"].str.strip().str.lower()
        available = available_fuels.map(lambda values: fuel in values)
        status = pd.Series("unknown", index=snapshot.index, dtype="string")
        status.loc[available] = "available"
        status.loc[rupture.eq("temporaire").fillna(False)] = "temporary_outage"
        status.loc[rupture.eq("definitive").fillna(False)] = "permanent_outage"

        fuel_rows = stations.assign(
            fuel=fuel,
            price_eur_l=prices,
            price_reported_at=pd.to_datetime(
                snapshot[f"Prix {fuel} mis à jour le"], utc=True, format="ISO8601", errors="coerce"
            ),
            availability=status,
            outage_started_at=pd.to_datetime(
                snapshot[f"Début rupture {suffix} (si temporaire)"],
                utc=True,
                format="ISO8601",
                errors="coerce",
            ).where(status.eq("temporary_outage")),
        )
        rows.append(fuel_rows.loc[available | prices.notna() | rupture.notna()])

    return pd.concat(rows, ignore_index=True)
