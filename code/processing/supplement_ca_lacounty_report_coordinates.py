"""Exact agency-scoped police report number + date/roads/counts linkage."""
import os,json,re,argparse
from pathlib import Path
import pandas as pd,geopandas as gpd,shapely
R=Path(r'F:\LH_Research\USCrash\Crash');U=R/'Unified_MMUCC6';P=U/'qa/CA_other_cities_2026-10-16';S=R/'States/CA/Local_coordinate_sources_2026-10-16/LACountyReports'
os.environ['USCRASH_COORDINATE_AUDIT_ROOT']=str(P)
from coordinate_supplement_utils import apply,sha
from pilot_ca_composite_coordinates import road
from supplement_ca_other_cities import gis_rows,geometry_screen

def key(x):
 s=re.sub('[^A-Z0-9]','',str(x).upper());return s.lstrip('0') if s.isdigit() else s
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
 b=gis_rows('LACountyReports').rename(columns={'TCR_ID':'donor_id','NCIC':'agency','REPORT_NO':'report','PRIMARY_ROAD_NAME':'road1','STREET_NAME':'road2','INJURED':'injured','KILLED':'killed'})
 b['donor_date']=pd.to_datetime(b.CRASH_DT,unit='ms',errors='coerce').dt.strftime('%Y-%m-%d');b['year']=b.donor_date.str[:4];b['report_key']=b.report.map(key);b['agency']=b.agency.fillna('').astype(str).str.lstrip('0');b['roads']=['|'.join(sorted([road(x),road(y)])) if road(x) and road(y) and road(x)!=road(y) else '' for x,y in zip(b.road1,b.road2)]
 b=b.loc[b.report_key.ne('') & b.roads.ne('')].copy();b=b.loc[~b.duplicated(['agency','report_key','year'],keep=False)]
 f=S/'reviewed_exact_report_coordinate_extract.csv';b.to_csv(f,index=False);sourcehash=sha(f)
 g=gpd.read_file(P/'CA_counties.geojson').to_crs(3310);g.geometry=g.geometry.buffer(2000);g=g.to_crs(4326);county=dict(zip(((g.COUNTY.astype(int)+1)//2).astype(str),g.geometry))
 cityfile=Path(r'F:\LH_Research\USCrash\Crash\verification\reference\cb_2023_06_place_500k.zip');g=gpd.read_file(cityfile).to_crs(3310);g.geometry=g.geometry.buffer(1000);g=g.to_crs(4326);cities=dict(zip(g.NAME.str.upper(),g.geometry))
 results=[]
 fields=['Collision Id','Report Number','NCIC Code','Crash Date Time','PrimaryRoad','SecondaryRoad','NumberKilled','NumberInjured','City Name','County Code']
 for y in range(2017,2022):
  raw=R/f'States/CA/{y}/Crashes_{y}.csv';a=pd.read_csv(raw,dtype=str,keep_default_na=False,usecols=lambda c:c.strip() in fields);a.columns=a.columns.str.strip();a=a.rename(columns={'Collision Id':'id','Report Number':'report','NCIC Code':'agency','PrimaryRoad':'road1','SecondaryRoad':'road2','NumberKilled':'killed','NumberInjured':'injured','City Name':'city','County Code':'county'})
  a['report_key']=a.report.map(key);a['year']=str(y);a['agency']=a.agency.str.lstrip('0');a['date']=pd.to_datetime(a['Crash Date Time'],format='%m/%d/%Y %I:%M:%S %p',errors='coerce').dt.strftime('%Y-%m-%d');a['roads']=['|'.join(sorted([road(x),road(z)])) if road(x) and road(z) and road(x)!=road(z) else '' for x,z in zip(a.road1,a.road2)]
  a=a.loc[~a.duplicated(['agency','report_key','year'],keep=False)];m=a.merge(b.loc[b.year.eq(str(y))],on=['agency','report_key','year'],suffixes=('_raw','_donor'),validate='one_to_one')
  good=m.date.eq(m.donor_date)&m.roads_raw.ne('')&m.roads_raw.eq(m.roads_donor)
  for k in ['injured','killed']:good &= pd.to_numeric(m[k+'_raw'],errors='coerce').eq(pd.to_numeric(m[k+'_donor'],errors='coerce'))
  m=m.loc[good].copy();m['crash_uid']='CA:'+str(y)+':'+m.id;m['city_upper']=m.city.str.upper();m['county']=m.county.str.lstrip('0')
  for k in ['candidate_lat','candidate_lon']:m[k]=pd.to_numeric(m[k],errors='coerce')
  m['county_pass']=geometry_screen(m,county,'county');m['city_pass']=geometry_screen(m,cities,'city_upper');m=m.loc[m.county_pass&(~m.city_upper.isin(cities)|m.city_pass)].copy()
  m.to_csv(P/f'LACountyReports_{y}_exact_linkage.csv',index=False)
  m['coordinate_source']='LA County official all collisions2017–2021';m['coordinate_source_url']='https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/All_Collisions_2017_to_2021/FeatureServer/0';m['coordinate_source_file']=str(f);m['coordinate_source_sha256']=sourcehash;m['coordinate_method']='OFFICIAL_PUBLISHED_GEOCODE_EXACT_POLICE_REPORT_DATE_ROADS';m['linkage_rule']='Unique agency + normalized police report number + year; exact date, both normalized roads, killed and injured counts. County2km and city1km screens. Source exposes date only; no minute agreement claimed.'
  if args.apply:
   keep=['crash_uid','candidate_lat','candidate_lon','coordinate_source','coordinate_source_url','coordinate_source_file','coordinate_source_sha256','coordinate_method','linkage_rule','donor_id','city','county','report_key'];r=apply('CA',y,m[keep],'LACounty_reports_v1');results.append(r)
  else:results.append({'year':y,'exact_report_date_roads_counts_geography_matches':len(m)})
  print(results[-1],flush=True)
 (P/('LACounty_promotion_manifest.json' if args.apply else 'LACounty_dryrun_manifest.json')).write_text(json.dumps({'results':results,'script_sha256':sha(__file__)},indent=2))
