"""Withdraw earlier v1 local supplements invalidated by normalized-key ambiguity.
Only coordinates explicitly changed by our own v1 ledger may be withdrawn.
"""
from pathlib import Path
import json
import pandas as pd
from supplement_ca_coordinates import U,sha
V1=U/'qa/CA_coordinate_supplement_2026-10-16'
V2=U/'qa/CA_coordinate_supplement_2026-10-16_010438'
rows=[];runs=[]
for y in range(2016,2027):
    old=pd.read_csv(V1/f'CA_{y}_coordinate_changes.csv',dtype=str,keep_default_na=False)
    old=old.loc[old.coordinate_source.eq('Los Angeles')]
    p=V2/f'Los_Angeles_{y}_linkage.csv'
    if not p.exists():continue
    b=pd.read_csv(p,dtype=str,keep_default_na=False)
    supported=set(b.loc[b.eligible_link.eq('True'),'crash_uid'])
    withdraw=old.loc[~old.crash_uid.isin(supported)].copy().set_index('crash_uid')
    if not len(withdraw):continue
    file=U/f'data/crash/CA/CA_crashes_harmonized_{y}.csv'
    a=pd.read_csv(file,dtype=str,keep_default_na=False);original=a.copy();before=sha(file)
    mask=a.crash_uid.isin(withdraw.index)
    assert int(mask.sum())==len(withdraw)
    for col,ledger in [('latitude','new_latitude'),('longitude','new_longitude')]:
        actual=pd.to_numeric(a.loc[mask,col],errors='coerce')
        expected=pd.to_numeric(a.loc[mask,'crash_uid'].map(withdraw[ledger]),errors='coerce')
        assert actual.eq(expected).all(),'Do not overwrite independently modified coordinates'
    for col in ['latitude','longitude','coordinate_status']:
        a.loc[mask,col]=a.loc[mask,'crash_uid'].map(withdraw[col])
    assert a.loc[~mask].equals(original.loc[~mask])
    assert a.drop(columns=['latitude','longitude','coordinate_status']).equals(original.drop(columns=['latitude','longitude','coordinate_status']))
    tmp=file.with_suffix('.reconcile.tmp');a.to_csv(tmp,index=False);tmp.replace(file)
    reloaded=pd.read_csv(file,dtype=str,keep_default_na=False,usecols=['crash_uid','latitude','longitude','coordinate_status']).set_index('crash_uid')
    for col in ['latitude','longitude','coordinate_status']:assert reloaded.loc[withdraw.index,col].eq(withdraw[col]).all()
    withdraw=withdraw.reset_index();withdraw['withdrawal_reason']='Previous raw-key match excluded by nine-digit key normalization (ambiguous normalized key); restore pre-supplement values, do not invent a preferred collision.'
    withdraw.to_csv(V2/f'CA_{y}_withdrawn_v1_supplements.csv',index=False)
    rows.append(withdraw)
    runs.append({'year':y,'withdrawn':len(withdraw),'sha256_before':before,'sha256_after':sha(file),'status':'PASS'})
    print('WITHDRAWN',y,len(withdraw),flush=True)
(V2/'reconciliation_manifest.json').write_text(json.dumps({'runs':runs,'total_withdrawn':sum(r['withdrawn'] for r in runs),'script_sha256':sha(Path(__file__)),'raw_data_modified':False,'row_count_changed':False,'reason':'Remove stale v1 supplements excluded by stricter normalized-key uniqueness; fresh v2 runs from original baseline exclude these automatically.'},indent=2),encoding='utf-8')
print('RECONCILIATION COMPLETE',sum(r['withdrawn'] for r in runs),flush=True)
