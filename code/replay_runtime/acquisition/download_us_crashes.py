"""Archive identified public official crash sources by jurisdiction/year.

Readonly API queries only. No accounts, emails, or research-repository code execution.
CSV bytes from direct downloads are gzip-compressed without changing contents.
ArcGIS exports retain every published attribute and add WGS84 geometry columns.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlparse
import requests, json, csv, gzip, io, re, hashlib, time, shutil, threading, sys, traceback

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
META = ROOT / 'docs/source_metadata'
MANIFEST = ROOT / 'manifests/acquisition'
for p in [META, MANIFEST]: p.mkdir(parents=True, exist_ok=True)
csv.field_size_limit(100 * 1024 * 1024)
LOCK = threading.RLock()
CLIENT_DATE = '2026-10-08'
CURRENT_YEAR = 2026
SOURCES = []
JOBS = []
EVENTS = MANIFEST / 'events.jsonl'

def stamp(): return datetime.now(timezone.utc).isoformat()
def safe(name): return re.sub(r'[^A-Za-z0-9._-]+', '_', str(name)).strip('_')
def relative(path): return str(path.relative_to(ROOT)).replace('\\', '/')
def check_disk():
    if shutil.disk_usage(ROOT).free < 2 * 1024**3:
        raise RuntimeError('Disk free space below 2 GiB reserve; download paused before further writes')
def atomic_json(path, data):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    tmp.replace(path)
def event(kind, **kwargs):
    payload = {'utc': stamp(), 'event': kind, **kwargs}
    with LOCK:
        with EVENTS.open('a', encoding='utf-8') as f: f.write(json.dumps(payload, ensure_ascii=False, default=str) + '\n')
    if kind in ['source_discovered', 'done', 'failed', 'source_failed', 'blocked']:
        print(json.dumps(payload, ensure_ascii=True, default=str), flush=True)
def request(url, params=None, method='get', stream=False):
    last = None
    for attempt in range(4):
        try:
            kwargs = {'timeout': (30, 150), 'stream': stream, 'headers': {'User-Agent':'OfficialCrashResearchArchive/1.0', 'Accept-Encoding':'identity' if stream else 'gzip,deflate'}}
            if method == 'post': response = requests.post(url, data=params, **kwargs)
            else: response = requests.get(url, params=params, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last = exc
            if getattr(exc.response, 'status_code', None) in [401,403,404]: break
            time.sleep(min(2 ** attempt, 8))
    raise last
def api(url, params=None, post=False):
    response = request(url, params, method='post' if post else 'get')
    data = response.json()
    if isinstance(data, dict) and data.get('error'): raise RuntimeError(json.dumps(data['error']))
    return data
def write_meta(region, name, data):
    folder = META / region
    folder.mkdir(parents=True, exist_ok=True)
    atomic_json(folder / (safe(name) + '.json'), data)
def register_source(source):
    with LOCK: SOURCES.append(source)
    event('source_discovered', region=source['region'], source=source['name'], years=source.get('years'), jobs=source.get('jobs'))
def add_job(job):
    job['id'] = safe(job['region'] + '_' + str(job.get('year','source')) + '_' + job['name'])
    job['status'] = 'pending'
    with LOCK: JOBS.append(job)
def output_path(job):
    path = ROOT / job['region'] / str(job.get('year','_source')) / job['filename']
    if not path.resolve().is_relative_to(ROOT.resolve()): raise RuntimeError('Output escapes US folder')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
def hash_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4*1024*1024), b''): h.update(block)
    return h.hexdigest()

def direct_job(region, year, name, url, filename=None, notes='', split_excel=False):
    filename = filename or safe(Path(urlparse(url).path).name)
    compress = filename.lower().endswith('.csv')
    if compress: filename += '.gz'
    add_job({'kind':'direct','region':region,'year':year,'name':name,'url':url,'filename':filename,
             'compress_csv':compress,'notes':notes,'split_excel':split_excel})

def discover_ca():
    package = api('https://publish.data.ca.gov/api/3/action/package_show', {'id':'ccrs'})['result']
    write_meta('CA','CCRS_catalog',package)
    years = set(); count=0
    for resource in package['resources']:
        match = re.fullmatch(r'(Crashes|Parties|InjuredWitnessPassengers)_(\d{4})',resource.get('name',''))
        if match:
            year=int(match[2]); years.add(year);count+=1
            direct_job('CA',year,resource['name'],resource['url'],filename=resource['name']+'.csv',
                       notes='Official yearly raw file. Injury severity requires person-table linkage. Current year provisional.')
        elif resource['name']=='Raw Data Template':
            direct_job('CA','_source','CCRS_raw_data_template',resource['url'],filename='CCRS_raw_data_template.docx')
    register_source({'region':'CA','name':'CHP_CCRS','years':sorted(years),'jobs':count,
                     'scope':'statewide','four_fields':'yes via joined person table','url':'https://data.ca.gov/dataset/ccrs'})

def source_fields(meta): return [f['name'] for f in meta.get('fields',[]) if f.get('type')!='esriFieldTypeGeometry']
def arc_years(url, meta, date_field=None, year_field=None):
    stats=[{'statisticType':'count','onStatisticField':meta.get('objectIdField',meta.get('objectIdFieldName','OBJECTID')),'outStatisticFieldName':'n'}]
    if year_field:
        data=api(url+'/query',{'where':'1=1','groupByFieldsForStatistics':year_field,'outStatistics':json.dumps(stats),'f':'json','returnGeometry':'false'},post=True)
        years=[]
        for feature in data.get('features',[]):
            value=feature['attributes'].get(year_field)
            try: year=int(value)
            except (ValueError,TypeError):continue
            if 1900<=year<=2099:years.append(year)
        if not years: raise RuntimeError('No years returned by public grouped query')
        return sorted(set(years))
    data=api(url+'/query',{'where':f'{date_field} IS NOT NULL','outStatistics':json.dumps([
        {'statisticType':'min','onStatisticField':date_field,'outStatisticFieldName':'min_date'},
        {'statisticType':'max','onStatisticField':date_field,'outStatisticFieldName':'max_date'}]),'f':'json'},post=True)
    attr={key.lower():value for key,value in data['features'][0]['attributes'].items()}
    def year_of(value):
        if isinstance(value,(int,float)):return (datetime(1970,1,1,tzinfo=timezone.utc)+timedelta(milliseconds=value)).year
        return int(str(value)[:4])
    low,high=year_of(attr['min_date']),year_of(attr['max_date'])
    low,high=max(1900,low),min(2099,high)
    if high<low:raise RuntimeError(f'Invalid date range {attr}')
    return list(range(low,high+1))
def arc_discover(region,name,url,date_field=None,year_field=None,fixed_year=None,notes='',four_fields='yes',include_null=False):
    meta=api(url,{'f':'json'})
    if not meta.get('fields'):raise RuntimeError('No public attributes at '+url)
    write_meta(region,name+'_layer',meta)
    fields=source_fields(meta)
    oid=meta.get('objectIdField',meta.get('objectIdFieldName'))
    if not oid: oid=next(f['name'] for f in meta['fields'] if f['type']=='esriFieldTypeOID')
    if fixed_year is not None:years=[fixed_year]
    else:years=arc_years(url,meta,date_field,year_field)
    base={'kind':'arcgis','region':region,'url':url,'fields':fields,'oid':oid,'meta':meta,'notes':notes}
    for year in years:
        if fixed_year is not None:where='1=1'
        elif year_field:
            definition=next(f for f in meta['fields'] if f['name']==year_field)
            value=f"'{year}'" if definition['type']=='esriFieldTypeString' else str(year)
            where=f'{year_field}={value}'
        else:where=f"{date_field} >= timestamp '{year}-01-01 00:00:00' AND {date_field} < timestamp '{year+1}-01-01 00:00:00'"
        add_job({**base,'year':year,'name':name,'filename':safe(name)+'.csv.gz','where':where})
    if include_null and (date_field or year_field):
        field=year_field or date_field
        add_job({**base,'year':'_undated','name':name+'_undated','filename':safe(name)+'_undated.csv.gz','where':f'{field} IS NULL'})
    register_source({'region':region,'name':name,'url':url,'years':years,'jobs':len(years),'scope':'published coverage only','four_fields':four_fields,'notes':notes})

def discover_il():
    root='https://services2.arcgis.com/aIrBD8yn1TDTEXoz/arcgis/rest/services'
    catalog=api(root,{'f':'json'});write_meta('IL','IDOT_service_catalog',catalog)
    selected={}
    for service in catalog.get('services',[]):
        if service['type']!='FeatureServer':continue
        match=re.match(r'^Crashes_*(\d{4})(?:_|$)',service['name'],re.I)
        if match:selected.setdefault(int(match[1]),service)
    if not selected:raise RuntimeError('No annual IDOT services found')
    for year,service in sorted(selected.items()):
        url=service.get('url') or root+'/'+service['name']+'/FeatureServer'
        arc_discover('IL','IDOT_Crashes_'+str(year),url+'/0',fixed_year=year,
                     notes='Statewide reportable crash records; native annual publication. Invalid coordinates retained.')

def discover_ma():
    url='https://gis.crashdata.dot.mass.gov/arcgis/rest/services/MassDOT/MASSDOT_QV_CRASH/MapServer/0'
    arc_discover('MA','MassDOT_historical_crashes',url,date_field='CRASH_DATE',
                 notes='Multiyear public query layer; WGS84 point geometry appended; overlaps annual detailed layers.',include_null=True)
    catalog=api('https://gis.crashdata.dot.mass.gov/arcgis/rest/services/MassDOT',{'f':'json'})
    write_meta('MA','MassDOT_service_catalog',catalog)
    for service in catalog.get('services',[]):
        match=re.search(r'MASSDOT_ODP_OPEN_(\d{4})(.*)',service['name'])
        if match and service['type']=='FeatureServer':
            year=int(match[1]);url='https://gis.crashdata.dot.mass.gov/arcgis/rest/services/'+service['name']+'/FeatureServer'
            root=api(url,{'f':'json'});write_meta('MA',service['name'].split('/')[-1]+'_service',root)
            # Preserve crash, vehicle, and person tables where present, with annual attribution.
            for layer in root.get('layers',[])+root.get('tables',[]):
                arc_discover('MA','MassDOT_'+str(year)+'_'+safe(layer['name']),url+'/'+str(layer['id']),fixed_year=year,
                             notes='Annual published table; do not concatenate person/vehicle rows as crash counts. Overlaps historical layer.',four_fields='companion if not crash layer')

def discover_or():
    arc_discover('OR','ODOT_OTSDE_crashes','https://gis.odot.state.or.us/arcgis1006/rest/services/agol/OTSDE_Crash/MapServer/0',
                 year_field='CRASH_YR_NO',notes='Time is hourly interval. UNLOCT_FLG and coordinate validity need analysis filtering.',four_fields='hour-level time')
    from bs4 import BeautifulSoup
    url='https://www.oregon.gov/odot/Data/Pages/GIS%20Data.aspx'
    soup=BeautifulSoup(request(url).text,'html.parser')
    archives=[]
    for a in soup.find_all('a'):
        match=re.fullmatch(r'Crashes\s+(\d{4})',a.get_text(' ',strip=True))
        if match and a.get('href'):
            year=int(match[1]);href=urljoin(url,a['href']);archives.append({'year':year,'url':href})
            direct_job('OR',year,'ODOT_geodatabase_'+str(year),href,filename='crashes'+str(year)+'.gdb.zip',
                       notes='Original geodatabase archive with related tables; overlapping OTSDE years are alternative representations, not extra crashes.')
    write_meta('OR','GIS_archives',archives)

def discover_va():
    urls=[('VDOT_Full_Crash','https://services.arcgis.com/p5v98VHDX9Atv3l7/ArcGIS/rest/services/Full_Crash/FeatureServer/0'),
          ('VDOT_legacy_CrashData','https://services.arcgis.com/p5v98VHDX9Atv3l7/ArcGIS/rest/services/CrashData/FeatureServer/0')]
    for name,url in urls:
        arc_discover('VA',name,url,year_field='CRASH_YEAR',notes='Versioned public snapshot; modern and legacy sources have different schemas.',include_null=True)
def discover_ia():
    arc_discover('IA','Iowa_DOT_crashes','https://gis.iowadot.gov/agshost/rest/services/Traffic_Safety/Crash_Data/MapServer/0',
                 date_field='CRASH_DATETIME',notes='WGS84 point geometry appended; official projected X/Y retained.',include_null=True)
def discover_mt():
    from bs4 import BeautifulSoup
    url='https://www.mdt.mt.gov/publications/datastats/crashdata.aspx'
    soup=BeautifulSoup(request(url).text,'html.parser')
    archives=[]
    for a in soup.find_all('a'):
        text=a.get_text(' ',strip=True);href=a.get('href','')
        if re.search(r'Montana Statewide Crash (?:Vehicle |Person )?Data',text) and '.xlsx' in href.lower():
            full=urljoin(url,href);name=safe(text)
            direct_job('MT','_source',name,full,filename=safe(Path(urlparse(full).path).name),split_excel=True,
                       notes='Original multiyear Excel preserved; year CSVs split after all crash-ID/year links are built. Coordinates are State Plane meters.')
            archives.append({'title':text,'url':full})
    if not archives:raise RuntimeError('No official Montana Excel links found')
    write_meta('MT','MDT_archives',archives)
    register_source({'region':'MT','name':'MDT_multiyear_Excel','years':list(range(2016,2026)),'jobs':len(archives),
                     'url':url,'four_fields':'via projected-coordinate conversion','notes':'One-time snapshot; provider warns crash locations not reviewed.'})

def soc_discover(region,name,domain,dataset,date_field,notes='',four_fields='yes'):
    meta=api('https://'+domain+'/api/views/'+dataset+'.json')
    write_meta(region,name+'_dataset',meta)
    url='https://'+domain+'/resource/'+dataset+'.json'
    columns={x['fieldName']:x for x in meta['columns']}
    native_year=next((x for x in ['year','accident_year','crash_year'] if x in columns and columns[x].get('dataTypeName')=='number'),None)
    expr=native_year or f'date_extract_y({date_field})'
    query={'$select':f'{expr} as __download_year,count(*) as n','$group':expr,'$order':'__download_year','$limit':50000}
    grouped=api(url,query)
    fields=[f['fieldName'] for f in meta['columns'] if not f['fieldName'].startswith(':@')]
    base={'kind':'socrata','region':region,'name':name,'url':url,'dataset':dataset,'domain':domain,
          'date_field':date_field,'fields':fields,'notes':notes}
    years=[]
    for row in grouped:
        value=row.get('__download_year');count=int(row['n'])
        if value is None:year='_undated';where=f'{native_year or date_field} IS NULL'
        else:
            year=int(value)
            if not 1900<=year<=2099:
                event('source_failed',region=region,source=name,error='Out-of-range year requires separate handling: '+str(year));continue
            years.append(year)
            where=f'{native_year}={year}' if native_year else f"{date_field} >= '{year}-01-01T00:00:00' AND {date_field} < '{year+1}-01-01T00:00:00'"
        add_job({**base,'year':year,'filename':safe(name)+'.csv.gz','where':where,'expected_rows_discovery':count})
    register_source({'region':region,'name':name,'url':'https://'+domain+'/d/'+dataset,'years':sorted(years),'jobs':len(grouped),
                     'scope':'published portal coverage','four_fields':four_fields,'notes':notes})

SOC_SOURCES=[
('DE','Delaware_Public_Crash_Data','data.delaware.gov','827n-m6xc','crash_datetime','Coarse classification; Non-Reportable mixes private-property outcomes. PDO threshold changed in 2021.','coarse severity'),
('Chicago','CPD_crashes','data.cityofchicago.org','85ca-t3if','crash_date','Some districts only before Sep 2017; non-CPD highways generally excluded.','yes'),
('Chicago','CPD_people','data.cityofchicago.org','u6pd-qa9d','crash_date','Companion person records; link crash_record_id before counting accidents.','companion'),
('Chicago','CPD_vehicles','data.cityofchicago.org','68nd-jvt3','crash_date','Companion vehicle/unit records; link crash_record_id.','companion'),
('Austin','Austin_crashes','data.austintexas.gov','y2wy-tgr5','crash_timestamp_ct','Rolling 10-year retention; current full-purpose boundary.','yes'),
('Cincinnati','CPD_traffic_crash_reports','data.cincinnati-oh.gov','rvmt-pkmq','crashdate','Coordinates intentionally perturbed within block; audit row grain; current system migration may pause updates.','yes with perturbed coordinates'),
('SanFrancisco','DataSF_injury_crashes','data.sf.gov','ubvf-ztfx','collision_datetime','Injury/fatal crashes only; highways excluded.','yes injury-only'),
('BatonRouge','BR_crash_incidents_current','data.brla.gov','7wah-qncc','crash_date','New schema starts Sep 2022. Severity only derivable as fatal/injury/no injury.','coarse severity'),
('NewYorkCity','NYPD_collisions_crashes','data.cityofnewyork.us','h9gi-nx95','crash_date','Supplementary archive: published main table lacks standard collision-manner field.','type missing'),
('Denver','Denver_traffic_accidents','data.colorado.gov','cpwf-cznk','first_occu','Supplementary archive: coarse injury fields, full injury-grade mapping not verified; rolling five years plus current.','not fully verified'),
]

def discover_cities_arc():
    configs=[
    ('Seattle','SDOT_collisions','https://services.arcgis.com/ZOyb2t4B0UYuYNYH/arcgis/rest/services/SDOT_Collisions_All_Years_1/FeatureServer/0','INCDATE',None,'General intersection/segment location; time is INCDTTM.','yes'),
    ('SanJose','SJ_crash_locations','https://geo.sanjoseca.gov/server/rest/services/OPN/OPN_OpenDataService/MapServer/512','CRASHDATETIME',None,'Some older severity values null; preserve original and UTC date fields.','yes'),
    ('Tempe','Tempe_crash_report','https://services.arcgis.com/lQySeXwbBg53XWDi/arcgis/rest/services/CrashDataReportforGISstory/FeatureServer/0','DateTime','Year','Arizona time; export timestamp conventions must be interpreted from metadata.','yes'),
    ('WashingtonDC','DDOT_crash_points','https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Public_Safety_WebMercator/MapServer/24','REPORTDATE',None,'Supplementary archive grouped by REPORTDATE, not proven crash occurrence time; standard collision type missing in this layer.','not fully verified'),
    ]
    for region,name,url,date,year,notes,grade in configs:
        try:arc_discover(region,name,url,date_field=date,year_field=year,notes=notes,four_fields=grade,include_null=True)
        except Exception as exc:event('source_failed',region=region,source=name,error=str(exc))
def discover_oh():
    url='https://tims.dot.state.oh.us/ags/rest/services/Safety'
    catalog=api(url,{'f':'json'});write_meta('OH','ODOT_safety_catalog',catalog)
    for source in catalog.get('services',[]):
        match=re.search(r'/(\d{4})_Crash_Locations$',source['name'])
        if match:
            arc_discover('OH','ODOT_crash_locations_'+match[1],
                         'https://tims.dot.state.oh.us/ags/rest/services/'+source['name']+'/MapServer/0',fixed_year=int(match[1]),
                         notes='Supplementary: year/month/weekday/hour are published, full calendar date missing.',four_fields='full date missing')

def discovery():
    functions=[discover_ca,discover_il,discover_ma,discover_or,discover_va,discover_ia,discover_mt,discover_cities_arc,discover_oh]
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures={pool.submit(fn):fn.__name__ for fn in functions}
        for future in as_completed(futures):
            try:future.result()
            except Exception as exc:event('source_failed',source=futures[future],error=str(exc))
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(soc_discover,*config):config[1] for config in SOC_SOURCES}
        for future in as_completed(futures):
            try:future.result()
            except Exception as exc:event('source_failed',source=futures[future],error=str(exc))
    # Discover historic Baton Rouge tables and the Austin person companion from the public catalog.
    for domain,term,region in [('data.brla.gov','legacy traffic','BatonRouge'),('data.austintexas.gov','crash person','Austin')]:
        try:
            cat=api('https://api.us.socrata.com/api/catalog/v1',{'domains':domain,'search_context':domain,'q':term,'limit':50})
            write_meta(region,'additional_public_catalog',cat)
            for hit in cat.get('results',[]):
                resource=hit.get('resource',{});name=resource.get('name','');dataset=resource.get('id','')
                if not dataset:continue
                if region=='BatonRouge' and not ('legacy' in name.lower() and 'traffic' in name.lower()):continue
                if region=='Austin' and not ('person level' in name.lower() and 'crash' in name.lower()):continue
                meta=api('https://'+domain+'/api/views/'+dataset+'.json')
                cols={x['fieldName']:x for x in meta.get('columns',[])}
                date=next((x for x in ['crash_timestamp_ct','crash_date','incident_date','date_time','crash_timestamp'] if x in cols),None)
                if date:soc_discover(region,safe(name),domain,dataset,date,notes='Additional historical/companion table; not an independent crash sample.',four_fields='requires mapping/linkage')
                else:write_meta(region,'unplanned_'+dataset,meta);event('source_failed',region=region,source=name,error='Date field not mapped automatically; inspect metadata')
        except Exception as exc:event('source_failed',region=region,source='additional_catalog',error=str(exc))
    event('blocked',region='TX',source='CRIS_public_extract',reason='Bulk public extract requires self-registration/request; no credentials used')
    event('blocked',region='NV',source='NDOT_old_public_service',reason='Previously verified error 500: service not started')
    event('blocked',region='MD',source='old_statewide_download',reason='Previously verified public endpoint redirects/login or returns 403; current download not recovered')
    atomic_json(MANIFEST/'sources.json',SOURCES)
    atomic_json(MANIFEST/'download_plan.json',JOBS)

def verify_csv(path):
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
        reader=csv.reader(f);header=next(reader);count=0;bad=0
        for row in reader:
            if not row:continue
            count+=1
            if len(row)!=len(header):bad+=1
    return count,len(header),bad

def native_download(job,path):
    temp=path.with_name(path.name+'.part')
    raw_hash=hashlib.sha256();downloaded=0
    with request(job['url'],stream=True) as response:
        expected=response.headers.get('Content-Length')
        content_type=response.headers.get('Content-Type','')
        if 'text/html' in content_type.lower():raise RuntimeError('Server returned HTML instead of data file')
        with temp.open('wb') as raw:
            if job.get('compress_csv'): target=gzip.GzipFile(filename='',mode='wb',fileobj=raw,compresslevel=3,mtime=0)
            else:target=raw
            try:
                last=time.time()
                for block in response.iter_content(1024*1024):
                    if not block:continue
                    check_disk();target.write(block);raw_hash.update(block);downloaded+=len(block)
                    if time.time()-last>30:
                        event('progress',id=job['id'],downloaded_bytes=downloaded);last=time.time()
            finally:
                if target is not raw:target.close()
    if expected and downloaded!=int(expected):raise RuntimeError(f'Content-Length mismatch {downloaded} != {expected}')
    details={'downloaded_raw_bytes':downloaded,'raw_sha256':raw_hash.hexdigest(),'content_type':content_type}
    if job.get('compress_csv'):
        count,columns,bad=verify_csv(temp);details.update(records=count,columns=columns,nonstandard_width_rows=bad)
    elif path.suffix=='.zip':
        import zipfile
        with zipfile.ZipFile(temp) as z:
            bad=z.testzip()
            if bad:raise RuntimeError('Bad zip member '+bad)
            details['archive_members']=len(z.infolist())
    elif path.suffix=='.xlsx':
        import zipfile
        with zipfile.ZipFile(temp) as z:
            bad=z.testzip()
            if bad:raise RuntimeError('Bad xlsx member '+bad)
    temp.replace(path)
    return details

def cell(value):
    if value is None:return ''
    if isinstance(value,(dict,list)):return json.dumps(value,ensure_ascii=False,separators=(',',':'))
    return value

def arc_download(job,path):
    url=job['url']+'/query'
    ids=api(url,{'where':job['where'],'returnIdsOnly':'true','f':'json'},post=True)
    object_ids=sorted(set(ids.get('objectIds') or []))
    if not object_ids:return {'records':0,'empty':True,'expected_records_snapshot':0}
    id_path=META/job['region']/(safe(job['name'])+'_'+str(job['year'])+'_object_ids.json.gz')
    with gzip.open(id_path,'wt',encoding='utf-8') as f:json.dump({'snapshot_utc':stamp(),'where':job['where'],'objectIdFieldName':ids.get('objectIdFieldName'),'ids':object_ids},f)
    fields=job['fields'];fieldnames=fields+['__geometry_longitude_wgs84','__geometry_latitude_wgs84','__geometry_json_wgs84']
    oid=job['oid'];seen=set();count=0;null_geometry=0
    limit=job['meta'].get('standardMaxRecordCount') or job['meta'].get('maxRecordCount') or 2000
    chunk_size=min(10000,max(500,int(limit)))
    # IDs freeze membership even if the current-year live table changes during pagination.
    def obtain(part):
        params={'objectIds':','.join(map(str,part)),'outFields':'*','returnGeometry':'true','outSR':4326,
                'resultType':'standard','resultRecordCount':len(part),'f':'json'}
        try:data=api(url,params,post=True)
        except Exception:
            if len(part)>500:
                half=len(part)//2;return obtain(part[:half])+obtain(part[half:])
            raise
        features=data.get('features',[])
        if data.get('exceededTransferLimit') and len(part)>1:
            half=len(part)//2;return obtain(part[:half])+obtain(part[half:])
        return features
    temp=path.with_name(path.name+'.part')
    with gzip.open(temp,'wt',encoding='utf-8',newline='',compresslevel=3) as f:
        writer=csv.DictWriter(f,fieldnames=fieldnames);writer.writeheader()
        for offset in range(0,len(object_ids),chunk_size):
            check_disk()
            features=obtain(object_ids[offset:offset+chunk_size])
            for feature in features:
                attr=feature.get('attributes',{});key=attr.get(oid)
                if key in seen:continue
                seen.add(key);row={x:cell(attr.get(x)) for x in fields};geo=feature.get('geometry')
                if geo:
                    row.update(__geometry_longitude_wgs84=geo.get('x',''),__geometry_latitude_wgs84=geo.get('y',''),
                               __geometry_json_wgs84=json.dumps(geo,ensure_ascii=False,separators=(',',':')))
                else:null_geometry+=1
                writer.writerow(row);count+=1
            event('progress',id=job['id'],records=count,expected=len(object_ids))
    missing=set(object_ids)-seen
    if missing:raise RuntimeError(f'{len(missing)} snapshot object IDs not returned; keep partial file for diagnosis')
    verified,columns,bad=verify_csv(temp)
    if verified!=len(object_ids) or bad:raise RuntimeError(f'CSV verification mismatch rows={verified}, expected={len(object_ids)}, bad={bad}')
    temp.replace(path)
    return {'records':count,'columns':columns,'expected_records_snapshot':len(object_ids),'missing_geometry':null_geometry,
            'geometry_crs':'EPSG:4326','date_encoding':'published JSON date values (typically epoch milliseconds); see field schema',
            'id_snapshot_file':relative(id_path)}

def soc_download(job,path):
    url=job['url'];where=job['where']
    expected=int(api(url,{'$select':'count(*) as n','$where':where})[0]['n'])
    if not expected:return {'records':0,'empty':True,'expected_records_snapshot':0}
    fields=job['fields'];temp=path.with_name(path.name+'.part');count=0;offset=0
    with gzip.open(temp,'wt',encoding='utf-8',newline='',compresslevel=3) as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        while True:
            check_disk()
            rows=api(url,{'$select':','.join(fields),'$where':where,'$order':':id','$limit':20000,'$offset':offset})
            if not rows:break
            for row in rows:writer.writerow({key:cell(row.get(key)) for key in fields})
            count+=len(rows);offset+=len(rows)
            event('progress',id=job['id'],records=count,expected=expected)
            if len(rows)<20000:break
    end_count=int(api(url,{'$select':'count(*) as n','$where':where})[0]['n'])
    if count!=expected:
        raise RuntimeError(f'Socrata row count changed or pagination incomplete: start={expected}, got={count}, end={end_count}')
    checked,columns,bad=verify_csv(temp)
    if checked!=count or bad:raise RuntimeError('Socrata CSV verification failed')
    temp.replace(path)
    return {'records':count,'columns':columns,'expected_records_snapshot':expected,'provider_end_count':end_count,
            'provider_membership_changed':end_count!=expected,'date_encoding':'published Socrata text timestamps; see portal time-zone metadata'}

def run_job(job):
    path=output_path(job);receipt=path.with_name(path.name+'.metadata.json')
    if path.exists() and receipt.exists():
        previous=json.loads(receipt.read_text(encoding='utf-8'))
        if previous.get('status')=='complete' and path.stat().st_size==previous.get('stored_bytes'):
            job.update(status='complete',path=relative(path),records=previous.get('records'),stored_bytes=previous.get('stored_bytes'),cached=True)
            event('done',id=job['id'],path=relative(path),cached=True);return job
    job['status']='running';job['started_utc']=stamp();last=None
    for attempt in range(3):
        try:
            if job['kind']=='direct':details=native_download(job,path)
            elif job['kind']=='arcgis':details=arc_download(job,path)
            else:details=soc_download(job,path)
            if details.get('empty'):
                job.update(status='empty',records=0,path=relative(path));return job
            completed={k:v for k,v in job.items() if k!='meta'}
            completed.update(details,status='complete',finished_utc=stamp(),access_date=CLIENT_DATE,
                             path=relative(path),stored_bytes=path.stat().st_size,sha256=hash_file(path),
                             current_year_partial=(job.get('year')==CURRENT_YEAR))
            atomic_json(receipt,completed)
            job.update(status='complete',path=relative(path),records=details.get('records'),stored_bytes=completed['stored_bytes'],sha256=completed['sha256'])
            event('done',id=job['id'],path=relative(path),records=details.get('records'),stored_bytes=completed['stored_bytes']);return job
        except Exception as exc:
            last=exc
            event('retry',id=job['id'],attempt=attempt+1,error=str(exc))
            if 'Disk free' in str(exc) or any(x in str(exc) for x in ['401','403','404']):break
            time.sleep(2*(attempt+1))
    job.update(status='failed',error=str(last),path=relative(path))
    atomic_json(receipt,{k:v for k,v in job.items() if k!='meta'})
    event('failed',id=job['id'],error=str(last));return job

def split_montana():
    import subprocess
    subprocess.run([sys.executable, '-X', 'utf8', str(ROOT/'acquisition'/'split_mt_years.py')], check=True)


def report():
    files=[]
    for receipt in ROOT.glob('*/*/*.metadata.json'):
        try:record=json.loads(receipt.read_text(encoding='utf-8'))
        except Exception:continue
        files.append({k:v for k,v in record.items() if k not in ['meta','fields']})
    atomic_json(MANIFEST/'files.json',files)
    atomic_json(MANIFEST/'job_status.json',[{k:v for k,v in dict(job).items() if k!='meta'} for job in JOBS])
    complete=[x for x in files if x.get('status')=='complete']
    summary={}
    for record in complete:
        region=record['region'];entry=summary.setdefault(region,{'years':set(),'files':0,'bytes':0,'records':0})
        if isinstance(record.get('year'),int):entry['years'].add(record['year'])
        entry['files']+=1;entry['bytes']+=record.get('stored_bytes',0);entry['records']+=record.get('records') or 0
    normalized={key:{**value,'years':sorted(value['years'])} for key,value in summary.items()}
    atomic_json(MANIFEST/'summary.json',normalized)
    with (MANIFEST/'files.csv').open('w',encoding='utf-8-sig',newline='') as f:
        keys=['region','year','name','status','records','stored_bytes','path','url','sha256','notes','error']
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
        for record in files:writer.writerow({key:record.get(key,'') for key in keys})
    readme='# US公开事故数据归档\n\n下载访问日期：'+CLIENT_DATE+'。各文件实际获取UTC时间见旁边metadata.json。\n\n'
    readme+='结构：`US/州缩写或城市名/年份/数据文件`。CSV使用gzip压缩；pandas.read_csv可直接读取.csv.gz。原始年度CSV压缩后内容未改；接口导出保留所有属性，并追加WGS84几何列。日期数值保持API原始格式，常为毫秒时间戳，时区见源字典。\n\n'
    readme+='| 州/城市 | 已下载年份 | 数据文件数 | 存储MB |\n|---|---|---:|---:|\n'
    for region,entry in sorted(normalized.items()):
        years=', '.join(map(str,entry['years']))
        readme+=f"| {region} | {years} | {entry['files']} | {entry['bytes']/1024**2:.1f} |\n"
    readme+='\n2026为当前不完整年份；Chicago 2017年9月前覆盖有限。滚动窗口源只包含目前门户保留的历史，不能声称覆盖已删除年份。`_undated`保存无法归入有效年份的记录。MT原始多年Excel保存在`MT/_source`，年度CSV按Crash ID与Crash Date拆分。\n\n'
    readme+='Massachusetts历史层与年度详细层、Oregon ZIP与OTSDE可能重叠；人员/车辆行也不是独立事故，不要直接把不同文件记录数相加作为事故数。\n\n'
    readme+='补充源NewYorkCity、Denver、WashingtonDC、OH等并非都满足研究四项硬条件，源清单中已标记；下载不等于分析准入。Cincinnati位置有扰动，SF只含伤亡且排除高速，DE类别较粗且有报告门槛变化。\n\n'
    readme+='完成/失败文件见`manifests/acquisition/files.csv`和`job_status.json`；完整字段字典及IDs快照见`docs/source_metadata`。每个完成文件均有SHA256、字节数，CSV另核验行数/列数；ArcGIS按对象ID固定成员并验证全数返回。\n\n'
    failed=[job for job in JOBS if job['status']=='failed']
    readme+='## 当前不能获取/失败\n\n- TX公共bulk需注册/申请；未使用账号。\n- NV旧服务未启动。\n- MD州旧公开入口403/跳转登录，当前下载未恢复。\n'
    for job in failed:readme+='- '+job['id']+'：'+str(job.get('error',''))+'\n'
    (ROOT/'README.md').write_text(readme,encoding='utf-8')
    return {'completed_files':len(complete),'failed_jobs':len(failed),'regions':len(summary),'stored_bytes':sum(x.get('stored_bytes',0) for x in complete)}

def main():
    retry='--retry-failed' in sys.argv
    if retry and (MANIFEST/'download_plan.json').exists():
        JOBS.extend(json.loads((MANIFEST/'download_plan.json').read_text(encoding='utf-8')))
        SOURCES.extend(json.loads((MANIFEST/'sources.json').read_text(encoding='utf-8')))
        for job in JOBS:job['status']='pending'
    else:discovery()
    # Interleave jurisdictions so a single host is not hit by all simultaneous workers.
    groups={}
    for job in JOBS:groups.setdefault(job['region'],[]).append(job)
    queue=[]
    while any(groups.values()):
        for region in groups:
            if groups[region]:queue.append(groups[region].pop(0))
    print('PLAN',len(queue),'download/export jobs',flush=True)
    report()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(run_job,job):job['id'] for job in queue}
        completed=0
        for future in as_completed(futures):
            try:future.result()
            except Exception as exc:event('failed',id=futures[future],error=str(exc))
            completed+=1
            if completed%10==0:print('SUMMARY',json.dumps(report()),flush=True)
    split_montana()
    print('FINAL',json.dumps(report()),flush=True)

if __name__=='__main__':main()
