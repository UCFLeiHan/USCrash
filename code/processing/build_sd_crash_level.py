"""Aggregate South Dakota crash, person, vehicle and weather tables safely."""
import argparse,csv
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(r"F:\LH_Research\USCrash\Crash\States\SD")
FIELDS=["CrashID","CrashDateTime","County","City","Latitude","Longitude","SeverityCode","SeverityRaw","Fatalities","Injuries","Vehicles","MannerCode","MannerRaw","FHECode","FHERaw","WeatherCode","WeatherRaw","LightCode","LightRaw","RoadCode","RoadRaw","FunctionalClass","IntersectionRelated","IntersectionType","WorkZoneRelated","WorkZoneType","AlcoholInvolved","DrugInvolved","HitAndRun","PedestrianCount","BicyclistCount","MotorcycleCount","CommercialVehicleCount","SchoolBusRelated","UrbanRural","PostedSpeedLimit","NumberOfLanes","SourceLayer"]
RANK={"No injury":(0,"O"),"Possible":(1,"C"),"Non-incapacitating":(2,"B"),"Incapacitating":(3,"A"),"Fatal injury":(4,"K")}
def s(x): return (x or "").strip()
def manner(x):
 x=s(x).lower()
 if "no collision" in x or "wild animal" in x:return "0"
 if "rear-end" in x or "rear-to-rear" in x:return "1"
 if "head-on" in x:return "2"
 if x=="angle":return "6"
 if "sideswipe, same" in x:return "7"
 if "sideswipe, opposite" in x:return "8"
 if x in {"unknown","not applicable",""}:return "99" if x else ""
 return "11"
def fhe(x):
 x=s(x).lower()
 if "motor vehicle in transport" in x:return "MOTOR_VEHICLE_IN_TRANSPORT"
 if "parked motor vehicle" in x:return "PARKED_VEHICLE"
 if x=="pedestrian":return "PEDESTRIAN"
 if x=="pedalcycle":return "PEDALCYCLIST"
 if "animal" in x:return "ANIMAL"
 if "railway" in x:return "TRAIN"
 if any(k in x for k in ["post","pole","support","guardrail","barrier","bridge","fence","ditch","embankment","mailbox","tree","shrub","culvert","curb","rock","fixed object","snow bank","barricade","pavement"]):return "FIXED_OBJECT"
 if any(k in x for k in ["overturn","fire/explosion","jackknife","immersion","non-collision","fell/jumped","cargo/equipment loss"]):return "OTHER_NON_COLLISION"
 return "OTHER_NON_FIXED_OBJECT" if x else ""
def weather(values):
 raw="; ".join(sorted(set(s(v) for v in values if s(v))))
 u=raw.lower()
 for key,code in [("freezing","SLEET_HAIL"),("sleet","SLEET_HAIL"),("hail","SLEET_HAIL"),("rain","RAIN"),("snow","SNOW"),("fog","FOG_SMOKE"),("smog","FOG_SMOKE"),("smoke","FOG_SMOKE"),("crosswind","SEVERE_CROSSWIND"),("sand","BLOWING_SAND_SOIL"),("cloudy","CLOUDY"),("clear","CLEAR")]:
  if key in u:return code,raw
 return ("UNKNOWN" if raw else ""),raw
def light(x):
 return {"daylight":"DAYLIGHT","dawn":"DAWN","dusk":"DUSK","dark - lighted roadway":"DARK_LIGHTED","dark - roadway not lighted":"DARK_UNLIGHTED","dark - unknown roadway lighting":"UNKNOWN","unknown":"UNKNOWN","other":"OTHER"}.get(s(x).lower(),"")
def road(x):
 u=s(x).lower()
 if u=="dry":return "DRY"
 if u=="wet":return "WET"
 if u in {"ice","frost"}:return "ICE_FROST"
 if u=="snow":return "SNOW"
 if u=="slush":return "SLUSH"
 if "water" in u:return "WATER_STANDING_MOVING"
 if any(k in u for k in ["sand","mud","dirt","gravel"]):return "MUD_DIRT_GRAVEL"
 if u=="oil":return "OIL"
 if u in {"unknown","not applicable"}:return "UNKNOWN"
 return "OTHER" if u else ""
def tri(values,positive):
 vals={s(v).lower() for v in values if s(v)}
 if any(v in positive for v in vals):return "True"
 if any(v in {"unknown","not reported"} for v in vals):return "Unknown"
 return "False" if vals else ""
