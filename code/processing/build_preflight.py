from __future__ import annotations
import csv, json, re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import importlib.util

CRASH_ROOT=Path(r'F:\LH_Research\USCrash\Crash')
SOURCE=CRASH_ROOT/'States'
OUT=CRASH_ROOT/'Unified_MMUCC6'
MANIFEST=CRASH_ROOT/'manifests/acquisition'/'US_state_data_overview_2026-10-13.csv'
BUILDER=CRASH_ROOT/'code/acquisition'/'build_states_inventory_html.py'

spec=importlib.util.spec_from_file_location('inventory_builder',BUILDER)
b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)

PREF=re.compile(r'(crash(?:es)?|collision|incident|accident|portal|mtcf|dt4000|mapped)',re.I)
SKIP=re.compile(r'(person|vehicle|driver|occupant|pedestrian|unit_|_unit|involved|airbag)',re.I)
EXTS={'.csv','.tsv','.txt','.xlsx'}

def candidates(ydir:Path):
 out=[]
 if not ydir.exists(): return out
 for p in ydir.rglob('*'):
  if not p.is_file() or p.suffix.lower() not in EXTS or p.stat().st_size==0: continue
  low=str(p).lower()
  if any(x in low for x in ('\\raw\\','/raw/','daily_zips','_daily_download','date_fragments')): continue
  score=0
  if PREF.search(p.name) and not SKIP.search(p.name): score+=1000
  elif not SKIP.search(p.name): score+=100
  score+=min(p.stat().st_size//1_000_000,99)
  out.append((score,p))
 return sorted(out,key=lambda x:(x[0],x[1].stat().st_size),reverse=True)

def header(path:Path):
 return b.sniff_header(path)

def norm(value):
 return re.sub(r'[^a-z0-9]+','_',str(value).strip().lower()).strip('_')

FALLBACK_PATTERNS={
 'crash_id':[r'^crash_id$',r'^crashid$',r'^crash.*(?:number|no|num)$',r'^(?:case|report|incident).*(?:id|number|no|num)$',r'^ser_no$',r'^agy_st_no$'],
 'crash_datetime':[r'^(?:crash|accident|collision|incident).*(?:datetime|date_time)$',r'^crashdatetime$'],
 'crash_date':[r'^(?:crash|accident|collision|incident)_?(?:dt|date)$',r'^date_of_crash$',r'^crash_dt$'],
 'crash_time':[r'^(?:crash|accident|collision|incident)_?(?:tm|time)$',r'^crash_hr.*$'],
 'latitude':[r'^lat(?:itude)?(?:_dd|_wgs84)?$',r'.*_latitude$'],
 'longitude':[r'^(?:lon|lng|long|longitude)(?:_dd|_wgs84)?$',r'.*_longitude$'],
 'severity':[r'.*(?:crash|collision|accident).*(?:severity|svrt).*',r'^severity$',r'^highest_inj.*$',r'^max_injury.*$'],
 'manner_collision':[r'.*(?:manner|collision|collis).*(?:type|typ).*',r'^manner_of_collision$',r'^collis_typ$'],
}

def match_fields(headers):
 mp=b.match_canonical(headers)
 normalized=[(h,norm(h)) for h in headers]
 for key,patterns in FALLBACK_PATTERNS.items():
  if mp.get(key): continue
  for original,n in normalized:
   if any(re.match(p,n) for p in patterns):
    mp[key]=original; break
 return mp

rows=[]; inventory=[]
with MANIFEST.open(encoding='utf-8-sig',newline='') as f:
 overview=list(csv.DictReader(f))
for rec in overview:
 st=rec['缩写']; stated=[] if rec['年份明细']=='无' else rec['年份明细'].split(',')
 if rec['有数据']!='有':
  rows.append({'state':st,'year':'','source_status':'NO_LOCAL_DATA','primary_file':'','bytes':'','columns':'','duplicate_headers':'','crash_id':'','crash_datetime':'','crash_date':'','crash_time':'','latitude':'','longitude':'','severity':'','manner_collision':'','preflight_status':'NOT_APPLICABLE','issues':rec['备注']})
  continue
 for y in stated:
  ydir=SOURCE/st/y; cands=candidates(ydir); issues=[]
  if not ydir.exists():
   rows.append({'state':st,'year':y,'source_status':'MISSING_YEAR_DIRECTORY','primary_file':'','bytes':'','columns':'','duplicate_headers':'','crash_id':'','crash_datetime':'','crash_date':'','crash_time':'','latitude':'','longitude':'','severity':'','manner_collision':'','preflight_status':'FAIL','issues':'manifest year directory missing'})
   continue
  if not cands:
   rawfiles=[p for p in ydir.rglob('*') if p.is_file() and p.stat().st_size>0]
   status='RAW_ONLY' if rawfiles else 'EMPTY_YEAR_DIRECTORY'
   rows.append({'state':st,'year':y,'source_status':status,'primary_file':'','bytes':'','columns':'','duplicate_headers':'','crash_id':'','crash_datetime':'','crash_date':'','crash_time':'','latitude':'','longitude':'','severity':'','manner_collision':'','preflight_status':'WARN' if rawfiles else 'FAIL','issues':'no standardized readable table; extraction required' if rawfiles else 'no source files'})
   continue
  p=cands[0][1]; h=header(p); counts=Counter(x for x in h if x); dups=[x for x,n in counts.items() if n>1]; mp=match_fields(h)
  if not h: issues.append('header unreadable')
  if dups: issues.append('duplicate headers: '+'|'.join(dups[:10]))
  if not mp.get('crash_id'): issues.append('crash identifier not mapped')
  if not (mp.get('crash_datetime') or mp.get('crash_date') or mp.get('crash_time')): issues.append('crash date/time not mapped')
  if not (mp.get('latitude') and mp.get('longitude')): issues.append('coordinate pair not mapped')
  if not mp.get('severity'): issues.append('severity not mapped in crash table')
  if not mp.get('manner_collision'): issues.append('manner not mapped in crash table')
  critical=not h or not mp.get('crash_id') or not (mp.get('crash_datetime') or mp.get('crash_date') or mp.get('crash_time'))
  status='FAIL' if critical else ('WARN' if issues else 'PASS')
  rel=str(p.relative_to(SOURCE)).replace('\\','/')
  rows.append({'state':st,'year':y,'source_status':'STANDARDIZED_TABLE','primary_file':rel,'bytes':p.stat().st_size,'columns':len(h),'duplicate_headers':'|'.join(dups),'crash_id':mp.get('crash_id') or '','crash_datetime':mp.get('crash_datetime') or '','crash_date':mp.get('crash_date') or '','crash_time':mp.get('crash_time') or '','latitude':mp.get('latitude') or '','longitude':mp.get('longitude') or '','severity':mp.get('severity') or '','manner_collision':mp.get('manner_collision') or '','preflight_status':status,'issues':'; '.join(issues)})
  inventory.append({'state':st,'year':y,'role':'crash_primary_candidate','source_path':str(p),'relative_path':rel,'bytes':p.stat().st_size,'modified_utc':datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat(),'sha256':'PENDING_ROW_LEVEL_VALIDATION','read_only_source':True})

fields=list(rows[0])
with (OUT/'qa'/'preflight'/'state_year_preflight.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
with (OUT/'manifests'/'source_file_inventory.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(inventory[0]));w.writeheader();w.writerows(inventory)
summary=[]
for st in b.US:
 rr=[r for r in rows if r['state']==st]
 summary.append({'state':st,'years_expected':sum(bool(r['year']) for r in rr),'pass':sum(r['preflight_status']=='PASS' for r in rr),'warn':sum(r['preflight_status']=='WARN' for r in rr),'fail':sum(r['preflight_status']=='FAIL' for r in rr),'not_applicable':sum(r['preflight_status']=='NOT_APPLICABLE' for r in rr),'ready_for_mapping':all(r['preflight_status'] in {'PASS','WARN','NOT_APPLICABLE'} for r in rr) and any(r['preflight_status'] in {'PASS','WARN'} for r in rr)})
with (OUT/'qa'/'preflight'/'state_preflight_summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
counts=Counter(r['preflight_status'] for r in rows)
print(json.dumps({'state_year_rows':len(rows),'primary_candidates':len(inventory),'status_counts':counts,'states_ready':sum(x['ready_for_mapping'] for x in summary)},default=dict,indent=2))
