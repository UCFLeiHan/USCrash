"""Reproduce the corrected FL annual files in a fresh isolated output directory.

python code/processing/rebuild_fl_signal4_2017_2019.py --output-root <new-folder>
Original Signal4 files are copied byte-for-byte, never edited. This command does
not promote outputs over the formal release. CODEABLE=N remains in raw inputs.
"""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8388608),b''):h.update(b)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-root',type=Path,default=Path(r'F:\S4ACrashes\Crash_data'))
    ap.add_argument('--output-root',type=Path,required=True)
    a=ap.parse_args();out=a.output_root.resolve()
    if out.exists():ap.error('Use a new, nonexistent output directory to preserve prior results.')
    code=Path(__file__).resolve().parents[1]
    config=json.loads((code/'config/states/FL.json').read_text(encoding='utf-8'))
    versions=[v for v in config['versions'] if v['year_start']<=2019 and v['year_end']>=2017]
    assert len(versions)==1 and versions[0]['schema_id']=='FL_SIGNAL4_2017_2019'
    out.mkdir(parents=True);shutil.copytree(code/'config',out/'Unified_MMUCC6/config')
    manifest=[]
    for y in [2017,2018,2019]:
        src=a.source_root/str(y)/'crash tables'/('event.csv' if y<2019 else 'crash_event.csv')
        dst=out/f'States/FL/{y}/CSV/FL_Signal4_crashes_{y}.csv';dst.parent.mkdir(parents=True)
        shutil.copy2(src,dst);digest=sha(src);assert digest==sha(dst)
        manifest.append(dict(year=y,original=str(src.resolve()),copy=str(dst),sha256=digest))
        for readme in src.parent.parent.glob('*.html'):
            md=dst.parent.parent/'Metadata';md.mkdir(exist_ok=True);shutil.copy2(readme,md/'Signal4_README.html')
    (out/'source_copy_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    env=os.environ.copy();env['USCRASH_ROOT']=str(out);env['USCRASH_SOURCE_ROOT']=str(out/'States')
    subprocess.run([sys.executable,str(code/'processing/harmonize_crash.py'),'--state','FL','--year-start','2017','--year-end','2019'],env=env,check=True)
    subprocess.run([sys.executable,str(code/'processing/validate_harmonized_crash.py'),'--state','FL'],env=env,check=True)

if __name__=='__main__':main()
