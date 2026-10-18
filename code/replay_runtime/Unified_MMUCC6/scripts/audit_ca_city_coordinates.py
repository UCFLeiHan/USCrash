"""Audit original CCRS coordinate availability by city/year and reporting code.
Read only; no coordinate imputation or canonical data mutation.
"""
import os as _uscrash_paths_os
from pathlib import Path
import json,hashlib
import pandas as pd
import numpy as np
R=Path(_uscrash_paths_os.environ['USCRASH_ROOT']);P=R/'Unified_MMUCC6/qa/CA_city_coordinate_audit_2026-10-16';P.mkdir(exist_ok=True)
city_rows=[];agency_rows=[];state_rows=[];sources=[]
need=['City Name','Latitude','Longitude','NCIC Code','IsFreeway']
for year in range(2016,2027):
    f=R/f'States/CA/{year}/Crashes_{year}.csv';city_parts=[];agency_parts=[]
    for a in pd.read_csv(f,dtype=str,keep_default_na=False,usecols=lambda c:c.strip() in need,chunksize=200000):
        a.columns=a.columns.str.strip()
        lat=pd.to_numeric(a.Latitude,errors='coerce');lon=pd.to_numeric(a.Longitude,errors='coerce')
        valid=lat.between(32.3,42.2)&lon.between(-124.6,-113.9)
        a['city']=a['City Name'].str.strip().replace('','[BLANK]');a['agency']=a['NCIC Code'].str.strip().replace('','[BLANK]')
        a['rows']=1;a['valid']=valid.astype(int)
        a['missing_pair']=(lat.isna()|lon.isna()).astype(int)
        a['zero_pair']=(lat.eq(0)|lon.eq(0)).astype(int)
        a['positive_west_candidate']=(lat.between(32.3,42.2)&lon.between(113.9,124.6)).astype(int)
        a['freeway']=a.IsFreeway.eq('True').astype(int)
        a['freeway_valid']=(a.IsFreeway.eq('True')&valid).astype(int)
        a['nonfreeway_explicit']=a.IsFreeway.eq('False').astype(int)
        a['nonfreeway_explicit_valid']=(a.IsFreeway.eq('False')&valid).astype(int)
        a['freeway_unspecified']=a.IsFreeway.eq('').astype(int)
        a['freeway_unspecified_valid']=(a.IsFreeway.eq('')&valid).astype(int)
        cols=['rows','valid','missing_pair','zero_pair','positive_west_candidate','freeway','freeway_valid','nonfreeway_explicit','nonfreeway_explicit_valid','freeway_unspecified','freeway_unspecified_valid']
        city_parts.append(a.groupby('city')[cols].sum())
        agency_parts.append(a.groupby(['city','agency'])[cols].sum())
    c=pd.concat(city_parts).groupby(level=0).sum().reset_index();c.insert(0,'year',year)
    c['coordinate_pct']=100*c.valid/c.rows
    ag=pd.concat(agency_parts).groupby(level=[0,1]).sum().reset_index();ag.insert(0,'year',year);ag['coordinate_pct']=100*ag.valid/ag.rows
    city_rows.append(c);agency_rows.append(ag)
    s={'year':year,**{k:int(c[k].sum()) for k in cols}};s['coordinate_pct']=100*s['valid']/s['rows'];state_rows.append(s)
    sources.append({'year':year,'file':str(f),'bytes':f.stat().st_size,'mtime_ns':f.stat().st_mtime_ns})
    print(year,s['rows'],round(s['coordinate_pct'],2),'LA',c.loc[c.city.eq('Los Angeles'),['rows','valid','coordinate_pct']].to_dict('records'),flush=True)
c=pd.concat(city_rows,ignore_index=True);ag=pd.concat(agency_rows,ignore_index=True)
c.to_csv(P/'all_city_year_coordinate_completeness.csv',index=False,encoding='utf-8-sig')
ag.to_csv(P/'all_city_agency_year_coordinate_completeness.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(state_rows).to_csv(P/'state_year_coordinate_completeness.csv',index=False,encoding='utf-8-sig')
chosen=['Los Angeles','San Diego','San Francisco','San Jose','Sacramento','Fresno','Oakland','Long Beach','Bakersfield','Anaheim','Riverside','Stockton']
table=c.loc[c.city.isin(chosen)].pivot(index='year',columns='city',values='coordinate_pct').reindex(columns=chosen)
table.to_csv(P/'selected_cities_coordinate_percent_by_year.csv',encoding='utf-8-sig')
report={'scope':'Original CCRS annual crash files, 2016–2026. 2026 YTD; earlier file completeness is not established by this audit.','valid_definition':'Numeric latitude/longitude inside configured CA bounding box [-124.6,32.3,-113.9,42.2]. Not a geocoding accuracy validation.','city_definition':'Original City Name label; no polygon or geocoding-based city imputation.','sources':sources,'source_data_modified':False,'state_years':state_rows,'selected_city_percentages':json.loads(table.reset_index().to_json(orient='records')),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(P/'audit_manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('SELECTED 2023',c.loc[c.year.eq(2023)&c.city.isin(chosen),['city','rows','valid','coordinate_pct']].to_string(index=False))
print('PERCENTAGES',table.round(1).to_string())
print('DONE',P)
