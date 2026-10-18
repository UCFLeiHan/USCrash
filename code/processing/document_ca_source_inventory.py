"""Document archived public source coverage, linkage tiers and clock limitations."""
import json,pandas as pd
from pathlib import Path
R=Path(r'F:\LH_Research\USCrash\Crash');U=R/'Unified_MMUCC6';P=U/'qa/CA_other_cities_2026-10-16';S=R/'States/CA/Local_coordinate_sources_2026-10-16';rows=[]
def load(name):
 records=[]
 for p in (S/name).glob('batch_*.json'):records.extend(x['attributes'] for x in json.loads(p.read_text())['features'])
 return pd.DataFrame(records)
clock=load('SacramentoCity');clock['minute_zero']=pd.to_datetime(clock.Collision_Time.astype(str),format='mixed',errors='coerce').dt.minute.eq(0);clock.groupby('Highest_Degree_of_Injury').agg(records=('minute_zero','size'),fraction_minute_zero=('minute_zero','mean')).to_csv(P/'SacramentoCity_clock_precision_diagnostic.csv')
def add(name,kind,rule,precision,notes):
 manifest=S/name/'download_manifest.json'
 if manifest.exists():
  j=json.loads(manifest.read_text());count=j.get('downloaded',j.get('records_downloaded',j.get('count',0)));url=j.get('source',j.get('url',''))
 else:
  js=[json.loads(p.read_text()) for p in (S/name).glob('manifest_*.json')];count=sum(x['downloaded'] for x in js);url='https://opendata.sandag.org/resource/uzct-sb5t.json'
 f=S/name/('reviewed_exact_report_coordinate_extract.csv' if name in ['Pasadena','LACountyReports'] else 'reviewed_composite_coordinate_extract.csv');b=pd.read_csv(f,dtype=str,keep_default_na=False);year=b.year if 'year' in b else pd.to_datetime(b.dt,format='mixed').dt.year.astype(str)
 rows.append(dict(source=name,official_public_service=url,downloaded_source_rows=count,source_record_level=kind,prepared_rows=len(b),prepared_year_min=year.min(),prepared_year_max=year.max(),linkage=rule,coordinate_basis=precision,limitations=notes))
add('SACOG','Crash points','Unique agency/date/minute/two roads/fatalities/injuries','Published GIS geometry exported EPSG4326','Only passing source-year batches promoted; source coverage is not all California crashes.')
add('OrangeCounty_TIMS','Joined crash/party/victim rows','Collapse consistent case_id then unique agency/date/minute/two roads/fatalities','Published GIS geometry exported EPSG4326','date_year is an ArcGIS date/epoch field, not a literal calendar year; year derived from collision date. Overlapping entity rows are not new crashes. Injury-focused source.')
add('SANDAG','Crash points','Unique county/date/minute/two roads/fatalities/injuries','Official latitude_sandag/longitude_sandag geocodes','Downloaded2016–2023; agency unavailable in selected source, so uniqueness is required across the whole county. No2024+ records claimed.')
add('LACountyReports','Crash points','Exact agency-scoped police report/year + date/both roads/counts','Published GIS geometry exported EPSG4326','2017–2021 regional extract. Date-only field; no minute agreement claimed. Most matching points were already present.')
add('Pasadena','Crash points','Exact Accidno/police report + agency1953/date/minute/both roads/counts','Published GIS geometry exported EPSG4326','Older opaque Accidno values not decoded. Separate exact-ID tier used despite insufficient samples for the composite-only tier.')
add('SacramentoCity','Crash points','Held: no safe minute-level injury link or adequate reference sample','Published GIS geometry exported EPSG4326','Injury rows show minute00 throughout; PDO rows preserve finer clocks. No municipal-only coordinates promoted by this source; Sacramento additions come from SACOG.')
pd.DataFrame(rows).to_csv(P/'source_inventory.csv',index=False,encoding='utf-8-sig');print('SOURCE INVENTORY',len(rows))
