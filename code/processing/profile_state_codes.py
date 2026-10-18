from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from project_source_coordinates import coordinate_values

ROOT = Path(os.environ.get("USCRASH_ROOT", r"F:\LH_Research\USCrash\Crash"))
PIPE = ROOT / "Unified_MMUCC6"
STATES = ROOT / "States"
PAIRS = ["severity", "injury_severity", "manner", "weather", "light", "road_surface"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def resolve_field(spec: str, headers: list[str]) -> str:
    optional = spec.startswith("?")
    if optional:
        spec = spec[1:]
    alternatives = spec.split("|")
    for name in alternatives:
        if name in headers:
            return name
    if optional:
        return ""
    raise ValueError(f"none of {alternatives!r} found")


def resolve_source(state: str, year: int, version: dict) -> Path:
    ydir = STATES / state / str(year)
    matches = [ydir / p.format(year=year) for p in version["source_patterns"]]
    found = [p for p in matches if p.is_file() and p.stat().st_size > 0]
    if len(found) != 1:
        raise FileNotFoundError(f"{state} {year}: expected exactly one configured source; found {found}")
    return found[0]


def main():
    ap = argparse.ArgumentParser(description="Profile source code/label domains before MMUCC crosswalking")
    ap.add_argument("--state", required=True)
    args = ap.parse_args()
    state = args.state.upper()
    config_path = PIPE / "config" / "states" / f"{state}.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    bounds = config.get("coordinate_bounds", [-125.0, 41.0, -116.0, 47.0])
    output_dir = PIPE / "qa" / "preflight" / "code_profiles" / state
    output_dir.mkdir(parents=True, exist_ok=True)
    all_profiles = {name: Counter() for name in PAIRS}
    year_rows = []
    coordinate_issues = []

    for version in config["versions"]:
        for year in range(version["year_start"], version["year_end"] + 1):
            source = resolve_source(state, year, version)
            source_encoding = version.get("encoding", "utf-8-sig")
            with source.open("r", encoding=source_encoding, errors="strict", newline="") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                if len(headers) != len(set(headers)):
                    raise ValueError(f"{source}: duplicate headers")
                resolved = {k: value for k, v in version["fields"].items()
                            if (value := resolve_field(v, headers))}
                count = 0
                blank_ids = 0
                ids = set()
                duplicates = 0
                year_mismatch = 0
                coordinate_invalid = 0
                for row in reader:
                    count += 1
                    crash_id = row[resolved["crash_id"]].strip()
                    if not crash_id:
                        blank_ids += 1
                    elif crash_id in ids:
                        duplicates += 1
                    else:
                        ids.add(crash_id)
                    date_field = resolved.get("crash_datetime") or resolved.get("crash_date")
                    date_value = row[date_field].strip()
                    if str(year) not in date_value:
                        year_mismatch += 1
                    lat_raw, lon_raw = coordinate_values(row, resolved, version)
                    try:
                        lat = float(lat_raw); lon = float(lon_raw)
                        if not (bounds[1] <= lat <= bounds[3] and bounds[0] <= lon <= bounds[2]):
                            coordinate_invalid += 1
                            if len(coordinate_issues) < 1000:
                                coordinate_issues.append({"state": state, "year": year, "crash_id": crash_id,
                                    "latitude_raw": lat_raw, "longitude_raw": lon_raw,
                                    "reason": "outside_broad_state_bounds"})
                    except (ValueError, TypeError):
                        coordinate_invalid += 1
                        if len(coordinate_issues) < 1000:
                            coordinate_issues.append({"state": state, "year": year, "crash_id": crash_id,
                                "latitude_raw": lat_raw, "longitude_raw": lon_raw,
                                "reason": "missing_or_non_numeric"})
                    for name in PAIRS:
                        if f"{name}_raw_code" not in resolved or f"{name}_raw_label" not in resolved:
                            continue
                        code = row[resolved[f"{name}_raw_code"]].strip()
                        label = row[resolved[f"{name}_raw_label"]].strip()
                        all_profiles[name][(version["schema_id"], code, label)] += 1
            year_rows.append({
                "state": state, "schema_id": version["schema_id"], "year": year,
                "source_file": str(source), "source_sha256": sha256(source), "rows": count,
                "unique_crash_ids": len(ids), "blank_crash_ids": blank_ids,
                "duplicate_crash_ids": duplicates, "date_year_mismatch": year_mismatch,
                "coordinate_missing_or_out_of_bounds": coordinate_invalid,
            })
            print(f"{state} {year}: {count} rows", flush=True)

    for name, counts in all_profiles.items():
        path = output_dir / f"{name}_codes.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            fields = ["state", "schema_id", "source_field_group", "source_code", "source_label", "count"]
            writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for (schema, code, label), count in sorted(counts.items()):
                writer.writerow({"state": state, "schema_id": schema, "source_field_group": name,
                                 "source_code": code, "source_label": label, "count": count})

    manifest = output_dir / "year_validation.csv"
    with manifest.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(year_rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(year_rows)
    coordinate_path = output_dir / "coordinate_issues.csv"
    with coordinate_path.open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["state", "year", "crash_id", "latitude_raw", "longitude_raw", "reason"]
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(coordinate_issues)
    run = {
        "tool": "profile_state_codes.py", "state": state,
        "config": str(config_path), "config_sha256": sha256(config_path),
        "executed_utc": datetime.now(timezone.utc).isoformat(), "years": len(year_rows),
        "result": "PASS",
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    print(json.dumps(run, indent=2))


if __name__ == "__main__":
    main()
