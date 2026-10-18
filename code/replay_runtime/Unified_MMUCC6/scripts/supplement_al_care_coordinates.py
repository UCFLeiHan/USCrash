"""Recover explicitly published CARE historical coordinate columns omitted by old export.
Unique Record ID, exact date and same reported hour required. No clock imputation.
"""
from pathlib import Path
import requests,json,time,html,calendar,concurrent.futures as cf
import pandas as pd
from coordinate_supplement_utils import R,U,REV,sha,apply
URL='https://safety.aladata.com/DataSource/GetCategoryDetails'
SOURCE=R/'States/AL/_CoordinateSources_2026-10-16';SOURCE.mkdir(exist_ok=True)
OUT=REV/'AL_CARE_v1';OUT.mkdir(parents=True,exist_ok=True)
FIELDS=['Crash Number','Record ID','Year','Month','Day of Month','Time of Day','Latitude','Longitude','Has Coordinate','key.dat']
def download(y):
 folder=SOURCE/str(y);folder.mkdir(exist_ok=True);final=folder/f'AL_CARE_coordinate_linkage_{y}.csv'
 if final.exists() and (folder/'download_manifest.json').exists():return y,final
 rows=[];total=None;page=0;session=requests.Session();queries=[]
 while total is None or len(rows)<total:
  payload={'dataSourceID':'eCrash1420','startDate':f'1/1/{y}','endDate':f'12/31/{y}','selectedCategoriesString':'','variableNames':','.join(FIELDS),'recordsPerPage':10000,'pageIndex':page,'sortVariable':'Crash Number','sortAscending':True,'returnTotalNumberOfRecordsFound':True,'includePdfLink':'False'}
  cache=folder/f'page_{page:04d}.txt'
  if cache.exists():body=cache.read_text(encoding='utf-8')
  else:
   for attempt in range(4):
    try:
     response=session.post(URL,json=payload,timeout=90);response.raise_for_status();body=response.text;assert body.split('|')[0].isdigit();break
    except Exception:
     if attempt==3:raise
     time.sleep(2**attempt)
   cache.write_text(body,encoding='utf-8')
  parts=body.split('|');n=int(parts[0]);columns=[]
  if total is None:total=n
  assert total==n,'Source population changed during download'
  for raw in parts[1:]:
   if raw=='':continue
   values=raw.split(',')
   if values and values[-1]=='':values.pop()
   columns.append([html.unescape(v) for v in values])
  assert len(columns)==len(FIELDS) and len(set(map(len,columns)))==1
  batch=list(zip(*columns));assert batch or total==len(rows)
  rows.extend(batch);queries.append({'page':page,'request':payload,'response_sha256':sha(cache),'received':len(batch)});page+=1
  print('AL DOWNLOADED',y,len(rows),'/',total,flush=True)
 assert len(rows)==total
 b=pd.DataFrame(rows,columns=FIELDS);b.to_csv(final,index=False)
 (folder/'download_manifest.json').write_text(json.dumps({'url':URL,'year':y,'dataSourceID':'eCrash1420','rows':len(b),'fields':FIELDS,'pages':queries,'sha256':sha(final),'coordinate_columns_are_explicit_source_values':True},indent=2),encoding='utf-8')
 return y,final

if __name__=='__main__':
 results=[]
 with cf.ThreadPoolExecutor(max_workers=3) as pool:
  jobs={pool.submit(download,y):y for y in range(2014,2021)}
  for f in cf.as_completed(jobs):
   year,p=f.result();b=pd.read_csv(p,dtype=str,keep_default_na=False)
   b=b.loc[b['Record ID'].ne('')&~b['Record ID'].duplicated(keep=False)].copy()
   b['source_crash_id']=b['Record ID'];months={m:i for i,m in enumerate(calendar.month_name) if m}
   b['donor_date']=pd.to_datetime({'year':pd.to_numeric(b.Year,errors='coerce'),'month':b.Month.map(months),'day':pd.to_numeric(b['Day of Month'],errors='coerce')},errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
   # Source reports a one-hour interval, e.g. 3:00 PM to 3:59 PM.
   start=b['Time of Day'].str.split(' to ').str[0]
   b['donor_hour']=pd.to_datetime(start,format='%I:%M %p',errors='coerce').dt.hour
   a=pd.read_csv(U/f'data/crash/AL/AL_crashes_harmonized_{year}.csv',dtype=str,keep_default_na=False,usecols=['crash_uid','source_crash_id','crash_date','crash_time'])
   assert a.source_crash_id.is_unique
   m=a.merge(b,on='source_crash_id',validate='one_to_one')
   m['date_agree']=m.crash_date.ne('')&m.crash_date.eq(m.donor_date)
   m['hour_agree']=pd.to_numeric(m.crash_time.str[:2],errors='coerce').eq(m.donor_hour)&m.donor_hour.notna()
   m.to_csv(OUT/f'AL_{year}_linkage.csv',index=False)
   good=m.loc[m.date_agree&m.hour_agree].copy()
   good['candidate_lat']=good.Latitude;good['candidate_lon']=good.Longitude
   good['coordinate_source']='Alabama CARE historical public export, explicit Latitude/Longitude'
   good['coordinate_source_file']=str(p);good['coordinate_source_sha256']=sha(p)
   good['coordinate_method_reported']=good['Has Coordinate']
   good['linkage_rule']='Unique exact Record ID GUID + exact reported calendar date + same source-reported hour interval; explicit source coordinates; fill missing only, with 2km state-polygon screen.'
   result=apply('AL',year,good[['crash_uid','candidate_lat','candidate_lon','coordinate_source','coordinate_source_file','coordinate_source_sha256','coordinate_method_reported','linkage_rule']],'AL_CARE_v1');results.append(result)
 (OUT/'manifest.json').write_text(json.dumps({'results':results,'total_filled':sum(x['filled'] for x in results),'source':URL,'cause':'Old historical download did not request published Latitude/Longitude columns; recovered from the same public source.','script_sha256':sha(__file__),'source_geocoding_precision':'Preserve Has Coordinate: officer coordinates and node-derived coordinates remain distinct in change ledger.'},indent=2),encoding='utf-8')
 print('AL CARE COMPLETE',sum(x['filled'] for x in results),flush=True)
