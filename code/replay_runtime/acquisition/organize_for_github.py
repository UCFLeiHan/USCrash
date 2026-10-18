"""Organize States/ for GitHub: year folders + SOURCE.md; drop process/zip clutter.

Keep official extract scripts; remove probe/explore helpers.

Usage:
  python organize_for_github.py            # dry-run
  python organize_for_github.py --apply    # execute deletes/writes
"""
from __future__ import annotations
import os as _uscrash_paths_os

import argparse
import csv
import json
import shutil
from pathlib import Path

ROOT = Path(_uscrash_paths_os.environ['USCRASH_ROOT'])
STATES = ROOT / "States"
SCRIPTS = ROOT / "acquisition"
MANIFEST = ROOT / "manifests/acquisition" / "US_state_data_overview_2026-10-13.csv"
REPORT = ROOT / "manifests/acquisition" / "organize_for_github_report.json"

# Do not delete KY daily_zips while download/merge is incomplete.
SKIP_ZIP_DELETE_STATES = {"KY"}

PROCESS_DIR_NAMES = {
    "_probe",
    "_partial",
    "_download",
    "date_fragments",
    "_portal",  # NJ token/log scratch; keep scripts, drop local token cache
}

PROCESS_FILE_SUFFIXES = {".partial", ".log", ".stderr.log"}
PROCESS_FILE_NAMES = {
    "download.log",
    "date_backfill.log",
    "date_backfill.stderr.log",
    "process.stderr.log",
    "maine_download.log",
    "maine_download.err.log",
    "maine_download_2020_2023.log",
    "maine_download_2020_2023.err.log",
    "entity_token.txt",
    "download_portal.log",
}

# Scripts to DELETE (probe / explore / one-off helpers).
DELETE_SCRIPTS = {
    "_audit_state_folders.py",
    "_emit_overview_canvas.py",
    "_summarize_overview.py",
    "_probe_az_wi_ok2.py",
    "_probe_dashboard_deep.py",
    "_probe_dashboard_states.py",
    "_probe_ky_wi_mi_ok.py",
    "_probe_nj_token.py",
    "_probe_nj_token2.py",
    "_probe_remaining_states.py",
    "_probe_wi_fields_only.py",
    "_probe_wi_mi_extract.py",
    "_probe_wi_props_once.py",
    "probe_wi_oneday_2023_01_01.py",
    "probe_co_onbase.py",
    "probe_pa_archives.py",
    "explore_expansion.py",
    "explore_expansion2.py",
    "explore_expansion3.py",
    "explore_expansion4.py",
    "explore_expansion5.py",
    "explore_expansion6.py",
    "explore_expansion7.py",
    "explore_expansion8.py",
    "explore_expansion9.py",
    "explore_expansion10.py",
    "explore_expansion11.py",
    "explore_expansion12.py",
    "explore_expansion13.py",
    "prepare_web_form.py",
    "receipt_mn.py",
    # superseded / city-only scratch not needed for state repo
    "download_dc.py",  # superseded by download_district_of_columbia.py
    "download_phoenix_ksi.py",
    "download_charlotte.py",
    "download_nashville.py",
    "download_indianapolis.py",
    "download_nyc_companions.py",
    "download_denver_official.py",
    "download_albuquerque_nm_2020_2024.py",
}

