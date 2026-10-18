"""Use archived official NCDOT K/A points to fill exact-ID/date matched crashes."""
import json
import pandas as pd
from coordinate_supplement_utils import R,U,REV,sha,apply
out=REV/'NC_KA_v1';out.mkdir(parents=True,exist_ok=True)
results=[]
for year in range(2016,2027):
 p=R/f'States/NC/{year}/NCDOT_KA_crashes.csv';canon=U/f'data/crash/NC/NC_crashes_harmonized_{year}.csv'
 if not p.exists() or not canon.exists():continue
 b=pd.read_csv(p,dtype=str,keep_default_na=False)
 b=b.loc[~b.Crash_ID.duplicated(keep=False)&b.Crash_ID.ne('')].copy()
 b['crash_uid']='NC:'+b.Crash_ID
 b['donor_date']=pd.to_datetime(b.Date.str.rstrip('.'),format='%m/%d/%Y',errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
 a=pd.read_csv(canon,dtype=str,keep_default_na=False,usecols=['crash_uid','crash_date'])
 m=a.merge(b,on='crash_uid',validate='one_to_one')
 m['date_agree']=m.crash_date.ne('')&m.crash_date.eq(m.donor_date)
 m.to_csv(out/f'NC_{year}_linkage.csv',index=False)
 good=m.loc[m.date_agree].copy()
 good['candidate_lat']=good['__geometry_latitude_wgs84'];good['candidate_lon']=good['__geometry_longitude_wgs84']
 good['coordinate_source']='NCDOT official fatal and serious injury crash GIS';good['coordinate_source_file']=str(p);good['coordinate_source_sha256']=sha(p)
 good['linkage_rule']='Unique exact statewide Crash_ID + exact crash date; archived official geocoded point; Census state boundary 2km screen; fill missing only.'
 results.append(apply('NC',year,good[['crash_uid','candidate_lat','candidate_lon','coordinate_source','coordinate_source_file','coordinate_source_sha256','linkage_rule']], 'NC_KA_v1'))
(out/'manifest.json').write_text(json.dumps({'results':results,'total_filled':sum(r['filled'] for r in results),'limitation':'K/A injury subset only; does not restore all-severity statewide geography. Canonical dates and clocks are not changed.','script_sha256':sha(__file__)},indent=2),encoding='utf-8')
print('NC KA COMPLETE',sum(r['filled'] for r in results),flush=True)
