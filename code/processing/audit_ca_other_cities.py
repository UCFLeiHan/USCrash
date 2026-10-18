"""Independent audit of CA other-city overlays and source/precision limitations."""
import json,html,shutil
from pathlib import Path
from itertools import zip_longest
import pandas as pd,numpy as np
from coordinate_supplement_utils import U,R,sha
P=U/'qa/CA_other_cities_2026-10-16';promotions=[]
for p in P.glob('*/*_promotion.json'):
 j=json.loads(p.read_text());j['promotion_file']=str(p)
 if j.get('filled',0):promotions.append(j)
groups={}
for j in promotions:groups.setdefault(j['year'],[]).append(j)
checks=[];ledgers=[];baselines={}
for y,items in sorted(groups.items()):
 afters={x['sha256_after'] for x in items};first=[x for x in items if x['sha256_before'] not in afters];assert len(first)==1;chain=[first[0]]
 while len(chain)<len(items):
  n=[x for x in items if x['sha256_before']==chain[-1]['sha256_after']];assert len(n)==1;chain+=n
 cp=U/f'data/crash/CA/CA_crashes_harmonized_{y}.csv';bp=Path(first[0]['promotion_file']).parent/'canonical_before'/cp.name;baselines[y]=bp
 assert sha(bp)==chain[0]['sha256_before'] and sha(cp)==chain[-1]['sha256_after']
 n=changed=0
 for a,b in zip_longest(pd.read_csv(bp,dtype=str,keep_default_na=False,chunksize=75000),pd.read_csv(cp,dtype=str,keep_default_na=False,chunksize=75000)):
  assert a is not None and b is not None and len(a)==len(b) and list(a.columns)==list(b.columns) and len(a.columns)==77
  cols=['latitude','longitude','coordinate_status'];other=[x for x in a if x not in cols];assert a[other].equals(b[other])
  v=a.coordinate_status.eq('VALID')&pd.to_numeric(a.latitude,errors='coerce').between(-90,90)&pd.to_numeric(a.longitude,errors='coerce').between(-180,180);assert a.loc[v,cols].equals(b.loc[v,cols])
  changed+=int(a[cols].ne(b[cols]).any(axis=1).sum());n+=len(a)
 assert changed==sum(x['filled'] for x in items)
 for it in items:ledgers.append(pd.read_csv(Path(it['promotion_file']).parent/f'CA_{y}_coordinate_changes.csv',dtype=str,keep_default_na=False).assign(year=y))
 checks.append(dict(year=y,records=n,added=changed,columns=77,noncoordinate_fields_unchanged=True,existing_valid_points_unchanged=True,row_order_unchanged=True,hash_chain_verified=True,status='PASS'));print('INDEPENDENT PASS',y,changed,flush=True)
pd.DataFrame(checks).to_csv(P/'independent_validation.csv',index=False);ledger=pd.concat(ledgers,ignore_index=True);assert ledger.crash_uid.is_unique;ledger.to_csv(P/'all_coordinate_changes.csv',index=False)
pairs=set(ledger[['coordinate_source_file','coordinate_source_sha256']].itertuples(index=False,name=None));hashes=[]
for f,h in sorted(pairs):
 actual=sha(f);assert actual==h;hashes.append(dict(source_file=f,sha256=h,status='PASS'))
pd.DataFrame(hashes).to_csv(P/'source_hash_verification.csv',index=False)
annual=[];cities=[];changed_lookup=ledger.set_index('crash_uid').coordinate_source
for y in range(2016,2027):
 cp=U/f'data/crash/CA/CA_crashes_harmonized_{y}.csv';bp=baselines.get(y,cp)
 keep=['crash_uid','source_crash_id','latitude','longitude','coordinate_status'];a=pd.read_csv(bp,usecols=keep,dtype=str,keep_default_na=False);b=pd.read_csv(cp,usecols=keep,dtype=str,keep_default_na=False);assert a.crash_uid.equals(b.crash_uid) and a.crash_uid.is_unique
 valid=lambda d:d.coordinate_status.eq('VALID')&pd.to_numeric(d.latitude,errors='coerce').between(-90,90)&pd.to_numeric(d.longitude,errors='coerce').between(-180,180)
 a['valid_before']=valid(a);a['valid_after']=valid(b);a['added']=a.valid_after.astype(int)-a.valid_before.astype(int);assert a.added.ge(0).all()
 raw=pd.read_csv(R/f'States/CA/{y}/Crashes_{y}.csv',dtype=str,keep_default_na=False,usecols=lambda c:c.strip() in ['Collision Id','City Name','County Code']);raw.columns=raw.columns.str.strip();a=a.merge(raw,left_on='source_crash_id',right_on='Collision Id',validate='one_to_one');assert len(a)==len(b)
 g=a.groupby(['County Code','City Name'],dropna=False).agg(records=('crash_uid','size'),valid_before=('valid_before','sum'),valid_after=('valid_after','sum'),added=('added','sum')).reset_index();g['year']=y;cities.append(g)
 annual.append(dict(year=y,records=len(a),valid_before=int(a.valid_before.sum()),valid_after=int(a.valid_after.sum()),added=int(a.added.sum()),missing_before=int((~a.valid_before).sum()),missing_after=int((~a.valid_after).sum())))
