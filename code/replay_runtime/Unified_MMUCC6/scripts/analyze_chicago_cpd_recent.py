"""Separate CPD annual and matched Jan–Sep comparisons; never merge with IDOT."""
import os as _uscrash_paths_os
from pathlib import Path
import pandas as pd
R=Path(_uscrash_paths_os.environ['USCRASH_ROOT']);P=R/'Unified_MMUCC6/qa/Chicago_temporal_2026-10-16';rows=[]
for y in range(2018,2027):
 d=pd.read_csv(R/f'Cities/Chicago/{y}/CPD_crashes.csv',dtype=str,keep_default_na=False,usecols=['crash_date','injuries_fatal','injuries_total','injuries_incapacitating']);dt=pd.to_datetime(d.crash_date,format='mixed',errors='coerce')
 for period,mask in [('available_year',dt.dt.year.eq(y)),('Jan_Sep',dt.dt.year.eq(y)&dt.lt(pd.Timestamp(y,10,1)))]:
  z=d.loc[mask];k=pd.to_numeric(z.injuries_fatal,errors='coerce');inj=pd.to_numeric(z.injuries_total,errors='coerce')
  rows.append(dict(year=y,period=period,crashes=len(z),fatal_crashes=int(k.gt(0).sum()),fatalities=int(k.sum()),injury_crashes=int(inj.gt(0).sum()),fatality_field_available=int(k.notna().sum()),date_max=str(dt.loc[mask].max())))
pd.DataFrame(rows).to_csv(P/'cpd_annual_and_matched_JanSep.csv',index=False)