# Canonical extract scripts referenced in SOURCE.md
EXTRACT_SCRIPTS: dict[str, list[str]] = {
    "AL": ["acquisition/download_alabama_crashes.py"],
    "AR": ["acquisition/download_arkansas_acat.py"],
    "AZ": [],  # user-supplied official package; no public bulk downloader
    "CA": ["acquisition/download_ca_fast.py", "acquisition/download_us_crashes.py"],
    "CO": ["acquisition/download_expansionCO.py", "acquisition/download_us_crashes.py"],
    "CT": ["acquisition/download_us_crashes.py"],
    "DC": ["acquisition/download_district_of_columbia.py"],
    "DE": ["acquisition/download_us_crashes.py"],
    "FL": ["acquisition/download_us_crashes.py", "acquisition/prefill_fdot.py"],
    "GA": ["acquisition/download_georgia_dashboard.py"],
    "IA": ["acquisition/download_us_crashes.py"],
    "ID": ["acquisition/download_us_crashes.py"],
    "IL": ["acquisition/download_us_crashes.py"],
    "KS": ["acquisition/download_us_crashes.py"],
    "KY": ["acquisition/kentucky_crash_downloader.py"],
    "MA": ["acquisition/download_us_crashes.py"],
    "MD": [],  # Tableau Crash Map export (script not yet checked in)
    "ME": [
        "acquisition/maine_crash_public_downloader.py",
        "acquisition/download_maine_public.py",
    ],
    "MI": [
        "acquisition/michigan_crash_downloader.py",
        "acquisition/download_michigan_arcgis.py",
    ],
    "MN": ["acquisition/download_us_crashes.py"],
    "MO": ["acquisition/download_missouri.py"],
    "MS": ["acquisition/download_mississippi.py"],
    "MT": ["acquisition/download_us_crashes.py", "acquisition/split_mt_years.py"],
    "NC": ["acquisition/download_us_crashes.py"],
    "NE": [
        "acquisition/download_nebraska_portal.py",
        "acquisition/download_nebraska_2021_current.py",
    ],
    "NJ": [
        "acquisition/download_new_jersey_2001_2018.py",
        "acquisition/download_new_jersey_2020_2023.py",
        "acquisition/download_new_jersey_portal_api.py",
    ],
    "NM": ["acquisition/download_new_mexico_2019.py"],
    "NV": ["acquisition/download_nevada_arcgis_2019_2023.py"],
    "NY": ["acquisition/download_expansionNY.py", "acquisition/download_us_crashes.py"],
    "OH": ["acquisition/download_us_crashes.py"],
    "OK": ["acquisition/download_ok_remaining.py", "acquisition/download_us_crashes.py"],
    "OR": ["acquisition/download_us_crashes.py"],
    "PA": ["acquisition/download_pa.py"],
    "SD": ["States/SD/acquisition/download_sd_crashes.py"],
    "TN": [
        "States/TN/acquisition/download_tn_arcgis.py",
        "States/TN/acquisition/partition_titan_extract.py",
    ],
    "TX": ["acquisition/download_us_crashes.py"],
    "UT": ["States/UT/acquisition/download_ut_crashes.py"],
    "VA": ["States/VA/acquisition/download_va_crashes.py"],
    "VT": ["States/VT/acquisition/download_vt_crashes.py"],
    "WA": ["acquisition/download_wa.py"],
    "WI": ["acquisition/download_wisconsin_box_annual.py"],
}

