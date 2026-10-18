"""Refresh current documentation only after the WA revision validates."""
from pathlib import Path
import json,hashlib,shutil,re
import pandas as pd
P=Path(__file__).resolve().parents[1];ROOT=P.parent
Q=P/'qa/revisions/WA_SRFF_2026-10-15_v1'
r=json.loads((Q/'revision_report.json').read_text(encoding='utf-8'))
v=json.loads((P/'qa/post_harmonization/WA/validation_report.json').read_text(encoding='utf-8'))
assert r['status']=='PROMOTED' and r['result']=='PASS' and v['result']=='PASS' and v['rows']==r['total_after']
warnings=[]
for item in r['years']:
    year=item['year']
    a=pd.read_csv(P/f'data/crash/WA/WA_crashes_harmonized_{year}.csv',dtype=str,keep_default_na=False,usecols=['crash_uid','source_crash_id','crash_year','severity_kabco','severity_raw_label','severity_provenance','fatalities','source_file','source_row_number'])
    bad=a.loc[a.severity_kabco.eq('K')&a.fatalities.eq('0')].copy()
    if len(bad):
        source=list((ROOT/f'States/WA/{year}/SRFF').glob('*.csv'))
        if source:
            n=pd.read_csv(source[0],skiprows=1,encoding='cp1252',dtype=str,keep_default_na=False,usecols=['REPORT NUMBER','MOST SEVERE INJURY TYPE','TOTAL FATALITIES'])
            bad=bad.merge(n,left_on='source_crash_id',right_on='REPORT NUMBER',how='left',validate='one_to_one').fillna('')
        warnings.extend(bad.to_dict('records'))
