from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from project_source_coordinates import coordinate_values

ROOT = Path(os.environ.get("USCRASH_ROOT", r"F:\LH_Research\USCrash\Crash"))
PIPE = ROOT / "Unified_MMUCC6"
# An explicit read-only source root permits isolated, auditable rebuilds.
STATES = Path(os.environ.get("USCRASH_SOURCE_ROOT", str(ROOT / "States")))
VERSION = "0.2.0"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def resolve_source(state, year, version):
    options = [STATES / state / str(year) / p.format(year=year) for p in version["source_patterns"]]
    found = [p for p in options if p.is_file() and p.stat().st_size]
    if len(found) != 1:
        raise RuntimeError(f"{state} {year}: expected one source, found {found}")
    return found[0]


def resolve_fields(specs, headers):
    result = {}
    for key, spec in specs.items():
        optional = spec.startswith("?")
        if optional: spec = spec[1:]
        match = next((x for x in spec.split("|") if x in headers), None)
        if match: result[key] = match
        elif not optional: raise RuntimeError(f"required field {key} ({spec}) absent")
    return result


def integer(value):
    value = value.strip()
    if not value: return ""
    try:
        return str(int(float(value)))
    except ValueError:
        if value.casefold().startswith("no "): return "0"
        match = re.match(r"(\d+)\b", value)
        if match: return match.group(1)
        raise


def strict_integer(value):
    """Parse an integer only when the entire source value is integer-like."""
    value = (value or "").strip()
    if not value: return ""
    if not re.fullmatch(r"[+-]?\d+(?:\.0+)?", value):
        raise ValueError(f"unrecognized strict integer {value!r}")
    return str(int(float(value)))


def vehicle_count(value):
    value = value.strip()
    if not value: return "", "", "", "UNAVAILABLE"
    try:
        exact = str(int(float(value)))
        return exact, exact, value, "EXACT"
    except ValueError:
        numbered = re.fullmatch(r"(\d+)\s+Vehicles?", value, re.I)
        if numbered:
            exact = numbered.group(1)
            return exact, exact, value, "EXACT"
        match = re.match(r"more\s+than\s+(\d+)", value, re.I)
        if match:
            minimum = str(int(match.group(1)) + 1)
            return "", minimum, value, "LOWER_BOUND"
        match = re.match(r"(\d+)\s+or\s+more\s+vehicles?", value, re.I)
        if match:
            return "", match.group(1), value, "LOWER_BOUND"
        raise ValueError(f"unrecognized vehicle count {value!r}")


def parse_date(value, epoch_millis_timezone=None):
    value = value.strip().rstrip(".")
    if not value or value == "0": return ""
    if re.fullmatch(r"\d{12,13}", value):
        # ArcGIS date exports are UTC epoch milliseconds. Official annual
        # layers encode the local crash date at a UTC hour that preserves the
        # same calendar date, so extract the UTC calendar date deterministically.
        dt = datetime.fromtimestamp(int(value) / 1000, timezone.utc)
        if epoch_millis_timezone:
            dt = dt.astimezone(ZoneInfo(epoch_millis_timezone))
        return dt.date().isoformat()
    if "T" in value: return value.split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d",
                "%m/%d/%Y", "%m/%d/%y", "%m %d %Y",
                "%m/%d/%Y %I:%M:%S %p"):
        try: return datetime.strptime(value, fmt).date().isoformat()
        except ValueError: pass
    raise ValueError(f"unparseable date {value!r}")


def parse_month_strict(value):
    """Parse numeric months or exact English full/abbreviated month names."""
    value = (value or "").strip()
    if value.isdigit():
        month = int(value)
        if 1 <= month <= 12:
            return month
        raise ValueError(f"invalid crash month {value!r}")
    for fmt in ("%B", "%b"):
        try:
            return datetime.strptime(value, fmt).month
        except ValueError:
            pass
    raise ValueError(f"invalid crash month {value!r}")


