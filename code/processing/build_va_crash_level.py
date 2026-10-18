"""Normalize official VDOT annual crash layers to reviewed crash-level inputs."""
import argparse,csv,json,re
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(r"F:\LH_Research\USCrash\Crash\States\VA")
FIELDS=["CrashID","CrashDateTime","County","Latitude","Longitude","SeverityCode","SeverityRaw","Fatalities","Injuries","Vehicles","MannerCode","MannerRaw","FHECode","FHERaw","WeatherCode","WeatherRaw","LightCode","LightRaw","RoadCode","RoadRaw","FunctionalClass","IntersectionRelated","IntersectionType","WorkZoneRelated","WorkZoneType","AlcoholInvolved","DrugInvolved","HitAndRun","SpeedingInvolved","PedestrianCount","BicyclistCount","MotorcycleCount","CommercialVehicleCount","UrbanRural","SourceFile"]
def s(x):return (x or '').strip()
def code(x):
 m=re.match(r'(\d+)',s(x)); return m.group(1) if m else s(x)
def yn(x,yes=('1','yes'),no=('0','no')):
 u=s(x).lower();return 'True' if u in yes else 'False' if u in no else 'Unknown' if u in {'99','not applicable','not provided'} else ''
def num(x):
 try:return str(int(float(s(x))))
 except:return ''
def dt(r):
 v=s(r.get('CRASH_DT')); tm=s(r.get('CRASH_MILITARY_TM'))
 if not v:return ''
 d=datetime.fromtimestamp(int(v)/1000,timezone.utc).astimezone(ZoneInfo('America/New_York')).date()
 if re.fullmatch(r'\d{1,4}',tm):
  z=tm.zfill(4); h,m=int(z[:2]),int(z[2:])
  if h<24 and m<60:return f'{d.isoformat()} {h:02d}:{m:02d}:00'
 return d.isoformat()
def manner(x):return {'1':'1','2':'6','3':'2','4':'7','5':'8','6':'0','7':'0','8':'0','9':'0','10':'0','11':'0','12':'0','13':'0','14':'11','15':'11','16':'11','0':'99','99':'99','Not Applicable':'99','Not Provided':'99'}.get(code(x),'')
def fhe(x):
 c=code(x)
 if c=='20':return 'MOTOR_VEHICLE_IN_TRANSPORT'
 if c=='6':return 'PARKED_VEHICLE'
 if c=='19':return 'PEDESTRIAN'
 if c=='22':return 'PEDALCYCLIST'
 if c=='23':return 'ANIMAL'
 if c=='21':return 'TRAIN'
 if c in {'1','2','3','4','5','7','8','9','11','12','13','14','15','16','17','18'}:return 'FIXED_OBJECT'
 if c in {str(i) for i in range(28,43)}:return 'OTHER_NON_COLLISION'
 if c in {'10','24','25','26','27'}:return 'OTHER_NON_FIXED_OBJECT'
 return ''
def wx(x):return {'1':'CLEAR','3':'FOG_SMOKE','4':'FOG_SMOKE','5':'RAIN','6':'SNOW','7':'SLEET_HAIL','8':'FOG_SMOKE','9':'OTHER','10':'BLOWING_SAND_SOIL','11':'SEVERE_CROSSWIND','99':'UNKNOWN','Not Applicable':'UNKNOWN','Not Provided':'UNKNOWN'}.get(code(x),'')
def light(x):return {'1':'DAWN','2':'DAYLIGHT','3':'DUSK','4':'DARK_LIGHTED','5':'DARK_UNLIGHTED','6':'UNKNOWN','7':'UNKNOWN','99':'UNKNOWN','Not Applicable':'UNKNOWN','Not Provided':'UNKNOWN'}.get(code(x),'')
def road(x):return {'1':'DRY','2':'WET','3':'SNOW','4':'ICE_FROST','5':'MUD_DIRT_GRAVEL','6':'OIL','7':'OTHER','8':'OTHER','9':'WATER_STANDING_MOVING','10':'SLUSH','11':'MUD_DIRT_GRAVEL','0':'UNKNOWN','99':'UNKNOWN','Not Applicable':'UNKNOWN','Not Provided':'UNKNOWN'}.get(code(x),'')
def func(x):return {'1':'INTERSTATE','INT':'INTERSTATE','2':'FREEWAY_EXPRESSWAY','OFE':'FREEWAY_EXPRESSWAY','3':'OTHER_PRINCIPAL_ARTERIAL','OPA':'OTHER_PRINCIPAL_ARTERIAL','4':'MINOR_ARTERIAL','MIA':'MINOR_ARTERIAL','5':'MAJOR_COLLECTOR','MAC':'MAJOR_COLLECTOR','6':'MINOR_COLLECTOR','MIC':'MINOR_COLLECTOR','7':'LOCAL','LOC':'LOCAL'}.get(code(x),'')
def inter(x):
 c=code(x); return 'False' if c=='1' else 'True' if c in {'2','3','4','5','6'} else 'Unknown' if c in {'0','99','Not Applicable','Not Provided'} else ''
