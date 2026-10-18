#!/usr/bin/env python3
"""Download recent Kentucky statewide crash extracts from crashinformationky.org.

The public site stores query state in the ASP.NET session.  This script opens one
headless Edge session to initialize that state, then uses the site's own search
and CSV-extract endpoints one day at a time.  Daily ZIPs make the job resumable;
after downloading, the seven record-level tables are merged into annual CSVs.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By


BASE = "http://crashinformationky.org"
DEFAULT_ROOT = Path(r"F:\LH_Research\USCrash\Crash\States\KY")
MODEL_ID = "3d52afb0-a229-461f-968a-5814991d3cb2"


def date_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def query_json(day: date) -> str:
    label = f"{day.day} {day.strftime('%B %Y')}"
    expression = {
        "typeName": "CONST",
        "dataType": "Date",
        "kind": "Scalar",
        "value": day.isoformat(),
        "text": label,
    }
    query = {
        "root": {
            "linkType": "All",
            "enabled": True,
            "conditions": [
                {
                    "justAdded": False,
                    "typeName": "SMPL",
                    "enabled": True,
                    "operatorID": "DateFromTo",
                    "expressions": [
                        {
                            "kind": "Attribute",
                            "typeName": "ENTATTR",
                            "id": "Incident.IncidentDte",
                        },
                        expression,
                        dict(expression),
                    ],
                    "blockId": "QueryPanel-cond-1",
                }
            ],
        },
        "columns": [],
        "justsorted": [],
        "modelId": MODEL_ID,
        "modelName": "Classic-Collision",
    }
    return json.dumps(query, separators=(",", ":"))


def open_public_session() -> tuple[requests.Session, str]:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,1000")
    options.page_load_strategy = "eager"
    driver = webdriver.Edge(options=options)
    try:
        driver.get(f"{BASE}/AdvancedSearch")
        deadline = time.time() + 45
        while time.time() < deadline:
            try:
                ready = driver.execute_script(
                    "return !!(window.EQ && EQ.client && EQ.client.getQuery())"
                )
                if ready:
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("Kentucky search model did not initialize")

        token = driver.find_element(By.NAME, "__RequestVerificationToken").get_attribute(
            "value"
        )
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": driver.execute_script("return navigator.userAgent"),
                "Referer": f"{BASE}/AdvancedSearch",
            }
        )
        for cookie in driver.get_cookies():
            session.cookies.set(
                cookie["name"], cookie["value"], domain=cookie.get("domain")
            )
        return session, token
    finally:
        driver.quit()


def decode_execute_response(response: requests.Response) -> dict:
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected ExecuteQuery response")
    return payload


def download_day(
    session: requests.Session,
    token: str,
    day: date,
    destination: Path,
    retries: int,
) -> tuple[str, int]:
    query = query_json(day)
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            execute = session.post(
                f"{BASE}/AdvancedSearch/ExecuteQuery",
                data={"queryJson": query, "__RequestVerificationToken": token},
                timeout=180,
            )
            payload = decode_execute_response(execute)
            error = payload.get("errorMessage")
            if error:
                raise RuntimeError(str(error))

            result = payload.get("result") or {}
            total = int(result.get("total", len(result.get("results", []))) or 0)

            set_type = session.post(
                f"{BASE}/AdvancedSearch/SetExtractType",
                data={
                    "data": "COM",
                    "__RequestVerificationToken": token,
                    "json": query,
                },
                timeout=60,
            )
            set_type.raise_for_status()

            extract = session.get(
                f"{BASE}/AdvancedSearch/GenerateExtract", timeout=360
            )
            extract.raise_for_status()
            content = extract.content
            if not content.startswith(b"PK"):
                raise RuntimeError(
                    f"Expected ZIP, received {extract.headers.get('content-type')}"
                )
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                archive.testzip()
                names = archive.namelist()

            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(".zip.partial")
            temporary.write_bytes(content)
            temporary.replace(destination)
            return ",".join(names), total
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(30, 3 * attempt))
    raise RuntimeError(f"{day}: {last_error}")


def rebuild_annual_csv(year_dir: Path, year: int) -> dict[str, int]:
    output_rows: dict[str, int] = defaultdict(int)
    handles: dict[str, object] = {}
    writers: dict[str, csv.writer] = {}
    headers: dict[str, list[str]] = {}
    try:
        for zip_path in sorted((year_dir / "daily_zips").glob("*.zip")):
            with zipfile.ZipFile(zip_path) as archive:
                for member in sorted(archive.namelist()):
                    if not member.lower().endswith(".txt"):
                        continue
                    table = Path(member).stem
                    text = archive.read(member).decode("utf-8-sig", errors="replace")
                    reader = csv.reader(io.StringIO(text))
                    try:
                        header = next(reader)
                    except StopIteration:
                        continue
                    if header and header[-1] == "":
                        header = header[:-1]
                    if table not in writers:
                        output = year_dir / f"KY_{table}_{year}.csv"
                        handle = output.open("w", newline="", encoding="utf-8-sig")
                        handles[table] = handle
                        writers[table] = csv.writer(handle)
                        headers[table] = header
                        writers[table].writerow(header)
                    elif headers[table] != header:
                        raise RuntimeError(f"Header changed in {zip_path.name}: {table}")

                    for row in reader:
                        if row and row[-1] == "" and len(row) == len(header) + 1:
                            row = row[:-1]
                        if not row or not any(value.strip() for value in row):
                            continue
                        writers[table].writerow(row)
                        output_rows[table] += 1
    finally:
        for handle in handles.values():
            handle.close()
    return dict(output_rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--year", type=int, action="append", dest="years")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--rebuild-only", action="store_true")
    return parser.parse_args()


def requested_ranges(args: argparse.Namespace) -> list[tuple[date, date]]:
    today = date.today()
    if args.start_date or args.end_date:
        if not (args.start_date and args.end_date):
            raise SystemExit("--start-date and --end-date must be used together")
        if args.start_date > args.end_date:
            raise SystemExit("start date is after end date")
        return [(args.start_date, args.end_date)]
    years = args.years or [today.year]
    return [
        (date(year, 1, 1), min(date(year, 12, 31), today)) for year in sorted(set(years))
    ]


def main() -> int:
    args = parse_args()
    ranges = requested_ranges(args)
    session = token = None
    if not args.rebuild_only:
        session, token = open_public_session()

    failures: list[str] = []
    for start, end in ranges:
        for day in date_range(start, end):
            year_dir = args.output_root / str(day.year)
            target = year_dir / "daily_zips" / f"KY_{day.isoformat()}.zip"
            if target.exists() and target.stat().st_size > 22:
                print(f"SKIP {day} ({target.stat().st_size:,} bytes)", flush=True)
                continue
            if args.rebuild_only:
                continue
            try:
                names, total = download_day(
                    session, token, day, target, retries=args.retries
                )
                print(
                    f"OK   {day}: {total:,} crashes, {target.stat().st_size:,} bytes; {names}",
                    flush=True,
                )
            except Exception as exc:
                message = str(exc)
                failures.append(message)
                print(f"FAIL {message}", file=sys.stderr, flush=True)
            time.sleep(args.delay)

    for year in sorted({start.year for start, _ in ranges}):
        year_dir = args.output_root / str(year)
        if (year_dir / "daily_zips").exists():
            counts = rebuild_annual_csv(year_dir, year)
            manifest = {
                "state": "Kentucky",
                "source": f"{BASE}/AdvancedSearch",
                "year": year,
                "generated_at": datetime.now().astimezone().isoformat(),
                "daily_zip_count": len(list((year_dir / "daily_zips").glob("*.zip"))),
                "annual_table_rows": counts,
                "failed_requests": [x for x in failures if str(year) in x],
            }
            (year_dir / "download_manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
            print(f"MERGED {year}: {counts}", flush=True)

    if failures:
        print(f"Completed with {len(failures)} failed day(s). Re-run to retry.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
