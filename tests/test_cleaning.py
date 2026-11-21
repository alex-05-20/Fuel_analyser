import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile
import pandas as pd
from src.processing.prices import clean_snapshot
from src.processing.annual import prepare_year


class CleaningTests(unittest.TestCase):
    def test_snapshot_preserves_columns_and_raw_json(self):
        source=pd.DataFrame({'id':['0001','0002'],'Code postal':['01000','02000'],'latitude':['4800000','wrong'],'longitude':['200000','200000'],'Prix Gazole':['1,85','bad'],'services':['{"service":["Lavage"]}','not-json'],'Automate 24-24 (oui/non)':['Oui','?']},dtype='string')
        result,report=clean_snapshot(source)
        self.assertEqual(list(result),list(source))
        self.assertEqual(len(result),2)
        self.assertEqual(result.loc[0,'Code postal'],'01000')
        self.assertEqual(result.loc[0,'latitude'],48)
        self.assertEqual(result.loc[0,'Prix Gazole'],1.85)
        self.assertEqual(result.loc[1,'services'],'not-json')
        self.assertTrue(pd.isna(result.loc[1,'Prix Gazole']))
        self.assertTrue(report['issues'])

    def test_annual_retains_invalid_duplicates_and_station_metadata(self):
        xml='<pdv_liste><pdv id="001" cp="01000" latitude="4800000" longitude="200000" pop="R"><adresse>A</adresse><ville>V</ville><services><service>Lavage</service></services><ouverture debut="08.00"/><prix id="1" nom="Gazole" maj="2022-01-01 10:00:00" valeur="1.5"/><prix id="1" nom="Gazole" maj="2022-01-01 10:00:00" valeur="1.5"/><prix id="1" nom="Gazole" maj="bad" valeur="bad"/><fermeture debut="2022-01-02"/></pdv><pdv id="002" cp="02000" latitude="4900000" longitude="300000"><services/></pdv></pdv_liste>'
        with TemporaryDirectory() as temp:
            root=Path(temp)
            archive=root/'2022.zip'
            with ZipFile(archive,'w') as z:z.writestr('prices.xml',xml)
            destination=root/'data/cleaned/historical/2022.parquet'
            report=prepare_year(archive,destination)
            result=pd.read_parquet(destination)
            self.assertEqual(len(result),4)
            self.assertEqual(report['source_price_elements'],3)
            self.assertEqual(result['no_price'].sum(),1)
            self.assertEqual(result['duplicate_price'].sum(),2)
            self.assertEqual(result['invalid_price'].sum(),1)
            self.assertEqual(result['invalid_date'].sum(),1)
            self.assertEqual(result.loc[2,'price_raw'],'bad')
            meta=json.loads(result.loc[0,'station_source_json'])
            self.assertIn('ouverture',[c['tag'] for c in meta['children']])
            self.assertIn('fermeture',[c['tag'] for c in meta['children']])
            self.assertTrue((root/'data/quality/2022.json').exists())


if __name__=='__main__':unittest.main()
