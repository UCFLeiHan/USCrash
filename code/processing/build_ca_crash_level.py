"""Build reproducible California crash-level inputs from the three CCRS tables."""
import argparse, csv, re
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"F:\LH_Research\USCrash\Crash")
CA = ROOT / "States" / "CA"

SEVERITY_RANK = {
    "PossibleInjury": (1, "C"), "ComplaintOfPainInactive": (1, "C"),
    "SuspectMinor": (2, "B"), "OtherVisibleInactive": (2, "B"),
    "SuspectSerious": (3, "A"), "SevereInactive": (3, "A"),
    "Fatal": (4, "K"),
}

FIELDS = [
    "CollisionId", "CrashDateTime", "County", "City", "Latitude", "Longitude",
    "Severity", "SeverityRaw", "Fatalities", "Injuries", "Vehicles",
    "MannerCategory", "MannerRaw", "HarmfulCategory", "HarmfulRaw",
    "WeatherCategory", "WeatherRaw", "LightCategory", "LightRaw",
    "SurfaceCategory", "SurfaceRaw", "WorkZone", "AlcoholInvolved",
    "DrugInvolved", "HitRun", "PedestrianCount", "BicyclistCount",
    "MotorcycleCount", "SchoolBusRelated", "IsPreliminary",
]

def clean(row):
    return {(k or "").strip(): (v or "").strip() for k, v in row.items()
            if k is not None and not isinstance(v, list)}

def truth(v): return v.casefold() == "true"

def weather(v):
    x = v.strip().upper()
    if not x: return ""
    if "RAIN" in x or "DRIZZ" in x or "SPRINK" in x: return "RAIN"
    if "SNOW" in x: return "SNOW"
    if "HAIL" in x or "SLEET" in x or "ICE" in x: return "SLEET_HAIL"
    if "FOG" in x or "MIST" in x or "SMOKE" in x or "HAZE" in x: return "FOG_SMOKE"
    if "WIND" in x: return "SEVERE_CROSSWIND"
    if "DUST" in x or "SANDSTORM" in x: return "BLOWING_SAND_SOIL"
    if x in {"CLEAR", "SUN", "SUNNY", "SUNLIGHT"}: return "CLEAR"
    if "CLOUD" in x or "OVERCAST" in x: return "CLOUDY"
    if x in {"UNKNOWN", "UNK"}: return "UNKNOWN"
    return "OTHER"

def light(v):
    return {"DAYLIGHT":"DAYLIGHT", "DARK-STREET LIGHTS":"DARK_LIGHTED",
            "DARK-NO STREET LIGHTS":"DARK_UNLIGHTED",
            "DARK-STREET LIGHTS NOT FUNCTIONING*":"DARK_UNLIGHTED",
            "DUSK-DAWN":"OTHER"}.get(v.strip().upper(), "" if not v.strip() else "OTHER")

def surface(code):
    return {"A":"DRY", "B":"WET", "C":"ICE_FROST", "D":"OTHER"}.get(code.strip().upper(), "" if not code.strip() else "UNKNOWN")

def manner(v):
    return {"REAR END":"1", "HEAD-ON":"2", "BROADSIDE":"6", "SIDE SWIPE":"11",
            "OTHER":"11", "HIT OBJECT":"0", "OVERTURNED":"0",
            "VEHICLE/PEDESTRAIN":"0"}.get(v.strip().upper(), "")

def harmful(v):
    return {"OTHER MOTOR VEHICLE":"MOTOR_VEHICLE_IN_TRANSPORT",
            "MOTOR VEHICLE ON OTHER ROADWAY":"MOTOR_VEHICLE_IN_TRANSPORT",
            "FIXED OBJECT":"FIXED_OBJECT", "PARKED MOTOR VEHICLE":"PARKED_VEHICLE",
            "PEDESTRIAN":"PEDESTRIAN", "BICYCLE":"PEDALCYCLIST",
            "NON-COLLISION":"OTHER_NON_COLLISION", "OTHER OBJECT":"OTHER_NON_FIXED_OBJECT",
            "ANIMAL":"ANIMAL", "TRAIN":"TRAIN"}.get(v.strip().upper(), "")

