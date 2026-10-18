import csv
import json
import os
import time
from pathlib import Path

import requests

URL = "https://services9.arcgis.com/eNX73FDxjlKFtCtH/ArcGIS/rest/services/NDOT_FY2024_Crashes_2019_2023/FeatureServer/3"
ROOT = Path(r"F:\LH_Research\USCrash\Crash\States\NV")
YEARS = range(2023, 2018, -1)
session = requests.Session()


def get(params):
    for attempt in range(7):
        try:
            response = session.post(URL + "/query", data=params, timeout=300)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            return data
        except Exception:
            if attempt == 6:
                raise
            time.sleep(2 ** attempt)


ROOT.mkdir(parents=True, exist_ok=True)
metadata = session.get(URL, params={"f": "json"}, timeout=120).json()
(ROOT / "arcgis_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
field_names = [field["name"] for field in metadata["fields"]]
output_fields = field_names + ["longitude", "latitude"]

for year in YEARS:
    directory = ROOT / str(year)
    directory.mkdir(parents=True, exist_ok=True)
    final = directory / f"NV_crashes_{year}.csv"
    if final.exists():
        continue
    ids = get({"f": "json", "where": f"Crash_Year={year}", "returnIdsOnly": "true"}).get("objectIds", [])
    partial = final.with_suffix(".csv.partial")
    with partial.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields, extrasaction="ignore")
        writer.writeheader()
        completed = 0
        for start in range(0, len(ids), 1000):
            batch = ids[start:start + 1000]
            data = get({
                "f": "json", "objectIds": ",".join(map(str, batch)), "outFields": "*",
                "returnGeometry": "true", "outSR": "4326",
            })
            for feature in data.get("features", []):
                row = feature.get("attributes", {})
                geometry = feature.get("geometry") or {}
                row["longitude"] = geometry.get("x")
                row["latitude"] = geometry.get("y")
                writer.writerow(row)
            completed += len(data.get("features", []))
            handle.flush()
            print(year, completed, "/", len(ids), flush=True)
    os.replace(partial, final)
    print(year, "COMPLETE", len(ids), flush=True)
