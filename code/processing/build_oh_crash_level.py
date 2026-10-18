"""Build reproducible Ohio crash-level inputs without double-counting flat rows."""
import argparse, csv
from datetime import datetime
from pathlib import Path

ROOT = Path(r"F:\LH_Research\USCrash\Crash\States\OH")
OUT_FIELDS = [
    "CrashID","CrashDate","CrashYear","CrashMonth","CrashTime","CrashHour","County","Latitude","Longitude",
    "SeverityCode","SeverityLabel","Fatalities","Injuries","Vehicles",
    "MannerCode","MannerLabel","FirstHarmfulCode","FirstHarmfulLabel",
    "WeatherCode","LightCode","RoadConditionCode","FunctionalClass",
    "IntersectionRelated","IntersectionType","WorkZoneRelated","WorkZoneType",
    "AlcoholInvolved","DrugInvolved","SpeedingInvolved","HitAndRun",
    "PedestrianInvolved","BicyclistInvolved","MotorcycleInvolved",
    "CommercialVehicleInvolved","SchoolZoneRelated","UrbanRural",
    "PostedSpeedLimit","NumberOfLanes","DetailAvailable","SourceLayer",
]

def s(v): return (v or "").strip()
def b(v): return s(v).lower() in {"1","true","t","yes","y"}
def dt_parts(v):
    v=s(v)
    if not v: return "", ""
    for fmt in ("%Y-%m-%d %H:%M:%S","%Y-%m-%dT%H:%M:%S","%m/%d/%Y %H:%M"):
        try:
            d=datetime.strptime(v,fmt); return d.date().isoformat(),d.time().isoformat()
        except ValueError: pass
    raise ValueError(f"Unrecognized Ohio datetime: {v!r}")

