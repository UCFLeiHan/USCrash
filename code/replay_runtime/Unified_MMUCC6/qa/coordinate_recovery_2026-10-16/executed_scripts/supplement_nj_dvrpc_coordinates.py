"""Use DVRPC's published NJDOT/LRS geocoded points, not invented GPS.
Includes an explicit 2019 portal-ID bridge through year+municipal NCIC+case number.
"""
import requests,json,time
import pandas as pd
from coordinate_supplement_utils import R,U,REV,sha,apply
URL='https://arcgis.dvrpc.org/portal/rest/services/transportation/crash_newjersey/FeatureServer/0'
SOURCE=R/'States/NJ/_CoordinateSources_2026-10-16/DVRPC';SOURCE.mkdir(parents=True,exist_ok=True)
OUT=REV/'NJ_DVRPC_v1';OUT.mkdir(parents=True,exist_ok=True)
def get(params):
 for attempt in range(4):
  try:
   r=requests.get(URL+'/query',params=params,timeout=60);r.raise_for_status();d=r.json();assert 'error' not in d;return d
  except Exception:
   if attempt==3:raise
   time.sleep(2**attempt)
if __name__=='__main__':
 meta=requests.get(URL,params={'f':'json'},timeout=40).json();(SOURCE/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
 where="latitude IS NULL OR latitude = '' OR longitude IS NULL OR longitude = ''"
 spatial={'geometry':'-76,38,-73,42','geometryType':'esriGeometryEnvelope','inSR':4326,'spatialRel':'esriSpatialRelIntersects'}
 expected=get({'f':'json','where':where,'returnCountOnly':'true',**spatial})['count'];rows=[]
 fields='objectid,casenumber,year,ncic_code,dept_case_num,date,time_of_day,sri,milepost,latitude,longitude'
 for offset in range(0,expected,2000):
  p=SOURCE/f'batch_{offset:07d}.json'
  if p.exists():d=json.loads(p.read_text())
  else:
   d=get({'f':'json','where':where,**spatial,'outFields':fields,'returnGeometry':'true','outSR':4326,'orderByFields':'objectid','resultOffset':offset,'resultRecordCount':2000});p.write_text(json.dumps(d),encoding='utf-8')
  assert len(d.get('features',[]))==min(2000,expected-offset)
  for f in d['features']:
   a=f['attributes'];g=f.get('geometry') or {};a['candidate_lat']=g.get('y');a['candidate_lon']=g.get('x');rows.append(a)
  if offset%10000==0:print('NJ DVRPC DOWNLOADED',len(rows),'/',expected,flush=True)
 assert len(rows)==expected
 b=pd.DataFrame(rows);sourcefile=SOURCE/'coordinate_extract.csv';b.to_csv(sourcefile,index=False)
 b['join_key']=b.casenumber.fillna('').astype(str).str.strip()
 b['donor_date']=pd.to_datetime(b.date,format='mixed',errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
 clock=b.time_of_day.fillna('').astype(str).str.replace(r'\D','',regex=True).str.zfill(4)
 hh=pd.to_numeric(clock.str[:2],errors='coerce');mm=pd.to_numeric(clock.str[2:],errors='coerce');ok=clock.str.fullmatch(r'\d{4}')&hh.between(0,23)&mm.between(0,59)
 b['donor_time']=clock.str[:2]+':'+clock.str[2:]+':00';b.loc[~ok,'donor_time']=''
 b=b.loc[b.join_key.ne('')&~b.join_key.duplicated(keep=False)]
 results=[]
 for year in range(2017,2024):
  a=pd.read_csv(U/f'data/crash/NJ/NJ_crashes_harmonized_{year}.csv',dtype=str,keep_default_na=False,usecols=['crash_uid','source_crash_id','crash_date','crash_time'])
  if year==2019:
   bridge=pd.read_csv(R/'States/NJ/2019/NJ_portal_crashes_2019.csv',dtype=str,keep_default_na=False,usecols=['id_cr','municipalitycode','casenumber'])
   bridge['join_key']=str(year)+bridge.municipalitycode.str.zfill(4)+bridge.casenumber.str.strip()
   bridge=bridge.loc[bridge.casenumber.ne('')&~bridge.id_cr.duplicated(keep=False)&~bridge.join_key.duplicated(keep=False)]
   a=a.merge(bridge[['id_cr','join_key']],left_on='source_crash_id',right_on='id_cr',validate='one_to_one')
  else:a['join_key']=a.source_crash_id.str.strip()
  a=a.loc[a.join_key.ne('')&~a.join_key.duplicated(keep=False)]
  m=a.merge(b.loc[b.year.astype(str).eq(str(year))],on='join_key',validate='one_to_one')
  m['date_agree']=m.crash_date.ne('')&m.crash_date.eq(m.donor_date)
  m['minute_agree']=m.crash_time.ne('')&m.crash_time.str[:5].eq(m.donor_time.str[:5])&m.donor_time.ne('')
  m.to_csv(OUT/f'NJ_{year}_linkage.csv',index=False)
  good=m.loc[m.date_agree&m.minute_agree].copy()
  good['coordinate_source']='DVRPC official NJDOT crash/LRS geocoded points'
  good['coordinate_source_url']=URL;good['coordinate_source_file']=str(sourcefile);good['coordinate_source_sha256']=sha(sourcefile)
  good['coordinate_method']='SOURCE_PUBLISHED_LRS_GEOCODE_NOT_OFFICER_GPS'
  good['linkage_rule']='Unique exact composite NJDOT case number + exact date/minute. 2019 bridge: canonical id_cr -> raw municipalitycode/casenumber -> year + NCIC(4) + police case; no fuzzy matching. Missing only, state-polygon screen.'
  cols=['crash_uid','candidate_lat','candidate_lon','coordinate_source','coordinate_source_url','coordinate_source_file','coordinate_source_sha256','coordinate_method','sri','milepost','linkage_rule'];results.append(apply('NJ',year,good[cols],'NJ_DVRPC_v1'))
 (OUT/'manifest.json').write_text(json.dumps({'source':URL,'source_catalog':'https://catalog.dvrpc.org/dataset/new-jersey-crash-data-points','source_rows':expected,'results':results,'total_filled':sum(x['filled'] for x in results),'scope':'DVRPC published regional 2017–2023 subset, not statewide historical restoration','precision':'Published LRS/map-derived coordinates, not original officer GPS. Source SRI and milepost retained in change ledgers.','script_sha256':sha(__file__)},indent=2),encoding='utf-8');print('NJ DVRPC COMPLETE',sum(x['filled'] for x in results),flush=True)
