#!/usr/bin/env python3
"""Conservatively enrich Idaho crash tables from official crash-unit MHE records.

A crash-level MHE/manner is populated only when all nonblank unit-level
Most_Harmful_Event values for that Serial_Number agree.  When values conflict,
only collision_partner_group may be populated, and only when every distinct
value maps to the same nonblank partner group.  Existing non-derived values are
never overwritten.
"""
from __future__ import annotations
import os as _uscrash_paths_os
import argparse, csv, hashlib, json, os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(_uscrash_paths_os.environ['USCRASH_ROOT'])
PIPE = ROOT / "Unified_MMUCC6"
STATE = ROOT / "States" / "ID"
DATA = PIPE / "data" / "crash" / "ID"
XWALK = PIPE / "config" / "enrichment" / "ID_unit_mhe_crosswalk.csv"
QA = PIPE / "qa" / "post_harmonization" / "ID"
PROVENANCE = "DERIVED_FROM_UNIT_MHE"


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def clean(value: str | None) -> str:
    return (value or "").strip()


def load_crosswalk():
    maps={}
    with XWALK.open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            key=clean(row['source_label']).casefold()
            if not key or key in maps: raise RuntimeError(f"invalid/duplicate crosswalk label {row['source_label']!r}")
            maps[key]=row
    return maps


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--year-start',type=int,default=2005)
    ap.add_argument('--year-end',type=int,default=2023)
    args=ap.parse_args()
    maps=load_crosswalk(); QA.mkdir(parents=True,exist_ok=True)
    annual=[]; conflict_partner_audit=[]
    for year in range(args.year_start,args.year_end+1):
        unit_path=STATE/str(year)/f'idaho_crash_units_{year}.csv'
        crash_path=DATA/f'ID_crashes_harmonized_{year}.csv'
        if not unit_path.exists() or not crash_path.exists():
            raise FileNotFoundError(f"missing inputs for {year}: {unit_path}, {crash_path}")
        labels_by_crash=defaultdict(set); unit_rows=blank_mhe=0
        with unit_path.open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                unit_rows+=1; cid=clean(row.get('Serial_Number')); label=clean(row.get('Most_Harmful_Event'))
                if label.casefold() in {'null', 'none', 'not reported', 'unknown'}: label=''
                if not cid: continue
                labels_by_crash[cid]  # retain linkage even if every MHE is blank
                if label: labels_by_crash[cid].add(label)
                else: blank_mhe+=1
        unknown=sorted({lab for labs in labels_by_crash.values() for lab in labs if lab.casefold() not in maps})
        if unknown: raise RuntimeError(f"ID {year}: unmapped Most_Harmful_Event values: {unknown}")
        partial=crash_path.with_suffix('.csv.enriching')
        metrics=defaultdict(int); seen=set()
        with crash_path.open(encoding='utf-8-sig',newline='') as src, partial.open('w',encoding='utf-8-sig',newline='') as dst:
            reader=csv.DictReader(src); fields=reader.fieldnames or []
            required={'source_crash_id','manner_of_collision_mmucc','manner_raw_code','manner_raw_label','manner_provenance','first_harmful_event','first_harmful_event_group','first_harmful_event_raw_code','first_harmful_event_raw_label','first_harmful_event_provenance','collision_partner_group'}
            missing=required-set(fields)
            if missing: raise RuntimeError(f"ID {year}: missing canonical fields {sorted(missing)}")
            writer=csv.DictWriter(dst,fieldnames=fields,lineterminator='\n'); writer.writeheader()
            for row in reader:
                metrics['crash_rows']+=1; cid=clean(row['source_crash_id']); seen.add(cid)
                # Reset values created by a prior run so reruns and crosswalk revisions are deterministic.
                if clean(row['first_harmful_event_provenance'])==PROVENANCE:
                    for key in ('first_harmful_event','first_harmful_event_group','first_harmful_event_raw_code','first_harmful_event_raw_label','collision_partner_group'): row[key]=''
                    row['first_harmful_event_provenance']='UNAVAILABLE'
                if clean(row['manner_provenance'])==PROVENANCE:
                    for key in ('manner_of_collision_mmucc','manner_raw_code','manner_raw_label','manner_provenance'): row[key]=''
                if cid not in labels_by_crash:
                    metrics['crashes_without_unit_link']+=1; writer.writerow(row); continue
                metrics['crashes_linked_to_units']+=1; labels=labels_by_crash[cid]
                if not labels:
                    metrics['linked_all_mhe_blank']+=1; writer.writerow(row); continue
                if len(labels)==1:
                    metrics['consistent_nonblank_mhe']+=1
                    label=next(iter(labels)); m=maps[label.casefold()]
                    # Only fill empty values or refresh values created by this same enrichment.
                    fhe_refresh=clean(row['first_harmful_event_provenance'])==PROVENANCE
                    manner_refresh=clean(row['manner_provenance'])==PROVENANCE
                    if not clean(row['first_harmful_event']) or fhe_refresh:
                        row['first_harmful_event']=m['first_harmful_event']; row['first_harmful_event_group']=m['first_harmful_event_group']
                        row['first_harmful_event_raw_code']=label; row['first_harmful_event_raw_label']=label
                        row['first_harmful_event_provenance']=PROVENANCE; metrics['fhe_rows_enriched']+=1
                    partner=clean(m['collision_partner_group'])
                    if partner and (not clean(row['collision_partner_group']) or fhe_refresh):
                        row['collision_partner_group']=partner; metrics['partner_rows_enriched_consistent']+=1
                    manner=clean(m['manner_of_collision_mmucc'])
                    if manner and (not clean(row['manner_of_collision_mmucc']) or manner_refresh):
                        row['manner_of_collision_mmucc']=manner; row['manner_raw_code']=label; row['manner_raw_label']=label
                        row['manner_provenance']=PROVENANCE; metrics['manner_rows_enriched']+=1
                else:
                    metrics['conflicting_nonblank_mhe']+=1
                    mapped=[maps[x.casefold()] for x in labels]
                    partners={clean(x['collision_partner_group']) for x in mapped}
                    if len(partners)==1 and '' not in partners:
                        partner=next(iter(partners)); applied=False
                        if not clean(row['collision_partner_group']):
                            row['collision_partner_group']=partner; applied=True
                        elif clean(row['collision_partner_group']) != partner:
                            metrics['conflict_partner_not_applied_due_existing']+=1
                        metrics['partner_rows_supported_from_conflict']+=1
                        conflict_partner_audit.append({'year':year,'source_crash_id':cid,'unit_mhe_labels':' | '.join(sorted(labels)),'collision_partner_group':partner,'mapping_status':PROVENANCE,'applied_or_already_present':'APPLIED' if applied else ('ALREADY_PRESENT' if clean(row['collision_partner_group'])==partner else 'NOT_APPLIED_EXISTING_CONFLICT')})
                writer.writerow(row)
        unmatched_units=len(set(labels_by_crash)-seen)
        os.replace(partial,crash_path)
        metrics.update({'year':year,'unit_rows':unit_rows,'unit_rows_blank_mhe':blank_mhe,'unit_crash_ids':len(labels_by_crash),'unit_crash_ids_not_in_harmonized':unmatched_units,'output_sha256':sha256(crash_path)})
        metrics['consistent_coverage_pct']=round(100*metrics['consistent_nonblank_mhe']/metrics['crash_rows'],6) if metrics['crash_rows'] else 0
        metrics['conflict_rate_linked_nonblank_pct']=round(100*metrics['conflicting_nonblank_mhe']/(metrics['consistent_nonblank_mhe']+metrics['conflicting_nonblank_mhe']),6) if metrics['consistent_nonblank_mhe']+metrics['conflicting_nonblank_mhe'] else 0
        annual.append(dict(metrics)); print(f"ID {year}: {metrics['crash_rows']} crashes; consistent={metrics['consistent_nonblank_mhe']}; conflicts={metrics['conflicting_nonblank_mhe']}",flush=True)
    totals=defaultdict(int)
    numeric=sorted({k for row in annual for k in row if k not in {'year','output_sha256','consistent_coverage_pct','conflict_rate_linked_nonblank_pct'}})
    for row in annual:
        for k in numeric: totals[k]+=int(row.get(k,0))
    totals['consistent_coverage_pct']=round(100*totals['consistent_nonblank_mhe']/totals['crash_rows'],6)
    denom=totals['consistent_nonblank_mhe']+totals['conflicting_nonblank_mhe']
    totals['conflict_rate_linked_nonblank_pct']=round(100*totals['conflicting_nonblank_mhe']/denom,6) if denom else 0
    report={'state':'ID','executed_utc':datetime.now(timezone.utc).isoformat(),'method':'All nonblank unit MHE labels must agree; conflicting labels can populate only a unanimously supported nonblank collision partner group.','provenance':PROVENANCE,'crosswalk':str(XWALK),'crosswalk_sha256':sha256(XWALK),'years':annual,'totals':dict(totals),'result':'PASS'}
    (QA/'unit_mhe_enrichment_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    with (QA/'unit_mhe_enrichment_summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
        summary_fields=['year'] + sorted({key for row in annual for key in row if key != 'year'})
        writer=csv.DictWriter(f,fieldnames=summary_fields,lineterminator='\n'); writer.writeheader(); writer.writerows(annual)
    with (QA/'unit_mhe_conflict_partner_audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
        audit_fields=['year','source_crash_id','unit_mhe_labels','collision_partner_group','mapping_status','applied_or_already_present']
        writer=csv.DictWriter(f,fieldnames=audit_fields,lineterminator='\n'); writer.writeheader(); writer.writerows(conflict_partner_audit)
    print(json.dumps({'state':'ID','totals':dict(totals),'result':'PASS'},indent=2))

if __name__=='__main__': main()
