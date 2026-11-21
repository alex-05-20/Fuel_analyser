"""Clean the complete instantaneous CSV without removing columns or rows."""
import json
import numpy as np
import pandas as pd

FUELS=("Gazole","SP95","E85","GPLc","E10","SP98")


def clean_snapshot(raw):
    out=raw.copy().astype('string')
    issues=[]
    def flag(column, mask, reason):
        for idx in raw.index[mask.fillna(False)]:
            issues.append({'row':int(idx)+2,'id':str(raw.at[idx,'id']),'column':column,'reason':reason,'raw_value':str(raw.at[idx,column])})
    for c in out:
        out[c]=out[c].str.strip().replace('',pd.NA)
    for c in ['id','Code postal','code_departement','code_region']:
        if c in out:
            flag(c,out[c].notna() & ~out[c].str.fullmatch(r'[0-9A-Za-z]+',na=False),'format_code')
    flag('id',out['id'].isna() | out['id'].duplicated(keep=False),'identifiant_absent_ou_repete')
    for c in ['latitude','longitude']+[f'Prix {f}' for f in FUELS]:
        if c not in out:continue
        original=out[c]
        number=pd.to_numeric(original.str.replace(',','.',regex=False),errors='coerce').astype('Float64')
        flag(c,original.notna() & (number.isna() | ~np.isfinite(number)),'nombre_invalide')
        number=number.where(np.isfinite(number))
        if c in ['latitude','longitude']:
            number=number/100000
            limit=90 if c=='latitude' else 180
            flag(c,number.notna() & ~number.between(-limit,limit),'coordonnees_hors_limites')
            number=number.where(number.between(-limit,limit))
        else:flag(c,number.notna() & ~number.between(.2,5),'prix_atypique_conserve')
        out[c]=number
    for c in out:
        if 'mis à jour le' in c or c.startswith('Début rupture'):
            original=out[c]
            aware=original.str.contains(r'(?:Z|[+-]\d{2}:?\d{2})$',regex=True,na=False)
            dates=pd.to_datetime(original.where(aware),format='mixed',utc=True,errors='coerce')
            flag(c,original.notna() & dates.isna(),'date_invalide_ou_fuseau_absent')
            out[c]=dates
    c='Automate 24-24 (oui/non)'
    if c in out:
        original=out[c].str.casefold()
        mapping={'oui':True,'non':False,'true':True,'false':False,'1':True,'0':False}
        flag(c,original.notna() & ~original.isin(mapping),'booleen_inconnu')
        out[c]=original.map(mapping).astype('boolean')
    for c in ['horaires','services','prix','rupture']:
        if c not in out:continue
        for idx,value in out[c].items():
            if pd.isna(value):continue
            try:out.at[idx,c]=json.dumps(json.loads(value),ensure_ascii=False,separators=(',',':'))
            except (ValueError,TypeError):
                issues.append({'row':int(idx)+2,'id':str(raw.at[idx,'id']),'column':c,'reason':'json_invalide_conserve','raw_value':str(value)})
    for c in ['Adresse','Ville','Département','Région','Services proposés']:
        if c in out:out[c]=out[c].str.replace(r'\s+',' ',regex=True)
    # Geometry stays as supplied; disagreement is reported, never silently corrected.
    if 'geom' in out:
        pair=out['geom'].str.split(',',n=1,expand=True)
        if pair.shape[1]==2:
            lat=pd.to_numeric(pair[0],errors='coerce');lon=pd.to_numeric(pair[1],errors='coerce')
            flag('geom',lat.isna() & out['geom'].notna(),'geometrie_invalide')
            flag('geom',(lat-out['latitude']).abs().gt(.00001) | (lon-out['longitude']).abs().gt(.00001),'coordonnees_incoherentes')
    for c in ['pop']+[name for name in out if name.startswith('Type rupture')]:
        if c not in out:continue
        valid={'R','A'} if c=='pop' else {'temporaire','definitive'}
        flag(c,out[c].notna() & ~out[c].isin(valid),'categorie_inconnue_conservee')
    for c in [name for name in out if name.startswith('Carburants ')]:
        for idx,value in out[c].dropna().items():
            import re
            tokens=[v.strip() for v in re.split('[,;]',value) if v.strip()]
            if any(v not in FUELS for v in tokens):
                issues.append({'row':int(idx)+2,'id':str(raw.at[idx,'id']),'column':c,'reason':'carburant_inconnu_conserve','raw_value':str(raw.at[idx,c])})
    if 'prix' in out:
        for idx,value in out['prix'].dropna().items():
            try: entries=json.loads(value)
            except (TypeError,ValueError):continue
            if isinstance(entries,dict):entries=[entries]
            if not isinstance(entries,list):continue
            for entry in entries:
                if not isinstance(entry,dict):continue
                c='Prix '+str(entry.get('@nom',''))
                if c not in out:continue
                original=pd.to_numeric(entry.get('@valeur'),errors='coerce')
                actual=out.at[idx,c]
                if pd.notna(original) and (pd.isna(actual) or abs(float(original)-float(actual))>1e-8):
                    issues.append({'row':int(idx)+2,'id':str(raw.at[idx,'id']),'column':c,'reason':'prix_json_incoherent','raw_value':str(raw.at[idx,c]),'json_value':str(original)})
    assert list(out)==list(raw) and len(out)==len(raw)
    report={'schema_version':2,'rows':len(out),'columns':list(out),'rows_removed':0,'coordinate_divisor':100000,'issues':issues,'types':{c:str(t) for c,t in out.dtypes.items()}}
    return out,report
