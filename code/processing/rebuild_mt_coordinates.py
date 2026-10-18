"""Stage, validate, compare and promote MT coordinates. Raw sources are read-only.

Run audit_xy_coordinates.py first. Promotion permits changes to only the three
coordinate columns and retains all prior canonical CSVs and QA in the revision.
"""
import csv, json, shutil, importlib.util, sys, hashlib, os
from pathlib import Path

U=(Path(__file__).resolve().parents[2] / 'Unified_MMUCC6');ROOT=U.parent
REV=U/'qa/coordinate_revision_2026-10-14';WORK=REV/'staged';PIPE=WORK/'Unified_MMUCC6'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if __name__=='__main__':
 audit=REV/'xy_coordinate_audit.csv'
 if not audit.exists():raise RuntimeError('Run the independent XY audit first.')
 shutil.copytree(U/'config',PIPE/'config',dirs_exist_ok=True)
 for stage in ['profile_state_codes','harmonize_crash','validate_harmonized_crash']:
  path=U/'scripts'/f'{stage}.py';spec=importlib.util.spec_from_file_location(stage,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  if stage=='validate_harmonized_crash':m.DATA_ROOT=WORK;m.ROOT=PIPE
  else:m.ROOT=WORK;m.PIPE=PIPE;m.STATES=ROOT/'States'
  sys.argv=[str(path),'--state','MT']
  try:m.main()
  except SystemExit as e:
   if e.code not in (None,0):raise
 report=[];allowed={'latitude','longitude','coordinate_status'}
 for new in sorted((PIPE/'data/crash/MT').glob('*.csv')):
  old=REV/'before/MT'/new.name
  with old.open(encoding='utf-8-sig',newline='') as f,new.open(encoding='utf-8-sig',newline='') as g:
   a=csv.DictReader(f);b=csv.DictReader(g);assert a.fieldnames==b.fieldnames
   n=valid=changed=0
   from itertools import zip_longest
   for left,right in zip_longest(a,b):
    assert left is not None and right is not None,'Row count changed'
    differences={k for k in left if left[k]!=right[k]}
    assert differences<=allowed,(new.name,left['crash_uid'],differences)
    n+=1;changed+=bool(differences);valid+=right['coordinate_status']=='VALID'
   report.append(dict(file=new.name,rows=n,valid_coordinates=valid,changed_rows=changed,before_sha256=digest(old),after_sha256=digest(new)))
 assert sum(r['rows'] for r in report)==219482
 assert sum(r['valid_coordinates'] for r in report)==sum(int(r['valid_bounds']) for r in csv.DictReader(audit.open(encoding='utf-8-sig')) if r['state']=='MT')
 # Verify every original prepared source remained byte-identical.
 inputs=json.loads((REV/'source_hashes.json').read_text())
 for r in inputs:assert digest(Path(r['file']))==r['sha256'],r['file']
 qa=U/'qa/post_harmonization/MT';qa.mkdir(parents=True,exist_ok=True)
 for row in report:
  src=PIPE/'data/crash/MT'/row['file'];dest=U/'data/crash/MT'/row['file'];tmp=dest.with_suffix('.csv.partial');shutil.copy2(src,tmp);tmp.replace(dest)
 shutil.copytree(PIPE/'qa/post_harmonization/MT',qa,dirs_exist_ok=True)
 # The run was staged but the promoted bytes and source hashes are identical.
 summary=qa/'harmonization_summary.csv'
 with summary.open(encoding='utf-8-sig',newline='') as f: reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
 for r in rows:r['output_file']=str(U/'data/crash/MT'/Path(r['output_file']).name)
 with summary.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
 shutil.copytree(PIPE/'qa/preflight/code_profiles/MT',U/'qa/preflight/code_profiles/MT',dirs_exist_ok=True)
 data=dict(result='PASS',allowed_changed_columns=sorted(allowed),all_other_cells_identical=True,raw_source_hashes_unchanged=True,rows=sum(r['rows'] for r in report),valid_coordinates=sum(r['valid_coordinates'] for r in report),files=report)
 (REV/'mt_promotion_verification.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
 print(json.dumps(data),flush=True)