def parse_datetime_value(value):
    value = value.strip()
    if re.fullmatch(r"\d{12,13}", value):
        dt = datetime.fromtimestamp(int(value) / 1000, timezone.utc)
        return dt.date().isoformat(), dt.time().replace(tzinfo=None).isoformat(), "SECOND"
    try:
        iso_value = value.replace("Z", "+00:00").replace("/", "-")
        if re.search(r"[+-]\d{2}$", iso_value): iso_value += ":00"
        dt = datetime.fromisoformat(iso_value)
        return dt.date().isoformat(), dt.time().replace(tzinfo=None).isoformat(), "SECOND"
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M %p", "%m/%d/%Y %I:%M:%S %p",
                "%d-%b-%Y %I:%M %p", "%d-%b-%Y %I:%M:%S %p",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S%z"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.date().isoformat(), dt.time().isoformat(), "SECOND"
        except ValueError:
            pass
    raise ValueError(f"unparseable datetime {value!r}")


def parse_time(raw, hour):
    raw = raw.strip(); hour = hour.strip()
    if raw:
        is_range = bool(re.search(r"\s+(?:to|[-–—])\s+", raw, flags=re.I))
        first = re.split(r"\s+(?:to|[-–—])\s+", raw, maxsplit=1, flags=re.I)[0]
        first = re.sub(r"\bMidnight\b", "AM", first, flags=re.I)
        first = re.sub(r"\bNoon\b", "PM", first, flags=re.I)
        for fmt in ("%I:%M %p", "%H:%M", "%H:%M:%S"):
            try: return datetime.strptime(first, fmt).time().isoformat(), "HOUR_RANGE" if is_range else "MINUTE"
            except ValueError: pass
        # Several official state extracts store local military time as HMM/HHMM
        # (for example, 127 = 01:27 and 1700 = 17:00). Keep this parsing
        # explicit so numeric codes cannot be mistaken for decimal hours.
        if re.fullmatch(r"\d{1,4}", first):
            military = first.zfill(4)
            h, m = int(military[:2]), int(military[2:])
            if 0 <= h <= 23 and 0 <= m <= 59:
                return f"{h:02d}:{m:02d}:00", "MINUTE"
        # Some official exports serialize local clock time as H.MM/HH.MM.
        # A one-digit fractional part represents tens of minutes because
        # spreadsheet numeric formatting drops a trailing zero (6.3 = 06:30).
        dotted = re.fullmatch(r"(\d{1,2})\.(\d{1,2})", first)
        if dotted:
            h = int(dotted.group(1))
            m = int(dotted.group(2).ljust(2, "0"))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return f"{h:02d}:{m:02d}:00", "MINUTE"
    if hour:
        h = int(float(hour))
        if 0 <= h <= 23: return f"{h:02d}:00:00", "HOUR"
    return "", "DATE"


def load_crosswalk(state):
    path = PIPE / "config" / f"code_crosswalk_{state}.csv"
    maps = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = (row["field_group"], row["source_code"], row["source_label"].strip().casefold())
            if key in maps: raise RuntimeError(f"duplicate crosswalk key: {key}")
            maps[key] = row
    return path, maps


def crosswalk_value(maps, group, code, label):
    """Resolve an audited categorical mapping, allowing reviewed code- or label-only rules."""
    code = (code or "").strip()
    label = (label or "").strip()
    return (maps.get((group, code, label.casefold())) or
            maps.get((group, code, "")) or
            maps.get((group, "", label.casefold())))


def mapped_category(raw, fields, maps, prefix, group, unknown):
    code_field = f"{prefix}_raw_code"
    label_field = f"{prefix}_raw_label"
    if code_field not in fields and label_field not in fields:
        return "", "", "", "UNAVAILABLE"
    code = raw[fields[code_field]].strip() if code_field in fields else ""
    label = raw[fields[label_field]].strip() if label_field in fields else ""
    if not code and not label:
        return "", code, label, "SOURCE_MISSING"
    mapped = crosswalk_value(maps, group, code, label)
    if not mapped:
        unknown.add((group, code, label))
        return "", code, label, "UNRESOLVED_CODE"
    return mapped["canonical_code"], code, label, mapped["mapping_status"]


def normalized_flag(value):
    value = (value or "").strip().casefold()
    if not value: return ""
    if value in {"1", "101", "y", "yes", "true", "involved", "hit-and-run", "yes, directly invovled", "yes, indirectly involved"} or value.startswith("yes") or " yes" in value or "directly involved" in value or "indirectly involved" in value: return "TRUE"
    if value in {"0", "102", "n", "no", "false", "not hit-and-run", "not an intersection"} or value.startswith("no") or "not involved" in value: return "FALSE"
    if value in {"-9", "9", "99", "999", "unknown", "u", "na", "n/a",
                 "reported but invalid", "not reported"}: return "UNKNOWN"
    if value.isdigit(): return "TRUE" if int(value) > 0 else "FALSE"
    raise ValueError(f"unrecognized flag value {value!r}")


