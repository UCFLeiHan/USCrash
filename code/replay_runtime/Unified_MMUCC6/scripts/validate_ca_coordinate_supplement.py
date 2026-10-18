"""Independent post-write accounting of all changed canonical annual files."""
import os as _uscrash_paths_os
from pathlib import Path
import json,hashlib
import pandas as pd
import argparse
R=(Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'Unified_MMUCC6')
parser=argparse.ArgumentParser();parser.add_argument('--run-dir',default=str(R/'qa/CA_coordinate_supplement_2026-10-16'));args=parser.parse_args()
P=Path(args.run_dir)
manifest=json.loads((P/'run_manifest.json').read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
result=[]
for run in manifest['years']:
 y=run['year'];p=R/f'data/crash/CA/CA_crashes_harmonized_{y}.csv';old=P/'canonical_before'/p.name
 if not old.exists() and run['filled']==0:old=p
 assert sha(old)==run['sha256_before'];assert sha(p)==run['sha256_after']
 changes=pd.read_csv(P/f'CA_{y}_coordinate_changes.csv',dtype=str,keep_default_na=False)
 cols=['crash_uid','latitude','longitude','coordinate_status','city']
 a=pd.read_csv(old,usecols=cols,dtype=str,keep_default_na=False);b=pd.read_csv(p,usecols=cols,dtype=str,keep_default_na=False)
 assert len(a)==len(b)==run['rows'] and a.crash_uid.equals(b.crash_uid) and b.crash_uid.is_unique
 assert len(changes)==run['filled'] and changes.crash_uid.is_unique
 mask=b.crash_uid.isin(changes.crash_uid)
 assert a.loc[~mask].equals(b.loc[~mask])
 valid=lambda d:pd.to_numeric(d.latitude,errors='coerce').between(32.3,42.2)&pd.to_numeric(d.longitude,errors='coerce').between(-124.6,-113.9)
 assert not valid(a.loc[mask]).any();assert valid(b.loc[mask]).all()
 assert len(pd.read_csv(p,nrows=0).columns)==77
 for city in ['ALL','Los Angeles','San Francisco','San Jose']:
  sub=pd.Series(True,index=a.index) if city=='ALL' else a.city.eq(city)
  result.append(dict(year=y,city=city,rows=int(sub.sum()),coordinates_before=int((valid(a)&sub).sum()),coordinates_after=int((valid(b)&sub).sum()),filled=int((mask&sub).sum()),status='PASS'))
pd.DataFrame(result).to_csv(P/'independent_validation.csv',index=False)
print(pd.DataFrame(result).query("year==2023").to_string(index=False));print('ALL 11 YEARS PASSED')
