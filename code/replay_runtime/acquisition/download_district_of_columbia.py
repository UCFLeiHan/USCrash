"""Download DDOT/MPD public crash points + details from Open Data DC / ArcGIS.

Sources:
  Crashes in DC (points):
    https://opendata.dc.gov/datasets/DCGIS::crashes-in-dc
    https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Public_Safety_WebMercator/MapServer/24
  Crash Details Table (participants, linked by CRIMEID/CRASHID):
    https://opendata.dc.gov/datasets/DCGIS::crash-details-table
    MapServer/25
"""
from __future__ import annotations
import os as _uscrash_paths_os

import csv
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = (Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/DC')
RAW = ROOT / "Raw"
SOURCE = ROOT / "_source"
ROOT.mkdir(parents=True, exist_ok=True)
RAW.mkdir(parents=True, exist_ok=True)
SOURCE.mkdir(parents=True, exist_ok=True)

CRASH_LAYER = (
    "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/"
    "Public_Safety_WebMercator/MapServer/24"
)
DETAILS_LAYER = (
    "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/"
    "Public_Safety_WebMercator/MapServer/25"
)
HUB_CRASH_CSV = (
    "https://opendata.dc.gov/api/download/v1/items/"
    "70392a096a8e431381f1f692aaa06afd/csv?layers=24"
)
HUB_DETAILS_CSV = (
    "https://opendata.dc.gov/api/download/v1/items/"
    "70248b73c20f46b0a5ee895fc91d6222/csv?layers=25"
)

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (compatible; academic-crash-research/1.0; "
            "+https://opendata.dc.gov/)"
        )
    }
)

# Prefer crash occurrence date; fall back to report date when splitting years.
YEAR_MIN = 2010
YEAR_MAX = 2026


def api(url: str, params: dict, *, post: bool = False, retries: int = 5) -> dict:
    last = None
    for attempt in range(retries):
        try:
            if post:
                resp = SESSION.post(url, data=params, timeout=180)
            else:
                resp = SESSION.get(url, params=params, timeout=180)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and data.get("error"):
                raise RuntimeError(data["error"])
            return data
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"API failed {url}: {last}")


def ms_to_iso(value) -> str:
    if value in (None, ""):
        return ""
    try:
        ms = int(float(value))
    except (TypeError, ValueError):
        return str(value)
    # ArcGIS sometimes returns already-string dates in Hub CSV
    if ms < 10_000_000_000:  # seconds
        ms *= 1000
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def year_from_ms(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        ms = int(float(value))
    except (TypeError, ValueError):
        # try parse ISO / MM/DD/YYYY
        s = str(value)
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(s[:19], fmt).year
            except ValueError:
                continue
        if len(s) >= 4 and s[:4].isdigit():
            y = int(s[:4])
            return y if 1900 <= y <= 2100 else None
        return None
    if ms < 10_000_000_000:
        ms *= 1000
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).year
    except (OSError, OverflowError, ValueError):
        return None


def severity_label(row: dict) -> str:
    def n(key: str) -> int:
        try:
            return int(float(row.get(key) or 0))
        except (TypeError, ValueError):
            return 0

    fatal = (
        n("FATAL_BICYCLIST")
        + n("FATAL_DRIVER")
        + n("FATAL_PEDESTRIAN")
        + n("FATALPASSENGER")
        + n("FATALOTHER")
    )
    major = (
        n("MAJORINJURIES_BICYCLIST")
        + n("MAJORINJURIES_DRIVER")
        + n("MAJORINJURIES_PEDESTRIAN")
        + n("MAJORINJURIESPASSENGER")
        + n("MAJORINJURIESOTHER")
    )
    minor = (
        n("MINORINJURIES_BICYCLIST")
        + n("MINORINJURIES_DRIVER")
        + n("MINORINJURIES_PEDESTRIAN")
        + n("MINORINJURIESPASSENGER")
        + n("MINORINJURIESOTHER")
    )
    unknown = (
        n("UNKNOWNINJURIES_BICYCLIST")
        + n("UNKNOWNINJURIES_DRIVER")
        + n("UNKNOWNINJURIES_PEDESTRIAN")
        + n("UNKNOWNINJURIESPASSENGER")
        + n("UNKNOWNINJURIESOTHER")
    )
    if fatal > 0:
        return "Fatal"
    if major > 0:
        return "Major"
    if minor > 0:
        return "Minor"
    if unknown > 0:
        return "UnknownInjury"
    return "PDO"


