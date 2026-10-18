from __future__ import annotations
import csv,json,hashlib
from pathlib import Path
ROOT=Path(r'F:\LH_Research\USCrash\Crash');PIPE=ROOT/'Unified_MMUCC6'
annual=json.loads((PIPE/'qa'/'cross_state'/'all_42_state_annual_integrity_audit.json').read_text())
with (PIPE/'config'/'canonical_crash_schema.csv').open(encoding='utf-8-sig',newline='') as f:canonical=[r['field_name'] for r in csv.DictReader(f)]
pii_tokens=('person_name','first_name','last_name','full_name','date_of_birth','birth_date','driver_license','street_address','home_address','phone','email','narrative','vin','license_plate')
pii_columns=[c for c in canonical if any(t in c.casefold() for t in pii_tokens)]
no_data={
 'HI':{'status':'NO_HARMONIZABLE_STATEWIDE_DATA','detail':'No local statewide crash-level files or verified unrestricted bulk source.'},
 'IN':{'status':'NO_HARMONIZABLE_STATEWIDE_DATA','detail':'No local statewide crash-level files or verified unrestricted bulk source.'},
 'LA':{'status':'NO_HARMONIZABLE_STATEWIDE_DATA','detail':'No local statewide crash-level files or verified unrestricted bulk source.'},
 'MD':{'status':'LOCAL_PARTIAL_NOT_HARMONIZED','detail':'Official 2024-2026 crash-level map exports exist locally, but the current package lacks per-crash time and has not passed the formal MMUCC harmonization workflow.'},
 'ND':{'status':'ACCESS_REQUEST_REQUIRED','detail':'No unrestricted statewide bulk endpoint verified; detailed records require research/public-records access and state law restricts general crash-list copying.'},
 'NH':{'status':'ACCESS_REQUEST_REQUIRED','detail':'Statewide detailed VISION records exist but no unrestricted bulk endpoint was verified.'},
 'RI':{'status':'APPLICATION_REQUIRED','detail':'No local data; a request draft exists but submission/fulfillment is unconfirmed.'},
 'SC':{'status':'PAID_CUSTOM_REQUEST_REQUIRED','detail':'Full statewide crash/unit/occupant tables qualify by content but require a paid/custom SCDPS request; public ArcGIS is only a subset.'},
 'WV':{'status':'APPLICATION_PENDING_NO_LOCAL_DATA','detail':'Request was reported as submitted; no statewide crash-level package is present locally.'}
}
report={'title':'Final 42-state MMUCC harmonized crash integrity audit','generated_from':'formal state configs, annual summaries, run manifests, validation reports, and output CSV headers','canonical_schema_columns':len(canonical),'canonical_schema_sha256':hashlib.sha256((PIPE/'config'/'canonical_crash_schema.csv').read_bytes()).hexdigest(),'pii_columns_detected':pii_columns,'data_states':{},'states_without_formal_harmonized_data':no_data}
flat=[];total=0;issues=[]
for s in sorted(annual['states']):
 a=annual['states'][s];qa=PIPE/'qa'/'post_harmonization'/s
 val=json.loads((qa/'validation_report.json').read_text());man=json.loads((qa/'run_manifest.json').read_text())
 unique_ok=int(val.get('unique_crash_uids',-1))==int(val.get('rows',-2))
 state_issues=list(a['issues'])
 if not unique_ok:state_issues.append('DUPLICATE_OR_MISSING_UNIQUE_UID_COUNT')
 if pii_columns:state_issues.append('PII_COLUMN_PRESENT')
 item={'expected_years':a['expected_years'],'year_count':a['expected_year_count'],'rows':int(val['rows']),'annual_files':int(val['files']),'all_outputs_exact_77_column_schema':not a['header_mismatch_years'],'schema_sha256':man.get('schema_sha256'),'summary_source_output_closed':not a['summary_closure_bad_years'],'summary_rows':a['summary_output_rows'],'validation_result':val.get('result'),'validation_rows':val.get('rows'),'validation_unique_crash_uids':val.get('unique_crash_uids'),'unique_crash_uids_equal_rows':unique_ok,'validation_issues':val.get('issues',{}),'pii_columns':pii_columns,'issues':state_issues,'result':'PASS' if not state_issues else 'FAIL'}
 report['data_states'][s]=item;total+=item['rows']
 if state_issues:issues.append(s)
 flat.append({'state':s,'status':'HARMONIZED','years':item['year_count'],'year_start':min(item['expected_years']),'year_end':max(item['expected_years']),'rows':item['rows'],'columns':77 if item['all_outputs_exact_77_column_schema'] else 'MIXED','schema_hash_ok':item['schema_sha256']==report['canonical_schema_sha256'],'summary_closed':item['summary_source_output_closed'],'validation':item['validation_result'],'validation_rows_match':item['validation_rows']==item['summary_rows'],'unique_uid':item['unique_crash_uids_equal_rows'],'pii_columns':';'.join(pii_columns),'issues':';'.join(state_issues)})
for s,x in no_data.items():flat.append({'state':s,'status':x['status'],'years':0,'year_start':'','year_end':'','rows':0,'columns':'','schema_hash_ok':'','summary_closed':'','validation':'','validation_rows_match':'','unique_uid':'','pii_columns':'','issues':''})
report['data_state_count']=len(report['data_states']);report['no_formal_data_state_count']=len(no_data);report['total_harmonized_records']=total;report['result']='PASS' if not issues and annual['result']=='PASS' and len(canonical)==77 and not pii_columns else 'FAIL';report['problem_states']=issues
out=PIPE/'qa'/'cross_state';out.mkdir(parents=True,exist_ok=True)
(out/'final_42_state_integrity_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
with (out/'final_42_state_integrity_audit.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=flat[0].keys(),lineterminator='\n');w.writeheader();w.writerows(flat)
print(json.dumps({'result':report['result'],'data_states':report['data_state_count'],'no_data_states':report['no_formal_data_state_count'],'total_records':total,'problem_states':issues,'pii_columns':pii_columns,'no_data':no_data},indent=2))
