"""Reconcile ledger accounting against an independent full canonical availability scan."""
import json,shutil,pandas as pd
from coordinate_supplement_utils import REV,U,sha
s=json.loads((REV/'summary.json').read_text());assert s['new_coordinates']==1489889
actual=pd.read_csv(REV/'current_coordinate_full_scan.csv');expected=pd.read_csv(REV/'state_year_coordinate_before_after.csv')
m=actual.merge(expected[['state','year','records','valid_after']],on=['state','year'],suffixes=('_scan','_ledger'),validate='one_to_one');assert len(m)==511
assert m.records_scan.eq(m.records_ledger).all() and m.valid.eq(m.valid_after).all()
m['status']='PASS';m.to_csv(REV/'full_scan_reconciliation.csv',index=False)
s['full_511_file_scan_reconciled']=True;s['ID_county_screen_withdrawn']=64
pairs=set()
for p in REV.glob('*/*_coordinate_changes.csv'):
 d=pd.read_csv(p,usecols=lambda c:c in ['coordinate_source_file','coordinate_source_sha256'],dtype=str,keep_default_na=False)
 if len(d) and len(d.columns)==2:pairs.update(d.itertuples(index=False,name=None))
rows=[]
for p,h in sorted(pairs):
 current=sha(p);assert current==h;rows.append(dict(source_file=p,recorded_sha256=h,current_sha256=current,status='PASS'))
pd.DataFrame(rows).to_csv(REV/'source_hash_verification.csv',index=False);s['source_files_hash_verified']=len(rows)
(REV/'summary.json').write_text(json.dumps(s,indent=2),encoding='utf8');(U/'coordinate_recovery_manifest.json').write_text(json.dumps({**s,'revision_directory':str(REV),'report':str(REV/'index.html'),'code_runner':str(U/'scripts/run_coordinate_recovery.py')},indent=2),encoding='utf8')
p=REV/'README.md';t=p.read_text(encoding='utf8').replace('Before/after availability totals use frozen baseline counts plus independently verified additions, not a new nationwide scan.', 'Before/after ledger totals were reconciled against an independent full-current scan of all 511 canonical annual files (full_scan_reconciliation.csv). All state/year record and valid-coordinate counts agree. All 58 source-extract hashes used for promotions were independently verified.');p.write_text(t,encoding='utf8')
p=REV/'index.html';t=p.read_text(encoding='utf8').replace('<h1>Coordinate recovery</h1>','<h1>Coordinate recovery</h1><p><strong>Final QA: PASS.</strong> Full-current scan of all 511 annual files agrees with the before/after ledgers. Source-extract SHA-256 checks passed. <a href="full_scan_reconciliation.csv">Full-scan reconciliation</a> | <a href="source_hash_verification.csv">Source hashes</a></p>');p.write_text(t,encoding='utf8')
for f in ['finalize_coordinate_recovery_report.py','run_coordinate_recovery.py']:shutil.copy2(U/'scripts'/f,REV/'executed_scripts'/f)
print(json.dumps(s),flush=True)