OFFICIAL_URLS: dict[str, list[str]] = {
    "AL": ["https://safety.aladata.com/"],
    "AK": ["https://dot.alaska.gov/"],
    "AZ": [
        "https://azdot.gov/planning/traffic-safety/arizona-motor-vehicle-crash-facts",
        "https://azdot.gov/planning/traffic-safety/acis-access-request-form",
    ],
    "AR": ["https://www.ardot.gov/"],
    "CA": ["https://tims.berkeley.edu/", "https://iswitrs.chp.ca.gov/"],
    "CO": ["https://www.codot.gov/safety/traffic-safety"],
    "CT": ["https://www.ctcrash.uconn.edu/"],
    "DC": [
        "https://opendata.dc.gov/datasets/DCGIS::crashes-in-dc",
        "https://opendata.dc.gov/datasets/DCGIS::crash-details-table",
        "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Public_Safety_WebMercator/MapServer/24",
    ],
    "DE": ["https://deldot.gov/"],
    "FL": ["https://signal4analytics.com/", "https://www.flhsmv.gov/"],
    "GA": ["https://www.dot.ga.gov/"],
    "IA": ["https://data.iowadot.gov/"],
    "ID": ["https://iplan.maps.arcgis.com/"],
    "IL": ["https://idot.illinois.gov/"],
    "KS": ["https://www.ksdot.gov/"],
    "KY": [
        "https://crashinformationky.org/AdvancedSearch",
        "https://transportation.ky.gov/",
    ],
    "MA": ["https://apps.impact.dot.state.ma.us/"],
    "MD": [
        "https://analytics.mdsp.org/t/Public/views/PublicCrash2/PublicCrash?:embed=y&:showVizHome=no"
    ],
    "ME": ["https://mdotapps.maine.gov/MaineCrashPublic/"],
    "MI": [
        "https://www.michigan.gov/msp/services/ohsp",
        "https://gisago-qa.mcgi.state.mi.us/arcgis/rest/services/MSP/CrashDashboard/MapServer",
    ],
    "MN": ["https://www.dot.state.mn.us/"],
    "MO": ["https://www.modot.org/"],
    "MS": ["https://mdot.ms.gov/"],
    "MT": ["https://www.mdt.mt.gov/"],
    "NC": ["https://connect.ncdot.gov/"],
    "NE": ["https://dot.nebraska.gov/"],
    "NJ": [
        "https://www.nj.gov/transportation/refdata/accident/",
        "https://njdot.aashtowaresafety.net/njdot-crash-data-dashboard",
    ],
    "NM": ["https://www.dot.nm.gov/"],
    "NV": ["https://www.dot.nv.gov/"],
    "NY": ["https://data.ny.gov/"],
    "OH": ["https://gis.dot.state.oh.us/tims"],
    "OK": ["https://oklahoma.gov/odot.html"],
    "OR": ["https://www.oregon.gov/odot/"],
    "PA": ["https://www.penndot.pa.gov/"],
    "SD": ["https://dot.sd.gov/"],
    "TN": ["https://www.tn.gov/tdot.html"],
    "TX": ["https://www.txdot.gov/data-maps/crash-reports-records.html"],
    "UT": ["https://udot.utah.gov/"],
    "VA": ["https://www.virginiadot.org/"],
    "VT": ["https://vtrans.vermont.gov/"],
    "WA": ["https://www.wsdot.wa.gov/"],
    "WI": [
        "https://wisdot.app.box.com/s/m2zb01vibvqglci1ec59c8jcbr65ud1k",
        "https://transportal.cee.wisc.edu/services/crash-data/requests/",
    ],
    "WY": ["https://www.dot.state.wy.us/home/dot_safety/crash-data.html"],
}


def load_overview() -> dict[str, dict]:
    if not MANIFEST.exists():
        return {}
    with MANIFEST.open(encoding="utf-8-sig", newline="") as f:
        return {r["缩写"]: r for r in csv.DictReader(f)}


def year_dirs(state_dir: Path) -> list[Path]:
    return sorted(
        [p for p in state_dir.iterdir() if p.is_dir() and p.name.isdigit()],
        key=lambda p: p.name,
    )


def has_year_data_tables(ydir: Path) -> bool:
    for p in ydir.glob("*.csv"):
        if p.stat().st_size > 50_000:
            return True
    for p in ydir.glob("*.xlsx"):
        if p.stat().st_size > 50_000:
            return True
    # nested CSV/ under year
    for p in ydir.glob("CSV/*.csv"):
        if p.stat().st_size > 50_000:
            return True
    return False


