from __future__ import annotations
import csv,json,hashlib,sys
from collections import Counter
from pathlib import Path
ROOT=Path(r'F:\LH_Research\USCrash\Crash\Unified_MMUCC6')
STATES=['PA','OH','NJ','SD','TN','UT','VA','VT','WA','TX']
NO_DATA={'RI':'NO_DATA_APPLICATION_REQUIRED','SC':'NO_DATA_APPLICATION_REQUIRED'}
EXPECTED='972609b90f887171d309cde8f31a66d4050e21a3691064d4cb871c928ec5ebf5'
PII_TOKENS=('person_name','first_name','last_name','full_name','date_of_birth','birth_date','driver_license','street_address','home_address','phone','email','narrative','vin','license_plate')

def sha256(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()

def main():
 schema=ROOT/'config'/'canonical_crash_schema.csv'
 with schema.open(encoding='utf-8-sig',newline='') as f: canonical=[r['field_name'] for r in csv.DictReader(f)]
 schema_hash=sha256(schema); report={'scope':STATES,'expected_schema_sha256':EXPECTED,'actual_schema_sha256':schema_hash,'states':{},'overall_result':'PASS'}
 outrows=[]
 for s in STATES:
  print('AUDIT',s,flush=True)
  qa=ROOT/'qa'/'post_harmonization'/s; data=ROOT/'data'/'crash'/s
  man=json.loads((qa/'run_manifest.json').read_text(encoding='utf-8'))
  val=json.loads((qa/'validation_report.json').read_text(encoding='utf-8'))
  with (qa/'harmonization_summary.csv').open(encoding='utf-8-sig',newline='') as f: sums=list(csv.DictReader(f))
  closure=[];source_rows=output_rows=duplicates=excluded=0
  for x in sums:
   sr=int(x['source_rows']);oo=int(x['output_rows']);dd=int(x.get('duplicate_source_rows') or 0);ee=int(x.get('excluded_source_rows') or 0)
   source_rows+=sr;output_rows+=oo;duplicates+=dd;excluded+=ee
   if sr-dd-ee!=oo:closure.append({'year':x['year'],'source_rows':sr,'duplicates':dd,'excluded':ee,'output_rows':oo})
  files=sorted(data.glob(f'{s}_crashes_harmonized_*.csv'))
  coverage_fields=['crash_date','crash_time','latitude','severity_kabco','manner_of_collision_mmucc','first_harmful_event','weather','light_condition','road_surface_condition']
  coverage=Counter(); coordinate=Counter()
  header_issues=[];rows=0;sev=Counter();prov=Counter();missing_to_u=0;missing_non_u=0;unavailable_to_u=0;blank_sev=0;uid=set();dupuid=0
  for p in files:
   with p.open(encoding='utf-8-sig',newline='') as f:
    rd=csv.DictReader(f)
    if rd.fieldnames!=canonical: header_issues.append({'file':str(p),'columns':len(rd.fieldnames or []),'exact_order_match':False})
    for r in rd:
     rows+=1
     for k in coverage_fields: coverage[k]+=bool(r[k].strip())
     coordinate[r['coordinate_status']]+=1
     sv=r['severity_kabco'];sp=r['severity_provenance'];sev[sv]+=1;prov[sp]+=1
     if sp=='SOURCE_MISSING':
      if sv=='U':missing_to_u+=1
      else:missing_non_u+=1
     if sp=='UNAVAILABLE' and sv=='U':unavailable_to_u+=1
     if not sv:blank_sev+=1
     u=r['crash_uid']
     if u in uid:dupuid+=1
     uid.add(u)
  pii=[x for x in canonical if any(t in x.casefold() for t in PII_TOKENS)]
  observed=rows-prov.get('SOURCE_MISSING',0)-prov.get('UNAVAILABLE',0)-prov.get('UNRESOLVED_CODE',0)
  issues=[]
  if man.get('schema_sha256')!=EXPECTED or schema_hash!=EXPECTED:issues.append('SCHEMA_HASH_MISMATCH')
  if man.get('result')!='PASS':issues.append('RUN_MANIFEST_NOT_PASS')
  if val.get('result')!='PASS':issues.append('VALIDATION_NOT_PASS')
  if closure:issues.append('SOURCE_OUTPUT_NOT_CLOSED')
  if header_issues:issues.append('CANONICAL_HEADER_MISMATCH')
  if rows!=output_rows or rows!=val.get('rows'):issues.append('ROW_TOTAL_MISMATCH')
  if dupuid:issues.append('DUPLICATE_CRASH_UID')
  if pii:issues.append('PII_COLUMN_PRESENT')
  item={'years':len(files),'rows':rows,'schema_hash':man.get('schema_sha256'),'all_files_exact_77_column_schema':not header_issues,'run_manifest_result':man.get('result'),'validation_result':val.get('result'),'validation_issues':val.get('issues',{}),'source_rows':source_rows,'duplicate_source_rows':duplicates,'excluded_source_rows':excluded,'output_rows':output_rows,'source_output_closure':not closure,'duplicate_crash_uids':dupuid,'pii_columns':pii,'field_coverage':{k:{'count':coverage[k],'percent':round(100*coverage[k]/rows,4) if rows else None} for k in coverage_fields},'coordinate_status':dict(coordinate),'severity_counts':dict(sev),'severity_provenance_counts':dict(prov),'source_observed_severity_rows':observed,'source_observed_severity_percent':round(100*observed/rows,4) if rows else None,'source_missing_severity_rows':prov.get('SOURCE_MISSING',0),'source_missing_mapped_to_U_rows':missing_to_u,'source_missing_other_severity_rows':missing_non_u,'source_unavailable_mapped_to_U_rows':unavailable_to_u,'blank_canonical_severity_rows':blank_sev,'issues':issues}
  report['states'][s]=item
  if issues:report['overall_result']='FAIL'
  outrows.append({'state':s,'years':len(files),'rows':rows,'schema_77_exact':not header_issues,'validation':val.get('result'),'closure':not closure,'pii_columns':';'.join(pii),'observed_severity_rows':observed,'observed_severity_pct':item['source_observed_severity_percent'],'source_missing_rows':prov.get('SOURCE_MISSING',0),'source_missing_mapped_U':missing_to_u,'source_unavailable_mapped_U':unavailable_to_u,'blank_severity':blank_sev,'issues':';'.join(issues)})
 report['no_data_states']={k:{'status':v,'harmonized_files_created':False} for k,v in NO_DATA.items()}
 report['scope_accounting']={'data_states':len(STATES),'no_data_application_states':len(NO_DATA),'total_enumerated_states':len(STATES)+len(NO_DATA),'note':'The explicitly enumerated scope contains 10 states with harmonized data plus RI and SC as application-required statuses; no placeholder data files were created.'}
 outdir=ROOT/'qa'/'cross_state';outdir.mkdir(parents=True,exist_ok=True)
 (outdir/'final_consistency_audit_10_data_2_application_states.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 with (outdir/'final_consistency_audit_10_data_2_application_states.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=outrows[0].keys(),lineterminator='\n');w.writeheader();w.writerows(outrows)
 print(json.dumps({'result':report['overall_result'],'summary':outrows},indent=2),flush=True)
if __name__=='__main__':main()
