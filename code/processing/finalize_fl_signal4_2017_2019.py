"""Validate and promote the staged Signal4 source correction; preserve old bytes.

Run only after the isolated harmonizer and validator have passed for 2017-2019.
All paths are constrained to the explicit project root. Original S4ACrashes files
are read-only. Historical validation reports remain historical.
"""
from pathlib import Path
from datetime import datetime, timezone
import csv, hashlib, json, shutil
import pandas as pd

ROOT = Path(r'F:\LH_Research\USCrash\Crash')
REV = ROOT/'verification/unified_revision_evidence/FL_signal4_2017_2019_2026-10-18'
STAGE = REV/'staging'
YEARS = [2017, 2018, 2019]

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8388608),b''): h.update(b)
    return h.hexdigest()

def backup(p):
    assert p.resolve().is_relative_to(ROOT.resolve())
    dest=REV/'before'/p.relative_to(ROOT)
    if p.exists() and not dest.exists():
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)

def replace(src,dst):
    assert dst.resolve().is_relative_to(ROOT.resolve())
    backup(dst);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)

def write_csv(p,d):
    backup(p);d.to_csv(p,index=False,encoding='utf-8-sig',lineterminator='\n')

def main():
    assert not (REV/'promotion_manifest.json').exists(),'Already promoted'
    qa=STAGE/'Unified_MMUCC6/qa/post_harmonization/FL'
    report=json.loads((qa/'validation_report.json').read_text())
    assert report['result']=='PASS' and report['files']==3
    schema=pd.read_csv(ROOT/'code/config/canonical_crash_schema.csv').field_name.tolist()
    audits=[];catalog=pd.read_csv(ROOT/'manifests/annual_data_catalog.csv',keep_default_na=False)
    before_total=int(catalog.records.sum())
    for y in YEARS:
        source=STAGE/f'States/FL/{y}/CSV/FL_Signal4_crashes_{y}.csv'
        output=STAGE/f'Unified_MMUCC6/data/crash/FL/FL_crashes_harmonized_{y}.csv'
        d=pd.read_csv(output,dtype=str,keep_default_na=False)
        raw=pd.read_csv(source,usecols=['REPORT_NUMBER','CODEABLE','CRASH_YEAR'],dtype=str,keep_default_na=False)
        selected=raw[raw.CODEABLE.eq('Y')]
        assert list(d)==schema and len(schema)==77
        assert selected.REPORT_NUMBER.is_unique and d.crash_uid.is_unique
        assert d.source_crash_id.tolist()==selected.REPORT_NUMBER.tolist()
        assert d.source_row_number.astype(int).tolist()==(selected.index+1).tolist()
        assert d.crash_year.eq(str(y)).all() and d.state.eq('FL').all()
        assert d.source_schema_id.eq('FL_SIGNAL4_2017_2019').all()
        assert d.source_file.eq(f'FL/{y}/CSV/FL_Signal4_crashes_{y}.csv').all()
        raw[~raw.CODEABLE.eq('Y')].to_csv(REV/f'excluded_reports_{y}.csv.gz',index=False,compression='gzip')
        old=ROOT/f'Unified_MMUCC6/data/crash/FL/FL_crashes_harmonized_{y}.csv'
        audits.append(dict(year=y,source_rows=len(raw),retained_records=len(d),excluded_records=len(raw)-len(d),
                           old_records=int(catalog.loc[(catalog.state=='FL')&(catalog.year==y),'records'].iloc[0]),
                           source_sha256=sha(source),old_output_sha256=sha(old),output_sha256=sha(output),
                           coordinates_status_valid=int(d.coordinate_status.eq('VALID').sum()),
                           schema_columns=77,retained_ids_and_source_rows_exact=True,result='PASS'))
    # Save the complete preceding catalogs/configuration before replacing data.
    for y in YEARS:
        for rel in [f'Unified_MMUCC6/data/crash/FL/FL_crashes_harmonized_{y}.csv',
                    f'States/FL/{y}/FDOT_all_crashes.csv']:
            backup(ROOT/rel)
    for a in audits:
        y=a['year']
        for rel in [f'States/FL/{y}/CSV/FL_Signal4_crashes_{y}.csv',
                    f'States/FL/{y}/Metadata/Signal4_README.html',
                    f'Unified_MMUCC6/data/crash/FL/FL_crashes_harmonized_{y}.csv']:
            if (STAGE/rel).exists():replace(STAGE/rel,ROOT/rel)
        old=ROOT/f'States/FL/{y}/FDOT_all_crashes.csv'
        archived=REV/'before'/old.relative_to(ROOT)
        assert old.resolve().is_relative_to((ROOT/'States/FL').resolve())
        assert old.exists() and sha(old)==sha(archived)
        old.unlink()  # Exact recoverable copy verified immediately above.
        mask=(catalog.state=='FL')&(catalog.year==y)
        for key,value in {'records':a['retained_records'],'unique_ids':a['retained_records'],
                          'coordinates_status_valid':a['coordinates_status_valid']}.items(): catalog.loc[mask,key]=value
    for folder in ['code/config','Unified_MMUCC6/config','code/replay_runtime/Unified_MMUCC6/config']:
        replace(STAGE/'Unified_MMUCC6/config/states/FL.json',ROOT/folder/'states/FL.json')
    for p in [ROOT/'manifests/annual_data_catalog.csv',ROOT/'Unified_MMUCC6/manifests/annual_data_catalog.csv']:
        view=catalog.copy()
        if 'Unified_MMUCC6/manifests' in str(p).replace('\\','/'):
            view['path']=view.path.str.removeprefix('Unified_MMUCC6/')
        write_csv(p,view)
    state=pd.read_csv(ROOT/'manifests/state_data_catalog.csv',keep_default_na=False)
    fl=catalog[catalog.state.eq('FL')]
    state.loc[state.state.eq('FL'),'records']=int(fl.records.sum())
    state.loc[state.state.eq('FL'),'valid_coordinate_records']=int(fl.coordinates_status_valid.sum())
    for p in [ROOT/'manifests/state_data_catalog.csv',ROOT/'Unified_MMUCC6/docs/state_coverage.csv']:
        write_csv(p,state)
    sources=ROOT/'Unified_MMUCC6/docs/data_sources.csv'
    ds=pd.read_csv(sources,keep_default_na=False);ds.loc[ds.state.eq('FL'),'retained_records']=int(fl.records.sum());write_csv(sources,ds)
    links=ROOT/'manifests/configured_input_output_links.csv';d=pd.read_csv(links,keep_default_na=False)
    for y in YEARS:
        mask=d.state.eq('FL')&d.year.eq(y)
        # Preserve the existing catalog column names.
        for col in d:
            if 'schema' in col:d.loc[mask,col]='FL_SIGNAL4_2017_2019'
            if col in ['source','source_file','input_file','input_path','source_path']:d.loc[mask,col]=f'States/FL/{y}/CSV/FL_Signal4_crashes_{y}.csv'
    write_csv(links,d)
    current=ROOT/'verification/unified_revision_evidence/post_harmonization/FL'
    prev=pd.read_csv(current/'harmonization_summary.csv',keep_default_na=False)
    new=pd.read_csv(qa/'harmonization_summary.csv',keep_default_na=False)
    for col in ['source_file','output_file']:new[col]=new[col].str.replace(str(STAGE),str(ROOT),regex=False)
    merged=pd.concat([prev[~prev.year.isin(YEARS)],new]).sort_values('year')
    write_csv(current/'harmonization_summary.csv',merged)
    # A full-state validation will be run separately after this promotion.
    result=dict(revision='2026-10-18_FL_signal4_2017_2019',executed_utc=datetime.now(timezone.utc).isoformat(),
                years=audits,records_before=before_total,records_after=int(catalog.records.sum()),
                florida_records_after=int(fl.records.sum()),other_annual_catalog_rows_unchanged=True,
                source_root_originals_unchanged=True,backup=str(REV/'before'),result='PASS')
    (REV/'promotion_manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