def collect_deletions(state_dir: Path) -> list[Path]:
    victims: list[Path] = []
    st = state_dir.name

    # process directories anywhere under state
    for p in state_dir.rglob("*"):
        if p.is_dir() and p.name in PROCESS_DIR_NAMES:
            victims.append(p)

    # process files
    for p in state_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.name.lower() in PROCESS_FILE_NAMES or any(
            p.name.lower().endswith(suf) for suf in PROCESS_FILE_SUFFIXES
        ):
            victims.append(p)

    # Raw trees / zips when year tables exist
    for ydir in year_dirs(state_dir):
        if not has_year_data_tables(ydir):
            continue
        raw = ydir / "Raw"
        if raw.exists():
            victims.append(raw)
        # loose zips in year folder
        if st not in SKIP_ZIP_DELETE_STATES:
            for z in ydir.glob("*.zip"):
                victims.append(z)
            daily = ydir / "daily_zips"
            if daily.exists() and st not in SKIP_ZIP_DELETE_STATES:
                victims.append(daily)

    # state-level Raw
    state_raw = state_dir / "Raw"
    if state_raw.exists():
        # keep only if no year tables at all
        if any(has_year_data_tables(y) for y in year_dirs(state_dir)):
            victims.append(state_raw)

    # WI Raw annual zips at States/WI/Raw
    if st == "WI":
        wi_raw = state_dir / "Raw"
        if wi_raw.exists():
            victims.append(wi_raw)
        # probe leftovers
        probe = state_dir / "_probe"
        if probe.exists():
            victims.append(probe)

    # NJ classic zip cache under _probe already covered; also NewJersey*.zip under state root
    if st not in SKIP_ZIP_DELETE_STATES:
        for z in state_dir.glob("*.zip"):
            victims.append(z)

    # dedupe while preserving parents-before-children delete order (dirs last by sorting reverse path length)
    uniq = []
    seen = set()
    for p in victims:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        uniq.append(p)
    return uniq


