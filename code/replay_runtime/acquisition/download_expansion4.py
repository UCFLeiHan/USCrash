import download_us_crashes as d
from concurrent.futures import ThreadPoolExecutor
for year in range(2007,2011):
    try:d.arc_discover('FL','FDOT_SSOGIS_crashes','https://gis.fdot.gov/arcgis/rest/services/sso/ssogis/FeatureServer/'+str(year),fixed_year=year,notes='Official SSO independent annual layer; these early years are omitted by the published All Crashes layer. Preserve all fields.',four_fields='yes; geometry and raw attributes retained')
    except Exception as exc:d.event('source_failed',region='FL',source=str(year),error=str(exc))
try:d.arc_discover('TN','TDOSHS_TITAN_pulled_crashes','https://services8.arcgis.com/LXsQ6ODUaTWmnnpV/arcgis/rest/services/TITAN_Dashboard_Crashes__12_03_25_WFL1/FeatureServer/17',date_field='Collision_Date',year_field='Collision_Year',notes='Official owner sarah.fielden@tn.gov. Public dashboard All Pulled Crash Records layer; completeness/severity coverage must be audited before treating it as all reportable crashes.',four_fields='candidate; Crash_Type and First_Harmfu_Event roles require interpretation',include_null=True)
except Exception as exc:d.event('source_failed',region='TN',source='TITAN_public',error=str(exc))
d.atomic_json(d.MANIFEST/'expansion4_plan.json',d.JOBS);d.atomic_json(d.MANIFEST/'expansion4_sources.json',d.SOURCES)
print('EXPANSION4 PLAN',len(d.JOBS),flush=True)
with ThreadPoolExecutor(2) as pool:
    for result in pool.map(d.run_job,d.JOBS):d.atomic_json(d.MANIFEST/'expansion4_status.json',[{k:v for k,v in x.items() if k!='meta'} for x in d.JOBS])
print('EXPANSION4 COMPLETE',flush=True)
