"""Summarize the two recorded passes and normalized-key withdrawals."""
from pathlib import Path
import json,hashlib
import pandas as pd
from supplement_ca_coordinates import U,sha
V1=U/'qa/CA_coordinate_supplement_2026-10-16';V2=U/'qa/CA_coordinate_supplement_2026-10-16_010438'
a=json.loads((V1/'run_manifest.json').read_text());b=json.loads((V2/'run_manifest.json').read_text());c=json.loads((V2/'reconciliation_manifest.json').read_text())
withdraw={r['year']:r for r in c['runs']};bypre={r['year']:r for r in a['years']}
records=[]
for r in b['years']:
 y=r['year'];w=withdraw.get(y,{});file=U/f'data/crash/CA/CA_crashes_harmonized_{y}.csv'
 actual=sha(file);assert actual==w.get('sha256_after',r['sha256_after'])
 records.append({'year':y,'rows':r['rows'],'v1_filled':bypre[y]['filled'],'v2_added':r['filled'],'withdrawn_ambiguous_v1':w.get('withdrawn',0),'net_recovered_from_original':bypre[y]['filled']+r['filled']-w.get('withdrawn',0),'final_sha256':actual,'status':'PASS'})
df=pd.DataFrame(records);df.to_csv(V2/'final_annual_accounting.csv',index=False)
latlon=pd.read_csv(U/'data/crash/CA/CA_crashes_harmonized_2023.csv',dtype=str,keep_default_na=False,usecols=['crash_uid','latitude','longitude','city'])
base=pd.read_csv(V1/'canonical_before/CA_crashes_harmonized_2023.csv',dtype=str,keep_default_na=False,usecols=['crash_uid','latitude','longitude','city'])
valid=lambda d:pd.to_numeric(d.latitude,errors='coerce').between(32.3,42.2)&pd.to_numeric(d.longitude,errors='coerce').between(-124.6,-113.9)
assert latlon.crash_uid.equals(base.crash_uid)
coverage=[]
for city in ['ALL','Los Angeles','San Francisco','San Jose']:
 mask=pd.Series(True,index=base.index) if city=='ALL' else base.city.eq(city)
 coverage.append({'city':city,'year':2023,'records':int(mask.sum()),'coordinates_original':int((mask&valid(base)).sum()),'coordinates_final':int((mask&valid(latlon)).sum())})
pd.DataFrame(coverage).to_csv(V2/'final_2023_coordinate_coverage.csv',index=False)
summary={'status':'COMPLETED_AND_CHECKED','rule_version':'CA_LOCAL_COORDINATES_v2_LAPD_NINE_DIGITS','columns':77,'raw_data_modified':False,'new_crashes_added':0,'total_filled_since_original':int(df.net_recovered_from_original.sum()),'v2_added':b['total_filled'],'withdrawn_earlier_ambiguous_supplements':c['total_withdrawn'],'qa_directory':str(V2),'previous_pass':str(V1),'by_source':{'Los Angeles':45991+b['total_filled']-c['total_withdrawn'],'San Francisco':26140,'San Jose':1687},'coverage_2023':coverage,'reproduction':'Run scripts/supplement_ca_coordinates.py v2 on the pre-supplement canonical baseline. Retain the source caches and change ledgers. Withdrawals reconcile the historical incremental v1+v2 execution; fresh v2 excludes ambiguous normalized keys automatically.','limitations':'Remaining coordinate gaps and source-population differences persist. Block/intersection geocodes are not exact crash GPS. Existing valid original coordinates were not replaced.'}
(V2/'final_revision_manifest.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
(U/'data/crash/CA/coordinate_supplement_manifest.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
(V2/'README.md').write_text('''# CA coordinate supplementation: normalized LAPD report identifiers

The earlier original-string join missed report numbers such as `23-12-04719`, whose LAPD DR Number is `231204719`. Version 2 removes non-digit separators for LAPD only, requires exactly nine digits, and rejects duplicate normalized keys. No padding, truncation, guessed digits or fuzzy report-number matching is allowed. Exact date/minute, agreeing normalized road and city-buffer coordinate screens remain required.

See `final_revision_manifest.json` and `final_annual_accounting.csv` for the final, independently hash-checked result. `CA_YEAR_coordinate_changes.csv` records additional v2 replacements; earlier replacements remain in the referenced v1 ledger. `CA_YEAR_withdrawn_v1_supplements.csv` withdraws 18 earlier v1 points that no longer pass normalized-key uniqueness, restoring their pre-supplement values. These withdrawals change coordinates only, never remove crash records. `canonical_before/` preserves files before the incremental v2 pass. `independent_validation.csv` documents the pre-withdrawal v2 output checks, while `reconciliation_manifest.json` and final hashes document the subsequent withdrawals.

For complete per-coordinate provenance keep both pass directories and the withdrawal ledgers. Raw agency files, crash counts, source identifiers and all non-coordinate fields remain unchanged. The canonical table remains 77 columns. Running current `scripts/supplement_ca_coordinates.py` on the original pre-supplement baseline applies normalized-key uniqueness directly. Regional source downloads have separate audit results; unverified SWITRS-to-CCRS identifier correspondence is not assumed.

City name coverage uses source labels; figure inclusion uses Census polygons. They are different diagnostics. Los Angeles still has missing coordinates and the map is not a complete city crash distribution.
''',encoding='utf-8')
print(json.dumps(summary,indent=2),flush=True)
