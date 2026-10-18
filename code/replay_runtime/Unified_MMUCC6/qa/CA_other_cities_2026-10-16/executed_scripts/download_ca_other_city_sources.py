"""Cache official public CA city/region point sources with completeness checks."""
import os as _uscrash_paths_os
from pathlib import Path
import requests,json,hashlib
from concurrent.futures import ThreadPoolExecutor
R=Path(_uscrash_paths_os.environ['USCRASH_ROOT']);S=R/'States/CA/Local_coordinate_sources_2026-10-16'
def download_gis(name,u):
 p=S/name;p.mkdir(exist_ok=True);j=requests.get(u,params={'f':'json'},timeout=60).json();(p/'metadata.json').write_text(json.dumps(j));ids=requests.get(u+'/query',params={'f':'json','where':'1=1','returnIdsOnly':'true'},timeout=60).json()['objectIds'];rows=[]
 for n in range(0,len(ids),500):
  f=p/f'batch_{n:06}.json'
  if f.exists():b=json.loads(f.read_text())
  else:
   b=requests.post(u+'/query',data={'f':'json','objectIds':','.join(map(str,ids[n:n+500])),'outFields':'*','outSR':4326,'returnGeometry':'true'},timeout=120).json();assert 'features' in b,b;f.write_text(json.dumps(b))
  assert len(b['features'])==len(ids[n:n+500]);rows+=b['features']
 (p/'download_manifest.json').write_text(json.dumps({'url':u,'count':len(ids),'records_downloaded':len(rows),'outSR':4326}));print(name,len(rows),flush=True)
def sandag(y):
 p=S/'SANDAG';p.mkdir(exist_ok=True);f=p/f'SANDAG_{y}.json';u='https://opendata.sandag.org/resource/uzct-sb5t.json'
 where=f'accident_year={y}';n=int(requests.get(u,params={'$where':where,'$select':'count(*) as n'},timeout=90).json()[0]['n'])
 if f.exists():rows=json.loads(f.read_text());assert len(rows)==n;return
 rows=[];fields='sandag_case_id,accident_year,collision_date,collision_time,primary_rd,secondary_rd,number_killed,number_injured,party_count,collision_severity,latitude_sandag,longitude_sandag,intersection,direction,postmile,state_route'
 for o in range(0,n,10000):
  r=requests.get(u,params={'$where':where,'$select':fields,'$order':'sandag_case_id,:id','$limit':10000,'$offset':o},timeout=120);r.raise_for_status();j=r.json();assert isinstance(j,list);rows+=j
 assert len(rows)==n;f.write_text(json.dumps(rows));(p/f'manifest_{y}.json').write_text(json.dumps({'url':u,'where':where,'fields':fields,'expected':n,'downloaded':len(rows),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}));print('SANDAG',y,n,flush=True)
if __name__=='__main__':
 download_gis('SacramentoCity','https://services5.arcgis.com/54falWtcpty3V47Z/arcgis/rest/services/City_of_Sacramento_Crash_Data/FeatureServer/0')
 download_gis('Pasadena','https://services2.arcgis.com/zNjnZafDYCAJAbN0/arcgis/rest/services/Traffic_Collisions/FeatureServer/0')
 with ThreadPoolExecutor(max_workers=3) as ex:list(ex.map(sandag,range(2016,2024)))