def build(y):
 src=ROOT/str(y)/'CSV'/f'VDOT_Crashes_{y}.csv'; out=ROOT/str(y)/'Derived'/f'VA_crash_level_{y}.csv';out.parent.mkdir(exist_ok=True)
 seen=set();dup=0;n=0; vals={k:Counter() for k in ['severity','manner','fhe']}
 with src.open(encoding='utf-8-sig',newline='') as fi,out.open('w',encoding='utf-8-sig',newline='') as fo:
  rd=csv.DictReader(fi);wr=csv.DictWriter(fo,fieldnames=FIELDS);wr.writeheader()
  for r in rd:
   cid=s(r.get('DOCUMENT_NBR'))
   if cid in seen:dup+=1;continue
   seen.add(cid);n+=1; sev=code(r.get('CRASH_SEVERITY')); vals['severity'][s(r.get('CRASH_SEVERITY'))]+=1; vals['manner'][s(r.get('COLLISION_TYPE'))]+=1;vals['fhe'][s(r.get('FIRST_HARMFUL_EVENT'))]+=1
   ped=int(num(r.get('PEDESTRIANS_KILLED')) or 0)+int(num(r.get('PEDESTRIANS_INJURED')) or 0)
   wr.writerow({'CrashID':cid,'CrashDateTime':dt(r),'County':s(r.get('PHYSICAL_JURIS')),'Latitude':s(r.get('Latitude_WGS84')) or s(r.get('__geometry_latitude_wgs84')) or s(r.get('LAT')),'Longitude':s(r.get('Longitude_WGS84')) or s(r.get('__geometry_longitude_wgs84')) or s(r.get('LON')),'SeverityCode':('O' if s(r.get('CRASH_SEVERITY')).lstrip().upper().startswith('PDO') else s(r.get('CRASH_SEVERITY')).lstrip()[:1] if s(r.get('CRASH_SEVERITY')).lstrip()[:1] in {'K','A','B','C','O'} else 'U'),'SeverityRaw':s(r.get('CRASH_SEVERITY')),'Fatalities':num(r.get('K_PEOPLE')),'Injuries':num(r.get('PERSONS_INJURED')),'Vehicles':num(r.get('VEH_COUNT')),'MannerCode':manner(r.get('COLLISION_TYPE')),'MannerRaw':s(r.get('COLLISION_TYPE')),'FHECode':fhe(r.get('FIRST_HARMFUL_EVENT')),'FHERaw':s(r.get('FIRST_HARMFUL_EVENT')),'WeatherCode':wx(r.get('WEATHER_CONDITION')),'WeatherRaw':s(r.get('WEATHER_CONDITION')),'LightCode':light(r.get('LIGHT_CONDITION')),'LightRaw':s(r.get('LIGHT_CONDITION')),'RoadCode':road(r.get('ROADWAY_SURFACE_COND')),'RoadRaw':s(r.get('ROADWAY_SURFACE_COND')),'FunctionalClass':func(r.get('FUN')),'IntersectionRelated':inter(r.get('INTERSECTION_TYPE')),'IntersectionType':s(r.get('INTERSECTION_TYPE')),'WorkZoneRelated':yn(r.get('WORK_ZONE_RELATED'),('1','yes','1. yes'),('2','no','2. no')),'WorkZoneType':s(r.get('WORK_ZONE_TYPE')),'AlcoholInvolved':yn(r.get('ALCOHOL_NOTALCOHOL')),'DrugInvolved':yn(r.get('DRUG_NODRUG')),'HitAndRun':yn(r.get('HITRUN_NOT_HITRUN')),'SpeedingInvolved':yn(r.get('SPEED_NOTSPEED')),'PedestrianCount':str(ped),'BicyclistCount':'1' if yn(r.get('BIKE_NONBIKE'))=='True' else '0','MotorcycleCount':'1' if yn(r.get('MOTOR_NONMOTOR'))=='True' else '0','CommercialVehicleCount':'1' if yn(r.get('LGTRUCK_NONLGTRUCK'))=='True' else '0','UrbanRural':{'0':'RURAL','1':'URBAN','Rural':'RURAL','Urban':'URBAN'}.get(s(r.get('AREA_TYPE')),''),'SourceFile':str(src)})
 (out.parent/f'VA_build_audit_{y}.json').write_text(json.dumps({'year':y,'source_rows':n+dup,'output_rows':n,'duplicate_ids_excluded':dup,'values':{k:dict(v) for k,v in vals.items()}},indent=2),encoding='utf-8')
 print(y,n,dup)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--years',nargs='+',type=int,default=list(range(2009,2027)));a=ap.parse_args()
 for y in a.years:build(y)



