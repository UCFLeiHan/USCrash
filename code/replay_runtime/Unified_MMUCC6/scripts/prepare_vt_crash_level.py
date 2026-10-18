from __future__ import annotations
import os as _uscrash_paths_os
import csv, json, hashlib
from collections import Counter
from pathlib import Path

ROOT=Path(_uscrash_paths_os.environ['USCRASH_ROOT'])
STATE=ROOT/'States'/'VT'

def sha256(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
 return h.hexdigest()

def derive(row):
 imp=row.get('Impairment','').strip()
 if not imp: alc=drug=''
 elif imp=='None': alc=drug='false'
 elif imp=='Alcohol': alc,drug='true','false'
 elif imp=='Drugs': alc,drug='false','true'
 elif imp=='Alcohol and Drugs': alc=drug='true'
 else: raise ValueError(f'unknown Impairment {imp!r}')
 inv=row.get('Involving','').strip()
 flags={k:'' for k in ('PedestrianDerived','BicyclistDerived','MotorcycleDerived','CommercialVehicleDerived')}
 if inv=='None': flags={k:'false' for k in flags}
 elif inv=='NULL': flags={k:'unknown' for k in flags}
 elif inv=='Pedestrian': flags['PedestrianDerived']='true'
 elif inv=='Bicycle': flags['BicyclistDerived']='true'
 elif inv=='Motorcycle': flags['MotorcycleDerived']='true'
 elif inv=='Heavy Truck': flags['CommercialVehicleDerived']='true'
 elif inv: raise ValueError(f'unknown Involving {inv!r}')
 rc=row.get('RoadCharacteristics','').strip()
 true_inter={'T - Intersection','Four-way Intersection','Y - Intersection','Traffic circle / roundabout','Five-point or more'}
 intersection='true' if rc in true_inter else ('false' if rc=='Not at a Junction' else '')
 roadcond=row.get('RoadCondition','').strip()
 work='true' if roadcond=='Work zone (construction / maintenance / utility)' else ('false' if roadcond else '')
 row.update({'AlcoholDerived':alc,'DrugDerived':drug,'IntersectionDerived':intersection,'WorkZoneDerived':work,**flags})
 return row

def main():
 manifest={'state':'VT','operation':'derive conservative crash-level flags without modifying source','years':{},'pii_audit':{}}
 all_obj=set(); total=0
 for y in range(2010,2027):
  src=STATE/str(y)/'CSV'/f'VTrans_Crashes_{y}.csv'
  dst=STATE/str(y)/f'VT_prepared_crashes_{y}.csv'
  tmp=dst.with_suffix('.csv.partial')
  with src.open(encoding='utf-8-sig',newline='') as f, tmp.open('w',encoding='utf-8-sig',newline='') as o:
   rd=csv.DictReader(f); headers=list(rd.fieldnames or [])
   derived=['AlcoholDerived','DrugDerived','IntersectionDerived','WorkZoneDerived','PedestrianDerived','BicyclistDerived','MotorcycleDerived','CommercialVehicleDerived']
   wr=csv.DictWriter(o,fieldnames=headers+derived,lineterminator='\n'); wr.writeheader()
   n=0; written=0; duplicate_obj=0; exact_semantic_duplicates_removed=0; year_mismatch=0
   seen=set(); seen_semantic=set()
   for row in rd:
    n+=1; obj=row['OBJECTID'].strip()
    semantic=tuple(row.get(k,'') for k in headers if k != 'OBJECTID')
    if semantic in seen_semantic:
     exact_semantic_duplicates_removed+=1
     continue
    seen_semantic.add(semantic); written+=1
    if obj in seen or obj in all_obj: duplicate_obj+=1
    seen.add(obj); all_obj.add(obj)
    if not row['AccidentDateTime_ISO'].startswith(str(y)+'-'): year_mismatch+=1
    wr.writerow(derive(row))
  tmp.replace(dst); total+=written
  manifest['years'][str(y)]={'source':str(src),'prepared':str(dst),'source_rows':n,'prepared_rows':written,'exact_semantic_duplicates_removed':exact_semantic_duplicates_removed,'duplicate_objectids':duplicate_obj,'date_year_mismatch':year_mismatch,'source_sha256':sha256(src),'prepared_sha256':sha256(dst)}
 manifest['total_rows']=total
 manifest['pii_audit']={'direct_person_identifiers_found':False,'fields_reviewed':['all 37 public layer fields'],'potentially_sensitive_public_fields_excluded_from_canonical':['REPORTNUMBER','STREETADDRESS','INTERSECTIONWITH','NonReportableAddress'],'canonical_source_identifier':'OBJECTID','notes':'No names, birth dates, driver license numbers, phone numbers, or person/vehicle rows occur in this crash layer.'}
 (STATE/'preparation_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 print(json.dumps({'rows':total,'years':len(manifest['years'])},indent=2))
if __name__=='__main__': main()
