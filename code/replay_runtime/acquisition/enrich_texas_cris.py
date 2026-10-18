"""Build PII-minimized crash-level analytical files from official TxDOT CRIS extracts."""
from __future__ import annotations
import os as _uscrash_paths_os
import argparse,csv,hashlib,json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=(Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/TX')
MOTO={'71','90'}; SPEED={'22','60','61'}; ALCOHOL={'67'}; DRUG={'68'}
KEEP=['Crash_ID','Crash_Date','Crash_Time','Rpt_CRIS_Cnty_ID','Rpt_City_ID','Wthr_Cond_ID','Light_Cond_ID','Surf_Cond_ID','Harm_Evnt_ID','Intrsct_Relat_ID','FHE_Collsn_ID','Road_Relat_ID','Rural_Fl','Rural_Urban_Type_ID','Func_Sys_ID','Crash_Sev_ID','Nbr_Of_Lane','Crash_Speed_Limit','Road_Constr_Zone_Fl','At_Intrsct_Fl','Cmv_Involv_Fl','Schl_Bus_Fl','Sus_Serious_Injry_Cnt','Nonincap_Injry_Cnt','Poss_Injry_Cnt','Tot_Injry_Cnt','Death_Cnt']
DERIVED=['DerivedLatitude','DerivedLongitude','DerivedVehicleCount','DerivedPedestrianCount','DerivedBicyclistCount','DerivedMotorcycleCount','DerivedAlcoholInvolved','DerivedDrugInvolved','DerivedSpeedingInvolved','DerivedHitAndRun','DerivedUrbanRural']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def schemas(year):
 if year<=2022:return ['2018']
 if year==2023:return ['2018','2023']
 if year<=2025:return ['2023']
 return ['2026']
def run(year):
 d=ROOT/str(year)/'CSV'; ss=schemas(year)
 crashes=[d/f'TX_{year}_crash_schema{s}.csv' for s in ss];units=[d/f'TX_{year}_unit_schema{s}.csv' for s in ss]
 agg={};unit_rows=unit_duplicates=0
 for up in units:
  with up.open(encoding='utf-8-sig',newline='') as f:
   for r in csv.DictReader(f):
    unit_rows+=1;k=r['Crash_ID'].strip();un=r['Unit_Nbr'].strip();key=(k,un)
    a=agg.setdefault(k,{'units':set(),'ped':0,'bike':0,'moto':0,'alcohol':False,'drug':False,'speed':False,'hnr':False})
    if un in a['units']:unit_duplicates+=1;continue
    a['units'].add(un);desc=r['Unit_Desc_ID'].strip();body=r['Veh_Body_Styl_ID'].strip()
    a['ped']+=desc=='4';a['bike']+=desc=='3';a['moto']+=body in MOTO;a['hnr']|=r['Veh_HNR_Fl'].strip().upper()=='Y'
    factors={r.get(x,'').strip() for x in ['Contrib_Factr_1_ID','Contrib_Factr_2_ID','Contrib_Factr_3_ID','Contrib_Factr_P1_ID','Contrib_Factr_P2_ID']}
    a['speed']|=bool(factors&SPEED);a['alcohol']|=bool(factors&ALCOHOL);a['drug']|=bool(factors&DRUG)
 out=d/'TX_crash_enriched_safe.csv';meta=d/'TX_crash_enriched_safe.metadata.json';tmp=out.with_suffix('.csv.partial')
 rows=dupes=unit_missing=0;seen=set();mind=maxd=None
 with tmp.open('w',encoding='utf-8-sig',newline='') as dst:
  wr=csv.DictWriter(dst,fieldnames=KEEP+DERIVED,lineterminator='\n');wr.writeheader()
  for cp in crashes:
   with cp.open(encoding='utf-8-sig',newline='') as f:
    rd=csv.DictReader(f);missing=set(KEEP+['Latitude','Longitude','Rpt_Latitude','Rpt_Longitude'])-set(rd.fieldnames or [])
    if missing:raise ValueError(f'{cp}: missing {sorted(missing)}')
    for r in rd:
     k=r['Crash_ID'].strip()
     if k in seen:dupes+=1;continue
     seen.add(k);rows+=1;dt=r['Crash_Date'].strip();mind=dt if mind is None or datetime.strptime(dt,'%m/%d/%Y')<datetime.strptime(mind,'%m/%d/%Y') else mind;maxd=dt if maxd is None or datetime.strptime(dt,'%m/%d/%Y')>datetime.strptime(maxd,'%m/%d/%Y') else maxd
     a=agg.get(k)
     if a is None:unit_missing+=1;a={'units':set(),'ped':0,'bike':0,'moto':0,'alcohol':False,'drug':False,'speed':False,'hnr':False}
     o={x:r[x].strip() for x in KEEP};o['DerivedLatitude']=r['Latitude'].strip() or r['Rpt_Latitude'].strip();o['DerivedLongitude']=r['Longitude'].strip() or r['Rpt_Longitude'].strip();o['DerivedVehicleCount']=len(a['units']) or ''
     for x,key in [('DerivedPedestrianCount','ped'),('DerivedBicyclistCount','bike'),('DerivedMotorcycleCount','moto')]:o[x]=a[key]
     o['DerivedUrbanRural']='RURAL' if r['Rural_Fl'].strip().upper()=='Y' else ('URBAN' if r['Rural_Fl'].strip().upper()=='N' else '')
     for x,key in [('DerivedAlcoholInvolved','alcohol'),('DerivedDrugInvolved','drug'),('DerivedSpeedingInvolved','speed'),('DerivedHitAndRun','hnr')]:o[x]='Y' if a[key] else ('N' if a['units'] else '')
     wr.writerow(o)
 tmp.replace(out)
 m={'year':year,'created_utc':datetime.now(timezone.utc).isoformat(),'schemas':ss,'source_crash_files':[x.name for x in crashes],'source_unit_files':[x.name for x in units],'source_crash_rows_including_duplicates':rows+dupes,'output_rows':rows,'duplicate_crash_ids_excluded':dupes,'source_unit_rows':unit_rows,'duplicate_unit_numbers_excluded':unit_duplicates,'crashes_without_units':unit_missing,'date_min':mind,'date_max':maxd,'pii_policy':'Output whitelist excludes VIN, owner ZIP, names/addresses and Investigator_Narrative. Raw restricted files remain local and must not be published without TxDOT authorization and disclosure review.','source_crash_sha256':{x.name:sha(x) for x in crashes},'source_unit_sha256':{x.name:sha(x) for x in units},'output_sha256':sha(out)}
 meta.write_text(json.dumps(m,indent=2),encoding='utf-8');return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('years',nargs='*',type=int);a=ap.parse_args();print(json.dumps([run(y) for y in (a.years or range(2019,2027))],indent=2))
if __name__=='__main__':main()
