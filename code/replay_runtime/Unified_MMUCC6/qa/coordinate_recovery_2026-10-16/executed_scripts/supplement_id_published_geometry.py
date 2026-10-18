"""Restore ITD published map geometry; never infer points from blank GPS fields."""
import json,requests,pandas as pd
import geopandas as gpd,shapely
from coordinate_supplement_utils import R,U,REV,sha,apply
OUT=REV/'ID_published_geometry_v2';OUT.mkdir(parents=True,exist_ok=True)
g=gpd.read_file(REV/'ID_county_boundaries.geojson').to_crs(5070);g.geometry=g.geometry.buffer(2000);g=g.to_crs(4326);county_polygons=dict(zip(g.NAME.str.replace(' County','').str.upper(),g.geometry))
results=[]
for year,layer in [(2005,0),(2006,1),(2007,2)]:
 base=f'https://gis.itd.idaho.gov/arcgisprod/rest/services/ArcGISOnline/CrashLayers/MapServer/{layer}'
 cache=R/f'States/ID/_CoordinateSources_2026-10-16/{year}';cache.mkdir(parents=True,exist_ok=True)
 def query(params):
  r=requests.get(base+'/query',params={'f':'json',**params},timeout=180);r.raise_for_status();j=r.json()
  if 'error' in j:raise RuntimeError(j['error'])
  return j
 ids=sorted(query({'where':'1=1','returnIdsOnly':'true'})['objectIds']);features=[]
 (cache/'ids.json').write_text(json.dumps(ids))
 for i in range(0,len(ids),1000):
  f=cache/f'page_{i//1000:04}.json'
  if f.exists():j=json.loads(f.read_text())
  else:
   j=query({'where':f'OBJECTID >= {min(ids[i:i+1000])} AND OBJECTID <= {max(ids[i:i+1000])}','outFields':'*','outSR':4326,'returnGeometry':'true'})
   f.write_text(json.dumps(j))
  assert len(j['features'])==len(ids[i:i+1000]);features+=j['features']
 rows=[]
 for f in features:
  a=f['attributes'];g=f.get('geometry') or {};rows.append({**a,'candidate_lat':g.get('y'),'candidate_lon':g.get('x')})
 b=pd.DataFrame(rows);b['source_crash_id']=b.Serial_Number.astype(str)
 b=b.loc[~b.source_crash_id.duplicated(keep=False)].copy()
 b['donor_datetime']=pd.to_datetime(b.Accident_Date_Time,unit='ms',errors='coerce').dt.strftime('%Y-%m-%dT%H:%M:%S')
 donor=cache/'coordinate_extract.csv';b.to_csv(donor,index=False)
 a=pd.read_csv(U/f'data/crash/ID/ID_crashes_harmonized_{year}.csv',dtype=str,keep_default_na=False,usecols=['crash_uid','source_crash_id','crash_datetime','county'])
 m=a.merge(b,on='source_crash_id',validate='one_to_one');m['time_agree']=m.crash_datetime.ne('')&m.crash_datetime.eq(m.donor_datetime)
 m.to_csv(OUT/f'ID_{year}_linkage.csv',index=False)
 m['county_screen']=False
 for county,part in m.groupby('county'):
  key=str(county).upper()
  if key in county_polygons:m.loc[part.index,'county_screen']=shapely.covers(county_polygons[key],shapely.points(pd.to_numeric(part.candidate_lon,errors='coerce'),pd.to_numeric(part.candidate_lat,errors='coerce')))
 m.to_csv(OUT/f'ID_{year}_county_linkage.csv',index=False)
 good=m.loc[m.time_agree & m.county_screen].copy();good['coordinate_source']=base;good['coordinate_source_file']=str(donor);good['coordinate_source_sha256']=sha(donor)
 good['coordinate_method']='ITD_PUBLISHED_MAP_GEOMETRY_REPORTED_GPS_MAY_BE_ABSENT'
 good['linkage_rule']='Exact unique Serial_Number and full date/time; server-declared outSR4326; state and source-county polygons each buffered 2km; retain existing VALID locations. Published map geometry may reflect route/milepoint geocoding, not reported GPS.'
 results.append(apply('ID',year,good[['crash_uid','candidate_lat','candidate_lon','coordinate_source','coordinate_source_file','coordinate_source_sha256','coordinate_method','linkage_rule']],'ID_published_geometry_v2'))
 (cache/'download_manifest.json').write_text(json.dumps({'url':base,'count':len(ids),'pages':len(list(cache.glob('page_*.json'))),'extract_sha256':sha(donor)}))
(OUT/'manifest.json').write_text(json.dumps({'results':results,'total_filled':sum(x['filled'] for x in results),'script_sha256':sha(__file__)},indent=2));print('ID COMPLETE',sum(x['filled'] for x in results),flush=True)
