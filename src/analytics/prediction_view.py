"""Prediction page, local training only and explicit historical error reporting."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from src.analytics.overview import load_overview
from src.analytics.overview_data import signature,FUELS_ORDER
from src.analytics.overview_charts import COLORS,finish
from src.analytics.forecasting import analyse_fuel,CUTOFF

@st.cache_data(max_entries=2,show_spinner=False)
def train_all(monthly):
    futures,tests,scores,errors=[],[],[],[]
    for fuel in FUELS_ORDER:
        try:
            future,test,score=analyse_fuel(monthly,fuel)
            futures.append(future);tests.append(test);scores.append(score)
        except ValueError as exc: errors.append(str(exc))
    return (pd.concat(futures,ignore_index=True) if futures else pd.DataFrame(),
            pd.concat(tests,ignore_index=True) if tests else pd.DataFrame(),pd.DataFrame(scores),errors)


def render(root):
    st.title('Prévision du prix des carburants')
    st.caption('12 mois · Novembre 2026 à octobre 2027 · Prix moyens nationaux en €/L')
    st.info('Estimations fondées uniquement sur les prix passés. Le modèle ne connaît pas les futures crises, taxes ou décisions politiques.')
    files=sorted((root/'data/cleaned/historical').glob('[0-9][0-9][0-9][0-9].parquet'))
    if not files:
        st.warning('Aucune archive locale disponible.');return
    try:
        with st.spinner('Validation chronologique et entraînement des six modèles…'):
            monthly,_=load_overview(root,tuple(signature(root,p) for p in files))
            future,test,scores,errors=train_all(monthly)
    except (OSError,ImportError,RuntimeError,ValueError) as exc:
        st.error(f'Prévisions indisponibles : {exc}');return
    for error in errors:st.warning(error)
    if future.empty:return
    mode=st.radio('Affichage',['Un carburant','Tous les carburants'],horizontal=True,key='prediction_mode')
    available=[f for f in FUELS_ORDER if f in set(future.fuel)]
    if mode=='Un carburant':chosen=[st.selectbox('Carburant',available,key='prediction_fuel')]
    else:chosen=available
    band=st.checkbox('Afficher les bandes d’erreur historiques',value=(mode=='Un carburant'),key='prediction_bands')
    with st.container(border=True):
        st.subheader('Historique et prévision à 12 mois')
        fig=go.Figure()
        for fuel in chosen:
            color=COLORS[fuel]
            past=monthly.loc[monthly.fuel.eq(fuel)&monthly.month.between(CUTOFF-pd.DateOffset(months=35),CUTOFF)&~monthly['partial']].sort_values('month')
            f=future.loc[future.fuel.eq(fuel)]
            fig.add_trace(go.Scatter(x=past.month,y=past.price,name=fuel+' · observé',line=dict(color=color),connectgaps=False,hovertemplate='%{x|%m/%Y}<br>%{y:.3f} €/L<extra>%{fullData.name}</extra>'))
            if band:
                fig.add_trace(go.Scatter(x=f.month,y=f.upper,mode='lines',line=dict(width=0),showlegend=False,hoverinfo='skip'))
                fig.add_trace(go.Scatter(x=f.month,y=f.lower,mode='lines',line=dict(width=0),fill='tonexty',fillcolor='rgba('+','.join(str(int(color[i:i+2],16)) for i in (1,3,5))+',0.13)',showlegend=False,hoverinfo='skip'))
            fig.add_trace(go.Scatter(x=f.month,y=f.prediction,name=fuel+' · ML',line=dict(color=color,dash='dash'),hovertemplate='%{x|%m/%Y}<br>%{y:.3f} €/L<extra>%{fullData.name}</extra>'))
            if len(chosen)==1:
                fig.add_trace(go.Scatter(x=f.month,y=f.reference,name='Référence saisonnière',line=dict(color='#AAAAAA',dash='dot')))
        fig.add_vline(x='2026-10-16',line_dash='dot',line_color='#999999')
        fig.update_layout(yaxis_title='Prix moyen nominal (€/L)',xaxis_title='Mois',legend=dict(orientation='h'),hovermode='x unified')
        st.plotly_chart(finish(fig,580),width='stretch',theme=None,key='prediction_chart',alt='Prix observés et prévisions mensuelles à douze mois des carburants sélectionnés')
        st.caption('Trait plein : prix observés ; tirets : gradient boosting. Entraînement arrêté à octobre 2026 ; novembre partiel exclu. Le graphique montre les 36 derniers mois observés, mais le modèle utilise tout l’historique consécutif exploitable.')
        if band:st.caption('Bande indicative : ± 90e percentile des erreurs absolues sur les 24 mois de validation. Ce n’est pas un intervalle de confiance garanti à 90 % ; elle peut sous-estimer une crise future et ne varie pas selon l’horizon.')
    st.subheader('Le modèle fait-il mieux qu’une référence simple ?')
    visible=scores.loc[scores.fuel.isin(chosen)].copy()
    weak=visible.loc[visible.test_coverage < .9]
    if not weak.empty:
        st.warning('Les bandes historiques ont une couverture insuffisante sur le test final : '+', '.join(f"{row.fuel} {row.test_coverage:.0%}" for row in weak.itertuples())+'. Elles ne constituent pas une fourchette fiable des futurs prix.')
    names={'fuel':'Carburant','validation_ml':'Validation · MAE ML (€/L)','validation_reference':'Validation · MAE référence (€/L)','test_ml':'Test · MAE ML (€/L)','test_reference':'Test · MAE référence (€/L)'}
    st.dataframe(visible[list(names)].rename(columns=names).round(3),hide_index=True,alt='Comparaison des erreurs du gradient boosting et de la référence saisonnière')
    worse=visible.loc[visible.test_ml>=visible.test_reference,'fuel'].tolist()
    if worse:st.warning('Sur le test final, le modèle ML ne surpasse pas la référence pour : '+', '.join(worse)+'. Ses prévisions ne doivent pas être considérées comme supérieures à cette référence.')
    st.caption('MAE : erreur absolue moyenne, plus petite = meilleure. Référence : répéter le prix du même mois de l’année précédente. Validation : novembre 2023–octobre 2025, deux fenêtres de 12 mois. Test final : novembre 2025–octobre 2026, tenu à l’écart de la validation.')
    with st.expander('Résultats détaillés et méthode'):
        st.write('Un gradient boosting par carburant, sans réglage sur les périodes de validation ou de test. Variables : prix retardés de 1, 2, 3, 6 et 12 mois, moyennes passées et calendrier saisonnier. Apprentissage du logarithme du prix ; prévisions récursives, sans utiliser les observations futures.')
        st.write('Après évaluation, chaque modèle est réentraîné sur les mois complets disponibles jusqu’à octobre 2026. Aucun prix manquant n’est inventé : une interruption limite l’entraînement à la dernière série mensuelle consécutive. Les prix sont nominaux et le panel de stations peut changer.')
        st.dataframe(visible[['fuel','training_start','months','band_width','test_coverage']].rename(columns={'fuel':'Carburant','training_start':'Début entraînement','months':'Mois utilisés','band_width':'Demi-largeur bande (€/L)','test_coverage':'Couverture constatée sur le test'}),hide_index=True,alt='Historique utilisé et couverture réelle des bandes sur le test final')
        st.dataframe(test.loc[test.fuel.isin(chosen)],hide_index=True,alt='Prévisions historiques à douze mois comparées aux prix réellement observés')
    export=future.loc[future.fuel.isin(chosen)]
    st.download_button('Télécharger les prévisions',export.to_csv(index=False).encode('utf-8-sig'),'previsions_nov2026_oct2027.csv','text/csv',key='download_predictions')
