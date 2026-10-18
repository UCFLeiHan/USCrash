"""Archive public Washington CAT summary exports; partition below the public export limit."""
import download_us_crashes as d
import json,csv,io,gzip,hashlib,calendar,requests,threading,time
from datetime import date,datetime,timedelta
from concurrent.futures import ThreadPoolExecutor
BASE=json.loads((d.META/'expansion'/'WA_query_body.json').read_text())
JOBS=[];STATUS=[];LOCK=threading.RLock();SOURCES=[{'region':'WA','name':'WSP_CAT_summary','url':'https://wrecr.wsp.wa.gov/cat','scope':'public statewide CAT portal','four_fields':'datetime, coordinates, injury severity, coarse ObjectStruck; standard collision manner absent; ReportNumber is not guaranteed unique, preserve provider rows','notes':'CSV retains official two-line disclaimer preamble; pandas skiprows=2. Partitioned below 10000-record export cap. Early sparse years are anomalies, not full coverage.'}]
def query_body(start,end):
    body=json.loads(json.dumps(BASE));body['collisionDateFilter'].update(startDate=start.isoformat(),endDate=end.isoformat(),startTime='00:00:00',endTime='23:59:59');return {'fieldFilters':body}
def post(route,body):
    for attempt in range(3):
        try:
            r=requests.post('https://api.wrecr.wsp.wa.gov/api/'+route,json=body,headers={'Origin':'https://wrecr.wsp.wa.gov','Referer':'https://wrecr.wsp.wa.gov/cat'},timeout=(30,120));r.raise_for_status();return r
        except Exception:
            if attempt==2:raise
            time.sleep(2*(attempt+1))
def count(start,end):return post('cat-queries/total',query_body(start,end)).json()['totalCount']
def persist():
    with LOCK:
        d.atomic_json(d.MANIFEST/'expansionWA_plan.json',JOBS);d.atomic_json(d.MANIFEST/'expansionWA_status.json',STATUS);d.atomic_json(d.MANIFEST/'expansionWA_sources.json',SOURCES)
def export_period(period):
    start,end=period;n=count(start,end)
    if not n:return
    if n>10000:
        if start==end:raise RuntimeError('One day exceeds public export limit; requires supported narrower time partition')
        middle=start+timedelta(days=(end-start).days//2);export_period((start,middle));export_period((middle+timedelta(days=1),end));return
    name='WSP_CAT_summary_'+start.isoformat()+'_'+end.isoformat();job={'id':'WA_'+name,'kind':'public_rest_export','region':'WA','year':start.year,'name':name,'filename':name+'.csv.gz','url':'https://api.wrecr.wsp.wa.gov/api/cat-exports/summary','query':query_body(start,end)};dest=d.output_path(job);receipt=dest.with_name(dest.name+'.metadata.json')
    with LOCK:JOBS.append(job)
    if receipt.exists():
        prior=json.loads(receipt.read_text());result={**job,'status':prior.get('status'),'records':prior.get('records')}
        with LOCK:STATUS.append(result)
        persist();return
    payload={'exportSettings':{'fileType':'csv','query':job['query'],'maxScrollSearchSize':10000}};r=post('cat-exports/summary',payload)
    if 'text/csv' not in r.headers.get('content-type',''):raise RuntimeError('CSV export returned unexpected content')
    raw=r.content;reader=csv.reader(io.StringIO(raw.decode('utf-8-sig')));preamble=next(reader);blank=next(reader);header=next(reader);rows=list(reader);bad=sum(len(row)!=len(header) for row in rows)
    if len(rows)!=n:
        if start<end:
            with LOCK:JOBS.remove(job)
            middle=start+timedelta(days=(end-start).days//2)
            export_period((start,middle));export_period((middle+timedelta(days=1),end));return
        raise RuntimeError(f'Export row-count mismatch for single day {start}: {len(rows)} vs {n}')
    date_i=header.index('DateTimeOfIncident');id_i=header.index('ReportNumber');identifiers=set();duplicate_reports=0
    for row in rows:
        actual=datetime.strptime(row[date_i],'%m/%d/%Y %H:%M:%S %z').date()
        if not start<=actual<=end:raise RuntimeError('Date filter was not applied')
        if row[id_i] in identifiers:duplicate_reports+=1
        identifiers.add(row[id_i])
    end_count=count(start,end);d.check_disk();temp=dest.with_name(dest.name+'.part')
    with temp.open('wb') as f:
        with gzip.GzipFile(filename='',mode='wb',fileobj=f,compresslevel=3,mtime=0) as g:g.write(raw)
    temp.replace(dest)
    record={**job,'status':'complete','path':d.relative(dest),'records':len(rows),'expected_records_snapshot':n,'provider_end_count':end_count,'provider_membership_changed':n!=end_count,'columns':len(header),'nonstandard_width_rows':bad,'duplicate_report_number_rows':duplicate_reports,'identical_row_duplicates':len(rows)-len(set(tuple(row) for row in rows)),'csv_preamble_rows':2,'raw_sha256':hashlib.sha256(raw).hexdigest(),'downloaded_raw_bytes':len(raw),'stored_bytes':dest.stat().st_size,'sha256':d.hash_file(dest),'date_encoding':'local timestamp with explicit UTC offset','access_date':d.CLIENT_DATE,'finished_utc':d.stamp(),'current_year_partial':start.year==2026,'notes':SOURCES[0]['notes']}
    d.atomic_json(receipt,record)
    with LOCK:STATUS.append({**job,'status':'complete','records':len(rows)})
    persist();d.event('done',id=job['id'],path=d.relative(dest),records=len(rows),stored_bytes=dest.stat().st_size)
periods=[];year_counts={}
for year in range(2010,2027):
    n=count(date(year,1,1),date(year,12,31));year_counts[year]=n
    if not n:continue
    if n<=10000:periods.append((date(year,1,1),date(year,12,31)))
    else:
        periods.extend((date(year,m,1),date(year,m,calendar.monthrange(year,m)[1])) for m in range(1,13))
SOURCES[0]['years']=[year for year,n in year_counts.items() if n];d.atomic_json(d.META/'expansion'/'WA_year_counts.json',year_counts);persist();print('WA year counts',year_counts,flush=True)
with ThreadPoolExecutor(3) as pool:list(pool.map(export_period,periods))
persist();print('WA ALL AVAILABLE YEARS COMPLETE',len(STATUS),'files',flush=True)
