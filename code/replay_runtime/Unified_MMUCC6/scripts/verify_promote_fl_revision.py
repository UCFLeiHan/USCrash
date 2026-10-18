"""Validate and promote the isolated 2026-10-14 Florida rebuild.

Prerequisite: reviewed FL.json, then run harmonize_crash.py --state FL with
USCRASH_ROOT=<revision>/staging and USCRASH_SOURCE_ROOT=<original>/States.
Only CODEABLE=N rows and the six erroneous first-event-derived cells may
change. Preserve prior outputs, excluded IDs, and most-event observations.
Never infer missing cases from annual report totals. Original sources are read-only.
"""
from __future__ import annotations
import csv, gzip, hashlib, itertools, json, os, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

U=Path(__file__).resolve().parents[1]
R=U/'qa/revisions/2026-10-14_FL_codeable_fhe'
S=R/'staging/Unified_MMUCC6'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    assert not (R/'promotion_manifest.json').exists(), 'already promoted'
    old_summary=pd.read_csv(R/'before/qa_FL/harmonization_summary.csv',keep_default_na=False)
    new_summary=pd.read_csv(S/'qa/post_harmonization/FL/harmonization_summary.csv',keep_default_na=False)
    assert list(old_summary.year)==list(new_summary.year)==list(range(2007,2026))
    assert old_summary.source_sha256.tolist()==new_summary.source_sha256.tolist(), 'raw source bytes changed'
    assert len(list((S/'data/crash/FL').glob('*.csv')))==19
    assert not list((S/'data/crash/FL').glob('*.partial'))
    staged_manifest=json.loads((S/'qa/post_harmonization/FL/run_manifest.json').read_text())
    assert staged_manifest['config_sha256']==sha(U/'config/states/FL.json')
    assert staged_manifest['crosswalk_sha256']==sha(U/'config/code_crosswalk_FL.csv')
    report=[]
    bad_fields=['first_harmful_event','first_harmful_event_raw_code',
                'first_harmful_event_raw_label','first_harmful_event_provenance',
                'first_harmful_event_group','collision_partner_group']
    with gzip.open(R/'excluded_CODEABLE_N_reports.csv.gz','wt',encoding='utf-8',newline='') as ef, \
         gzip.open(R/'preserved_most_harmful_event_observations.csv.gz','wt',encoding='utf-8',newline='') as mf:
        ew=csv.writer(ef,lineterminator='\n');mw=csv.writer(mf,lineterminator='\n')
        ew.writerow(['crash_uid','source_crash_id','source_file','source_row_number','CODEABLE','exclusion_reason'])
        mw.writerow(['crash_uid','source_file','source_row_number','most_harmful_event_raw_code',
                     'most_harmful_event_raw_label','previous_category_from_most_event',
                     'previous_group_from_most_event','semantic_warning'])
        for rec in new_summary.to_dict('records'):
            y=int(rec['year']);old=U/'data/crash/FL'/f'FL_crashes_harmonized_{y}.csv'
            new=Path(rec['output_file']);assert sha(new)==rec['output_sha256']
            assert sha(old)==old_summary.loc[old_summary.year.eq(y),'output_sha256'].iloc[0]
            code={}
            if y>=2020:
                d=pd.read_csv(rec['source_file'],usecols=['REPORT_NUMBER','CODEABLE'],dtype=str,keep_default_na=False)
                assert d.REPORT_NUMBER.is_unique and set(d.CODEABLE)<= {'Y','N'}
                code=dict(zip(d.REPORT_NUMBER,d.CODEABLE));del d
            nold=nnew=excluded=corrected=0
            with old.open(encoding='utf-8-sig',newline='') as of,new.open(encoding='utf-8-sig',newline='') as nf:
                a=csv.reader(of);b=csv.reader(nf);header=next(a);assert header==next(b) and len(header)==77
                ix={c:header.index(c) for c in header}
                for row in a:
                    nold+=1
                    if y>=2020 and code[row[ix['source_crash_id']]]=='N':
                        ew.writerow([row[ix[c]] for c in ['crash_uid','source_crash_id','source_file','source_row_number']]+['N','OUTSIDE_CODEABLE_Y_STUDY_POPULATION'])
                        excluded+=1;continue
                    if 2011<=y<=2019:
                        mw.writerow([row[ix[c]] for c in ['crash_uid','source_file','source_row_number',
                                      'first_harmful_event_raw_code','first_harmful_event_raw_label',
                                      'first_harmful_event','first_harmful_event_group']]+
                                    ['MOST_EVENT_IS_NOT_FIRST_EVENT; prior categories retained for provenance, not first-event analysis'])
                        for c in bad_fields:row[ix[c]]='UNAVAILABLE' if c=='first_harmful_event_provenance' else ''
                        corrected+=1
                    actual=next(b,None)
                    if row!=actual:
                        diffs=[header[i] for i in range(len(header)) if actual is None or row[i]!=actual[i]]
                        raise AssertionError((y,nold,'unexpected record change',diffs))
                    nnew+=1
                assert next(b,None) is None, (y,'unexpected extra rows')
            assert nnew==int(rec['output_rows']) and nold-excluded==nnew
            assert excluded==int(rec['excluded_source_rows'])
            report.append(dict(year=y,previous_rows=nold,current_rows=nnew,excluded_codeable_n=excluded,
                               first_event_semantic_corrections=corrected,all_other_cells_exactly_preserved=True,
                               source_sha256_verified_unchanged=True))
            print(json.dumps(report[-1]),flush=True)
    pd.DataFrame(report).to_csv(R/'record_level_revision_audit.csv',index=False,encoding='utf-8-sig')
    env=os.environ.copy();env['USCRASH_ROOT']=str(R/'staging')
    subprocess.run([sys.executable,str(U/'scripts/validate_harmonized_crash.py'),'--state','FL'],env=env,check=True)
    backup=R/'before/data_FL';assert not backup.exists()
    target=U/'data/crash/FL';staged=S/'data/crash/FL'
    # Resolve and constrain each move destination within the expressly named project.
    for p in [target,staged,backup]:assert p.resolve().is_relative_to(U.resolve())
    target.rename(backup)
    try:staged.rename(target)
    except BaseException:
        backup.rename(target);raise
    qa=S/'qa/post_harmonization/FL'
    staged_manifest['config_revision']=R.name
    staged_manifest['revision_audit']=str(R/'record_level_revision_audit.csv')
    (qa/'run_manifest.json').write_text(json.dumps(staged_manifest,indent=2),encoding='utf-8')
    for row in new_summary.itertuples():
        new_summary.loc[new_summary.year.eq(row.year),'output_file']=str(target/Path(row.output_file).name)
    new_summary.to_csv(qa/'harmonization_summary.csv',index=False,encoding='utf-8-sig')
    shutil.copytree(qa,U/'qa/post_harmonization/FL',dirs_exist_ok=True)
    env['USCRASH_ROOT']=str(U.parent)
    subprocess.run([sys.executable,str(U/'scripts/validate_harmonized_crash.py'),'--state','FL'],env=env,check=True)
    manifest=dict(revision_id=R.name,executed_utc=datetime.now(timezone.utc).isoformat(),
                  canonical_fl_rows_before=sum(x['previous_rows'] for x in report),
                  canonical_fl_rows_after=sum(x['current_rows'] for x in report),
                  excluded_codeable_n=sum(x['excluded_codeable_n'] for x in report),
                  semantic_corrections=sum(x['first_event_semantic_corrections'] for x in report),
                  raw_sources_unchanged=True,other_columns_exactly_preserved=True,
                  config_sha256=sha(U/'config/states/FL.json'),
                  audit_sha256=sha(R/'record_level_revision_audit.csv'),
                  excluded_id_ledger_sha256=sha(R/'excluded_CODEABLE_N_reports.csv.gz'),
                  most_event_sidecar_sha256=sha(R/'preserved_most_harmful_event_observations.csv.gz'),
                  previous_outputs=str(backup),result='PASS')
    (R/'promotion_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2),flush=True)

if __name__=='__main__':main()
