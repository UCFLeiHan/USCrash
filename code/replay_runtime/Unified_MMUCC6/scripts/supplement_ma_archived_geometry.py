"""Recover existing declared WGS84 geometry when reported MA LAT/LON is absent."""
import json,pandas as pd
from coordinate_supplement_utils import R,U,REV,sha,apply
OUT=REV/'MA_archived_geometry_v1';OUT.mkdir(parents=True,exist_ok=True)
results=[]
for year in range(2021,2027):
 p=R/f'States/MA/{year}/MassDOT_{year}_Crash.csv';cp=U/f'data/crash/MA/MA_crashes_harmonized_{year}.csv'
 if not p.exists():continue
 b=pd.read_csv(p,dtype=str,keep_default_na=False,usecols=['CRASH_NUMB','CRASH_DATE_TEXT','__geometry_latitude_wgs84','__geometry_longitude_wgs84'])
 b['source_crash_id']=b.CRASH_NUMB;b=b.loc[b.source_crash_id.ne('')&~b.source_crash_id.duplicated(keep=False)].copy()
 b['donor_date']=pd.to_datetime(b.CRASH_DATE_TEXT,format='mixed',errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
 a=pd.read_csv(cp,dtype=str,keep_default_na=False,usecols=['crash_uid','source_crash_id','crash_date'])
 m=a.merge(b,on='source_crash_id',validate='one_to_one');m['date_agree']=m.crash_date.ne('')&m.crash_date.eq(m.donor_date)
 m.to_csv(OUT/f'MA_{year}_linkage.csv',index=False)
 good=m.loc[m.date_agree].copy();good['candidate_lat']=good['__geometry_latitude_wgs84'];good['candidate_lon']=good['__geometry_longitude_wgs84']
 good['coordinate_source']='MassDOT official archived GIS geometry, declared EPSG:4326 export'
 good['coordinate_source_file']=str(p);good['coordinate_source_sha256']=sha(p)
 good['coordinate_method']='SOURCE_PUBLISHED_GEOMETRY_NOT_REPORTED_LAT_LON'
 good['linkage_rule']='Same preserved source file, exact unique CRASH_NUMB and date; declared WGS84 geometry; fill missing reported LAT/LON only, state-polygon screen.'
 results.append(apply('MA',year,good[['crash_uid','candidate_lat','candidate_lon','coordinate_source','coordinate_source_file','coordinate_source_sha256','coordinate_method','linkage_rule']],'MA_archived_geometry_v1'))
(OUT/'manifest.json').write_text(json.dumps({'results':results,'total_filled':sum(x['filled'] for x in results),'script_sha256':sha(__file__)},indent=2),encoding='utf-8');print('MA GEOMETRY COMPLETE',sum(x['filled'] for x in results),flush=True)
