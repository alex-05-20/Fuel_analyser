"""Availability declared in the current snapshot, not inferred from prices."""
import re
import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from src.analytics.overview_charts import COLORS, finish


def summarize_availability(frame):
    data=frame[['id','Carburants disponibles']].copy()
    data['id']=data['id'].astype('string').str.strip()
    valid=data['id'].str.fullmatch(r'[0-9]+',na=False)
    invalid_rows=int((~valid).sum())
    data=data.loc[valid]
    names={name.casefold():name for name in COLORS}
    def parse(value):
        if pd.isna(value) or not str(value).strip():return None
        tokens={p.strip().casefold() for p in re.split('[,;]',str(value)) if p.strip()}
        if not tokens or not tokens.issubset(names):return None
        return tuple(sorted(names[t] for t in tokens))
    data['available']=data['Carburants disponibles'].map(parse)
    pairs=[];missing=0;conflicts=0
    for station,group in data.groupby('id'):
        declarations=set(group.available)
        if len(declarations)>1:
            conflicts+=1;continue
        fuels=next(iter(declarations))
        if fuels is None:missing+=1;continue
        pairs.extend((station,fuel) for fuel in fuels)
    total=int(data.id.nunique())
    counts=pd.DataFrame(pairs,columns=['station','fuel']).groupby('fuel').station.nunique().reindex(list(COLORS),fill_value=0)
    result=counts.rename('stations').rename_axis('fuel').reset_index()
    result['station_percent']=result.stations/total*100 if total else 0.
    return result,{'total':total,'missing':missing,'conflicts':conflicts,'invalid_rows':invalid_rows}


@st.cache_data(max_entries=2,show_spinner=False)
def load_snapshot(path,stamp,field='Carburants disponibles'):
    frame=pd.read_parquet(path,columns=['id',field]).rename(columns={field:'Carburants disponibles'})
    return summarize_availability(frame)


def render_available(root):
    with st.container(border=True):
        st.subheader('Carburants déclarés disponibles dans les stations')
        st.caption('France · Dernière collecte locale · Tous les carburants, indépendamment du sélecteur de la carte')
        path=root/'data/cleaned/current.parquet'
        if not path.exists():
            st.info('Le fichier instantané local est absent.');return
        try:
            counts,quality=load_snapshot(str(path),(path.stat().st_mtime_ns,path.stat().st_size))
        except (OSError,ValueError,ImportError,KeyError) as exc:
            st.error(f'Disponibilité non consultable : {exc}');return
        usable=counts.loc[counts.stations.gt(0)].sort_values('stations',ascending=False)
        if usable.empty:
            st.info('Aucune disponibilité déclarée exploitable dans cette collecte.')
        else:
            fig=go.Figure(go.Pie(labels=usable.fuel,values=usable.stations,sort=False,
                marker=dict(colors=[COLORS[f] for f in usable.fuel]),
                textinfo='label+percent',customdata=usable[['station_percent']].to_numpy(),
                hovertemplate='<b>%{label}</b><br>%{value:,.0f} stations<br>%{customdata[0]:.1f} % des stations couvertes<br>%{percent} des disponibilités déclarées<extra></extra>'))
            fig.update_layout(legend=dict(orientation='h'))
            st.plotly_chart(finish(fig,420),key='availability_pie',theme=None,width='stretch',alt='Répartition des couples station et carburant déclaré disponible dans la dernière collecte locale')
        st.caption('Chaque couple station–carburant compte une fois. Une station proposant quatre carburants contribue à quatre catégories. Les parts totalisent 100 % des disponibilités déclarées, pas 100 % des stations.')
        st.caption(f"{quality['total']:,} stations couvertes · {quality['missing']:,} avec information manquante ou non interprétable · {quality['conflicts']:,} avec déclarations contradictoires · {int(counts.stations.sum()):,} couples comptabilisés.")
        if quality['invalid_rows']:st.caption(f"{quality['invalid_rows']} lignes sans identifiant exploitable exclues.")
        st.caption('Une information manquante ne signifie pas une rupture. Le pourcentage de stations au survol utilise toutes les stations à identifiant valide de la collecte, y compris celles sans information de disponibilité.')
        report=root/'data/quality/current.json'
        if report.exists():
            try:
                metadata=json.loads(report.read_text(encoding='utf-8'))
                date=pd.to_datetime(metadata.get('cleaned_at_utc'),utc=True)
                if pd.notna(date):st.caption(f'Instantané local préparé le {date:%d/%m/%Y à %H:%M} UTC ; disponibilité déclarée, non vérifiée en temps réel.')
            except (ValueError,OSError):pass


def render_unavailable(root):
    with st.container(border=True):
        st.subheader('Carburants déclarés indisponibles')
        st.caption('France · Même collecte locale · Classement par nombre de stations')
        path=root/'data/cleaned/current.parquet'
        if not path.exists():
            st.info('Le fichier instantané local est absent.');return
        try:
            counts,quality=load_snapshot(str(path),(path.stat().st_mtime_ns,path.stat().st_size),'Carburants indisponibles')
        except (OSError,ValueError,ImportError,KeyError) as exc:
            st.error(f'Indisponibilité non consultable : {exc}');return
        ordered=counts.sort_values('stations',ascending=True)
        if not ordered.stations.sum():
            st.info('Aucune indisponibilité déclarée exploitable dans cette collecte.')
        else:
            fig=go.Figure(go.Bar(y=ordered.fuel,x=ordered.stations,orientation='h',
                marker_color=[COLORS[f] for f in ordered.fuel],
                text=ordered.stations,textposition='outside',cliponaxis=False,
                customdata=ordered[['station_percent']].to_numpy(),
                hovertemplate='<b>%{y}</b><br>%{x:,.0f} stations<br>%{customdata[0]:.1f} % des stations couvertes<extra></extra>'))
            fig.update_layout(xaxis_title='Nombre de stations',yaxis_title=None,
                              xaxis=dict(range=[0,max(ordered.stations)*1.18]))
            st.plotly_chart(finish(fig,420),key='unavailability_bar',theme=None,width='stretch',alt='Classement des carburants déclarés indisponibles par nombre de stations dans la dernière collecte locale')
        st.caption('Chaque station compte une fois par carburant déclaré indisponible. Une station peut figurer dans plusieurs barres.')
        st.caption(f"{quality['total']:,} stations couvertes · {quality['missing']:,} avec information manquante ou non interprétable · {quality['conflicts']:,} avec déclarations contradictoires.")
        st.caption('Source : champ « Carburants indisponibles ». Ce classement ne représente pas uniquement les ruptures temporaires. Une liste absente ne signifie ni disponibilité ni indisponibilité ; elle est comptée séparément.')


def render(root):
    left,right=st.columns(2)
    with left:render_available(root)
    with right:render_unavailable(root)