annual=pd.DataFrame(annual);assert annual.records.sum()==4670092 and annual.valid_before.sum()==3376507;assert annual.added.sum()==len(ledger)
annual['missing_pct_before']=100*annual.missing_before/annual.records;annual['missing_pct_after']=100*annual.missing_after/annual.records;annual.to_csv(P/'annual_before_after.csv',index=False)
cities=pd.concat(cities,ignore_index=True);cities['missing_pct_before']=100*(cities.records-cities.valid_before)/cities.records;cities['missing_pct_after']=100*(cities.records-cities.valid_after)/cities.records;cities.to_csv(P/'city_year_before_after.csv',index=False,encoding='utf-8-sig')
g=cities.groupby(['County Code','City Name'])[['records','valid_before','valid_after','added']].sum().reset_index();g['missing_pct_before']=100*(g.records-g.valid_before)/g.records;g['missing_pct_after']=100*(g.records-g.valid_after)/g.records;g=g.sort_values('added',ascending=False);g.to_csv(P/'city_all_years_before_after.csv',index=False,encoding='utf-8-sig');cities.loc[cities.year.eq(2023)].sort_values('added',ascending=False).to_csv(P/'city_2023_before_after.csv',index=False,encoding='utf-8-sig')
ledger.groupby(['coordinate_source','year']).size().rename('added').reset_index().to_csv(P/'source_year_additions.csv',index=False)
# Disagreement is a review flag: it does not establish which source is correct.
flags=[]
for p in P.glob('*_linkage.csv'):
 try:d=pd.read_csv(p,dtype=str,keep_default_na=False)
 except pd.errors.EmptyDataError:continue
 if 'distance_m' in d and 'existing_valid' in d:
  keep=d.existing_valid.eq('True')&pd.to_numeric(d.distance_m,errors='coerce').gt(5000)
  cols=[c for c in ['crash_uid','source','city','county','minute','roads','latitude','longitude','candidate_lat','candidate_lon','distance_m','donor_id'] if c in d]
  if keep.any():flags.append(d.loc[keep,cols])
