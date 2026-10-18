import download_us_crashes as d
from concurrent.futures import ThreadPoolExecutor
for name,ident,date in [('NYS_DMV_case','e8ky-4vqe','date'),('NYS_DMV_vehicle','xe9x-a24f','year'),('NYS_DMV_person','ir4y-sesj','year'),('NYS_DMV_violation','abfj-y7uq','year')]:
    try:d.soc_discover('NY',name,'data.ny.gov',ident,date,notes='Official public DMV four-year window. No latitude/longitude; case table lacks public crash key for companion joins. Supplemental archive, not eligible for spatial crash analysis.',four_fields='no: missing coordinates; joining limitations')
    except Exception as exc:d.event('source_failed',region='NY',source=name,error=str(exc))
d.atomic_json(d.MANIFEST/'expansionNY_plan.json',d.JOBS);d.atomic_json(d.MANIFEST/'expansionNY_sources.json',d.SOURCES)
with ThreadPoolExecutor(2) as pool:
    for result in pool.map(d.run_job,d.JOBS):d.atomic_json(d.MANIFEST/'expansionNY_status.json',[{k:v for k,v in x.items() if k!='meta'} for x in d.JOBS])
print('NY EXPANSION COMPLETE',flush=True)
