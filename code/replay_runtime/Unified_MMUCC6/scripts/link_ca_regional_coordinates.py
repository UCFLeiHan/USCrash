"""Download audit, annual coordinate extracts, and strict ID/date/street linkage.
Never equate unrelated identifier systems without date/minute and street agreement.
Unlinked regional records are NOT appended as new crashes.
"""
from pathlib import Path
import json,hashlib,shutil
from datetime import datetime
import pandas as pd
from supplement_ca_coordinates import R,U,S,street,sha

P=U/('qa/CA_regional_coordinate_linkage_'+datetime.now().strftime('%Y-%m-%d_%H%M%S'));P.mkdir(parents=True,exist_ok=True)
sources=[];status=[]
for name in ['SACOG','OrangeCounty_TIMS','OrangeCounty_CCRS']:
    folder=S/name;manifest=folder/'download_manifest.json'
    if not manifest.exists():
        status.append({'source':name,'status':'DOWNLOAD_NOT_COMPLETE_NOT_USED'});continue
    rows=[]
    for p in sorted(folder.glob('batch_*.json')):
        d=json.loads(p.read_text(encoding='utf-8-sig'))
        for f in d['features']:
            a=f['attributes'];g=f.get('geometry') or {};a['candidate_lon']=g.get('x');a['candidate_lat']=g.get('y');rows.append(a)
    b=pd.DataFrame(rows)
    if name=='SACOG':
        b=b.rename(columns={'CASE_ID':'join_id','ACCIDENT_YEAR':'year','JURIS':'agency','PRIMARY_RD':'road1','SECONDARY_RD':'road2'})
        clock=pd.to_numeric(b.COLLISION_TIME,errors='coerce');day=pd.to_datetime(b.COLLISION_DATE,format='mixed',errors='coerce')
        b['dt']=day+pd.to_timedelta((clock//100).where(clock.between(0,2359)&(clock%100<60)),unit='h')+pd.to_timedelta((clock%100).where(clock.between(0,2359)&(clock%100<60)),unit='m')
    elif name=='OrangeCounty_TIMS':
        b=b.rename(columns={'case_id':'join_id','date_year':'year','juris':'agency','primary_rd':'road1','secondary_rd':'road2'})
        # Timestamp field may contain timezone conventions; use official separate date/time.
        clock=pd.to_numeric(b.coll_time,errors='coerce');day=pd.to_datetime(b.coll_date,format='mixed',errors='coerce')
        if pd.api.types.is_datetime64tz_dtype(day.dtype):day=day.dt.tz_localize(None)
        b['dt']=day.dt.normalize()+pd.to_timedelta((clock//100).where(clock.between(0,2359)&(clock%100<60)),unit='h')+pd.to_timedelta((clock%100).where(clock.between(0,2359)&(clock%100<60)),unit='m')
    else:
        b=b.rename(columns={'Collision_Id':'join_id','Year':'year','NCIC_Code':'agency','PrimaryRoad':'road1','SecondaryRoad':'road2'})
        b['dt']=pd.to_datetime(b.Crash_Date_Time,format='mixed',errors='coerce')
    for col in ['join_id','year','agency']:b[col]=b[col].fillna('').astype(str).str.replace(r'\.0$','',regex=True)
    for year,a in b.groupby('year'):
        a.to_csv(folder/f'coordinate_extract_{year}.csv',index=False)
    status.append({'source':name,'status':'DOWNLOAD_COMPLETE','source_rows':len(b),'years':sorted(b.year.unique().tolist()),'unique_crash_ids':int(b.join_id.nunique())})
    sources.append((name,b))

reports=[];changes=[]
for y in range(2016,2027):
    raw=R/f'States/CA/{y}/Crashes_{y}.csv';canon=U/f'data/crash/CA/CA_crashes_harmonized_{y}.csv'
    if not raw.exists() or not canon.exists():continue
    fields=['Collision Id','NCIC Code','Crash Date Time','PrimaryRoad','SecondaryRoad']
    a=pd.read_csv(raw,dtype=str,keep_default_na=False,usecols=lambda c:c.strip() in fields);a.columns=a.columns.str.strip()
    a=a.rename(columns={'Collision Id':'join_id'});a['raw_dt']=pd.to_datetime(a['Crash Date Time'],format='%m/%d/%Y %I:%M:%S %p',errors='coerce')
    updates=[]
    for name,b in sources:
        b=b.loc[b.year.eq(str(y))].copy()
        keep=['join_id','dt','agency','road1','road2','candidate_lat','candidate_lon']
        b=b[keep].drop_duplicates();b=b.loc[b.join_id.ne('')&~b.join_id.duplicated(keep=False)]
        m=a.merge(b,on='join_id',validate='one_to_one')
        m['minute_agree']=m.raw_dt.notna()&m.dt.notna()&m.raw_dt.dt.floor('min').eq(m.dt.dt.floor('min'))
        m['agency_agree']=m['NCIC Code'].str.lstrip('0').eq(m.agency.str.lstrip('0'))
        m['road_agree']=[bool(set(filter(None,[street(p),street(q)]))&set(filter(None,[street(r),street(s)]))) for p,q,r,s in zip(m.PrimaryRoad,m.SecondaryRoad,m.road1,m.road2)]
        for c in ['candidate_lat','candidate_lon']:m[c]=pd.to_numeric(m[c],errors='coerce')
        m['eligible']=m.minute_agree&m.agency_agree&m.road_agree&m.candidate_lat.between(32.3,42.2)&m.candidate_lon.between(-124.6,-113.9)
        m['crash_uid']='CA:'+str(y)+':'+m.join_id;m['coordinate_source']=name
        m.to_csv(P/f'{name}_{y}_ID_linkage.csv',index=False)
        reports.append({'year':y,'source':name,'unique_regional_records':len(b),'same_numeric_id':len(m),'confirmed_ID_date_minute_agency_street':int(m.eligible.sum())})
        updates.append(m.loc[m.eligible])
    if not updates:continue
    d=pd.concat(updates,ignore_index=True)
    # Require agreement between sources; never arbitrarily pick a conflicting point.
    if len(d):
        conflicts=d.groupby('crash_uid')[['candidate_lat','candidate_lon']].nunique().max(axis=1).gt(1)
        d=d.loc[~d.crash_uid.isin(conflicts[conflicts].index)].drop_duplicates('crash_uid').set_index('crash_uid')
    else:continue
    c=pd.read_csv(canon,dtype=str,keep_default_na=False);original=c.copy()
    valid=pd.to_numeric(c.latitude,errors='coerce').between(32.3,42.2)&pd.to_numeric(c.longitude,errors='coerce').between(-124.6,-113.9)
    mask=~valid&c.crash_uid.isin(d.index)
    ledger=c.loc[mask,['crash_uid','latitude','longitude','coordinate_status']].copy()
    ledger['coordinate_source']=ledger.crash_uid.map(d.coordinate_source)
    for field,dest in [('candidate_lat','latitude'),('candidate_lon','longitude')]:c.loc[mask,dest]=c.loc[mask,'crash_uid'].map(d[field]).astype(str)
    c.loc[mask,'coordinate_status']='VALID'
    ledger['new_latitude']=c.loc[mask,'latitude'];ledger['new_longitude']=c.loc[mask,'longitude']
    ledger.to_csv(P/f'CA_{y}_changes.csv',index=False)
    assert c.loc[~mask].equals(original.loc[~mask])
    assert c.drop(columns=['latitude','longitude','coordinate_status']).equals(original.drop(columns=['latitude','longitude','coordinate_status']))
    if mask.any():
        backup=P/'canonical_before';backup.mkdir(exist_ok=True);shutil.copy2(canon,backup/canon.name)
        tmp=canon.with_suffix('.regional.tmp');c.to_csv(tmp,index=False);tmp.replace(canon)
    changes.append({'year':y,'filled':int(mask.sum()),'sha256_after':sha(canon)})
pd.DataFrame(reports).to_csv(P/'matching_summary.csv',index=False)
(P/'manifest.json').write_text(json.dumps({'sources':status,'changes':changes,'total_filled':sum(x['filled'] for x in changes),'script_sha256':sha(Path(__file__)),'rule':'Exact unique numeric identifier AND same agency, date, minute and normalized road; no invented crosswalk and no appending unmatched crashes. Coordinate extracts are selected fields, not full crash archives.','unlinked_policy':'Retained in source extracts; unresolved identifier systems require further linkage work.'},indent=2),encoding='utf-8')
print(json.dumps({'output':str(P),'sources':status,'total_filled':sum(x['filled'] for x in changes)},indent=2),flush=True)
