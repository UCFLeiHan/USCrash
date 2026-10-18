import os as _uscrash_paths_os
import requests,json,re,csv,time,os
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=(Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/ME')
URL='https://mdotapps.maine.gov/MaineCrashPublic/PublicQueryMap'
s=requests.Session()
def req(method,url,**kw):
 for attempt in range(5):
  try:
   r=s.request(method,url,timeout=180,**kw);r.raise_for_status();return r
  except Exception:
   if attempt==4:raise
   time.sleep(5*(attempt+1))
def points(year):
 d=ROOT/str(year);d.mkdir(parents=True,exist_ok=True)
 cache=d/'map_points.json'
 if cache.exists():return json.loads(cache.read_text())
 b=BeautifulSoup(req('GET',URL).text,'html.parser');form={}
 for x in b.select('input[name]'):
  if x.get('type') in ['radio','checkbox'] and not x.has_attr('checked'):continue
  form[x['name']]=x.get('value','')
 for k in form:
  if 'rddYearFrom' in k or 'rddYearTo' in k:
   form[k]=json.dumps({'value':str(year),'text':str(year),'enabled':True}) if k.endswith('ClientState') else str(year)
 form['__EVENTTARGET']='ctl00$ContentPlaceHolder1$btnStandard';form['__EVENTARGUMENT']=''
 text=req('POST',URL,data=form).text
 (d/'public_query_response.html').write_text(text,encoding='utf8')
 arrays={k:json.loads(re.search(r'var '+k+r' = (\[.*?\]);',text).group(1)) for k in ['info','latitudes','longitudes']}
 if len({len(a) for a in arrays.values()})!=1:raise RuntimeError('Map array length mismatch')
 rows=[{'id':i,'latitude':lat,'longitude':lon} for i,lat,lon in zip(arrays['info'],arrays['latitudes'],arrays['longitudes'])]
 cache.write_text(json.dumps(rows),encoding='utf8');print(year,'map points',len(rows),flush=True);return rows
ROOT.mkdir(parents=True,exist_ok=True)
(ROOT/'README.txt').write_text('Source: '+URL+'\nPublic map records and public popup details. Map-only coverage: not yet reconciled with all statewide crashes, including unmapped crashes. Files marked partial are incomplete.\n',encoding='utf8')
for year in range(2025,2015,-1):
 try:points(year)
 except Exception as e:print(year,'MAP FAILED',repr(e),flush=True)
# Requested historical cutoff is 2016; never recreate 2015 or older data.
for year in range(2025,2015,-1):
 try:
  rows=points(year);d=ROOT/str(year);out=d/f'ME_mapped_crashes_{year}.csv';part=out.with_suffix('.csv.partial')
  if out.exists():continue
  done=set()
  if part.exists():
   with part.open(encoding='utf-8-sig',newline='') as h:done={r['id'] for r in csv.DictReader(h)}
  fields=['id','latitude','longitude','report','Injury Level','Date/Time','Location','Type Of Crash','MDOT ID']
  fresh=not part.exists()
  with part.open('a',encoding='utf-8-sig',newline='') as h:
   w=csv.DictWriter(h,fieldnames=fields,extrasaction='ignore')
   if fresh:w.writeheader()
   failures=[]
   for row in rows:
    if str(row['id']) in done:continue
    try:
     data=req('POST',URL+'.aspx/GetReportDetails',json={'crashReportId':str(row['id']),'accessLevel':'1'}).json()['d']
     b=BeautifulSoup(data[1],'html.parser');vals=b.select('td[style*="padding-left"]');labels=b.select('span[style*="italic"]')
     row.update({k.get_text(' ',strip=True):v.get_text(' ',strip=True) for k,v in zip(labels,vals)})
     if not row.get('Date/Time'):raise RuntimeError('Missing detail fields')
     row['report']=b.get_text(' ',strip=True).split('Injury Level')[0]
     w.writerow(row);h.flush();done.add(str(row['id']))
     if len(done)%100==0:print(year,'details',len(done),'/',len(rows),flush=True)
    except Exception as e:
     failures.append({'id':str(row['id']),'error':repr(e)})
     print(year,'record failed',row['id'],repr(e),flush=True)
    time.sleep(.25)
  if len(done)==len(rows):
   os.replace(part,out);print(year,'MAPPED RECORDS COMPLETE',len(done),flush=True)
  else:
   (d/f'ME_mapped_crashes_{year}_failures.json').write_text(json.dumps(failures),encoding='utf8')
   print(year,'INCOMPLETE',len(done),'/',len(rows),'failed this pass',len(failures),flush=True)
 except Exception as e:print(year,'DETAIL FAILED',repr(e),flush=True)
