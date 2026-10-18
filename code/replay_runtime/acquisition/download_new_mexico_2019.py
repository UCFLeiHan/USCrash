import os as _uscrash_paths_os
import csv, json, os, time
from pathlib import Path
import requests

URL = 'https://gis.dot.nm.gov/epermit/rest/services/EGIS/EgisViewer/MapServer/2'
OUT = (Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/NM/2019')
OUT.mkdir(parents=True, exist_ok=True)
session = requests.Session()

def get(suffix='', **params):
    for attempt in range(6):
        try:
            response = session.get(URL + suffix, params={'f': 'json', **params}, timeout=180)
            response.raise_for_status()
            result = response.json()
            if 'error' in result:
                raise RuntimeError(result['error'])
            return result
        except Exception:
            if attempt == 5:
                raise
            time.sleep(2 ** attempt)

meta = get()
(OUT / 'arcgis_metadata.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
ids = sorted(get('/query', where='Year=2019', returnIdsOnly='true')['objectIds'])
fields = [field['name'] for field in meta['fields'] if field['type'] != 'esriFieldTypeGeometry']
fields += ['longitude', 'latitude']
final = OUT / 'NM_crashes_2019.csv'
partial = final.with_suffix('.csv.partial')
written = 0
with partial.open('w', encoding='utf-8-sig', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    for start in range(0, len(ids), 100):
        batch = ids[start:start + 100]
        result = get('/query', objectIds=','.join(map(str, batch)), outFields='*',
                     returnGeometry='true', outSR='4326')
        for feature in result['features']:
            row = feature['attributes']
            geometry = feature.get('geometry') or {}
            row['longitude'] = geometry.get('x', '')
            row['latitude'] = geometry.get('y', '')
            writer.writerow(row)
            written += 1
        handle.flush()
        print(f'{written}/{len(ids)}', flush=True)
if written != len(ids):
    raise RuntimeError(f'Expected {len(ids)}, wrote {written}')
os.replace(partial, final)
print(f'COMPLETE {written}', flush=True)
