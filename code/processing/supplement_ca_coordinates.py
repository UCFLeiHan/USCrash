"""Reproducible conservative local-source coordinate overlay; source files immutable.
Run after CA harmonization. Existing valid canonical coordinates are never replaced.
Local report IDs are agency scoped; collision IDs are NOT assumed to be SWITRS IDs.
"""
from pathlib import Path
import concurrent.futures as cf
import hashlib, json, re, shutil, time
import pandas as pd
import numpy as np
import requests
import geopandas as gpd
import shapely

R=Path(r'F:\LH_Research\USCrash\Crash')
U=R/'Unified_MMUCC6'
from datetime import datetime
P=U/('qa/CA_coordinate_supplement_'+datetime.now().strftime('%Y-%m-%d_%H%M%S'))
P.mkdir(parents=True,exist_ok=True)
S=R/'States/CA/Local_coordinate_sources_2026-10-16';S.mkdir(exist_ok=True)
YEARS=range(2016,2027)

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for x in iter(lambda:f.read(8*1024*1024),b''): h.update(x)
    return h.hexdigest()

def get(url,params=None):
    for attempt in range(4):
        try:
            r=requests.get(url,params=params,timeout=90);r.raise_for_status();return r.json()
        except Exception:
            if attempt==3: raise
            time.sleep(2**attempt)

def lapd(y):
    p=S/f'LAPD_{y}.json'
    if p.exists():return y,p
    url='https://data.lacity.org/resource/d5tf-ez2w.json'
    where=f"date_occ >= '{y}-01-01T00:00:00' AND date_occ < '{y+1}-01-01T00:00:00'"
    n=int(get(url,{'$where':where,'$select':'count(*) as n'})[0]['n']);rows=[]
    for offset in range(0,n,10000):
        rows.extend(get(url,{'$where':where,'$select':'dr_no,date_occ,time_occ,location_1,location,cross_street','$order':':id','$limit':10000,'$offset':offset}))
    assert len(rows)==n,(y,n,len(rows))
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(rows),encoding='utf-8');tmp.replace(p)
    print('LAPD downloaded',y,n,flush=True);return y,p

def street(x):
    s=re.sub(r'[^A-Z0-9 ]',' ',str(x).upper())
    s=re.sub(r'^\s*\d+\s+','',s)
    tokens=s.split()
    replace={'STREET':'ST','AVENUE':'AVE','AV':'AVE','BOULEVARD':'BLVD','ROAD':'RD','DRIVE':'DR','HIGHWAY':'HWY','NORTH':'N','SOUTH':'S','EAST':'E','WEST':'W'}
    return ' '.join(replace.get(t,t) for t in tokens)

def prepare(b):
    b=b.fillna('');b['report_key']=b.report_key.str.strip()
    b=b.drop_duplicates(subset=['report_key','dt','lat','lon','road1','road2'])
    b=b.loc[b.report_key.ne('')&~b.report_key.duplicated(keep=False)].copy()
    for k in ['lat','lon']:b[k]=pd.to_numeric(b[k],errors='coerce')
    b['dt']=pd.to_datetime(b.dt,format='mixed',errors='coerce')
    return b

