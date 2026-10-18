from __future__ import annotations
import os as _uscrash_paths_os
import argparse,csv,hashlib,json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=(Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/MT')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def flag(value):return 'Yes' if value else 'No'
def process(y):
 yd=ROOT/str(y); crash=yd/'MDT_Crash.csv'; person=yd/'MDT_Person.csv'; vehicle=yd/'MDT_Vehicle.csv'; out=yd/'MDT_Crash_enriched.csv';meta=yd/'MDT_Crash_enriched.metadata.json'
 p=defaultdict(lambda:{'fatal':0,'injury':0,'ped':0,'bike':0,'alcohol_yes':False,'alcohol_unknown':False,'drug_yes':False,'drug_unknown':False})
 pr=0
 with person.open(encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f):
   pr+=1;i=r['Crash ID'].strip();a=p[i];sev=r['Occupant Injury Severity'].strip();detail=r['Person Type Details'].strip().upper()
   if sev=='Fatal Injury':a['fatal']+=1
   elif sev in {'Suspected Serious Injury','Suspected Minor Injury','Possible Injury'}:a['injury']+=1
   if 'PEDESTRIAN' in detail:a['ped']+=1
   if 'BICYCLIST' in detail or 'CYCLIST' in detail:a['bike']+=1
   al=r['Law Enforcement Suspected Alcohol Use'].strip();dr=r['Law Enforcement Suspected Drug Use'].strip()
   a['alcohol_yes']|=al=='Yes';a['alcohol_unknown']|=al=='Unknown';a['drug_yes']|=dr=='Yes';a['drug_unknown']|=dr=='Unknown'
 v=defaultdict(lambda:{'count':0,'hit_yes':False,'hit_unknown':False,'moto':False,'commercial':False,'schoolbus':False});vr=0
 with vehicle.open(encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f):
   vr+=1;i=r['Crash ID'].strip();a=v[i];a['count']+=1;hit=r['Hit and Run'].strip();body=r['Motor Vehicle Body Type Category'].strip();gvw=r['GVW Rating'].strip()
   a['hit_yes']|=hit.startswith('Yes');a['hit_unknown']|=hit=='Unknown';a['moto']|=body in {'Motorcycle','Moped'};a['schoolbus']|=body=='School Bus';a['commercial']|=gvw in {'10001-26000 Lbs (4536-11793 Kg)','More Than 26000 Lbs (11793 Kg)'} or body=='Medium / Heavy Trucks (More Than 10000 Lbs (4536 Kg))'
 fields_extra=['DerivedFatalities','DerivedInjuries','DerivedVehicleCount','DerivedAlcoholInvolved','DerivedDrugInvolved','DerivedHitAndRun','DerivedPedestrianCount','DerivedBicyclistCount','DerivedMotorcycleInvolved','DerivedCommercialVehicleInvolved','DerivedSchoolBusRelated']
 rows=0;seen=set();dup=0;tmp=out.with_suffix('.csv.partial')
 with crash.open(encoding='utf-8-sig',newline='') as src,tmp.open('w',encoding='utf-8-sig',newline='') as dst:
  rd=csv.DictReader(src);wr=csv.DictWriter(dst,fieldnames=(rd.fieldnames or [])+fields_extra,lineterminator='\n');wr.writeheader()
  for r in rd:
   rows+=1;i=r['Crash ID'].strip();dup+=i in seen;seen.add(i);pa=p[i];va=v[i]
   r.update({'DerivedFatalities':pa['fatal'],'DerivedInjuries':pa['injury'],'DerivedVehicleCount':va['count'],'DerivedAlcoholInvolved':'Yes' if pa['alcohol_yes'] else ('Unknown' if pa['alcohol_unknown'] else 'No'),'DerivedDrugInvolved':'Yes' if pa['drug_yes'] else ('Unknown' if pa['drug_unknown'] else 'No'),'DerivedHitAndRun':'Yes' if va['hit_yes'] else ('Unknown' if va['hit_unknown'] else 'No'),'DerivedPedestrianCount':pa['ped'],'DerivedBicyclistCount':pa['bike'],'DerivedMotorcycleInvolved':flag(va['moto']),'DerivedCommercialVehicleInvolved':flag(va['commercial']),'DerivedSchoolBusRelated':flag(va['schoolbus'])});wr.writerow(r)
 tmp.replace(out);m={'created_utc':datetime.now(timezone.utc).isoformat(),'year':y,'crash_rows':rows,'person_rows':pr,'vehicle_rows':vr,'duplicate_crash_ids':dup,'source_sha256':{'crash':sha(crash),'person':sha(person),'vehicle':sha(vehicle)},'output_sha256':sha(out)};meta.write_text(json.dumps(m,indent=2),encoding='utf-8');print(json.dumps(m))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--year',type=int,action='append');a=ap.parse_args()
 for y in (a.year or range(2016,2026)):process(y)
if __name__=='__main__':main()
