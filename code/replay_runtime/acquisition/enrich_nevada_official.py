"""Build one auditable crash-level Nevada table from official Crash/Person/Vehicle CSVs."""
from __future__ import annotations
import os as _uscrash_paths_os
import argparse, csv, hashlib, json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = (Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/NV')
SEVERITY_RANK = {"K": 0, "A": 1, "B": 2, "C": 3, "O": 4, "U": 5, "N": 6, "": 7}

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
    return h.hexdigest()

def flag(values, predicate):
    values=[(v or '').strip() for v in values]
    if any(predicate(v) for v in values): return 'TRUE'
    if not values: return ''
    if any(v.upper() in {'UNKNOWN','U'} for v in values): return 'UNKNOWN'
    return 'FALSE'

def enrich(year):
    folder=ROOT/str(year)/'CSV'
    crash=folder/f'NV_Official_Crash_{year}.csv'
    person=folder/f'NV_Official_Person_{year}.csv'
    vehicle=folder/f'NV_Official_Vehicle_{year}.csv'
    output=folder/f'NV_Official_Crash_enriched_{year}.csv'
    metadata=folder/f'NV_Official_Crash_enriched_{year}.metadata.json'

    people=defaultdict(lambda: defaultdict(list)); person_rows=0
    with person.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            person_rows+=1; key=r['CrashNum'].strip()
            for field in ('PersonType','AlcDrugInvolved'): people[key][field].append(r[field])
    vehicles=defaultdict(lambda: defaultdict(list)); vehicle_rows=0
    with vehicle.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            vehicle_rows+=1; key=r['CrashNum'].strip()
            for field in ('VehType','Commercial','Factors','SpeedLimit'): vehicles[key][field].append(r[field])

    by_id=defaultdict(list); crash_rows=0
    with crash.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f); source_fields=reader.fieldnames or []
        for i,r in enumerate(reader): crash_rows+=1; by_id[r['CrashNum'].strip()].append((i,r))
    extra=['NV_BicyclistInvolved','NV_BicyclistCount','NV_DrugInvolved','NV_CommercialVehicleInvolved','NV_CommercialVehicleCount','NV_MotorcycleDerived','NV_SpeedingInvolved','NV_PostedSpeedLimit']
    duplicate_keys=conflicting_duplicate_keys=0
    tmp=output.with_suffix('.csv.partial')
    with tmp.open('w',encoding='utf-8-sig',newline='') as dst:
        writer=csv.DictWriter(dst,fieldnames=source_fields+extra,lineterminator='\n');writer.writeheader()
        for key, candidates in by_id.items():
            if len(candidates)>1:
                duplicate_keys+=1
                if any(r != candidates[0][1] for _,r in candidates[1:]): conflicting_duplicate_keys+=1
            # Preserve the most severe record; then prefer the most complete row and source order.
            _,row=min(candidates,key=lambda ir:(SEVERITY_RANK.get(ir[1]['CrashSeverity'].strip(),8),-sum(bool(v.strip()) for v in ir[1].values()),ir[0]))
            p=people.get(key,{}); v=vehicles.get(key,{})
            ptypes=p.get('PersonType',[]); alcdrug=p.get('AlcDrugInvolved',[]); vtypes=v.get('VehType',[])
            bike=[x for x in ptypes if x.strip().casefold() in {'pedal cyclist','e-bike','other cyclist'}]
            commercial=[x for x in v.get('Commercial',[]) if x.strip().upper()=='YES']
            row['NV_BicyclistInvolved']='TRUE' if bike else ('FALSE' if ptypes else '')
            row['NV_BicyclistCount']=str(len(bike)) if ptypes else ''
            row['NV_DrugInvolved']=flag(alcdrug,lambda x:'DRUG' in x.upper() or 'MARIJUANA' in x.upper())
            row['NV_CommercialVehicleInvolved']='TRUE' if commercial else ('FALSE' if vtypes else '')
            row['NV_CommercialVehicleCount']=str(len(commercial)) if vtypes else ''
            row['NV_MotorcycleDerived']=flag(vtypes,lambda x:any(t in x.upper() for t in ('MOTORCYCLE','MOTORBIKE','MOPED')))
            factors=v.get('Factors',[])
            row['NV_SpeedingInvolved']='TRUE' if any('TOO FAST FOR CONDITIONS' in x.upper() for x in factors) else ('FALSE' if factors else '')
            speeds=set()
            for x in v.get('SpeedLimit',[]):
                try:
                    n=int(float(x));
                    if 1 <= n <= 85: speeds.add(n)
                except ValueError: pass
            row['NV_PostedSpeedLimit']=str(next(iter(speeds))) if len(speeds)==1 else ''
            writer.writerow(row)
    tmp.replace(output)
    crash_ids=set(by_id); person_ids=set(people); vehicle_ids=set(vehicles)
    meta={'year':year,'created_utc':datetime.now(timezone.utc).isoformat(),'selection_policy':'one row per CrashNum; most severe, then most complete, then source order','crash_source_rows':crash_rows,'unique_crashes':len(crash_ids),'duplicate_crashnum_keys':duplicate_keys,'conflicting_duplicate_crashnum_keys':conflicting_duplicate_keys,'person_rows':person_rows,'vehicle_rows':vehicle_rows,'crashes_without_person_rows':len(crash_ids-person_ids),'crashes_without_vehicle_rows':len(crash_ids-vehicle_ids),'unmatched_person_crash_ids':len(person_ids-crash_ids),'unmatched_vehicle_crash_ids':len(vehicle_ids-crash_ids),'inputs_sha256':{p.name:sha(p) for p in (crash,person,vehicle)},'output_sha256':sha(output),'output_rows':len(crash_ids)}
    metadata.write_text(json.dumps(meta,indent=2),encoding='utf-8'); return meta

def main():
    ap=argparse.ArgumentParser();ap.add_argument('years',nargs='*',type=int);a=ap.parse_args()
    print(json.dumps([enrich(y) for y in (a.years or range(2020,2025))],indent=2))
if __name__=='__main__':main()
