"""Download NJDOT statewide crash ZIPs for 2020-2023 and extract to yearly CSVs.

Mirrors States/NJ/2001-2018 layout:
  States/NJ/{year}/Raw/NewJersey{year}{Table}.zip
  States/NJ/{year}/NJ_{table}_{year}.csv
"""
from __future__ import annotations
import os as _uscrash_paths_os

import os
import time
import zipfile
from pathlib import Path

import requests

ROOT = (Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/NJ')
BASES = (
    "https://dot.nj.gov/transportation/refdata/accident",
    "https://www.nj.gov/transportation/refdata/accident",
)
YEARS = (2020, 2021, 2022, 2023)
TABLES = ("Accidents", "Drivers", "Vehicles", "Occupants", "Pedestrians")
MIN_REAL_ZIP_BYTES = 50_000

session = requests.Session()
session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (compatible; USCrash-research/1.0)",
        "Accept": "*/*",
    }
)


def download(url: str, destination: Path) -> None:
    partial = destination.with_suffix(destination.suffix + ".partial")
    last_error: Exception | None = None
    for attempt in range(6):
        try:
            with session.get(url, stream=True, timeout=300) as response:
                response.raise_for_status()
                with partial.open("wb") as handle:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            handle.write(chunk)
            size = partial.stat().st_size
            if size < MIN_REAL_ZIP_BYTES:
                partial.unlink(missing_ok=True)
                raise RuntimeError(f"stub/non-zip response ({size} bytes): {url}")
            with zipfile.ZipFile(partial) as probe:
                if probe.testzip() is not None:
                    raise RuntimeError(f"corrupt zip: {url}")
            os.replace(partial, destination)
            return
        except Exception as exc:  # noqa: BLE001 - retry then raise
            last_error = exc
            partial.unlink(missing_ok=True)
            if attempt == 5:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"failed after retries: {url}") from last_error


def fetch_zip(year: int, table: str, archive: Path) -> None:
    if archive.exists() and archive.stat().st_size >= MIN_REAL_ZIP_BYTES:
        try:
            with zipfile.ZipFile(archive) as probe:
                if probe.testzip() is None:
                    return
        except zipfile.BadZipFile:
            archive.unlink(missing_ok=True)
    errors: list[str] = []
    for base in BASES:
        url = f"{base}/{year}/NewJersey{year}{table}.zip"
        try:
            download(url, archive)
            return
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url} -> {exc}")
    raise RuntimeError(" ; ".join(errors))


def extract_csv(archive: Path, target: Path) -> None:
    if target.exists() and target.stat().st_size > 0:
        return
    with zipfile.ZipFile(archive) as bundle:
        members = [name for name in bundle.namelist() if not name.endswith("/")]
        if not members:
            raise RuntimeError(f"empty archive: {archive}")
        # Statewide packages contain one text member.
        member = members[0]
        with bundle.open(member) as source, target.open("wb") as output:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    readme = ROOT / "README.txt"
    readme.write_text(
        "Official NJDOT statewide crash tables.\n"
        "2001-2018 and 2020-2023 via classic ZIP downloads:\n"
        "https://dot.nj.gov/transportation/refdata/accident/rawdata01-current.shtm\n"
        "2019 and 2024+ are not available as classic ZIPs; use AASHTOWare portal API "
        "(see DOWNLOAD_STATUS.md).\n"
        "The five tables join on year, county code, municipality code, and department "
        "case number.\n",
        encoding="utf-8",
    )

    started = time.time()
    for year in YEARS:
        directory = ROOT / str(year)
        raw = directory / "Raw"
        raw.mkdir(parents=True, exist_ok=True)
        for table in TABLES:
            archive = raw / f"NewJersey{year}{table}.zip"
            target = directory / f"NJ_{table.lower()}_{year}.csv"
            t0 = time.time()
            fetch_zip(year, table, archive)
            extract_csv(archive, target)
            elapsed = time.time() - t0
            print(
                f"{year} {table}: zip={archive.stat().st_size:,} "
                f"csv={target.stat().st_size:,} ({elapsed:.1f}s)",
                flush=True,
            )
    print(f"DONE in {time.time() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
