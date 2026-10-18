import download_us_crashes as d
import json
from concurrent.futures import ThreadPoolExecutor
jobs=[j for j in json.loads((d.MANIFEST/'expansion3_plan.json').read_text()) if j['region']=='OK']
with ThreadPoolExecutor(2) as pool:
    for result in pool.map(d.run_job,jobs):print(result['id'],result['status'],result.get('records'),flush=True)
d.atomic_json(d.MANIFEST/'expansionOK_status.json',[{k:v for k,v in j.items() if k!='meta'} for j in jobs])
