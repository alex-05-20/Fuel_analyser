"""Reproducible recursive forecasts with strictly chronological validation."""
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

CUTOFF = pd.Timestamp('2026-10-01')
HORIZON = 12


def monthly_series(monthly, fuel):
    frame=monthly.loc[monthly.fuel.eq(fuel) & monthly.month.le(CUTOFF)].copy()
    frame.loc[frame['partial'].fillna(True), 'price']=np.nan
    if frame.empty: raise ValueError(f'{fuel} : aucune observation avant la date retenue.')
    series=frame.set_index('month')['price'].reindex(pd.date_range(frame.month.min(),CUTOFF,freq='MS')).astype(float)
    # Never invent a missing monthly price. Use the contiguous observed tail.
    missing=np.flatnonzero(~np.isfinite(series.to_numpy()) | series.le(0).to_numpy())
    if len(missing): series=series.iloc[missing[-1]+1:]
    if len(series)<72: raise ValueError(f'{fuel} : moins de 72 mois consécutifs exploitables jusqu’à octobre 2026.')
    return series


def features(values, date):
    a=np.asarray(values,dtype=float)
    if len(a)<12: raise ValueError('Douze mois antérieurs sont nécessaires.')
    return [a[-i] for i in (1,2,3,6,12)]+[a[-3:].mean(),a[-6:].mean(),a[-12:].mean(),a[-1]-a[-2],np.sin(2*np.pi*date.month/12),np.cos(2*np.pi*date.month/12)]


def forecast(train, horizon=HORIZON):
    # Model log prices to keep the forecast positive, without arbitrary clipping.
    logs=np.log(train.to_numpy())
    x=[features(logs[:i],train.index[i]) for i in range(12,len(train))]
    model=GradientBoostingRegressor(n_estimators=120,max_depth=2,learning_rate=.05,loss='huber',random_state=42)
    model.fit(x,logs[12:])
    history=list(logs)
    dates=pd.date_range(train.index[-1]+pd.offsets.MonthBegin(),periods=horizon,freq='MS')
    predicted=[]
    for date in dates:
        value=float(model.predict([features(history,date)])[0])
        history.append(value);predicted.append(np.exp(value))
    baseline=np.resize(train.iloc[-12:].to_numpy(),horizon)
    return pd.DataFrame({'month':dates,'prediction':predicted,'reference':baseline})


def analyse_fuel(monthly,fuel):
    series=monthly_series(monthly,fuel)
    n=len(series);validation=[]
    # Two non-overlapping 12-month validation windows, then an untouched 12-month test.
    for end in (n-36,n-24):
        out=forecast(series.iloc[:end]);actual=series.iloc[end:end+12].to_numpy()
        out['actual']=actual;validation.append(out)
    validation=pd.concat(validation,ignore_index=True)
    band=float(np.quantile(np.abs(validation.actual-validation.prediction),.9,method='higher'))
    test=forecast(series.iloc[:-12]);test['actual']=series.iloc[-12:].to_numpy()
    scores={'fuel':fuel,'validation_ml':float(np.abs(validation.actual-validation.prediction).mean()),
            'validation_reference':float(np.abs(validation.actual-validation.reference).mean()),
            'test_ml':float(np.abs(test.actual-test.prediction).mean()),
            'test_reference':float(np.abs(test.actual-test.reference).mean()),
            'band_width':band,'test_coverage':float((np.abs(test.actual-test.prediction)<=band).mean()),
            'training_start':str(series.index[0].date()),'months':n}
    future=forecast(series)
    future['lower']=(future.prediction-band).clip(lower=0)
    future['upper']=future.prediction+band
    future['fuel']=fuel
    test['fuel']=fuel
    return future,test,scores
