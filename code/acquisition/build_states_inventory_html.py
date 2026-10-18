"""Build States/ inventory HTML + per-state field/attribute maps for unified ingest.

Outputs:
  States/US_crash_data_inventory.html
  States/field_schemas/ALL_states_field_map.csv
  States/field_schemas/{ST}_fields.json
  (refreshes SOURCE.md official links section when missing)
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(r"F:\LH_Research\USCrash\Crash")
STATES = ROOT / "States"
MANIFEST = ROOT / "manifests/acquisition" / "US_state_data_overview_2026-10-13.csv"
SCHEMA_DIR = STATES / "field_schemas"
HTML_OUT = STATES / "US_crash_data_inventory.html"

# Reuse official URLs from organizer when available
try:
    from organize_for_github import EXTRACT_SCRIPTS, OFFICIAL_URLS
except Exception:  # noqa: BLE001
    OFFICIAL_URLS = {}
    EXTRACT_SCRIPTS = {}

US = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
]

NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

# Canonical research fields -> regexes to match local column names (priority order)
# Matching uses normalized names: lowercased, stripped, tabs/spaces collapsed.
CANONICAL = {
    "crash_id": [
        r"^incidentid$", r"^crashid$", r"^crash_id$", r"^collisionid$",
        r"^reportnumber$", r"^report_number$", r"^ccn$", r"^crn$",
        r"^crimeid$", r"^doctnmbr$", r"^casenumber$", r"^crashnum$",
        r"^id_cr$", r"^public_internal_id$", r"^mdot_id$", r"^crash_key$",
        r"^intcrashid$", r"^mstrrecnbrtxt$",
    ],
    "crash_datetime": [
        r"^incidentdatetime$", r"^crashdatetime$", r"^crash_datetime$",
        r"^crashdatetime_iso$", r"^accidentdatetime_iso$", r"^crash date time$",
        r"^crash_date_and_time$", r"^crashdateandtime$", r"^datetime$",
        r"^datetimeofincident$",
    ],
    "crash_date": [
        r"^incidentdate$", r"^crashdate$", r"^crash_date$", r"^crshdate$",
        r"^collisiondate$", r"^collisiondte$",
        r"^dateofcrash$", r"^acc_date$", r"^fromdate$", r"^date_of_accident$",
        r"^reportdate$", r"^doi_date$", r"^datcrashdate$",
    ],
    "crash_time": [
        r"^crashtime$", r"^timeofcrash$", r"^crshtime$", r"^acc_time$",
        r"^collisiontime$", r"^collisiontimetxt$",
        r"^crash_time$", r"^military_tm$", r"^crash_military_tm$", r"^doitime$",
        r"^doi_time$", r"^timestr$", r"^time_of_day$", r"^hour_of_day$",
        r"^crash time description$", r"^intmilitarycrashtime$",
    ],
    "latitude": [
        r"^latitude$", r"^lat$", r"^latdecdg$", r"^cmaalat$", r"^gps_lat$",
        r"^latitude \(generated\)$", r"^__geometry_latitude_wgs84$",
        r"^mpdlatitude$", r"^latdec$", r"^dec_latitude$", r"^dec latitude$",
        r"^decsystemlatitude$", r"^latdecimalnmb$", r"^latitude_wgs84$",
    ],
    "longitude": [
        r"^longitude$", r"^lon$", r"^lng$", r"^long$", r"^londecdg$", r"^cmaalon$",
        r"^gps_long$", r"^longitude \(generated\)$", r"^__geometry_longitude_wgs84$",
        r"^mpdlongitude$", r"^longdec$", r"^dec_longitude$", r"^dec longitude$",
        r"^decsystemlongitude$", r"^longdecimalnmb$", r"^longitude_wgs84$",
    ],
    "severity": [
        r"^injuryseverity$", r"^injury_level$", r"^injsvr$", r"^severity$",
        r"^crash_severity", r"^crash severity description$", r"^severitycode$",
        r"^severity code", r"^crash_sev", r"^most_serious_injury$",
        r"^acc_severity$", r"^csev$", r"^mapseverity$", r"^severityderived$",
        r"^crashsev$", r"^worst_injury", r"^crashseverity$",
    ],
    "manner_collision": [
        r"^collisionmanner$", r"^mnrcoll$", r"^mannerofcollision",
        r"^collision type description$", r"^collisionimpact description$",
        r"^collisionimpact$", r"^collision_type$", r"^collision type$",
        r"^collisiontype$", r"^fhe_collsn", r"^crash type$", r"^crash_type$",
        r"^crashtype$", r"^acc_type$", r"^typeofcollision$",
        r"^type_of_impact$", r"^typeofimpact$", r"^manner_of_collision$",
        r"^mannercollisioncde$",
    ],
    "first_harmful_event": [
        r"^firstharmfulevent$", r"^first harmful event$", r"^frstharm$",
        r"^mostharm$", r"^harm_evnt", r"^first_harmful", r"^objectstruck$",
        r"^first_harmful_event$", r"^firstharmfuleventcde$", r"^firstharmfuleventdesc$",
    ],
}

PREF_FILE = re.compile(
    r"(crash(?:es)?|collision|incident|accident|portal|mtcf|dt4000|crash_schema|mapped_crashes|wy_crash)",
    re.I,
)
SKIP_FILE = re.compile(
    r"(person|vehicle|driver|occupant|pedestrian|unit_|_unit|object|involved)",
    re.I,
)

# Known online field-dictionary / data-dictionary pages (when available)
FIELD_DOC_URLS: dict[str, list[str]] = {
    "AZ": [
        "Local: YYYY/Documentation/list of fields data export.xlsx",
        "Local: YYYY/Documentation/New definition tables.xls",
    ],
    "CA": ["https://tims.berkeley.edu/help/SWITRS.php"],
    "CT": ["https://www.ctcrash.uconn.edu/"],
    "DC": [
        "https://opendata.dc.gov/datasets/DCGIS::crashes-in-dc",
        "https://ddotwiki.atlassian.net/wiki/spaces/GIS0225/pages/2053603429/Crash+Data",
    ],
    "FL": ["https://signal4analytics.com/"],
    "MA": ["https://apps.impact.dot.state.ma.us/"],
    "MD": [
        "https://analytics.mdsp.org/t/Public/views/PublicCrash2/PublicCrash?:embed=y&:showVizHome=no",
        "Local columns documented in States/field_schemas/MD_fields.json",
    ],
    "ME": ["https://mdotapps.maine.gov/MaineCrashPublic/"],
    "NJ": [
        "https://www.nj.gov/transportation/refdata/accident/",
        "https://njdot.aashtowaresafety.net/njdot-crash-data-dashboard",
    ],
    "NY": ["https://data.ny.gov/"],
    "PA": ["https://www.penndot.pa.gov/"],
    "TX": ["https://www.txdot.gov/data-maps/crash-reports-records.html"],
    "VA": ["https://www.virginiadot.org/"],
    "WI": [
        "https://wisdot.app.box.com/s/m2zb01vibvqglci1ec59c8jcbr65ud1k",
        "Local: YYYY/WI_DT4000* / WIN_DT4000* dictionaries",
    ],
    "WY": [
        "https://www.dot.state.wy.us/home/dot_safety/crash-data.html",
        "Local: Documentation/2021 DATA DICTIONARY.pdf",
        "Local: Documentation/Statewide Crashes by Year 2016-2025.pdf",
    ],
}


def load_overview() -> dict[str, dict]:
    if not MANIFEST.exists():
        return {}
    with MANIFEST.open(encoding="utf-8-sig", newline="") as f:
        return {r["缩写"]: r for r in csv.DictReader(f)}


def sniff_header(path: Path) -> list[str]:
    try:
        if path.suffix.lower() == ".xlsx":
            from openpyxl import load_workbook

            wb = load_workbook(path, read_only=True, data_only=True)
            ws = wb["Crashes"] if "Crashes" in wb.sheetnames else wb.worksheets[0]
            values = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
            wb.close()
            return [str(v).strip() if v is not None else "" for v in values]
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
            sample = f.read(2_000_000)
        lines = [ln for ln in sample.splitlines() if ln.strip()]
        if not lines:
            return []
        # Some official exports put a prose disclaimer before the real header.
        # Pick the most delimiter-rich line from the opening block.
        delim_count = lambda ln: max(ln.count(","), ln.count("\t"), ln.count("|"), ln.count(";"))
        richest = max(lines[:20], key=delim_count)
        # Normal files start with their header. Switch only when the first line is
        # plainly prose/metadata and a later line is a real multi-column header.
        header_line = richest if delim_count(lines[0]) <= 2 and delim_count(richest) >= 5 else lines[0]
        try:
            dialect = csv.Sniffer().sniff(header_line, delimiters=",\t|;")
            delim = dialect.delimiter
        except Exception:
            delim = "," if header_line.count(",") >= header_line.count("\t") else "\t"
        fields = next(csv.reader([header_line], delimiter=delim))
        return [f.lstrip("\ufeff").strip() for f in fields]
    except Exception:
        return []


def pick_primary(state_dir: Path) -> Path | None:
    years = sorted(
        [p for p in state_dir.iterdir() if p.is_dir() and p.name.isdigit()],
        reverse=True,
    )
    for ydir in years:
        cands = []
        for p in ydir.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in {".csv", ".txt", ".tsv", ".xlsx"}:
                continue
            if p.stat().st_size < 20_000:
                continue
            low = str(p).lower()
            if any(x in low for x in ("\\raw\\", "/raw/", "daily_zips")):
                continue
            score = 0
            if re.search(r"wy_crash_\d{4}", p.name, re.I):
                score += 200
            if PREF_FILE.search(p.name) and not SKIP_FILE.search(p.name):
                score += 100
            elif not SKIP_FILE.search(p.name):
                score += 10
            score += min(p.stat().st_size // 1_000_000, 50)
            cands.append((score, p))
        if cands:
            return max(cands, key=lambda x: x[0])[1]
    return None


def norm_field(name: str) -> str:
    s = name.replace("\t", " ").replace("\xa0", " ").lstrip("\ufeff").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def match_canonical(fields: list[str]) -> dict[str, str | None]:
    lower_map = {norm_field(f): f for f in fields if f and norm_field(f)}
    # also underscore-collapsed keys
    collapsed = {re.sub(r"[\s_\-]+", "", k): v for k, v in lower_map.items()}
    out: dict[str, str | None] = {}
    for canon, patterns in CANONICAL.items():
        found = None
        for pat in patterns:
            for low, orig in lower_map.items():
                if re.search(pat, low, re.I):
                    found = orig
                    break
            if found:
                break
            # try against collapsed form for patterns without spaces
            if not found:
                for low, orig in collapsed.items():
                    if re.search(pat.replace(r"\s+", "").replace(" ", ""), low, re.I):
                        # only if pattern itself has no spaces / is simple
                        if " " not in pat and r"\s" not in pat:
                            found = orig
                            break
            if found:
                break
        out[canon] = found
    return out


def find_local_docs(state_dir: Path) -> list[str]:
    docs = []
    for p in state_dir.rglob("*"):
        if not p.is_file():
            continue
        name = p.name.lower()
        if p.suffix.lower() in {".pdf", ".xls", ".xlsx", ".doc", ".docx"} or any(
            k in name for k in ("dict", "dictionary", "layout", "attributes", "disclaimer")
        ):
            rel = str(p.relative_to(STATES)).replace("\\", "/")
            if any(x in rel.lower() for x in ("/raw/", "/_probe/", "/daily_zips/")):
                continue
            docs.append(rel)
    return sorted(set(docs))[:25]


def build_state_schema(st: str, overview: dict) -> dict:
    state_dir = STATES / st
    ov = overview.get(st, {})
    urls = list(OFFICIAL_URLS.get(st, []))
    scripts = list(EXTRACT_SCRIPTS.get(st, []))
    doc_urls = list(FIELD_DOC_URLS.get(st, []))
    local_docs = find_local_docs(state_dir) if state_dir.exists() else []

    primary = pick_primary(state_dir) if state_dir.exists() else None
    fields: list[str] = []
    mapping: dict[str, str | None] = {k: None for k in CANONICAL}
    primary_rel = None
    if primary:
        fields = sniff_header(primary)
        mapping = match_canonical(fields)
        primary_rel = str(primary.relative_to(STATES)).replace("\\", "/")

    years = []
    if state_dir.exists():
        years = sorted(
            p.name for p in state_dir.iterdir() if p.is_dir() and p.name.isdigit()
        )

    return {
        "state": NAMES.get(st, st),
        "abbr": st,
        "has_data": ov.get("有数据", "无" if not years else "有"),
        "span": ov.get("时间跨度", "–".join([years[0], years[-1]]) if years else "无"),
        "years": years,
        "source_summary": ov.get("数据来源", "无"),
        "official_urls": urls,
        "field_doc_urls": doc_urls,
        "local_field_docs": local_docs,
        "extract_scripts": scripts,
        "primary_file": primary_rel,
        "n_fields": len(fields),
        "all_fields": fields,
        "canonical_map": mapping,
        "flags": {
            "time": ov.get("事故时间", "无"),
            "coord": ov.get("事故坐标", "无"),
            "severity": ov.get("严重程度", "无"),
            "manner": ov.get("事故形态", "无"),
        },
        "notes": ov.get("备注", ""),
    }


def write_json_schemas(schemas: list[dict]) -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for s in schemas:
        (SCHEMA_DIR / f"{s['abbr']}_fields.json").write_text(
            json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    # flat map CSV for ingest
    path = SCHEMA_DIR / "ALL_states_field_map.csv"
    rows = []
    for s in schemas:
        if s["has_data"] != "有":
            continue
        m = s["canonical_map"]
        rows.append(
            {
                "abbr": s["abbr"],
                "state": s["state"],
                "span": s["span"],
                "primary_file": s["primary_file"] or "",
                "n_fields": s["n_fields"],
                "crash_id": m.get("crash_id") or "",
                "crash_datetime": m.get("crash_datetime") or "",
                "crash_date": m.get("crash_date") or "",
                "crash_time": m.get("crash_time") or "",
                "latitude": m.get("latitude") or "",
                "longitude": m.get("longitude") or "",
                "severity": m.get("severity") or "",
                "manner_collision": m.get("manner_collision") or "",
                "first_harmful_event": m.get("first_harmful_event") or "",
                "official_url_1": (s["official_urls"] or [""])[0],
                "local_field_doc_1": (s["local_field_docs"] or [""])[0],
                "extract_script_1": (s["extract_scripts"] or [""])[0],
            }
        )
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["abbr"])
        w.writeheader()
        w.writerows(rows)


def flag_cell(v: str) -> str:
    cls = {"有": "ok", "无": "no", "部分": "partial", "待核": "partial"}.get(v, "na")
    return f'<span class="flag {cls}">{escape(v)}</span>'


def write_html(schemas: list[dict]) -> None:
    have = [s for s in schemas if s["has_data"] == "有"]
    none = [s for s in schemas if s["has_data"] != "有"]
    mapped = [
        s
        for s in have
        if s["canonical_map"].get("latitude")
        and s["canonical_map"].get("longitude")
        and (
            s["canonical_map"].get("crash_datetime")
            or s["canonical_map"].get("crash_date")
            or s["canonical_map"].get("crash_time")
        )
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows_html = []
    for s in schemas:
        urls = "".join(
            f'<div><a href="{escape(u)}" target="_blank" rel="noopener">{escape(u)}</a></div>'
            for u in (s["official_urls"] or [])
        ) or "<div class='muted'>无</div>"
        docs = ""
        for d in (s["field_doc_urls"] or [])[:3]:
            if d.startswith("http"):
                docs += f'<div><a href="{escape(d)}" target="_blank" rel="noopener">{escape(d)}</a></div>'
            else:
                docs += f"<div class='muted'>{escape(d)}</div>"
        for d in (s["local_field_docs"] or [])[:2]:
            docs += f"<div class='muted'>{escape(d)}</div>"
        if not docs:
            docs = "<div class='muted'>见 field_schemas/{}/_fields.json 表头</div>".format(
                s["abbr"]
            )

        m = s["canonical_map"]
        map_bits = []
        for k in (
            "crash_id",
            "crash_datetime",
            "crash_date",
            "crash_time",
            "latitude",
            "longitude",
            "severity",
            "manner_collision",
        ):
            v = m.get(k)
            map_bits.append(
                f"<code>{k}</code>→<code>{escape(v)}</code>" if v else f"<code>{k}</code>→—"
            )
        map_html = "<br>".join(map_bits)
        schema_link = f"field_schemas/{s['abbr']}_fields.json"
        rows_html.append(
            "<tr>"
            f"<td><strong>{escape(s['abbr'])}</strong><br><span class='muted'>{escape(s['state'])}</span></td>"
            f"<td>{flag_cell(s['has_data'])}</td>"
            f"<td>{escape(s['span'])}</td>"
            f"<td>{urls}</td>"
            f"<td>{flag_cell(s['flags']['time'])}</td>"
            f"<td>{flag_cell(s['flags']['coord'])}</td>"
            f"<td>{flag_cell(s['flags']['severity'])}</td>"
            f"<td>{flag_cell(s['flags']['manner'])}</td>"
            f"<td class='map'>{map_html}</td>"
            f"<td>{docs}<div><a href='{schema_link}'>{s['abbr']}_fields.json</a>"
            f" <span class='muted'>({s['n_fields']} cols)</span></div></td>"
            "</tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>US State Crash Data Inventory</title>
<style>
  :root {{
    --bg: #f7f7f5; --card: #fff; --text: #1a1a1a; --muted: #666;
    --line: #e5e5e2; --ok: #0a7a3e; --no: #a11; --partial: #9a6b00;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: "Segoe UI", system-ui, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.45;
  }}
  header {{
    padding: 28px 32px 18px; border-bottom: 1px solid var(--line); background: var(--card);
  }}
  h1 {{ margin: 0 0 8px; font-size: 22px; font-weight: 650; }}
  .sub {{ color: var(--muted); font-size: 14px; max-width: 920px; }}
  .stats {{
    display: flex; gap: 16px; flex-wrap: wrap; padding: 16px 32px;
  }}
  .stat {{
    background: var(--card); border: 1px solid var(--line); border-radius: 8px;
    padding: 12px 16px; min-width: 120px;
  }}
  .stat b {{ display: block; font-size: 22px; }}
  .stat span {{ color: var(--muted); font-size: 12px; }}
  main {{ padding: 8px 24px 40px; }}
  table {{
    width: 100%; border-collapse: collapse; background: var(--card);
    border: 1px solid var(--line); font-size: 12.5px;
  }}
  th, td {{
    border-bottom: 1px solid var(--line); padding: 8px 10px; vertical-align: top; text-align: left;
  }}
  th {{
    position: sticky; top: 0; background: #f0f0ec; z-index: 1; font-weight: 600;
  }}
  tr:hover td {{ background: #fafaf8; }}
  a {{ color: #0b57d0; text-decoration: none; word-break: break-all; }}
  a:hover {{ text-decoration: underline; }}
  .muted {{ color: var(--muted); font-size: 11.5px; }}
  .flag {{ font-weight: 600; }}
  .flag.ok {{ color: var(--ok); }}
  .flag.no {{ color: var(--no); }}
  .flag.partial {{ color: var(--partial); }}
  .map code {{ font-size: 11px; }}
  footer {{ padding: 12px 32px 32px; color: var(--muted); font-size: 12px; }}
</style>
</head>
<body>
<header>
  <h1>美国各州车祸数据总览（入库用）</h1>
  <p class="sub">
    基于本地 <code>States/</code> 实测文件生成。含官方来源链接、核心字段映射（统一入库用）、
    以及各州完整表头 JSON（<code>field_schemas/</code>）。生成时间：{escape(now)}。
  </p>
</header>
<section class="stats">
  <div class="stat"><b>{len(have)}</b><span>有本地数据</span></div>
  <div class="stat"><b>{len(none)}</b><span>无本地数据</span></div>
  <div class="stat"><b>{len(mapped)}</b><span>已自动映射坐标+时间列</span></div>
  <div class="stat"><b>{len(schemas)}</b><span>司法辖区</span></div>
</section>
<main>
<table>
  <thead>
    <tr>
      <th>州</th><th>有数据</th><th>时间跨度</th><th>官方来源链接</th>
      <th>时间</th><th>坐标</th><th>严重度</th><th>形态</th>
      <th>统一字段映射（本地列名）</th><th>属性表 / 数据字典</th>
    </tr>
  </thead>
  <tbody>
    {''.join(rows_html)}
  </tbody>
</table>
</main>
<footer>
  配套文件：
  <code>field_schemas/ALL_states_field_map.csv</code>、
  <code>field_schemas/{{ST}}_fields.json</code>（含全部列名）、
  各州 <code>SOURCE.md</code>。
  重新生成：<code>python code/acquisition/build_states_inventory_html.py</code>
</footer>
</body>
</html>
"""
    HTML_OUT.write_text(html, encoding="utf-8")


