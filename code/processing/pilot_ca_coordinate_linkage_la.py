"""Stage candidate coordinate recovery from official LAPD historical records.
Only report IDs/date/minute are linked. No canonical crash file is modified.
"""
from pathlib import Path
import json,hashlib,requests
import pandas as pd,numpy as np,geopandas as gpd,shapely
from pyproj import Geod
R=Path(r'F:\LH_Research\USCrash\Crash');P=R/'Unified_MMUCC6/qa/CA_coordinate_recovery_pilot_2026-10-16';P.mkdir(exist_ok=True)
BASE='https://data.lacity.org';ID='d5tf-ez2w'
session=requests.Session()
response=session.get(BASE+f'/api/views/{ID}.json',timeout=60);response.raise_for_status();meta=response.json()
(P/'LAPD_source_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
where="date_occ >= '2023-01-01T00:00:00' AND date_occ < '2024-01-01T00:00:00'"
r=session.get(BASE+f'/resource/{ID}.json',params={'$where':where,'$select':'count(*) as n'},timeout=60);r.raise_for_status();expected=int(r.json()[0]['n'])
rows=[]
for offset in range(0,expected,10000):
    q={'$where':where,'$select':'dr_no,date_occ,time_occ,location_1','$order':':id','$offset':offset,'$limit':10000}
    r=session.get(BASE+f'/resource/{ID}.json',params=q,timeout=60);r.raise_for_status();batch=r.json();assert isinstance(batch,list)
    rows.extend(batch)
assert len(rows)==expected
(P/'LAPD_2023_selected_source.json').write_text(json.dumps(rows),encoding='utf-8')
records=[]
for row in rows:
    loc=row.get('location_1') or {}
    records.append({'report_key':row.get('dr_no','').strip(),'date_occ':row.get('date_occ',''),'time_occ':row.get('time_occ',''),'candidate_latitude':loc.get('latitude',''),'candidate_longitude':loc.get('longitude','')})
b=pd.DataFrame(records).fillna('')
# Collapse only exact duplicates across the selected linkage/location fields;
# disagreements within a report remain ambiguous and are not accepted.
b=b.drop_duplicates();ambiguous=b.report_key.duplicated(keep=False)
bu=b.loc[b.report_key.ne('')&~ambiguous].copy()
raw=R/'States/CA/2023/Crashes_2023.csv';wanted=['Collision Id','Report Number','NCIC Code','Crash Date Time','Latitude','Longitude']
a=pd.read_csv(raw,dtype=str,keep_default_na=False,usecols=lambda c:c.strip() in wanted);a.columns=a.columns.str.strip();a=a.loc[a['NCIC Code'].eq('1942')].copy();a['report_key']=a['Report Number'].str.strip()
au=a.loc[a.report_key.ne('')&~a.report_key.duplicated(keep=False)]
m=au.merge(bu,on='report_key',validate='one_to_one')
m['ccrs_datetime']=pd.to_datetime(m['Crash Date Time'],format='%m/%d/%Y %I:%M:%S %p',errors='coerce')
day=pd.to_datetime(m.date_occ,format='mixed',errors='coerce')
hhmm=m.time_occ.astype(str).str.zfill(4)
hh=pd.to_numeric(hhmm.str[:2],errors='coerce');mm=pd.to_numeric(hhmm.str[2:],errors='coerce')
clockvalid=hhmm.str.fullmatch(r'\d{4}')&hh.between(0,23)&mm.between(0,59)
m['lapd_datetime']=day+pd.to_timedelta(hh.where(clockvalid),unit='h')+pd.to_timedelta(mm.where(clockvalid),unit='m')
m['date_agree']=m.ccrs_datetime.dt.date.eq(day.dt.date)&m.ccrs_datetime.notna()&day.notna()
m['minute_agree']=m.ccrs_datetime.dt.floor('min').eq(m.lapd_datetime.dt.floor('min'))&m.ccrs_datetime.notna()&m.lapd_datetime.notna()
for dest,src in [('old_latitude','Latitude'),('old_longitude','Longitude'),('candidate_latitude','candidate_latitude'),('candidate_longitude','candidate_longitude')]:m[dest]=pd.to_numeric(m[src],errors='coerce')
m['old_valid']=m.old_latitude.between(32.3,42.2)&m.old_longitude.between(-124.6,-113.9)
m['candidate_valid']=m.candidate_latitude.between(32.3,42.2)&m.candidate_longitude.between(-124.6,-113.9)
geo=gpd.read_file(Path(r'F:\LH_Research\USCrash\Crash\verification\reference\Los_Angeles_boundary.geojson')).to_crs(32611);geo.geometry=geo.geometry.buffer(500);poly=geo.to_crs(4326).geometry.iloc[0];shapely.prepare(poly)
m['inside_LA_500m']=shapely.intersects_xy(poly,m.candidate_longitude.to_numpy(),m.candidate_latitude.to_numpy())
m['eligible']=m.minute_agree&m.candidate_valid&m.inside_LA_500m&~m.old_valid
m['decision']=np.select([m.eligible,~m.minute_agree,~m.candidate_valid,~m.inside_LA_500m,m.old_valid],['CANDIDATE_FILL_NOT_PROMOTED','DATE_OR_TIME_CONFLICT_REVIEW','CANDIDATE_COORDINATE_INVALID','OUTSIDE_CITY_REVIEW','EXISTING_COORDINATE_RETAINED'],default='REVIEW')
m['crash_uid']='CA:2023:'+m['Collision Id'];m['coordinate_source']='LAPD_OFFICIAL_HISTORICAL_PORTAL'
m.to_csv(P/'LA_2023_linkage_candidates.csv',index=False,encoding='utf-8-sig');m.loc[m.eligible].to_csv(P/'LA_2023_missing_coordinate_fill_candidates.csv',index=False,encoding='utf-8-sig')
both=m.minute_agree&m.candidate_valid&m.old_valid;distance=[]
if both.any():
    d=m.loc[both];_,_,distance=Geod(ellps='WGS84').inv(d.old_longitude.to_numpy(),d.old_latitude.to_numpy(),d.candidate_longitude.to_numpy(),d.candidate_latitude.to_numpy())
report={'year':2023,'city':'Los Angeles','official_source':BASE+f'/d/{ID}','source_description':meta.get('description'),'source_selected_rows':len(rows),'source_distinct_selected_rows':len(b),'source_ambiguous_report_rows_excluded':int(ambiguous.sum()),'CCRS_LAPD_rows':len(a),'CCRS_duplicate_report_rows_excluded':int(a.report_key.duplicated(keep=False).sum()),'unique_report_matches':len(m),'exact_date_matches':int(m.date_agree.sum()),'exact_minute_matches':int(m.minute_agree.sum()),'eligible_missing_coordinate_fill_candidates':int(m.eligible.sum()),'candidate_decisions':m.decision.value_counts().to_dict(),'existing_coordinate_comparison_count':len(distance),'existing_coordinate_distance_median_m':float(np.median(distance)) if len(distance) else None,'existing_coordinate_distance_p95_m':float(np.quantile(distance,.95)) if len(distance) else None,'data_promoted':False,'original_and_canonical_data_modified':False,'source_sha256':hashlib.sha256((P/'LAPD_2023_selected_source.json').read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'join_key':'NCIC 1942 + exact report number = LAPD DR Number; exact local date and minute required.','caution':'Official source is historical, transcribed and may contain inaccuracies. Location precision/privacy limitations must be preserved, not assumed to be officer GPS.'}
(P/'LA_2023_pilot_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
