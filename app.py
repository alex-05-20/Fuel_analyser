"""Application shell: four pages, with independent page-specific controls."""
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='Fuel Analyser',page_icon=':material/local_gas_station:',layout='wide')
st.sidebar.title('FUEL ANALYSER')
st.sidebar.caption('Prix des carburants en France')

def analysis():
    from src.analytics.overview import render
    render(ROOT)

def prediction():
    from src.analytics.prediction_view import render
    render(ROOT)

def budget():
    from src.analytics.budget_view import render
    render(ROOT)

def method():
    from src.analytics.method_view import render
    render(ROOT)

page=st.navigation([
    st.Page(analysis,title='Analyse des prix',icon=':material/analytics:',default=True,help='Évolution des six carburants, carte régionale et grille années par mois.'),
    st.Page(prediction,title='Prédiction',icon=':material/query_stats:',url_path='prediction',help='Prévisions à douze mois et comparaison des modèles sur les données passées.'),
    st.Page(budget,title='Budget',icon=':material/calculate:',url_path='budget',help='Estimer un budget selon les prix historiques, les trajets et la consommation.'),
    st.Page(method,title='Données et méthode',icon=':material/database:',url_path='donnees',help='Consulter les sources, les contrôles qualité et actualiser les fichiers locaux.'),
])
st.sidebar.caption('Données locales · Source officielle')
page.run()
