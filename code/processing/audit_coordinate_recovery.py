"""Independent before/final comparison and coordinate-only recovery report."""
import json,shutil,html
from itertools import zip_longest
from pathlib import Path
import pandas as pd
from coordinate_supplement_utils import U,REV,sha
promotions=[]
for p in REV.glob('*/*_promotion.json'):
 j=json.loads(p.read_text());j.update(promotion_file=str(p),revision=p.parent.name)
 if j.get('filled',0):promotions.append(j)
groups={}
for j in promotions:groups.setdefault((j['state'],j['year']),[]).append(j)
checks=[]
for (state,year),items in sorted(groups.items()):
 afters={x['sha256_after'] for x in items};first=[x for x in items if x['sha256_before'] not in afters];assert len(first)==1
 chain=[first[0]]
 while len(chain)<len(items):
  nxt=[x for x in items if x['sha256_before']==chain[-1]['sha256_after']];assert len(nxt)==1;chain+=nxt
 current=U/f'data/crash/{state}/{state}_crashes_harmonized_{year}.csv'
 backup=Path(first[0]['promotion_file']).parent/'canonical_before'/current.name
 assert sha(backup)==chain[0]['sha256_before'];assert sha(current)==chain[-1]['sha256_after']
 n=changed=0
 for a,b in zip_longest(pd.read_csv(backup,dtype=str,keep_default_na=False,chunksize=75000),pd.read_csv(current,dtype=str,keep_default_na=False,chunksize=75000)):
  assert a is not None and b is not None and list(a.columns)==list(b.columns) and len(a.columns)==77 and len(a)==len(b)
  cols=[c for c in a if c not in ['latitude','longitude','coordinate_status']];assert a[cols].equals(b[cols]),(state,year,'noncoordinate changed')
  old=a.coordinate_status.eq('VALID')&pd.to_numeric(a.latitude,errors='coerce').between(-90,90)&pd.to_numeric(a.longitude,errors='coerce').between(-180,180)
  c=['latitude','longitude','coordinate_status'];assert a.loc[old,c].equals(b.loc[old,c])
  changed+=int(a[c].ne(b[c]).any(axis=1).sum());n+=len(a)
 assert changed==sum(x['filled'] for x in items)
 checks.append(dict(state=state,year=year,records=n,coordinates_added=changed,columns=77,row_order_unchanged=True,noncoordinate_fields_unchanged=True,existing_valid_coordinates_unchanged=True,hash_chain_verified=True,status='PASS'))
 print('INDEPENDENT PASS',state,year,changed,flush=True)
pd.DataFrame(checks).to_csv(REV/'independent_final_validation.csv',index=False);pd.DataFrame(promotions).to_csv(REV/'promotion_index.csv',index=False)
b=pd.read_csv(REV/'baseline_state_coordinate_availability.csv');adds=pd.DataFrame(checks).groupby('state').coordinates_added.sum()
b['added']=b.state.map(adds).fillna(0).astype(int);b['valid_after']=b.valid+b.added;b['missing_after']=b.records-b.valid_after;b['missing_pct_after']=100*b.missing_after/b.records;b=b.sort_values('missing_after',ascending=False)
b.to_csv(REV/'state_coordinate_before_after.csv',index=False,encoding='utf-8-sig')
y=pd.read_csv(REV/'baseline_state_year_coordinate_availability.csv');lookup={(x['state'],x['year']):x['coordinates_added'] for x in checks};y['added']=[lookup.get((s,int(t)),0) for s,t in zip(y.state,y.year)];y['valid_after']=y.valid+y.added;y['missing_after']=y.records-y.valid_after;y['missing_pct_after']=100*y.missing_after/y.records;y.to_csv(REV/'state_year_coordinate_before_after.csv',index=False,encoding='utf-8-sig')
notes=[
('AL','Recovered','2014–2020 CARE coordinates were published but omitted by the old export request. Exact record GUID + date + hour; source coordinate-origin indicator retained.','https://safety.aladata.com/'),
('NC','Partial','Exact statewide ID + date from K/A and official special-population map layers. Conflicting donor points/dates held. All-severity gaps, especially 2026, remain.','https://services.arcgis.com/NuWFvHYDMVmmxMeM/ArcGIS/rest/services/'),
('NJ','Partial','DVRPC NJDOT regional 2017–2023 geometry includes LRS-derived points. Exact composite case ID + date + minute; preserved ID bridge required for 2019. Older statewide gaps remain.','https://catalog.dvrpc.org/dataset/new-jersey-crash-data-points'),
('OH','Partial','Official Cleveland and Columbus ODOT/GCAT points: exact document ID + date + hour. Historical statewide TIMS endpoint unavailable during probes; city recovery is not statewide coverage.','https://data.clevelandohio.gov/'),
('ID','Partial','ITD published geometry may exist when CSV GPS attributes are blank. Exact serial number and full date/time; state and county screens. 64 first-pass candidates failed the county screen and were withdrawn in v2; earlier outputs retained under superseded. Map geometry is not measured GPS; reported-versus-map distance diagnostics are archived.','https://gis.itd.idaho.gov/arcgisprod/rest/services/ArcGISOnline/CrashLayers/MapServer'),
('TX','Partial','Austin official city CRIS ID + local date/minute; deleted/temporary rows excluded. 2023 alternate state coordinate columns checked; no additional missing points recovered by that check.','https://data.austintexas.gov/d/y2wy-tgr5'),
('MA','Partial','Archived official WGS84 geometry used when reported LAT/LON absent. Exact crash number and date; gaps absent from both representations remain.','https://apps.impact.dot.state.ma.us/'),
('NY','Unresolved','Public DMV Case table has no coordinates or stable case identifier for safe municipal linkage. Row-derived canonical IDs are not police report numbers. NYC data exist, but day/time alone is insufficient. Need agency ID bridge or geocoded export.','https://data.ny.gov/'),
('MS','Unresolved','Older ReportBeam crash/person/vehicle/occupant/weather tables inspected: coordinate fields not found. No verified exact-key historical geocoded donor located. Recent eCrash availability does not resolve old years.','https://publicdata.dps.ms.gov/Public-CrashData/'),
('CO','Candidate held','DRCOG officially cleans/maps CDOT regional crashes. Dashboard uses DRCOG IDs with no validated CDOT CUID bridge; some legacy canonical IDs are row numbers. Metadata archived; no unverified points promoted.','https://www.drcog.org/transportation-planning/planning-future/safety/regional-vision-zero'),
('CA','Previous recovery retained','Existing LA/SF/San Jose supplements retained. Regional TIMS/SANDAG IDs are not established CCRS ID equivalents; no unsupported new joins. See earlier CA revision ledgers.','https://data.lacity.org/d/d5tf-ez2w'),
('MO','Audited no additions','Archived GPS and geometry alternatives yielded no new missing-point recovery. Earlier source-year coverage gap is a separate issue.','https://www.mshp.dps.missouri.gov/')]
pd.DataFrame(notes,columns=['state','status','finding','official_source']).to_csv(REV/'source_findings_and_remaining_actions.csv',index=False,encoding='utf-8-sig')
snap=REV/'executed_scripts';snap.mkdir(exist_ok=True)
for p in (U/'scripts').glob('*.py'):
 if p.name.startswith(('supplement_','coordinate_supplement_utils','audit_coordinate_recovery')):shutil.copy2(p,snap/p.name)