(Q/'fatality_severity_conflicts.json').write_text(json.dumps({'count':len(warnings),'resolution':'KEEP_BOTH_REPORTED_VALUES; EXCLUDE_FROM_INTERNALLY_CONSISTENT_FATALITY_COUNT_COHORT_UNTIL_ADJUDICATED','records':warnings},indent=2),encoding='utf-8')
r['quality_warnings']={'K_with_zero_fatalities':len(warnings),'detail_file':str(Q/'fatality_severity_conflicts.json'),'cross_year_report_id_matches':sum(x['cross_year_id_matches_not_duplicated'] for x in r['years'])}
(Q/'revision_report.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
(P/'qa/post_harmonization/WA/srff_revision_manifest.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
backup=Q/'baseline/documentation';backup.mkdir(parents=True,exist_ok=True)
def edit(path,fn):
    target=backup/path.name
    if not target.exists():shutil.copy2(path,target)
    old=path.read_text(encoding='utf-8-sig');path.write_text(fn(old),encoding='utf-8')
oldcount=65540775;newcount=oldcount+r['total_after']-r['total_before']
card=P/'DATASET_CARD.md'
def update_card(s):
    s=s.replace('Snapshot date: 2026-10-14','Snapshot date: 2026-10-15 (WA SRFF revision; other states retain their prior snapshots)')
    s=s.replace(f'Unique crash records: {oldcount:,}',f'Unique crash records: {newcount:,}')
    s=s.replace('missing collision manner and road surface in Washington','CAT-only collision-manner/surface gaps in Washington (2020–2026 SRFF-linked rows are now enriched)')
    if 'WA_SRFF_REVISION_2026-10-15.md' not in s:
        s+='\n## Washington detailed-source revision\n\nWA now contains '+f"{r['total_after']:,}"+' unique crashes in ten annual files, including 639 newly linked distinct IDs. The detailed 2020–2026 SRFF source supplements severity, collision, weather/light/surface, counts and involvement flags. CAT-only Minor is unspecified injury severity, not automatically B. Raw ObjectStruck does not establish a first harmful event. Existing CAT coordinates are retained; SRFF-only XY awaits documented datum confirmation. See [revision rules](docs/WA_SRFF_REVISION_2026-10-15.md) and `qa/revisions/WA_SRFF_2026-10-15_v1/`. Historical figure/analysis snapshots predate this revision and require regeneration.\n'
    return s
edit(card,update_card)
quality=ROOT/'States/WA/QUALITY_NOTES.md'
text='''# Washington harmonization quality notes — updated 2026-10-15

- Sources: Washington State Patrol CAT baseline (2017–2026) plus agency-supplied SRFF detailed exports (2020–2026). All source files remain intact. 2026 is YTD; files and older annual snapshots do not establish complete current reporting.
- Output: TOTAL unique crashes in ten annual 77-column files. SRFF adds 639 new distinct IDs; two further same-year candidates already existed in other CAT years and are not duplicated. Date conflicts are logged.
- CAT-only rows are retained. The earlier 2014–2016 partial/near-empty exclusions remain unchanged. Original within-CAT deduplication also remains unchanged.
- Detailed SRFF mappings provide K/A/B/C/O severity, fatal/injury counts, explicit collision descriptions, weather/light/surface and work-zone/alcohol/drug/speed flags. Unknown and ambiguous values remain explicit; field coverage is not universal.
- CAT Minor combines B/C: unmatched records use U with INJURY_PRESENT_SEVERITY_UNSPECIFIED and retain the original label. Do not treat this U as no injury.
- CAT ObjectStruck does not establish event order: unsupported first-event/partner mappings are withdrawn. Raw labels are retained. Guardrail text is not a train collision.
- Existing CAT coordinates are retained. SRFF X/Y are preserved in sources/extensions but not transformed until the datum is documented; newly added rows have missing canonical coordinates.
- Six retained K records have a reported fatality count of zero. Both observations are preserved and listed in fatality_severity_conflicts.json. Exclude these unresolved records from internally consistent fatality-count cohorts; a PASS structural validation does not resolve them.
- Combined categories are not arbitrarily split. Unknown lighting is not assumed unlighted. Work-zone FALSE is based on an explicit flag, not a blank subtype. Commercial involvement is not an exact count; motorcycle and speed-limit aggregation are conservative.
- Full rules: ../../Unified_MMUCC6/docs/WA_SRFF_REVISION_2026-10-15.md. Revision manifest, staged evidence, cell-change logs and pre-revision backup: ../../Unified_MMUCC6/qa/revisions/WA_SRFF_2026-10-15_v1/.
'''.replace('TOTAL',f"{r['total_after']:,}")
edit(quality,lambda _:text)
edit(P/'PIPELINE.md',lambda s:s if '## WA detailed SRFF enrichment' in s else s+'\n## WA detailed SRFF enrichment\n\nThe WA wrapper now builds CAT inputs and runs `scripts/enrich_wa_from_srff.py --promote` after harmonization, before validation. Retain `States/WA/<year>/SRFF/` and the dictionary. Running the generic harmonizer alone does not reproduce the enriched outputs. See `docs/WA_SRFF_REVISION_2026-10-15.md`.\n')
source=ROOT/'States/WA/SOURCE.md'
edit(source,lambda s:s if '## SRFF detailed official package, 2026-10-15' in s else s+'\n## SRFF detailed official package, 2026-10-15\n\nAgency-supplied 2020–2026 SRFF annual CSVs (307 columns each; CP1252; second-record header) are retained under each year/SRFF. The original supplied dictionary is under docs/source_metadata. The 663,433 source records supplement the CAT baseline; they do not replace its broader population. Source hashes, exact linkage and the cross-year conflicts are recorded in the Unified_MMUCC6 WA revision manifest.\n')
manifest=P/'qa/post_harmonization/WA/run_manifest.json'
m=json.loads(manifest.read_text(encoding='utf-8'));m['post_harmonization_revision']='WA_SRFF_2026-10-15_v1';m['post_harmonization_manifest']=str(Q/'revision_report.json');m['post_harmonization_output_rows']=r['total_after']
manifest.write_text(json.dumps(m,indent=2),encoding='utf-8')
# Keep current HTML inventory's WA note in sync without altering other states.
inventory=ROOT/'States/US_crash_data_inventory.html'
def html(s):
    pattern=r'<tr><td><strong>WA</strong>.*?</tr>'
    found=re.search(pattern,s,re.S)
    if found and 'WA_SRFF_2026_10_15' not in found.group():
        row=found.group();note="<div id='WA_SRFF_2026_10_15'><strong>2026-10-15更新：</strong>2020–2026官方SRFF详细CSV（307字段）已与CAT按编号合并。含详细严重性、碰撞形态、路面、伤亡数及酒精/药物/超速等；共1,168,229起。CAT有效经纬度保留，SRFF新增记录的XY待确认基准后转换。<a href='../Unified_MMUCC6/docs/WA_SRFF_REVISION_2026-10-15.md'>规则与限制</a></div>"
        row=row.replace('</td></tr>',note+'</td></tr>');s=s[:found.start()]+row+s[found.end():]
    return s
if inventory.exists():edit(inventory,html)
print(json.dumps({'WA_rows':r['total_after'],'national_rows':newcount,'documentation_updated':True}))