def func(x):
 u=s(x); low=u.lower()
 if "interstate" in low:f="INTERSTATE"
 elif "freeway" in low or "expressway" in low:f="FREEWAY_EXPRESSWAY"
 elif "principal" in low:f="OTHER_PRINCIPAL_ARTERIAL"
 elif "minor arterial" in low:f="MINOR_ARTERIAL"
 elif "major collector" in low:f="MAJOR_COLLECTOR"
 elif "minor collector" in low or low.endswith("collector"):f="MINOR_COLLECTOR"
 elif "local" in low:f="LOCAL"
 else:f=""
 return f, ("URBAN" if low.startswith("urban") else "RURAL" if low.startswith("rural") else "")
def junction(x):
 u=s(x).lower()
 if u in {"non-junction","wild animal hit - damage only"}:return "False"
 if not u or u in {"unknown","not applicable"}:return "Unknown" if u else ""
 return "True"
def work(x):
 u=s(x).lower(); return "True" if u=="yes" else "False" if u=="no" else "Unknown" if u in {"unknown","not reported"} else ""
def school(x):
 u=s(x).lower(); return "True" if "involved" in u and not u.startswith("no") else "False" if u.startswith("no") else "Unknown" if u in {"unknown","not reported"} else ""

def build_detail(y):
 d=ROOT/str(y)/"CSV"; people=defaultdict(lambda:{"rank":-1,"sev":"","fat":0,"inj":0,"alc":[],"drug":[]})
 with (d/f"Person{y}.csv").open(encoding="utf-8-sig",newline="") as f:
  for r in csv.DictReader(f):
   a=people[s(r["AccidentSeqID"])]; lab=s(r["InjuryStatusDesc"])
   if lab in RANK:
    rank,sev=RANK[lab]
    if rank>a["rank"]:a["rank"],a["sev"]=rank,sev
    if sev=="K":a["fat"]+=1
    elif sev in {"A","B","C"}:a["inj"]+=1
   a["alc"].append(r.get("AlcoholUseDesc")); a["drug"].append(r.get("DrugUseDesc"))
 veh=defaultdict(lambda:{"n":0,"hit":[],"ped":0,"bike":0,"mc":0,"comm":0})
 with (d/f"Vehicle{y}.csv").open(encoding="utf-8-sig",newline="") as f:
  for r in csv.DictReader(f):
   a=veh[s(r["AccidentSeqID"])]; typ=s(r["UnitTypeDesc"]).lower(); cfg=s(r["VehConfigDesc"]).lower()
   if "motor vehicle" in typ:a["n"]+=1
   if typ=="pedestrian":a["ped"]+=1
   if "pedalcycl" in typ:a["bike"]+=1
   if cfg in {"motorcycle","moped"}:a["mc"]+=1
   if s(r["IsUnitCommercialInd"]).lower()=="true":a["comm"]+=1
   a["hit"].append(r.get("HitandRunDesc"))
 wx=defaultdict(list)
 with (d/f"Weather{y}.csv").open(encoding="utf-8-sig",newline="") as f:
  for r in csv.DictReader(f):wx[s(r["AccidentSeqID"])].append(r.get("WeatherDesc"))
 outdir=ROOT/str(y)/"Derived";outdir.mkdir(exist_ok=True);out=outdir/f"SD_crash_level_{y}.csv";part=out.with_suffix('.csv.partial');n=0
 with (d/f"Accident{y}.csv").open(encoding="utf-8-sig",newline="") as f,part.open('w',encoding='utf-8-sig',newline='') as g:
  w=csv.DictWriter(g,fieldnames=FIELDS,lineterminator='\n');w.writeheader()
  for r in csv.DictReader(f):
   sid=s(r["AccidentSeqID"]);p=people[sid];v=veh[sid]; wc,wr=weather(wx[sid]); fc,ur=func(r.get("FuncClass")); sev=p['sev'] or {'Fatal':'K','PDO':'O','Injury':'U'}.get(s(r.get('Severity')),'U')
   lanes=s(r.get('LocLanesQty')); lanes=lanes if lanes.isdigit() and lanes!='0' else ''; speed=s(r.get('LocSpeedLimitNbr')); speed=speed if speed.isdigit() and speed!='0' else ''
   row={"CrashID":s(r['AccidentNbr']),"CrashDateTime":s(r['AccidentDateTime']),"County":s(r['CountyName']),"City":s(r['CityName']),"Latitude":s(r['LatitudeValue']),"Longitude":s(r['LongitudeValue']),"SeverityCode":sev,"SeverityRaw":s(r.get('Severity')),"Fatalities":p['fat'],"Injuries":p['inj'],"Vehicles":v['n'],"MannerCode":manner(r.get('MOCDesc')),"MannerRaw":s(r.get('MOCDesc')),"FHECode":fhe(r.get('FHEvent')),"FHERaw":s(r.get('FHEvent')),"WeatherCode":wc,"WeatherRaw":wr,"LightCode":light(r.get('LightDesc')),"LightRaw":s(r.get('LightDesc')),"RoadCode":road(r.get('RoadCondDesc')),"RoadRaw":s(r.get('RoadCondDesc')),"FunctionalClass":fc,"IntersectionRelated":junction(r.get('JunctionDesc')),"IntersectionType":s(r.get('JunctionDesc')),"WorkZoneRelated":work(r.get('WorkZoneDesc')),"WorkZoneType":s(r.get('WorkZoneTypeDesc')),"AlcoholInvolved":tri(p['alc'],{'alcohol used'}),"DrugInvolved":tri(p['drug'],{'drugs used'}),"HitAndRun":tri(v['hit'],{'yes','yes, left scene but was found later'}),"PedestrianCount":v['ped'],"BicyclistCount":v['bike'],"MotorcycleCount":v['mc'],"CommercialVehicleCount":v['comm'],"SchoolBusRelated":school(r.get('SchoolBusDesc')),"UrbanRural":ur,"PostedSpeedLimit":speed,"NumberOfLanes":lanes,"SourceLayer":"DETAIL_MULTI_TABLE"}
   w.writerow({k:row.get(k,'') for k in FIELDS});n+=1
 part.replace(out);print(y,n,flush=True)