if flags:pd.concat(flags,ignore_index=True).to_csv(P/'existing_coordinate_disagreements_over5km.csv',index=False)
summary=dict(records=int(annual.records.sum()),years='2016–2026',valid_before=int(annual.valid_before.sum()),valid_after=int(annual.valid_after.sum()),new_coordinates=len(ledger),missing_after=int(annual.missing_after.sum()),missing_pct_after=float(100*annual.missing_after.sum()/annual.records.sum()),modified_annual_files=len(checks),named_cities_improved=int(g.loc[g['City Name'].ne('Unincorporated')&g.added.gt(0),'City Name'].nunique()),raw_modified=False,existing_valid_coordinates_overwritten=False,noncoordinate_fields_changed=False,independent_validation='PASS',source_hashes_verified=len(hashes),geometry_precision='Published/geocoded locations; not necessarily measured GPS. Composite links are not exact police-ID links.')
(P/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8');(U/'CA_coordinate_recovery_manifest.json').write_text(json.dumps({**summary,'report':str(P/'index.html'),'revision_directory':str(P)},indent=2),encoding='utf8')
snap=P/'executed_scripts';snap.mkdir(exist_ok=True)
for name in ['download_ca_other_city_sources.py','supplement_ca_other_cities.py','supplement_ca_lacounty_report_coordinates.py','review_ca_other_city_candidates.py','validate_ca_composite_negative_controls.py','audit_ca_other_cities.py','coordinate_supplement_utils.py','pilot_ca_composite_coordinates.py','supplement_ca_pasadena_report_coordinates.py']:shutil.copy2(U/'scripts'/name,snap/name)
readme="""# CA other-city coordinate supplement, 2026-10-16

Original CCRS files, all crash populations, 77 columns, all non-coordinate values, original row order and previously VALID points remain unchanged. Independent chunked comparisons, hash chains, source-extract hashes and per-city/year coordinate counts are included.

## Linkage tiers
Regional SACOG, Orange County and SANDAG use unique exact composite fingerprints: agency (or whole San Diego county when agency unavailable), local date and minute, unordered pair of TWO normalized named roads, fatalities, plus injuries where available. Both-side ambiguous keys and inconsistent duplicate donor records are held. These are high-specificity composite links, NOT exact incident-ID matches. No claim of incident-level certainty is made. Unknown/placeholder road labels are rejected. Date-displacement controls for 2023 provide a specificity diagnostic; they are not formal estimates of false-match rate.

LA County and Pasadena use an independent tier: exact agency-scoped normalized police report number + year, corroborated by date, both roads and injury/fatal counts. LA County publishes a date-only field, so no minute agreement is claimed there. Pasadena additionally requires exact date/minute agreement. Older opaque Pasadena Accidno values are not decoded or guessed.

Candidate points must lie in the correct county (2 km buffer) and, where a Census place is identifiable, city (1 km buffer). CCRS county ordinal codes 1–58 are mapped to California FIPS county codes 001–115 as 2*ordinal-1. City/borough boundaries and road positions can change; screening is a plausibility check, not positional certification.

Regional source-year promotion is conservatively gated on at least 50 existing located matches, median separation <=100 m and at least 95% within 1 km after geography screens. This is a COARSE geocode validation, not a guarantee of sub-kilometre precision. Some published points differ from existing CCRS coordinates by hundreds of metres. Keep the source/method ledger for analyses; do not describe these points as GPS or assume suitability for 250 m cells or road-segment assignment without further validation. Existing coordinates are an imperfect reference and these metrics do not identify which location is correct. Older years failing this gate were held rather than silently merged. Existing large coordinate disagreements are separately flagged, not overwritten. Municipal Sacramento injury rows exhibit hour-only clock patterns and have not been used as reliable minute-level evidence; Pasadena composite-only batches lack adequate located reference samples and were held; its newer exact police-report matches are accepted through the separate ID tier.

No centroid filling, arbitrary average points, fuzzy nearest-place matches or new unmatched crash appends were used. All input coordinates are published source values. Cross-source candidates more than100m apart are held; when sources agree within100m, the declared preference is city-published source first, then regional source (no averaging). Changes apply only to previously missing/nonvalid coordinates.

## Reproduction
Use retained source caches for the exact snapshot. download_ca_other_city_sources.py creates the public city/SANDAG caches; LA County is obtained through its download_gis function using the URL recorded in the source manifest. Previously downloaded SACOG/Orange County caches and their acquisition manifests are retained. Run supplement_ca_other_cities.py (proposal only), validate_ca_composite_negative_controls.py, review_ca_other_city_candidates.py, then supplement_ca_other_cities.py --apply, supplement_ca_lacounty_report_coordinates.py --apply, supplement_ca_pasadena_report_coordinates.py, and audit_ca_other_cities.py. Scripts use the current F: research root; configure paths when relocating. Preserve all prior revision directories and apply these overlays AFTER base harmonization and prior LA/SF/San Jose overlays. A clean rebuild needs a fresh audit/revision directory rather than the previous promotion ledgers. The candidate proposal hashes prevent applying to a changed base. Interrupted writes retain their backup and staged file; Windows transient locks are retried without destroying the original.

These sources do not make California complete. Source coverage differs by county, year and severity. SANDAG is available here through2023; the other regional sources have different endpoints. Earlier failed/insufficient-reference batches, unmatched crashes and unresolved cities remain unfilled. Baseline refers to the current snapshot immediately before THIS revision, including previous159717 CA supplements.
"""
(P/'README.md').write_text(readme,encoding='utf8')
top=g.loc[g.added.gt(0)].head(35);c23=cities.loc[cities.year.eq(2023)&cities.added.gt(0)].sort_values('added',ascending=False).head(25)
links='<p><a href="annual_before_after.csv">Annual counts</a> | <a href="city_year_before_after.csv">All city/year counts</a> | <a href="source_year_additions.csv">Source additions</a> | <a href="source_year_calibration.csv">Calibration (including held batches)</a> | <a href="independent_validation.csv">Independent QA</a> | <a href="README.md">Methods and reproduction</a></p>'
page='<!doctype html><meta charset="utf-8"><title>CA other-city coordinate recovery</title><style>body{font-family:Arial;max-width:1300px;margin:30px auto;line-height:1.5}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:6px;border-bottom:1px solid #ddd;text-align:left}th{background:#edf3f6}</style><h1>CA other-city coordinate recovery</h1><p>'+f"New locations: {summary['new_coordinates']:,}; current located records: {summary['valid_after']:,}/{summary['records']:,}; remaining missing: {summary['missing_pct_after']:.2f}%. Independent QA: PASS."+'</p><p><strong>Partial supplement.</strong> All source files, previously valid points and non-coordinate fields retained. Regional records use composite linkage; LA County uses police report IDs. Geocoded positions are not necessarily GPS or precise enough for road-segment / 250m-grid analysis. Failed or insufficient-reference batches remain held.</p>'+links+'<h2>Annual before/after</h2>'+annual.to_html(index=False,float_format=lambda v:f'{v:.2f}')+'<h2>Largest additions by city (all acquired years)</h2>'+top.to_html(index=False,float_format=lambda v:f'{v:.2f}')+'<h2>2023 city results</h2>'+c23.to_html(index=False,float_format=lambda v:f'{v:.2f}')+'<h2>Outstanding issues</h2><p>Existing coordinate conflicts over5km are retained for review. No assumption is made that one source must be correct. Sacramento municipal injury times show hour-only patterns; they were not treated as minute-precision evidence. Many old regional batches failed location-agreement checks; Pasadena composite-only batches had insufficient reference points; newer exact-report matches were accepted separately. Oakland and other unresolved cities remain unfilled by this revision. California is not fully geocoded.</p>'
(P/'index.html').write_text(page,encoding='utf8');print(json.dumps(summary),flush=True)
