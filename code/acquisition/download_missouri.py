import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://www.mshp.dps.missouri.gov/arcgis/rest/services/STARS_CRASHES/MapServer/0/query"
ROOT = Path(r"F:\LH_Research\USCrash\Crash\States\MO")
YEARS = range(2002, 2027)
CHUNK = 5000


def get_json(params, attempts=6):
    data = urlencode(params).encode("utf-8")
    for attempt in range(attempts):
        try:
            req = Request(BASE, data=data, headers={"User-Agent": "USCrash research downloader/1.0"})
            with urlopen(req, timeout=180) as response:
                result = json.load(response)
            if "error" in result:
                raise RuntimeError(result["error"])
            return result
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(min(60, 2 ** attempt))


def iso_date(value):
    if value in (None, ""):
        return ""
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def download_year(year):
    year_dir = ROOT / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    final = year_dir / f"MO_crashes_{year}.csv"
    partial = year_dir / f"MO_crashes_{year}.csv.partial"
    if final.exists() and final.stat().st_size > 100:
        print(f"{year}: already complete", flush=True)
        return

    where = f"ACC_DATE >= DATE '{year}-01-01' AND ACC_DATE < DATE '{year + 1}-01-01'"
    count_result = get_json({"f": "json", "where": where, "returnCountOnly": "true"})
    if "count" not in count_result:
        raise RuntimeError(f"{year}: missing official count response")
    expected = int(count_result["count"])
    if expected == 0:
        # An empty public-layer query is a coverage gap, not a completed dataset.
        # Preserve any existing historical empty placeholder without promoting it.
        (year_dir / "acquisition_status.json").write_text(json.dumps({
            "year": year, "status": "NO_RECORDS_RETURNED_BY_PUBLIC_LAYER",
            "official_query_count": 0, "source": BASE, "where": where,
            "checked_utc": datetime.now(timezone.utc).isoformat(),
            "completed_data_file": False,
            "note": "Does not establish absence of crashes or absence from other agency systems."
        }, indent=2), encoding="utf-8")
        print(f"{year}: public layer returned 0; coverage gap recorded, no completed CSV created", flush=True)
        return
    ids_result = get_json({"f": "json", "where": where, "returnIdsOnly": "true"})
    if "objectIds" not in ids_result:
        raise RuntimeError(f"{year}: missing objectIds response")
    ids = sorted(ids_result.get("objectIds") or [])
    if len(ids) != expected or len(set(ids)) != expected:
        raise RuntimeError(f"{year}: official count {expected} disagrees with unique returned IDs; retry required")
    print(f"{year}: {len(ids):,} records", flush=True)

    columns = None
    written = 0
    with partial.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = None
        for start in range(0, len(ids), CHUNK):
            batch = ids[start:start + CHUNK]
            result = get_json({
                "f": "json",
                "objectIds": ",".join(map(str, batch)),
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": "4326",
            })
            features = result.get("features", [])
            if columns is None:
                columns = [field["name"] for field in result.get("fields", [])]
                columns += ["longitude", "latitude"]
                writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
                writer.writeheader()
            for feature in features:
                row = dict(feature.get("attributes") or {})
                row["ACC_DATE"] = iso_date(row.get("ACC_DATE"))
                row["INV_DATE"] = iso_date(row.get("INV_DATE"))
                geometry = feature.get("geometry") or {}
                row["longitude"] = geometry.get("x", "")
                row["latitude"] = geometry.get("y", "")
                writer.writerow(row)
            written += len(features)
            print(f"{year}: {written:,}/{len(ids):,}", flush=True)

    if written != len(ids):
        raise RuntimeError(f"{year}: expected {len(ids)} records, wrote {written}")
    os.replace(partial, final)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "SOURCE.txt").write_text(
        "Official source: Missouri State Highway Patrol, STARS/MOCARS crash map\n"
        "Portal: https://www.mshp.dps.missouri.gov/TR15Map/index.jsp\n"
        "ArcGIS layer: https://www.mshp.dps.missouri.gov/arcgis/rest/services/STARS_CRASHES/MapServer/0\n"
        "Downloaded as individual crash records, partitioned by ACC_DATE year.\n"
        "The current year is provisional/incomplete.\n",
        encoding="utf-8",
    )
    for year in reversed(list(YEARS)):
        download_year(year)


if __name__ == "__main__":
    main()