if __name__=='__main__':
    if not (S/'LAPD_metadata.json').exists():
        meta=get('https://data.lacity.org/api/views/d5tf-ez2w.json')
        (S/'LAPD_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    failures=[]
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(lapd,y):y for y in YEARS}
        for f in cf.as_completed(jobs):
            try:f.result()
            except Exception as e: failures.append({'year':jobs[f],'error':str(e)});print('DOWNLOAD FAILED',jobs[f],e,flush=True)
    boundary=Path(r'F:\LH_Research\USCrash\Crash\verification\reference\cb_2023_06_place_500k.zip')
    geo=gpd.read_file(boundary)
    polys={}
    for city in ['Los Angeles','San Francisco','San Jose']:
        g=geo.loc[geo.NAME.eq(city)].to_crs(3310);g.geometry=g.geometry.buffer(500)
        polys[city]=g.to_crs(4326).geometry.iloc[0]
    summaries=[];manifest=[]
    for y in YEARS:
        raw=R/f'States/CA/{y}/Crashes_{y}.csv'
        canon=U/f'data/crash/CA/CA_crashes_harmonized_{y}.csv'
        if not raw.exists() or not canon.exists():continue
        fields=['Collision Id','Report Number','NCIC Code','Crash Date Time','Latitude','Longitude','PrimaryRoad','SecondaryRoad']
        a=pd.read_csv(raw,dtype=str,keep_default_na=False,usecols=lambda c:c.strip() in fields);a.columns=a.columns.str.strip()
        a['report_key']=a['Report Number'].str.strip();a['raw_dt']=pd.to_datetime(a['Crash Date Time'],format='%m/%d/%Y %I:%M:%S %p',errors='coerce')
        sources=[]
        lp=S/f'LAPD_{y}.json'
        if lp.exists():
            rows=json.loads(lp.read_text(encoding='utf-8'));rec=[]
            for r in rows:
                t=str(r.get('time_occ','')).zfill(4)
                dt=str(r.get('date_occ',''))[:10]+' '+t[:2]+':'+t[2:]+':00' if re.fullmatch(r'\d{4}',t) else ''
                loc=r.get('location_1') or {}
                rec.append(dict(report_key=r.get('dr_no',''),dt=dt,lat=loc.get('latitude',''),lon=loc.get('longitude',''),road1=r.get('location',''),road2=r.get('cross_street','')))
            if rec:sources.append(('Los Angeles','1942',lp,prepare(pd.DataFrame(rec))))
        sf=R/f'Cities/SanFrancisco/{y}/DataSF_injury_crashes.csv'
        if sf.exists():
            b=pd.read_csv(sf,dtype=str,keep_default_na=False)
            b=b.rename(columns={'case_id_pkey':'report_key','collision_datetime':'dt','tb_latitude':'lat','tb_longitude':'lon','primary_rd':'road1','secondary_rd':'road2'})
            sources.append(('San Francisco','3801',sf,prepare(b)))
        sj=R/f'Cities/SanJose/{y}/SJ_crash_locations.csv'
        if sj.exists():
            b=pd.read_csv(sj,dtype=str,keep_default_na=False)
            b=b.rename(columns={'TCRNUMBER':'report_key','LATITUDE':'lat','LONGITUDE':'lon','INTASTREETNAME':'road1','INTBSTREETNAME':'road2'})
            b['dt']=pd.to_datetime(pd.to_numeric(b.CRASHDATETIME,errors='coerce'),unit='ms',errors='coerce')
            sources.append(('San Jose','4313',sj,prepare(b)))
        updates=[]
        for city,agency,src,b in sources:
            aa=a.loc[a['NCIC Code'].eq(agency)].copy()
            if agency=='1942':
                # LAPD DR numbers contain nine digits; CCRS often inserts hyphens/spaces.
                # Do not pad, truncate, infer digits, or choose among ambiguous keys.
                aa['report_key']=aa['Report Number'].str.replace(r'[^0-9]','',regex=True)
                aa=aa.loc[aa.report_key.str.fullmatch(r'\d{9}')]
            aa=aa.loc[aa.report_key.ne('')&~aa.report_key.duplicated(keep=False)]
            m=aa.merge(b[['report_key','dt','lat','lon','road1','road2']],on='report_key',validate='one_to_one')
            m['minute_agree']=m.raw_dt.notna()&m.dt.notna()&m.raw_dt.dt.floor('min').eq(m.dt.dt.floor('min'))
            m['road_agree']=[bool(set(filter(None,[street(p),street(q)]))&set(filter(None,[street(r),street(s)]))) for p,q,r,s in zip(m.PrimaryRoad,m.SecondaryRoad,m.road1,m.road2)]
            m['candidate_valid']=m.lat.between(32.3,42.2)&m.lon.between(-124.6,-113.9)
            m['inside_city_buffer']=shapely.intersects_xy(polys[city],m.lon.to_numpy(),m.lat.to_numpy())
            m['crash_uid']='CA:'+str(y)+':'+m['Collision Id']
            m['eligible_link']=m.minute_agree&m.road_agree&m.candidate_valid&m.inside_city_buffer
            m['coordinate_source']=city;m['coordinate_source_file']=str(src);m['coordinate_source_sha256']=sha(src)
            m.to_csv(P/f'{city.replace(" ","_")}_{y}_linkage.csv',index=False)
            good=m.loc[m.eligible_link].copy();updates.append(good)
            summaries.append(dict(year=y,city=city,source_rows=len(b),unique_report_matches=len(m),exact_minute_matches=int(m.minute_agree.sum()),street_confirmed_matches=int(m.eligible_link.sum())))
        if not updates:continue
        changes=pd.concat(updates,ignore_index=True)
        changes=changes.loc[~changes.crash_uid.duplicated(keep=False)].set_index('crash_uid')
        c=pd.read_csv(canon,dtype=str,keep_default_na=False);original=c.copy();cols=list(c.columns);before=sha(canon)
        assert c.crash_uid.is_unique
        oldlat=pd.to_numeric(c.latitude,errors='coerce');oldlon=pd.to_numeric(c.longitude,errors='coerce')
        valid=oldlat.between(32.3,42.2)&oldlon.between(-124.6,-113.9)
        mask=~valid&c.crash_uid.isin(changes.index)
        ledger=c.loc[mask,['crash_uid','latitude','longitude','coordinate_status','pipeline_version']].copy()
        for field,dest in [('lat','latitude'),('lon','longitude')]:
            c.loc[mask,dest]=c.loc[mask,'crash_uid'].map(changes[field]).astype(str)
        # VALID means range/city-screen passed, not survey-grade positional accuracy.
        c.loc[mask,'coordinate_status']='VALID'
        ledger['new_latitude']=c.loc[mask,'latitude'];ledger['new_longitude']=c.loc[mask,'longitude']
        ledger['coordinate_source']=ledger.crash_uid.map(changes.coordinate_source)
        ledger['coordinate_source_file']=ledger.crash_uid.map(changes.coordinate_source_file)
        ledger['coordinate_source_sha256']=ledger.crash_uid.map(changes.coordinate_source_sha256)
        ledger['rule']='agency + unique report number (LAPD only: remove non-digits, require exactly nine digits; no padding/truncation) + exact local date/minute + normalized street agreement + 500m city buffer; fill missing/out-of-CA-range only'
        ledger.to_csv(P/f'CA_{y}_coordinate_changes.csv',index=False)
        assert list(c.columns)==cols and len(c)==len(a)
        assert c.loc[~mask].equals(original.loc[~mask])
        unaffected=[k for k in cols if k not in ['latitude','longitude','coordinate_status']]
        assert c[unaffected].equals(original[unaffected])
        n=int(mask.sum())
        if n:
            backup=P/'canonical_before';backup.mkdir(exist_ok=True)
            bp=backup/canon.name
            if not bp.exists():shutil.copy2(canon,bp)
            tmp=canon.with_suffix('.coordinate_update.tmp');c.to_csv(tmp,index=False,encoding='utf-8');tmp.replace(canon)
        manifest.append(dict(year=y,rows=len(c),filled=n,by_source=ledger.coordinate_source.value_counts().to_dict(),sha256_before=before,sha256_after=sha(canon)))
        print('YEAR COMPLETE',y,'filled',n,flush=True)
    pd.DataFrame(summaries).to_csv(P/'matching_summary.csv',index=False)
    (P/'run_manifest.json').write_text(json.dumps({'rules_version':'CA_LOCAL_COORDINATES_v2_LAPD_NINE_DIGITS','script_sha256':sha(Path(__file__)),'downloads_failed':failures,'years':manifest,'total_filled':sum(r['filled'] for r in manifest),'raw_files_modified':False,'attributes_changed':['latitude','longitude','coordinate_status'],'limitations':'Local geocodes may be intersection/block-level. Injury-only sources cannot recover all PDO locations. Existing valid coordinates are retained. Re-run overlay after any canonical regeneration; backups and change ledgers preserve provenance.'},indent=2),encoding='utf-8')
    print('DONE',sum(r['filled'] for r in manifest),flush=True)
