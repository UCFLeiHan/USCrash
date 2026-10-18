import csv
import html
import json
import os
import time
from pathlib import Path

import requests


ROOT = Path(r"F:\LH_Research\USCrash\Crash")
STATE = ROOT / "States" / "AL"
HIST_URL = "https://safety.aladata.com/DataSource/GetCategoryDetails"
ARCGIS_QUERY = "https://care-esriext.aladata.com/arcgis/rest/services/eCrash/Green/MapServer/0/query"

HIST_VARS = [
    "Year", "Month", "Day of Month", "Day of the Week", "Time of Day",
    "City", "County", "Crash Severity", "Primary Contributing Circumstance",
    "First Harmful Event", "E Manner of Crash", "Number Injured (Includes Fatalities)",
    "Number Injured (Non-Fatal)", "Number Killed", "Number of Suspected Minor Injuries",
    "Number of Suspected Serious Injuries", "Number of Vehicles", "Number of Persons Recorded",
    "Number of Pedestrians", "Number of Pedacyclists", "Weather", "Lighting Conditions",
    "Rural or Urban", "Locale", "Intersection Related", "At Intersection",
    "Functional Class", "Highway Classifications", "Mileposted Route", "Has Coordinate",
    "E CU Road Surface Type", "CU Roadway Condition", "CU Roadway Curvature and Grade",
    "CU Speed Limit", "CU Traffic Control", "CU Trafficway Lanes", "CU Workzone Related",
    "School Bus Related", "CMV Involved", "E Distracted Driving Opinion", "Record ID",
]

CURRENT_FIELDS = [
    "OBJECTID", "CrashNum", "RecordID", "DateTime", "Year", "Month", "Day", "DayofWeek",
    "Week", "Time", "Latitude", "Longitude", "City", "County", "CrashSev", "mapSeverity",
    "PriCause", "FrstHmEv", "MostHmEv", "ManrCrs", "NumKilledN", "NumNonFatN", "NumInjFatN",
    "NumMajInj", "NumMinInj", "NumVeh", "NumPer", "NumPed", "NumByc", "Weather", "Lighting",
    "RuralUrban", "Locale", "IntRel", "AtInt", "HwyClass", "FXClass", "Route", "Milepoint",
    "StreetName", "CrossStreet1", "CrossStreet2", "RouteId", "AADT", "CURdType", "CURdCond",
    "CUCurveGrad", "CUSpeedLim", "CUTrafCtl", "CUNumLanes", "CUWrkZone", "SchoolBus", "CMVInv",
    "DistrDrv", "AgencyORI", "HasCoord", "DataSrc",
]


def request_with_retry(session, method, url, **kwargs):
    last = None
    for attempt in range(6):
        try:
            response = session.request(method, url, timeout=120, **kwargs)
            response.raise_for_status()
            return response
        except Exception as exc:
            last = exc
            time.sleep(min(2 ** attempt, 20))
    raise last


def decode_column(text):
    values = text.split(",")
    if values and values[-1] == "":
        values.pop()
    return [html.unescape(v) for v in values]


def download_historical(session, year):
    out_dir = STATE / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / f"alabama_care_historical_{year}.csv"
    partial = final.with_suffix(".csv.partial")
    requested = ",".join(["Crash Number"] + HIST_VARS + ["key.dat"])
    headers = ["Crash Number"] + HIST_VARS + ["key.dat"]
    # Wide CARE exports become unstable above this size even though narrow
    # queries accept much larger pages.
    page_size = 5000
    total = None
    written = 0
    with partial.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        page = 0
        while total is None or written < total:
            payload = {
                "dataSourceID": "eCrash1420",
                "startDate": f"1/1/{year}",
                "endDate": f"12/31/{year}",
                "selectedCategoriesString": "",
                "variableNames": requested,
                "recordsPerPage": page_size,
                "pageIndex": page,
                "sortVariable": "Crash Number",
                "sortAscending": True,
                "returnTotalNumberOfRecordsFound": True,
                "includePdfLink": "False",
            }
            response = request_with_retry(session, "POST", HIST_URL, json=payload)
            parts = response.text.split("|")
            total = int(parts[0])
            columns = [decode_column(x) for x in parts[1:] if x != ""]
            if len(columns) != len(headers):
                raise RuntimeError(f"{year}: expected {len(headers)} columns, received {len(columns)}")
            sizes = {len(x) for x in columns}
            if len(sizes) != 1:
                raise RuntimeError(f"{year}: unequal column sizes: {sorted(sizes)}")
            rows = list(zip(*columns))
            writer.writerows(rows)
            written += len(rows)
            print(f"historical {year}: {written:,}/{total:,}", flush=True)
            if not rows:
                break
            page += 1
    if written != total:
        raise RuntimeError(f"{year}: wrote {written}, expected {total}")
    os.replace(partial, final)
    return {"source": "CARE historical", "year": year, "rows": written, "file": str(final)}


def epoch_to_iso(value):
    if value in (None, ""):
        return ""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


def download_current(session, year):
    out_dir = STATE / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / f"alabama_arcgis_current_{year}.csv"
    partial = final.with_suffix(".csv.partial")
    page_size = 5000
    offset = 0
    written = 0
    coord_count = 0
    headers = CURRENT_FIELDS + ["geometry_x", "geometry_y"]
    with partial.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        while True:
            payload = {
                "f": "json", "where": f"Year='{year}'", "outFields": ",".join(CURRENT_FIELDS),
                "returnGeometry": "true", "outSR": "4326", "orderByFields": "OBJECTID",
                "resultOffset": offset, "resultRecordCount": page_size,
            }
            data = request_with_retry(session, "POST", ARCGIS_QUERY, data=payload).json()
            if "error" in data:
                raise RuntimeError(f"ArcGIS {year}: {data['error']}")
            features = data.get("features", [])
            for feature in features:
                row = feature.get("attributes", {})
                row["DateTime"] = epoch_to_iso(row.get("DateTime"))
                geom = feature.get("geometry") or {}
                row["geometry_x"] = geom.get("x", "")
                row["geometry_y"] = geom.get("y", "")
                if row.get("Latitude") is not None and row.get("Longitude") is not None:
                    coord_count += 1
                writer.writerow(row)
            written += len(features)
            print(f"current {year}: {written:,}", flush=True)
            if len(features) < page_size:
                break
            offset += len(features)
    os.replace(partial, final)
    return {
        "source": "ArcGIS current", "year": year, "rows": written,
        "coordinate_rows": coord_count, "file": str(final),
    }


def main():
    STATE.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 research data downloader"})
    request_with_retry(session, "GET", "https://safety.aladata.com/")
    request_with_retry(session, "GET", "https://safety.aladata.com/DataSource/Index/eCrash1420")
    results = []
    for year in range(2014, 2021):
        results.append(download_historical(session, year))
    for year in range(2020, 2026):
        results.append(download_current(session, year))
    metadata = {
        "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "official_portal": "https://safety.aladata.com/",
        "historical_dataset": "2014-2020 Alabama Integrated Crash Data",
        "current_arcgis_layer": ARCGIS_QUERY.rsplit("/query", 1)[0],
        "notes": [
            "Historical public CARE export does not expose numeric latitude/longitude columns; Has Coordinate records coordinate availability.",
            "Current ArcGIS files include latitude, longitude, geometry, crash severity, time, crash characteristics, AADT and roadway fields.",
            "2020 is retained from both sources for schema/coverage comparison.",
            "2025 is partial through 2025-03-31 at download time.",
        ],
        "files": results,
    }
    meta_file = STATE / "metadata.json"
    meta_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
