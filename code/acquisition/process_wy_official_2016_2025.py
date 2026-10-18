from __future__ import annotations
import csv, json, shutil, hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(r"F:\LH_Research\USCrash\Crash\States\WY")
YEARS=range(2016,2026)
SOURCES={
 'crash':ROOT/'Crash Level Variables Report - 2016-2025.csv',
 'vehicle':ROOT/'Vehicle Level Variables Report - 2016-2025.csv',
 'involved':ROOT/'Involved Level Variables Report - 2016-2025.csv',
}

def unique_header(header):
    seen=Counter(); out=[]
    for raw in header:
        name=raw.strip().lstrip('\ufeff')
        seen[name]+=1
        out.append(name if seen[name]==1 else f'{name}_{seen[name]}')
    return out

def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
    return h.hexdigest()

for y in YEARS:
    (ROOT/str(y)).mkdir(parents=True,exist_ok=True)

# Pass 1: crash table supplies authoritative crash-to-year mapping.
outputs={}; writers={}; handles={}
for y in YEARS:
    p=ROOT/str(y)/f'WY_crash_{y}.csv'
    handles[y]=p.open('w',encoding='utf-8-sig',newline='')
    outputs[('crash',y)]=p
crash_year={}; crash_counts=Counter(); duplicate_ids=Counter(); coord_valid=Counter(); datetime_present=Counter(); bad_date=0
with SOURCES['crash'].open('r',encoding='utf-8-sig',newline='') as f:
    rd=csv.reader(f); header=unique_header(next(rd)); idx={n:i for i,n in enumerate(header)}
    out_header=header[:1]+['CRASH_YEAR']+header[1:]
    for y in YEARS:
        writers[y]=csv.writer(handles[y]); writers[y].writerow(out_header)
    for row in rd:
        if len(row)<len(header): row += ['']*(len(header)-len(row))
        cid=row[idx['INTCRASHID']].strip(); ds=row[idx['DATCRASHDATE']].strip()
        try: y=int(datetime.strptime(ds,'%m/%d/%Y').year)
        except Exception: bad_date+=1; continue
        if y not in YEARS: continue
        if cid in crash_year: duplicate_ids[y]+=1
        crash_year[cid]=y; crash_counts[y]+=1
        lat=row[idx['DECSYSTEMLATITUDE']].strip(); lon=row[idx['DECSYSTEMLONGITUDE']].strip()
        try:
            if 40<=float(lat)<=46 and -112<=float(lon)<=-104: coord_valid[y]+=1
        except Exception: pass
        if ds and row[idx['INTMILITARYCRASHTIME']].strip(): datetime_present[y]+=1
        writers[y].writerow(row[:1]+[y]+row[1:])
for h in handles.values(): h.close()

stats={'crash':{},'vehicle':{},'involved':{}}
for y in YEARS:
    stats['crash'][str(y)]={'rows':crash_counts[y],'duplicate_INTCRASHID':duplicate_ids[y],
      'valid_WY_coordinates':coord_valid[y],'date_and_time_present':datetime_present[y],
      'file':outputs[('crash',y)].name,'sha256':sha256(outputs[('crash',y)])}

# Pass 2: split child tables using INTCRASHID and track referential integrity.
for kind in ('vehicle','involved'):
    handles={}; writers={}; counts=Counter(); orphan=0; orphan_samples=[]
    for y in YEARS:
        p=ROOT/str(y)/f'WY_{kind}_{y}.csv'; outputs[(kind,y)]=p
        handles[y]=p.open('w',encoding='utf-8-sig',newline='')
    with SOURCES[kind].open('r',encoding='utf-8-sig',newline='') as f:
        rd=csv.reader(f); header=unique_header(next(rd)); id_idx=header.index('INTCRASHID')
        out_header=header[:1]+['CRASH_YEAR']+header[1:]
        for y in YEARS:
            writers[y]=csv.writer(handles[y]); writers[y].writerow(out_header)
        for row in rd:
            if len(row)<len(header): row += ['']*(len(header)-len(row))
            cid=row[id_idx].strip(); y=crash_year.get(cid)
            if y is None:
                orphan+=1
                if len(orphan_samples)<10: orphan_samples.append(cid)
                continue
            counts[y]+=1; writers[y].writerow(row[:1]+[y]+row[1:])
    for h in handles.values(): h.close()
    for y in YEARS:
        stats[kind][str(y)]={'rows':counts[y],'file':outputs[(kind,y)].name,'sha256':sha256(outputs[(kind,y)])}
    stats[kind]['orphan_rows_not_written']=orphan
    stats[kind]['orphan_samples']=orphan_samples

# Per-year QA files.
for y in YEARS:
    qa={'state':'Wyoming','abbreviation':'WY','year':y,
        'source':'Official Wyoming crash data supplied by researcher',
        'processed_utc':datetime.now(timezone.utc).isoformat(),
        'relationships':'INTCRASHID joins crash, vehicle, and involved tables',
        'tables':{k:stats[k][str(y)] for k in ('crash','vehicle','involved')}}
    (ROOT/str(y)/'qa_summary.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')

inventory={'state':'Wyoming','abbreviation':'WY','coverage':'2016-2025','record_level':True,
 'source_files':[p.name for p in SOURCES.values()], 'bad_or_out_of_range_crash_dates':bad_date,
 'tables':stats,'processed_utc':datetime.now(timezone.utc).isoformat()}
(ROOT/'WY_2016_2025_inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')

# Preserve untouched source files and group documentation after successful conversion.
raw=ROOT/'Raw'; docs=ROOT/'Documentation'; raw.mkdir(exist_ok=True); docs.mkdir(exist_ok=True)
for p in SOURCES.values(): shutil.move(str(p),raw/p.name)
for p in list(ROOT.glob('*.pdf')):
    shutil.move(str(p),docs/p.name)

print(json.dumps({str(y):{k:stats[k][str(y)]['rows'] for k in ('crash','vehicle','involved')}|{
 'valid_coords':stats['crash'][str(y)]['valid_WY_coordinates'],
 'date_time':stats['crash'][str(y)]['date_and_time_present']} for y in YEARS},indent=2))
print('orphans',stats['vehicle']['orphan_rows_not_written'],stats['involved']['orphan_rows_not_written'])