def primary_fhe(path):
    """Select unit fields for the unit identified as UnitInError."""
    out={}
    with path.open(encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            cid=s(r.get("CrashID")); unit=s(r.get("Units.UnitNumber")); primary=s(r.get("UnitInError"))
            if cid and cid not in out and unit and unit==primary:
                out[cid]=(s(r.get("Units.FirstHarmfulEvent")),s(r.get("Units.PostedSpeed")),s(r.get("Units.NumberOfThruLanes")))
    return out

def harmful_from_unit(code):
    try: n=int(code)
    except (TypeError,ValueError): return "", ""
    if 1 <= n <= 13: cat="OTHER_NON_COLLISION"
    elif n==14: cat="PEDESTRIAN"
    elif n==15: cat="PEDALCYCLIST"
    elif n==16: cat="TRAIN"
    elif 17 <= n <= 19: cat="ANIMAL"
    elif n==20: cat="MOTOR_VEHICLE_IN_TRANSPORT"
    elif n==21: cat="PARKED_VEHICLE"
    elif 25 <= n <= 54: cat="FIXED_OBJECT"
    else: cat="OTHER_NON_FIXED_OBJECT"
    return cat, code

def harmful_from_type(code,label):
    c=s(code)
    if c in {"1","2","3","4","5","6","18","19"}: cat="MOTOR_VEHICLE_IN_TRANSPORT"
    elif c=="7": cat="PARKED_VEHICLE"
    elif c=="8": cat="PEDESTRIAN"
    elif c=="9": cat="ANIMAL"
    elif c=="10": cat="TRAIN"
    elif c=="11": cat="PEDALCYCLIST"
    elif c=="13": cat="FIXED_OBJECT"
    elif c=="14" or c=="12": cat="OTHER_NON_FIXED_OBJECT"
    elif c in {"16","17"}: cat="OTHER_NON_COLLISION"
    else: cat="UNKNOWN"
    return cat, s(label)

def manner_from_type(code,label):
    return ({"1":"2","2":"1","3":"11","4":"8","5":"7","6":"6",
             "18":"6","19":"6","7":"0","8":"0","9":"0","10":"0",
             "11":"0","12":"0","13":"0","14":"0","16":"0","17":"0",
             "0":"99"}.get(s(code),""), s(label))

def functional(code):
    return {"1":"INTERSTATE","2":"FREEWAY_EXPRESSWAY","3":"OTHER_PRINCIPAL_ARTERIAL",
            "4":"MINOR_ARTERIAL","5":"MAJOR_COLLECTOR","6":"MINOR_COLLECTOR",
            "7":"LOCAL"}.get(s(code),"")

def intersection(code,label):
    c=s(code)
    return ("True" if c in {"2","3","4","5","6"} else "False", s(label))

def workzone_type(code):
    return {"1":"LANE_CLOSURE","2":"LANE_SHIFT_CROSSOVER","3":"SHOULDER_MEDIAN_WORK",
            "4":"INTERMITTENT_MOVING_WORK","5":"OTHER"}.get(s(code),"")

def urban_rural(value):
    return {"City":"URBAN","Village":"URBAN","Township":"UNKNOWN"}.get(s(value),"")

def build_flat(year):
    folder=ROOT/str(year); src=folder/"CSV"/f"OH_{year}_crash_vehicle_person_flat.csv"
    p_fhe=primary_fhe(src); outdir=folder/"Derived"; outdir.mkdir(exist_ok=True)
    out=outdir/f"OH_crash_level_{year}.csv"; part=out.with_suffix(".csv.partial")
    seen=set(); n=0
    with src.open(encoding="utf-8-sig",newline="") as f, part.open("w",encoding="utf-8-sig",newline="") as g:
        rd=csv.DictReader(f); w=csv.DictWriter(g,fieldnames=OUT_FIELDS,lineterminator="\n"); w.writeheader()
        for r in rd:
            cid=s(r.get("CrashID"))
            if not cid or cid in seen: continue
            seen.add(cid); date,time=dt_parts(r.get("CrashDateTime")); primary=p_fhe.get(cid,("","","")); fhe, fhel=harmful_from_unit(primary[0])
            row={
                "CrashID":cid,"CrashDate":date,"CrashYear":str(year),"CrashMonth":str(int(date[5:7])),"CrashTime":time,
                "SeverityCode":s(r.get("CrashSeverity")),"Vehicles":s(r.get("NumberOfUnits")),
                "Fatalities":s(r.get("TotalKilled")),"Injuries":s(r.get("TotalInjured")),
                "MannerLabel":s(r.get("MannerOfCollision")),"FirstHarmfulCode":fhe,"FirstHarmfulLabel":fhel,
                "WeatherCode":s(r.get("Weather")),"LightCode":s(r.get("LightCondition")),
                "RoadConditionCode":s(r.get("RoadCondition")),
                "IntersectionRelated":str(b(r.get("IntersectionOrApproachRelated"))),
                "WorkZoneRelated":str(b(r.get("WorkZoneRelated"))),"WorkZoneType":workzone_type(r.get("WorkZoneType")),
                "AlcoholInvolved":str(b(r.get("IsAlcoholRelated"))),"DrugInvolved":str(b(r.get("IsDrugRelated"))),
                "SpeedingInvolved":str(b(r.get("IsSpeedRelated"))),"HitAndRun":str(s(r.get("HitSkip")) not in {"","0","False","false"}),
                "PedestrianInvolved":str(b(r.get("IsPedestrianRelated"))),"BicyclistInvolved":str(b(r.get("IsBicycleRelated"))),
                "MotorcycleInvolved":str(b(r.get("IsMotorcycleRelated"))),"CommercialVehicleInvolved":str(b(r.get("IsCommercialRelated"))),
                "SchoolZoneRelated":str(b(r.get("ActiveSchoolZoneRelated"))),"UrbanRural":urban_rural(r.get("InCityVillageTownship")),
                "PostedSpeedLimit":primary[1],"NumberOfLanes":primary[2],
                "DetailAvailable":"True","SourceLayer":"FIGSHARE_FLAT",
            }
            w.writerow({k:row.get(k,"") for k in OUT_FIELDS}); n+=1
    part.replace(out); print(year,n,out,flush=True)

DETAIL_KEYS=["CrashDateTime","MannerOfCollision","Weather","LightCondition","RoadCondition",
 "NumberOfUnits","TotalKilled","TotalInjured","IntersectionOrApproachRelated","WorkZoneRelated","WorkZoneType",
 "IsAlcoholRelated","IsDrugRelated","IsSpeedRelated","HitSkip","IsPedestrianRelated","IsBicycleRelated",
 "IsMotorcycleRelated","IsCommercialRelated","ActiveSchoolZoneRelated","InCityVillageTownship"]

def build_tims(year):
    folder=ROOT/str(year); src=folder/"CSV"/f"OH_{year}_crash.csv"; details={}
    ep=folder/"CSV"/f"OH_{year}_crash_enriched_figshare_tims.csv"
    if ep.exists():
        with ep.open(encoding="utf-8-sig",newline="") as f:
            for r in csv.DictReader(f):
                details[s(r.get("CrashID"))]={k:s(r.get(k)) for k in DETAIL_KEYS}
    outdir=folder/"Derived"; outdir.mkdir(exist_ok=True); out=outdir/f"OH_crash_level_{year}.csv"; part=out.with_suffix(".csv.partial")
    n=matched=0
    with src.open(encoding="utf-8-sig",newline="") as f, part.open("w",encoding="utf-8-sig",newline="") as g:
        rd=csv.DictReader(f); w=csv.DictWriter(g,fieldnames=OUT_FIELDS,lineterminator="\n"); w.writeheader()
        for r in rd:
            cid=s(r.get("DOCUMENT_NBR")); d=details.get(cid,{})
            def bd(key):
                value=s(d.get(key))
                return str(b(value)) if value else ""
            if d: date,time=dt_parts(d.get("CrashDateTime")); hour=""; matched+=1
            else: date=""; time=""; hour=s(r.get("HOUR_OF_CRASH"))
            mc,ml=(('',d.get("MannerOfCollision",'')) if d.get("MannerOfCollision") else manner_from_type(r.get("CRASH_TYPE_CD"),r.get("CRASH_TYPE_TXT")))
            fhe,fhel=harmful_from_type(r.get("CRASH_TYPE_CD"),r.get("CRASH_TYPE_TXT")); ir,it=intersection(r.get("ODOT_CRASH_LOCATION_CD"),r.get("ODOT_CRASH_LOCATION_TXT"))
            row={
                "CrashID":cid,"CrashDate":date,"CrashYear":s(r.get("CRASH_YR")) or str(year),"CrashMonth":s(r.get("MONTH_OF_CRASH")),"CrashTime":time,"CrashHour":hour,"County":s(r.get("COUNTY_CD")),
                "Latitude":s(r.get("geometry_latitude")) or s(r.get("ODOT_LATITUDE_NBR")),
                "Longitude":s(r.get("geometry_longitude")) or s(r.get("ODOT_LONGITUDE_NBR")),
                "SeverityCode":s(r.get("CRASH_SEVERITY_CD")),"SeverityLabel":s(r.get("CRASH_SEVERITY_TXT")),
                "Fatalities":d.get("TotalKilled",""),"Injuries":d.get("TotalInjured",""),"Vehicles":d.get("NumberOfUnits",""),
                "MannerCode":mc,"MannerLabel":ml,"FirstHarmfulCode":fhe,"FirstHarmfulLabel":fhel,
                "WeatherCode":d.get("Weather",""),"LightCode":d.get("LightCondition",""),"RoadConditionCode":d.get("RoadCondition",""),
                "FunctionalClass":functional(r.get("FUNCTIONAL_CLASS_CD")),"IntersectionRelated":ir,"IntersectionType":it,
                "WorkZoneRelated":bd("WorkZoneRelated"),"WorkZoneType":workzone_type(d.get("WorkZoneType","")),
                "AlcoholInvolved":bd("IsAlcoholRelated"),"DrugInvolved":bd("IsDrugRelated"),
                "SpeedingInvolved":bd("IsSpeedRelated"),"HitAndRun":bd("HitSkip"),
                "PedestrianInvolved":bd("IsPedestrianRelated") or ("True" if s(r.get("CRASH_TYPE_CD"))=="8" else ""),
                "BicyclistInvolved":bd("IsBicycleRelated") or ("True" if s(r.get("CRASH_TYPE_CD"))=="11" else ""),
                "MotorcycleInvolved":bd("IsMotorcycleRelated"),"CommercialVehicleInvolved":bd("IsCommercialRelated"),
                "SchoolZoneRelated":bd("ActiveSchoolZoneRelated"),"UrbanRural":urban_rural(d.get("InCityVillageTownship","")),
                "NumberOfLanes":s(r.get("ODOT_LANES_NBR")),"DetailAvailable":str(bool(d)),"SourceLayer":"TIMS_WITH_FIGSHARE" if d else "TIMS_ONLY",
            }
            w.writerow({k:row.get(k,"") for k in OUT_FIELDS}); n+=1
    part.replace(out); print(year,n,"detail",matched,out,flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--year-start",type=int,default=2017); ap.add_argument("--year-end",type=int,default=2025); a=ap.parse_args()
    for y in range(a.year_start,a.year_end+1): build_flat(y) if y<=2020 else build_tims(y)
