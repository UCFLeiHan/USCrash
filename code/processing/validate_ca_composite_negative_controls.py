"""Date-displacement negative controls; diagnostic, not a formal false-match rate."""
import pandas as pd,json
from pathlib import Path
from pilot_ca_composite_coordinates import R,U,S,P,prepare
P=U/'qa/CA_other_cities_2026-10-16';rows=[]
y=2023
fields=['Collision Id','NCIC Code','Crash Date Time','PrimaryRoad','SecondaryRoad','NumberKilled','NumberInjured','County Code']
a=pd.read_csv(R/f'States/CA/{y}/Crashes_{y}.csv',dtype=str,keep_default_na=False,usecols=lambda c:c.strip() in fields);a.columns=a.columns.str.strip();a=a.rename(columns={'Collision Id':'id','NCIC Code':'agency','PrimaryRoad':'road1','SecondaryRoad':'road2','NumberKilled':'killed','NumberInjured':'injured','County Code':'county'});a['dt']=pd.to_datetime(a['Crash Date Time'],format='%m/%d/%Y %I:%M:%S %p',errors='coerce');a['county']=a.county.str.lstrip('0');a=prepare(a)
for name,keys in [('SACOG',['minute','agency','roads']),('OrangeCounty_TIMS',['minute','agency','roads']),('SANDAG',['minute','county','roads'])]:
 b=pd.read_csv(S/name/'reviewed_composite_coordinate_extract.csv',dtype=str,keep_default_na=False);b=b.loc[b.year.eq(str(y))];aa=a.loc[~a.duplicated(keys,keep=False)]
 for days in [0,-28,-14,-7,7,14,28]:
  c=b.copy();d=pd.to_datetime(c.minute,format='%Y-%m-%dT%H:%M')+pd.Timedelta(days=days);c['minute']=d.dt.strftime('%Y-%m-%dT%H:%M');c=c.loc[d.dt.year.eq(y)]
  m=aa.merge(c,on=keys,suffixes=('_raw','_donor'),validate='one_to_one')
  for field in ['killed','injured']:
   if field+'_donor' in m:m=m.loc[pd.to_numeric(m[field+'_raw'],errors='coerce').eq(pd.to_numeric(m[field+'_donor'],errors='coerce'))]
  rows.append(dict(source=name,year=y,date_shift_days=days,donor_records=len(c),matching_records=len(m)));print(rows[-1],flush=True)
pd.DataFrame(rows).to_csv(P/'date_displacement_negative_controls.csv',index=False)