def load_detail_crosswalk(state):
    path = PIPE / "config" / f"code_crosswalk_{state}_manner_detail.csv"
    maps = {}
    if not path.exists(): return path, maps
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = (row["parent_source_code"], row["detail_source_code"], row["detail_source_label"].strip().casefold())
            if key in maps: raise RuntimeError(f"duplicate detail crosswalk key: {key}")
            maps[key] = row
    return path, maps


def main():
    ap = argparse.ArgumentParser(description="Create state/year harmonized crash tables from reviewed configuration")
    ap.add_argument("--state", required=True)
    ap.add_argument("--year-start", type=int)
    ap.add_argument("--year-end", type=int)
    args = ap.parse_args()
    state = args.state.upper()
    config_path = PIPE / "config" / "states" / f"{state}.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    crash_id_scope = config.get("crash_id_scope", "STATE")
    deduplicate_by_crash_id = bool(config.get("deduplicate_by_crash_id", False))
    skip_if_blank = list(config.get("skip_if_blank", []))
    row_valid_values = dict(config.get("row_valid_values", {}))
    severity_from_fatalities_when_unknown = bool(config.get("severity_from_fatalities_when_unknown", False))
    severity_from_fatalities_always = bool(config.get("severity_from_fatalities_always", False))
    if crash_id_scope not in {"STATE", "YEAR"}:
        raise RuntimeError(f"unsupported crash_id_scope {crash_id_scope!r}")
    bounds = config.get("coordinate_bounds", [-125.0, 41.0, -116.0, 47.0])
    schema_path = PIPE / "config" / "canonical_crash_schema.csv"
    with schema_path.open(encoding="utf-8-sig", newline="") as f:
        output_fields = [r["field_name"] for r in csv.DictReader(f)]
    crosswalk_path, crosswalk = load_crosswalk(state)
    detail_crosswalk_path, detail_crosswalk = load_detail_crosswalk(state)
    out_dir = PIPE / "data" / "crash" / state
    qa_dir = PIPE / "qa" / "post_harmonization" / state
    out_dir.mkdir(parents=True, exist_ok=True); qa_dir.mkdir(parents=True, exist_ok=True)
    summaries = []

    for version in config["versions"]:
        # Compatible category codes do not make MOST and FIRST event order equivalent.
        for key in ("first_harmful_event_raw_code", "first_harmful_event_raw_label"):
            if "MOST_HARM" in version.get("fields", {}).get(key, "").upper():
                raise ValueError(f"{state}: most harmful event cannot supply {key}")
        for year in range(version["year_start"], version["year_end"] + 1):
            if args.year_start and year < args.year_start: continue
            if args.year_end and year > args.year_end: continue
            source = resolve_source(state, year, version)
            output = out_dir / f"{state}_crashes_harmonized_{year}.csv"
            partial = output.with_suffix(".csv.partial")
            unknown = set(); source_rows = 0; output_rows = 0; duplicate_source_rows = 0; excluded_source_rows = 0
            invalid_coords = 0; unresolved_manner = 0; seen_crash_ids = set()
            source_encoding = version.get("encoding", "utf-8-sig")
            with source.open("r", encoding=source_encoding, errors="strict", newline="") as src, partial.open("w", encoding="utf-8-sig", newline="") as dst:
                reader = csv.DictReader(src); headers = reader.fieldnames or []
                fields = resolve_fields(version["fields"], headers)
                writer = csv.DictWriter(dst, fieldnames=output_fields, lineterminator="\n", extrasaction="raise")
                writer.writeheader()
                for row_number, raw in enumerate(reader, 1):
                    source_rows += 1
                    excluded_field_values = version.get("exclude_if_field_values", {})
                    if any(raw[fields[name]].strip() in values
                           for name, values in excluded_field_values.items() if name in fields):
                        excluded_source_rows += 1
                        continue
                    if any(not raw[fields[name]].strip() for name in skip_if_blank):
                        excluded_source_rows += 1
                        continue
                    if any(raw[fields[name]].strip() not in allowed
                           for name, allowed in row_valid_values.items() if name in fields):
                        excluded_source_rows += 1
                        continue
                    crash_id = (str(row_number) if version.get("crash_id_from_row_number", False)
                                else raw[fields["crash_id"]].strip())
                    if deduplicate_by_crash_id and crash_id in seen_crash_ids:
                        duplicate_source_rows += 1
                        continue
                    seen_crash_ids.add(crash_id)
                    output_rows += 1
                    if version.get("date_precision") == "MONTH":
                        date_year = int(raw[fields["crash_year"]].strip())
                        date_month = parse_month_strict(raw[fields["crash_month"]])
                        crash_date = ""
                        crash_time, precision = parse_time(
                            raw[fields["crash_time_raw"]] if "crash_time_raw" in fields else "",
                            raw[fields["crash_hour"]] if "crash_hour" in fields else "")
                        crash_year = str(date_year); crash_month = str(date_month)
                        date_precision = "MONTH"
                    elif "crash_datetime" in fields:
                        crash_date, crash_time, precision = parse_datetime_value(raw[fields["crash_datetime"]])
                    elif all(x in fields for x in ("crash_year", "crash_month", "crash_day")):
                        month = parse_month_strict(raw[fields["crash_month"]])
                        date_year = year if version.get("date_year_from_file", False) else int(raw[fields["crash_year"]])
                        crash_date = datetime(date_year, month,
                                              int(raw[fields["crash_day"]])).date().isoformat()
                        crash_time, precision = parse_time(
                            raw[fields["crash_time_raw"]] if "crash_time_raw" in fields else "", "")
                    else:
                        source_date = raw[fields["crash_date"]].strip()
                        if source_date in set(version.get("invalid_date_values_as_missing", [])):
                            crash_date = ""
                        else:
                            crash_date = parse_date(source_date, version.get("epoch_millis_timezone"))
                        crash_time, precision = parse_time(
                            raw[fields["crash_time_raw"]] if "crash_time_raw" in fields else "",
                            raw[fields["crash_hour"]] if "crash_hour" in fields else "",
                        )
                    if version.get("date_precision") != "MONTH":
                        if crash_date:
                            crash_year = crash_date[:4]
                            crash_month = str(int(crash_date[5:7]))
                            date_precision = "DAY"
                        elif version.get("partial_date_from_year_month_when_date_missing", False):
                            year_raw = raw[fields["crash_year"]].strip()
                            month_raw = raw[fields["crash_month"]].strip()
                            if not re.fullmatch(r"\d{4}", year_raw):
                                raise ValueError(f"invalid partial crash year {year_raw!r}")
                            if not re.fullmatch(r"\d{1,2}", month_raw):
                                raise ValueError(f"invalid partial crash month {month_raw!r}")
                            partial_year, partial_month = int(year_raw), int(month_raw)
                            if not 1900 <= partial_year <= 2100:
                                raise ValueError(f"partial crash year outside supported range {partial_year!r}")
                            if not 1 <= partial_month <= 12:
                                raise ValueError(f"invalid partial crash month {partial_month!r}")
                            crash_year = str(partial_year)
                            crash_month = str(partial_month)
                            date_precision = "MONTH"
                        else:
                            crash_year = ""
                            crash_month = ""
                            date_precision = "MISSING"
                    lat_raw, lon_raw = coordinate_values(raw, fields, version)
                    try:
                        lat = float(lat_raw); lon = float(lon_raw)
                        coordinate_status = "VALID" if bounds[1] <= lat <= bounds[3] and bounds[0] <= lon <= bounds[2] else "OUT_OF_BOUNDS"
                    except ValueError:
                        lat = lon = None; coordinate_status = "MISSING" if not lat_raw and not lon_raw else "INVALID"
                    if coordinate_status != "VALID": invalid_coords += 1
                    latitude = str(lat) if coordinate_status == "VALID" else ""
                    longitude = str(lon) if coordinate_status == "VALID" else ""

                    if version.get("severity_from_fatality_injury_counts", False):
                        sc = sl = ""
                        fatality_value = integer(raw[fields["fatalities"]]) if "fatalities" in fields else ""
                        injury_value = integer(raw[fields["injuries"]]) if "injuries" in fields else ""
                        if fatality_value != "" and int(fatality_value) > 0:
                            severity = "K"
                        elif injury_value != "" and int(injury_value) > 0:
                            severity = "U"
                        elif fatality_value != "" and injury_value != "":
                            severity = "O"
                        else:
                            severity = "U"
                        severity_prov = ("INJURY_PRESENT_SEVERITY_UNSPECIFIED" if severity == "U" and
                                         injury_value != "" and int(injury_value) > 0 else
                                         "DERIVED_FATALITY_INJURY_COUNTS")
                    elif version.get("severity_from_injury_counts", False):
                        sc = sl = ""
                        count_codes = (("severity_count_k", "K"), ("severity_count_a", "A"),
                                       ("severity_count_b", "B"), ("severity_count_c", "C"))
                        severity = "O"
                        for field_key, kabco_code in count_codes:
                            value = integer(raw[fields[field_key]]) if field_key in fields else ""
                            if value != "" and int(value) > 0:
                                severity = kabco_code
                                break
                        severity_prov = "DERIVED_INJURY_COUNTS"
                    elif "injury_severity_raw_code" in fields:
                        sc = raw[fields["injury_severity_raw_code"]].strip(); sl = raw[fields["injury_severity_raw_label"]].strip()
                        if (not sc and not sl and version.get("injury_severity_fallback_to_severity", False)
                                and ("severity_raw_code" in fields or "severity_raw_label" in fields)):
                            sc = raw[fields["severity_raw_code"]].strip() if "severity_raw_code" in fields else ""
                            sl = raw[fields["severity_raw_label"]].strip() if "severity_raw_label" in fields else ""
                            mapped = crosswalk_value(crosswalk, "severity", sc, sl)
                            if mapped:
                                severity = mapped["canonical_code"]
                                severity_prov = "FALLBACK_TO_CRASH_SEVERITY"
                            else:
                                unknown.add(("severity", sc, sl)); severity = ""; severity_prov = "UNRESOLVED_CODE"
                        else:
                            mapped = crosswalk_value(crosswalk, "injury_severity", sc, sl)
                            if not mapped: unknown.add(("injury_severity", sc, sl)); severity = ""; severity_prov = "UNRESOLVED_CODE"
                            else: severity = mapped["canonical_code"]; severity_prov = mapped["mapping_status"]
                    elif "severity_raw_code" in fields or "severity_raw_label" in fields:
                        sc = raw[fields["severity_raw_code"]].strip(); sl = raw[fields["severity_raw_label"]].strip()
                        severity_map = crosswalk_value(crosswalk, "severity", sc, sl)
                        if severity_map:
                            severity = severity_map["canonical_code"]; severity_prov = severity_map["mapping_status"]
                        else:
                            severity = {"2": "K", "5": "O"}.get(sc, "U" if sc == "4" else "")
                            severity_prov = "CROSSWALK" if severity else "UNRESOLVED_CODE"
                        if not severity and not sc and not sl:
                            severity = "U"; severity_prov = "SOURCE_MISSING"
                        elif not severity: unknown.add(("severity", sc, sl))
                    else:
                        sc = sl = ""
                        severity = "U"
                        severity_prov = "UNAVAILABLE"

                    if severity_from_fatalities_when_unknown and severity in {"", "U"} and "fatalities" in fields:
                        fatality_value = integer(raw[fields["fatalities"]])
                        if fatality_value and int(fatality_value) > 0:
                            severity = "K"
                            severity_prov = "DERIVED_FATALITY_COUNT"
                    if severity_from_fatalities_always and "fatalities" in fields:
                        fatality_value = integer(raw[fields["fatalities"]])
                        if fatality_value and int(fatality_value) > 0 and severity != "K":
                            severity = "K"
                            severity_prov = "DERIVED_FATALITY_COUNT_OVERRIDES_SOURCE"

                    if "manner_raw_code" not in fields and "manner_raw_label" not in fields:
                        mc = ml = manner_code = ""; manner_prov = "UNAVAILABLE"
                        manner = None
                    else:
                        mc = raw[fields["manner_raw_code"]].strip() if "manner_raw_code" in fields else ""
                        ml = raw[fields["manner_raw_label"]].strip() if "manner_raw_label" in fields else ""
                        manner = crosswalk_value(crosswalk, "manner", mc, ml)
                    if manner:
                        manner_code = manner["canonical_code"]; manner_prov = manner["mapping_status"]
                        if manner_prov == "UNRESOLVED_CODE" and "manner_detail_raw_code" in fields:
                            dc = raw[fields["manner_detail_raw_code"]].strip()
                            dl = raw[fields["manner_detail_raw_label"]].strip()
                            detail = detail_crosswalk.get((mc, dc, dl.casefold()))
                            if detail:
                                manner_code = detail["canonical_code"]
                                manner_prov = detail["mapping_status"]
                        if manner_prov == "UNRESOLVED_CODE": unresolved_manner += 1
                    elif manner_prov != "UNAVAILABLE":
                        if not mc and not ml:
                            manner_code = ""; manner_prov = "SOURCE_MISSING"
                        else:
                            unknown.add(("manner", mc, ml)); manner_code = ""; manner_prov = "UNRESOLVED_CODE"

                    vehicle_exact, vehicle_minimum, vehicle_raw, vehicle_precision = vehicle_count(
                        raw[fields["vehicles"]] if "vehicles" in fields else "")

                    weather, weather_code, weather_label, weather_prov = mapped_category(
                        raw, fields, crosswalk, "weather", "weather", unknown)
                    light, light_code, light_label, light_prov = mapped_category(
                        raw, fields, crosswalk, "light", "light_condition", unknown)
                    road_surface, road_code, road_label, road_prov = mapped_category(
                        raw, fields, crosswalk, "road_surface", "road_surface_condition", unknown)
                    harmful, harmful_code, harmful_label, harmful_prov = mapped_category(
                        raw, fields, crosswalk, "first_harmful_event", "first_harmful_event", unknown)
                    harmful_group, _, _, _ = mapped_category(
                        raw, fields, crosswalk, "first_harmful_event", "first_harmful_event_group", unknown)

                    crash_uid = f"{state}:{year}:{crash_id}" if crash_id_scope == "YEAR" else f"{state}:{crash_id}"
                    injuries_value = integer(raw[fields["injuries"]]) if "injuries" in fields else ""
                    if version.get("injuries_from_severity_counts", False):
                        injury_parts = [integer(raw[fields[key]]) for key in
                                        ("severity_count_a", "severity_count_b", "severity_count_c")
                                        if key in fields]
                        injuries_value = str(sum(int(value) for value in injury_parts if value != ""))
                    out = {
                        "crash_uid": crash_uid, "state": state, "source_crash_id": crash_id,
                        "crash_date": crash_date, "crash_year": crash_year,
                        "crash_month": crash_month, "date_precision": date_precision,
                        "crash_time": crash_time,
                        "crash_datetime": f"{crash_date}T{crash_time}" if crash_date and crash_time else "", "time_precision": precision,
                        "latitude": latitude, "longitude": longitude, "coordinate_status": coordinate_status,
                        "county": raw[fields["county"]].strip() if "county" in fields else "",
                        "city": raw[fields["city"]].strip() if "city" in fields else "",
                        "severity_kabco": severity, "severity_raw_code": sc, "severity_raw_label": sl,
                        "severity_provenance": severity_prov,
                        "fatalities": integer(raw[fields["fatalities"]]) if "fatalities" in fields else "",
                        "injuries": injuries_value,
                        "vehicles": vehicle_exact, "vehicles_minimum": vehicle_minimum,
                        "vehicles_raw": vehicle_raw, "vehicles_precision": vehicle_precision,
                        "manner_of_collision_mmucc": manner_code, "manner_raw_code": mc, "manner_raw_label": ml,
                        "manner_provenance": manner_prov, "source_schema_id": version["schema_id"],
                        "weather": weather, "weather_raw_code": weather_code,
                        "weather_raw_label": weather_label, "weather_provenance": weather_prov,
                        "light_condition": light, "light_raw_code": light_code,
                        "light_raw_label": light_label, "light_provenance": light_prov,
                        "road_surface_condition": road_surface, "road_surface_raw_code": road_code,
                        "road_surface_raw_label": road_label, "road_surface_provenance": road_prov,
                        "first_harmful_event": harmful, "first_harmful_event_raw_code": harmful_code,
                        "first_harmful_event_raw_label": harmful_label,
                        "first_harmful_event_provenance": harmful_prov,
                        "first_harmful_event_group": harmful_group,
                        "collision_partner_group": harmful_group if harmful_group in {
                            "MOTOR_VEHICLE_IN_TRANSPORT", "PEDESTRIAN", "PEDALCYCLIST", "ANIMAL",
                            "PARKED_VEHICLE", "FIXED_OBJECT", "TRAIN", "OTHER_NON_FIXED_OBJECT"} else "",
                        "source_file": str(source.relative_to(STATES)).replace("\\", "/"),
                        "source_row_number": row_number, "pipeline_version": VERSION,
                    }
                    for target in ("intersection_related", "work_zone_related", "alcohol_involved",
                                   "drug_involved", "speeding_involved", "hit_and_run",
                                   "school_bus_related", "pedestrian_involved", "bicyclist_involved",
                                   "motorcycle_involved", "commercial_vehicle_involved"):
                        if target in fields:
                            out[target] = normalized_flag(raw[fields[target]])
                    for target in ("pedestrian_count", "bicyclist_count", "motorcycle_count",
                                   "commercial_vehicle_count"):
                        if target in fields:
                            out[target] = integer(raw[fields[target]])
                            involved = target.replace("_count", "_involved")
                            if out[target] != "": out[involved] = "TRUE" if int(out[target]) > 0 else "FALSE"
                    for target in ("posted_speed_limit", "number_of_lanes"):
                        if target in fields:
                            out[target] = strict_integer(raw[fields[target]])
                    # These values are retained verbatim for future reviewed crosswalks.
                    # They are source categories, not claims that state labels already
                    # conform to the canonical MMUCC/FHWA domains.
                    for target in ("relation_to_trafficway", "urban_rural",
                                   "work_zone_type", "intersection_type"):
                        if target in fields:
                            out[target] = raw[fields[target]].strip()
                    if "functional_class" in fields:
                        functional_raw = raw[fields["functional_class"]].strip()
                        out["functional_class"] = functional_raw
                        out["functional_class_raw_code"] = functional_raw
                        out["functional_class_raw_label"] = functional_raw
                        out["functional_class_provenance"] = (
                            "SOURCE_RAW_UNSTANDARDIZED" if functional_raw else "SOURCE_MISSING")
                    if "speeding_involved" in fields:
                        out["speeding_provenance"] = "REPORTED"
                    elif not out.get("speeding_provenance"):
                        out["speeding_provenance"] = "UNAVAILABLE"
                    writer.writerow(out)
            if unknown:
                partial.unlink(missing_ok=True)
                raise RuntimeError(f"{state} {year}: unmapped source codes: {sorted(unknown)[:20]}")
            partial.replace(output)
            summaries.append({
                "state": state, "year": year, "schema_id": version["schema_id"], "source_file": str(source),
                "source_sha256": sha256(source), "output_file": str(output), "output_sha256": sha256(output),
                "source_rows": source_rows, "output_rows": output_rows,
                "duplicate_source_rows": duplicate_source_rows, "excluded_source_rows": excluded_source_rows,
                "invalid_coordinates": invalid_coords,
                "unresolved_manner_rows": unresolved_manner, "result": "PASS",
            })
            print(f"{state} {year}: {source_rows} source rows, {output_rows} crashes -> {output.name}", flush=True)

    summary_path = qa_dir / "harmonization_summary.csv"
    with summary_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summaries[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(summaries)
    manifest = {
        "pipeline_version": VERSION, "state": state, "executed_utc": datetime.now(timezone.utc).isoformat(),
        "config_revision": config.get("revision", {}).get("id"),
        "config_sha256": sha256(config_path), "crosswalk_sha256": sha256(crosswalk_path),
        "detail_crosswalk_sha256": sha256(detail_crosswalk_path) if detail_crosswalk_path.exists() else None,
        "schema_sha256": sha256(schema_path), "years": len(summaries), "result": "PASS",
    }
    (qa_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import sys
        if "--state" in sys.argv:
            failed_state = sys.argv[sys.argv.index("--state") + 1].upper()
            failed_dir = PIPE / "data" / "crash" / failed_state
            if failed_dir.exists():
                for partial_file in failed_dir.glob("*.partial"):
                    partial_file.unlink(missing_ok=True)
        raise
