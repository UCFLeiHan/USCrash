import download_us_crashes as d
import json
from concurrent.futures import ThreadPoolExecutor
ut=json.loads((d.META/'expansion'/'UT_service.json').read_text())
for layer in sorted(ut['layers'],key=lambda x:x['name']):
    year=int(layer['name'][-4:])
    try:d.arc_discover('UT','UDOT_crash_locations','https://maps.udot.utah.gov/central/rest/services/TrafficAndSafety/Crash_Locations/MapServer/'+str(layer['id']),fixed_year=year,notes='Official annual point layer; projected geometry converted to WGS84 by published API; preserve original coordinates and all fields.',four_fields='yes; field presence verified')
    except Exception as exc:d.event('source_failed',region='UT',source=layer['name'],error=str(exc))
for region,name,url,date,year,notes,eligibility in [
('FL','FDOT_all_crashes','https://gis.fdot.gov/arcgis/rest/services/Crashes_All/FeatureServer/0','CRASH_DATE','CALENDAR_YEAR','Official statewide public-road crash records. Contains reported/officer and safety-geocoded coordinates, severity, impact type, injury counts.','yes; field presence verified'),
('NC','NCDOT_public_crash_table','https://services.arcgis.com/NuWFvHYDMVmmxMeM/arcgis/rest/services/StatewideCrashTable/FeatureServer/3','Date','Year','Official public statewide dashboard table; no coordinates or geometry. Supplemental archive; cannot perform spatial research from this table alone.','no: public table lacks coordinates')]:
    try:d.arc_discover(region,name,url,date_field=date,year_field=year,notes=notes,four_fields=eligibility,include_null=True)
    except Exception as exc:d.event('source_failed',region=region,source=name,error=str(exc))
d.atomic_json(d.MANIFEST/'expansion2_plan.json',d.JOBS);d.atomic_json(d.MANIFEST/'expansion2_sources.json',d.SOURCES)
print('EXPANSION2 PLAN',len(d.JOBS),flush=True)
with ThreadPoolExecutor(2) as pool:
    for result in pool.map(d.run_job,d.JOBS):d.atomic_json(d.MANIFEST/'expansion2_status.json',[{k:v for k,v in x.items() if k!='meta'} for x in d.JOBS])
print('EXPANSION2 COMPLETE',flush=True)
