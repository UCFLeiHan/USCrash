"""Fill statewide CRIS missing locations from preserved official Austin exports."""
import pandas as pd,json
from coordinate_supplement_utils import R,U,REV,sha,apply
OUT=REV/'TX_Austin_v1';OUT.mkdir(parents=True,exist_ok=True)
results=[]
for year in range(2019,2027):
 p=R/f'Cities/Austin/{year}/Austin_crashes.csv';cp=U/f'data/crash/TX/TX_crashes_harmonized_{year}.csv'
 if not p.exists() or not cp.exists():continue
 b=pd.read_csv(p,dtype=str,keep_default_na=False,usecols=['cris_crash_id','latitude','longitude','crash_timestamp_ct','is_deleted','is_temp_record'])
 b=b.loc[~b.is_deleted.str.lower().eq('true')&~b.is_temp_record.str.lower().eq('true')].copy()
 b['source_crash_id']=b.cris_crash_id.str.replace(r'\.0$','',regex=True)
 b=b.loc[b.source_crash_id.str.fullmatch(r'\d+')]
 b=b.drop_duplicates(subset=['source_crash_id','latitude','longitude','crash_timestamp_ct'])
 b=b.loc[~b.source_crash_id.duplicated(keep=False)]
 dt=pd.to_datetime(b.crash_timestamp_ct,format='mixed',errors='coerce')
 b['donor_date']=dt.dt.strftime('%Y-%m-%d').fillna('');b['donor_time']=dt.dt.strftime('%H:%M').fillna('')
 a=pd.read_csv(cp,dtype=str,keep_default_na=False,usecols=['crash_uid','source_crash_id','crash_date','crash_time'])
 m=a.merge(b,on='source_crash_id',validate='one_to_one')
 m['date_agree']=m.crash_date.ne('')&m.crash_date.eq(m.donor_date)
 m['minute_agree']=m.crash_time.ne('')&m.crash_time.str[:5].eq(m.donor_time)&m.donor_time.ne('')
 m.to_csv(OUT/f'TX_{year}_linkage.csv',index=False)
 d=m.loc[m.date_agree&m.minute_agree].copy();d['candidate_lat']=d.latitude;d['candidate_lon']=d.longitude
 d['coordinate_source']='City of Austin official Vision Zero CRIS-based public crash records'
 d['coordinate_source_url']='https://data.austintexas.gov/d/y2wy-tgr5'
 d['coordinate_source_file']=str(p);d['coordinate_source_sha256']=sha(p)
 d['coordinate_method']='CITY_PUBLISHED_COORDINATE_MAY_INCLUDE_LOCAL_GEOCODING'
 d['linkage_rule']='Unique exact CRIS Crash_ID = Austin cris_crash_id; exact local date/minute; deleted/temp records excluded; missing only with state polygon screen.'
 results.append(apply('TX',year,d[['crash_uid','candidate_lat','candidate_lon','coordinate_source','coordinate_source_url','coordinate_source_file','coordinate_source_sha256','coordinate_method','linkage_rule']],'TX_Austin_v1'))
(OUT/'manifest.json').write_text(json.dumps({'results':results,'total_filled':sum(x['filled'] for x in results),'scope':'Austin subset only; no crash appended and no source GPS coordinates overwritten','script_sha256':sha(__file__)},indent=2),encoding='utf-8');print('TX AUSTIN COMPLETE',sum(x['filled'] for x in results),flush=True)
