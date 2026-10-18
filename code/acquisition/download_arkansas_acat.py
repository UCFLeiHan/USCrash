#!/usr/bin/env python3
"""Download Arkansas ARDOT ACAT crash records and split them into yearly CSVs."""

from __future__ import annotations

import csv
import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


SERVICE = (
    "https://gis.ardot.gov/referenced/rest/services/"
    "TPP_TrafficSafety/NotForOfficialUse/FeatureServer/20"
)
OUT_ROOT = Path(r"F:\LH_Research\USCrash\Crash\States\AR")
YEARS = range(2021, 2026)


def get_json(url: str, params: dict | None = None, attempts: int = 5, post: bool = False) -> dict:
    encoded = urllib.parse.urlencode(params or {}).encode("ascii")
    if params and not post:
        url += "?" + encoded.decode("ascii")
    last_error = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url,
                data=encoded if post else None,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
                    "Accept": "application/json,text/plain,*/*",
                    "Referer": "https://gis.ardot.gov/portal/apps/dashboards/3ae35f942fa340888abd27f26d405558",
                },
            )
            with urllib.request.urlopen(request, timeout=90) as response:
                value = json.load(response)
            if "error" in value:
                raise RuntimeError(value["error"])
            return value
        except Exception as exc:
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"Request failed: {url}") from last_error


def iso_date(value):
    if value in (None, ""):
        return ""
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    meta = get_json(SERVICE, {"f": "json"})
    fields = [f["name"] for f in meta["fields"]]
    date_fields = {f["name"] for f in meta["fields"] if f["type"] == "esriFieldTypeDate"}
    output_fields = fields + ["geometry_x", "geometry_y"]
    qa = {"source": SERVICE, "downloaded_at_utc": datetime.now(timezone.utc).isoformat(), "years": {}}

    for year in YEARS:
        where = f"Year='{year}'"
        ids_result = get_json(
            SERVICE + "/query",
            {"f": "json", "where": where, "returnIdsOnly": "true"},
        )
        ids = sorted(ids_result.get("objectIds") or [])
        year_dir = OUT_ROOT / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        partial = year_dir / f"arkansas_acat_{year}.csv.partial"
        final = year_dir / f"arkansas_acat_{year}.csv"
        city_counts = Counter()
        missing_coords = 0
        seen_ids = set()

        with partial.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=output_fields, extrasaction="ignore")
            writer.writeheader()
            for start in range(0, len(ids), 1000):
                chunk = ids[start : start + 1000]
                result = get_json(
                    SERVICE + "/query",
                    {
                        "f": "json",
                        "objectIds": ",".join(map(str, chunk)),
                        "outFields": "*",
                        "returnGeometry": "true",
                        "outSR": 4326,
                    },
                    post=True,
                )
                for feature in result.get("features", []):
                    row = feature.get("attributes", {})
                    for name in date_fields:
                        row[name] = iso_date(row.get(name))
                    geometry = feature.get("geometry") or {}
                    row["geometry_x"] = geometry.get("x", "")
                    row["geometry_y"] = geometry.get("y", "")
                    if row.get("Latitude") in (None, "") or row.get("Longitude") in (None, ""):
                        missing_coords += 1
                    city_counts[str(row.get("City") or "(missing)")] += 1
                    seen_ids.add(row.get("OBJECTID"))
                    writer.writerow(row)
                print(f"{year}: {min(start + len(chunk), len(ids))}/{len(ids)}", flush=True)

        if len(seen_ids) != len(ids):
            raise RuntimeError(f"{year}: expected {len(ids)} records, wrote {len(seen_ids)} unique OBJECTIDs")
        partial.replace(final)
        qa["years"][str(year)] = {
            "records": len(ids),
            "unique_objectids": len(seen_ids),
            "missing_latitude_or_longitude": missing_coords,
            "top_cities": city_counts.most_common(20),
            "file": str(final),
            "bytes": final.stat().st_size,
        }

    (OUT_ROOT / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_ROOT / "qa_summary.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_ROOT / "README.md").write_text(
        """# Arkansas statewide crash data (ARDOT ACAT)

Official public dashboard: https://gis.ardot.gov/portal/apps/dashboards/3ae35f942fa340888abd27f26d405558

Source layer: https://gis.ardot.gov/referenced/rest/services/TPP_TrafficSafety/NotForOfficialUse/FeatureServer/20

Downloaded as one UTF-8 CSV per year for 2021–2025. Each row represents one crash. The original attributes are preserved, and `geometry_x`/`geometry_y` contain the ArcGIS point geometry transformed to EPSG:4326. ARDOT labels the dashboard data as non-official and advises contacting Arkansas State Police for official records/statistics.
""",
        encoding="utf-8",
    )
    print(json.dumps(qa, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
