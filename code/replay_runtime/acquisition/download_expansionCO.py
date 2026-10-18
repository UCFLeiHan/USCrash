import download_us_crashes as d
from concurrent.futures import ThreadPoolExecutor
for name,url in [
('JeffersonCounty_crashes_2011_2015','https://services3.arcgis.com/9ntQlfNHEhmpX4cl/arcgis/rest/services/Crash/FeatureServer/1'),
('JeffersonCounty_crashes_2016_2019','https://services3.arcgis.com/9ntQlfNHEhmpX4cl/arcgis/rest/services/Crash_2016___June_2019/FeatureServer/1')]:
    try:
        d.arc_discover('CO',name,url,date_field='DATE_' if '2016_2019' in name else None,year_field=None if '2016_2019' in name else 'YEAR',notes='Jefferson County, Colorado local-government dataset; county scope, NOT statewide. In the 2016-June2019 layer YEAR is zero; calendar partitions use DATE_ and preserve the original YEAR field. Official county page explicitly provides public geolocated 2011-June2019 downloads: https://www.jeffco.us/4046/Crash-Analysis . Retain coded severity/type fields and original reported coordinates plus WGS84 geometry.',four_fields='yes in published schema; county coverage only',include_null=True)
        d.SOURCES[-1]['scope']='Jefferson County, Colorado; not statewide'
    except Exception as exc:d.event('source_failed',region='CO',source=name,error=str(exc))
d.atomic_json(d.MANIFEST/'expansionCO_plan.json',d.JOBS);d.atomic_json(d.MANIFEST/'expansionCO_sources.json',d.SOURCES)
with ThreadPoolExecutor(2) as pool:
    for result in pool.map(d.run_job,d.JOBS):d.atomic_json(d.MANIFEST/'expansionCO_status.json',[{k:v for k,v in j.items() if k!='meta'} for j in d.JOBS])
print('COLORADO COUNTY SUPPLEMENT COMPLETE',flush=True)
