"""Attach PennDOT's official crash-level FLAGS table to annual CRASH rows."""
from __future__ import annotations
import argparse, csv, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(r"F:\LH_Research\USCrash\Crash\States\PA")
FLAG_FIELDS=['ALCOHOL_RELATED','DRUG_RELATED','SPEEDING_RELATED','HIT_RUN','PEDESTRIAN','BICYCLE','MOTORCYCLE','COMM_VEHICLE','SCHOOL_BUS_RELATED']

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()

def run(year):
 folder=ROOT/str(year)/'CSV';crash=folder/f'CRASH_{year}.csv';flags=folder/f'FLAGS_{year}.csv'
 output=folder/f'CRASH_enriched_{year}.csv';manifest=folder/f'CRASH_enriched_{year}.metadata.json'
 by_id={};flag_rows=duplicates=0
 with flags.open(encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f);missing=set(['CRN',*FLAG_FIELDS])-set(reader.fieldnames or [])
  if missing:raise ValueError(f'{flags}: missing {sorted(missing)}')
  for row in reader:
   flag_rows+=1;key=row['CRN'].strip()
   if key in by_id:duplicates+=1
   else:by_id[key]={x:row[x].strip() for x in FLAG_FIELDS}
 if duplicates:raise RuntimeError(f'{year}: {duplicates} duplicate FLAGS CRN rows')
 rows=matched=0;crash_ids=set();tmp=output.with_suffix('.csv.partial')
 with crash.open(encoding='utf-8-sig',newline='') as src,tmp.open('w',encoding='utf-8-sig',newline='') as dst:
  reader=csv.DictReader(src);out_fields=(reader.fieldnames or [])+[f'FLAG_{x}' for x in FLAG_FIELDS]
  writer=csv.DictWriter(dst,fieldnames=out_fields,lineterminator='\n');writer.writeheader()
  for row in reader:
   rows+=1;key=row['CRN'].strip();crash_ids.add(key);detail=by_id.get(key)
   if detail:matched+=1
   for x in FLAG_FIELDS:row[f'FLAG_{x}']=detail[x] if detail else ''
   writer.writerow(row)
 tmp.replace(output)
 meta={'year':year,'created_utc':datetime.now(timezone.utc).isoformat(),'join_key':'CRN exact','crash_rows':rows,'flag_rows':flag_rows,'matched_crash_rows':matched,'unmatched_crash_rows':rows-matched,'unmatched_flag_ids':len(set(by_id)-crash_ids),'duplicate_flag_ids':duplicates,'crash_sha256':sha(crash),'flags_sha256':sha(flags),'output_sha256':sha(output),'output_rows':rows,'fields':[f'FLAG_{x}' for x in FLAG_FIELDS]}
 manifest.write_text(json.dumps(meta,indent=2),encoding='utf-8');return meta

def main():
 ap=argparse.ArgumentParser();ap.add_argument('years',nargs='*',type=int);a=ap.parse_args()
 print(json.dumps([run(y) for y in (a.years or range(2006,2026))],indent=2))
if __name__=='__main__':main()
