import csv,json,pathlib,hashlib
U=pathlib.Path(r'F:\LH_Research\USCrash\Crash\Unified_MMUCC6'); D=U/'data'/'crash'; Q=U/'qa'/'post_harmonization'; canon=[]
with (U/'config'/'canonical_crash_schema.csv').open(encoding='utf-8-sig',newline='') as f:canon=[r['field_name'] for r in csv.DictReader(f)]
states=sorted(p.name for p in D.iterdir() if p.is_dir()); out={}; grand=files=0;bad=[]
for s in states:
 fs=sorted((D/s).glob('*.csv')); partial=list((D/s).glob('*.partial')); annual={}; colsets={}; names=[]
 for f in fs:
  with f.open(encoding='utf-8-sig',newline='') as z:h=next(csv.reader(z));colsets.setdefault(len(h),[]).append(f.name)
  if h!=canon:bad.append([s,f.name,'header_mismatch',len(h)])
 summary=Q/s/'harmonization_summary.csv'; sr=[]
 if summary.exists():
  with summary.open(encoding='utf-8-sig',newline='') as z:sr=list(csv.DictReader(z))
 rows=sum(int(x['output_rows']) for x in sr); grand+=rows;files+=len(fs)
 vr=Q/s/'validation_report.json'; rm=Q/s/'run_manifest.json'; v=json.loads(vr.read_text()) if vr.exists() else {};m=json.loads(rm.read_text()) if rm.exists() else {}
 issues=[]
 if len(sr)!=len(fs):issues.append(f'summary_files={len(sr)} csv_files={len(fs)}')
 if v.get('files')!=len(fs):issues.append(f'validator_files={v.get("files")}')
 if v.get('rows')!=rows:issues.append(f'validator_rows={v.get("rows")} summary_rows={rows}')
 if v.get('result')!='PASS':issues.append(f'validation={v.get("result")}')
 if m.get('schema_sha256')!='972609b90f887171d309cde8f31a66d4050e21a3691064d4cb871c928ec5ebf5':issues.append('schema_hash_bad')
 if partial:issues.append(f'partial={len(partial)}')
 out[s]={'files':len(fs),'rows':rows,'columns':{str(k):len(vv) for k,vv in colsets.items()},'validation':v.get('result'),'validator_issues':v.get('issues'),'audit_issues':issues}
 if issues:bad.append([s,'STATE',';'.join(issues),''])
res={'states':len(states),'files':files,'rows':grand,'canonical_columns':len(canon),'state_results':out,'problems':bad}
p=U/'qa'/'cross_state'/'unified_data_readonly_audit_2026-10-14.json';p.write_text(json.dumps(res,indent=2),encoding='utf-8');print(p);print(states);print('TOTAL',len(states),files,grand,len(canon));print('PROBLEMS',json.dumps(bad,indent=2))
