"""Download NJDOT AASHTOWare Crash Portal crash rows for years without classic ZIPs.

Parallelizes by year x month. Within each month, pages with id_cr range cursor.
Resumable via per-month JSONL shards + manifest.

Output:
  States/NJ/{year}/NJ_portal_crashes_{year}.csv
  States/NJ/{year}/_portal/{YYYY}_{MM}.jsonl
  States/NJ/{year}/_portal/manifest.json
"""
from __future__ import annotations

import csv
import json
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import requests

ROOT = Path(r"F:\LH_Research\USCrash\Crash\States\NJ")
TOKEN_FILE = ROOT / "_portal" / "entity_token.txt"
PORTAL = "https://njdot.aashtowaresafety.net/njdot-crash-data-dashboard"
DASHBOARD_ID = "82d79442-3eac-4a7f-a4f3-9177a99740f6"
CRASH_METRIC_ID = "1b5f3254-21b6-4a50-becd-0e9c8bdf5c21"
DATASET_ID = "4008b3e5-a75c-4efe-ac1f-4dd7c7e26a65"
YEAR_QF = "3d5dc6cb-deab-4aad-86ed-b77a9864a9d7"
MONTH_QF = "099ddcce-41e7-4817-924a-37f03a8e3b3d"

YEARS = (2019, 2024, 2025, 2026)
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
MONTH_NUM = {name: i for i, name in enumerate(MONTHS, start=1)}

WORKERS = 8
PAGE_SIZE = 500
REQUEST_TIMEOUT = 120
MAX_RETRIES = 8

# Prefer stable core fields first, then whatever else appears.
PREFERRED_FIELDS = [
    "id_cr",
    "njdot_dln",
    "casenumber",
    "dateofcrash",
    "timeofcrash",
    "County",
    "countycode",
    "Municipality",
    "municipalitycode",
    "latitude",
    "longitude",
    "Crash Type",
    "crashtypecode",
    "severitycode",
    "Severity Code*",
    "severityrating_5",
    "Severity Rating (5)",
    "injurycount",
    "fatalitycount",
    "First Harmful Event",
    "firstharmfuleventcode",
    "Weather Condition",
    "Light Condition",
    "streetname",
    "milepost",
]


class TokenStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token: str | None = None
        self._fetched_at = 0.0
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://njdot.aashtowaresafety.net",
                "Referer": PORTAL,
            }
        )

    @property
    def session(self) -> requests.Session:
        return self._session

    def get(self, force: bool = False) -> str:
        with self._lock:
            age = time.time() - self._fetched_at
            if not force and self._token and age < 45 * 60:
                return self._token
            token = self._fetch_token()
            self._token = token
            self._fetched_at = time.time()
            TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_FILE.write_text(token, encoding="utf-8")
            return token

    def _fetch_token(self) -> str:
        # 1) Seeded/cached public portal token.
        if TOKEN_FILE.exists():
            cached = TOKEN_FILE.read_text(encoding="utf-8").strip()
            if cached and self._token_works(cached):
                return cached

        # 2) Reload portal HTML (modern UA required; else /oldbrowser redirect).
        html = self._session.get(PORTAL, timeout=60)
        html.raise_for_status()
        token = self._extract_token(html.text)
        if token and self._token_works(token):
            return token

        raise RuntimeError(
            "Could not obtain portal entityToken. Save PORTAL.entityToken into "
            f"{TOKEN_FILE}"
        )

    def _token_works(self, token: str) -> bool:
        url = (
            f"https://njdot.aashtowaresafety.net/api/dashboards/{DASHBOARD_ID}"
            f"/metrics/{CRASH_METRIC_ID}/search?entityToken="
            f"{requests.utils.quote(token, safe='')}"
        )
        try:
            resp = self._session.post(
                url,
                json={"filters": [], "sorting": {"direction": "desc", "sortBy": "id_cr"}},
                timeout=60,
            )
            if not resp.ok:
                return False
            payload = resp.json()
            return bool(payload.get("success") and "rows" in (payload.get("data") or {}))
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _extract_token(text: str) -> str | None:
        patterns = [
            r'"entityToken"\s*:\s*"([^"]+)"',
            r"'entityToken'\s*:\s*'([^']+)'",
            r"entityToken=([^&\"'\s]+)",
        ]
        for pat in patterns:
            match = re.search(pat, text)
            if match:
                return unquote(match.group(1))
        return None