def build_year(year):
    folder = CA / str(year)
    people = defaultdict(lambda: [0, "", ""])
    with (folder / f"InjuredWitnessPassengers_{year}.csv").open(encoding="utf-8-sig", newline="") as f:
        for raw in csv.DictReader(f):
            r = clean(raw); cid = r.get("CollisionId", ""); code = r.get("ExtentOfInjuryCode", "")
            if not cid or code not in SEVERITY_RANK: continue
            rank, kabco = SEVERITY_RANK[code]
            if rank > people[cid][0]: people[cid] = [rank, kabco, code]

    parties = defaultdict(lambda: {"vehicles":0,"ped":0,"bike":0,"mc":0,"school":False,
                                   "alcohol":False,"drug":False,"hitrun":False})
    with (folder / f"Parties_{year}.csv").open(encoding="utf-8-sig", newline="") as f:
        for raw in csv.DictReader(f):
            r = clean(raw); cid = r.get("CollisionId", "")
            if not cid: continue
            a = parties[cid]; ptype = r.get("PartyType", ""); vehicle = r.get("Vehicle1TypeDesc", "")
            if ptype in {"Driver", "ParkedVehicle"}: a["vehicles"] += 1
            if ptype == "Pedestrian": a["ped"] += 1
            if ptype == "Bicyclist": a["bike"] += 1
            vl = vehicle.casefold()
            if "motorcycle" in vl or "motordrivencycle" in vl: a["mc"] += 1
            if "schoolbus" in vl: a["school"] = True
            if truth(r.get("IsHitAndRun", "")): a["hitrun"] = True
            codes = {r.get("SobrietyDrugPhysicalCode1", ""), r.get("SobrietyDrugPhysicalCode2", "")}
            if "B" in codes: a["alcohol"] = True
            if "E" in codes: a["drug"] = True

    outdir = folder / "Derived"; outdir.mkdir(exist_ok=True)
    output = outdir / f"CA_crash_level_{year}.csv"; partial = output.with_suffix(".csv.partial")
    rows = 0
    with (folder / f"Crashes_{year}.csv").open(encoding="utf-8-sig", newline="") as f, partial.open("w", encoding="utf-8-sig", newline="") as g:
        w = csv.DictWriter(g, fieldnames=FIELDS, lineterminator="\n"); w.writeheader()
        for raw in csv.DictReader(f):
            r = clean(raw); cid = r["Collision Id"]; a = parties[cid]; p = people[cid]
            killed = r.get("NumberKilled", ""); injured = r.get("NumberInjured", "")
            if p[1]: sev, sevraw = p[1], p[2]
            elif killed and int(killed) > 0: sev, sevraw = "K", "DERIVED_NUMBER_KILLED"
            elif injured and int(injured) > 0: sev, sevraw = "U", "INJURY_LEVEL_UNAVAILABLE"
            else: sev, sevraw = "O", "NO_REPORTED_INJURY"
            mraw = r.get("Collision Type Description", ""); hraw = r.get("MotorVehicleInvolvedWithDesc", "")
            wr = r.get("Weather 1", ""); lr = r.get("LightingDescription", ""); sr = r.get("RoadwaySurfaceCode", "")
            hit = a["hitrun"] or bool(r.get("HitRun", ""))
            work = "CONSTRUCTION-REPAIR ZONE" in r.get("Road Condition 1", "").upper()
            w.writerow({
                "CollisionId":cid, "CrashDateTime":r.get("Crash Date Time", ""),
                "County":r.get("County Code", ""), "City":r.get("City Name", ""),
                "Latitude":r.get("Latitude", ""), "Longitude":r.get("Longitude", ""),
                "Severity":sev, "SeverityRaw":sevraw, "Fatalities":killed, "Injuries":injured,
                "Vehicles":a["vehicles"], "MannerCategory":manner(mraw), "MannerRaw":mraw,
                "HarmfulCategory":harmful(hraw), "HarmfulRaw":hraw,
                "WeatherCategory":weather(wr), "WeatherRaw":wr,
                "LightCategory":light(lr), "LightRaw":lr,
                "SurfaceCategory":surface(sr), "SurfaceRaw":sr,
                "WorkZone":str(work), "AlcoholInvolved":str(a["alcohol"]),
                "DrugInvolved":str(a["drug"]), "HitRun":str(hit),
                "PedestrianCount":a["ped"], "BicyclistCount":a["bike"],
                "MotorcycleCount":a["mc"], "SchoolBusRelated":str(a["school"]),
                "IsPreliminary":r.get("Is Preliminary", ""),
            }); rows += 1
    partial.replace(output); print(year, rows, output, flush=True)

if __name__ == "__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--year-start",type=int,default=2016); ap.add_argument("--year-end",type=int,default=2026); a=ap.parse_args()
    for y in range(a.year_start,a.year_end+1): build_year(y)
