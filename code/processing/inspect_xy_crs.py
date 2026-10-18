"""Capture official CRS evidence without modifying source crash records."""
import json, requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

OUT=(Path(__file__).resolve().parents[2] / 'Unified_MMUCC6')/'qa/coordinate_revision_2026-10-14'
OUT.mkdir(parents=True,exist_ok=True)
URLS={
 'mt_service':'https://gis.mtmdt.us/server/rest/services/MDTGIS/Public_Crash_Information/MapServer',
 'mt_layer':'https://gis.mtmdt.us/server/rest/services/MDTGIS/Public_Crash_Information/MapServer/0',
 'nv_service':'https://gis.dot.nv.gov/arcgis/rest/services/ArcGISOnline/CrashData_OpenData/FeatureServer',
 'nv_layer':'https://gis.dot.nv.gov/arcgis/rest/services/ArcGISOnline/CrashData_OpenData/FeatureServer/0',
 'mt_app':'https://www.arcgis.com/sharing/rest/content/items/237b766a07074259ad7a6eec66d699b7/data',
}
def capture(kv):
 name,url=kv
 try:
  r=requests.get(url,params={'f':'json'},timeout=45);r.raise_for_status();d=r.json()
  if 'error' in d:raise ValueError(d['error'])
  (OUT/(name+'.json')).write_text(json.dumps({'url':url,'response':d},indent=2),encoding='utf-8')
  print(name,json.dumps({'sr':d.get('spatialReference',d.get('extent',{}).get('spatialReference')),'fields':[(f['name'],f.get('alias')) for f in d.get('fields',[])],'map':d.get('map'),'operationalLayers':d.get('operationalLayers')},ensure_ascii=False),flush=True)
 except Exception as e:print(name,'ERROR',str(e),flush=True)
with ThreadPoolExecutor(max_workers=5) as ex:list(ex.map(capture,URLS.items()))
