import os as _uscrash_paths_os
import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = (Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/TN')
LAYER = "https://services2.arcgis.com/nf3p7v7Zy4fTOh6M/ArcGIS/rest/services/Tennessee_Crashes_JAN_2021_JAN_2025/FeatureServer/0"


def post(params, retries=5):
    data = urllib.parse.urlencode(params).encode()
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(LAYER + "/query", data=data, timeout=120) as r:
                result = json.load(r)
            if "error" in result:
                raise RuntimeError(result["error"])
            return result
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def main():
    meta_dir = ROOT / "Metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(LAYER + "?f=pjson", timeout=120) as r:
        metadata = json.load(r)
    (meta_dir / "arcgis_layer_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = [f["name"] for f in metadata["fields"]]
    page_size = int(metadata.get("maxRecordCount", 2000))
    manifest = []
    for year in range(2021, 2026):
        year_dir = ROOT / str(year)
        csv_dir = year_dir / "CSV"
        csv_dir.mkdir(parents=True, exist_ok=True)
        output = csv_dir / f"TN_Crashes_{year}.csv"
        offset = 0
        count = 0
        with output.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields + ["Longitude", "Latitude"])
            writer.writeheader()
            while True:
                result = post({
                    "f": "json",
                    "where": f"YEAROFCRAS='{year}'",
                    "outFields": "*",
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "orderByFields": "OBJECTID",
                    "resultOffset": offset,
                    "resultRecordCount": page_size,
                })
                features = result.get("features", [])
                for feature in features:
                    row = feature["attributes"]
                    geometry = feature.get("geometry") or {}
                    row["Longitude"] = geometry.get("x")
                    row["Latitude"] = geometry.get("y")
                    writer.writerow(row)
                count += len(features)
                if len(features) < page_size:
                    break
                offset += len(features)
                if offset % 20000 == 0:
                    print(f"{year}: {offset:,}", flush=True)
        manifest.append({"year": year, "rows": count, "file": str(output), "status": "partial_January" if year == 2025 else "complete_year"})
        print(f"Completed {year}: {count:,}", flush=True)
    with (meta_dir / "tn_download_manifest.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "rows", "file", "status"])
        writer.writeheader()
        writer.writerows(manifest)


if __name__ == "__main__":
    main()
