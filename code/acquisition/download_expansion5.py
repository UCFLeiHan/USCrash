import download_us_crashes as d
from concurrent.futures import ThreadPoolExecutor
import gzip,csv,re,json
try:
 d.arc_discover('TN','TDOSHS_TITAN_2023_snapshot','https://services8.arcgis.com/LXsQ6ODUaTWmnnpV/arcgis/rest/services/TITAN_Dashboard_Crashes__07_18_23_WFL1/FeatureServer/17',date_field='Collision_Date',year_field='Collision_Year',notes='Earlier official dashboard snapshot supplies 2021 and 2022. Injury/fatal-focused subset; do not assume all reportable crashes. 2023 overlaps newer snapshot and is omitted here.',four_fields='candidate; injury-focused coverage and type mapping require review')
 d.JOBS[:]=[j for j in d.JOBS if j['year'] in [2021,2022]];d.SOURCES[-1]['available_years']=d.SOURCES[-1]['years'];d.SOURCES[-1]['years']=[2021,2022]
except Exception as exc:d.event('source_failed',region='TN',source='TITAN_older',error=str(exc))
try:d.arc_discover('NC','NCDOT_KA_crashes','https://services.arcgis.com/NuWFvHYDMVmmxMeM/arcgis/rest/services/NC_FatalAndSeriousInjuryCrashes/FeatureServer/0',fixed_year='_source',notes='Official fatal and serious-injury point layer only; not all crashes. Date strings have a trailing period; preserve originals and split year copies using the published date.',four_fields='yes for K/A subset; clock time, coordinates, severity, type present')
except Exception as exc:d.event('source_failed',region='NC',source='NCDOT_KA',error=str(exc))
d.atomic_json(d.MANIFEST/'expansion5_plan.json',d.JOBS);d.atomic_json(d.MANIFEST/'expansion5_sources.json',d.SOURCES)
with ThreadPoolExecutor(2) as pool:
 for result in pool.map(d.run_job,d.JOBS):d.atomic_json(d.MANIFEST/'expansion5_status.json',[{k:v for k,v in x.items() if k!='meta'} for x in d.JOBS])
p=d.ROOT/'NC'/'_source'/'NCDOT_KA_crashes.csv.gz';handles={};counts={};paths={}
if p.exists():
 try:
  with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:
   reader=csv.DictReader(f);header=reader.fieldnames
   for row in reader:
    m=re.fullmatch(r'\d{2}/\d{2}/(\d{4})\.?',row.get('Date',''));year=int(m[1]) if m else '_undated'
    if year not in handles:
     target=d.ROOT/'NC'/str(year)/'NCDOT_KA_crashes.csv.gz';target.parent.mkdir(parents=True,exist_ok=True);g=gzip.open(target.with_name(target.name+'.part'),'wt',encoding='utf-8',newline='',compresslevel=3);w=csv.DictWriter(g,fieldnames=header);w.writeheader();handles[year]=(g,w);counts[year]=0;paths[year]=target
    handles[year][1].writerow(row);counts[year]+=1
 finally:
  for g,w in handles.values():g.close()
 for year,target in paths.items():
  temp=target.with_name(target.name+'.part');n,columns,bad=d.verify_csv(temp)
  if n!=counts[year] or bad:raise RuntimeError('NC split verification failed')
  temp.replace(target);r={'status':'complete','kind':'year_split_api_export','region':'NC','year':year,'name':'NCDOT_KA_crashes','source_original':d.relative(p),'path':d.relative(target),'records':n,'stored_bytes':target.stat().st_size,'sha256':d.hash_file(target),'access_date':d.CLIENT_DATE,'year_attribution':'Published Date string; trailing punctuation retained; K/A subset only'};d.atomic_json(target.with_name(target.name+'.metadata.json'),r)
 d.SOURCES[-1]['years']=sorted(y for y in counts if isinstance(y,int));d.atomic_json(d.MANIFEST/'expansion5_sources.json',d.SOURCES)
 print('NC K/A year split counts',counts,flush=True)
print('EXPANSION5 COMPLETE',flush=True)