TOKENS = TokenStore()
PRINT_LOCK = threading.Lock()


def log(msg: str) -> None:
    with PRINT_LOCK:
        print(msg, flush=True)


def year_filter(year: int) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "field": "Year Dashboard",
        "datasetId": DATASET_ID,
        "key": "Year Dashboard",
        "filter": "group",
        "filters": [
            {
                "value": str(year),
                "id": str(uuid.uuid4()),
                "field": "Year Dashboard",
                "datasetId": DATASET_ID,
                "key": "Year Dashboard",
                "filter": "term",
                "displayName": "Year Dashboard",
                "type": "term",
            }
        ],
        "value": [str(year)],
        "displayName": "Year Dashboard",
        "type": "term",
        "quickFilterId": YEAR_QF,
    }


def month_filter(month: str) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "field": "Month Dashboard",
        "datasetId": DATASET_ID,
        "key": "Month Dashboard",
        "filter": "group",
        "filters": [
            {
                "value": month,
                "id": str(uuid.uuid4()),
                "field": "Month Dashboard",
                "datasetId": DATASET_ID,
                "key": "Month Dashboard",
                "filter": "term",
                "displayName": "Month Dashboard",
                "type": "term",
            }
        ],
        "value": [month],
        "displayName": "Month Dashboard",
        "type": "term",
        "quickFilterId": MONTH_QF,
    }


def search(filters: list[dict[str, Any]], force_token: bool = False) -> dict[str, Any]:
    token = TOKENS.get(force=force_token)
    url = (
        f"https://njdot.aashtowaresafety.net/api/dashboards/{DASHBOARD_ID}"
        f"/metrics/{CRASH_METRIC_ID}/search?entityToken={requests.utils.quote(token, safe='')}"
    )
    body = {"filters": filters, "sorting": {"direction": "desc", "sortBy": "id_cr"}}
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = TOKENS.session.post(url, json=body, timeout=REQUEST_TIMEOUT)
            if resp.status_code in {401, 403}:
                token = TOKENS.get(force=True)
                url = (
                    f"https://njdot.aashtowaresafety.net/api/dashboards/{DASHBOARD_ID}"
                    f"/metrics/{CRASH_METRIC_ID}/search?entityToken="
                    f"{requests.utils.quote(token, safe='')}"
                )
                resp = TOKENS.session.post(url, json=body, timeout=REQUEST_TIMEOUT)
            if resp.status_code >= 500:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            resp.raise_for_status()
            payload = resp.json()
            if not payload.get("success"):
                raise RuntimeError(str(payload.get("error") or payload)[:300])
            return payload["data"]
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(min(2**attempt, 30))
            if attempt >= 2:
                # refresh token on sticky failures
                try:
                    TOKENS.get(force=True)
                except Exception:
                    pass
    raise RuntimeError(f"search failed: {last_err}")


def shard_paths(year: int, month: str) -> tuple[Path, Path]:
    portal_dir = ROOT / str(year) / "_portal"
    portal_dir.mkdir(parents=True, exist_ok=True)
    mm = f"{MONTH_NUM[month]:02d}"
    jsonl = portal_dir / f"{year}_{mm}.jsonl"
    done = portal_dir / f"{year}_{mm}.done.json"
    return jsonl, done


