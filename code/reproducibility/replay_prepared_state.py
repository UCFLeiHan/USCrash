"""Rebuild from preserved prepared inputs in a fresh, isolated output directory.

This executes generic harmonization and validation, not source acquisition or
entity preparation. A byte mismatch is reported as a mismatch, not repaired by
copying the final output. Post-harmonization revisions require separate replay.
"""
import argparse,csv,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--state',required=True)
    p.add_argument('--output-root',type=Path,required=True)
    p.add_argument('--portable-code',action='store_true',help='Exercise the separately tracked path-portability candidate')
    a=p.parse_args();root=a.root.resolve();target=a.output_root.resolve();state=a.state.upper()
    if target==root or root.is_relative_to(target) or target.is_relative_to(root/'Unified_MMUCC6') or target.is_relative_to(root/'States'):
        p.error('Output must be isolated from source and canonical trees')
    if target.exists() and any(target.iterdir()):p.error('Output directory must be empty')
    source=root/'Unified_MMUCC6';release=Path(__file__).resolve().parents[1]
    frozen=(release/'replay_runtime' if a.portable_code else root)/'Unified_MMUCC6'
    if not (frozen/'config/states'/f'{state}.json').is_file():p.error('State is not present in frozen configurations')
    script_dir=frozen/'scripts' if a.portable_code else root/'code/processing'
    target.mkdir(parents=True,exist_ok=True);pipeline=target/'Unified_MMUCC6'
    shutil.copytree(frozen/'config',pipeline/'config')
    env=os.environ.copy();env['USCRASH_ROOT']=str(target);env['USCRASH_SOURCE_ROOT']=str(root/'States');env['USCRASH_PROJECT_ROOT']=str(root.parent);env['PYTHONDONTWRITEBYTECODE']='1'
    commands=[]
    for script in ['harmonize_crash.py','validate_harmonized_crash.py']:
        command=[sys.executable,str(script_dir/script),'--state',state]
        commands.append(command)
        with (target/(script+'.log')).open('w',encoding='utf8') as log:
            subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    files=[]
    for f in sorted((pipeline/'data/crash'/state).glob('*.csv')):
        canonical=source/'data/crash'/state/f.name
        files.append({'year':int(f.stem.rsplit('_',1)[1]),'replayed_sha256':sha(f),'frozen_final_sha256':sha(canonical)})
        files[-1]['byte_identical']=files[-1]['replayed_sha256']==files[-1]['frozen_final_sha256']
    result={'state':state,'portable_code':a.portable_code,'scope':'prepared source to generic harmonization and validator; acquisition/preparation/overlays not executed','files':files,'commands':commands,'result':'BYTE_IDENTICAL_TO_FINAL' if files and all(x['byte_identical'] for x in files) else 'BASE_DIFFERS_FROM_FINAL_REVIEW_REVISIONS'}
    (target/'replay_report.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
