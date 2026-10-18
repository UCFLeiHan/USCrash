"""Official PennDOT statewide annual raw ZIPs, as linked by the public download web map."""
import download_us_crashes as d
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests,json

base='https://gis.penndot.pa.gov/gishub/crashZip/Statewide/'
for year in range(2006,2026):
    filename=f'Statewide_{year}.zip'
    d.direct_job('PA',year,'PennDOT_Statewide_'+str(year),base+filename,filename=filename,
                 notes='Supplementary: publicly deidentified crash/unit/person/flag tables. Exact occurrence-date privacy limitations; not all four requirements verified.')
# The collection-code reference documents 2005; retain it only if the public archive exists.
filename='Statewide_2005.zip'
try:
    with requests.get(base+filename,stream=True,timeout=30) as r:
        if r.status_code==200 and 'text/html' not in r.headers.get('Content-Type',''):
            d.direct_job('PA',2005,'PennDOT_Statewide_2005',base+filename,filename=filename,notes='Historical supplementary public raw archive; date/privacy limitations apply.')
except requests.RequestException:pass
d.register_source({'region':'PA','name':'PennDOT_public_statewide_ZIP','years':sorted(j['year'] for j in d.JOBS),'jobs':len(d.JOBS),
                   'url':'https://experience.arcgis.com/experience/51809b06e7b140208a4ed6fbad964990','four_fields':'exact date restricted / supplementary',
                   'notes':'Native statewide ZIPs found in public web-map popup expression, not a private database request.'})
d.atomic_json(d.MANIFEST/'pa_plan.json',d.JOBS)
d.atomic_json(d.MANIFEST/'pa_sources.json',d.SOURCES)
with ThreadPoolExecutor(1) as pool:
    for task in as_completed([pool.submit(d.run_job,job) for job in d.JOBS]):task.result()
d.atomic_json(d.MANIFEST/'pa_status.json',[{k:v for k,v in job.items() if k!='meta'} for job in d.JOBS])
print('PA COMPLETE',flush=True)
