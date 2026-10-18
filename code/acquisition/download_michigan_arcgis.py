import requests,csv,json,time,os
from pathlib import Path
ROOT=Path(r'F:\LH_Research\USCrash\Crash\States\MI')
BASE='https://gisago-qa.mcgi.state.mi.us/arcgis/rest/services/MSP/CrashDashboard/MapServer'
s=requests.Session()
def get(url,params):
 for attempt in range(5):
  try:
   j=s.get(url,params=dict(f='json',**params),timeout=120).json()
   if 'error' in j: raise RuntimeError(j['error'])
   return j
  except Exception:
   if attempt==4:raise
   time.sleep(5*(attempt+1))
for year in range(2019,2009,-1):
 url=BASE+'/'+str(year-2009)
 d=ROOT/str(year);d.mkdir(parents=True,exist_ok=True)
 final=d/f'MI_crashes_{year}_arcgis.csv'
 if final.exists():continue
 meta=get(url,{})
 (d/'arcgis_metadata.json').write_text(json.dumps(meta),encoding='utf8')
 ids=sorted(get(url+'/query',{'where':'1=1','returnIdsOnly':'true'})['objectIds'])
 print(year,'expected',len(ids),flush=True)
 fields=[f['name'] for f in meta['fields'] if f['type']!='esriFieldTypeGeometry']+['longitude','latitude']
 part=final.with_suffix('.csv.partial');seen=set()
 with part.open('w',newline='',encoding='utf-8-sig') as h:
  w=csv.DictWriter(h,fieldnames=fields);w.writeheader()
  for start in range(0,len(ids),100):
   batch=ids[start:start+100]
   j=get(url+'/query',{'objectIds':','.join(map(str,batch)),'outFields':'*','returnGeometry':'true','outSR':4326})
   rows=j.get('features',[])
   if len(rows)!=len(batch):raise RuntimeError('Incomplete batch')
   for f in rows:
    a=f['attributes'];oid=a['CRSH_ID']
    if oid in seen:raise RuntimeError('Duplicate ID')
    seen.add(oid);g=f.get('geometry') or {};a.update(longitude=g.get('x'),latitude=g.get('y'));w.writerow(a)
   h.flush();print(year,len(seen),'/',len(ids),flush=True);time.sleep(.25)
 if len(seen)!=len(ids):raise RuntimeError('Count mismatch')
 os.replace(part,final)
 print(year,'COMPLETE',flush=True)
print('ALL AVAILABLE ANNUAL LAYERS COMPLETE; 2020-2025 remain pending',flush=True)
