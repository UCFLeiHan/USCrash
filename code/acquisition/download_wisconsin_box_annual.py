"""Download WisDOT public annual crash extracts listed in WI_Annual_Crash_Data_Flyer.pdf.

Source flyer:
https://wisdot.app.box.com/s/m2zb01vibvqglci1ec59c8jcbr65ud1k
Official index:
https://transportal.cee.wisc.edu/services/crash-data/requests/
"""
from __future__ import annotations

import csv
import json
import time
import zipfile
from pathlib import Path

import requests

ROOT = Path(r"F:\LH_Research\USCrash\Crash\States\WI")
RAW = ROOT / "Raw"
SOURCE = ROOT / "_source"
RAW.mkdir(parents=True, exist_ok=True)
SOURCE.mkdir(parents=True, exist_ok=True)

# Link order from flyer page-1 annotations (doc + Crash 2022..2017 + Accident 2016..1994)
ITEMS = [
    ("documentation", None, "57ojuczi71rffpehyjk39cfn8o6u44rd", "WI_Crash_Data_Documentation.zip"),
    ("crash", 2022, "d9t72ih7tko8w8nhx35t01aqdxppy5n5", "WI_Crash_Annual_2022.zip"),
    ("crash", 2021, "nze1fgpp5uxe0go365u04zq2j3y9qrho", "WI_Crash_Annual_2021.zip"),
    ("crash", 2020, "0ro1y4upd4bwp8xcmhfxxyyunh7xcxnf", "WI_Crash_Annual_2020.zip"),
    ("crash", 2019, "hcc85hy4tzh768v9u4b4ov0nbsge3h7q", "WI_Crash_Annual_2019.zip"),
    ("crash", 2018, "gu1o556fz24zlz8zp0huhhva4mo5nib9", "WI_Crash_Annual_2018.zip"),
    ("crash", 2017, "mpha5y6uqivbwykk76jznb9ojnlcnpsg", "WI_Crash_Annual_2017.zip"),
    ("accident", 2016, "mju99le7mgmffpqdxaa4anhja8a9yb2o", "WI_Accident_Annual_2016.zip"),
    ("accident", 2015, "4rd4sj9a5xjp63gpnbmbw1276vf33nt3", "WI_Accident_Annual_2015.zip"),
    ("accident", 2014, "haw2x1omgizrs11lgcd6oydjz8uujzm7", "WI_Accident_Annual_2014.zip"),
    ("accident", 2013, "le4yhmaouh87osdkztjx5g4cc88s6o3z", "WI_Accident_Annual_2013.zip"),
    ("accident", 2012, "ej1s1qujna5ypv5bf99f7oaemm6sjiwi", "WI_Accident_Annual_2012.zip"),
    ("accident", 2011, "pxgywd8zgavqs8kv05182zxxalg9par6", "WI_Accident_Annual_2011.zip"),
    ("accident", 2010, "r8ik1n6p9livlz9mej5q3h79zpzi7hzr", "WI_Accident_Annual_2010.zip"),
    ("accident", 2009, "a15ss2mjel872mcvlsm926ldulholelb", "WI_Accident_Annual_2009.zip"),
    ("accident", 2008, "lk6yt8pymv3az2d079k3c0rrwp0cdrk3", "WI_Accident_Annual_2008.zip"),
    ("accident", 2007, "7h51e6gyxrzu02gtb9pfy254npqowywb", "WI_Accident_Annual_2007.zip"),
    ("accident", 2006, "7ik5ygjf4ro93bbprqsdl7zptjyfbfin", "WI_Accident_Annual_2006.zip"),
    ("accident", 2005, "vf4t1titb646oirmev4pgzs9vft8h017", "WI_Accident_Annual_2005.zip"),
    ("accident", 2004, "ecsxetrtvowjaqtjyix5s8kcjf95po49", "WI_Accident_Annual_2004.zip"),
    ("accident", 2003, "yvh11uo0gz8wpv0a0sf3k67zayoalk6c", "WI_Accident_Annual_2003.zip"),
    ("accident", 2002, "w5wnqjwccxrrirtf1pwqjfuawi956sjk", "WI_Accident_Annual_2002.zip"),
    ("accident", 2001, "9jt8t3t1rp10eb1rlf57fed79i50816r", "WI_Accident_Annual_2001.zip"),
    ("accident", 2000, "zyrz0dtpmnjme6hboc8xdwgjybmld198", "WI_Accident_Annual_2000.zip"),
    ("accident", 1999, "yfu5np7af4110mdc2ma53145y65521f2", "WI_Accident_Annual_1999.zip"),
    ("accident", 1998, "i5it6d4mf35nq3ug0posue7vzux9grff", "WI_Accident_Annual_1998.zip"),
    ("accident", 1997, "plc6mt3k7mykwmhcljcc1715apfr47cm", "WI_Accident_Annual_1997.zip"),
    ("accident", 1996, "k17evgbsvn3us4rycfjyefcsvnio17s9", "WI_Accident_Annual_1996.zip"),
    ("accident", 1995, "plx7c75u1rmc32leizu7mj9z2844gtds", "WI_Accident_Annual_1995.zip"),
    ("accident", 1994, "emcsg054l76v3ek5wd9qfthxpyykqvos", "WI_Accident_Annual_1994.zip"),
]

# Prefer recent Crash System years first; include documentation.
DOWNLOAD_KEYS = {
    ("documentation", None),
    ("crash", 2022),
    ("crash", 2021),
    ("crash", 2020),
    ("crash", 2019),
    ("crash", 2018),
    ("crash", 2017),
}

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
    }
)


