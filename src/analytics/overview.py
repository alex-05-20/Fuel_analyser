"""New dark overview, three Plotly tabs and reserved chart spaces."""
import json
import pandas as pd
import streamlit as st
from src.analytics.overview_data import load_year, signature, combine, FUELS_ORDER
from src.analytics.overview_charts import evolution_chart, regional_chart, grid_chart

@st.cache_data(max_entries=2,show_spinner=False)
def load_overview(root, stamps):
    files=sorted((root/'data/cleaned/historical').glob('[0-9][0-9][0-9][0-9].parquet'))
    return combine([load_year(root,p) for p in files])


@st.cache_data(max_entries=20,show_spinner=False)
def load_map_year(root, path, stamp):
    return combine([load_year(root,path)])


def fuel_selector(label, key, options=None):
    options = FUELS_ORDER if options is None else options
    saved = 'saved_' + key
    if key not in st.session_state:
        st.session_state[key] = st.session_state.get(saved, options[0])
    def remember():
        st.session_state[saved] = st.session_state[key]
    return st.selectbox(label, options, key=key, on_change=remember)


def reserved(count=2):
    with st.container(horizontal=True):
        for _ in range(count):
            with st.container(border=True,height=140):
                st.caption('ESPACE RÉSERVÉ')
                st.write('Prochain graphique')
                st.caption('À définir ensemble')


def render(root):
    st.title('Prix des carburants en France')
    st.caption('Évolution des prix · Comparaison des régions · Lecture mois par mois')
    files=sorted((root/'data/cleaned/historical').glob('[0-9][0-9][0-9][0-9].parquet'))
    if not files:
        st.info('Aucune archive locale disponible. Prépare les données pour afficher les graphiques.')
        return
    try:
        stamps=tuple(signature(root,p) for p in files)
        with st.spinner('Préparation des synthèses locales. Le premier calcul peut prendre plusieurs minutes…'):
            monthly,regional=load_overview(root,stamps)
        geometry=json.loads((root/'assets/maps/regions_france.geojson').read_text(encoding='utf-8'))
    except (OSError,ValueError,ImportError,RuntimeError) as exc:
        st.error('Impossible de préparer les graphiques. Vérifie les données locales et utilise le Python du projet.')
        with st.expander('Détail du problème'):st.code(str(exc))
        return
    reports=[json.loads((root/'data/quality'/f'{p.stem}.json').read_text(encoding='utf-8')) for p in files]
    end=max(pd.Timestamp(r['last_price_date']) for r in reports)
    st.caption(f"{files[0].stem}–{files[-1].stem} · 6 carburants · Dernière déclaration : {end:%d/%m/%Y} · Données locales")
    evolution,carte,grille=st.tabs(['Évolution','Carte','Grille'],key='overview_tab',on_change='rerun')
    if evolution.open:
        with evolution:
            with st.container(border=True):
                st.subheader('Tous les carburants, toutes les années')
                st.caption('Prix mensuels moyens en €/L. Clique sur la légende pour masquer ou isoler une courbe.')
                st.plotly_chart(evolution_chart(monthly),key='fuel_evolution',theme=None,width='stretch',alt='Évolution mensuelle des prix des six carburants sur toutes les années disponibles')
            reserved()
    if carte.open:
        with carte:
            with st.container(border=True):
                st.subheader('Écarts de prix par région')
                year_control,fuel_control=st.columns(2)
                with year_control: year=fuel_selector('Année de la carte','map_year_filter',['Toutes les années']+[p.stem for p in files])
                with fuel_control: fuel=fuel_selector('Carburant de la carte','map_fuel_filter',['Tous les carburants']+FUELS_ORDER)
                if year=='Toutes les années':map_monthly,map_regional=monthly,regional
                else:
                    path=root/'data/cleaned/historical'/f'{year}.parquet'
                    map_monthly,map_regional=load_map_year(root,str(path),signature(root,path))
                st.caption(f'{year} · {fuel} · Bleu : moins cher que la moyenne nationale ; rouge : plus cher.')
                if map_regional.empty:st.info('Aucun prix rattaché à une région pour cette sélection.')
                else:st.plotly_chart(regional_chart(map_regional,geometry,fuel,map_monthly),key='fuel_map',theme=None,width='stretch',config={'scrollZoom':True,'displayModeBar':True,'displaylogo':False},alt=f'Écarts régionaux à la moyenne nationale : {fuel}, {year}')
                st.caption('Survole une région pour les prix réels en €/L et la couverture. Molette : zoom ; glisser : déplacement ; double-clic : réinitialiser.')
                st.caption('Tous les carburants : moyenne à poids égaux des écarts de chaque carburant à sa propre moyenne nationale. Seuls les carburants renseignés participent ; leur nombre figure au survol.')
                st.caption('Métropole et Corse. Contraste non linéaire renforcé près de zéro : les petites différences sont plus visibles, sans modifier les valeurs en %. L’échelle reste symétrique et dépend de la sélection. Gris : sans données. Les régions peuvent couvrir des jours et des carburants différents ; comparer leur couverture avant de conclure.')
                st.caption('Contours locaux 2026 : IGN / OpenStreetMap, ODbL. Outre-mer non affiché ; la référence nationale reste inchangée. Les graphiques de disponibilité ci-dessous restent ceux de la dernière collecte locale.')
            from src.analytics.availability import render as render_availability
            render_availability(root)
            reserved(count=1)
    if grille.open:
        with grille:
            with st.container(border=True):
                title,control=st.columns([3,1],vertical_alignment='bottom')
                title.subheader('Comparer les années mois par mois')
                with control: fuel=fuel_selector('Carburant de la grille','grid_fuel')
                st.caption(f'{fuel} · Une case par mois et par année · Couleur claire : prix plus élevé.')
                st.plotly_chart(grid_chart(monthly,fuel),key='fuel_grid',theme=None,width='stretch',alt=f'Prix mensuels du {fuel} en grille années par mois')
                st.caption('Case vide : aucune donnée exploitable ou mois non disponible. Les mois partiels sont signalés ci-dessous.')
            reserved()
    partial=monthly.loc[monthly['partial'] & monthly.price.notna(),'month'].drop_duplicates()
    if not partial.empty:st.caption('Mois partiels : '+', '.join(partial.dt.strftime('%m/%Y'))+'.')
    with st.expander('Comprendre les calculs'):
        st.write('Dernière déclaration de chaque station, carburant et jour. Si elle est invalide, aucun prix précédent ne la remplace. Aucun report aux jours suivants.')
        st.write('Courbes et grille : moyenne mensuelle des moyennes quotidiennes. Carte : moyenne des moyennes quotidiennes régionales sur les jours renseignés, avec les contours régionaux de 2026.')
        st.caption('Prix nominaux, sans pondération par les volumes vendus. Panel variable ; les écarts ne prouvent pas une causalité politique ou économique. Les prix hors de [0,20 ; 5] €/L et les contradictions sont exclus selon la politique de qualité du projet.')
