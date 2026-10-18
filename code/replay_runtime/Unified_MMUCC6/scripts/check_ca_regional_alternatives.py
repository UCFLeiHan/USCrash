"""Archive and inspect the public SANDAG regional alternative, no data merging."""
import os as _uscrash_paths_os
from pathlib import Path
import requests,json,hashlib,pandas as pd
P=(Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'Unified_MMUCC6/qa/CA_coordinate_recovery_pilot_2026-10-16/regional_alternatives');P.mkdir(exist_ok=True)
B='https://opendata.sandag.org';ID='uzct-sb5t';s=requests.Session()
def get(path,params=None):
    r=s.get(B+path,params=params,timeout=60);r.raise_for_status();return r.json()
meta=get(f'/api/views/{ID}.json');(P/'SANDAG_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
yearcounts=get(f'/resource/{ID}.json',{'$select':'accident_year,count(*) as n,count(latitude_sandag) as latitude_nonnull,count(longitude_sandag) as longitude_nonnull','$group':'accident_year','$order':'accident_year','$limit':100})
severities=get(f'/resource/{ID}.json',{'$where':'accident_year=2023','$select':'collision_severity,count(*) as n','$group':'collision_severity'})
rows=[]
for offset in [0,10000]:
    rows+=get(f'/resource/{ID}.json',{'$where':'accident_year=2023','$order':':id','$offset':offset,'$limit':10000})
assert len(rows)==int(next(x for x in yearcounts if x['accident_year']=='2023')['n'])
(P/'SANDAG_2023_source.json').write_text(json.dumps(rows),encoding='utf-8')
a=pd.DataFrame(rows);lat=pd.to_numeric(a.latitude_sandag,errors='coerce');lon=pd.to_numeric(a.longitude_sandag,errors='coerce')
valid=lat.between(32,34)&lon.between(-118,-116)
a.to_csv(P/'SANDAG_2023_source.csv',index=False,encoding='utf-8-sig')
report={'source':B+f'/d/{ID}','access':'Public API tested successfully, no login used','year_counts':yearcounts,'2023_severity_counts':severities,'2023_downloaded_rows':len(a),'2023_nonblank_ids':int(a.sandag_case_id.notna().sum()),'2023_unique_sandag_ids':int(a.sandag_case_id.nunique()),'2023_coordinates_in_broad_SD_bounds':int(valid.sum()),'sha256':hashlib.sha256((P/'SANDAG_2023_source.json').read_bytes()).hexdigest(),'canonical_data_modified':False,'caution':'Regional San Diego extract, not statewide. API 2023 count differs from dashboard narrative, so source population and snapshot must be reconciled. A nonmissing coordinate does not prove positional accuracy. sandag_case_id appears to concatenate a SWITRS identifier and year; do not strip year or equate it with CCRS ID without validation.'}
(P/'SANDAG_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
