"""Read-only MO 2023-2026 coverage audit; preserve current public count evidence.

Annual report counts are versioned preliminary references, not final census truth.
Never estimate missing records or extrapolate a full year from current-year data.
"""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
import requests

U=Path(__file__).resolve().parents[1]
O=U/'qa/external_validation_2026-10-14'
SERVICE='https://www.mshp.dps.missouri.gov/arcgis/rest/services/STARS_CRASHES/MapServer/0'

def main():
    now=datetime.now(timezone.utc).isoformat();rows=[];snapshots=[];months=[];agencies=[]
    refs={2023:(136516,'MO_2023_Annual_Report.pdf',45),
          2024:(103960,'MO_2024_Annual_Report.pdf',45),
          2025:(105195,'MO_2025_Annual_Report.pdf',47)}
    for year in [2023,2024,2025,2026]:
        p=U.parent/'States/MO'/str(year)/f'MO_crashes_{year}.csv'
        d=pd.read_csv(p,usecols=['ACCIDENT','ACC_DATE','AGENCY','COUNTY','SEVERITY','GPS_LAT','GPS_LONG'],dtype=str,keep_default_na=False)
        assert d.ACCIDENT.is_unique
        dates=pd.to_datetime(d.ACC_DATE,errors='raise');assert dates.dt.year.eq(year).all()
        where=f"ACC_DATE >= DATE '{year}-01-01' AND ACC_DATE < DATE '{year+1}-01-01'"
        response=requests.get(SERVICE+'/query',params=dict(f='json',where=where,returnCountOnly='true'),timeout=90)
        response.raise_for_status();j=response.json();assert 'count' in j and 'error' not in j
        snapshots.append(dict(year=year,url=response.url,queried_utc=now,result=j))
        official,file,page=refs.get(year,(None,None,None))
        status=('AGGREGATE_WITHIN_1PCT_NOT_CENSUS_VERIFIED' if year==2023 else
                'CONFIRMED_PUBLIC_LAYER_BELOW_ANNUAL_REPORT_SNAPSHOT' if year<2026 else
                'YTD_ONLY_COVERAGE_UNVERIFIED_SAME_SOURCE_AS_DEFICIENT_2024_2025')
        lat=pd.to_numeric(d.GPS_LAT,errors='coerce');lon=pd.to_numeric(d.GPS_LONG,errors='coerce')
        rows.append(dict(year=year,local_rows=len(d),live_public_layer_rows=int(j['count']),
                    live_minus_local_row_count=int(j['count'])-len(d),official_annual_snapshot=official,
                    local_difference_pct=((len(d)-official)/official*100) if official else None,
                    live_difference_pct=((j['count']-official)/official*100) if official else None,
                    first_date=dates.min().date().isoformat(),last_date=dates.max().date().isoformat(),
                    observed_months=int(dates.dt.month.nunique()),agencies=int(d.AGENCY.nunique()),
                    counties=int(d.COUNTY.nunique()),zero_or_missing_gps=int((lat.fillna(0).eq(0)|lon.fillna(0).eq(0)).sum()),
                    coverage_status=status,reference_file=file,pdf_page=page,
                    raw_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
        for month,n in dates.dt.month.value_counts().sort_index().items():months.append(dict(year=year,month=int(month),records=int(n)))
        for agency,n in d.AGENCY.value_counts().items():agencies.append(dict(year=year,agency=agency,records=int(n)))
    pd.DataFrame(rows).to_csv(O/'MO_2023_2026_coverage_audit.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(months).to_csv(O/'MO_recent_monthly_counts.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(agencies).to_csv(O/'MO_recent_agency_counts.csv',index=False,encoding='utf-8-sig')
    (O/'reference/MO_live_layer_counts_recent_review.json').write_text(json.dumps(snapshots,indent=2),encoding='utf-8')
    print(pd.DataFrame(rows).drop(columns=['raw_sha256']).to_string(index=False),flush=True)

if __name__=='__main__':main()
