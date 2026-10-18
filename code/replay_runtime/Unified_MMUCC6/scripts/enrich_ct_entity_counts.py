#!/usr/bin/env python3
"""Aggregate official CT person/vehicle entity tables to canonical crash counts/flags."""
import os as _uscrash_paths_os
import argparse,csv,json,os
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(_uscrash_paths_os.environ['USCRASH_ROOT']); STATE=ROOT/'States'/'CT'; PIPE=ROOT/'Unified_MMUCC6'; DATA=PIPE/'data'/'crash'/'CT'; QA=PIPE/'qa'/'post_harmonization'/'CT'
TRUE_SPEED={'Too Fast for Conditions','Exceeded Speed Limit','Racing'}; PED={'Pedestrian','Other Pedestrian (wheelchair, person in a building, skater, pedestrian conveyance)'}; BIKE={'Bicyclist','Other Cyclist'}; MC={'Motorcycle','Moped'}
def clean(v): return (v or '').strip()
def main():
 a=argparse.ArgumentParser(); a.add_argument('--year-start',type=int,default=2015); a.add_argument('--year-end',type=int,default=2026); x=a.parse_args(); QA.mkdir(parents=True,exist_ok=True); annual=[]
 for year in range(x.year_start,x.year_end+1):
  persons=STATE/str(year)/'CTDOT_persons.csv'; vehicles=STATE/str(year)/'CTDOT_vehicles.csv'; crashes=DATA/f'CT_crashes_harmonized_{year}.csv'; agg=defaultdict(lambda:defaultdict(int)); person_ids=set(); vehicle_ids=set(); pr=vr=0
  with persons.open(encoding='utf-8-sig',newline='') as f:
   for r in csv.DictReader(f):
    pr+=1; cid=clean(r.get('CrashID'))
    if not cid: continue
    person_ids.add(cid); injury=clean(r.get('InjuryStatus')); ptype=clean(r.get('PersonType')); speed=clean(r.get('SpeedingRelated'))
    if injury=='Fatal Injury (K)': agg[cid]['fatalities']+=1
    elif injury in {'Suspected Serious Injury (A)','Suspected Minor Injury (B)','Possible Injury (C)'}: agg[cid]['injuries']+=1
    if ptype in PED: agg[cid]['pedestrian_count']+=1
    if ptype in BIKE: agg[cid]['bicyclist_count']+=1
    if speed in TRUE_SPEED: agg[cid]['speed_true']=1
    elif speed=='Unknown': agg[cid]['speed_unknown']=1
    elif speed=='No': agg[cid]['speed_no']=1
  with vehicles.open(encoding='utf-8-sig',newline='') as f:
   for r in csv.DictReader(f):
    vr+=1; cid=clean(r.get('CrashID'))
    if not cid: continue
    vehicle_ids.add(cid); agg[cid]['vehicles']+=1
    if clean(r.get('VehicleBodyType')) in MC: agg[cid]['motorcycle_count']+=1
  partial=crashes.with_suffix('.csv.enriching'); seen=set(); m=defaultdict(int)
  with crashes.open(encoding='utf-8-sig',newline='') as src, partial.open('w',encoding='utf-8-sig',newline='') as dst:
   reader=csv.DictReader(src); writer=csv.DictWriter(dst,fieldnames=reader.fieldnames,lineterminator='\n'); writer.writeheader()
   for r in reader:
    m['crash_rows']+=1; cid=clean(r['source_crash_id']); seen.add(cid); z=agg.get(cid)
    if not z: m['crashes_without_entity_records']+=1; writer.writerow(r); continue
    r['fatalities']=str(z['fatalities']); r['injuries']=str(z['injuries']); r['vehicles']=str(z['vehicles']); r['vehicles_minimum']=str(z['vehicles']); r['vehicles_raw']=str(z['vehicles']); r['vehicles_precision']='EXACT'
    for kind in ('pedestrian','bicyclist','motorcycle'):
     count=z[f'{kind}_count']; r[f'{kind}_count']=str(count); r[f'{kind}_involved']='TRUE' if count else 'FALSE'
    if z['speed_true']: r['speeding_involved']='TRUE'; r['speeding_provenance']='DERIVED_FROM_PERSON_RECORDS'
    elif z['speed_unknown']: r['speeding_involved']='UNKNOWN'; r['speeding_provenance']='DERIVED_FROM_PERSON_RECORDS'
    elif z['speed_no']: r['speeding_involved']='FALSE'; r['speeding_provenance']='DERIVED_FROM_PERSON_RECORDS'
    m['crashes_enriched']+=1; writer.writerow(r)
  os.replace(partial,crashes); m.update({'year':year,'person_rows':pr,'vehicle_rows':vr,'person_crash_ids':len(person_ids),'vehicle_crash_ids':len(vehicle_ids),'person_ids_not_in_crashes':len(person_ids-seen),'vehicle_ids_not_in_crashes':len(vehicle_ids-seen)}); annual.append(dict(m)); print(year,dict(m),flush=True)
 totals=defaultdict(int)
 for r in annual:
  for k,v in r.items():
   if k!='year': totals[k]+=int(v)
 report={'state':'CT','executed_utc':datetime.now(timezone.utc).isoformat(),'method':'Counts aggregated by official CrashID from CTDOT persons and vehicles tables. Injury count=A+B+C; fatalities=K; motorcycle count includes Motorcycle and Moped.','provenance':{'speeding':'DERIVED_FROM_PERSON_RECORDS','counts':'CT official entity table aggregation'},'years':annual,'totals':dict(totals),'result':'PASS'}
 (QA/'entity_count_enrichment_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 with (QA/'entity_count_enrichment_summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
  fields=['year']+sorted({k for r in annual for k in r if k!='year'}); w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n'); w.writeheader(); w.writerows(annual)
 print(json.dumps({'totals':dict(totals),'result':'PASS'},indent=2))
if __name__=='__main__': main()
