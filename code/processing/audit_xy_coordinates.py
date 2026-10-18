"""Read-only XY/CRS validation for MT and NV; official inputs never change."""
import json, hashlib, requests, os
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from pyproj import Transformer
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(os.environ.get('USCRASH_ROOT',str(Path(__file__).resolve().parents[2])))
U=ROOT/'Unified_MMUCC6';OUT=U/'qa/coordinate_revision_2026-10-14'
OUT.mkdir(parents=True,exist_ok=True)
COUNTY_URL='https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip'
countyfile=OUT/'us_counties_census_2023.zip'
if not countyfile.exists():
 r=requests.get(COUNTY_URL,timeout=90);r.raise_for_status();countyfile.write_bytes(r.content)
counties=gpd.read_file(countyfile).to_crs(5070)
states=gpd.read_file(U/'qa/spatiotemporal_review_2026-10-14/reference/us_states_census_2023.zip').to_crs(5070)
to5070=Transformer.from_crs(4326,5070,always_xy=True)
summaries=[];examples=[];inputs=[]
for st,epsg,years,xfield,yfield,countfield,fips in [
 ('MT',32100,range(2016,2026),'X Coordinate','Y Coordinate','County Name','30'),
 ('NV',26911,range(2020,2025),'POINT_X','POINT_Y','County','32')]:
 tx=Transformer.from_crs(epsg,4326,always_xy=True)
 state=states.loc[states.STUSPS.eq(st),'geometry'].iloc[0]
 countygeoms={row.NAME.upper().replace(' COUNTY',''):row.geometry.buffer(2000) for _,row in counties[counties.STATEFP.eq(fips)].iterrows()}
 for y in years:
  path=ROOT/'States'/st/str(y)/('MDT_Crash_enriched.csv' if st=='MT' else f'CSV/NV_Official_Crash_enriched_{y}.csv')
  d=pd.read_csv(path,dtype=str,keep_default_na=False)
  x=pd.to_numeric(d[xfield],errors='coerce').to_numpy(float);z=pd.to_numeric(d[yfield],errors='coerce').to_numpy(float)
  good=np.isfinite(x)&np.isfinite(z)&(x!=0)&(z!=0)
  lon=np.full(len(d),np.nan);lat=lon.copy();lon[good],lat[good]=tx.transform(x[good],z[good])
  xmin,ymin,xmax,ymax=json.loads((U/'config/states'/f'{st}.json').read_text())['coordinate_bounds']
  valid=good&(lon>=xmin)&(lon<=xmax)&(lat>=ymin)&(lat<=ymax)
  px,pz=to5070.transform(lon[valid],lat[valid]);inside=shapely.contains_xy(state.buffer(2000),px,pz)
  supplied=d.loc[valid,countfield].str.upper().str.replace(' COUNTY','',regex=False)
  known=supplied.isin(countygeoms);match=np.zeros(int(valid.sum()),bool)
  for name in supplied[known].unique():
   mask=supplied.eq(name).to_numpy();match[mask]=shapely.contains_xy(countygeoms[name],np.asarray(px)[mask],np.asarray(pz)[mask])
  item=dict(state=st,year=y,records=len(d),source_crs=f'EPSG:{epsg}',valid_bounds=int(valid.sum()),missing_or_zero=int((~good).sum()),out_of_bounds=int((good&~valid).sum()),outside_state_2km=int((~inside).sum()),county_comparable=int(known.sum()),county_match_2km=int((match&known.to_numpy()).sum()))
  if st=='NV':
   oldlon=pd.to_numeric(d.Longitude_WGS84,errors='coerce').to_numpy(float);oldlat=pd.to_numeric(d.Latitude_WGS84,errors='coerce').to_numpy(float)
   delta=np.maximum(np.abs(oldlon[valid]-lon[valid]),np.abs(oldlat[valid]-lat[valid]));assert np.isfinite(delta).all()
   item['max_existing_difference_degrees']=float(delta.max());assert delta.max()<1e-7
  summaries.append(item)
  inputs.append(dict(file=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
  for i in np.flatnonzero(valid)[:3]:
   examples.append(dict(state=st,year=y,crash_id=d.iloc[i]['Crash ID' if st=='MT' else 'CrashNum'],city=d.iloc[i]['City Name' if st=='MT' else 'City'],county=d.iloc[i][countfield],source_x=x[i],source_y=z[i],longitude=lon[i],latitude=lat[i],source_crs=f'EPSG:{epsg}'))
  print(json.dumps(item),flush=True)
pd.DataFrame(summaries).to_csv(OUT/'xy_coordinate_audit.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(examples).to_csv(OUT/'converted_examples.csv',index=False,encoding='utf-8-sig')
(OUT/'source_hashes.json').write_text(json.dumps(inputs,indent=2),encoding='utf-8')
# Compare actual source XY with official hosted crash point geometry.
probes={
 'MT':('https://gis.mtmdt.us/server/rest/services/MDTGIS/Public_Crash_Information/MapServer/0/query',{'where':'X_COORD >= 605797.5 AND X_COORD <= 605798.6 AND Y_COORD >= 312908 AND Y_COORD <= 312909','outFields':'*','outSR':4326}),
 'NV':('https://services9.arcgis.com/eNX73FDxjlKFtCtH/ArcGIS/rest/services/NDOT_FY2024_Crashes_2019_2023/FeatureServer/3/query',{'where':'Crash_Year=2023','geometry':'347950,4370545,347955,4370550','geometryType':'esriGeometryEnvelope','inSR':26911,'outSR':4326,'outFields':'Crash_Date,Crash_Time,County,Primary_Street,Accident_Rec_Num','spatialRel':'esriSpatialRelIntersects'}),
}
def probe(kv):
 st,(url,params)=kv
 try:
  r=requests.get(url,params=dict(params,f='json',returnGeometry='true',resultRecordCount=20),timeout=40);r.raise_for_status();d=r.json()
  (OUT/(st+'_official_point_probe.json')).write_text(json.dumps({'url':r.url,'response':d},indent=2),encoding='utf-8')
  print(st,'PROBE',json.dumps(d)[:3000],flush=True)
 except Exception as e: print(st,'PROBE_FAILED',str(e),flush=True)
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(probe,probes.items()))
