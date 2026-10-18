"""Build named, crash-level New Jersey staging tables without modifying source files.

Classic NJDOT files are headerless comma-delimited fixed-layout records.  The first
field combines year, county/municipality (NCIC), and case number.  Layout changed
in 2017.  This script follows the official NJDOT Crash/Vehicle Table layouts,
repairs physical-line breaks in free-text fields, aggregates vehicle attributes,
and audits linkage to all five classic tables.  Portal years already have headers.
"""
from __future__ import annotations
import os as _uscrash_paths_os

import argparse, csv, json, re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(_uscrash_paths_os.environ['USCRASH_ROOT'])
STATES = ROOT / "States" / "NJ"
STAGING = STATES
CLASSIC = set(range(2001, 2019)) | set(range(2020, 2024))

OUT_FIELDS = [
    "CrashID", "CrashDate", "CrashTime", "Latitude", "Longitude", "County", "City",
    "SeverityRaw", "Fatalities", "Injuries", "Vehicles", "MannerRaw", "FHERaw",
    "WeatherRaw", "LightRaw", "SurfaceRaw", "AlcoholInvolved", "IntersectionRelated",
    "WorkZoneRelated", "HitAndRun", "PedestrianInvolved", "BicyclistInvolved",
    "MotorcycleInvolved", "CommercialVehicleInvolved", "PostedSpeed", "SourceSchema",
]

CRASH_TYPE = {
    "01": ("FRONT_TO_REAR", "MOTOR_VEHICLE_IN_TRANSPORT"),
    "02": ("SIDESWIPE_SAME_DIRECTION", "MOTOR_VEHICLE_IN_TRANSPORT"),
    "03": ("ANGLE", "MOTOR_VEHICLE_IN_TRANSPORT"),
    "04": ("FRONT_TO_FRONT_OR_ANGULAR", "MOTOR_VEHICLE_IN_TRANSPORT"),
    "05": ("SIDESWIPE_OPPOSITE_DIRECTION", "MOTOR_VEHICLE_IN_TRANSPORT"),
    "06": ("NOT_MOTOR_VEHICLE_IN_TRANSPORT", "PARKED_VEHICLE"),
    "07": ("OTHER_MOTOR_VEHICLE_COLLISION", "MOTOR_VEHICLE_IN_TRANSPORT"),
    "08": ("OTHER_MOTOR_VEHICLE_COLLISION", "MOTOR_VEHICLE_IN_TRANSPORT"),
    "09": ("OTHER_MOTOR_VEHICLE_COLLISION", "MOTOR_VEHICLE_IN_TRANSPORT"),
    "10": ("NOT_MOTOR_VEHICLE_IN_TRANSPORT", "ROLLOVER_OVERTURN"),
    "11": ("NOT_MOTOR_VEHICLE_IN_TRANSPORT", "FIXED_OBJECT"),
    "12": ("NOT_MOTOR_VEHICLE_IN_TRANSPORT", "ANIMAL"),
    "13": ("NOT_MOTOR_VEHICLE_IN_TRANSPORT", "PEDESTRIAN"),
    "14": ("NOT_MOTOR_VEHICLE_IN_TRANSPORT", "PEDALCYCLIST"),
    "15": ("NOT_MOTOR_VEHICLE_IN_TRANSPORT", "OTHER_NON_FIXED_OBJECT"),
    "16": ("NOT_MOTOR_VEHICLE_IN_TRANSPORT", "TRAIN"),
    "99": ("UNKNOWN", "UNKNOWN"), "00": ("UNKNOWN", "UNKNOWN"), "": ("UNKNOWN", "UNKNOWN"),
}


def records(path: Path, year: int):
    """Yield logical records, joining any newline-broken free-text continuation."""
    start = re.compile(rf"^{year}\d{{4}}")
    buffer = ""
    with path.open(encoding="latin-1", errors="strict", newline="") as handle:
        for physical in handle:
            physical = physical.rstrip("\r\n")
            if start.match(physical):
                if buffer:
                    yield next(csv.reader([buffer]))
                buffer = physical
            else:
                buffer += " " + physical
        if buffer:
            yield next(csv.reader([buffer]))


def key(row): return row[0].strip()
def val(row, i): return row[i].strip() if i < len(row) else ""


def vehicle_aggregate(year: int):
    path = STATES / str(year) / f"NJ_vehicles_{year}.csv"
    agg = defaultdict(lambda: {"rows": 0, "motorcycle": False, "commercial": False, "hitrun": False})
    type_i, hit_i = ((13, 33) if year <= 2016 else (17, 39))
    rows = 0
    for r in records(path, year):
        if len(r) <= type_i: continue
        rows += 1; a = agg[key(r)]; a["rows"] += 1
        vt = val(r, type_i).zfill(2)
        a["motorcycle"] |= vt in {"08", "11"}
        a["commercial"] |= vt[:1] in {"2", "3"}
        a["hitrun"] |= val(r, hit_i).upper() == "Y"
    return agg, rows


def audit_related(year: int, crash_keys: set[str]):
    counts = {}
    for table in ("drivers", "occupants", "pedestrians"):
        path = STATES / str(year) / f"NJ_{table}_{year}.csv"
        n = orphan = 0
        for r in records(path, year):
            if not r: continue
            n += 1; orphan += key(r) not in crash_keys
        counts[table] = {"rows": n, "unlinked_rows": orphan}
    return counts


