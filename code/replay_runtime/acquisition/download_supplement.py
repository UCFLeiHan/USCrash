"""Complete sources needing alternate query/date handling; uses main downloader."""
import download_us_crashes as d
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import json,csv,gzip,re

def split_text_date(region,name,original,candidates):
    handles={};counts={};destinations={}
    with gzip.open(original,'rt',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);headers=reader.fieldnames
        field=next((h for h in headers if h.lower() in [x.lower() for x in candidates]),None)
        if not field:raise RuntimeError('No mapped raw date field: '+str(headers))
        try:
            for row in reader:
                match=re.search(r'(?<!\d)(19\d{2}|20\d{2})(?!\d)',row.get(field,'') or '')
                year=int(match[1]) if match else '_undated'
                if year not in handles:
                    dest=d.ROOT/region/str(year)/(name+'.csv.gz');dest.parent.mkdir(parents=True,exist_ok=True)
                    handle=gzip.open(dest.with_name(dest.name+'.part'),'wt',encoding='utf-8',newline='',compresslevel=3)
                    writer=csv.DictWriter(handle,fieldnames=headers);writer.writeheader()
                    handles[year]=(handle,writer);counts[year]=0;destinations[year]=dest
                handles[year][1].writerow(row);counts[year]+=1
        finally:
            for handle,writer in handles.values():handle.close()
    for year,dest in destinations.items():
        temp=dest.with_name(dest.name+'.part');n,c,bad=d.verify_csv(temp)
        if n!=counts[year] or bad:raise RuntimeError('Text-date year split verification failed')
        temp.replace(dest)
        receipt={'status':'complete','kind':'year_split_original_csv','region':region,'year':year,'name':name,'records':n,'columns':c,
                 'path':d.relative(dest),'source_original':d.relative(original),'year_attribution':field+' raw text calendar-year component',
                 'stored_bytes':dest.stat().st_size,'sha256':d.hash_file(dest),'access_date':d.CLIENT_DATE}
        d.atomic_json(dest.with_name(dest.name+'.metadata.json'),receipt)
        d.event('done',id=region+'_'+str(year)+'_'+name,path=d.relative(dest),records=n)

def main():
    for action in [d.discover_ia,
                   lambda:d.arc_discover('WashingtonDC','DDOT_crash_points','https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Public_Safety_WebMercator/MapServer/24',date_field='REPORTDATE',notes='Supplement grouped by report date; occurrence time/type not verified.',four_fields='not fully verified',include_null=True),
                   lambda:d.soc_discover(*d.SOC_SOURCES[0])]:
        try:action()
        except Exception as exc:d.event('source_failed',source='supplement_discovery',error=str(exc))
    d.direct_job('Denver','_source','Denver_original_csv','https://data.colorado.gov/api/views/cpwf-cznk/rows.csv?accessType=DOWNLOAD',filename='Denver_original.csv',notes='Original raw CSV; text dates split locally; supplement, injury-grade mapping incomplete.')
    d.atomic_json(d.MANIFEST/'supplement_plan.json',d.JOBS)
    d.atomic_json(d.MANIFEST/'supplement_sources.json',d.SOURCES)
    with ThreadPoolExecutor(2) as pool:
        tasks=[pool.submit(d.run_job,job) for job in d.JOBS]
        for future in as_completed(tasks):future.result()
    source=d.ROOT/'Denver'/'_source'/'Denver_original.csv.gz'
    if source.exists():split_text_date('Denver','Denver_traffic_accidents',source,['first_occu','FIRST_OCCU'])
    # Main job owns summary while running; final consolidation happens after both finish.
    d.atomic_json(d.MANIFEST/'supplement_status.json',[{k:v for k,v in job.items() if k!='meta'} for job in d.JOBS])
    print('SUPPLEMENT COMPLETE',flush=True)

if __name__=='__main__':main()
