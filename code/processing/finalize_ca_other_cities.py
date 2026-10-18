"""Publish current CA revision manifest and reconcile refreshed canonical availability."""
import json,shutil,sys,platform
from pathlib import Path
import pandas as pd,numpy as np,geopandas as gpd,shapely
from coordinate_supplement_utils import U,R,sha
P=U/'qa/CA_other_cities_2026-10-16';s=json.loads((P/'summary.json').read_text());assert (P/'Pasadena_promotion_manifest.json').exists()
a=pd.read_csv(Path(r'F:\LH_Research\USCrash\Paper\Analysis\coverage')/'annual_field_availability.csv');a=a.loc[a.state.eq('CA')&a.field.eq('latitude'),['year','records','valid']];b=pd.read_csv(P/'annual_before_after.csv');m=a.merge(b[['year','records','valid_after']],on='year',suffixes=('_scan','_ledger'),validate='one_to_one');assert len(m)==11 and m.records_scan.eq(m.records_ledger).all() and m.valid.eq(m.valid_after).all();m['status']='PASS';m.to_csv(P/'full_coordinate_scan_reconciliation.csv',index=False)
d=pd.read_csv(P/'all_coordinate_changes.csv',dtype=str,keep_default_na=False)
g=gpd.read_file(P/'CA_counties.geojson').to_crs(3310);g.geometry=g.geometry.buffer(2000);g=g.to_crs(4326);polys=dict(zip(((g.COUNTY.astype(int)+1)//2).astype(str),g.geometry));passed=pd.Series(False,index=d.index)
for county,z in d.groupby('county'):
 key=str(int(county))
 if key in polys:passed.loc[z.index]=shapely.covers(polys[key],shapely.points(pd.to_numeric(z.candidate_lon),pd.to_numeric(z.candidate_lat)))
assert passed.all(),'New point fails independent county validation'
pd.DataFrame({'crash_uid':d.crash_uid,'county_screen_pass':passed}).to_csv(P/'independent_county_screen.csv',index=False)
s['independent_new_point_county_screen']='PASS'
s['full_current_CA_scan_reconciled']=True;(P/'summary.json').write_text(json.dumps(s,indent=2));(U/'CA_coordinate_recovery_manifest.json').write_text(json.dumps({**s,'report':str(P/'index.html'),'revision_directory':str(P)},indent=2))
manifest=U/'data/crash/CA/coordinate_supplement_manifest.json';oldfile=P/'coordinate_supplement_manifest_before_this_revision.json'
if not oldfile.exists():shutil.copy2(manifest,oldfile)
old=json.loads(oldfile.read_text());src=pd.read_csv(P/'source_year_additions.csv').groupby('coordinate_source').added.sum().to_dict();by_source={**old['by_source'],**{k:int(v) for k,v in src.items()}}
new=dict(status='COMPLETED_AND_INDEPENDENTLY_CHECKED',rule_version='CA_LOCAL_COORDINATES_V3_EXACT_REPORT_AND_REVIEWED_COMPOSITE',columns=77,raw_data_modified=False,new_crashes_added=0,total_filled_since_original=old['total_filled_since_original']+s['new_coordinates'],this_revision_added=s['new_coordinates'],by_source=by_source,records=s['records'],coordinates_valid_current=s['valid_after'],missing_current=s['missing_after'],missing_pct_current=s['missing_pct_after'],qa_directory=str(P),previous_pass=old['qa_directory'],previous_manifest_snapshot=str(oldfile),annual_coverage=str(P/'annual_before_after.csv'),coverage_2023=str(P/'city_2023_before_after.csv'),coordinate_change_ledger=str(P/'all_coordinate_changes.csv'),provenance_warning='Keep the ledger. Regional additions use high-specificity composite fingerprints; LA County/Pasadena use exact police report IDs with corroboration. Published geocodes are not necessarily measured GPS or suitable for fine road/grid assignment. Existing valid coordinates are not overwritten; unresolved conflicts remain flagged.')
new={**old,**new}
coverage=[];city2023=pd.read_csv(P/'city_2023_before_after.csv');annual2023=b.loc[b.year.eq(2023)].iloc[0]
for original in old.get('coverage_2023',[]):
 item=original.copy()
 if item['city']=='ALL':item['coordinates_final']=int(annual2023.valid_after)
 else:
  z=city2023.loc[city2023['City Name'].eq(item['city'])]
  if len(z):item['coordinates_final']=int(z.valid_after.sum())
 coverage.append(item)
new['coverage_2023']=coverage;new['coverage_2023_all_cities_file']=str(P/'city_2023_before_after.csv');assert sum(new['by_source'].values())==new['total_filled_since_original']
manifest.write_text(json.dumps(new,indent=2),encoding='utf8');(P/'final_revision_manifest.json').write_text(json.dumps(new,indent=2),encoding='utf8')
(P/'runtime_versions.json').write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),pandas=pd.__version__,numpy=np.__version__,geopandas=gpd.__version__,shapely=shapely.__version__),indent=2))
page=P/'index.html';text=page.read_text(encoding='utf8').replace('<h1>CA other-city coordinate recovery</h1>','<h1>CA other-city coordinate recovery</h1><p>Final current-file coordinate scan reconciled: <strong>PASS</strong>. <a href="full_coordinate_scan_reconciliation.csv">Reconciliation</a> | <a href="all_coordinate_changes.csv">All row-level changes</a> | <a href="date_displacement_negative_controls.csv">Date-displacement controls</a></p>');page.write_text(text,encoding='utf8')
# Previous nationwide report remains an immutable historical snapshot, with an explicit later-revision pointer.
f=U/'coordinate_recovery_manifest.json'
if f.exists():
 j=json.loads(f.read_text());j['historical_snapshot_only']=True;j['subsequent_CA_revision']=str(U/'CA_coordinate_recovery_manifest.json');f.write_text(json.dumps(j,indent=2),encoding='utf8')
shutil.copy2(Path(__file__),P/'executed_scripts'/Path(__file__).name)
print(json.dumps(s),flush=True)
