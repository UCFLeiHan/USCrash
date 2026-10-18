"""Create one reviewed Utah crash-level table per year from official UDOT exports."""
import os as _uscrash_paths_os
import argparse, csv, json
from collections import Counter
from pathlib import Path

ROOT=(Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/UT')
OUT_FIELDS=["CrashID","CrashDateTime","County","Latitude","Longitude","SeverityCode","SeverityRaw","Fatalities","Injuries","Vehicles","MannerCode","MannerRaw","FHECode","FHERaw","WeatherCode","WeatherRaw","LightCode","LightRaw","RoadCode","RoadRaw","FunctionalClass","IntersectionRelated","IntersectionType","WorkZoneRelated","AlcoholInvolved","HitAndRun","SpeedingInvolved","PedestrianCount","BicyclistCount","MotorcycleCount","CommercialVehicleCount","SourceFile"]

def s(v): return (v or "").strip()
def yn(v):
    u=s(v).lower()
    return "True" if u in {"y","yes","true","1"} else "False" if u in {"n","no","false","0"} else "Unknown" if u in {"u","unknown"} else ""
def count_flag(v):
    q=yn(v); return "1" if q=="True" else "0" if q=="False" else ""
def integer(v):
    try: return str(int(float(s(v))))
    except: return ""
def manner(v):
    return {"Not Applicable / Single Vehicle":"0","Front to Rear":"1","Head On (front-to-front)":"2","Angle":"6","Sideswipe Same Direction":"7","Sideswipe Opposite Direction":"8","Rear to Side":"11","Rear to Rear":"11","Parked Vehicle":"11","Other":"11","Unknown":"99"}.get(s(v),"")
def fhe(v):
    u=s(v).lower()
    if not u:return ""
    if "other motor vehicle in transport" in u:return "MOTOR_VEHICLE_IN_TRANSPORT"
    if "parked motor vehicle" in u:return "PARKED_VEHICLE"
    if u=="pedestrian":return "PEDESTRIAN"
    if u=="pedalcycle":return "PEDALCYCLIST"
    if "animal" in u:return "ANIMAL"
    if "rail" in u:return "TRAIN"
    fixed=("barrier","bridge","culvert","curb","ditch","embankment","fence","guardrail","mailbox","hydrant","post","pole","support","snow bank","tree","shrub","fixed object","crash cushion","access control cable")
    if any(x in u for x in fixed):return "FIXED_OBJECT"
    non=("overturn","rollover","fire/explosion","immersion","jackknife","fell/jumped","cargo/equipment loss","other non-collision")
    if any(x in u for x in non):return "OTHER_NON_COLLISION"
    return "OTHER_NON_FIXED_OBJECT"
def weather(v):
    return {"Clear":"CLEAR","Cloudy":"CLOUDY","Rain":"RAIN","Snowing":"SNOW","Blowing Snow":"BLOWING_SNOW","Fog, Smog":"FOG_SMOKE","Sleet, Hail":"SLEET_HAIL","Severe Crosswinds":"SEVERE_CROSSWIND","Blowing Sand, Soil, Dirt":"BLOWING_SAND_SOIL","Unknown":"UNKNOWN"}.get(s(v),"")
def light(v):
    return {"Daylight":"DAYLIGHT","Dawn":"DAWN","Dusk":"DUSK","Dark - Lighted":"DARK_LIGHTED","Dark - Not Lighted":"DARK_UNLIGHTED","Dark - Unknown Lighting":"UNKNOWN","Unknown":"UNKNOWN"}.get(s(v),"")
def road(v):
    u=s(v).lower()
    if u=="dry":return "DRY"
    if u=="wet":return "WET"
    if "ice" in u or "frost" in u:return "ICE_FROST"
    if u=="snow":return "SNOW"
    if u=="slush":return "SLUSH"
    if "water" in u:return "WATER_STANDING_MOVING"
    if any(x in u for x in ("sand","mud","dirt","gravel")):return "MUD_DIRT_GRAVEL"
    if u=="oil":return "OIL"
    if u=="unknown":return "UNKNOWN"
    return "OTHER" if u else ""
def functional(v):
    u=s(v).lower()
    if "interstate" in u:return "INTERSTATE"
    if "freeway" in u or "expressway" in u:return "FREEWAY_EXPRESSWAY"
    if "other principal" in u or "principal arterial" in u:return "OTHER_PRINCIPAL_ARTERIAL"
    if "minor arterial" in u:return "MINOR_ARTERIAL"
    if "major collector" in u:return "MAJOR_COLLECTOR"
    if "minor collector" in u:return "MINOR_COLLECTOR"
    if "local" in u:return "LOCAL"
    return "UNKNOWN" if u=="unknown" else ""
def junction(v):
    u=s(v)
    if not u:return "",""
    if u.lower() in {"non-junction","no special feature"}:return "False",u
    if u.lower()=="unknown":return "Unknown",u
    return "True",u

def build(year):
    src=ROOT/str(year)/"CSV"/f"UDOT_Crashes_{year}.csv"; out=ROOT/str(year)/"Derived"/f"UT_crash_level_{year}.csv"; out.parent.mkdir(exist_ok=True)
    seen=set(); dup=0; rows=0; vals={k:Counter() for k in ["severity","manner","fhe","weather","light","road","junction","functional"]}
    with src.open(encoding="utf-8-sig",newline="") as fi, out.open("w",encoding="utf-8-sig",newline="") as fo:
        rd=csv.DictReader(fi); wr=csv.DictWriter(fo,fieldnames=OUT_FIELDS); wr.writeheader()
        for raw in rd:
            r={k.lower():v for k,v in raw.items() if k is not None}; cid=s(r.get("crash_id"))
            if cid in seen: dup+=1; continue
            seen.add(cid); rows+=1
            sev=s(r.get("crash_severity_desc")); man=s(r.get("manner_collision_desc")); fh=s(r.get("first_harmful_event_desc")); wx=s(r.get("weather_condition_desc")); li=s(r.get("light_condition_desc")); rs=s(r.get("roadway_surf_condition_desc")); ju=s(r.get("roadway_junct_feature_desc")); fc=s(r.get("functional_class"))
            for k,v in [("severity",sev),("manner",man),("fhe",fh),("weather",wx),("light",li),("road",rs),("junction",ju),("functional",fc)]: vals[k][v]+=1
            inj=sum(int(integer(r.get(x)) or 0) for x in ["number_one_injuries","number_two_injuries","number_three_injuries","number_four_injuries"])
            inter,itype=junction(ju)
            wr.writerow({"CrashID":cid,"CrashDateTime":s(r.get("crashdatetime_iso")) or s(r.get("crash_datetime")),"County":s(r.get("county_name")),"Latitude":s(r.get("latitude")),"Longitude":s(r.get("longitude")),"SeverityCode":{"Fatal":"K","Suspected Serious Injury":"A","Suspected Minor Injury":"B","Possible Injury":"C","No Injury/PDO":"O"}.get(sev,"U"),"SeverityRaw":sev,"Fatalities":integer(r.get("number_fatalities")),"Injuries":str(inj),"Vehicles":integer(r.get("number_vehicles_involved")),"MannerCode":manner(man),"MannerRaw":man,"FHECode":fhe(fh),"FHERaw":fh,"WeatherCode":weather(wx),"WeatherRaw":wx,"LightCode":light(li),"LightRaw":li,"RoadCode":road(rs),"RoadRaw":rs,"FunctionalClass":functional(fc),"IntersectionRelated":inter,"IntersectionType":itype,"WorkZoneRelated":yn(r.get("work_zone_related_ynu")),"AlcoholInvolved":yn(r.get("dui")),"HitAndRun":yn(r.get("hit_and_run")),"SpeedingInvolved":yn(r.get("speed_related")),"PedestrianCount":count_flag(r.get("pedestrian_involved")),"BicyclistCount":count_flag(r.get("bicyclist_involved")),"MotorcycleCount":count_flag(r.get("motorcycle_involved")),"CommercialVehicleCount":count_flag(r.get("commercial_motor_veh_involved")),"SourceFile":str(src)})
    audit={"year":year,"source":str(src),"output":str(out),"source_rows":rows+dup,"output_rows":rows,"exact_duplicate_crash_ids_excluded":dup,"unique_crash_ids":len(seen),"values":{k:dict(v) for k,v in vals.items()}}
    (out.parent/f"UT_build_audit_{year}.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
    print(year,rows,"duplicates excluded",dup)
if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--years",nargs="+",type=int,default=list(range(2018,2027))); a=ap.parse_args()
    for y in a.years: build(y)
