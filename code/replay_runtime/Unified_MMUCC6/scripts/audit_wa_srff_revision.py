"""Independent conservation/lineage checks for the promoted WA source union."""
from pathlib import Path
import pandas as pd,json,hashlib
P=Path(__file__).resolve().parents[1];Q=P/'qa/revisions/WA_SRFF_2026-10-15_v1'
R=P.parent
report=json.loads((Q/'revision_report.json').read_text(encoding='utf-8'))
assert report['status']=='PROMOTED'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
read=lambda p,**kw:pd.read_csv(p,dtype=str,keep_default_na=False,low_memory=False,**kw)
baseline=set();after=set();source=set();rows=[]
stable=['crash_uid','crash_date','crash_year','crash_month','date_precision','crash_time','crash_datetime','time_precision','latitude','longitude','coordinate_status','county','city','source_file','source_row_number']
for item in report['years']:
    year=item['year'];name=f'WA_crashes_harmonized_{year}.csv'
    a=read(Q/'baseline/data'/name).set_index('source_crash_id',drop=False)
    b=read(P/'data/crash/WA'/name).set_index('source_crash_id',drop=False)
    assert b.index.is_unique and set(a.index)<=set(b.index)
    assert b.loc[a.index,stable].eq(a[stable]).all().all(),('Changed stable CAT data',year)
    assert sha(P/'data/crash/WA'/name)==item['output_sha256']
    assert sha(Q/'baseline/data'/name)==item['baseline_sha256']
    new=b.index.difference(a.index)
    assert b.loc[new,['latitude','longitude']].eq('').all().all()
    assert b.loc[new,'coordinate_status'].eq('MISSING').all()
    sources=list((R/f'States/WA/{year}/SRFF').glob('*.csv'))
    possible=0
    if sources:
        n=read(sources[0],skiprows=1,encoding='cp1252').set_index('REPORT NUMBER',drop=False)
        source.update(n.index)
        common=n.index.intersection(b.index)
        for target,raw in [('fatalities','TOTAL FATALITIES'),('vehicles','TOTAL VEHICLES'),('pedestrian_count','TOTAL PEDESTRIANS INVOLVED'),('bicyclist_count','TOTAL BICYCLISTS INVOLVED')]:
            assert pd.to_numeric(b.loc[common,target]).eq(pd.to_numeric(n.loc[common,raw])).all(),(year,target)
        inj=n.loc[common,['TOTAL SERIOUS INJURIES','TOTAL MINOR INJURIES','TOTAL POSSIBLE INJURIES']].apply(pd.to_numeric).sum(axis=1)
        assert pd.to_numeric(b.loc[common,'injuries']).eq(inj).all()
        cids=common[n.loc[common,'MOST SEVERE INJURY TYPE'].eq('Possible Injury') & pd.to_numeric(n.loc[common,'TOTAL FATALITIES']).eq(0)]
        assert b.loc[cids,'severity_kabco'].eq('C').all();possible=len(cids)
        assert sha(sources[0])==item['srff_sha256']
    # A coarse CAT Minor must never retain an unsupported precise B grade.
    assert not (b.severity_raw_label.eq('Minor')&b.severity_kabco.eq('B')).any()
    baseline.update(a.index);assert not after.intersection(b.index);after.update(b.index)
    rows.append({'year':year,'retained_baseline_rows':len(a),'output_rows':len(b),'possible_injury_C_checked':possible,'stable_columns_exact':True,'result':'PASS'})
assert after==baseline|source,('Union mismatch',len(after),len(baseline|source))
assert len(after-baseline)==639
for s in report['source_manifest']:assert sha(Path(s['path']))==s['sha256']
out={'result':'PASS','union_ids':len(after),'retained_original_ids':len(baseline),'added_distinct_ids':len(after-baseline),'years':rows,'all_source_hashes_match':True,'all_baseline_dates_times_coordinates_and_source_pointers_unchanged':True}
(Q/'independent_audit.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
