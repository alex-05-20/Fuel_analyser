import unittest
import pandas as pd
from src.analytics.overview_charts import regional_comparison

class MapComparisonTests(unittest.TestCase):
    def test_weighted_national_and_separate_fuels(self):
        m=pd.DataFrame({'fuel':['Gazole','Gazole','E85'],'price':[1.,2.,1.],'days':[10,30,40]})
        r=pd.DataFrame({'region':['11','11'],'fuel':['Gazole','E85'],'price':[1.925,.9]})
        d=regional_comparison(m,r)
        self.assertAlmostEqual(d.loc[d.fuel.eq('Gazole'),'national_price'].iloc[0],1.75)
        self.assertAlmostEqual(d.gap.mean(),0.)
        self.assertEqual(len(regional_comparison(m,r,'E85')),1)