def build_2026(y=2026):
 src=ROOT/str(y)/"SDDOT_crashes.csv";outdir=ROOT/str(y)/"Derived";outdir.mkdir(exist_ok=True);out=outdir/f"SD_crash_level_{y}.csv";part=out.with_suffix('.csv.partial');n=0
 with src.open(encoding='utf-8-sig',newline='') as f,part.open('w',encoding='utf-8-sig',newline='') as g:
  w=csv.DictWriter(g,fieldnames=FIELDS,lineterminator='\n');w.writeheader()
  for r in csv.DictReader(f):
   dt=datetime.fromtimestamp(int(s(r['AccidentDateTime']))/1000,timezone.utc).replace(tzinfo=None).isoformat(sep=' '); sev={'Fatal injury':'K','Incapacitating':'A','Non-incapacitating':'B','Possible':'C','No injury':'O'}.get(s(r['InjurySeverity']),'U'); wc,wr=weather([r.get('Weather')])
   row={"CrashID":s(r['AccidentNbr']),"CrashDateTime":dt,"County":s(r['County']),"Latitude":s(r['__geometry_latitude_wgs84']) or s(r['Latitudevalue']),"Longitude":s(r['__geometry_longitude_wgs84']) or s(r['Longitudevalue']),"SeverityCode":sev,"SeverityRaw":s(r['InjurySeverity']),"MannerCode":manner(r['MannerOfCollision']),"MannerRaw":s(r['MannerOfCollision']),"FHECode":fhe(r['FirstHarmfulEvent']),"FHERaw":s(r['FirstHarmfulEvent']),"WeatherCode":wc,"WeatherRaw":wr,"LightCode":light(r['LightCondition']),"LightRaw":s(r['LightCondition']),"RoadCode":road(r['RoadCondDesc']),"RoadRaw":s(r['RoadCondDesc']),"IntersectionRelated":junction(r['Junction']),"IntersectionType":s(r['Junction']),"WorkZoneRelated":"","WorkZoneType":s(r['WorkZoneType']),"AlcoholInvolved":"True" if s(r['AlcoholUse'])=='Y' else "False" if s(r['AlcoholUse'])=='N' else "","PostedSpeedLimit":s(r['EstSpeeds']) if s(r['EstSpeeds']).isdigit() and s(r['EstSpeeds'])!='0' else "","SourceLayer":"SDDOT_PUBLIC"}
   w.writerow({k:row.get(k,'') for k in FIELDS});n+=1
 part.replace(out);print(y,n,flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--year-start',type=int,default=2011);ap.add_argument('--year-end',type=int,default=2026);a=ap.parse_args()
 for y in range(a.year_start,a.year_end+1):build_detail(y) if y<=2025 else build_2026(y)
