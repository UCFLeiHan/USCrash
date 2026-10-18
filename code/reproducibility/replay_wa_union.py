"""Full WA dependency rerun: cross-year ID reconciliation needs all ten CAT baselines."""
import json,os,shutil,subprocess,sys,time
from replay_representative_years import L,R,C,W,sha
w=W/'WA';u=w/'Unified_MMUCC6'
while not (w/'report.json').exists():time.sleep(5)
r=json.loads((w/'report.json').read_text(encoding='utf-8-sig'));shutil.copy2(w/'report.json',w/'report_before_union.json')
env=os.environ.copy();env.update(USCRASH_ROOT=str(w),USCRASH_SOURCE_ROOT=str(w/'States'),USCRASH_PROJECT_ROOT=str(R.parent),PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
shutil.copytree(R/'States/WA',w/'States/WA',dirs_exist_ok=True)
shutil.copy2(C/'Unified_MMUCC6/config/states/WA.json',u/'config/states/WA.json')
stages=[('build_wa_crash_level.py',[]),('harmonize_crash.py',['--state','WA']),('enrich_wa_from_srff.py',['--promote']),('validate_harmonized_crash.py',['--state','WA'])]
try:
 for name,args in stages:
  log=w/('union_'+name+'.log')
  with log.open('w',encoding='utf8') as f:p=subprocess.run([sys.executable,str(C/'Unified_MMUCC6/scripts'/name),*args],env=env,stdout=f,stderr=subprocess.STDOUT)
  r['stages'].append({'script':name,'args':args,'exit_code':p.returncode,'log':str(log)})
  if p.returncode:raise RuntimeError(str(log))
 checks=[]
 for p in sorted((u/'data/crash/WA').glob('*.csv')):
  official=R/'Unified_MMUCC6/data/crash/WA'/p.name;checks.append({'file':p.name,'replayed_sha256':sha(p),'final_sha256':sha(official)})
  checks[-1]['byte_identical']=checks[-1]['replayed_sha256']==checks[-1]['final_sha256']
 r['dependency_years']=checks;r['byte_identical']=all(c['byte_identical'] for c in checks);r['status']='BYTE_IDENTICAL' if r['byte_identical'] else 'DIFFERENT_AFTER_WA_UNION';r['replayed_sha256']=sha(u/'data/crash/WA/WA_crashes_harmonized_2021.csv')
except Exception as e:r['status']='WA_UNION_ERROR';r['error']=str(e)
(w/'report.json').write_text(json.dumps(r,indent=2),encoding='utf8');print('WA',r['status'],flush=True)
