"""Reviewed composite linkage of official regional/city points to existing CCRS crashes.
No unmatched incidents appended. Published geocodes are not assumed measured GPS.
"""
import os,json,re,argparse,shutil
from pathlib import Path
import pandas as pd,numpy as np,geopandas as gpd,shapely
R=Path(r'F:\LH_Research\USCrash\Crash');U=R/'Unified_MMUCC6';S=R/'States/CA/Local_coordinate_sources_2026-10-16';P=U/'qa/CA_other_cities_2026-10-16';P.mkdir(exist_ok=True)
os.environ['USCRASH_COORDINATE_AUDIT_ROOT']=str(P)
from coordinate_supplement_utils import apply,sha
from pilot_ca_composite_coordinates import prepare

def distance(a,b,c,d):
 a,b,c,d=[pd.to_numeric(x,errors='coerce') for x in [a,b,c,d]]
 return 6371008.8*2*np.arcsin(np.minimum(1,np.sqrt(np.sin(np.radians(a-c)/2)**2+np.cos(np.radians(a))*np.cos(np.radians(c))*np.sin(np.radians(b-d)/2)**2)))
def geometry_screen(m,polys,col):
 out=pd.Series(False,index=m.index)
 for k,x in m.groupby(col):
  if str(k) in polys:out.loc[x.index]=shapely.covers(polys[str(k)],shapely.points(x.candidate_lon,x.candidate_lat))
 return out

def gis_rows(name):
 rows=[]
 for p in sorted((S/name).glob('batch_*.json')):
  for f in json.loads(p.read_text(encoding='utf8'))['features']:
   rows.append({**f['attributes'],'candidate_lon':(f.get('geometry') or {}).get('x'),'candidate_lat':(f.get('geometry') or {}).get('y')})
 return pd.DataFrame(rows)

def donors():
 out=[]
 b=pd.concat([pd.read_csv(p,dtype=str,keep_default_na=False) for p in (S/'SACOG').glob('coordinate_extract_*.csv')],ignore_index=True).rename(columns={'join_id':'donor_id','NUMBER_KILLED':'killed','NUMBER_INJURED':'injured'})
 out.append(('SACOG',b,['minute','agency','roads'],3))
 b=pd.concat([pd.read_csv(p,dtype=str,keep_default_na=False) for p in (S/'OrangeCounty_TIMS').glob('coordinate_extract_*.csv')],ignore_index=True).rename(columns={'join_id':'donor_id','number_killed':'killed'})
 out.append(('OrangeCounty_TIMS',b,['minute','agency','roads'],3))
 b=pd.concat([pd.DataFrame(json.loads(p.read_text())) for p in (S/'SANDAG').glob('SANDAG_*.json')],ignore_index=True).rename(columns={'sandag_case_id':'donor_id','primary_rd':'road1','secondary_rd':'road2','latitude_sandag':'candidate_lat','longitude_sandag':'candidate_lon','number_killed':'killed','number_injured':'injured'})
 b['agency']='';b['county']='37';b['dt']=pd.to_datetime(b.collision_date,format='mixed',errors='coerce').dt.normalize()+pd.to_timedelta(pd.to_datetime(b.collision_time,format='mixed',errors='coerce').dt.strftime('%H:%M:%S'))
 out.append(('SANDAG',b,['minute','county','roads'],3))
 b=gis_rows('SacramentoCity').rename(columns={'OBJECTID':'donor_id','Primary_Road':'road1','Secondary_Road':'road2','Number_Killed':'killed','Number_Injured':'injured'});b['agency']='3404';b['dt']=pd.to_datetime(b.Collision_date.astype(str)+' '+b.Collision_Time.astype(str),format='mixed',errors='coerce')
 out.append(('SacramentoCity',b,['minute','agency','roads'],1))
 b=gis_rows('Pasadena').rename(columns={'Accidno':'donor_id','Street':'road1','CrossSt':'road2','NoKilled':'killed','NoInjured':'injured'});b['agency']='1953';b['dt']=pd.to_datetime(b.Date.astype(str)+' '+b.Time.astype(str),format='mixed',errors='coerce')
 out.append(('Pasadena',b,['minute','agency','roads'],1))
 result=[]
 urls={name:json.loads((S/name/'download_manifest.json').read_text()).get('source',json.loads((S/name/'download_manifest.json').read_text()).get('url','')) for name in ['SACOG','OrangeCounty_TIMS','SacramentoCity','Pasadena']};urls['SANDAG']='https://opendata.sandag.org/resource/uzct-sb5t.json'
 for name,b,keys,priority in out:
  b=prepare(b);b['year']=pd.to_datetime(b.dt,format='mixed',errors='coerce').dt.year;b=b.loc[b.year.between(2016,2026)].copy()
  keep=list(dict.fromkeys(['donor_id','candidate_lat','candidate_lon','dt','year','road1','road2','killed']+keys+(['injured'] if 'injured' in b else [])))
  b=b[keep].drop_duplicates();b=b.loc[~b.donor_id.astype(str).duplicated(keep=False)&~b.duplicated(keys,keep=False)].copy()
  f=S/name/'reviewed_composite_coordinate_extract.csv';b.to_csv(f,index=False)
  result.append((name,b,keys,priority,str(f),sha(f),urls[name]))
 return result

