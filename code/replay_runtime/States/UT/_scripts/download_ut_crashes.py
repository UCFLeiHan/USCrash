import os as _uscrash_paths_os
import csv
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = (Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/UT')
MAP = "https://central.udot.utah.gov/central/rest/services/TrafficAndSafety/Crash_Locations/MapServer/10"
FEATURE = "https://services.arcgis.com/pA2nEVnB6tquxgOW/ArcGIS/rest/services/Utah_Crash_Locations/FeatureServer"
FEATURE_LAYERS = {2019: 7, 2020: 6, 2021: 5, 2022: 4, 2023: 3, 2024: 2, 2025: 1, 2026: 0}


def request_json(url, params=None, retries=6):
    data = urllib.parse.urlencode(params).encode() if params else None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, data=data, timeout=180) as response:
                result = json.load(response)
            if "error" in result:
                raise RuntimeError(result["error"])
            return result
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def iso_date(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, str) and value:
        return value
    return ""


def main():
    meta_dir = ROOT / "Metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for year in range(2018, 2027):
        layer = MAP if year == 2018 else f"{FEATURE}/{FEATURE_LAYERS[year]}"
        metadata = request_json(layer + "?f=pjson")
        (meta_dir / f"layer_{year}.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        fields = [f["name"] for f in metadata["fields"]]
        oid = metadata.get("objectIdField") or next(f["name"] for f in metadata["fields"] if f["type"] == "esriFieldTypeOID")
        page_size = min(int(metadata.get("maxRecordCount", 2000)), 2000)
        out_dir = ROOT / str(year) / "CSV"
        out_dir.mkdir(parents=True, exist_ok=True)
        output = out_dir / f"UDOT_Crashes_{year}.csv"
        offset = count = coords = 0
        min_date = max_date = None
        with output.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields + ["Longitude", "Latitude", "CrashDateTime_ISO"])
            writer.writeheader()
            while True:
                result = request_json(layer + "/query", {
                    "f": "json", "where": "1=1", "outFields": "*",
                    "returnGeometry": "true", "outSR": "4326",
                    "orderByFields": oid, "resultOffset": offset,
                    "resultRecordCount": page_size,
                })
                features = result.get("features", [])
                for feature in features:
                    row = feature["attributes"]
                    geom = feature.get("geometry") or {}
                    row["Longitude"] = geom.get("x")
                    row["Latitude"] = geom.get("y")
                    coords += bool(geom.get("x") is not None and geom.get("y") is not None)
                    raw_date = row.get("crash_datetime") if "crash_datetime" in row else row.get("CRASH_DATETIME")
                    date_iso = iso_date(raw_date)
                    row["CrashDateTime_ISO"] = date_iso
                    if date_iso:
                        min_date = date_iso if min_date is None or date_iso < min_date else min_date
                        max_date = date_iso if max_date is None or date_iso > max_date else max_date
                    writer.writerow(row)
                count += len(features)
                if len(features) < page_size:
                    break
                offset += len(features)
                if offset % 20000 == 0:
                    print(f"{year}: {offset:,}", flush=True)
        manifest.append({"year": year, "rows": count, "coordinates": coords, "min_datetime": min_date, "max_datetime": max_date, "source": layer, "file": str(output), "status": "partial_current_year" if year == 2026 else "complete_year"})
        print(f"Completed {year}: {count:,}", flush=True)
    with (meta_dir / "ut_download_manifest.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=manifest[0].keys()); writer.writeheader(); writer.writerows(manifest)


if __name__ == "__main__":
    main()
