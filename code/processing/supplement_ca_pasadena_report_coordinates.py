"""Pasadena exact report ID linkage with independent timestamp/road/outcome checks."""
import os,json,re
from pathlib import Path
import pandas as pd,geopandas as gpd,shapely
R=Path(r'F:\LH_Research\USCrash\Crash');U=R/'Unified_MMUCC6';P=U/'qa/CA_other_cities_2026-10-16';S=R/'States/CA/Local_coordinate_sources_2026-10-16/Pasadena';os.environ['USCRASH_COORDINATE_AUDIT_ROOT']=str(P)
from coordinate_supplement_utils import apply,sha
from supplement_ca_other_cities import gis_rows
from pilot_ca_composite_coordinates import road

def key(x):
 s=re.sub('[^A-Z0-9]','',str(x).upper());return s.lstrip('0') if s.isdigit() else s
b=gis_rows('Pasadena').rename(columns={'Accidno':'report','Street':'road1','CrossSt':'road2','NoKilled':'killed','NoInjured':'injured'})
b['donor_id']=b.report;b['donor_minute']=pd.to_datetime(b.Date.astype(str)+' '+b.Time.astype(str),format='mixed',errors='coerce').dt.strftime('%Y-%m-%dT%H:%M');b['year']=b.donor_minute.str[:4];b['report_key']=b.report.map(key);b['roads']=['|'.join(sorted([road(x),road(y)])) if road(x) and road(y) and road(x)!=road(y) else '' for x,y in zip(b.road1,b.road2)]
b=b.loc[b.report_key.ne('')&b.roads.ne('')&~b.duplicated(['report_key','year'],keep=False)].copy();f=S/'reviewed_exact_report_coordinate_extract.csv';b.to_csv(f,index=False);sourcehash=sha(f)
cityfile=Path(r'F:\LH_Research\USCrash\Crash\verification\reference\cb_2023_06_place_500k.zip');g=gpd.read_file(cityfile);g=g.loc[g.NAME.eq('Pasadena')].to_crs(3310);g.geometry=g.geometry.buffer(1000);polygon=g.to_crs(4326).geometry.iloc[0]
results=[];fields=['Collision Id','Report Number','NCIC Code','Crash Date Time','PrimaryRoad','SecondaryRoad','NumberKilled','NumberInjured','City Name','County Code']
for y in range(2016,2027):
 a=pd.read_csv(R/f'States/CA/{y}/Crashes_{y}.csv',dtype=str,keep_default_na=False,usecols=lambda c:c.strip() in fields);a.columns=a.columns.str.strip();a=a.loc[a['NCIC Code'].eq('1953')].copy();a=a.rename(columns={'Collision Id':'id','Report Number':'report','PrimaryRoad':'road1','SecondaryRoad':'road2','NumberKilled':'killed','NumberInjured':'injured','City Name':'city','County Code':'county'})
 a['report_key']=a.report.map(key);a['minute']=pd.to_datetime(a['Crash Date Time'],format='%m/%d/%Y %I:%M:%S %p',errors='coerce').dt.strftime('%Y-%m-%dT%H:%M');a['roads']=['|'.join(sorted([road(x),road(z)])) if road(x) and road(z) and road(x)!=road(z) else '' for x,z in zip(a.road1,a.road2)];a=a.loc[~a.report_key.duplicated(keep=False)]
 m=a.merge(b.loc[b.year.eq(str(y))],on='report_key',suffixes=('_raw','_donor'),validate='one_to_one');good=m.minute.notna()&m.minute.eq(m.donor_minute)&m.roads_raw.ne('')&m.roads_raw.eq(m.roads_donor)
 for k in ['injured','killed']:good &= pd.to_numeric(m[k+'_raw'],errors='coerce').eq(pd.to_numeric(m[k+'_donor'],errors='coerce'))
 m=m.loc[good].copy();m['crash_uid']='CA:'+str(y)+':'+m.id
 for k in ['candidate_lat','candidate_lon']:m[k]=pd.to_numeric(m[k],errors='coerce')
 m=m.loc[shapely.covers(polygon,shapely.points(m.candidate_lon,m.candidate_lat))].copy();m.to_csv(P/f'Pasadena_{y}_exact_report_linkage.csv',index=False)
 m['coordinate_source']='Pasadena official traffic collision GIS';m['coordinate_source_url']='https://services2.arcgis.com/zNjnZafDYCAJAbN0/arcgis/rest/services/Traffic_Collisions/FeatureServer/0';m['coordinate_source_file']=str(f);m['coordinate_source_sha256']=sourcehash;m['coordinate_method']='OFFICIAL_PUBLISHED_GEOCODE_EXACT_POLICE_REPORT_MINUTE_ROADS';m['linkage_rule']='NCIC1953, exact normalized Accidno versus CCRS police Report Number, unique both sides; same date/minute, both normalized roads and killed/injured counts; Pasadena boundary buffered1km and California state screen. Older pseudonymous Accidno values are not decoded or guessed.'
 keep=['crash_uid','candidate_lat','candidate_lon','coordinate_source','coordinate_source_url','coordinate_source_file','coordinate_source_sha256','coordinate_method','linkage_rule','donor_id','city','county','report_key'];results.append(apply('CA',y,m[keep],'Pasadena_reports_v1'))
(P/'Pasadena_promotion_manifest.json').write_text(json.dumps({'results':results,'total_filled':sum(x['filled'] for x in results),'script_sha256':sha(__file__)},indent=2));print('PASADENA COMPLETE',sum(x['filled'] for x in results),flush=True)
