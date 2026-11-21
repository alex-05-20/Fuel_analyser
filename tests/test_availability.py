import unittest
import pandas as pd
from src.analytics.availability import summarize_availability

class AvailabilityTests(unittest.TestCase):
    def test_pairs_not_station_partition(self):
        data=pd.DataFrame({'id':['01','01','02','03'],'Carburants disponibles':['Gazole,E10,E10','E10;Gazole','Gazole',None]})
        counts,q=summarize_availability(data)
        self.assertEqual(q['total'],3)
        self.assertEqual(q['missing'],1)
        self.assertEqual(counts.stations.sum(),3)
        self.assertEqual(counts.set_index('fuel').loc['Gazole','stations'],2)
        self.assertAlmostEqual(counts.set_index('fuel').loc['Gazole','station_percent'],200/3)

    def test_conflicting_and_unknown_are_not_guessed(self):
        data=pd.DataFrame({'id':['1','1','2',None],'Carburants disponibles':['Gazole','E10','unknown','Gazole']})
        counts,q=summarize_availability(data)
        self.assertEqual(counts.stations.sum(),0)
        self.assertEqual(q['conflicts'],1)
        self.assertEqual(q['missing'],1)
        self.assertEqual(q['invalid_rows'],1)
