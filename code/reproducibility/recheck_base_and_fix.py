"""Diagnostic reruns; frozen code and canonical outputs remain untouched."""
import json,os,subprocess,sys,shutil
from replay_representative_years import L,R,C,W,sha
for st in sys.argv[1:]:
 w=W/st;u=w/'Unified_MMUCC6';p=w/'report.json';r=json.loads(p.read_text(encoding='utf-8-sig'));y=r['year'];rel=f'data/crash/{st}/{st}_crashes_harmonized_{y}.csv'
 shutil.copy2(p,w/'report_before_diagnostic.json')
 env=os.environ.copy();env.update(USCRASH_ROOT=str(w),USCRASH_SOURCE_ROOT=str(w/'States'),USCRASH_PROJECT_ROOT=str(R.parent),PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',PYTHONPATH=str(C/'Unified_MMUCC6/scripts'))
 src=C/'Unified_MMUCC6/scripts/harmonize_crash.py'
 if st not in {'CT','ID','MS'}:
  text=src.read_text(encoding='utf-8-sig');needle='                    if "manner_raw_code" not in fields and "manner_raw_label" not in fields:'
  assert text.count(needle)==1
  target=w/'harmonize_crash_candidate.py';target.write_text(text.replace(needle,'                    manner_code = ""; manner_prov = "UNRESOLVED_CODE"\n'+needle),encoding='utf8');src=target
  r['candidate_fix']='Initialize manner_code/provenance per record before optional crosswalk lookup; frozen code unchanged.'
 if (u/rel).exists():shutil.copy2(u/rel,w/'output_before_diagnostic.csv')
 with (w/'diagnostic_core.log').open('w') as f:proc=subprocess.run([sys.executable,str(src),'--state',st],env=env,stdout=f,stderr=subprocess.STDOUT)
 r['diagnostic_core_exit']=proc.returncode
 if proc.returncode==0:
  r['replayed_sha256']=sha(u/rel);r['byte_identical']=r['replayed_sha256']==r['canonical_sha256_before'];r['status']='BYTE_IDENTICAL_CORE_ONLY' if r['byte_identical'] else 'DIFFERENT_CORE_ONLY'
 else:r['status']='DIAGNOSTIC_ERROR'
 p.write_text(json.dumps(r,indent=2),encoding='utf8');print(st,r['status'],flush=True)
