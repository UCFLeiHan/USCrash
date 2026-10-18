"""Audited coordinate-only promotions. All other canonical fields are immutable."""
from pathlib import Path
import hashlib,json,shutil,os,time
import pandas as pd
import geopandas as gpd
import shapely
R=Path(os.environ.get('USCRASH_CRASH_ROOT',r'F:\LH_Research\USCrash\Crash'))
U=Path(os.environ.get('USCRASH_UNIFIED_ROOT',str(R/'Unified_MMUCC6')))
REV=Path(os.environ.get('USCRASH_COORDINATE_AUDIT_ROOT',str(U/'qa/coordinate_recovery_2026-10-16')))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def state_polygon(state):
 paths=[Path(os.environ.get('USCRASH_CENSUS_STATES',r'F:\LH_Research\USCrash\Crash\verification\reference\census_states.zip'))]
 for p in paths:
  if p.exists():
   g=gpd.read_file(p);g=g.loc[g.STUSPS.eq(state)].to_crs(5070);g.geometry=g.geometry.buffer(2000);return g.to_crs(4326).geometry.iloc[0]
 raise FileNotFoundError('Archived Census state polygons required')
def apply(state,year,donor,revision):
 """Donor has unique crash_uid, candidate_lat/lon and all provenance columns.
 Identifier, date and other linkage validation must be done by caller first.
 """
 out=REV/revision;out.mkdir(parents=True,exist_ok=True)
 path=U/f'data/crash/{state}/{state}_crashes_harmonized_{year}.csv'
 if not path.exists():return {'state':state,'year':year,'status':'NO_CANONICAL_FILE','filled':0}
 previous=out/f'{state}_{year}_promotion.json'
 if previous.exists():
  result=json.loads(previous.read_text(encoding='utf-8'))
  ledger=pd.read_csv(out/f'{state}_{year}_coordinate_changes.csv',dtype=str,keep_default_na=False)
  current=pd.read_csv(path,usecols=['crash_uid','latitude','longitude','coordinate_status'],dtype=str,keep_default_na=False).set_index('crash_uid')
  for dest,src in [('latitude','candidate_lat'),('longitude','candidate_lon')]:
   assert pd.to_numeric(current.loc[ledger.crash_uid,dest],errors='coerce').reset_index(drop=True).eq(pd.to_numeric(ledger[src],errors='coerce').reset_index(drop=True)).all(),'Previously promoted coordinates changed; review before rerun'
  print('PREVIOUS PROMOTION VERIFIED',state,year,result['filled'],flush=True)
  return result
 d=donor.copy()
 if not len(d):return {'state':state,'year':year,'status':'NO_ELIGIBLE_DONOR','filled':0}
 for col in ['candidate_lat','candidate_lon']:d[col]=pd.to_numeric(d[col],errors='coerce')
 d['inside_state_2km']=shapely.intersects_xy(state_polygon(state),d.candidate_lon.to_numpy(),d.candidate_lat.to_numpy())
 d=d.loc[d.inside_state_2km&d.candidate_lat.between(-90,90)&d.candidate_lon.between(-180,180)].copy()
 ambiguous=d.crash_uid.duplicated(keep=False)
 d.loc[ambiguous].to_csv(out/f'{state}_{year}_ambiguous_donor_rows.csv',index=False)
 d=d.loc[~ambiguous].set_index('crash_uid')
 if not len(d):return {'state':state,'year':year,'status':'NO_UNAMBIGUOUS_IN_STATE_DONOR','filled':0}
 a=pd.read_csv(path,dtype=str,keep_default_na=False);before=a.copy();assert a.crash_uid.is_unique and len(a.columns)==77
 lat=pd.to_numeric(a.latitude,errors='coerce');lon=pd.to_numeric(a.longitude,errors='coerce')
 valid=a.coordinate_status.eq('VALID')&lat.between(-90,90)&lon.between(-180,180)
 mask=~valid&a.crash_uid.isin(d.index)
 ledger=a.loc[mask,['crash_uid','latitude','longitude','coordinate_status']].copy()
 for col in d.columns:ledger[col]=ledger.crash_uid.map(d[col])
 ledger.to_csv(out/f'{state}_{year}_coordinate_changes.csv',index=False)
 for src,dest in [('candidate_lat','latitude'),('candidate_lon','longitude')]:a.loc[mask,dest]=a.loc[mask,'crash_uid'].map(d[src]).astype(str)
 a.loc[mask,'coordinate_status']='VALID'
 assert before.loc[~mask].equals(a.loc[~mask])
 assert before.drop(columns=['latitude','longitude','coordinate_status']).equals(a.drop(columns=['latitude','longitude','coordinate_status']))
 prior=sha(path)
 if mask.any():
  backup=out/'canonical_before';backup.mkdir(exist_ok=True);bp=backup/path.name
  if bp.exists():
   assert sha(bp)==prior,'Existing backup differs from current base; manual recovery required'
  else:shutil.copy2(path,bp)
  tmp=path.with_suffix('.coordinate_recovery.tmp');a.to_csv(tmp,index=False)
  for attempt in range(5):
   try:
    tmp.replace(path);break
   except PermissionError:
    if attempt==4:raise
    time.sleep(2**attempt)
  check=pd.read_csv(path,usecols=['crash_uid','latitude','longitude','coordinate_status'],dtype=str,keep_default_na=False)
  assert len(check)==len(before) and check.crash_uid.equals(before.crash_uid)
  assert check.loc[mask,'latitude'].eq(a.loc[mask,'latitude']).all() and check.loc[mask,'longitude'].eq(a.loc[mask,'longitude']).all()
 result={'state':state,'year':year,'rows':len(a),'filled':int(mask.sum()),'valid_before':int(valid.sum()),'valid_after':int(valid.sum()+mask.sum()),'sha256_before':prior,'sha256_after':sha(path),'status':'PASS','columns':77,'raw_modified':False,'noncoordinate_fields_changed':False}
 (out/f'{state}_{year}_promotion.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True);return result
