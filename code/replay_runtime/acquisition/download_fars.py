"""Official nationwide fatal-crash annual CSV bundles; separate from all-crash state archives."""
import download_us_crashes as d
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests

for year in range(1975,2025):
    base=f'https://static.nhtsa.gov/nhtsa/downloads/FARS/{year}/National/'
    filename=f'FARS{year}NationalCSV.zip'
    d.direct_job('FARS_Nationwide',year,'FARS_National_CSV_'+str(year),base+filename,filename=filename,
                 notes='Nationwide fatal crashes only. Early years may lack usable coordinates. Original CSV bundle, not an all-severity crash database.')
    # Derived auxiliary labels were not published for every historical year.
    if year>=2010:
        name=f'FARS{year}NationalAuxiliaryCSV.zip'
        response=requests.head(base+name,timeout=30,allow_redirects=True)
        if response.status_code==200:
            d.direct_job('FARS_Nationwide',year,'FARS_Auxiliary_CSV_'+str(year),base+name,filename=name,
                         notes='Official derived auxiliary fields; link to main bundle rather than treating as additional crashes.')
d.register_source({'region':'FARS_Nationwide','name':'NHTSA_FARS_annual_bundles','years':list(range(1975,2025)),
                   'jobs':len(d.JOBS),'url':'https://www.nhtsa.gov/file-downloads?p=nhtsa/downloads/FARS/',
                   'four_fields':'fatal-only; early coordinates not guaranteed','scope':'national'})
d.atomic_json(d.MANIFEST/'fars_plan.json',d.JOBS)
d.atomic_json(d.MANIFEST/'fars_sources.json',d.SOURCES)
with ThreadPoolExecutor(2) as pool:
    tasks=[pool.submit(d.run_job,job) for job in d.JOBS]
    for task in as_completed(tasks):task.result()
d.atomic_json(d.MANIFEST/'fars_status.json',[{k:v for k,v in job.items() if k!='meta'} for job in d.JOBS])
print('FARS COMPLETE',flush=True)
