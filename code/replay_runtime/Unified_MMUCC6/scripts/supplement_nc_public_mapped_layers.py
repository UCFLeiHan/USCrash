"""Download public NCDOT mapped subsets; link only exact Crash ID/date pairs.
No extra crashes appended. Disagreeing donor coordinates are held for review.
"""
import requests,json,time,concurrent.futures as cf
from pathlib import Path
import pandas as pd,numpy as np
from coordinate_supplement_utils import R,U,REV,sha,apply
BASE='https://services.arcgis.com/NuWFvHYDMVmmxMeM/ArcGIS/rest/services/'
SOURCE=R/'States/NC/_CoordinateSources_2026-10-16';SOURCE.mkdir(exist_ok=True)
OUT=REV/'NC_public_mapped_v1';OUT.mkdir(parents=True,exist_ok=True)
def get(url,p=None):
 for attempt in range(4):
  try:
   r=requests.get(url,params=p,timeout=60);r.raise_for_status();d=r.json()
   if 'error' in d:raise RuntimeError(str(d['error']))
   return d
  except Exception:
   if attempt==3:raise
   time.sleep(2**attempt)
def source(name):
 folder=SOURCE/name;folder.mkdir(exist_ok=True);url=BASE+name+'/FeatureServer/0'
 meta=get(url,{'f':'json'});(folder/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
 fields={f['name']:f for f in meta.get('fields',[])}
 ident=next((x for x in ['Crash_ID','CrashID','CRSH_ID'] if x in fields),None)
 date=next((x for x in ['Date','Date_','CrashDate','Date_First','ACDNT_DT_T'] if x in fields),None)
 if not ident or not date:return {'name':name,'status':'NO_VERIFIED_ID_OR_DATE_FIELD'},pd.DataFrame()
 oid=meta.get('objectIdField') or next(x for x,v in fields.items() if v['type']=='esriFieldTypeOID')
 requested=list(dict.fromkeys([oid,ident,date]+[x for x in ['Latitude','Longitude','LOC_ERROR','MapMethod','Source_ID'] if x in fields]))
 expected=get(url+'/query',{'f':'json','where':'1=1','returnCountOnly':'true'})['count'];rows=[]
 step=min(2000,int(meta.get('maxRecordCount',2000)))
 for offset in range(0,expected,step):
  p=folder/f'batch_{offset:07d}.json'
  if p.exists():d=json.loads(p.read_text(encoding='utf-8'))
  else:
   d=get(url+'/query',{'f':'json','where':'1=1','outFields':','.join(requested),'returnGeometry':'true','outSR':4326,'orderByFields':oid,'resultOffset':offset,'resultRecordCount':step})
   p.write_text(json.dumps(d),encoding='utf-8')
  features=d.get('features',[]);assert len(features)==min(step,expected-offset),(name,offset,len(features))
  for f in features:
   a=f['attributes'];g=f.get('geometry') or {};rows.append({'source_crash_id':str(a.get(ident) or ''),'raw_date':a.get(date),'candidate_lat':g.get('y'),'candidate_lon':g.get('x'),'coordinate_source':name,'coordinate_source_url':url,'location_error':a.get('LOC_ERROR',''),'source_mapping_method':a.get('MapMethod','')})
 assert len(rows)==expected
 b=pd.DataFrame(rows)
 if len(b):
  if fields[date]['type'] in ['esriFieldTypeDate','esriFieldTypeDateOnly'] and pd.to_numeric(b.raw_date,errors='coerce').notna().sum()>len(b)/2:
   b['donor_date']=pd.to_datetime(pd.to_numeric(b.raw_date,errors='coerce'),unit='ms',utc=True,errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
  else:b['donor_date']=pd.to_datetime(b.raw_date.astype(str).str.rstrip('.'),format='mixed',errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
  b.source_crash_id=b.source_crash_id.str.replace(r'\.0$','',regex=True)
  b.to_csv(folder/'coordinate_extract.csv',index=False)
  b['coordinate_source_file']=str(folder/'coordinate_extract.csv');b['coordinate_source_sha256']=sha(folder/'coordinate_extract.csv')
 info={'name':name,'url':url,'source_rows':len(b),'id_field':ident,'date_field':date,'date_type':fields[date]['type'],'requested_fields':requested,'status':'DOWNLOADED','source_scope':'Official published subset; no all-crash completeness assumed'}
 (folder/'download_manifest.json').write_text(json.dumps(info,indent=2),encoding='utf-8');print('NC SOURCE COMPLETE',name,len(b),flush=True);return info,b

if __name__=='__main__':
 catalog=get(BASE,{'f':'json'});names=[]
 for s in catalog['services']:
  n=s['name']
  if s.get('type')!='FeatureServer':continue
  if ((any(n.startswith(x) for x in ['OlderDriverCrashes','AnimalCrashes','AlcoholCrashes','TeenDriverCrashes','MotorcycleCrashes','MotorycleCrashes','WWDCrashes']) and any(str(y) in n for y in range(2021,2026))) or n in ['NCDOT_NonMotoristCrashes','NC_Motorcycle_Crashes_2025','Crash_Points','LaneDepartureCrashes']):names.append(n)
 frames=[];sources=[]
 with cf.ThreadPoolExecutor(max_workers=3) as pool:
  jobs={pool.submit(source,n):n for n in sorted(set(names))}
  for f in cf.as_completed(jobs):
   try:
    info,b=f.result();sources.append(info)
    if len(b):frames.append(b)
   except Exception as e:sources.append({'name':jobs[f],'status':'FAILED_NOT_USED','error':str(e)});print('NC SOURCE FAILED',jobs[f],str(e)[:150],flush=True)
 assert frames
 b=pd.concat(frames,ignore_index=True);b=b.loc[b.donor_date.ne('')&b.source_crash_id.ne('')].copy()
 for c in ['candidate_lat','candidate_lon']:b[c]=pd.to_numeric(b[c],errors='coerce')
 b=b.loc[b.candidate_lat.between(33.7,36.7)&b.candidate_lon.between(-84.5,-75.3)]
 error=b.location_error.fillna('').astype(str).str.upper().str.strip()
 clear=error.isin(['','NO ERROR','0','NONE'])
 b.loc[~clear].to_csv(OUT/'source_location_error_flags_held.csv',index=False)
 b=b.loc[clear].copy()
 b['crash_uid']='NC:'+b.source_crash_id
 # Annual source overlap must agree to rounding-level (1e-6 degrees), not guessed averaging.
 b['rounded_lat']=b.candidate_lat.round(6);b['rounded_lon']=b.candidate_lon.round(6)
 spread=b.groupby('crash_uid')[['rounded_lat','rounded_lon','donor_date']].nunique().max(axis=1)
 conflict=set(spread[spread.gt(1)].index)
 b.loc[b.crash_uid.isin(conflict)].to_csv(OUT/'conflicting_donor_points_held.csv',index=False)
 b=b.loc[~b.crash_uid.isin(conflict)].sort_values(['coordinate_source','crash_uid']).drop_duplicates('crash_uid')
 results=[]
 for year in range(2016,2027):
  canon=U/f'data/crash/NC/NC_crashes_harmonized_{year}.csv'
  if not canon.exists():continue
  a=pd.read_csv(canon,dtype=str,keep_default_na=False,usecols=['crash_uid','crash_date'])
  m=a.merge(b,on='crash_uid',validate='one_to_one');m['date_agree']=m.crash_date.ne('')&m.crash_date.eq(m.donor_date)
  m.to_csv(OUT/f'NC_{year}_linkage.csv',index=False)
  good=m.loc[m.date_agree].copy();good['linkage_rule']='Unique exact statewide Crash ID + exact calendar date; conflicting cross-layer points withheld; official point geometry transformed by service to EPSG:4326; state-polygon screen; missing only.'
  cols=['crash_uid','candidate_lat','candidate_lon','coordinate_source','coordinate_source_url','coordinate_source_file','coordinate_source_sha256','location_error','source_mapping_method','linkage_rule']
  results.append(apply('NC',year,good[cols],'NC_public_mapped_v1'))
 (OUT/'manifest.json').write_text(json.dumps({'sources':sources,'results':results,'total_filled':sum(x['filled'] for x in results),'conflicting_crash_ids_held':len(conflict),'script_sha256':sha(__file__),'no_new_crashes_appended':True},indent=2),encoding='utf-8');print('NC MAPPED COMPLETE',sum(x['filled'] for x in results),flush=True)
