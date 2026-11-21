import unittest
import pandas as pd
from src.analytics.overview_data import combine
from src.analytics.overview_charts import evolution_chart, grid_chart

class OverviewTests(unittest.TestCase):
    def test_regional_daily_weighting(self):
        base={'region':'11','fuel':'Gazole','first_date':'2020-01-01','last_date':'2020-12-31'}
        p={'monthly':[{'month':'2020-01-01','fuel':'Gazole','price':1.5}],
           'regional':[{**base,'total_daily_price':2.,'days':1,'station_days':10},
                       {**base,'total_daily_price':3.,'days':3,'station_days':60}]}
        _,r=combine([p])
        self.assertEqual(r.iloc[0].price,1.25)
        self.assertEqual(r.iloc[0].stations,17.5)

    def test_missing_month_not_connected_or_zero(self):
        m=pd.DataFrame({'month':pd.to_datetime(['2020-01-01','2020-03-01']),
                        'fuel':['Gazole','Gazole'],'price':[1.,2.],'days':[2,3],'stations':[10,12]})
        line=evolution_chart(m)
        self.assertEqual(len(line.data),6)
        self.assertFalse(line.data[0].connectgaps)
        self.assertTrue(pd.isna(line.data[0].y[1]))
        heat=grid_chart(m,'Gazole')
        self.assertTrue(pd.isna(heat.data[0].z[0][1]))
        self.assertEqual(len(heat.data[0].x),12)

if __name__=='__main__':unittest.main()
