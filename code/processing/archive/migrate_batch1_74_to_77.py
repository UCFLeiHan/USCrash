from __future__ import annotations
import csv,json,subprocess,sys,hashlib
from pathlib import Path
BASE=Path(r'F:\LH_Research\USCrash\Crash\Unified_MMUCC6')
STATES=['AK','AL','AR','AZ','CO','CT','DC','DE','GA','IA']
EXPECTED='972609b90f887171d309cde8f31a66d4050e21a3691064d4cb871c928ec5ebf5'
baseline=json.loads((BASE/'qa'/'cross_state'/'migration_batch1_74_to_77_baseline.json').read_text())
with (BASE/'config'/'canonical_crash_schema.csv').open(encoding='utf-8-sig',newline='') as f: canon=[r['field_name'] for r in csv.DictReader(f)]
results={}
for s in STATES:
 print(f'BEGIN {s}',flush=True)
 h=subprocess.run([sys.executable,str(BASE/'scripts'/'harmonize_crash.py'),'--state',s],text=True,capture_output=True)
 print(h.stdout[-3000:],flush=True)
 if h.returncode:
  print(h.stderr,flush=True);raise SystemExit(f'{s} harmonize failed')
 v=subprocess.run([sys.executable,str(BASE/'scripts'/'validate_harmonized_crash.py'),'--state',s],text=True,capture_output=True)
 print(v.stdout[-2000:],flush=True)
 if v.returncode:
  print(v.stderr,flush=True);raise SystemExit(f'{s} validate failed')
 qa=BASE/'qa'/'post_harmonization'/s
 with (qa/'harmonization_summary.csv').open(encoding='utf-8-sig',newline='') as f: summ=list(csv.DictReader(f))
 annual={x['year']:int(x['output_rows']) for x in summ}
 if annual!=baseline[s]['annual']: raise SystemExit(f'{s} annual row change baseline={baseline[s]["annual"]} now={annual}')
 badclosure=[x['year'] for x in summ if int(x['source_rows'])-int(x['duplicate_source_rows'])-int(x['excluded_source_rows'])!=int(x['output_rows'])]
 if badclosure: raise SystemExit(f'{s} closure failed {badclosure}')
 manifest=json.loads((qa/'run_manifest.json').read_text()); validation=json.loads((qa/'validation_report.json').read_text())
 if manifest.get('schema_sha256')!=EXPECTED:raise SystemExit(f'{s} schema hash {manifest.get("schema_sha256")}')
 if manifest.get('result')!='PASS' or validation.get('result')!='PASS':raise SystemExit(f'{s} pass failure')
 if validation.get('rows')!=baseline[s]['total'] or validation.get('files')!=baseline[s]['years']:raise SystemExit(f'{s} validation count changed')
 headerbad=[]
 for p in sorted((BASE/'data'/'crash'/s).glob(f'{s}_crashes_harmonized_*.csv')):
  with p.open(encoding='utf-8-sig',newline='') as f:
   if next(csv.reader(f))!=canon:headerbad.append(p.name)
 if headerbad:raise SystemExit(f'{s} header mismatch {headerbad}')
 results[s]={'years':len(summ),'rows':sum(annual.values()),'schema_columns':77,'schema_sha256':EXPECTED,'validation':'PASS','annual_counts_unchanged':True,'summary_closed':True}
 (BASE/'qa'/'cross_state'/'migration_batch1_74_to_77_result.partial.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
 print(f'PASS {s} years={len(summ)} rows={sum(annual.values())}',flush=True)
out=BASE/'qa'/'cross_state'/'migration_batch1_74_to_77_result.json';out.write_text(json.dumps({'result':'PASS','states':results},indent=2),encoding='utf-8')
print('BATCH PASS',out,flush=True)
