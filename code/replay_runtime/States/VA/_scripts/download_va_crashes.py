import os as _uscrash_paths_os
import csv
import json
import time
import urllib.parse
import urllib.request
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

ROOT = (Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/VA')
LAYER = "https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/Full_Crash/FeatureServer/0"


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


def date_iso(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return value or ""


def main():
    meta = ROOT / "Metadata"
    meta.mkdir(parents=True, exist_ok=True)
    metadata = request_json(LAYER + "?f=pjson")
    (meta / "Full_Crash_layer_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = [f["name"] for f in metadata["fields"]]
    oid = metadata["objectIdField"]
    page_size = min(int(metadata.get("maxRecordCount", 16000)), 16000)
    counts = {}
    minmax = {}
    with ExitStack() as stack:
        writers = {}
        offset = 0
        while True:
            result = request_json(LAYER + "/query", {
                "f": "json", "where": "1=1", "outFields": "*",
                "returnGeometry": "true", "outSR": "4326",
                "orderByFields": oid, "resultOffset": offset,
                "resultRecordCount": page_size,
            })
            features = result.get("features", [])
            for feature in features:
                row = feature["attributes"]
                year_value = row.get("CRASH_YEAR")
                year = str(int(year_value)) if isinstance(year_value, (int, float)) else str(year_value or "UnknownYear")
                if year not in writers:
                    out_dir = ROOT / year / "CSV"
                    out_dir.mkdir(parents=True, exist_ok=True)
                    f = stack.enter_context((out_dir / f"VDOT_Crashes_{year}.csv").open("w", encoding="utf-8-sig", newline=""))
                    writers[year] = csv.DictWriter(f, fieldnames=fields + ["Longitude_WGS84", "Latitude_WGS84", "CrashDateTime_ISO"])
                    writers[year].writeheader(); counts[year] = 0
                geometry = feature.get("geometry") or {}
                row["Longitude_WGS84"] = geometry.get("x")
                row["Latitude_WGS84"] = geometry.get("y")
                iso = date_iso(row.get("CRASH_DT"))
                row["CrashDateTime_ISO"] = iso
                writers[year].writerow(row); counts[year] += 1
                if iso:
                    mm = minmax.setdefault(year, [iso, iso]); mm[0] = min(mm[0], iso); mm[1] = max(mm[1], iso)
            if len(features) < page_size:
                break
            offset += len(features)
            if offset % 64000 == 0:
                print(f"Downloaded {offset:,}", flush=True)
    rows = [{"year": y, "rows": counts[y], "min_datetime": minmax.get(y, ["", ""])[0], "max_datetime": minmax.get(y, ["", ""])[1], "status": "partial_current_year" if y == "2026" else "complete_year", "file": str(ROOT / y / "CSV" / f"VDOT_Crashes_{y}.csv")} for y in sorted(counts)]
    with (meta / "va_download_manifest.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    print(f"Completed {sum(counts.values()):,} records", flush=True)


if __name__ == "__main__":
    main()
