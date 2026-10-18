import csv,json,os,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from replay_representative_years import W,R,L,C,sha
links=list(csv.DictReader((R/'manifests/configured_input_output_links.csv').open(encoding='utf-8-sig')))
def inspect(p):
 r=json.loads(p.read_text(encoding='utf-8-sig'));st=r['state'];year=r['year'];w=p.parent
 env=os.environ.copy();env.update(USCRASH_ROOT=str(w),USCRASH_SOURCE_ROOT=str(w/'States'),PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
 with (w/'final_validation.log').open('w',encoding='utf8') as f:ret=subprocess.run([sys.executable,str(C/'Unified_MMUCC6/scripts/validate_harmonized_crash.py'),'--state',st],env=env,stdout=f,stderr=subprocess.STDOUT)
 a=next(x for x in links if x['state']==st and int(x['year'])==year);canonical=R/a['output_path'];out=w/a['output_path']
 row={'state':st,'year':year,'result':r['status'],'byte_identical':out.exists() and sha(out)==sha(canonical),'canonical_unchanged':sha(canonical)==r['canonical_sha256_before'],'source_input_unchanged':sha(R/a['input_path'])==r['prepared_input_sha256_before'],'validator_pass':ret.returncode==0,'preparation':r['preparation'],'candidate_fix':r.get('candidate_fix',''),'report':str(p)}
 return row
rows=list(ThreadPoolExecutor(max_workers=2).map(inspect,sorted(W.glob('*/report.json'))))
with (W/'verification_results.csv').open('w',encoding='utf-8-sig',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
summary={'cases':len(rows),'byte_identical_cases':sum(x['byte_identical'] for x in rows),'validator_pass_cases':sum(x['validator_pass'] for x in rows),'source_and_canonical_unchanged':all(x['canonical_unchanged'] and x['source_input_unchanged'] for x in rows),'raw_preparation_executed_cases':sum(x['preparation']=='REEXECUTED' for x in rows),'corrected_core_cases':[x['state'] for x in rows if x['candidate_fix']],'scope':'Preserved local source snapshots, representative years. Not live re-download verification or all schema versions. Calendar-only adapters and cached service-catalog adapters retained. CT/ID/MS optional entity enrichments excluded from this frozen release; diagnostic differences preserved. WA additionally reruns ten dependency years.','rows':rows}
summary['result']='PASS' if len(rows)==42 and all(x['byte_identical'] and x['validator_pass'] and x['canonical_unchanged'] and x['source_input_unchanged'] for x in rows) else 'REVIEW_REQUIRED'
(W/'verification_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
text=['# Representative-year reproducibility verification','',f"Result: {summary['result']}",f"Representative cases: {len(rows)}; byte-identical: {summary['byte_identical_cases']}; validators passed: {summary['validator_pass_cases']}.",'','## Scope','',summary['scope'],'','The preserved original code snapshot is unchanged. KY/MT/TN encountered an uninitialized manner-provenance variable; a separately saved per-record initialization fix reproduced the existing final data. No formal data values were changed.','', '## Cases','', '| State | Year | Exact final bytes | Validator | Preparation rerun |','|---|---:|---|---|---|']
text += [f"| {x['state']} | {x['year']} | {x['byte_identical']} | {x['validator_pass']} | {x['preparation']=='REEXECUTED'} |" for x in rows]
(W/'README.md').write_text('\n'.join(text)+'\n',encoding='utf8');print(json.dumps({k:v for k,v in summary.items() if k!='rows'},indent=2))
