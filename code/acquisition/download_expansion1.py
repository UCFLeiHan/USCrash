import download_us_crashes as d
from concurrent.futures import ThreadPoolExecutor
specs=[
('CT','CTDOT_crashes','https://gis.cti.uconn.edu/arcgis/rest/services/Crash_Dashboards/ConnecticutCrash/FeatureServer/0','CrashDate','CrashDateYear','CrashTimeHour gives hour precision; date encoding and geometry need quality review.'),
('CT','CTDOT_persons','https://gis.cti.uconn.edu/arcgis/rest/services/Crash_Dashboards/ConnecticutCrash/FeatureServer/1','CrashDate','CrashDateYear','Person table; link CrashID; not extra crashes.'),
('CT','CTDOT_vehicles','https://gis.cti.uconn.edu/arcgis/rest/services/Crash_Dashboards/ConnecticutCrash/FeatureServer/2','CrashDateTime','CrashDateYear','Vehicle table; link CrashID; not extra crashes.'),
('SD','SDDOT_crashes','https://sdgis.sd.gov/dot/rest/services/TIM/DOT_Crashes/MapServer/0','AccidentDateTime','AccYear','Official statewide crash layer; dates, WGS84 coords, InjurySeverity, MannerOfCollision.'),
('VT','VTrans_public_crashes','https://services1.arcgis.com/NXmBVyW5TaiCXqFs/arcgis/rest/services/CrashPQT/FeatureServer/0','ACCIDENTDATE',None,'Includes reportable and nonreportable records; check whether date contains real time; public geometry precision varies.')]
for region,name,url,date,year,notes in specs:
    try:d.arc_discover(region,name,url,date_field=date,year_field=year,notes=notes,four_fields='candidate; temporal precision requires review',include_null=True)
    except Exception as exc:d.event('source_failed',region=region,source=name,error=str(exc))
d.atomic_json(d.MANIFEST/'expansion1_plan.json',d.JOBS);d.atomic_json(d.MANIFEST/'expansion1_sources.json',d.SOURCES)
print('EXPANSION PLAN',len(d.JOBS),flush=True)
with ThreadPoolExecutor(4) as pool:
    for result in pool.map(d.run_job,d.JOBS):d.atomic_json(d.MANIFEST/'expansion1_status.json',[{k:v for k,v in x.items() if k!='meta'} for x in d.JOBS])
print('EXPANSION1 COMPLETE',flush=True)