def propose():
 g=gpd.read_file(P/'CA_counties.geojson').to_crs(3310);g.geometry=g.geometry.buffer(2000);g=g.to_crs(4326);county=dict(zip(((g.COUNTY.astype(int)+1)//2).astype(str),g.geometry))
 cityfile=Path(r'F:\LH_Research\USCrash\Crash\verification\reference\cb_2023_06_place_500k.zip')
 g=gpd.read_file(cityfile).to_crs(3310);g.geometry=g.geometry.buffer(1000);g=g.to_crs(4326);cities=dict(zip(g.NAME.str.upper(),g.geometry))
 sources=donors();summaries=[];annual=[]
 fields=['Collision Id','NCIC Code','Crash Date Time','PrimaryRoad','SecondaryRoad','NumberKilled','NumberInjured','City Name','County Code']
 for y in range(2016,2027):
  raw=R/f'States/CA/{y}/Crashes_{y}.csv';cp=U/f'data/crash/CA/CA_crashes_harmonized_{y}.csv'
  if not raw.exists():continue
  a=pd.read_csv(raw,dtype=str,keep_default_na=False,usecols=lambda c:c.strip() in fields);a.columns=a.columns.str.strip();a=a.rename(columns={'Collision Id':'id','NCIC Code':'agency','PrimaryRoad':'road1','SecondaryRoad':'road2','NumberKilled':'killed','NumberInjured':'injured','City Name':'city','County Code':'county'})
  a['dt']=pd.to_datetime(a['Crash Date Time'],format='%m/%d/%Y %I:%M:%S %p',errors='coerce');a['city_upper']=a.city.str.upper();a['county']=a.county.str.lstrip('0');a=prepare(a)
  c=pd.read_csv(cp,dtype=str,keep_default_na=False,usecols=['crash_uid','source_crash_id','latitude','longitude','coordinate_status']);a=a.merge(c,left_on='id',right_on='source_crash_id',validate='one_to_one')
  proposals=[]
  for name,b,keys,priority,sourcefile,sourcehash,url in sources:
   b=b.loc[b.year.eq(y)].copy();aa=a.loc[~a.duplicated(keys,keep=False)].copy()
   m=aa.merge(b,on=keys,suffixes=('_raw','_donor'),validate='one_to_one')
   for k in ['killed','injured']:
    if k+'_donor' in m:m=m.loc[pd.to_numeric(m[k+'_raw'],errors='coerce').eq(pd.to_numeric(m[k+'_donor'],errors='coerce'))]
   for f in ['latitude','longitude','candidate_lat','candidate_lon']:m[f]=pd.to_numeric(m[f],errors='coerce')
   m=m.loc[m.candidate_lat.between(32.3,42.2)&m.candidate_lon.between(-124.6,-113.9)].copy()
   m['county_screen']=geometry_screen(m,county,'county');m['city_screen']=geometry_screen(m,cities,'city_upper');m['city_boundary_available']=m.city_upper.isin(cities)
   # County is mandatory; municipal boundary required where a Census place can be identified.
   m['geography_pass']=m.county_screen&(~m.city_boundary_available|m.city_screen)
   m['existing_valid']=m.coordinate_status.eq('VALID')&m.latitude.between(-90,90)&m.longitude.between(-180,180)
   m['distance_m']=distance(m.latitude,m.longitude,m.candidate_lat,m.candidate_lon)
   m['source']=name;m['priority']=priority
   eligible=m.loc[m.geography_pass];known=eligible.loc[eligible.existing_valid,'distance_m']
   # This is a coarse published-geocode gate, NOT metre-level validation or proof of identity.
   gate=len(known)>=50 and known.le(1000).mean()>=.95 and known.median()<=100
   row=dict(source=name,year=y,unique_composite_matches=len(m),geography_pass=len(eligible),known_points=len(known),median_m=float(known.median()),p95_m=float(known.quantile(.95)),within250=float(known.le(250).mean()),within1000=float(known.le(1000).mean()),coarse_geocode_gate=bool(gate),missing_candidates=int((~eligible.existing_valid).sum()))
   summaries.append(row);m.to_csv(P/f'{name}_{y}_linkage.csv',index=False)
   if gate:
    d=eligible.loc[~eligible.existing_valid].copy();d['coordinate_source']=name;d['coordinate_source_url']=url;d['coordinate_source_file']=sourcefile;d['coordinate_source_sha256']=sourcehash
    d['coordinate_method']='OFFICIAL_PUBLISHED_GEOCODE_COMPOSITE_LINK_NOT_MEASURED_GPS';d['linkage_rule']='Unique exact agency (or San Diego county), local date/minute, unordered pair of two normalized roads, fatalities and injuries when available; duplicate keys rejected on both sides; county buffer2km, city buffer1km; source-year coarse-geocode calibration; existing valid points retained.'
    proposals.append(d)
   print(json.dumps(row),flush=True)
  d=pd.concat(proposals,ignore_index=True) if proposals else pd.DataFrame()
  conflicts=[];selected=[]
  if len(d):
   for uid,z in d.groupby('crash_uid',sort=False):
    z=z.sort_values(['priority','source']);first=z.iloc[0];dist=distance(z.candidate_lat,z.candidate_lon,pd.Series(first.candidate_lat,index=z.index),pd.Series(first.candidate_lon,index=z.index))
    if dist.gt(100).any():conflicts.append(uid);continue
    first=first.copy();first['corroborating_sources']=';'.join(z.source);first['cross_source_max_distance_m']=float(dist.max());selected.append(first)
  final=pd.DataFrame(selected);final.to_csv(P/f'CA_{y}_proposed.csv',index=False)
  pd.DataFrame({'crash_uid':conflicts}).to_csv(P/f'CA_{y}_cross_source_conflicts.csv',index=False)
  annual.append(dict(year=y,proposed=len(final),conflicting_crashes=len(conflicts),canonical_sha256_before=sha(cp)))
 pd.DataFrame(summaries).to_csv(P/'source_year_calibration.csv',index=False);pd.DataFrame(annual).to_csv(P/'annual_proposal_counts.csv',index=False)
 (P/'proposal_manifest.json').write_text(json.dumps({'annual':annual,'total_proposed':sum(x['proposed'] for x in annual),'rule_version':'COMPOSITE_V1_TWO_ROADS_EXACT_MINUTE_UNIQUE_BOTH_SIDES','source_accuracy':'Published geocodes. Coarse known-point screen: >=50 samples, median<=100m, >=95% within1km after geography screens. Does not certify sub-km accuracy or incident identity; not equivalent to exact ID matching. See detailed diagnostics and do not claim all values are GPS.','raw_modified':False,'script_sha256':sha(__file__)},indent=2))

def promote():
 plan=json.loads((P/'proposal_manifest.json').read_text());results=[]
 for row in plan['annual']:
  y=row['year'];cp=U/f'data/crash/CA/CA_crashes_harmonized_{y}.csv';prior=P/'CA_other_cities_v1'/f'CA_{y}_promotion.json'
  if not prior.exists():assert sha(cp)==row['canonical_sha256_before'],'Base changed after reviewed proposal; rebuild linkage'
  if not row['proposed']:continue
  d=pd.read_csv(P/f'CA_{y}_proposed.csv',dtype=str,keep_default_na=False)
  keep=['crash_uid','candidate_lat','candidate_lon','coordinate_source','coordinate_source_url','coordinate_source_file','coordinate_source_sha256','coordinate_method','linkage_rule','donor_id','city','county','minute','roads','corroborating_sources','cross_source_max_distance_m']
  results.append(apply('CA',y,d[keep],'CA_other_cities_v1'))
 (P/'promotion_manifest.json').write_text(json.dumps({'results':results,'total_filled':sum(x['filled'] for x in results),'script_sha256':sha(__file__)},indent=2));print('CA OTHER CITIES COMPLETE',sum(x['filled'] for x in results),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
 if args.apply:promote()
 else:propose()