def candidate_urls(shared: str, filename: str) -> list[str]:
    stem = Path(filename).stem
    return [
        f"https://wisdot.app.box.com/shared/static/{shared}.zip",
        f"https://wisdot.box.com/shared/static/{shared}.zip",
        f"https://wisdot.app.box.com/index.php?rm=box_download_shared_file&shared_name={shared}",
        f"https://wisdot.box.com/index.php?rm=box_download_shared_file&shared_name={shared}",
        # sometimes static uses original filename hash differently; keep shared id primary
        f"https://wisdot.app.box.com/shared/static/{shared}",
    ]


def download_one(shared: str, filename: str, dest: Path) -> dict:
    if dest.exists() and dest.stat().st_size > 50_000:
        try:
            with zipfile.ZipFile(dest) as zf:
                if zf.testzip() is None:
                    return {"status": "exists", "path": str(dest), "bytes": dest.stat().st_size}
        except zipfile.BadZipFile:
            dest.unlink(missing_ok=True)

    partial = dest.with_suffix(dest.suffix + ".partial")
    errors: list[str] = []
    for url in candidate_urls(shared, filename):
        try:
            with SESSION.get(url, stream=True, timeout=300, allow_redirects=True) as resp:
                if resp.status_code >= 400:
                    errors.append(f"{url} -> HTTP {resp.status_code}")
                    continue
                ctype = (resp.headers.get("content-type") or "").lower()
                # skip HTML login/interstitial pages
                first = next(resp.iter_content(8192), b"")
                if first[:4] != b"PK\x03\x04" and "zip" not in ctype and "octet" not in ctype:
                    # maybe still zip without magic early; keep going only if large
                    pass
                with partial.open("wb") as out:
                    if first:
                        out.write(first)
                    for chunk in resp.iter_content(1024 * 1024):
                        if chunk:
                            out.write(chunk)
            size = partial.stat().st_size
            if size < 10_000:
                errors.append(f"{url} -> too small ({size})")
                partial.unlink(missing_ok=True)
                continue
            if partial.read_bytes()[:4] != b"PK\x03\x04":
                # not a zip
                head = partial.read_bytes()[:80]
                errors.append(f"{url} -> not zip head={head!r}")
                partial.unlink(missing_ok=True)
                continue
            with zipfile.ZipFile(partial) as zf:
                bad = zf.testzip()
                if bad is not None:
                    raise RuntimeError(f"corrupt member {bad}")
            partial.replace(dest)
            return {"status": "downloaded", "path": str(dest), "bytes": dest.stat().st_size, "url": url}
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url} -> {exc}")
            partial.unlink(missing_ok=True)
            time.sleep(1)
    return {"status": "failed", "file": filename, "errors": errors}


def extract_year(archive: Path, year: int) -> dict:
    out_dir = ROOT / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    members = []
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename).name
            target = out_dir / name
            if not target.exists() or target.stat().st_size == 0:
                with zf.open(info) as src, target.open("wb") as dst:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        dst.write(chunk)
            members.append({"name": name, "bytes": target.stat().st_size})
    return {"year": year, "members": members}


def qa_crash_csv(path: Path, limit: int = 200000) -> dict:
    # lightweight header/field check
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        n = 0
        lat_hits = 0
        for row in reader:
            n += 1
            # common DT4000 / extract names
            lat = None
            lon = None
            for a, b in [
                ("LATITUDE", "LONGITUDE"),
                ("CMAALAT", "CMAALON"),
                ("LAT", "LON"),
                ("Y", "X"),
            ]:
                if a in row and b in row and row[a] not in (None, "", "NA"):
                    lat, lon = row[a], row[b]
                    break
            if lat is not None:
                lat_hits += 1
            if n >= limit:
                break
    interesting = [
        c
        for c in fields
        if any(
            k in c.upper()
            for k in [
                "LAT",
                "LON",
                "DATE",
                "TIME",
                "INJ",
                "SEV",
                "MANNER",
                "MNR",
                "COLL",
                "CRASH",
                "TYPE",
            ]
        )
    ]
    return {
        "file": path.name,
        "rows_sampled": n,
        "latlon_nonempty_sampled": lat_hits,
        "n_fields": len(fields),
        "interesting_fields": interesting[:40],
    }


def main() -> None:
    manifest = []
    for kind, year, shared, filename in ITEMS:
        if (kind, year) not in DOWNLOAD_KEYS:
            continue
        dest = (SOURCE if kind == "documentation" else RAW) / filename
        print(f"GET {filename} ...", flush=True)
        result = download_one(shared, filename, dest)
        print(" ", result.get("status"), result.get("bytes"), flush=True)
        entry = {
            "kind": kind,
            "year": year,
            "shared": shared,
            "filename": filename,
            **result,
        }
        if result.get("status") in {"downloaded", "exists"} and kind == "crash" and year:
            entry["extract"] = extract_year(dest, year)
            # QA first CSV-looking member
            for m in entry["extract"]["members"]:
                p = ROOT / str(year) / m["name"]
                if p.suffix.lower() in {".csv", ".txt"} or "crash" in p.name.lower():
                    try:
                        entry["qa"] = qa_crash_csv(p)
                        print("  QA", entry["qa"], flush=True)
                    except Exception as exc:  # noqa: BLE001
                        entry["qa_error"] = str(exc)
                    break
        manifest.append(entry)

    out = ROOT / "_source" / "box_download_manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
