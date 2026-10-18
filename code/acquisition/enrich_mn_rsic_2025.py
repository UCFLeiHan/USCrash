"""Join annual Minnesota RSIC detail to MnCrash public collision records.

The filename is retained for backwards compatibility; the program now accepts
one or more years and defaults to every year for which both inputs exist.
"""
from __future__ import annotations
import argparse, csv, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

STATE_ROOT = Path(r"F:\LH_Research\USCrash\Crash\States\MN")
RSIC_FIELDS = ["CrashType", "CrashDetail", "WeatherCde_txtCARTO", "SurfaceConditionCde_txtCARTO", "ExceedingSpeedLimitInd_boolCARTO", "AlcoholSuspectedCde_txtCARTO", "DrugSuspectedCde_txtCARTO", "WorkZoneInd_txtCARTO", "HitAndRunInd_txtCARTO", "Num_Occupants", "Num_MotorVehicles", "NonMotorist_calc", "Aggregated_Non_Motorist_txt", "RelativeLocIntersectCde", "PostedSpeedNbr_binCARTO", "RdwyTypeCde_txtCARTO"]

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""): h.update(block)
    return h.hexdigest()

def coord(value):
    try: return round(float(value), 6)
    except (TypeError, ValueError): return None

def public_dt(value):
    try: return datetime.strptime(value.strip(), "%m/%d/%Y %I:%M:%S %p").strftime("%Y-%m-%d %H:%M:%S")
    except (AttributeError, ValueError): return ""

def paths(year):
    root = STATE_ROOT / str(year)
    return (root / f"MnCrash_public_collisions_{year}.csv", root / f"MN_RSIC_all_crashes_{year}.csv", root / f"MN_MnCrash_RSIC_enriched_{year}.csv", root / f"MN_MnCrash_RSIC_enriched_{year}.metadata.json")

def enrich(year):
    public, rsic, output, manifest = paths(year)
    for required in (public, rsic):
        if not required.exists(): raise FileNotFoundError(required)
    detail = {}; duplicate_keys = 0; ambiguous_keys = set(); rsic_rows = 0
    with rsic.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = set(["DateOfIncident", "LatDec", "LongDec", *RSIC_FIELDS]) - set(reader.fieldnames or [])
        if missing: raise ValueError(f"{rsic}: missing fields {sorted(missing)}")
        for row in reader:
            rsic_rows += 1
            key = (row["DateOfIncident"].strip(), coord(row["LatDec"]), coord(row["LongDec"]))
            if key in detail:
                duplicate_keys += 1; ambiguous_keys.add(key)
            else:
                detail[key] = row
    matched_keys = set(); matched = unmatched = rows = 0
    tmp = output.with_suffix(".csv.partial")
    with public.open(encoding="utf-8-sig", newline="") as src, tmp.open("w", encoding="utf-8-sig", newline="") as dst:
        reader = csv.DictReader(src)
        out_fields = (reader.fieldnames or []) + [f"RSIC_{field}" for field in RSIC_FIELDS]
        writer = csv.DictWriter(dst, fieldnames=out_fields, lineterminator="\n"); writer.writeheader()
        for row in reader:
            row.pop(None, None); rows += 1
            key = (public_dt(row["Crash Date"]), coord(row["Latitude"]), coord(row["Longitude"]))
            # A same-time/same-coordinate key can represent distinct crashes.
            # Leave such rows unmatched rather than assigning an arbitrary detail row.
            detail_row = None if key in ambiguous_keys else detail.get(key)
            if detail_row: matched += 1; matched_keys.add(key)
            else: unmatched += 1
            for field in RSIC_FIELDS: row[f"RSIC_{field}"] = detail_row[field].strip() if detail_row else ""
            writer.writerow(row)
    tmp.replace(output)
    metadata = {"year": year, "created_utc": datetime.now(timezone.utc).isoformat(), "join_key": "crash datetime + latitude/longitude rounded to 6 decimals", "ambiguity_policy": "duplicate RSIC keys are left unmatched", "public_rows": rows, "rsic_rows": rsic_rows, "matched_public_rows": matched, "unmatched_public_rows": unmatched, "matched_rate": matched / rows if rows else None, "matched_rsic_rows": len(matched_keys), "unmatched_rsic_rows": rsic_rows - len(matched_keys), "duplicate_rsic_rows_beyond_first": duplicate_keys, "ambiguous_rsic_join_keys": len(ambiguous_keys), "public_sha256": sha(public), "rsic_sha256": sha(rsic), "output_sha256": sha(output), "output_rows": rows, "rsic_fields": [f"RSIC_{field}" for field in RSIC_FIELDS]}
    manifest.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata

def available_years():
    result = []
    for folder in STATE_ROOT.iterdir():
        if folder.is_dir() and folder.name.isdigit():
            year = int(folder.name); public, rsic, _, _ = paths(year)
            if public.exists() and rsic.exists(): result.append(year)
    return sorted(result)

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("years", nargs="*", type=int)
    years = parser.parse_args().years or available_years()
    print(json.dumps([enrich(year) for year in years], indent=2))

if __name__ == "__main__": main()
