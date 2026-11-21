"""Plotly figures using only local data and embedded polygon coordinates."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import sample_colorscale
from src.analytics.overview_data import FUELS_ORDER, polygons

COLORS = dict(zip(FUELS_ORDER,['#43CDE6','#F4C95D','#FF816C','#65D6A4','#B89AFF','#EBA5C9']))
MONTHS=['Jan','Fév','Mar','Avr','Mai','Juin','Juil','Août','Sep','Oct','Nov','Déc']
SCALE=[[0,'#183A45'],[.35,'#20899B'],[.7,'#62D7DF'],[1,'#FFE6A0']]

def finish(fig,height=530):
    fig.update_layout(template='plotly_dark',height=height,paper_bgcolor='#252628',plot_bgcolor='#252628',
                      font=dict(color='#EEEEF0',size=13),margin=dict(l=24,r=24,t=35,b=30))
    return fig


def evolution_chart(monthly):
    fig=go.Figure()
    dates=pd.date_range(monthly.month.min(),monthly.month.max(),freq='MS')
    for fuel in FUELS_ORDER:
        data=monthly.loc[monthly.fuel.eq(fuel)].set_index('month').reindex(dates)
        fig.add_trace(go.Scatter(x=dates,y=data.price,name=fuel,mode='lines',connectgaps=False,
            line=dict(color=COLORS[fuel],width=2.2),
            customdata=np.column_stack([data.days,data.stations]),
            hovertemplate='%{x|%m/%Y}<br>%{y:.3f} €/L<br>%{customdata[0]:.0f} jours avec prix<br>%{customdata[1]:.0f} stations/jour<extra>%{fullData.name}</extra>'))
    fig.update_layout(hovermode='x unified',legend=dict(orientation='h',y=1.14,x=0),
                      xaxis=dict(title='Année',gridcolor='#373A3E',rangeslider=dict(visible=True,thickness=.07)),
                      yaxis=dict(title='Prix moyen (€/L)',gridcolor='#373A3E',tickformat='.2f'))
    return finish(fig,550)


def grid_chart(monthly,fuel):
    selected=monthly.loc[monthly.fuel.eq(fuel)].copy()
    selected['year']=selected.month.dt.year
    selected['number']=selected.month.dt.month
    years=list(range(monthly.month.dt.year.min(),monthly.month.dt.year.max()+1))
    values=selected.pivot(index='year',columns='number',values='price').reindex(index=years,columns=range(1,13))
    days=selected.pivot(index='year',columns='number',values='days').reindex(index=years,columns=range(1,13))
    fig=go.Figure(go.Heatmap(z=values.to_numpy(dtype=float),x=MONTHS,y=[str(y) for y in years],
          colorscale=SCALE,hoverongaps=False,xgap=3,ygap=3,customdata=days.to_numpy(),
          colorbar=dict(title='€/L'),hovertemplate='%{x} %{y}<br>%{z:.3f} €/L<br>%{customdata:.0f} jours avec prix<extra>'+fuel+'</extra>'))
    fig.update_layout(yaxis=dict(title='Année',autorange='reversed',type='category'),xaxis=dict(side='top',title='Mois'))
    return finish(fig,max(540,len(years)*27))


def regional_comparison(monthly,regional,fuel='Tous les carburants'):
    observed=monthly.loc[monthly.price.notna() & monthly.days.gt(0)].copy()
    observed['total']=observed.price*observed.days
    national=observed.groupby('fuel').agg(total=('total','sum'),days=('days','sum'))
    national['national_price']=national.total/national.days
    detail=regional.merge(national[['national_price']],left_on='fuel',right_index=True,validate='many_to_one')
    if fuel!='Tous les carburants':detail=detail.loc[detail.fuel.eq(fuel)]
    detail['gap']=100*(detail.price/detail.national_price-1)
    return detail


def regional_chart(regional,geometry,fuel,monthly):
    mainland={'11','24','27','28','32','44','52','53','75','76','84','93','94'}
    regions=[f for f in geometry['features'] if f['properties']['code'] in mainland]
    fig=go.Figure()
    detail=regional_comparison(monthly,regional,fuel)
    detail=detail.loc[detail.region.isin(mainland)]
    selected=detail.groupby('region').gap.mean()
    bound=max(float(selected.abs().max()),.01) if not selected.empty else 1.
    low,high=-bound,bound
    # Monotonic, symmetric nonlinear contrast. Values and legend remain actual percentages.
    base_scale=[[0,'#1682FF'],[.5,'#E8E8E8'],[1,'#F02F43']]
    signed=np.linspace(-1,1,201)
    positions=.5+.5*np.sign(signed)*np.abs(signed)**3
    scale=[[float(t),sample_colorscale(base_scale,[float(.5+.5*np.sign(2*t-1)*abs(2*t-1)**.35)])[0]] for t in positions]
    for feature in regions:
        code=feature['properties']['code'];name=feature['properties']['nom']
        value=selected.get(code,np.nan)
        color=sample_colorscale(scale,[(value-low)/(high-low)])[0] if pd.notna(value) else '#505359'
        text=f'{name}<br>Écart national : {value:+.2f} %' if pd.notna(value) else f'{name}<br>Sans données exploitables'
        if pd.notna(value):
            rows=detail.loc[detail.region.eq(code)]
            text+=f'<br>{len(rows)} carburant(s) représenté(s)'
            for record in rows.itertuples():
                text+=f'<br>{record.fuel} : {record.price:.3f} €/L (France {record.national_price:.3f}) · {int(record.days)} jours · {record.stations:.0f} stations/jour'
        for rings in polygons(feature):
            ring=rings[0]
            fig.add_trace(go.Scatter(x=[p[0] for p in ring],y=[p[1] for p in ring],mode='lines',
                fill='toself',fillcolor=color,line=dict(color='#252628',width=.7),
                hoveron='fills',hovertemplate=text+'<extra></extra>',name=name,showlegend=False))
            for hole in rings[1:]:
                fig.add_trace(go.Scatter(x=[p[0] for p in hole],y=[p[1] for p in hole],mode='lines',fill='toself',
                    fillcolor='#252628',line=dict(width=0),hoverinfo='skip',showlegend=False))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_xaxes(range=[-5.5,10])
    fig.update_yaxes(range=[41,51.5],scaleanchor='x',scaleratio=1/np.cos(np.radians(46.5)))
    # Invisible markers carry the common color scale; no remote geographic topology is loaded.
    fig.add_trace(go.Scatter(x=[None],y=[None],mode='markers',hoverinfo='skip',showlegend=False,
        marker=dict(color=[low],cmin=low,cmax=high,colorscale=scale,showscale=True,
                    colorbar=dict(title='Écart national (%) · contraste non linéaire',orientation='h',x=.5,xanchor='center',y=-.08,len=.85,thickness=12))))
    fig.update_layout(dragmode="pan")
    return finish(fig,650)
