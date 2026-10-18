"""Non-destructive proof of coordinate recovery from local official SF data.
Do not append City records or overwrite existing CCRS coordinates. Only unique
agency/report-number links with exact date and minute agreement are accepted.
"""
from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np,geopandas as gpd,shapely
from pyproj import Geod
R=Path(r'F:\LH_Research\USCrash\Crash');P=R/'Unified_MMUCC6/qa/CA_coordinate_recovery_pilot_2026-10-16';P.mkdir(exist_ok=True)
YEAR=2023
raw=R/f'States/CA/{YEAR}/Crashes_{YEAR}.csv';city=R/f'Cities/SanFrancisco/{YEAR}/DataSF_injury_crashes.csv'
fields=['Collision Id','Report Number','NCIC Code','City Name','Crash Date Time','Latitude','Longitude']
a=pd.read_csv(raw,dtype=str,keep_default_na=False,usecols=lambda c:c.strip() in fields);a.columns=a.columns.str.strip()
b=pd.read_csv(city,dtype=str,keep_default_na=False)
a=a.loc[a['NCIC Code'].eq('3801')].copy();a['report_key']=a['Report Number'].str.strip();b['report_key']=b.case_id_pkey.str.strip()
au=a.loc[a.report_key.ne('')&~a.report_key.duplicated(keep=False)]
bu=b.loc[b.report_key.ne('')&~b.report_key.duplicated(keep=False)]
m=au.merge(bu,on='report_key',validate='one_to_one',suffixes=('_ccrs','_sf'))
m['ccrs_datetime']=pd.to_datetime(m['Crash Date Time'],format='%m/%d/%Y %I:%M:%S %p',errors='coerce')
m['sf_datetime']=pd.to_datetime(m.collision_datetime,format='mixed',errors='coerce')
m['date_agree']=m.ccrs_datetime.dt.date.eq(m.sf_datetime.dt.date)&m.ccrs_datetime.notna()&m.sf_datetime.notna()
m['minute_agree']=m.ccrs_datetime.dt.floor('min').eq(m.sf_datetime.dt.floor('min'))&m.ccrs_datetime.notna()&m.sf_datetime.notna()
for target,src in [('candidate_latitude','tb_latitude'),('candidate_longitude','tb_longitude'),('old_latitude','Latitude'),('old_longitude','Longitude')]:m[target]=pd.to_numeric(m[src],errors='coerce')
m['candidate_valid']=m.candidate_latitude.between(32.3,42.2)&m.candidate_longitude.between(-124.6,-113.9)
m['old_valid']=m.old_latitude.between(32.3,42.2)&m.old_longitude.between(-124.6,-113.9)
# Use the already archived Census SF boundary only to screen city/coordinate
# gross mismatches. 500 m is a review tolerance, not a position correction.
boundary=Path(r'F:\LH_Research\USCrash\Crash\verification\reference\cb_2023_06_place_500k.zip')
g=gpd.read_file(boundary);g=g.loc[g.NAME.eq('San Francisco')].to_crs(32610);g.geometry=g.geometry.buffer(500);poly=g.to_crs(4326).geometry.iloc[0];shapely.prepare(poly)
m['inside_SF_500m']=shapely.intersects_xy(poly,m.candidate_longitude.to_numpy(),m.candidate_latitude.to_numpy())
m['eligible_missing_coordinate_fill']=m.minute_agree&m.candidate_valid&m.inside_SF_500m&~m.old_valid
m['decision']=np.select([m.eligible_missing_coordinate_fill,~m.minute_agree,~m.candidate_valid,~m.inside_SF_500m,m.old_valid],['CANDIDATE_FILL_NOT_PROMOTED','DATE_OR_TIME_CONFLICT_REVIEW','CANDIDATE_COORDINATE_INVALID','OUTSIDE_CITY_REVIEW','EXISTING_COORDINATE_RETAINED'],default='REVIEW')
m['crash_uid']='CA:'+str(YEAR)+':'+m['Collision Id'];m['agency']='3801'
keep=['crash_uid','Collision Id','report_key','agency','Crash Date Time','collision_datetime','candidate_latitude','candidate_longitude','old_latitude','old_longitude','geocode_source','date_agree','minute_agree','inside_SF_500m','decision']
m[keep].to_csv(P/'SF_2023_linkage_candidates.csv',index=False,encoding='utf-8-sig')
m.loc[m.eligible_missing_coordinate_fill,keep].to_csv(P/'SF_2023_verified_missing_coordinate_fill_candidates.csv',index=False,encoding='utf-8-sig')
both=m.minute_agree&m.candidate_valid&m.old_valid
dist=[]
if both.any():
    d=m.loc[both];_,_,dist=Geod(ellps='WGS84').inv(d.old_longitude.to_numpy(),d.old_latitude.to_numpy(),d.candidate_longitude.to_numpy(),d.candidate_latitude.to_numpy())
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
out={'year':YEAR,'city':'San Francisco','source_files':[{'path':str(p),'sha256':sha(p)} for p in [raw,city]],'CCRS_SFPD_rows':len(a),'city_rows':len(b),'duplicate_report_rows_excluded_CCRS':int(a.report_key.duplicated(keep=False).sum()),'duplicate_report_rows_excluded_city':int(b.report_key.duplicated(keep=False).sum()),'unique_report_matches':len(m),'exact_date_matches':int(m.date_agree.sum()),'exact_minute_matches':int(m.minute_agree.sum()),'eligible_missing_coordinate_fill_candidates':int(m.eligible_missing_coordinate_fill.sum()),'candidate_decisions':m.decision.value_counts().to_dict(),'existing_coordinate_comparisons':len(dist),'existing_coordinate_distance_median_m':float(np.median(dist)) if len(dist) else None,'existing_coordinate_distance_p95_m':float(np.quantile(dist,.95)) if len(dist) else None,'data_promoted':False,'original_and_canonical_data_modified':False,'scope':'City dataset is injury/fatal focused; it does not restore coordinates for every CCRS property-damage-only crash. Exact-match eligibility is not independent validation of coordinate accuracy.','join_key':'CCRS NCIC 3801 + exact Report Number = official SF case_id_pkey; exact date and minute required. Do not equate SF case_id_pkey with CCRS Collision Id.'}
(P/'SF_2023_pilot_report.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
