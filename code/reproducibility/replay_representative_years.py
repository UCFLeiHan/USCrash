"""Isolated representative-year rerun. Never writes into the original source/data tree."""
import ast,csv,hashlib,json,os,shutil,subprocess,sys,time,traceback
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
L=Path(__file__).resolve().parents[1]; R=L.parent; C=L/'replay_runtime'
W=Path(os.environ.get('USCRASH_REPLAY_ROOT',str(R/'verification/replay_checks'/'representative_years'))).resolve()
if W==R or W.is_relative_to(R/'States') or W.is_relative_to(R/'Unified_MMUCC6') or R.is_relative_to(W):raise ValueError('Replay root must be isolated from preserved sources and formal outputs')
W.mkdir(parents=True,exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
def adapt(src,dst,year):
 # Restrict only literal calendar-year iteration; never change classification ranges.
 tree=ast.parse(src.read_text(encoding='utf-8-sig'))
 class Years(ast.NodeTransformer):
  def selected(self,n):
   return isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='range' and n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,int) and 1990<=n.args[0].value<=2030
  def visit_For(self,n):
   self.generic_visit(n)
   if self.selected(n.iter):n.iter=ast.List(elts=[ast.Constant(year)],ctx=ast.Load())
   return n
  def visit_Assign(self,n):
   self.generic_visit(n)
   if any(isinstance(x,ast.Name) and x.id=='YEARS' for x in n.targets) and self.selected(n.value):n.value=ast.List(elts=[ast.Constant(year)],ctx=ast.Load())
   return n
 tree=Years().visit(tree);ast.fix_missing_locations(tree);dst.write_text(ast.unparse(tree),encoding='utf8')
PRE={
 'CA':('build_ca_crash_level.py','span'),'OH':('build_oh_crash_level.py','span'),'SD':('build_sd_crash_level.py','span'),
 'UT':('build_ut_crash_level.py','years'),'VA':('build_va_crash_level.py','years'),'NJ':('prepare_nj_crash_level.py','year'),
 'VT':('prepare_vt_crash_level.py','adapt'),'WA':('build_wa_crash_level.py','pos'),
 'KY':('../code/acquisition/enrich_kentucky_incidents.py','year'),'MN':('../code/acquisition/enrich_mn_rsic_2025.py','pos'),
 'MT':('../code/acquisition/enrich_montana_crashes.py','year'),'NV':('../code/acquisition/enrich_nevada_official.py','pos'),
 'PA':('../code/acquisition/enrich_pennsylvania_flags.py','pos'),'TN':('../code/acquisition/enrich_tennessee_titan.py','pos'),
 'TX':('../code/acquisition/enrich_texas_cris.py','pos'),'WY':('../code/acquisition/process_wy_official_2016_2025.py','adapt')}