def classic(year: int, out: Path):
    vehicles, vehicle_rows = vehicle_aggregate(year)
    src = STATES / str(year) / f"NJ_accidents_{year}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_suffix(".csv.partial")
    crash_keys, malformed = set(), 0
    with partial.open("w", encoding="utf-8-sig", newline="") as dst:
        w = csv.DictWriter(dst, fieldnames=OUT_FIELDS, lineterminator="\n"); w.writeheader()
        for r in records(src, year):
            if len(r) < 47: malformed += 1; continue
            k = key(r); crash_keys.add(k); ct = val(r, 17).zfill(2); manner, fhe = CRASH_TYPE.get(ct, ("UNKNOWN", "UNKNOWN"))
            if year <= 2016:
                surface_i, light_i, weather_i, speed_i, lat_i, lon_i = 28, 29, 30, 40, 42, 43
            else:
                surface_i, light_i, weather_i, speed_i, lat_i, lon_i = 30, 31, 32, 42, 45, 46
            lon = val(r, lon_i)
            try:
                if lon and float(lon) > 0: lon = str(-float(lon))
            except ValueError: pass
            va = vehicles.get(k, {})
            w.writerow({
                "CrashID": k, "CrashDate": val(r, 3), "CrashTime": val(r, 5),
                "Latitude": val(r, lat_i), "Longitude": lon, "County": val(r, 1), "City": val(r, 2),
                "SeverityRaw": val(r, 13), "Fatalities": val(r, 9), "Injuries": val(r, 10), "Vehicles": val(r, 18),
                "MannerRaw": manner, "FHERaw": fhe, "WeatherRaw": val(r, weather_i),
                "LightRaw": val(r, light_i), "SurfaceRaw": val(r, surface_i),
                "AlcoholInvolved": val(r, 15), "IntersectionRelated": val(r, 14),
                "WorkZoneRelated": "Y" if val(r, 34 if year >= 2017 else 32) not in {"", "00", "01", "NO"} else "N",
                "HitAndRun": "Y" if va.get("hitrun") else "N",
                "PedestrianInvolved": "Y" if ct == "13" else "N", "BicyclistInvolved": "Y" if ct == "14" else "N",
                "MotorcycleInvolved": "Y" if va.get("motorcycle") else "N",
                "CommercialVehicleInvolved": "Y" if va.get("commercial") else "N",
                "PostedSpeed": val(r, speed_i), "SourceSchema": "NJDOT_CLASSIC_2001_2016" if year <= 2016 else "NJDOT_CLASSIC_2017_PLUS",
            })
    partial.replace(out)
    related = audit_related(year, crash_keys)
    missing_vehicle_keys = sum(1 for k in crash_keys if k not in vehicles)
    return {"year": year, "crashes": len(crash_keys), "malformed_crash_records": malformed,
            "vehicle_rows": vehicle_rows, "vehicle_crashes": len(vehicles), "crashes_without_vehicle_row": missing_vehicle_keys,
            **related}


def portal(year: int, out: Path):
    src = STATES / str(year) / f"NJ_portal_crashes_{year}.csv"
    out.parent.mkdir(parents=True, exist_ok=True); partial = out.with_suffix(".csv.partial")
    n = 0
    with src.open(encoding="utf-8-sig", newline="") as s, partial.open("w", encoding="utf-8-sig", newline="") as d:
        rd=csv.DictReader(s); w=csv.DictWriter(d,fieldnames=OUT_FIELDS,lineterminator="\n");w.writeheader()
        for r in rd:
            n += 1
            w.writerow({
                "CrashID":r.get("id_cr", ""),"CrashDate":r.get("dateofcrash", ""),"CrashTime":r.get("timeofcrash", ""),
                "Latitude":r.get("latitude", ""),"Longitude":r.get("longitude", ""),"County":r.get("County", ""),"City":r.get("Municipality", ""),
                "SeverityRaw":r.get("Severity Rating (5)", ""),"Fatalities":r.get("fatalitycount", ""),"Injuries":r.get("injurycount", ""),"Vehicles":r.get("vehiclecount", ""),
                "MannerRaw":r.get("Crash Type", ""),"FHERaw":r.get("First Harmful Event", ""),"WeatherRaw":r.get("Weather Condition", ""),
                "LightRaw":r.get("Light Condition", ""),"SurfaceRaw":r.get("Surface Condition", ""),"AlcoholInvolved":r.get("Alcohol Involved", ""),
                "IntersectionRelated":r.get("At Intersection", ""),"WorkZoneRelated":"Y" if r.get("Traffic Control Zone", "") not in {"", "None"} else "N",
                "HitAndRun":"", "PedestrianInvolved":"Y" if int(r.get("pedestrianfatalitycount") or 0)+int(r.get("pedestrianinjurycount") or 0)>0 else "N",
                "BicyclistInvolved":"", "MotorcycleInvolved":"", "CommercialVehicleInvolved":"", "PostedSpeed":r.get("speedlimit", ""),
                "SourceSchema":"NJDOT_AASHTOWARE_PORTAL",
            })
    partial.replace(out); return {"year":year,"crashes":n}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--year",type=int);args=ap.parse_args()
    years=[args.year] if args.year else list(range(2001,2027)); manifest=[]
    for y in years:
        out=STAGING/str(y)/f"NJ_prepared_crashes_{y}.csv"
        result=classic(y,out) if y in CLASSIC else portal(y,out)
        manifest.append(result);print(json.dumps(result),flush=True)
    (STAGING/"preparation_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")

if __name__ == "__main__": main()
