#!/usr/bin/env python3
"""Download Michigan Traffic Crash Facts list records, 90 rows per page.

The public query tool enforces a 90-row page size but accepts stable offsets.
This downloader runs closed annual datasets in parallel and checkpoints after
every page so an interrupted job resumes without repeating completed pages.
"""

from __future__ import annotations
import os as _uscrash_paths_os

import argparse
import csv
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests


BASE = "https://www.michigantrafficcrashfacts.org"
API = f"{BASE}/qjson"
OUT = (Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/MI')
PAGE_SIZE = 90

# Crash-level fields needed for the study.  The API returns human-readable
# labels rather than the underlying numeric codes.
COLUMNS = sorted(
    [
        "0,0",   # Crash ID
        "0,2",   # month
        "0,3",   # day
        "0,4",   # year
        "0,5",   # hour/time band
        "0,6",   # day of week
        "0,7",   # county
        "0,8",   # city/township
        "0,15",  # road condition
        "0,17",  # speed limit
        "0,18",  # traffic control
        "0,19",  # trafficway
        "0,24",  # light
        "0,25",  # crash type
        "0,28",  # total units
        "0,29",  # motor vehicles
        "0,31",  # hit and run
        "0,46",  # PDO
        "0,47",  # injury crash
        "0,48",  # fatal crash
        "0,49",  # greatest severity
        "0,50",  # longitude
        "0,51",  # latitude
        "0,75",  # non-motor vehicles
        "0,76",  # weather
        "0,78",  # contributing circumstance 1
        "0,79",  # contributing circumstance 2
    ]
)


def new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 Michigan-crash-public-data-research",
            "Referer": f"{BASE}/data/querytool/",
        }
    )
    return session


def query_code(year: int) -> str:
    return f"1;0;{year};;"


def get_count(session: requests.Session, year: int) -> int:
    response = session.get(API, params={"q": query_code(year)}, timeout=90)
    response.raise_for_status()
    payload = response.json()
    errors = payload.get("errors") or []
    if errors:
        raise RuntimeError(f"{year}: {errors}")
    return int(payload["0"]["crash_id"])


def page_parameters(offset: int) -> str:
    ordering = ":".join(f"{index},asc" for index in range(len(COLUMNS)))
    return f"{':'.join(COLUMNS)}|{offset}|{PAGE_SIZE}|{ordering}"


def get_page(session: requests.Session, year: int, offset: int, retries: int = 6) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.post(
                API,
                data={
                    "q": query_code(year),
                    "v": "list",
                    "p": page_parameters(offset),
                },
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("errors"):
                raise RuntimeError(str(payload["errors"]))
            return payload
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(30, 2**attempt))
    raise RuntimeError(f"{year} offset {offset}: {last_error}")


def numeric_rows(payload: dict) -> list[dict]:
    return [payload[key] for key in sorted((k for k in payload if k.isdigit()), key=int)]


def download_year(year: int, output_root: Path) -> dict:
    session = new_session()
    folder = output_root / str(year)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"MI_crashes_{year}_mtcf.csv"
    state_path = folder / "mtcf_download_state.json"

    count = get_count(session, year)
    offset = 0
    if state_path.exists() and target.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("year") == year and state.get("expected_count") == count:
            offset = int(state.get("next_offset", 0))
    if offset == 0 and target.exists():
        target.unlink()

    first = get_page(session, year, offset)
    rows = numeric_rows(first)
    if not rows and offset < count:
        raise RuntimeError(f"{year}: empty page at offset {offset}")

    # Remove the token used by the website to request a paid/full police report.
    # The public research attributes and public map coordinates are retained.
    fields = [name for name in first["headers"] if name != "report"]
    for name in ("lng", "lat"):
        if name in rows[0] and name not in fields:
            fields.append(name)
    fields.append("source")

    mode = "a" if offset and target.exists() else "w"
    with target.open(mode, newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        if mode == "w":
            writer.writeheader()

        total_pages = math.ceil(count / PAGE_SIZE)
        while offset < count:
            payload = first
            page_rows = numeric_rows(payload)
            if not page_rows:
                raise RuntimeError(f"{year}: empty page at offset {offset}")
            for row in page_rows:
                row["source"] = f"{BASE}/data/querytool/#q{query_code(year)}/list"
                writer.writerow(row)
            output.flush()
            offset += len(page_rows)
            state_path.write_text(
                json.dumps(
                    {
                        "year": year,
                        "expected_count": count,
                        "next_offset": offset,
                        "page_size": PAGE_SIZE,
                        "complete": offset >= count,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            if offset % 900 == 0 or offset >= count:
                print(
                    f"{year}: {offset:,}/{count:,} ({math.ceil(offset / PAGE_SIZE):,}/{total_pages:,} pages)",
                    flush=True,
                )
            if offset < count:
                first = get_page(session, year, offset)

    return {"year": year, "rows": offset, "file": str(target)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", nargs="*", type=int, default=list(range(2020, 2026)))
    parser.add_argument("--year-workers", type=int, default=3)
    parser.add_argument("--output-root", type=Path, default=OUT)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)

    failed = []
    with ThreadPoolExecutor(max_workers=max(1, args.year_workers)) as pool:
        futures = {
            pool.submit(download_year, year, args.output_root): year
            for year in sorted(set(args.years), reverse=True)
        }
        for future in as_completed(futures):
            year = futures[future]
            try:
                print(f"COMPLETE {future.result()}", flush=True)
            except Exception as exc:
                failed.append(year)
                print(f"FAILED {year}: {type(exc).__name__}: {exc}", flush=True)
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
