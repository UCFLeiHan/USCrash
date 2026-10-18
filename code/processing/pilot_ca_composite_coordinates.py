import pandas as pd,numpy as np,re,json
from pathlib import Path
R=Path(r'F:\LH_Research\USCrash\Crash');U=R/'Unified_MMUCC6';S=R/'States/CA/Local_coordinate_sources_2026-10-16';P=U/'qa/CA_other_cities_2026-10-16';P.mkdir(exist_ok=True)
def road(v):
 s=re.sub(r'[^A-Z0-9 ]',' ',str(v).upper());s=re.sub(r'^\s*\d+\s+','',s);d={'STREET':'ST','AVENUE':'AVE','AV':'AVE','BOULEVARD':'BLVD','ROAD':'RD','DRIVE':'DR','HIGHWAY':'HWY','NORTH':'N','SOUTH':'S','EAST':'E','WEST':'W'};return ' '.join(d.get(t,t) for t in s.split())
def prepare(d):
 d=d.copy();d['minute']=pd.to_datetime(d.dt,format='mixed',errors='coerce').dt.strftime('%Y-%m-%dT%H:%M');d['agency']=d.agency.fillna('').astype(str).str.replace(r'\.0$','',regex=True).str.lstrip('0')
 d['r1']=d.road1.fillna('').map(road);d['r2']=d.road2.fillna('').map(road)
 d=d.loc[d.minute.notna()&d.r1.ne('')&d.r2.ne('')&d.r1.ne(d.r2)].copy();d['roads']=['|'.join(sorted([a,b])) for a,b in zip(d.r1,d.r2)];return d
if __name__=='__main__':
 year=2023
 a=pd.read_csv(R/f'States/CA/{year}/Crashes_{year}.csv',dtype=str,keep_default_na=False);a.columns=a.columns.str.strip();a=a.rename(columns={'Collision Id':'id','NCIC Code':'agency','PrimaryRoad':'road1','SecondaryRoad':'road2','NumberKilled':'killed','NumberInjured':'injured','City Name':'city','County Code':'county'})
 a['dt']=pd.to_datetime(a['Crash Date Time'],format='%m/%d/%Y %I:%M:%S %p',errors='coerce');a=prepare(a)
 c=pd.read_csv(U/f'data/crash/CA/CA_crashes_harmonized_{year}.csv',dtype=str,keep_default_na=False,usecols=['source_crash_id','latitude','longitude','coordinate_status']);a=a.merge(c,left_on='id',right_on='source_crash_id',validate='one_to_one')
 donors=[]
 b=pd.read_csv(S/f'SACOG/coordinate_extract_{year}.csv',dtype=str,keep_default_na=False).rename(columns={'join_id':'donor_id','NUMBER_KILLED':'killed','NUMBER_INJURED':'injured'});donors.append(('SACOG',b,['minute','agency','roads']))
 b=pd.read_csv(S/'OrangeCounty_TIMS/coordinate_extract_1672531200000.csv',dtype=str,keep_default_na=False).rename(columns={'join_id':'donor_id','number_killed':'killed'});donors.append(('OrangeCounty',b,['minute','agency','roads']))
 b=pd.read_csv(U/'qa/CA_coordinate_recovery_pilot_2026-10-16/regional_alternatives/SANDAG_2023_source.csv',dtype=str,keep_default_na=False).rename(columns={'sandag_case_id':'donor_id','primary_rd':'road1','secondary_rd':'road2','latitude_sandag':'candidate_lat','longitude_sandag':'candidate_lon','number_killed':'killed','number_injured':'injured'});b['agency']='';b['county']='37';b['dt']=pd.to_datetime(b.collision_date,format='mixed',errors='coerce').dt.normalize()+pd.to_timedelta(pd.to_datetime(b.collision_time,format='mixed',errors='coerce').dt.strftime('%H:%M:%S'));donors.append(('SANDAG',b,['minute','county','roads']))
 results=[]
 for name,b,keys in donors:
  b=prepare(b);use=['donor_id','candidate_lat','candidate_lon','killed']+keys+(['injured'] if 'injured' in b else [])
  b=b[use].drop_duplicates();b=b.loc[~b.donor_id.duplicated(keep=False)&~b.duplicated(keys,keep=False)]
  aa=a.loc[~a.duplicated(keys,keep=False)].copy();m=aa.merge(b,on=keys,suffixes=('_raw','_donor'),validate='one_to_one')
  for k in ['killed','injured']:
   if k+'_donor' in m:m=m.loc[pd.to_numeric(m[k+'_raw'],errors='coerce').eq(pd.to_numeric(m[k+'_donor'],errors='coerce'))]
  for f in ['latitude','longitude','candidate_lat','candidate_lon']:m[f]=pd.to_numeric(m[f],errors='coerce')
  m=m.loc[m.candidate_lat.between(32.3,42.2)&m.candidate_lon.between(-124.6,-113.9)].copy()
  v=m.coordinate_status.eq('VALID')&m.latitude.between(-90,90)&m.longitude.between(-180,180)
  m['distance_m']=6371008.8*2*np.arcsin(np.minimum(1,np.sqrt(np.sin(np.radians(m.latitude-m.candidate_lat)/2)**2+np.cos(np.radians(m.latitude))*np.cos(np.radians(m.candidate_lat))*np.sin(np.radians(m.longitude-m.candidate_lon)/2)**2)))
  known=m.loc[v,'distance_m'];m.to_csv(P/f'{name}_2023_composite_pilot.csv',index=False)
  x=dict(source=name,matched=len(m),known=len(known),missing=int((~v).sum()),median=float(known.median()),p95=float(known.quantile(.95)),within250=float(known.le(250).mean()),within1000=float(known.le(1000).mean()));results.append(x);print(x,flush=True)
 pd.DataFrame(results).to_csv(P/'pilot_summary.csv',index=False)
