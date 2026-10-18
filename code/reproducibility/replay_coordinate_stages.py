"""Rerun coordinate linkage using preserved donor snapshots, without network acquisition."""
import ast,json,os,shutil,subprocess,sys,time
from pathlib import Path
from replay_representative_years import L,R,C,W,adapt,sha
S=C/'Unified_MMUCC6/scripts'
def copy(src,dst):
 if src.is_dir():shutil.copytree(src,dst,dirs_exist_ok=True)
 elif src.exists():dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
def main(st):
 w=W/st;u=w/'Unified_MMUCC6';year=2021
 r=json.loads((w/'report.json').read_text(encoding='utf-8-sig'));out=u/f'data/crash/{st}/{st}_crashes_harmonized_2021.csv'
 if r['status']=='ERROR':raise RuntimeError('Base replay failed')
 env=os.environ.copy();env.update(USCRASH_ROOT=str(w),USCRASH_SOURCE_ROOT=str(w/'States'),USCRASH_PROJECT_ROOT=str(R.parent),USCRASH_CRASH_ROOT=str(w),USCRASH_UNIFIED_ROOT=str(u),PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',PYTHONPATH=str(S),USCRASH_CENSUS_STATES=str(R.parent/'Crash/verification/reference/census_states.zip'))
 def execute(name,args=(),offline=None):
  src=S/name;dst=w/('selected_'+name);adapt(src,dst,year)
  if offline:
   text=dst.read_text(encoding='utf-8-sig')
   if offline=='NC':
    # Recreate service catalog/count responses solely from frozen metadata and batches.
    hook="\ndef get(url, params):\n if url.rstrip('/') == BASE.rstrip('/'):\n  return {'services':[{'name':p.name,'type':'FeatureServer'} for p in SOURCE.iterdir() if p.is_dir() and (p/'metadata.json').exists()]}\n name=url.split('/')[ -4 if url.endswith('/query') else -3 ];folder=SOURCE/name\n if params.get('returnCountOnly'):\n  return {'count':sum(len(json.loads(p.read_text(encoding='utf-8-sig')).get('features',[])) for p in folder.glob('batch_*.json'))}\n return json.loads((folder/'metadata.json').read_text(encoding='utf-8-sig'))\n"
    text=text.replace("if __name__ == '__main__':",hook+"\nif __name__ == '__main__':")
   if offline=='NJ':
    text=text.replace("meta = requests.get(URL, params={'f': 'json'}, timeout=40).json()","meta = json.loads((SOURCE / 'metadata.json').read_text(encoding='utf-8-sig'))")
    hook="\ndef get(params):\n assert params.get('returnCountOnly'), 'Unexpected network-dependent request'\n return {'count':sum(len(json.loads(p.read_text(encoding='utf-8-sig')).get('features',[])) for p in SOURCE.glob('batch_*.json'))}\n"
    text=text.replace("if __name__ == '__main__':",hook+"\nif __name__ == '__main__':")
   dst.write_text(text,encoding='utf8')
  log=w/('post_'+name+'.log')
  with log.open('w',encoding='utf8') as f:p=subprocess.run([sys.executable,str(dst),*args],env=env,stdout=f,stderr=subprocess.STDOUT)
  r['stages'].append({'script':str(src.relative_to(L)),'calendar_year_adapter':True,'offline_catalog_adapter':offline,'exit_code':p.returncode,'log':str(log)})
  if p.returncode:raise RuntimeError(str(log))
 try:
  if st=='MA':execute('supplement_ma_archived_geometry.py')
  if st=='TX':
   copy(R/'Cities/Austin/2021',w/'Cities/Austin/2021');execute('supplement_tx_austin_coordinates.py')
  if st=='NC':
   copy(R/'States/NC/_CoordinateSources_2026-10-16',w/'States/NC/_CoordinateSources_2026-10-16')
   execute('supplement_nc_ka_coordinates.py');execute('supplement_nc_public_mapped_layers.py',offline='NC')
  if st=='NJ':
   copy(R/'States/NJ/_CoordinateSources_2026-10-16/DVRPC',w/'States/NJ/_CoordinateSources_2026-10-16/DVRPC');execute('supplement_nj_dvrpc_coordinates.py',offline='NJ')
  if st=='CA':
   copy(R/'States/CA/Local_coordinate_sources_2026-10-16',w/'States/CA/Local_coordinate_sources_2026-10-16')
   for city in ['SanFrancisco','SanJose']:copy(R/f'Cities/{city}/2021',w/f'Cities/{city}/2021')
   copy(R/'verification/unified_revision_evidence/CA_other_cities_2026-10-16/CA_counties.geojson',u/'qa/CA_other_cities_2026-10-16/CA_counties.geojson')
   execute('supplement_ca_coordinates.py');execute('supplement_ca_other_cities.py');execute('supplement_ca_other_cities.py',['--apply']);execute('supplement_ca_lacounty_report_coordinates.py',['--apply']);execute('supplement_ca_pasadena_report_coordinates.py')
  r['replayed_sha256']=sha(out);r['byte_identical']=r['replayed_sha256']==r['canonical_sha256_before'];r['status']='BYTE_IDENTICAL' if r['byte_identical'] else 'DIFFERENT_AFTER_POSTPROCESSING'
 except Exception as e:r['status']='POSTPROCESSING_ERROR';r['error']=str(e)
 (w/'report.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(st,r['status'],flush=True)
if __name__=='__main__':
 for st in sys.argv[1:]:main(st)
