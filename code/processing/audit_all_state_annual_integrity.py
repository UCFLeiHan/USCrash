from __future__ import annotations
import csv,json,hashlib
from pathlib import Path
ROOT=Path(r'F:\LH_Research\USCrash\Crash')
PIPE=ROOT/'Unified_MMUCC6'; STATES=ROOT/'States'
with (PIPE/'config'/'canonical_crash_schema.csv').open(encoding='utf-8-sig',newline='') as _f: CANONICAL=[r['field_name'] for r in csv.DictReader(_f)]
CANONICAL_HASH=hashlib.sha256((PIPE/'config'/'canonical_crash_schema.csv').read_bytes()).hexdigest()
configs=sorted((PIPE/'config'/'states').glob('??.json'))
report={'scope':'all 42 states with formal configs','audit_only':True,'known_exceptions':['NY','NV'],'states':{},'unexpected_problem_states':[]}
rows=[]
for cp in configs:
 s=cp.stem; cfg=json.loads(cp.read_text(encoding='utf-8'))
 year_versions={}
 for v in cfg.get('versions',[]):
  for y in range(int(v['year_start']),int(v['year_end'])+1): year_versions.setdefault(y,[]).append(v)
 expected=sorted(year_versions); source_missing=[];source_ambiguous=[];overlap=[]
 for y,vs in year_versions.items():
  if len(vs)!=1: overlap.append(y);continue
  v=vs[0]; candidates=[STATES/s/str(y)/pat.format(year=y) for pat in v['source_patterns']]
  found=[str(p) for p in candidates if p.is_file() and p.stat().st_size>0]
  if not found:source_missing.append(y)
  elif len(found)>1:source_ambiguous.append({'year':y,'files':found})
 qa=PIPE/'qa'/'post_harmonization'/s; data=PIPE/'data'/'crash'/s
 summary_path=qa/'harmonization_summary.csv'; validation_path=qa/'validation_report.json'; manifest_path=qa/'run_manifest.json'
 summaries=[]
 if summary_path.exists():
  with summary_path.open(encoding='utf-8-sig',newline='') as f:summaries=list(csv.DictReader(f))
 summary_years=sorted({int(x['year']) for x in summaries})
 summary_duplicates=len(summaries)-len(summary_years)
 summary_output=sum(int(x.get('output_rows') or 0) for x in summaries)
 closure_bad=[]
 for x in summaries:
  sr=int(x.get('source_rows') or 0);du=int(x.get('duplicate_source_rows') or 0);ex=int(x.get('excluded_source_rows') or 0);out=int(x.get('output_rows') or 0)
  if sr-du-ex!=out:closure_bad.append(int(x['year']))
 output_files=sorted(data.glob(f'{s}_crashes_harmonized_*.csv')) if data.exists() else []
 output_years=[];unexpected_names=[];header_mismatch_years=[]
 for p in output_files:
  try:
   _y=int(p.stem.rsplit('_',1)[-1]);output_years.append(_y)
   with p.open(encoding='utf-8-sig',newline='') as _f:
    if next(csv.reader(_f))!=CANONICAL:header_mismatch_years.append(_y)
  except:unexpected_names.append(p.name)
 output_years=sorted(set(output_years))
 val=json.loads(validation_path.read_text(encoding='utf-8')) if validation_path.exists() else {}
 man=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
 issues=[]
 def add_if(cond,label):
  if cond:issues.append(label)
 add_if(overlap,'CONFIG_YEAR_OVERLAP')
 add_if(source_missing,'SOURCE_YEAR_MISSING')
 add_if(source_ambiguous,'SOURCE_YEAR_AMBIGUOUS')
 add_if(set(expected)-set(summary_years),'SUMMARY_MISSING_EXPECTED_YEARS')
 add_if(set(summary_years)-set(expected),'SUMMARY_HAS_UNEXPECTED_YEARS')
 add_if(summary_duplicates,'SUMMARY_DUPLICATE_YEARS')
 add_if(set(expected)-set(output_years),'OUTPUT_MISSING_EXPECTED_YEARS')
 add_if(set(output_years)-set(expected),'OUTPUT_HAS_UNEXPECTED_YEARS')
 add_if(unexpected_names,'OUTPUT_UNEXPECTED_FILENAMES')
 add_if(header_mismatch_years,'OUTPUT_SCHEMA_HEADER_MISMATCH')
 add_if(closure_bad,'SUMMARY_ROW_CLOSURE_MISMATCH')
 add_if(not validation_path.exists(),'VALIDATION_REPORT_MISSING')
 add_if(bool(val) and val.get('result')!='PASS','VALIDATION_NOT_PASS')
 add_if(bool(val) and int(val.get('files',-1))!=len(output_years),'VALIDATION_FILE_COUNT_MISMATCH')
 add_if(bool(val) and int(val.get('rows',-1))!=summary_output,'VALIDATION_ROW_COUNT_MISMATCH')
 add_if(not manifest_path.exists(),'RUN_MANIFEST_MISSING')
 add_if(bool(man) and man.get('result')!='PASS','RUN_MANIFEST_NOT_PASS')
 add_if(bool(man) and man.get('schema_sha256')!=CANONICAL_HASH,'RUN_MANIFEST_SCHEMA_HASH_MISMATCH')
 add_if(bool(man) and int(man.get('years',-1))!=len(summary_years),'RUN_MANIFEST_YEAR_COUNT_MISMATCH')
 regression_overwrite=(set(output_years)==set(expected) and set(summary_years)!=set(expected)) or (len(output_years)>len(summary_years))
 add_if(regression_overwrite,'LIKELY_REGRESSION_RUN_OVERWROTE_QA')
 item={'expected_years':expected,'expected_year_count':len(expected),'config_overlap_years':overlap,'source_missing_years':source_missing,'source_ambiguous_years':source_ambiguous,'summary_years':summary_years,'summary_output_rows':summary_output,'summary_closure_bad_years':closure_bad,'output_years':output_years,'header_mismatch_years':header_mismatch_years,'canonical_schema_sha256':CANONICAL_HASH,'run_manifest_schema_sha256':man.get('schema_sha256'),'validation_exists':validation_path.exists(),'validation_result':val.get('result'),'validation_files':val.get('files'),'validation_rows':val.get('rows'),'manifest_result':man.get('result'),'manifest_years':man.get('years'),'regression_overwrite_detected':regression_overwrite,'issues':issues,'exception_status':'KNOWN_EXCEPTION' if s in {'NY','NV'} and issues else ''}
 report['states'][s]=item
 if issues and s not in {'NY','NV'}: report['unexpected_problem_states'].append(s)
 rows.append({'state':s,'expected_range':f'{min(expected)}-{max(expected)}' if expected else '','expected_years':len(expected),'source_missing':';'.join(map(str,source_missing)),'summary_years':len(summary_years),'output_years':len(output_years),'header_mismatch_years':';'.join(map(str,header_mismatch_years)),'validation_files':val.get('files',''),'summary_rows':summary_output,'validation_rows':val.get('rows',''),'regression_overwrite':regression_overwrite,'issues':';'.join(issues),'exception_status':item['exception_status']})
report['result']='PASS' if not report['unexpected_problem_states'] else 'ISSUES_FOUND'
out=PIPE/'qa'/'cross_state';out.mkdir(parents=True,exist_ok=True)
(out/'all_42_state_annual_integrity_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
with (out/'all_42_state_annual_integrity_audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys(),lineterminator='\n');w.writeheader();w.writerows(rows)
print(json.dumps({'result':report['result'],'unexpected_problem_states':report['unexpected_problem_states'],'problems':{s:x['issues'] for s,x in report['states'].items() if x['issues']}},indent=2))
