"""Prefill pending historical CHP files using checked byte ranges, without sharing partial files."""
import download_us_crashes as d
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json,requests,gzip,hashlib,math

def ranged(job):
    path=d.output_path(job);receipt=path.with_name(path.name+'.metadata.json')
    if path.exists() and receipt.exists():return
    # Do not duplicate a main-worker file already being streamed.
    if path.with_name(path.name+'.part').exists():return
    # The portal signs GET redirects, so HEAD is not a usable metadata probe here.
    with requests.get(job['url'],headers={'Range':'bytes=0-0','Accept-Encoding':'identity'},stream=True,timeout=40) as probe:
        probe.raise_for_status()
        content_range=probe.headers.get('Content-Range','')
        if probe.status_code!=206 or '/' not in content_range:raise RuntimeError('Public range probe unavailable')
        total=int(content_range.split('/')[-1]);etag=probe.headers.get('ETag')
    if not total:raise RuntimeError('No checked source length')
    chunks=[];n=4;width=math.ceil(total/n)
    for index in range(n):
        lo=index*width;hi=min(total-1,(index+1)*width-1)
        if lo<=hi:chunks.append((index,lo,hi,path.with_name(path.name+f'.range{index}.part')))
    def segment(part):
        index,lo,hi,target=part
        headers={'Range':f'bytes={lo}-{hi}','Accept-Encoding':'identity'}
        if etag:headers['If-Range']=etag
        with requests.get(job['url'],headers=headers,stream=True,timeout=(30,150)) as r:
            r.raise_for_status()
            if r.status_code!=206 or r.headers.get('Content-Range')!=f'bytes {lo}-{hi}/{total}':
                raise RuntimeError('Range or version was not honoured')
            if etag and r.headers.get('ETag')!=etag:raise RuntimeError('Source ETag changed')
            count=0
            with target.open('wb') as f:
                for block in r.iter_content(1024*1024):
                    d.check_disk();f.write(block);count+=len(block)
            if count!=hi-lo+1:raise RuntimeError('Range length mismatch')
        return target
    with ThreadPoolExecutor(4) as pool:list(pool.map(segment,chunks))
    temp=path.with_name(path.name+'.fast.part');raw_hash=hashlib.sha256();raw_size=0
    with temp.open('wb') as f:
        with gzip.GzipFile(filename='',mode='wb',fileobj=f,compresslevel=3,mtime=0) as g:
            for _,_,_,chunk in chunks:
                with chunk.open('rb') as source:
                    for block in iter(lambda:source.read(4*1024*1024),b''):
                        g.write(block);raw_hash.update(block);raw_size+=len(block)
    if raw_size!=total:raise RuntimeError('Concatenated source size mismatch')
    rows,cols,bad=d.verify_csv(temp)
    # If the normal worker completed meanwhile, retain its already verified copy.
    if path.exists() and receipt.exists():
        temp.unlink()
    else:
        temp.replace(path)
        record={k:v for k,v in job.items() if k!='meta'}
        record.update(status='complete',kind='direct_ranged',path=d.relative(path),access_date=d.CLIENT_DATE,
                      finished_utc=d.stamp(),records=rows,columns=cols,nonstandard_width_rows=bad,
                      downloaded_raw_bytes=total,raw_sha256=raw_hash.hexdigest(),source_etag=etag,
                      stored_bytes=path.stat().st_size,sha256=d.hash_file(path),current_year_partial=False)
        d.atomic_json(receipt,record)
        d.event('done',id=job['id'],path=d.relative(path),records=rows,stored_bytes=record['stored_bytes'],ranged=True)
    for _,_,_,chunk in chunks:
        if chunk.resolve().is_relative_to(d.ROOT.resolve()):chunk.unlink()

jobs=json.loads((d.MANIFEST/'download_plan.json').read_text(encoding='utf-8'))
selected=sorted([j for j in jobs if j['region']=='CA' and isinstance(j.get('year'),int) and j['year']<=2022],key=lambda j:(j['year'],j['name']))
for job in selected:
    try:ranged(job)
    except Exception as exc:d.event('source_failed',region='CA',source=job['name'],error='Range prefill: '+str(exc))
print('CA HISTORICAL PREFILL COMPLETE',flush=True)