def main() -> None:
    overview = load_overview()
    schemas = [build_state_schema(st, overview) for st in US]
    write_json_schemas(schemas)
    write_html(schemas)
    # summary sidecar
    (SCHEMA_DIR / "README.md").write_text(
        """# Field schemas for unified ingest

- `ALL_states_field_map.csv` — one row per state with canonical→local column mapping
- `{ST}_fields.json` — full header list, official URLs, local dictionary files, extract scripts

Canonical targets: `crash_id`, `crash_datetime` / `crash_date`+`crash_time`, `latitude`, `longitude`, `severity`, `manner_collision`, `first_harmful_event`.

Open `../US_crash_data_inventory.html` for the browsable inventory.
""",
        encoding="utf-8",
    )
    have = sum(1 for s in schemas if s["has_data"] == "有")
    with_map = sum(
        1
        for s in schemas
        if s["has_data"] == "有"
        and s["canonical_map"].get("latitude")
        and s["canonical_map"].get("longitude")
        and (
            s["canonical_map"].get("crash_datetime")
            or s["canonical_map"].get("crash_date")
            or s["canonical_map"].get("crash_time")
        )
    )
    print(f"wrote {HTML_OUT}")
    print(f"wrote {SCHEMA_DIR} ({have} states with data, {with_map} with lat+time map)")
    # print a few key mappings
    for st in ["AZ", "MD", "WI", "NJ", "DC", "ME", "MI", "TX", "CA"]:
        s = next(x for x in schemas if x["abbr"] == st)
        m = s["canonical_map"]
        print(
            f"{st}: id={m.get('crash_id')} dt={m.get('crash_datetime') or m.get('crash_date')} "
            f"lat={m.get('latitude')} sev={m.get('severity')} manner={m.get('manner_collision')} "
            f"n={s['n_fields']} docs={len(s['local_field_docs'])}"
        )


if __name__ == "__main__":
    main()
