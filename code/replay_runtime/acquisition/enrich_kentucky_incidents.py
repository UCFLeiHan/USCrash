from __future__ import annotations
import os as _uscrash_paths_os
import argparse,csv,hashlib,json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
ROOT=(Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/KY')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def process(year):
 yd=ROOT/str(year); inc=yd/f'KY_Incident_{year}.csv'; per=yd/f'KY_Person_{year}.csv'; out=yd/f'KY_Incident_enriched_{year}.csv'; meta=yd/f'KY_Incident_enriched_{year}.metadata.json'
 worst={}; person_rows=0
 with per.open(encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f):
   person_rows+=1; iid=r['IncidentID'].strip(); code=r['InjurySeverityCde'].strip()
   if iid and code in {'01','02','03','04','05'}:
    if iid not in worst or int(code)<int(worst[iid]):worst[iid]=code
 counts=Counter(); seen=set(); tmp=out.with_suffix('.csv.partial')
 with inc.open(encoding='utf-8-sig',newline='') as src,tmp.open('w',encoding='utf-8-sig',newline='') as dst:
  rd=csv.DictReader(src); fields=(rd.fieldnames or [])+['DerivedCollisionDateISO','DerivedWorstInjurySeverityCde','DerivedSeverityBasis']
  wr=csv.DictWriter(dst,fieldnames=fields,lineterminator='\n');wr.writeheader()
  for r in rd:
   counts['incident_rows']+=1; iid=r['IncidentID'].strip()
   if iid in seen:counts['duplicate_incident_ids']+=1
   seen.add(iid); code=worst.get(iid,''); basis='PERSON_WORST_INJURY_CODE' if code else ''
   if not code:
    try:k=int(float(r['NumberKilled'] or 0)); injured=int(float(r['NumberInjured'] or 0))
    except ValueError:k=injured=-1
    if k>0:code='01';basis='INCIDENT_FATALITY_COUNT_FALLBACK'
    elif k==0 and injured==0:code='05';basis='INCIDENT_ZERO_KILLED_INJURED_FALLBACK'
    elif injured>0: basis='INJURY_PRESENT_GRADE_UNAVAILABLE'
   r['DerivedCollisionDateISO']=datetime.strptime(r['CollisionDate'].strip(),'%m/%d/%Y %I:%M:%S %p').date().isoformat()
   r['DerivedWorstInjurySeverityCde']=code;r['DerivedSeverityBasis']=basis;counts['severity_'+(code or 'U')]+=1;wr.writerow(r)
 tmp.replace(out)
 m={'created_utc':datetime.now(timezone.utc).isoformat(),'year':year,'incident_rows':counts['incident_rows'],'person_rows':person_rows,'duplicate_incident_ids':counts['duplicate_incident_ids'],'severity_counts':{k.removeprefix('severity_'):v for k,v in counts.items() if k.startswith('severity_')},'incident_sha256':sha(inc),'person_sha256':sha(per),'output_sha256':sha(out),'output':str(out)}
 meta.write_text(json.dumps(m,indent=2),encoding='utf-8');print(json.dumps(m))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--year',type=int,action='append');a=ap.parse_args()
 for y in (a.year or range(2020,2027)):process(y)
if __name__=='__main__':main()
