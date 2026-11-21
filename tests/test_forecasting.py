import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from src.analytics.forecasting import monthly_series, analyse_fuel, features

class ForecastTests(unittest.TestCase):
    def data(self):
        dates=pd.date_range('2017-01-01','2026-11-01',freq='MS')
        return pd.DataFrame({'month':dates,'fuel':'Gazole','price':1+np.arange(len(dates))*.001,'partial':dates==pd.Timestamp('2026-11-01')})

    def test_partial_and_future_excluded(self):
        df=self.data(); df.loc[df['partial'],'price']=10000
        s=monthly_series(df,'Gazole')
        self.assertEqual(s.index[-1],pd.Timestamp('2026-10-01'))
        self.assertLess(s.max(),2)

    def test_chronological_windows(self):
        df=self.data(); seen=[]
        def fake(train,horizon=12):
            seen.append(train.index[-1])
            return pd.DataFrame({'month':pd.date_range(train.index[-1]+pd.offsets.MonthBegin(),periods=12,freq='MS'),'prediction':train.iloc[-1],'reference':train.iloc[-12:].to_numpy()})
        with patch('src.analytics.forecasting.forecast',side_effect=fake):
            future,test,_=analyse_fuel(df,'Gazole')
        self.assertEqual(seen,list(pd.to_datetime(['2023-10-01','2024-10-01','2025-10-01','2026-10-01'])))
        self.assertEqual(test.month.iloc[0],pd.Timestamp('2025-11-01'))
        self.assertEqual(future.month.iloc[-1],pd.Timestamp('2027-10-01'))

    def test_missing_month_not_imputed(self):
        df=self.data();df.loc[df.month.eq('2024-01-01'),'price']=np.nan
        with self.assertRaises(ValueError):monthly_series(df,'Gazole')

if __name__=='__main__':unittest.main()
