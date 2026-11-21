import unittest
import pandas as pd
from src.processing.quality_rules import assess_prices, analytical_events, clean_station_view, parse_intervals
from src.analytics.dashboard import prepare

class QualityRulesTests(unittest.TestCase):
    def frame(self, values, times=None):
        return pd.DataFrame({'station_id':['001']*len(values),'fuel':['Gazole']*len(values),'fuel_code':['1']*len(values),'archive_year':[2022]*len(values),'price_eur_l':values,'price_reported_at':pd.to_datetime(times or ['2022-01-01 10:00']*len(values))})

    def test_numeric_duplicates_and_conflicts(self):
        result=assess_prices(self.frame(['1.50','1.500']))
        self.assertEqual(result.analysis_eligible.sum(),1)
        self.assertFalse(result.dq_conflict.any())
        result=assess_prices(self.frame([1.5,1.6]))
        self.assertTrue(result.dq_conflict.all())
        self.assertFalse(result.analysis_eligible.any())

    def test_invalid_last_event_blocks_earlier_and_no_carry(self):
        result=analytical_events(self.frame([1.5,9.9],['2022-01-01 08:00','2022-01-01 12:00']))
        wide,_=prepare(result,pd.DataFrame({'station_id':['001']}),'2022-01-01','2022-01-02')
        self.assertTrue(wide.isna().all().all())

    def test_map_does_not_discard_national_station(self):
        stations=pd.DataFrame({'station_id':['001','002'],'latitude':[0.,48.],'longitude':[0.,0.],'postal_code':['1000','01000']})
        result=clean_station_view(stations)
        self.assertEqual(len(result),2)
        self.assertFalse(result.iloc[0].map_eligible)
        self.assertTrue(result.iloc[1].map_eligible)
        self.assertTrue(pd.isna(result.iloc[0].postal_code))

    def test_intervals(self):
        result=parse_intervals('[{"tag":"rupture","attributes":{"debut":"2022-01-02"}},{"tag":"rupture","attributes":{"debut":"2022-01-02","fin":"2022-01-01"}}]')
        self.assertTrue(result.iloc[0].interval_eligible)
        self.assertTrue(result.iloc[0].end_absent)
        self.assertFalse(result.iloc[1].interval_eligible)
        self.assertFalse(parse_intervals('bad').iloc[0].interval_eligible)

    def test_invalid_identity_price_and_year(self):
        result=self.frame([0,-1,float('inf'),1.5])
        result.loc[3,'archive_year']=2021
        self.assertFalse(assess_prices(result).analysis_eligible.any())

if __name__=='__main__': unittest.main()