def download_hub_csv(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"exists {dest.name} ({dest.stat().st_size:,} bytes)", flush=True)
        return dest
    partial = dest.with_suffix(dest.suffix + ".partial")
    print(f"GET hub CSV -> {dest.name}", flush=True)
    with SESSION.get(url, stream=True, timeout=600) as resp:
        resp.raise_for_status()
        with partial.open("wb") as out:
            for chunk in resp.iter_content(1024 * 1024):
                if chunk:
                    out.write(chunk)
    if partial.stat().st_size < 100_000:
        raise RuntimeError(f"Hub CSV too small: {partial.stat().st_size}")
    partial.replace(dest)
    print(f"  saved {dest.stat().st_size:,} bytes", flush=True)
    return dest


def download_layer_paginated(layer: str, dest: Path, page_size: int = 1000) -> Path:
    """Fallback ArcGIS pagination if Hub CSV fails."""
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"exists {dest.name}", flush=True)
        return dest
    query = f"{layer}/query"
    count = api(query, {"where": "1=1", "returnCountOnly": "true", "f": "json"}).get(
        "count", 0
    )
    print(f"ArcGIS download {layer.split('/')[-1]} expected={count:,}", flush=True)
    # freeze IDs
    ids_payload = api(query, {"where": "1=1", "returnIdsOnly": "true", "f": "json"}, post=True)
    object_ids = sorted(set(ids_payload.get("objectIds") or []))
    if not object_ids:
        raise RuntimeError("no objectIds")
    fields_info = api(layer, {"f": "json"})
    fieldnames = [f["name"] for f in fields_info.get("fields", []) if f["name"] != "SHAPE"]
    fieldnames += ["__geometry_longitude_wgs84", "__geometry_latitude_wgs84"]
    partial = dest.with_suffix(dest.suffix + ".partial")
    written = 0
    with partial.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for offset in range(0, len(object_ids), page_size):
            part = object_ids[offset : offset + page_size]
            data = api(
                query,
                {
                    "objectIds": ",".join(map(str, part)),
                    "outFields": "*",
                    "returnGeometry": "true",
                    "outSR": 4326,
                    "f": "json",
                },
                post=True,
            )
            for feat in data.get("features", []):
                row = dict(feat.get("attributes") or {})
                geo = feat.get("geometry") or {}
                row["__geometry_longitude_wgs84"] = geo.get("x", "")
                row["__geometry_latitude_wgs84"] = geo.get("y", "")
                writer.writerow(row)
                written += 1
            if written % 10000 == 0 or offset + page_size >= len(object_ids):
                print(f"  {written:,}/{len(object_ids):,}", flush=True)
    if written != len(object_ids):
        raise RuntimeError(f"wrote {written} expected {len(object_ids)}")
    partial.replace(dest)
    return dest


def split_crashes_by_year(all_csv: Path) -> dict:
    writers: dict[int, csv.DictWriter] = {}
    handles: dict[int, object] = {}
    counts: Counter[int] = Counter()
    lat_hits: Counter[int] = Counter()
    out_files: dict[int, Path] = {}
    header: list[str] | None = None

    def get_writer(year: int, fieldnames: list[str]) -> csv.DictWriter:
        if year not in writers:
            ydir = ROOT / str(year)
            ydir.mkdir(parents=True, exist_ok=True)
            path = ydir / f"DC_crashes_{year}.csv"
            out_files[year] = path
            h = path.open("w", encoding="utf-8-sig", newline="")
            handles[year] = h
            # enrich with derived fields
            extras = ["CrashDateTime_ISO", "ReportDateTime_ISO", "SeverityDerived"]
            w = csv.DictWriter(h, fieldnames=fieldnames + extras, extrasaction="ignore")
            w.writeheader()
            writers[year] = w
        return writers[year]

    with all_csv.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        for row in reader:
            y = year_from_ms(row.get("FROMDATE")) or year_from_ms(row.get("REPORTDATE"))
            if y is None or y < YEAR_MIN or y > YEAR_MAX:
                continue
            row = dict(row)
            row["CrashDateTime_ISO"] = ms_to_iso(row.get("FROMDATE")) or ms_to_iso(
                row.get("REPORTDATE")
            )
            row["ReportDateTime_ISO"] = ms_to_iso(row.get("REPORTDATE"))
            row["SeverityDerived"] = severity_label(row)
            get_writer(y, header).writerow(row)
            counts[y] += 1
            lat = row.get("LATITUDE") or row.get("MPDLATITUDE")
            lon = row.get("LONGITUDE") or row.get("MPDLONGITUDE")
            if lat not in (None, "", "0", "0.0") and lon not in (None, "", "0", "0.0"):
                lat_hits[y] += 1

    for h in handles.values():
        h.close()

    qa = {
        "years": {
            str(y): {
                "rows": counts[y],
                "latlon_nonempty": lat_hits[y],
                "file": str(out_files[y].relative_to(ROOT)),
            }
            for y in sorted(counts)
        },
        "total_rows_kept": int(sum(counts.values())),
        "fields": header,
        "has_time": True,
        "has_coords": True,
        "has_severity": True,
        "has_crash_manner": False,
        "notes": (
            "FROMDATE used as crash datetime when present (else REPORTDATE). "
            "SeverityDerived from injury/fatality count fields. "
            "Public crash-points layer has no classic manner-of-collision field; "
            "participant vehicle types are in Crash Details Table."
        ),
    }
    return qa


