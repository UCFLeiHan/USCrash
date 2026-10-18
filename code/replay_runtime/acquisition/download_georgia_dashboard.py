#!/usr/bin/env python3
"""Download Georgia GDOT dashboard crash records by year in the background."""

from __future__ import annotations
import os as _uscrash_paths_os

import csv
import json
import os
import re
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests


HOME = "https://gdot.aashtowaresafety.net/crash-data-dashboard/"
ROOT = (Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/GA')
METRIC_ID = "8b8bbe7f-ec9d-439c-9ffc-3d1d5ecf971a"
YEARS = range(2021, 2026)
LOG = ROOT / "download.log"


def log(message: str) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = f"{stamp} {message}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def get_context(session: requests.Session):
    page = session.get(HOME, timeout=90)
    page.raise_for_status()
    match = re.search(r"PORTAL = (\{[^\n]+\})", page.text)
    if not match:
        raise RuntimeError("The public portal configuration was not found")
    portal = json.loads(match.group(1))
    dashboard_id = portal["content"]["dashboardIds"][0]
    token = portal["entityToken"]
    response = session.get(
        f"https://gdot.aashtowaresafety.net/api/dashboards/{dashboard_id}",
        params={"entityToken": token},
        timeout=120,
    )
    response.raise_for_status()
    dashboard = response.json()["data"]
    return portal, dashboard_id, token, dashboard


def download_ready_file(session: requests.Session, link: str, year: int) -> Path:
    year_dir = ROOT / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    partial = year_dir / f"georgia_gdot_{year}.download.partial"
    response = session.get(link, stream=True, timeout=600)
    response.raise_for_status()
    with partial.open("wb") as handle:
        for chunk in response.iter_content(1024 * 1024):
            if chunk:
                handle.write(chunk)

    with partial.open("rb") as handle:
        signature = handle.read(4)
    final = year_dir / f"georgia_gdot_{year}.csv"
    if signature[:2] == b"PK":
        with zipfile.ZipFile(partial) as archive:
            candidates = [n for n in archive.namelist() if n.lower().endswith(".csv")]
            if len(candidates) != 1:
                raise RuntimeError(f"Unexpected ZIP contents: {archive.namelist()}")
            extracted = year_dir / (final.name + ".partial")
            with archive.open(candidates[0]) as src, extracted.open("wb") as dst:
                while block := src.read(1024 * 1024):
                    dst.write(block)
            extracted.replace(final)
        partial.unlink()
    else:
        partial.replace(final)
    return final


def validate_csv(path: Path) -> tuple[int, list[str]]:
    rows = 0
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        for _ in reader:
            rows += 1
    if rows == 0:
        raise RuntimeError(f"Downloaded CSV is empty: {path}")
    return rows, header


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/140 Safari/537.36"
    )
    portal, dashboard_id, token, dashboard = get_context(session)
    shown = list(dashboard["metrics"][METRIC_ID]["dataSchema"]["shownColumns"])
    extra = [
        "IncidentIdNbr",
        "DateofIncidentDte",
        "FatalitiesNbr",
        "UnitsNbr",
        "CountyNameTxt",
        "CityNameTxt",
        "Roadway",
        "Intersection Name",
    ]
    columns = shown + [name for name in extra if name not in shown]
    template = dashboard["content"]["filters"][0]
    endpoint = (
        f"https://gdot.aashtowaresafety.net/api/dashboards/{dashboard_id}"
        f"/metrics/{METRIC_ID}/download"
    )
    summary = {
        "source": HOME,
        "dashboard_id": dashboard_id,
        "downloaded_at_utc": None,
        "years": {},
    }

    log("Georgia dashboard downloader started")
    for year in YEARS:
        final = ROOT / str(year) / f"georgia_gdot_{year}.csv"
        if final.exists() and final.stat().st_size > 0:
            rows, header = validate_csv(final)
            summary["years"][str(year)] = {
                "status": "existing",
                "rows": rows,
                "bytes": final.stat().st_size,
                "columns": header,
            }
            log(f"{year}: existing validated file, {rows:,} rows")
            continue

        year_filter = json.loads(json.dumps(template))
        year_filter["script"]["params"] = {"param1": year, "param2": year}
        year_filter["selectionValue"] = [str(year), str(year)]
        body = {
            "filters": [year_filter],
            "fileName": f"georgia_crashes_{year}",
            "columns": columns,
        }
        last_status = None
        while True:
            response = session.post(
                endpoint,
                params={"entityToken": token},
                json=body,
                timeout=180,
            )
            response.raise_for_status()
            status = response.json()
            status_key = (status.get("status"), status.get("phase"), status.get("progress"))
            if status_key != last_status:
                safe_status = {k: v for k, v in status.items() if k != "link"}
                if "link" in status:
                    safe_status["link"] = "[ready download URL omitted]"
                log(f"{year}: {safe_status}")
                last_status = status_key
            if status.get("status") == "FILE_READY":
                path = download_ready_file(session, status["link"], year)
                rows, header = validate_csv(path)
                summary["years"][str(year)] = {
                    "status": "downloaded",
                    "rows": rows,
                    "bytes": path.stat().st_size,
                    "columns": header,
                }
                log(f"{year}: saved and validated, {rows:,} rows, {path.stat().st_size:,} bytes")
                break
            if status.get("status") == "FILE_FAILED":
                raise RuntimeError(f"{year}: server failed to build export: {status}")
            time.sleep(15)

    summary["downloaded_at_utc"] = datetime.now(timezone.utc).isoformat()
    (ROOT / "qa_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ROOT / "README.md").write_text(
        "# Georgia statewide crash data (GDOT Crash Data Dashboard)\n\n"
        "Official source: https://gdot.aashtowaresafety.net/crash-data-dashboard#/\n\n"
        "Public dashboard export split into yearly UTF-8 CSV files for 2021–2025. "
        "Each row is a crash-level record. See `qa_summary.json` for validation results "
        "and `download.log` for server-side generation progress.\n",
        encoding="utf-8",
    )
    log("All Georgia years completed")


if __name__ == "__main__":
    main()