summary=dict(records=int(b.records.sum()),jurisdictions=len(b),annual_files=len(y),new_coordinates=int(b.added.sum()),states_improved=int(b.added.gt(0).sum()),valid_before=int(b.valid.sum()),valid_after=int(b.valid_after.sum()),modified_annual_files=len(checks),independent_checks='PASS',raw_files_modified=False,fields_changed=['latitude','longitude','coordinate_status'])
(REV/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
readme="""# Coordinate recovery, 2026-10-16

This is a coordinate-only revision, not new crash acquisition. Raw files, canonical population, row order, all 77 columns, non-coordinate fields, and existing valid points are preserved. Each promotion has a backup, source linkage, change ledger and SHA-256 chain. Independent final comparison verifies the invariants.

Only unique source identifiers with corroborating dates/times were used. Points pass a 2 km buffered Census state polygon screen; this is not proof of positional accuracy. Published LRS/map-derived points are not necessarily measured GPS. No centroids, nearest-neighbour guessing, averaging conflicting donors or invented points were used. Unresolved gaps remain null.

Reproduce after ordinary harmonization using the archived supplement scripts and cached donor responses, then audit_coordinate_recovery.py. OH defaults to Cleveland; run again with USCRASH_OH_CITY=Columbus. Completed promotions verify prior ledgers on rerun. To apply to a clean base, select a fresh USCRASH_COORDINATE_AUDIT_ROOT and copy the baseline CSVs and ID_county_boundaries.geojson into it; do not reuse existing promotion ledgers with a reset base. USCRASH_CRASH_ROOT and USCRASH_UNIFIED_ROOT configure input and output roots. USCRASH_CENSUS_STATES selects the archived Census boundary ZIP for a different machine. Preserve caches/request metadata/extract hashes for this exact snapshot. A fresh base harmonization needs these overlays reapplied afterward. Per-source manifests describe parameters and linkage rules.

Before/after availability totals use frozen baseline counts plus independently verified additions, not a new nationwide scan. Percentages apply to acquired populations, whose reporting scope and years differ; they do not establish crash-population completeness or positional accuracy. Remaining jurisdictions with low missingness were screened by baseline availability; intensive donor investigation prioritized large gaps. Do not interpret the unlisted sources as an exhaustive search of every municipality.
"""
(REV/'README.md').write_text(readme,encoding='utf8')
t=b[['state','records','added','missing_pct','missing_pct_after','missing_after']].copy();t.columns=['State','Records','Added','Missing before %','Missing after %','Still missing']
rows=''.join('<tr><td>'+html.escape(s)+'</td><td>'+html.escape(st)+'</td><td>'+html.escape(n)+'</td><td><a href="'+html.escape(url)+'">Official source</a></td></tr>' for s,st,n,url in notes)
page='<!doctype html><meta charset="utf-8"><title>Coordinate recovery</title><style>body{font-family:Arial;max-width:1250px;margin:35px auto;line-height:1.5}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid #ddd;padding:7px;text-align:left}th{background:#edf3f6}</style><h1>Coordinate recovery</h1><p>'+f"{summary['new_coordinates']:,} additional locations; {summary['states_improved']} states; {summary['modified_annual_files']} annual files independently verified. Population unchanged: {summary['records']:,}."+'</p><p>Only coordinate fields changed. Source files and existing valid points retained. Agency map positions may be geocoded rather than GPS. Unresolved gaps remain.</p><p><a href="state_coordinate_before_after.csv">State CSV</a> | <a href="state_year_coordinate_before_after.csv">State/year CSV</a> | <a href="independent_final_validation.csv">Independent QA</a> | <a href="README.md">Reproduction notes</a></p>'+t.to_html(index=False,float_format=lambda x:f'{x:.2f}')+'<h2>Sources and unresolved issues</h2><table><tr><th>State</th><th>Status</th><th>Finding</th><th>Source</th></tr>'+rows+'</table>'
(REV/'index.html').write_text(page,encoding='utf8');print(json.dumps(summary),flush=True)
