"""Verify archived bytes against this release; never regenerate or alter data."""
import argparse,csv,hashlib,json
from datetime import datetime,timezone
from pathlib import Path

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--scope',choices=['final','code','all'],default='final')
    p.add_argument('--sample',type=int,help='Explicit smoke test only, not full-scope verification')
    a=p.parse_args();release=Path(__file__).resolve().parents[1]
    rows=list(csv.DictReader((release.parent/'manifests/file_manifest.csv').open(encoding='utf-8-sig')))
    roles={'final':{'canonical'},'code':{'processing_code','acquisition_code','configuration','entrypoint_or_documentation','documentation'}}
    selected=[r for r in rows if a.scope=='all' or r['role'] in roles[a.scope]]
    if a.sample is not None:
        if a.sample<1:p.error('--sample must be positive')
        selected=selected[:a.sample]
    bad=[]
    for i,r in enumerate(selected,1):
        f=a.root/r['path']
        if not f.is_file() or f.stat().st_size!=int(r['size_bytes']) or sha(f)!=r['sha256']:bad.append(r['path'])
        if i%25==0:print(f'Verified {i}/{len(selected)}',flush=True)
    result={'checked_utc':datetime.now(timezone.utc).isoformat(),'scope':a.scope,'sample_only':a.sample is not None,'files_checked':len(selected),'mismatches':bad,'result':'PASS' if not bad else 'FAIL'}
    out=release.parent/'verification/verification_runs';out.mkdir(exist_ok=True)
    (out/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')).write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2))
    if bad:raise SystemExit(2)

if __name__=='__main__':main()
