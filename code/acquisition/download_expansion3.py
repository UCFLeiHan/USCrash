import download_us_crashes as d
from concurrent.futures import ThreadPoolExecutor
for region,name,url,date,year,notes,eligible in [
('FL','FDOT_SSOGIS_crashes','https://gis.fdot.gov/arcgis/rest/services/sso/ssogis/FeatureServer/2000','CRASH_DATE','CALENDAR_YEAR','Official SSO statewide public-road crash layer; updated source distinct from legacy Crashes_All. Sources overlap; do not add rows. Retain all injury/type/coordinate/AADT attributes.','yes; field presence verified'),
('OK','OHSO_KAB_crashes_2016_2018','https://services2.arcgis.com/1RKb5IC5HFxsUYMS/arcgis/rest/services/kab_crashes_16_17_18/FeatureServer/0','DATE','YEAR','Official OHSO public-dashboard point layer. Injury/fatal crash subset, not all crash severities; no standard collision manner/type field in this layer.','no: collision type absent; restricted severity coverage')]:
    try:d.arc_discover(region,name,url,date_field=date,year_field=year,notes=notes,four_fields=eligible,include_null=True)
    except Exception as exc:d.event('source_failed',region=region,source=name,error=str(exc))
d.atomic_json(d.MANIFEST/'expansion3_plan.json',d.JOBS);d.atomic_json(d.MANIFEST/'expansion3_sources.json',d.SOURCES)
print('EXPANSION3 PLAN',len(d.JOBS),flush=True)
with ThreadPoolExecutor(2) as pool:
    for result in pool.map(d.run_job,d.JOBS):d.atomic_json(d.MANIFEST/'expansion3_status.json',[{k:v for k,v in x.items() if k!='meta'} for x in d.JOBS])
print('EXPANSION3 COMPLETE',flush=True)
