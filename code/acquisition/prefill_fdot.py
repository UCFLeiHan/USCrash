"""Prefill future FDOT jobs with four independent readonly ID batches, without touching active partial files."""
import download_us_crashes as d
import inspect,json
source=inspect.getsource(d.arc_download).replace('def arc_download(job,path):','def fast_arc_download(job,path):')
source=source.replace("safe(job['name'])+'_'+str(job['year'])", "safe(job['name'])+'_prefill_'+str(job['year'])")
a=source.index('        for offset in range(0,len(object_ids),chunk_size):');b=source.index('\n    missing=',a)
lines=source[a:b].splitlines();body=[line for line in lines[1:] if 'features=obtain(object_ids[' not in line]
replacement='        with ThreadPoolExecutor(4) as batch_pool:\n            chunks=(object_ids[i:i+chunk_size] for i in range(0,len(object_ids),chunk_size))\n            for features in batch_pool.map(obtain,chunks):\n'+'\n'.join('    '+line for line in body)
source=source[:a]+replacement+source[b:];exec(compile(source,'owned_fast_arc_download','exec'),d.__dict__)
jobs=json.loads((d.MANIFEST/'expansion3_plan.json').read_text());selected=sorted([j for j in jobs if j['region']=='FL' and isinstance(j.get('year'),int) and j['year']>=2015],key=lambda j:j['year'],reverse=True)
for job in selected:
    original=d.output_path(job);receipt=original.with_name(original.name+'.metadata.json');active=original.with_name(original.name+'.part')
    if receipt.exists() or active.exists():continue
    candidate=original.with_name('FDOT_SSOGIS_crashes.prefill.csv.gz')
    try:
        work={**job,'id':'prefill_'+job['id']};details=d.fast_arc_download(work,candidate)
        if receipt.exists() or active.exists():
            if candidate.resolve().is_relative_to(d.ROOT.resolve()):candidate.unlink()
            continue
        candidate.replace(original);record={k:v for k,v in job.items() if k!='meta'};record.update(details,status='complete',path=d.relative(original),stored_bytes=original.stat().st_size,sha256=d.hash_file(original),access_date=d.CLIENT_DATE,finished_utc=d.stamp(),current_year_partial=False,readonly_parallel_batches=4)
        d.atomic_json(receipt,record);d.event('done',id=job['id'],path=d.relative(original),records=record['records'],stored_bytes=record['stored_bytes'],prefilled=True)
    except Exception as exc:d.event('source_failed',region='FL',source=job['name']+' '+str(job['year']),error='Readonly prefill: '+str(exc))
print('FDOT FUTURE YEAR PREFILL COMPLETE',flush=True)