def list_keep_files(state_dir: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for ydir in year_dirs(state_dir):
        files = []
        for p in sorted(ydir.rglob("*")):
            if not p.is_file():
                continue
            rel = str(p.relative_to(state_dir)).replace("\\", "/")
            low = rel.lower()
            if any(
                x in low
                for x in (
                    "/raw/",
                    "/_probe/",
                    "/_partial/",
                    "/_download/",
                    "/date_fragments/",
                    "/daily_zips/",
                )
            ):
                continue
            if p.suffix.lower() in {".zip", ".partial"}:
                continue
            if p.name.lower().endswith(".log"):
                continue
            files.append(rel)
        out[ydir.name] = files
    return out


def find_field_docs(state_dir: Path) -> list[str]:
    docs = []
    for p in state_dir.rglob("*"):
        if not p.is_file():
            continue
        name = p.name.lower()
        if p.suffix.lower() in {".pdf", ".xls", ".xlsx", ".doc", ".docx"} or any(
            k in name
            for k in ("dict", "dictionary", "layout", "disclaimer", "readme", "attributes")
        ):
            rel = str(p.relative_to(state_dir)).replace("\\", "/")
            if any(x in rel.lower() for x in ("/raw/", "/_probe/", "/_partial/")):
                continue
            docs.append(rel)
    return sorted(docs)[:40]


def write_source_md(state_dir: Path, overview: dict[str, dict], apply: bool) -> str:
    st = state_dir.name
    ov = overview.get(st, {})
    years = [p.name for p in year_dirs(state_dir)]
    keep = list_keep_files(state_dir)
    docs = find_field_docs(state_dir)
    urls = OFFICIAL_URLS.get(st, [])
    scripts = EXTRACT_SCRIPTS.get(st, [])
    # also discover local Scripts
    local_scripts = sorted(
        str(p.relative_to(ROOT)).replace("\\", "/")
        for p in (state_dir / "acquisition").glob("*.py")
    ) if (state_dir / "acquisition").exists() else []
    scripts = list(dict.fromkeys(scripts + local_scripts))

    lines = [
        f"# {ov.get('州', st)} ({st}) — data source",
        "",
        "## Coverage",
        f"- Local years: {', '.join(years) if years else 'none'}",
        f"- Inventory span: {ov.get('时间跨度', 'n/a')}",
        f"- Fields: time={ov.get('事故时间', '?')}, coords={ov.get('事故坐标', '?')}, "
        f"severity={ov.get('严重程度', '?')}, manner={ov.get('事故形态', '?')}",
        "",
        "## Official source",
    ]
    if urls:
        for u in urls:
            lines.append(f"- {u}")
    else:
        lines.append(f"- See inventory note: {ov.get('数据来源', 'n/a')}")
    if ov.get("数据来源"):
        lines.append(f"- Acquisition summary: {ov['数据来源']}")
    if ov.get("备注"):
        lines.append(f"- Notes: {ov['备注']}")

    lines += ["", "## Extract / download scripts (keep)"]
    if scripts:
        for s in scripts:
            lines.append(f"- `{s}`")
    else:
        lines.append(
            "- No checked-in bulk downloader (manual/official package or pending script)."
        )

    lines += ["", "## Field documentation (local)"]
    if docs:
        for d in docs:
            lines.append(f"- `{d}`")
    else:
        lines.append("- No separate dictionary file located; see column headers in annual CSVs.")

    lines += ["", "## Files by year (kept)"]
    for y, files in keep.items():
        lines.append(f"### {y}")
        if not files:
            lines.append("- (empty after cleanup / still downloading)")
            continue
        for f in files[:30]:
            lines.append(f"- `{f}`")
        if len(files) > 30:
            lines.append(f"- … and {len(files) - 30} more")

    lines += [
        "",
        "## Layout convention",
        "- `YYYY/` — annual crash-level tables (and related unit/person tables when provided)",
        "- `Documentation/` or `YYYY/Documentation/` — official field dictionaries / code tables",
        "- `SOURCE.md` — this file",
        "- Intermediate `Raw/` zips, `_probe/`, `_download/`, `date_fragments/` removed when annual tables exist",
        "",
    ]
    text = "\n".join(lines)
    path = state_dir / "SOURCE.md"
    if apply:
        path.write_text(text, encoding="utf-8")
    return text


def delete_path(p: Path, apply: bool, deleted: list[str]) -> None:
    if not p.exists():
        return
    rel = str(p.relative_to(ROOT)).replace("\\", "/")
    if apply:
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        else:
            try:
                p.unlink()
            except OSError:
                pass
    deleted.append(rel)


def consolidate_wi_docs(state_dir: Path, apply: bool, moved: list[str]) -> None:
    """Move flyer + documentation zip contents pointer into Documentation/."""
    doc = state_dir / "Documentation"
    src = state_dir / "_source"
    if not src.exists():
        return
    if apply:
        doc.mkdir(exist_ok=True)
        for p in src.iterdir():
            if p.is_file() and p.suffix.lower() in {".pdf", ".zip", ".json"}:
                dest = doc / p.name
                if not dest.exists():
                    shutil.copy2(p, dest)
                    moved.append(str(dest.relative_to(ROOT)).replace("\\", "/"))
        # remove _source after copy
        shutil.rmtree(src, ignore_errors=True)
    else:
        moved.append(f"(dry-run) would consolidate {src} -> {doc}")


def consolidate_dc_raw(state_dir: Path, apply: bool, moved: list[str]) -> None:
    """DC: keep annual CSVs; drop bulk hub raw if years exist."""
    raw = state_dir / "Raw"
    source = state_dir / "_source"
    doc = state_dir / "Documentation"
    if apply:
        doc.mkdir(exist_ok=True)
        if source.exists():
            for p in source.glob("*.json"):
                shutil.copy2(p, doc / p.name)
                moved.append(str((doc / p.name).relative_to(ROOT)).replace("\\", "/"))
            shutil.rmtree(source, ignore_errors=True)
        if raw.exists() and any(has_year_data_tables(y) for y in year_dirs(state_dir)):
            shutil.rmtree(raw, ignore_errors=True)
            moved.append("deleted States/DC/Raw")


def write_scripts_readme(apply: bool) -> str:
    keep = sorted(
        p.name
        for p in SCRIPTS.glob("*.py")
        if p.name not in DELETE_SCRIPTS
    )
    text = "\n".join(
        [
            "# Extract / utility scripts",
            "",
            "Canonical state downloaders and shared utilities kept for GitHub.",
            "Probe/explore one-offs are removed by `organize_for_github.py`.",
            "",
            "## Kept scripts",
            *[f"- `{n}`" for n in keep],
            "",
            "## Per-state script map",
        ]
        + [
            f"- **{st}**: " + (", ".join(f"`{s}`" for s in scripts) if scripts else "(none / manual)")
            for st, scripts in sorted(EXTRACT_SCRIPTS.items())
        ]
        + ["", "Shared framework: `acquisition/download_us_crashes.py`", ""]
    )
    path = SCRIPTS / "README.md"
    if apply:
        path.write_text(text, encoding="utf-8")
    return text


def write_states_readme(apply: bool) -> None:
    text = """# US state crash data (local archive)

## Layout

```
States/{ST}/
  SOURCE.md                 # official URLs, field docs, extract scripts
  Documentation/            # dictionaries / code tables (when available)
  YYYY/
    *.csv                   # annual crash-level (and related) tables
    Documentation/          # year-specific official docs (when provided)
```

## Convention

- Prefer one crash table per year (plus unit/person when the agency ships them).
- `SOURCE.md` records the official portal/API and the repo script used to obtain the files.
- Intermediate download artifacts (`Raw/` zips, `_probe/`, `_download/`, `date_fragments/`) are removed once annual tables exist.
- Kentucky `daily_zips/` may remain until the annual merge finishes.

## Inventory

See `manifests/acquisition/US_state_data_overview_2026-10-13.csv` for coverage and field completeness.
"""
    if apply:
        (STATES / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="perform deletes/writes")
    ap.add_argument(
        "--states",
        default="",
        help="comma-separated state list; default=all with folders",
    )
    args = ap.parse_args()
    apply = args.apply
    overview = load_overview()

    if args.states.strip():
        wanted = {s.strip().upper() for s in args.states.split(",") if s.strip()}
    else:
        wanted = {
            p.name
            for p in STATES.iterdir()
            if p.is_dir() and not p.name.startswith("_") and (len(p.name) == 2 or p.name == "DC")
        }

    report: dict = {
        "apply": apply,
        "states": {},
        "scripts_deleted": [],
        "notes": [],
    }

    # scripts cleanup
    for name in sorted(DELETE_SCRIPTS):
        p = SCRIPTS / name
        if p.exists():
            delete_path(p, apply, report["scripts_deleted"])

    write_scripts_readme(apply)
    write_states_readme(apply)

    total_deleted = 0
    for st in sorted(wanted):
        state_dir = STATES / st
        if not state_dir.exists():
            continue
        deleted: list[str] = []
        moved: list[str] = []

        if st == "WI":
            consolidate_wi_docs(state_dir, apply, moved)
        if st == "DC":
            consolidate_dc_raw(state_dir, apply, moved)

        victims = collect_deletions(state_dir)
        # delete files before dirs; longest paths first
        for p in sorted(victims, key=lambda x: len(str(x)), reverse=True):
            delete_path(p, apply, deleted)

        # MD: also drop giant utf16 crosstab duplicates under year if MD_crashes exists
        if st == "MD":
            for ydir in year_dirs(state_dir):
                if (ydir / f"MD_crashes_{ydir.name}.csv").exists():
                    for p in ydir.rglob("*.tsv"):
                        delete_path(p, apply, deleted)
                    for p in list(ydir.glob("Crash Map.csv")) + list(
                        (ydir / "_download").glob("Crash Map.csv")
                        if (ydir / "_download").exists()
                        else []
                    ):
                        delete_path(p, apply, deleted)

        # AZ: keep year Documentation/; Raw already queued
        write_source_md(state_dir, overview, apply)

        # Prefer SOURCE.md; if README exists and is older Phoenix-style only, leave AZ README (good)
        report["states"][st] = {
            "deleted_count": len(deleted),
            "deleted_sample": deleted[:25],
            "moved": moved,
            "years": [p.name for p in year_dirs(state_dir)],
        }
        total_deleted += len(deleted)
        print(
            f"{st}: delete~{len(deleted)} years={report['states'][st]['years']} "
            f"{'(applied)' if apply else '(dry-run)'}",
            flush=True,
        )

    report["total_delete_paths"] = total_deleted
    if apply:
        REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("wrote", REPORT)
    else:
        dry = ROOT / "manifests/acquisition" / "organize_for_github_dry_run.json"
        dry.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("wrote", dry)
        print("Re-run with --apply to execute.")


if __name__ == "__main__":
    main()
