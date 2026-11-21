"""Sources, quality, coverage and explicit optional updates."""
import json
import pandas as pd
import streamlit as st

def render(root):
    st.title('Données et méthode')
    st.caption('Sources, couverture, règles de calcul et mise à jour des fichiers locaux.')
    with st.container(border=True):
        st.subheader('Sources et couverture')
        st.link_button('Source officielle des prix et licence','https://www.data.gouv.fr/datasets/prix-des-carburants-en-france-flux-instantane-v2-amelioree')
        st.write('Les archives annuelles et le flux instantané sont conservés localement. Le flux nettoyé conserve ses 47 colonnes ; les historiques complets restent disponibles pour les notebooks.')
        paths=sorted((root/'data/quality').glob('[0-9][0-9][0-9][0-9].json'))
        reports=[json.loads(p.read_text(encoding='utf-8')) for p in paths]
        if reports:
            table=pd.DataFrame(reports)
            cols=[c for c in ['year','station_count','source_price_elements','retained_rows','first_price_date','last_price_date'] if c in table]
            st.dataframe(table[cols].rename(columns={'year':'Année','station_count':'Stations sources','source_price_elements':'Déclarations sources','retained_rows':'Lignes conservées','first_price_date':'Première déclaration','last_price_date':'Dernière déclaration'}),hide_index=True,alt='Couverture des archives locales par année')
            year=st.selectbox('Rapport qualité à consulter',[r['year'] for r in reports],key='quality_report_year')
            with st.expander('Rapport qualité complet'):st.json(next(r for r in reports if r['year']==year))
        else:st.info('Aucun rapport annuel disponible localement.')
    with st.container(border=True):
        st.subheader('Comment les prix sont calculés')
        st.write('Une station compte une fois par jour et par carburant : dernière déclaration du jour uniquement. Si elle est invalide, un ancien prix ne la remplace pas. Aucun prix n’est reporté aux jours suivants.')
        st.write('Les doublons exacts ne comptent qu’une fois. Les déclarations invalides, contradictoires ou hors année sont exclues des analyses. Le seuil de 0,20 à 5 €/L est une règle de prudence pour les prix atypiques, pas une norme officielle. Les observations sources restent conservées.')
        st.write('Évolution et grille : moyenne mensuelle des moyennes quotidiennes. Carte : moyenne des moyennes quotidiennes régionales sur toute la période, avec des contours régionaux de 2026. Les coordonnées servent au rattachement ; les stations non localisables ne participent pas à la carte.')
        st.write('Budget : moyenne des moyennes quotidiennes sur la période choisie, appliquée aux kilomètres et à la consommation saisis. Le territoire est déduit du code postal ; 20 regroupe la Corse. Le scénario de variation est une hypothèse, pas une prévision.')
        st.write('Prédiction : gradient boosting comparé à une référence saisonnière. Validation chronologique, puis test final séparé. L’entraînement est arrêté à octobre 2026 et les prévisions couvrent novembre 2026 à octobre 2027. Les bandes d’erreur sont indicatives.')
        st.caption('Prix nominaux, non pondérés par les ventes. Le panel de stations varie. Les courbes ne prouvent pas la cause politique ou économique des variations. Une absence de déclaration ne prouve ni fermeture ni rupture.')
        with st.expander('Attribution du fond géographique'):
            source=root/'assets/maps/SOURCE.md'
            if source.exists():st.text(source.read_text(encoding='utf-8'))
    with st.container(border=True):
        st.subheader('Mise à jour des données')
        st.write('La consultation fonctionne hors ligne. La mise à jour nécessite Internet et peut prendre plusieurs minutes. Ferme les notebooks qui utilisent les fichiers avant de la lancer.')
        if st.button('Mettre à jour les données',icon=':material/refresh:',key='update_local_data'):
            from scripts.update_local import update
            try:
                with st.spinner('Téléchargement et préparation des sources officielles…'):update(root)
                st.cache_data.clear()
                st.success('Données mises à jour. Les synthèses seront recalculées à la prochaine consultation.')
                st.rerun()
            except Exception:
                st.error('Mise à jour non terminée. Vérifie ta connexion et les fichiers locaux. Les données précédentes restent consultables après un échec réseau.')