def download_month(year: int, month: str) -> dict[str, Any]:
    jsonl_path, done_path = shard_paths(year, month)
    if done_path.exists():
        meta = json.loads(done_path.read_text(encoding="utf-8"))
        if meta.get("complete") and jsonl_path.exists():
            return meta

    filters = [year_filter(year), month_filter(month)]
    first = search(filters)
    expected = int(first.get("totalRows") or 0)
    if expected == 0:
        jsonl_path.write_text("", encoding="utf-8")
        meta = {
            "year": year,
            "month": month,
            "expected": 0,
            "written": 0,
            "complete": True,
            "pages": 0,
        }
        done_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        log(f"{year}-{month}: 0 rows")
        return meta

    # Restart shard each run unless previously complete.
    written = 0
    pages = 0
    min_id: int | None = None
    seen: set[int] = set()

    with jsonl_path.open("w", encoding="utf-8", newline="\n") as out:
        while True:
            page_filters = [year_filter(year), month_filter(month)]
            if min_id is not None:
                page_filters.append(
                    {
                        "field": "id_cr",
                        "key": "id_cr",
                        "filter": "range",
                        "type": "range",
                        "lt": min_id,
                    }
                )
            data = search(page_filters) if pages else first
            rows = data.get("rows") or []
            if not rows:
                break
            pages += 1
            page_ids = []
            for row in rows:
                rid = row.get("id_cr")
                if rid is None or rid in seen:
                    continue
                seen.add(rid)
                page_ids.append(rid)
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                written += 1
            if not page_ids:
                break
            min_id = min(page_ids)
            # Keep first payload only once.
            first = {"rows": [], "totalRows": expected}
            if written >= expected or len(rows) < PAGE_SIZE:
                # Confirm no more pages.
                if written >= expected:
                    break
                # If API returned short page before expected, try one more cursor page.
                if len(rows) < PAGE_SIZE:
                    break

    # Allow tiny drift if portal updates mid-download; require emptying the cursor.
    complete = written == expected or (written > 0 and written >= expected - 5)
    if written < expected:
        # Final confirmation page
        confirm_filters = [
            year_filter(year),
            month_filter(month),
            {
                "field": "id_cr",
                "key": "id_cr",
                "filter": "range",
                "type": "range",
                "lt": min_id,
            },
        ]
        more = search(confirm_filters).get("rows") or []
        if more:
            complete = False
        elif written >= int(expected * 0.995):
            complete = True
    meta = {
        "year": year,
        "month": month,
        "expected": expected,
        "written": written,
        "complete": complete,
        "pages": pages,
        "min_id": min_id,
    }
    done_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    status = "OK" if complete else "MISMATCH"
    log(f"{year}-{month}: {written:,}/{expected:,} rows pages={pages} [{status}]")
    if not complete:
        raise RuntimeError(f"{year}-{month} count mismatch {written} != {expected}")
    return meta


def merge_year(year: int) -> Path:
    portal_dir = ROOT / str(year) / "_portal"
    out_csv = ROOT / str(year) / f"NJ_portal_crashes_{year}.csv"
    jsonls = sorted(portal_dir.glob(f"{year}_*.jsonl"))
    if not jsonls:
        raise RuntimeError(f"No shards for {year}")

    fieldnames: list[str] = []
    seen_fields: set[str] = set()
    for preferred in PREFERRED_FIELDS:
        # discover actual presence while reading first few lines later
        pass

    # First pass: discover union of keys while streaming preferred order.
    for path in jsonls:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                for key in row:
                    if key not in seen_fields:
                        seen_fields.add(key)
                # enough to settle schema after some rows; still scan all for safety
    for key in PREFERRED_FIELDS:
        if key in seen_fields:
            fieldnames.append(key)
    for key in sorted(seen_fields):
        if key not in fieldnames:
            fieldnames.append(key)

    rows_written = 0
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for path in jsonls:
            with path.open("r", encoding="utf-8") as src:
                for line in src:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    writer.writerow(row)
                    rows_written += 1

    manifest = {
        "year": year,
        "csv": str(out_csv),
        "rows": rows_written,
        "fields": len(fieldnames),
        "source": "NJDOT AASHTOWare Crash Data Portal Raw Tables API",
        "note": "Preliminary/subject to change per portal disclaimer",
    }
    (portal_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log(f"MERGED {year}: {rows_written:,} rows -> {out_csv}")
    return out_csv


def main() -> None:
    t0 = time.time()
    log("Fetching portal entityToken...")
    token = TOKENS.get(force=True)
    log(f"Token OK (len={len(token)}) workers={WORKERS} years={list(YEARS)}")

    jobs = [(year, month) for year in YEARS for month in MONTHS]
    results: list[dict[str, Any]] = []
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(download_month, y, m): (y, m) for y, m in jobs}
        for fut in as_completed(futures):
            y, m = futures[fut]
            try:
                results.append(fut.result())
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{y}-{m}: {exc}")
                log(f"ERROR {y}-{m}: {exc}")

    if errors:
        log(f"Completed with {len(errors)} shard errors; merging complete years only")
    else:
        log("All shards complete")

    for year in YEARS:
        dones = list((ROOT / str(year) / "_portal").glob(f"{year}_*.done.json"))
        ok = True
        for done in dones:
            meta = json.loads(done.read_text(encoding="utf-8"))
            if not meta.get("complete"):
                ok = False
                break
        if len(dones) < 12:
            ok = False
        if ok:
            merge_year(year)
        else:
            log(f"SKIP merge {year}: incomplete shards")

    log(f"DONE in {(time.time() - t0) / 60:.1f} min; errors={len(errors)}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
