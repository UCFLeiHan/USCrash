import csv
import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from bs4 import BeautifulSoup


BASE = "https://mdotapps.maine.gov/MaineCrashPublic/PublicQueryMap"
DETAIL = BASE + ".aspx/GetReportDetails"
OUT = Path(r"F:\LH_Research\USCrash\Crash\States\ME")
YEARS = (2026, 2025, 2024)
WORKERS = 6
YEAR_WORKERS = 2


def public_map_records(year: int):
    session = requests.Session()
    page = session.get(BASE, timeout=90)
    page.raise_for_status()
    soup = BeautifulSoup(page.text, "html.parser")
    form = {}
    for item in soup.select("input[name]"):
        kind = (item.get("type") or "").lower()
        if kind in {"submit", "button", "image", "file"}:
            continue
        if kind in {"checkbox", "radio"} and not item.has_attr("checked"):
            continue
        form[item["name"]] = item.get("value", "")
    for key in list(form):
        if "RadScriptManager" in key or key == "ctl00_RadAjaxManager1":
            form.pop(key, None)
    form["ctl00$ContentPlaceHolder1$rddYearFrom"] = str(year)
    form["ctl00$ContentPlaceHolder1$rddYearTo"] = str(year)
    combo_state = json.dumps({
        "logEntries": [], "value": str(year), "text": str(year), "enabled": True,
        "checkedIndices": [], "checkedItemsTextOverflows": False,
    }, separators=(",", ":"))
    form["ctl00_ContentPlaceHolder1_rddYearFrom_ClientState"] = combo_state
    form["ctl00_ContentPlaceHolder1_rddYearTo_ClientState"] = combo_state
    form["ctl00$hfYear"] = str(year)
    button = soup.select_one("input[id*=btnStandard]")
    form[button["name"]] = button.get("value", "Submit Query")
    response = session.post(BASE, data=form, timeout=360)
    response.raise_for_status()
    html = response.text
    (OUT / "_source").mkdir(parents=True, exist_ok=True)
    (OUT / "_source" / f"PublicQueryMap_post_{year}.html").write_text(html, encoding="utf-8")

    def array(name):
        match = re.search(r"var\s+" + re.escape(name) + r"\s*=\s*(\[.*?\]);", html, re.S)
        if not match:
            raise RuntimeError(f"{year}: missing public map array {name}")
        return json.loads(match.group(1))

    ids, latitudes, longitudes = array("info"), array("latitudes"), array("longitudes")
    if not (len(ids) == len(latitudes) == len(longitudes)):
        raise RuntimeError(f"{year}: mismatched map arrays")
    if ids:
        check = requests.post(
            DETAIL,
            json={"crashReportId": str(ids[min(1, len(ids) - 1)]), "accessLevel": "1"},
            timeout=45,
        )
        check.raise_for_status()
        check_text = BeautifulSoup(check.json()["d"][1], "html.parser").get_text(" ", strip=True)
        if not re.search(rf"\b\d{{1,2}}/\d{{1,2}}/{year}\b", check_text):
            raise RuntimeError(f"{year}: server ignored year filter; sample was {check_text[:250]}")
    return list(zip(ids, latitudes, longitudes))


def detail_one(record):
    internal_id, latitude, longitude = record
    error = ""
    for attempt in range(5):
        try:
            response = requests.post(
                DETAIL,
                json={"crashReportId": str(internal_id), "accessLevel": "1"},
                timeout=45,
            )
            response.raise_for_status()
            markup = response.json()["d"][1]
            soup = BeautifulSoup(markup, "html.parser")
            rows = [tr.get_text(" | ", strip=True) for tr in soup.select("tr")]
            report_text = soup.select_one("tr").get_text(" | ", strip=True)
            report = re.search(r"Report:\s*(.*?)\s*\|\s*Injury Level", report_text)
            report_and_agency = report.group(1) if report else ""
            report_number, _, agency = report_and_agency.partition("/")
            injury_img = soup.select_one("img[alt]")
            values = {}
            for index, value in enumerate(rows[:-1]):
                if value in {"Injury Level", "Date/Time", "Location", "Type Of Crash", "MDOT ID"}:
                    values[value] = rows[index + 1].replace("\xa0", " ").replace(" | ", "; ")
            return {
                "public_internal_id": internal_id,
                "mdot_id": values.get("MDOT ID", ""),
                "report_number": report_number,
                "police_department": agency,
                "crash_datetime": " ".join(values.get("Date/Time", "").split()),
                "injury_level": injury_img.get("alt", "") if injury_img else values.get("Injury Level", ""),
                "crash_type": values.get("Type Of Crash", ""),
                "location": values.get("Location", ""),
                "latitude": latitude,
                "longitude": longitude,
                "source": DETAIL,
                "error": "",
            }
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            time.sleep(min(8, 2 ** attempt))
    return {
        "public_internal_id": internal_id,
        "mdot_id": "",
        "report_number": "",
        "police_department": "",
        "crash_datetime": "",
        "injury_level": "",
        "crash_type": "",
        "location": "",
        "latitude": latitude,
        "longitude": longitude,
        "source": DETAIL,
        "error": error,
    }


def download_year(year: int):
    folder = OUT / str(year)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"ME_crash_{year}.csv"
    records = public_map_records(year)
    completed = set()
    if target.exists():
        with target.open("r", newline="", encoding="utf-8-sig") as source:
            completed = {row["public_internal_id"] for row in csv.DictReader(source) if not row.get("error")}
    pending = [record for record in records if str(record[0]) not in completed]
    fields = list(detail_one((0, 0, 0)).keys()) if False else [
        "public_internal_id", "mdot_id", "report_number", "police_department",
        "crash_datetime", "injury_level", "crash_type", "location", "latitude",
        "longitude", "source", "error",
    ]
    mode = "a" if target.exists() and target.stat().st_size else "w"
    print(f"{year}: mapped={len(records):,}, already={len(completed):,}, pending={len(pending):,}", flush=True)
    with target.open(mode, newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        if mode == "w":
            writer.writeheader()
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(detail_one, record) for record in pending]
            for index, future in enumerate(as_completed(futures), 1):
                writer.writerow(future.result())
                if index % 250 == 0:
                    output.flush()
                    print(f"{year}: {index:,}/{len(pending):,}", flush=True)
    print(f"{year}: complete -> {target}", flush=True)


def parse_args():
    parser = argparse.ArgumentParser(description="Download Maine public crash records")
    parser.add_argument("years", type=int, nargs="*", default=list(YEARS))
    parser.add_argument("--year-workers", type=int, default=YEAR_WORKERS)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    selected = tuple(args.years)
    OUT.mkdir(parents=True, exist_ok=True)
    # Two years at a time, with six detail requests per year.  This keeps the
    # public endpoint at a conservative maximum of 12 concurrent requests.
    with ThreadPoolExecutor(max_workers=max(1, args.year_workers)) as year_pool:
        year_futures = {
            year_pool.submit(download_year, selected_year): selected_year
            for selected_year in selected
        }
        for future in as_completed(year_futures):
            selected_year = year_futures[future]
            try:
                future.result()
            except Exception as exc:
                print(f"{selected_year}: FAILED: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
