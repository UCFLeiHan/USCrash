#!/usr/bin/env python3
"""Conservatively enrich Mississippi crashes from ordered vehicle events."""
from __future__ import annotations
import os as _uscrash_paths_os
import argparse,csv,hashlib,json,os
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(_uscrash_paths_os.environ['USCRASH_ROOT']); PIPE=ROOT/'Unified_MMUCC6'; STATE=ROOT/'States'/'MS'; DATA=PIPE/'data'/'crash'/'MS'; QA=PIPE/'qa'/'post_harmonization'/'MS'; XWALK=PIPE/'config'/'enrichment'/'MS_vehicle_event_crosswalk.csv'; PROV='DERIVED_FROM_VEHICLE_EVENTS'

def clean(v): return (v or '').strip()
def sha256(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def load_maps():
 out={}
 with XWALK.open(encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f):
   k=(r['schema_family'],clean(r['source_value']).casefold())
   if k in out: raise RuntimeError(f'duplicate crosswalk key {k}')
   out[k]=r
 return out

def source_spec(year):
 if year<=2018:
  return ('REPORTBEAM',STATE/str(year)/'CSV'/f'MS_ReportBeam_{year}_CrashVehicleTab_{year}.csv','intCrashID',['V20_event_seq1_cd','V20_event_seq2_cd','V20_event_seq3_cd','V20_evnt_seq4_cd'])
 return ('ECRASH',STATE/str(year)/'CSV'/f'MS_Vehicles_{year}.csv','Crash ID',[f'Sequence of Events {i}' for i in range(1,5)])

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--year-start',type=int,default=2004); ap.add_argument('--year-end',type=int,default=2025); a=ap.parse_args()
 maps=load_maps(); QA.mkdir(parents=True,exist_ok=True); annual=[]; conflict_audit=[]; unknown_audit=[]
 for year in range(a.year_start,a.year_end+1):
  family,vpath,idcol,evcols=source_spec(year); cpath=DATA/f'MS_crashes_harmonized_{year}.csv'
  if not vpath.exists() or not cpath.exists(): raise FileNotFoundError(f'missing inputs {vpath} or {cpath}')
  events=defaultdict(list); linked_ids=set(); m=defaultdict(int)
  with vpath.open(encoding='utf-8-sig',newline='') as f:
   reader=csv.DictReader(f)
   for rownum,row in enumerate(reader,1):
    m['vehicle_rows']+=1; cid=clean(row.get(idcol))
    if not cid: m['vehicle_rows_missing_crash_id']+=1; continue
    linked_ids.add(cid); first=''; first_col=''
    for col in evcols:
     val=clean(row.get(col))
     if val and (family,val.casefold()) not in maps:
      m['unmapped_event_values_any_position']+=1; unknown_audit.append({'year':year,'source_file':str(vpath),'source_row_number':rownum,'source_crash_id':cid,'schema_family':family,'event_column':col,'source_value':val,'mapping_status':'UNMAPPED_NOT_USED'})
     if val and not first: first=val; first_col=col
    if not first: m['vehicle_rows_without_event']+=1; continue
    mapped=maps.get((family,first.casefold()))
    if not mapped:
     m['vehicle_rows_unmapped_first_event']+=1; continue
    m['vehicle_rows_mapped_first_event']+=1; events[cid].append(mapped)
  partial=cpath.with_suffix('.csv.enriching'); seen=set()
  with cpath.open(encoding='utf-8-sig',newline='') as src, partial.open('w',encoding='utf-8-sig',newline='') as dst:
   reader=csv.DictReader(src); fields=reader.fieldnames or []; writer=csv.DictWriter(dst,fieldnames=fields,lineterminator='\n'); writer.writeheader()
   required={'source_crash_id','first_harmful_event','first_harmful_event_group','first_harmful_event_raw_code','first_harmful_event_raw_label','first_harmful_event_provenance','collision_partner_group','manner_of_collision_mmucc','manner_raw_code','manner_raw_label','manner_provenance'}
   if required-set(fields): raise RuntimeError(f'MS {year} canonical fields missing {sorted(required-set(fields))}')
   for row in reader:
    m['crash_rows']+=1; cid=clean(row['source_crash_id']); seen.add(cid)
    if clean(row['first_harmful_event_provenance'])==PROV:
     for k in ('first_harmful_event','first_harmful_event_group','first_harmful_event_raw_code','first_harmful_event_raw_label','collision_partner_group'): row[k]=''
     row['first_harmful_event_provenance']='UNAVAILABLE'
    if clean(row['manner_provenance'])==PROV:
     for k in ('manner_of_collision_mmucc','manner_raw_code','manner_raw_label'): row[k]=''
     row['manner_provenance']='UNAVAILABLE'
    if cid not in linked_ids: m['crashes_without_vehicle_link']+=1; writer.writerow(row); continue
    m['crashes_linked_to_vehicles']+=1; mapped_events=events.get(cid,[])
    if not mapped_events: m['linked_crashes_without_usable_event']+=1; writer.writerow(row); continue
    # Consistency is assessed at the full canonical mapping tuple, not by picking one vehicle.
    sigs={(x['first_harmful_event'],x['first_harmful_event_group'],x['collision_partner_group'],x['manner_of_collision_mmucc']) for x in mapped_events}
    raw_values=sorted({x['source_value'] for x in mapped_events}); raw_join=' | '.join(raw_values)
    if len(sigs)==1:
     m['consistent_vehicle_events']+=1; x=mapped_events[0]
     if not clean(row['first_harmful_event']):
      row['first_harmful_event']=x['first_harmful_event']; row['first_harmful_event_group']=x['first_harmful_event_group']; row['first_harmful_event_raw_code']=raw_join; row['first_harmful_event_raw_label']=raw_join; row['first_harmful_event_provenance']=PROV; m['fhe_rows_enriched']+=1
     partner=clean(x['collision_partner_group'])
     if partner and not clean(row['collision_partner_group']): row['collision_partner_group']=partner; m['partner_rows_enriched_consistent']+=1
     manner=clean(x['manner_of_collision_mmucc'])
     if manner and not clean(row['manner_of_collision_mmucc']):
      row['manner_of_collision_mmucc']=manner; row['manner_raw_code']=raw_join; row['manner_raw_label']=raw_join; row['manner_provenance']=PROV; m['manner_rows_enriched']+=1
    else:
     m['conflicting_vehicle_events']+=1; partners={clean(x['collision_partner_group']) for x in mapped_events}
     if len(partners)==1 and '' not in partners:
      partner=next(iter(partners)); applied=False
      if not clean(row['collision_partner_group']): row['collision_partner_group']=partner; applied=True
      m['partner_rows_supported_from_conflict']+=1; conflict_audit.append({'year':year,'source_crash_id':cid,'vehicle_event_values':raw_join,'collision_partner_group':partner,'mapping_status':PROV,'applied_or_already_present':'APPLIED' if applied else 'ALREADY_PRESENT'})
    writer.writerow(row)
  os.replace(partial,cpath); m['vehicle_crash_ids']=len(linked_ids); m['vehicle_crash_ids_not_in_harmonized']=len(linked_ids-seen); m['year']=year; m['output_sha256']=sha256(cpath)
  m['consistent_coverage_pct']=round(100*m['consistent_vehicle_events']/m['crash_rows'],6) if m['crash_rows'] else 0
  denom=m['consistent_vehicle_events']+m['conflicting_vehicle_events']; m['conflict_rate_usable_pct']=round(100*m['conflicting_vehicle_events']/denom,6) if denom else 0
  annual.append(dict(m)); print(f"MS {year}: crashes={m['crash_rows']} consistent={m['consistent_vehicle_events']} conflicts={m['conflicting_vehicle_events']} no_link={m['crashes_without_vehicle_link']}",flush=True)
 numeric=sorted({k for r in annual for k in r if k not in {'year','output_sha256','consistent_coverage_pct','conflict_rate_usable_pct'}}); totals=defaultdict(int)
 for r in annual:
  for k in numeric: totals[k]+=int(r.get(k,0))
 totals['consistent_coverage_pct']=round(100*totals['consistent_vehicle_events']/totals['crash_rows'],6); den=totals['consistent_vehicle_events']+totals['conflicting_vehicle_events']; totals['conflict_rate_usable_pct']=round(100*totals['conflicting_vehicle_events']/den,6) if den else 0
 report={'state':'MS','executed_utc':datetime.now(timezone.utc).isoformat(),'method':'Use each vehicle first nonblank sequence event; enrich FHE/manner only when all mapped vehicle-first events agree at the full reviewed canonical tuple. Conflict cases may populate only a unanimously supported nonblank partner group.','provenance':PROV,'crosswalk':str(XWALK),'crosswalk_sha256':sha256(XWALK),'years':annual,'totals':dict(totals),'result':'PASS'}
 (QA/'vehicle_event_enrichment_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 with (QA/'vehicle_event_enrichment_summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
  fields=['year']+sorted({k for r in annual for k in r if k!='year'}); w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n'); w.writeheader(); w.writerows(annual)
 for name,rows,fields in [('vehicle_event_conflict_partner_audit.csv',conflict_audit,['year','source_crash_id','vehicle_event_values','collision_partner_group','mapping_status','applied_or_already_present']),('vehicle_event_unmapped_audit.csv',unknown_audit,['year','source_file','source_row_number','source_crash_id','schema_family','event_column','source_value','mapping_status'])]:
  with (QA/name).open('w',encoding='utf-8-sig',newline='') as f: w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n'); w.writeheader(); w.writerows(rows)
 print(json.dumps({'state':'MS','totals':dict(totals),'result':'PASS'},indent=2))
if __name__=='__main__': main()
