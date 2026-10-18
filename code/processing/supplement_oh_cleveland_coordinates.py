"""City-published ODOT/GCAT points linked to Ohio's retained 2017–2020 crashes."""
import requests,json,time,os
import pandas as pd
from coordinate_supplement_utils import R,U,REV,sha,apply
CITY=os.environ.get('USCRASH_OH_CITY','Cleveland');assert CITY in ['Cleveland','Columbus']
URL=('https://services3.arcgis.com/dty2kHktVXHrqO8i/arcgis/rest/services/Cleveland_Traffic_Crashes_view/FeatureServer/62' if CITY=='Cleveland' else 'https://gis.columbus.gov/arcgis/rest/services/Schemas/PublicService/MapServer/23')
SOURCE=R/f'States/OH/_CoordinateSources_2026-10-16/{CITY}';SOURCE.mkdir(parents=True,exist_ok=True)
OUT=REV/f'OH_{CITY}_v1';OUT.mkdir(parents=True,exist_ok=True)
def get(params):
 for attempt in range(4):
  try:
   r=requests.get(URL+'/query',params=params,timeout=60);r.raise_for_status();d=r.json();assert 'error' not in d;return d
  except Exception:
   if attempt==3:raise
   time.sleep(2**attempt)
if __name__=='__main__':
 meta=requests.get(URL,params={'f':'json'},timeout=40).json();(SOURCE/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
 where='CRASH_YR >= 2017 AND CRASH_YR <= 2020';expected=get({'f':'json','where':where,'returnCountOnly':'true'})['count'];rows=[]
 fields='OBJECTID,DOCUMENT_NBR,CRASH_YR,CRASH_DATE,HOUR_OF_CRASH,ODOT_LATITUDE_NBR,ODOT_LONGITUDE_NBR'
 for offset in range(0,expected,2000):
  p=SOURCE/f'batch_{offset:07d}.json'
  if p.exists():d=json.loads(p.read_text())
  else:
   d=get({'f':'json','where':where,'outFields':fields,'returnGeometry':'true','outSR':4326,'orderByFields':'OBJECTID','resultOffset':offset,'resultRecordCount':2000});p.write_text(json.dumps(d),encoding='utf-8')
  assert len(d.get('features',[]))==min(2000,expected-offset)
  for f in d['features']:
   a=f['attributes'];g=f.get('geometry') or {};a['candidate_lat']=g.get('y');a['candidate_lon']=g.get('x');rows.append(a)
 assert len(rows)==expected
 b=pd.DataFrame(rows);sourcefile=SOURCE/'coordinate_extract.csv';b.to_csv(sourcefile,index=False)
 b['source_crash_id']=b.DOCUMENT_NBR.astype(str).str.replace(r'\.0$','',regex=True)
 b['donor_date']=pd.to_datetime(b.CRASH_DATE,format='mixed',errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
 b=b.loc[~b.source_crash_id.duplicated(keep=False)&b.source_crash_id.ne('')]
 results=[]
 for year in range(2017,2021):
  a=pd.read_csv(U/f'data/crash/OH/OH_crashes_harmonized_{year}.csv',dtype=str,keep_default_na=False,usecols=['crash_uid','source_crash_id','crash_date','crash_time'])
  m=a.merge(b.loc[b.CRASH_YR.eq(year)],on='source_crash_id',validate='one_to_one')
  m['date_agree']=m.crash_date.ne('')&m.crash_date.eq(m.donor_date)
  m['hour_agree']=pd.to_numeric(m.crash_time.str[:2],errors='coerce').eq(pd.to_numeric(m.HOUR_OF_CRASH,errors='coerce'))
  m.to_csv(OUT/f'OH_{year}_linkage.csv',index=False)
  good=m.loc[m.date_agree&m.hour_agree].copy();good['coordinate_source']=f'City of {CITY} official ODOT-derived crash points'
  good['coordinate_source_url']=URL;good['coordinate_source_file']=str(sourcefile);good['coordinate_source_sha256']=sha(sourcefile)
  good['linkage_rule']='Exact unique Ohio DOCUMENT_NBR = retained CrashID; exact calendar date and same reported hour; official GIS point; fill missing only with state-polygon screen.'
  cols=['crash_uid','candidate_lat','candidate_lon','coordinate_source','coordinate_source_url','coordinate_source_file','coordinate_source_sha256','linkage_rule'];results.append(apply('OH',year,good[cols],f'OH_{CITY}_v1'))
 (OUT/'manifest.json').write_text(json.dumps({'source':URL,'source_rows':expected,'results':results,'total_filled':sum(x['filled'] for x in results),'scope':CITY+' only, not statewide historical restoration','official_city_context':('https://www.clevelandohio.gov/transportation-mobility/vision-zero' if CITY=='Cleveland' else 'https://opendata.columbus.gov/'),'script_sha256':sha(__file__)},indent=2),encoding='utf-8');print('OH',CITY,'COMPLETE',sum(x['filled'] for x in results),flush=True)
