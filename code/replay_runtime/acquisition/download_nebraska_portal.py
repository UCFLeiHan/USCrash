import os as _uscrash_paths_os
import csv, json, os, time
from pathlib import Path
import requests

URL = 'https://ntip.nebraska.gov/Map/Crashes'
ROOT = (Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/NE')
YEARS = range(2020, 2009, -1)
FIELDS = ['crash_key','latitude','longitude','severity_code','date','time','day_of_week',
          'county','location','crash_type','first_harmful_event','alcohol_related','weather']
session = requests.Session()

def fetch(year):
    for attempt in range(6):
        try:
            response = session.post(URL, data={'fromDate': f'{year}-01-01',
                                                'toDate': f'{year}-12-31'}, timeout=300)
            response.raise_for_status()
            return response.json()
        except Exception:
            if attempt == 5:
                raise
            time.sleep(2 ** attempt)

ROOT.mkdir(parents=True, exist_ok=True)
(ROOT/'README.txt').write_text(
    'Official source: Nebraska DOT Self Service Crash Data Portal\n'
    'https://ntip.nebraska.gov/\n'
    'Each CSV row is one mapped crash returned by the public portal.\n', encoding='utf-8')
for year in YEARS:
    directory = ROOT / str(year); directory.mkdir(parents=True, exist_ok=True)
    final = directory / f'NE_mapped_crashes_{year}.csv'
    if final.exists():
        continue
    result = fetch(year)
    rows = []
    for group in result.get('CoordGroups', []):
        for crash in group.get('Crashes', []):
            rows.append({
                'crash_key': crash.get('k'), 'latitude': crash.get('a'),
                'longitude': crash.get('o'), 'severity_code': crash.get('s'),
                'date': crash.get('d'), 'time': crash.get('t'),
                'day_of_week': crash.get('y'), 'county': crash.get('c'),
                'location': crash.get('l'), 'crash_type': crash.get('m'),
                'first_harmful_event': crash.get('f'),
                'alcohol_related': crash.get('r'), 'weather': crash.get('w')})
    partial = final.with_suffix('.csv.partial')
    with partial.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
    os.replace(partial, final)
    (directory/'portal_summary.json').write_text(json.dumps({
        'year': year, 'mapped_records': len(rows), 'severity': result.get('Severity')}, indent=2), encoding='utf-8')
    print(year, len(rows), result.get('Severity'), flush=True)