def run_one(st,year,link):
 work=W/st; report={'state':st,'year':year,'stages':[],'status':'RUNNING'}
 if (work/'report.json').exists() and (work/link['output_path']).exists():
  previous=json.loads((work/'report.json').read_text(encoding='utf-8-sig'))
  if previous.get('replayed_sha256')==sha(work/link['output_path']):return previous
 work.mkdir(exist_ok=True);u=work/'Unified_MMUCC6'
 env=os.environ.copy();env.update(USCRASH_ROOT=str(work),USCRASH_SOURCE_ROOT=str(work/'States'),USCRASH_PROJECT_ROOT=str(R.parent),USCRASH_CRASH_ROOT=str(work),USCRASH_UNIFIED_ROOT=str(u),PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',PYTHONPATH=str(C/'Unified_MMUCC6/scripts'),USCRASH_CENSUS_STATES=str(R.parent/'Crash/verification/reference/census_states.zip'))
 def execute(src,args=(),limited=False):
  p=src
  if limited:
   p=work/('selected_'+src.name);adapt(src,p,year)
  num=len(report['stages']);log=work/f'{num:02}_{src.stem}.log';t=time.time()
  with log.open('w',encoding='utf8') as f:ret=subprocess.run([sys.executable,str(p),*map(str,args)],env=env,stdout=f,stderr=subprocess.STDOUT)
  stage={'script':str(src.relative_to(L)),'calendar_year_adapter':limited,'args':list(map(str,args)),'exit_code':ret.returncode,'seconds':round(time.time()-t,2),'log':str(log)};report['stages'].append(stage)
  if ret.returncode:raise RuntimeError(f'{src.name} failed; see {log}')
 try:
  shutil.copytree(C/'Unified_MMUCC6/config',u/'config',dirs_exist_ok=True)
  conf=u/'config/states'/f'{st}.json';cfg=json.loads(conf.read_text(encoding='utf-8-sig'));cfg['versions']=[dict(v,year_start=year,year_end=year) for v in cfg['versions'] if v['year_start']<=year<=v['year_end']];conf.write_text(json.dumps(cfg,indent=2),encoding='utf8')
  shutil.copytree(R/'States'/st/str(year),work/'States'/st/str(year),dirs_exist_ok=True)
  original=R/link['output_path'];report['canonical_sha256_before']=sha(original)
  source=work/link['input_path']; report['prepared_input_sha256_before']=sha(R/link['input_path'])
  if st in PRE:
   name,mode=PRE[st];src=(C/'acquisition'/Path(name).name) if name.startswith('../') else C/'Unified_MMUCC6/scripts'/name
   # Required shared sources are copied, never linked to mutable originals.
   for item in (R/'States'/st).iterdir():
    if item.is_file():shutil.copy2(item,work/'States'/st/item.name)
   if st=='WY':
    for p in (R/'States/WY/Raw').glob('*.csv'):shutil.copy2(p,work/'States/WY'/p.name)
   source.unlink(missing_ok=True)
   args={'span':['--year-start',year,'--year-end',year],'years':['--years',year],'year':['--year',year],'pos':[year],'adapt':[]}[mode]
   execute(src,args,mode=='adapt');report['preparation']='REEXECUTED'
   report['prepared_input_sha256_rebuilt']=sha(source)
  else:report['preparation']='PRESERVED_SOURCE_INPUT_NO_SEPARATE_PREPARATION_EXECUTED'
  execute(C/'Unified_MMUCC6/scripts/harmonize_crash.py',['--state',st])
  # Archived entity enrichment experiments do not match this frozen release.
  # Diagnostic reruns are retained separately; do not apply them to formal replay.
  if st in set():
   name={'CT':'enrich_ct_entity_counts.py','ID':'enrich_id_from_units.py','MS':'enrich_ms_from_vehicle_events.py'}[st]
   execute(C/'Unified_MMUCC6/scripts'/name,['--year-start',year,'--year-end',year])
  execute(C/'Unified_MMUCC6/scripts/validate_harmonized_crash.py',['--state',st])
  out=work/link['output_path'];report['replayed_sha256']=sha(out);report['canonical_sha256_after']=sha(original)
  report['canonical_unchanged']=report['canonical_sha256_before']==report['canonical_sha256_after']
  report['byte_identical']=report['replayed_sha256']==report['canonical_sha256_before']
  report['status']='BYTE_IDENTICAL' if report['byte_identical'] else 'DIFFERENT_REQUIRES_POSTPROCESSING_OR_REVIEW'
 except Exception as e:report['status']='ERROR';report['error']=str(e);report['traceback']=traceback.format_exc()
 (work/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(st,year,report['status'],flush=True);return report
def main():
 rows=list(csv.DictReader((R/'dataset/manifests/configured_input_output_links.csv').open(encoding='utf-8-sig')));selected={}
 for row in rows:
  st=row['state'];year=int(row['year'])
  if st not in selected or abs(year-2021)<abs(int(selected[st]['year'])-2021):selected[st]=row
 results=[]
 with ThreadPoolExecutor(max_workers=2) as pool:
  futures=[pool.submit(run_one,st,int(row['year']),row) for st,row in sorted(selected.items())]
  for f in as_completed(futures):
   results.append(f.result());(W/'summary.json').write_text(json.dumps(sorted(results,key=lambda x:x['state']),indent=2),encoding='utf8')
 print('COMPLETE',len(results),flush=True)
if __name__=='__main__':main()
