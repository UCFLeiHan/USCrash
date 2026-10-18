import csv
import json
import os
import time
from calendar import monthrange
from datetime import date
from pathlib import Path

import requests

URL = "https://ntip2021.nebraska.gov/NTIP2021/Map/Crashes"
ROOT = Path(r"F:\LH_Research\USCrash\Crash\States\NE")
START_YEAR = 2021
TODAY = date.today()
FIELDS = [
    "crash_key", "latitude", "longitude", "severity_code", "date", "time",
    "day_of_week", "county", "location", "crash_type",
    "first_harmful_event", "alcohol_related", "weather",
]

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 research data downloader"})


def fetch(start, end):
    for attempt in range(7):
        try:
            response = session.post(
                URL,
                data={"fromDate": start.isoformat(), "toDate": end.isoformat()},
                timeout=300,
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            if attempt == 6:
                raise
            time.sleep(2 ** attempt)


def flatten(result):
    rows = []
    for group in result.get("CoordGroups", []):
        for crash in group.get("Crashes", []):
            rows.append({
                "crash_key": crash.get("k"),
                "latitude": crash.get("a"),
                "longitude": crash.get("o"),
                "severity_code": crash.get("s"),
                "date": crash.get("d"),
                "time": crash.get("t"),
                "day_of_week": crash.get("y"),
                "county": crash.get("c"),
                "location": crash.get("l"),
                "crash_type": crash.get("m"),
                "first_harmful_event": crash.get("f"),
                "alcohol_related": crash.get("r"),
                "weather": "|".join(crash.get("w") or []),
            })
    return rows


ROOT.mkdir(parents=True, exist_ok=True)
for year in range(START_YEAR, TODAY.year + 1):
    year_dir = ROOT / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    final = year_dir / f"NE_mapped_crashes_{year}.csv"
    if final.exists():
        continue

    by_key = {}
    monthly = []
    last_month = TODAY.month if year == TODAY.year else 12
    for month in range(1, last_month + 1):
        start = date(year, month, 1)
        end = date(year, month, monthrange(year, month)[1])
        if end > TODAY:
            end = TODAY
        result = fetch(start, end)
        rows = flatten(result)
        for row in rows:
            by_key[str(row["crash_key"])] = row
        monthly.append({
            "month": month,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "mapped_records": len(rows),
            "severity": result.get("Severity"),
        })
        print(year, month, len(rows), "year_total", len(by_key), flush=True)

    partial = final.with_suffix(".csv.partial")
    with partial.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(by_key.values())
    os.replace(partial, final)
    (year_dir / "portal_summary_2021plus.json").write_text(
        json.dumps({"year": year, "mapped_records": len(by_key), "months": monthly}, indent=2),
        encoding="utf-8",
    )
    print(year, "COMPLETE", len(by_key), flush=True)
