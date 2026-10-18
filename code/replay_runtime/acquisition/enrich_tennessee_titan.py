"""Create reproducible crash-level Tennessee TITAN enrichments from linked official tables."""
from __future__ import annotations
import os as _uscrash_paths_os
import argparse,csv,hashlib,json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=(Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/TN')
MOTORCYCLE_BODY={'80','81','82','83'}

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def yn(v):
 v=v.strip().upper()
 return 'Y' if v=='Y' else ('N' if v=='N' else '')
def run(year):
 d=ROOT/str(year)/'CSV'; coll=d/'TITAN_vwCollision.csv'; unit=d/'TITAN_vwUnit.csv'; person=d/'TITAN_vwPerson.csv'
 out=d/'TITAN_vwCollision_enriched.csv'; meta=d/'TITAN_vwCollision_enriched.metadata.json'
 agg=defaultdict(lambda:{'surface':set(),'speed':set(),'lanes':set(),'motorcycle':0})
 unit_rows=0
 with unit.open(encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f):
   unit_rows+=1;k=r['MstrRecNbrTxt'].strip();a=agg[k]
   v=r['SurfCondCde'].strip();
   if v:a['surface'].add(v)
   v=r['PostedSpeedNmb'].strip()
   if v and v.lstrip('+-').isdigit() and 0<=int(v)<=99:a['speed'].add(str(int(v)))
   v=r['TravelLanesCde'].strip()
   if v and v.isdigit() and 0<int(v)<=20:a['lanes'].add(str(int(v)))
   if r['BodyCde'].strip() in MOTORCYCLE_BODY:a['motorcycle']+=1
 people=defaultdict(lambda:{'ped':0,'bike':0});person_rows=0
 with person.open(encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f):
   person_rows+=1;k=r['MstrRecNbrTxt'].strip();t=r['PersonTypeCde'].strip()
   if t in {'05','12'}:people[k]['ped']+=1
   elif t in {'06','07'}:people[k]['bike']+=1
 appended=['DerivedSurfaceConditionCde','DerivedPostedSpeedNmb','DerivedNumberOfLanes','DerivedMotorcycleCount','DerivedPedestrianCount','DerivedBicyclistCount','DerivedWorkZoneRelated','DerivedSchoolBusRelated','DerivedSpeedingRelated']
 rows=unit_missing=person_missing=surface_conflict=speed_conflict=lanes_conflict=0;tmp=out.with_suffix('.csv.partial')
 with coll.open(encoding='utf-8-sig',newline='') as src,tmp.open('w',encoding='utf-8-sig',newline='') as dst:
  rd=csv.DictReader(src);wr=csv.DictWriter(dst,fieldnames=(rd.fieldnames or [])+appended,lineterminator='\n');wr.writeheader()
  for r in rd:
   rows+=1;k=r['MstrRecNbrTxt'].strip();a=agg.get(k);q=people.get(k)
   if a is None: unit_missing+=1;a={'surface':set(),'speed':set(),'lanes':set(),'motorcycle':0}
   if q is None:person_missing+=1;q={'ped':0,'bike':0}
   surface_conflict+=len(a['surface'])>1;speed_conflict+=len(a['speed'])>1;lanes_conflict+=len(a['lanes'])>1
   r['DerivedSurfaceConditionCde']=next(iter(a['surface'])) if len(a['surface'])==1 else ''
   r['DerivedPostedSpeedNmb']=next(iter(a['speed'])) if len(a['speed'])==1 else ''
   r['DerivedNumberOfLanes']=next(iter(a['lanes'])) if len(a['lanes'])==1 else ''
   r['DerivedMotorcycleCount']=a['motorcycle'];r['DerivedPedestrianCount']=q['ped'];r['DerivedBicyclistCount']=q['bike']
   wz=r['WorkZoneTypeCde'].strip();r['DerivedWorkZoneRelated']='N' if wz=='01' else ('Y' if wz in {'02','03','04','05'} else '')
   sb=r['SchoolBusCde'].strip();r['DerivedSchoolBusRelated']='N' if sb in {'00','N'} else ('Y' if sb in {'01','02','80'} else '')
   sp=r['SpeedInd'].strip();r['DerivedSpeedingRelated']=yn(sp)
   wr.writerow(r)
 tmp.replace(out)
 m={'year':year,'created_utc':datetime.now(timezone.utc).isoformat(),'collision_rows':rows,'output_rows':rows,'unit_rows':unit_rows,'person_rows':person_rows,'collisions_without_unit':unit_missing,'collisions_without_pedestrian_or_bicyclist':person_missing,'surface_conflicts_blank':surface_conflict,'speed_conflicts_blank':speed_conflict,'lane_conflicts_blank':lanes_conflict,'collision_sha256':sha(coll),'unit_sha256':sha(unit),'person_sha256':sha(person),'output_sha256':sha(out),'derivation':'Unit values are emitted only when all nonblank units agree; conflicting values remain blank. PersonType codes 05/12 count pedestrians, 06/07 count bicyclists/other cyclists. Motorcycle body codes 80-83 are counted. Work-zone, school-bus, and speeding flags use reviewed official code definitions; blank/unrecognized values remain blank.'}
 meta.write_text(json.dumps(m,indent=2),encoding='utf-8');return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('years',nargs='*',type=int);a=ap.parse_args();print(json.dumps([run(y) for y in (a.years or range(2016,2027))],indent=2))
if __name__=='__main__':main()
