"""Historical budget scenarios, separated from navigation and methodology."""
import json
import pandas as pd
import streamlit as st
from src.analytics.dashboard import prepare, summarize, department
from src.analytics.data import read_stations, read_prices

@st.cache_data(max_entries=3)
def load_stations(path, modified):
    result = read_stations(path)
    result["Territoire"] = department(result["postal_code"])
    return result


@st.cache_data(max_entries=2)
def load_year(path, modified, fuel, station_path, station_modified, start, end):
    prices = read_prices(path, fuel)
    stations = load_stations(station_path, station_modified)
    return prepare(prices, stations, start, end)



def render(root):
    ROOT = root
    ANNUAL = ROOT / "data/cleaned/historical"
    st.title("Budget carburant")
    st.caption("Estimer un budget à partir des prix historiques et de tes hypothèses de trajet.")
    years = sorted(int(p.stem) for p in ANNUAL.glob("*.parquet") if (ROOT / "data/quality" / f"{p.stem}.json").exists()) if ANNUAL.exists() else []
    if not years:
        st.error("Aucune archive locale trouvée. Place le dossier data à côté de app.py.")
        st.stop()
    a,b,c,d = st.columns(4)
    year = a.selectbox("Année", years, index=years.index(2022) if 2022 in years else len(years)-1, key="year")
    folder = ANNUAL
    try:
        report = json.loads((ROOT / "data/quality" / f"{year}.json").read_text(encoding="utf-8"))
        station_path = folder / f"{year}.parquet"
        stations = load_stations(str(station_path), station_path.stat().st_mtime)
    except (OSError, ValueError, ImportError):
        st.error("Archive illisible : vérifie les fichiers locaux et les dépendances Python.")
        st.stop()
    fuels = sorted(report["fuel_counts"])
    fuel = b.selectbox("Carburant", fuels, index=fuels.index("Gazole") if "Gazole" in fuels else 0, key="fuel")
    territory = c.selectbox("Territoire · code postal", ["France"] + sorted(stations["Territoire"].dropna().unique()), key="territory")
    road = d.selectbox("Réseau", ["Tous", "Route", "Autoroute"], key="road")
    first = pd.Timestamp(year=year, month=1, day=1).date()
    last = min(pd.Timestamp(year=year, month=12, day=31), pd.Timestamp(report["last_price_date"])).date()
    a,c = st.columns([3,1])
    period = a.date_input("Période", (first,last), min_value=first, max_value=last, key=f"period_{year}")
    litres = c.number_input("Volume du plein (L)", 1, 200, 50, key="litres")
    st.caption("Calcul : déclarations du jour uniquement, sans prolongement. Une station sans déclaration ce jour-là est absente de la moyenne.")
    st.caption(f"Archive {year} • Dernière déclaration : {report['last_price_date']} • Les résultats décrivent des prix historiques, pas des prix en direct.")
    if len(period)!=2 or period[0]>period[1]:
        st.info("Sélectionne le début et la fin de la période.")
        st.stop()
    try:
        path=folder / f"{year}.parquet"
        with st.spinner("Calcul des prix et de la couverture…"):
            wide, points = load_year(str(path),path.stat().st_mtime,fuel,str(station_path),station_path.stat().st_mtime,*period)
    except (OSError, ValueError, ImportError):
        st.error("Impossible de charger les prix locaux pour cette sélection.")
        st.stop()
    network = stations if road=="Tous" else stations.loc[stations["road_type"].eq("R" if road=="Route" else "A")]
    national = wide.loc[:,wide.columns.intersection(network["station_id"])].mean(axis=1)
    selected_stations = network if territory=="France" else network.loc[network["Territoire"].eq(territory)]
    selected = wide.loc[:,wide.columns.intersection(selected_stations["station_id"])]
    daily = summarize(selected)
    valid = daily.dropna(subset=["Prix moyen (€/L)"])
    if valid.empty:
        st.info("Aucun prix exploitable pour cette sélection. Change le carburant, le réseau ou la période.")
        st.stop()
    start_price,end_price = valid["Prix moyen (€/L)"].iloc[[0,-1]]
    mean = valid["Prix moyen (€/L)"].mean()
    gap = (selected.mean(axis=1)-national).mean()*100
    with st.container(horizontal=True):
        st.metric("Prix moyen de période",f"{mean:.3f} €/L",border=True)
        st.metric("Variation début / fin",f"{(end_price-start_price)*100:+.1f} c€/L",border=True)
        st.metric("Écart national",f"{gap:+.1f} c€/L",border=True)
        st.metric("Stations couvertes",f"{selected.notna().any().sum():,}",border=True)
        st.metric(f"Plein de {litres} L · fin",f"{end_price*litres:.2f} €",border=True)
    st.caption(f"Variation et plein : du {valid['Date'].iloc[0]:%d/%m/%Y} au {valid['Date'].iloc[-1]:%d/%m/%Y}. {len(valid)} jours couverts sur {len(daily)}.")
    st.subheader("Prévoir une enveloppe mensuelle")
    km=st.number_input("Kilomètres par mois",0,50000,1000,100,key="km")
    consumption=st.number_input("Consommation (L/100 km)",0.1,50.0,6.0,0.1,key="consumption")
    shock=st.slider("Scénario de variation du prix (%)",-50,100,10,key="shock")
    base=km*consumption/100*mean
    a,b=st.columns(2)
    a.metric("Budget de référence",f"{base:.2f} €/mois")
    b.metric("Budget du scénario",f"{base*(1+shock/100):.2f} €/mois")
    st.caption("Hypothèses saisies par l’utilisateur, appliquées au prix moyen historique sélectionné. Ce scénario n’est pas une prévision.")
    st.download_button("Exporter les prix moyens et la couverture",daily.to_csv(index=False).encode("utf-8-sig"),f"analyse_{year}_{fuel}_{territory}.csv","text/csv")
