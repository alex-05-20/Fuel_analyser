"""Lossless historical extraction: one row per price node (or station without price)."""
from collections import Counter
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET
from zipfile import ZipFile
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

STRINGS = ["station_id", "postal_code", "city", "address", "road_type", "latitude_raw", "longitude_raw", "fuel", "fuel_code", "price_raw", "date_raw", "hours_json", "opening_json", "services_json", "outages_json", "closures_json", "station_source_json", "price_source_json", "source_archive"]
FLAGS = ["invalid_price", "invalid_date", "unknown_fuel", "suspect_price", "outside_archive_year", "duplicate_price", "conflicting_price", "no_price"]
SCHEMA = pa.schema([(c,pa.string()) for c in STRINGS] + [(c,pa.float64()) for c in ("latitude","longitude","price_eur_l")] + [("price_reported_at",pa.timestamp("us")),("archive_year",pa.int32()),("source_station_index",pa.int32()),("source_price_index",pa.int32())] + [(c,pa.bool_()) for c in FLAGS])
FUELS={"1":"Gazole","2":"SP95","3":"E85","4":"GPLc","5":"E10","6":"SP98"}


def element(node):
    return {"tag":node.tag,"attributes":dict(node.attrib),"text":node.text,"children":[element(child) for child in node]}


def dump(value):
    return json.dumps(value,ensure_ascii=False,separators=(",",":"))


def prepare_year(archive_path, destination):
    archive_path, destination = Path(archive_path), Path(destination)
    year=int(archive_path.stem)
    divisor=1000 if year<=2021 else 1
    destination.parent.mkdir(parents=True,exist_ok=True)
    counts=Counter(); fuels=Counter(); bounds=[]; rows=[]; seen=set()
    with TemporaryDirectory(dir=destination.parent) as temp:
        output=Path(temp)/destination.name
        with pq.ParquetWriter(output,SCHEMA,compression="zstd") as writer:
            def flush():
                if not rows:return
                frame=pd.DataFrame(rows)
                for c in STRINGS:frame[c]=frame[c].astype("string")
                frame["price_eur_l"]=pd.to_numeric(frame["price_raw"],errors="coerce")/divisor
                frame["price_reported_at"]=pd.to_datetime(frame["date_raw"],format="mixed",errors="coerce")
                frame["invalid_price"]=~frame["no_price"] & (frame["price_eur_l"].isna() | frame["price_eur_l"].le(0) | frame["price_eur_l"].abs().eq(float("inf")))
                frame["invalid_date"]=~frame["no_price"] & frame["price_reported_at"].isna()
                frame["unknown_fuel"]=~frame["no_price"] & ~frame["fuel"].isin(FUELS.values())
                frame["suspect_price"]=~frame["no_price"] & (~frame["price_eur_l"].between(.2,5)).fillna(False)
                frame["outside_archive_year"]=frame["price_reported_at"].notna() & frame["price_reported_at"].dt.year.ne(year)
                for c,limit in (("latitude",90),("longitude",180)):
                    v=pd.to_numeric(frame[c+"_raw"],errors="coerce")/100000
                    frame[c]=v.where(v.between(-limit,limit))
                for c in FLAGS:counts[c]+=int(frame[c].sum())
                counts["retained_rows"]+=len(frame)
                fuels.update(frame.loc[~frame["no_price"],"fuel"].dropna().value_counts().to_dict())
                dates=frame["price_reported_at"].dropna()
                if not dates.empty:bounds.extend([dates.min(),dates.max()])
                writer.write_table(pa.Table.from_pandas(frame,schema=SCHEMA,preserve_index=False))
                rows.clear()
            with ZipFile(archive_path) as archive:
                names=[n for n in archive.namelist() if n.lower().endswith('.xml')]
                if len(names)!=1:raise ValueError("Un XML unique est attendu")
                with archive.open(names[0]) as source:
                    events=ET.iterparse(source,events=("start","end"));_,root=next(events)
                    if root.tag!='pdv_liste':raise ValueError('Racine XML inattendue')
                    for event,node in events:
                        if event!='end' or node.tag!='pdv':continue
                        counts["station_count"]+=1
                        sid=node.get('id')
                        if not sid or sid in seen:counts['missing_or_repeated_station_ids']+=1
                        seen.add(sid)
                        metadata=element(node);metadata['children']=[c for c in metadata['children'] if c['tag']!='prix']
                        base={"station_id":sid,"postal_code":node.get('cp'),"city":node.findtext('ville'),"address":node.findtext('adresse'),"road_type":node.get('pop'),"latitude_raw":node.get('latitude'),"longitude_raw":node.get('longitude'),"archive_year":year,"source_station_index":counts['station_count'],"source_archive":f"data/raw/annual/{archive_path.name}","station_source_json":dump(metadata)}
                        for col,tag in [('hours_json','horaires'),('opening_json','ouverture'),('services_json','services'),('outages_json','rupture'),('closures_json','fermeture')]:
                            nodes=node.findall(tag);base[col]=dump([element(n) for n in nodes]) if nodes else None
                        prices=node.findall('prix'); counts['source_price_elements']+=len(prices)
                        exact=Counter((p.get('id'),p.get('nom'),p.get('maj'),p.get('valeur')) for p in prices)
                        values={}
                        for p in prices:values.setdefault((p.get('id'),p.get('maj')),set()).add(p.get('valeur'))
                        for index,p in enumerate(prices or [None]):
                            attrs=p.attrib if p is not None else {}
                            rows.append({**base,'fuel':attrs.get('nom') or FUELS.get(attrs.get('id')),'fuel_code':attrs.get('id'),'price_raw':attrs.get('valeur'),'date_raw':attrs.get('maj'),'price_source_json':dump(element(p)) if p is not None else None,'source_price_index':index+1 if p is not None else 0,'no_price':p is None,'duplicate_price':p is not None and exact[(p.get('id'),p.get('nom'),p.get('maj'),p.get('valeur'))]>1,'conflicting_price':p is not None and len(values[(p.get('id'),p.get('maj'))])>1})
                        if len(rows)>=20000:flush()
                        node.clear();root.clear()
            flush()
        if not counts['station_count']:raise ValueError('Archive vide')
        report={"schema_version":2,"year":year,"price_divisor":divisor,**dict(counts),"fuel_counts":dict(fuels),"first_price_date":str(min(bounds)) if bounds else None,"last_price_date":str(max(bounds)) if bounds else None,"rows_removed":0,"date_convention":"Dates XML sans fuseau ajouté","station_metadata":"État fourni par l’archive annuelle, non garanti à la date de chaque prix"}
        (Path(temp)/'quality.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
        output.replace(destination)
        quality=destination.parents[2]/'quality'/f'{year}.json'
        quality.parent.mkdir(parents=True,exist_ok=True)
        (Path(temp)/'quality.json').replace(quality)
    return report