def main() -> None:
    # Prefer Hub bulk CSV (fast); fall back to ArcGIS objectId paging.
    crash_all = RAW / "DC_crashes_all_hub.csv"
    details_all = RAW / "DC_crash_details_all_hub.csv"
    try:
        download_hub_csv(HUB_CRASH_CSV, crash_all)
    except Exception as exc:  # noqa: BLE001
        print("Hub crash CSV failed, ArcGIS fallback:", exc, flush=True)
        crash_all = RAW / "DC_crashes_all_arcgis.csv"
        download_layer_paginated(CRASH_LAYER, crash_all)

    try:
        download_hub_csv(HUB_DETAILS_CSV, details_all)
    except Exception as exc:  # noqa: BLE001
        print("Hub details CSV failed, ArcGIS fallback:", exc, flush=True)
        details_all = RAW / "DC_crash_details_all_arcgis.csv"
        download_layer_paginated(DETAILS_LAYER, details_all)

    print("Splitting crashes by year...", flush=True)
    qa = split_crashes_by_year(crash_all)

    # Keep a copy of details under _source (not year-split; join key CRIMEID)
    details_copy = SOURCE / details_all.name
    if details_all.exists() and (
        not details_copy.exists() or details_copy.stat().st_size != details_all.stat().st_size
    ):
        details_copy.write_bytes(details_all.read_bytes())

    meta = {
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "crashes_layer": CRASH_LAYER,
            "details_layer": DETAILS_LAYER,
            "hub_crashes_csv": HUB_CRASH_CSV,
            "hub_details_csv": HUB_DETAILS_CSV,
            "portal": "https://opendata.dc.gov/datasets/DCGIS::crashes-in-dc",
        },
        "raw_crashes": str(crash_all),
        "raw_details": str(details_all),
        "qa": qa,
    }
    (SOURCE / "download_metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    status = f"""# District of Columbia crash data status

## Verdict
**YES — public Open Data DC / DDOT crash points are downloadable.**

## Source
- Portal: https://opendata.dc.gov/datasets/DCGIS::crashes-in-dc
- ArcGIS: `{CRASH_LAYER}`
- Companion details: https://opendata.dc.gov/datasets/DCGIS::crash-details-table

## Local coverage
Years kept ({YEAR_MIN}–{YEAR_MAX}): {", ".join(sorted(qa["years"]))}
Total rows: {qa["total_rows_kept"]:,}

| Year | Rows | Lat/lon nonempty |
|------|------|------------------|
""" + "\n".join(
        f"| {y} | {info['rows']:,} | {info['latlon_nonempty']:,} |"
        for y, info in sorted(qa["years"].items())
    ) + f"""

## Fields
- Time: `FROMDATE` / `REPORTDATE` (+ derived `CrashDateTime_ISO`)
- Coordinates: `LATITUDE` / `LONGITUDE` (also MPD* variants)
- Severity: injury/fatality count fields + derived `SeverityDerived`
- Crash manner/type: **not in points layer** (public summary has mode counts / speeding; participant vehicle types in details table)

## Files
- Annual: `States/DC/{{year}}/DC_crashes_{{year}}.csv`
- Raw: `States/DC/Raw/`
- Details: `{details_all.name}`
- Script: `acquisition/download_district_of_columbia.py`
"""
    (ROOT / "DOWNLOAD_STATUS.md").write_text(status, encoding="utf-8")
    print("DONE years", len(qa["years"]), "rows", qa["total_rows_kept"], flush=True)
    for y, info in sorted(qa["years"].items()):
        print(f"  {y}: {info['rows']:,}", flush=True)


if __name__ == "__main__":
    main()
