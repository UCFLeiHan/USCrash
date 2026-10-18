import csv,glob,json,re
from datetime import datetime
from pathlib import Path
R=Path(r'F:\LH_Research\USCrash\Crash\States\WA')
F=['CrashID','CrashDateTime','County','City','Latitude','Longitude','SeverityCode','SeverityRaw','Vehicles','FHECode','FHERaw','WeatherCode','WeatherRaw','LightCode','LightRaw','IntersectionRelated','SchoolBusRelated','HitAndRun','PedestrianCount','BicyclistCount','CommercialVehicleCount','SourceFile']
def s(x):return (x or '').strip()
def tri(x):return {'Y':'True','N':'False','U':'Unknown','Yes':'True','No':'False'}.get(s(x),'')
def weather(x):
 u=s(x).lower()
 if 'clear' in u or 'cloud' in u:return 'CLEAR' if 'clear' in u else 'CLOUDY'
 if 'rain' in u:return 'RAIN'
 if 'snow' in u:return 'SNOW'
 if 'fog' in u or 'smoke' in u:return 'FOG_SMOKE'
 if 'sleet' in u or 'hail' in u:return 'SLEET_HAIL'
 if 'wind' in u:return 'SEVERE_CROSSWIND'
 return 'UNKNOWN' if u else ''
def light(x):
 u=s(x).lower()
 if 'daylight' in u:return 'DAYLIGHT'
 if 'dawn' in u:return 'DAWN'
 if 'dusk' in u:return 'DUSK'
 if 'dark' in u and ('street light' in u or 'lighted' in u) and 'not' not in u:return 'DARK_LIGHTED'
 if 'dark' in u:return 'DARK_UNLIGHTED'
 return 'UNKNOWN' if u else ''
def fhe(x):
 u=s(x).lower()
 if not u:return ''
 if 'pedestrian' in u:return 'PEDESTRIAN'
 if 'bicycl' in u or 'pedal' in u:return 'PEDALCYCLIST'
 if 'animal' in u or 'deer' in u:return 'ANIMAL'
 if 'train' in u or 'rail' in u:return 'TRAIN'
 if 'parked' in u and 'vehicle' in u:return 'PARKED_VEHICLE'
 if 'vehicle' in u:return 'MOTOR_VEHICLE_IN_TRANSPORT'
 return 'FIXED_OBJECT'
def num(x):
 try:return str(int(float(s(x))))
 except:return ''
def crash_dt(x):
 x=s(x)
 try:return datetime.strptime(x,'%m/%d/%Y %H:%M:%S %z').isoformat()
 except ValueError:return x
def run(y):
 files=sorted((R/str(y)).glob('WSP_CAT_summary_*.csv')); out=R/str(y)/'Derived'/f'WA_crash_level_{y}.csv';out.parent.mkdir(exist_ok=True)
 seen=set();dup=0;n=0
 with out.open('w',encoding='utf-8-sig',newline='') as fo:
  w=csv.DictWriter(fo,fieldnames=F);w.writeheader()
  for p in files:
   with p.open(encoding='utf-8-sig',newline='') as fi:
    next(fi,None);next(fi,None)
    for r in csv.DictReader(fi):
     cid=s(r.get('ReportNumber'))
     if not cid:continue
     if cid in seen:dup+=1;continue
     seen.add(cid);n+=1; sev=s(r.get('InjurySeverity'))
     w.writerow({'CrashID':cid,'CrashDateTime':crash_dt(r.get('DateTimeOfIncident')),'County':s(r.get('CountyName')),'City':s(r.get('CityName')),'Latitude':s(r.get('Latitude')),'Longitude':s(r.get('Longitude')),'SeverityCode':{'Fatal':'K','Serious':'A','Minor':'B','No Injury':'O','Unknown':'U'}.get(sev,'U'),'SeverityRaw':sev,'Vehicles':num(r.get('NumberOfMotorVehiclesInvolved')),'FHECode':fhe(r.get('ObjectStruck')),'FHERaw':s(r.get('ObjectStruck')),'WeatherCode':weather(r.get('Weather')),'WeatherRaw':s(r.get('Weather')),'LightCode':light(r.get('Lighting')),'LightRaw':s(r.get('Lighting')),'IntersectionRelated':tri(r.get('IsIntersectionRelated')),'SchoolBusRelated':tri(r.get('IsSchoolBusInvolved')),'HitAndRun':tri(r.get('IsHitAndRun')),'PedestrianCount':num(r.get('NumberOfPedestriansInvolved')),'BicyclistCount':num(r.get('NumberOfPedalcyclistsInvolved')),'CommercialVehicleCount':'1' if tri(r.get('IsCommercialCarrierInvolved'))=='True' else '0','SourceFile':str(p)})
 (out.parent/f'WA_build_audit_{y}.json').write_text(json.dumps({'year':y,'files':len(files),'source_rows':n+dup,'output_rows':n,'duplicate_ids_removed':dup},indent=2));print(y,n,dup)
if __name__=='__main__':
 import sys
 for y in map(int,sys.argv[1:] or range(2017,2027)):run(y)

