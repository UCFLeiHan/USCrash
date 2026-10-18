"""Build statewide crash-data overview from local States/ inventory + known notes."""
from __future__ import annotations
import os as _uscrash_paths_os

import csv
import re
from pathlib import Path

ROOT = (Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States')
OUT = (Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'manifests/acquisition/US_state_data_overview_2026-10-13.csv')
COMPACT = (Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'manifests/acquisition/US_state_crash_data_compact_updated_2026-10-12.csv')

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

TIME_KEYS = re.compile(
    r"(date|time|datetime|crash.?date|crshdate|crashtime|hour|minute|"
    r"crsh.?time|crash_dt|_dt\b|military_tm|_tm\b|doi_time|acc_time|acc_date)",
    re.I,
)
COORD_KEYS = re.compile(
    r"(lat|lon|lng|x_coord|y_coord|latitude|longitude|latdecdg|londecdg|"
    r"geo.?point|shape|geometry|northing|easting|utm|gps_)",
    re.I,
)
SEV_KEYS = re.compile(
    r"(sev|inj|fatal|kabco|injury|severity|totinj|ksi|crash_class|most_serious)",
    re.I,
)
TYPE_KEYS = re.compile(
    r"(manner|mnr|collis|crash.?type|crashtype|type.?of.?crash|mannerof|"
    r"first.?harm|frstharm|object.?struck|harmful|acc_type|collsn|"
    r"harm_evnt|fhe_|crash_detail|collision_type|collisionimpact|"
    r"collision.?impact)",
    re.I,
)
PREF = re.compile(
    r"(crash|accident|incident|collision|portal|mtcf|dt4000|event)", re.I
)
SKIP = re.compile(
    r"(person|vehicle|driver|occupant|pedestrian|unit_|_unit|object\.|"
    r"lookup|code.?table|dict|readme|metadata|state\.json|letter|jurisdict|"
    r"crash map\.csv|date_fragment)",
    re.I,
)


def load_compact() -> dict[str, dict]:
    if not COMPACT.exists():
        return {}
    out = {}
    with COMPACT.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            out[row["缩写"].strip()] = row
    return out


def sniff_header(path: Path, max_bytes: int = 1_500_000) -> list[str]:
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
            sample = f.read(max_bytes)
        lines = [ln for ln in sample.splitlines() if ln.strip()]
        if not lines:
            return []
        try:
            dialect = csv.Sniffer().sniff(
                "\n".join(lines[:5]), delimiters=",\t|;"
            )
            delim = dialect.delimiter
        except Exception:
            delim = "," if lines[0].count(",") >= lines[0].count("\t") else "\t"
        fields = next(csv.reader([lines[0]], delimiter=delim))
        return [f.lstrip("\ufeff").strip() for f in fields]
    except Exception:
        return []


def yn(fields: list[str], pat: re.Pattern[str]) -> str:
    if not fields:
        return "无"
    return "有" if pat.search(" | ".join(fields)) else "无"


def collect_year_files(state_dir: Path) -> dict[str, list[Path]]:
    by_year: dict[str, list[Path]] = {}
    if not state_dir.exists():
        return by_year
    for p in state_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".csv", ".txt", ".tsv", ".xlsx", ".xls"}:
            # count zip as presence marker only for year inference later
            continue
        if p.stat().st_size < 5000:
            continue
        # skip probes / partial / raw duplicates / download scratch
        low = str(p).lower()
        if any(
            x in low
            for x in [
                "\\_probe",
                "/_probe",
                "\\_partial",
                "/_partial",
                "\\_source",
                "/_source",
                "\\_download",
                "/_download",
                "\\date_fragments",
                "/date_fragments",
                "\\raw\\extracted",
                "/raw/extracted",
            ]
        ):
            continue
        m = re.search(r"[\\/](\d{4})[\\/]", str(p))
        if not m:
            # also allow State/YYYY_something
            m2 = re.search(r"[\\/](\d{4})[^\\/]*$", p.stem)
            year = m2.group(1) if m2 else None
        else:
            year = m.group(1)
        if not year or not (1990 <= int(year) <= 2030):
            continue
        by_year.setdefault(year, []).append(p)
    # KY daily zips in progress
    for p in state_dir.rglob("*.zip"):
        if p.stat().st_size < 5000:
            continue
        m = re.search(r"[\\/](\d{4})[\\/]", str(p))
        if m:
            by_year.setdefault(m.group(1), [])
    return by_year


def pick_primary(files: list[Path]) -> Path | None:
    if not files:
        return None

    def score(p: Path) -> tuple:
        name = p.name.lower()
        # Prefer cleaned annual crash/incident tables over unit/person/raw crosstabs.
        if re.search(
            r"(md_crashes|az_incident|nj_portal|me_crash|dc_crashes|mi_crashes|"
            r"wy_crash_\d{4}|incident_\d{4}|crashes?_\d{4}|_\d{4}_mtcf|portal_crashes)",
            name,
        ) or re.search(r"(^|[_-])(crashes?|incident|accidents?)([_.-]|$)", name):
            tier = 3
        elif PREF.search(name) and not SKIP.search(name):
            tier = 2
        elif p.suffix.lower() in {".csv", ".txt", ".tsv"} and not SKIP.search(name):
            tier = 1
        elif p.suffix.lower() in {".csv", ".txt", ".tsv"}:
            tier = 0
        else:
            tier = -1
        # Prefer files directly under YYYY/ over nested Raw/
        depth_penalty = len(p.parts)
        return (tier, p.stat().st_size, -depth_penalty)

    ranked = [p for p in files if score(p)[0] >= 0]
    if not ranked:
        return None
    return max(ranked, key=score)


def infer_source(st: str, primary: str, compact_note: str) -> str:
    low = primary.lower()
    overrides = {
        "NJ": "NJDOT classic ZIP (2020–2023) + AASHTOWare portal API (2019, 2024–2026)",
        "ME": "Maine PublicQueryMap + GetReportDetails",
        "WI": "WisDOT Box annual DT4000 ZIP extracts",
        "MI": "MI Open Data ArcGIS (2017–2019) + MTCF export (2020–2025)",
        "KY": "KYTC Crash Data Portal daily ZIP (download in progress)",
        "MD": "MDSP PublicCrash Tableau Crash Map export (2024–2026)",
        "AZ": "ADOT official crash export (Incident/Unit/Person), user-supplied",
        "OK": "KAB/injury subset (not full PDO universe)",
        "NY": "NY Open Data case table (coords omitted in public release)",
        "PA": "PennDOT open crash data",
        "TX": "TxDOT CRIS official extract (application)",
        "CO": "CDOT official annual XLSX → CSV",
        "VA": "VDOT / open crash data",
        "WA": "WSDOT public crash extract",
        "NV": "NDOT official application extract + prior open source (2019)",
        "FL": "SIGNAL4 / Florida crash open data",
        "CA": "SWITRS / CHP open extracts",
        "MA": "MassDOT IMPACT open data",
        "CT": "CTDOT / UConn crash repository",
        "NC": "NCDOT TEAAS / open crash tables",
        "OH": "ODOT TIMS / Figshare mix",
        "OR": "ODOT crash data system extracts",
        "UT": "UDOT Numetric / open crash",
        "MN": "MnDOT open crash",
        "IL": "IDOT open crash",
        "GA": "GDOT GEARS / open crash",
        "AL": "ALDOT CARE / open crash",
        "IA": "Iowa DOT open crash",
        "KS": "KDOT open crash",
        "MO": "MoDOT open crash",
        "MS": "MDOT / eCrash packages",
        "MT": "MDT open crash XLSX",
        "NE": "NDOT open crash",
        "SD": "SDDOT open crash",
        "TN": "TDOT TITAN / open crash",
        "VT": "VTrans ArcGIS open crash",
        "DE": "DelDOT open crash",
        "AR": "ARDOT open crash",
        "AK": "Alaska DOT&PF open crash",
        "ID": "ITD ArcGIS crash services",
        "NM": "NMDOT open crash (2019 only locally)",
        "DC": "Open Data DC / DDOT crash points (MPD COBALT summary)",
        "WY": "WYDOT official crash/vehicle/involved extract (researcher-supplied), 2016–2025",
    }
    if st in overrides:
        return overrides[st]
    if "portal" in low:
        return "AASHTOWare / portal API"
    if "mtcf" in low:
        return "MI MTCF"
    if "arcgis" in low:
        return "ArcGIS open data"
    if "dt4000" in low or "wi_annual" in low or "win_annual" in low:
        return "WisDOT Box annual ZIP"
    if compact_note:
        # first clause before semicolon often has source-ish text
        return "local inventory (see notes)"
    return "local inventory"


# Manual field truth for known quirks (override sniff when needed)
FIELD_OVERRIDES: dict[str, tuple[str, str, str, str, str]] = {
    # time, coord, sev, type, note
    "NY": ("有", "无", "有", "有", "公开 Case 表无经纬度"),
    # MD Crash Map export: severity/collision/coords present; no per-crash clock time
    # (source_date_* are extract filter bounds, not event timestamps).
    "MD": ("无", "有", "有", "有", "MDSP Crash Map：有严重度/碰撞形态/坐标；无逐事故时刻（仅导出筛选起止日）"),
    "AZ": ("有", "有", "有", "有", "ADOT 官方三级表 2020–2025（Incident/Unit/Person）"),
    "OK": ("有", "有", "有", "部分", "KAB 子集，缺 PDO 全量"),
    "PA": ("部分", "有", "有", "有", "公开版有年月/时刻，无具体日号"),
    "OR": ("部分", "有", "有", "有", "小时编码到整点，无分钟"),
    "NC": ("部分", "有", "有", "有", "全事故公开表偏日期；细时间在伤亡层"),
    "OH": ("部分", "有", "有", "有", "TIMS 有月/星期/小时；缺完整日+分钟"),
    "WA": ("有", "有", "有", "部分", "公开版形态字段不完整（ObjectStruck）"),
    "KY": ("待核", "待核", "待核", "待核", "daily ZIP 下载中，尚未合并/验字段"),
    "DC": ("有", "有", "有", "无", "公开点层无 classic 碰撞形态；有行人/自行车/车辆与伤亡计数；Details 表可关联"),
    "WY": ("有", "有", "有", "有", "官方三级表 2016–2025（crash/vehicle/involved）；坐标与军时几乎全覆盖"),
}
# States where local inventory was refreshed after the 2026-10-12 compact sheet.
FRESH_STATES = {"ME", "NJ", "WI", "MI", "KY", "MD", "AZ", "DC", "WY"}


def main() -> None:
    compact = load_compact()
    rows = []
    for st in US:
        d = ROOT / st
        by_year = collect_year_files(d)
        years = sorted(by_year.keys())
        c_row = compact.get(st, {})
        c_status = (c_row.get("状态/覆盖年份") or "").strip()
        c_note = (c_row.get("关键说明") or "").strip()

        if not years:
            # keep known city-only / apply notes
            note = c_note or "本地无逐事故文件"
            rows.append(
                {
                    "州": NAMES.get(st, st),
                    "缩写": st,
                    "有数据": "无",
                    "时间跨度": "无",
                    "覆盖年份数": 0,
                    "年份明细": "无",
                    "数据来源": "无",
                    "事故时间": "无",
                    "事故坐标": "无",
                    "严重程度": "无",
                    "事故形态": "无",
                    "备注": note,
                }
            )
            continue

        yints = [int(y) for y in years]
        span = f"{min(yints)}–{max(yints)}"
        missing = sorted(set(range(min(yints), max(yints) + 1)) - set(yints))
        notes = []
        if missing:
            if len(missing) <= 10:
                notes.append("缺年:" + ",".join(map(str, missing)))
            else:
                notes.append(f"缺年:{len(missing)}个")

        # newest year with a CSV primary
        primary_path = None
        primary_year = None
        for y in sorted(years, reverse=True):
            primary_path = pick_primary(by_year[y])
            if primary_path:
                primary_year = y
                break

        if primary_path:
            fields = sniff_header(primary_path)
            t, c, s, ty = (
                yn(fields, TIME_KEYS),
                yn(fields, COORD_KEYS),
                yn(fields, SEV_KEYS),
                yn(fields, TYPE_KEYS),
            )
            primary_rel = f"{primary_year}/{primary_path.name}"
        else:
            t = c = s = ty = "待核"
            primary_rel = "无CSV(仅ZIP等)"
            notes.append("尚未解压/合并为年度CSV")

        # Prefer previously QA'd compact assessments when present and decisive.
        def map_compact(val: str) -> str | None:
            v = (val or "").strip()
            if not v:
                return None
            if v.startswith("有"):
                return "有"
            if v.startswith("无"):
                return "无"
            if "部分" in v or "/" in v:
                return "部分"
            if v.startswith("待") or v.startswith("预期"):
                return None
            return None

        if c_row and st not in FRESH_STATES:
            for key, slot in [
                ("事故时间", "t"),
                ("经纬度坐标", "c"),
                ("事故严重性", "s"),
                ("事故类型/形态", "ty"),
            ]:
                mapped = map_compact(c_row.get(key, ""))
                if mapped:
                    if slot == "t":
                        t = mapped
                    elif slot == "c":
                        c = mapped
                    elif slot == "s":
                        s = mapped
                    else:
                        ty = mapped

        if st in FIELD_OVERRIDES:
            t, c, s, ty, extra = FIELD_OVERRIDES[st]
            notes.append(extra)

        # freshness notes for recently completed downloads
        if st == "ME":
            notes.append("2020–2026 公开接口已下完")
        if st == "NJ":
            notes.append("2001–2026 已齐（schema 分 classic/portal）")
        if st == "WI":
            notes.append("官方 Box 年度包 2017–2022；2023+ 未发布于 flyer")
        if st == "MI":
            notes.append("2017–2025 本地齐全（ArcGIS+MTCF）")
        if st == "MD":
            notes.append("2024–2026 Crash Map 事故级导出已入库")
        if st == "WY":
            notes.append("2016–2025 官方 crash/vehicle/involved 已标准化入库")

        if c_note and st not in FRESH_STATES:
            # retain useful compact note if not superseded
            if "城市" in c_note or "子集" in c_note or "申请" in c_note or "公开版" in c_note:
                notes.append(c_note)

        source = infer_source(st, primary_rel, c_note)
        rows.append(
            {
                "州": NAMES.get(st, st),
                "缩写": st,
                "有数据": "有",
                "时间跨度": span,
                "覆盖年份数": len(yints),
                "年份明细": ",".join(years),
                "数据来源": source,
                "事故时间": t,
                "事故坐标": c,
                "严重程度": s,
                "事故形态": ty,
                "备注": "；".join(notes) if notes else "",
                "_primary": primary_rel,
            }
        )

    fieldnames = [
        "州",
        "缩写",
        "有数据",
        "时间跨度",
        "覆盖年份数",
        "年份明细",
        "数据来源",
        "事故时间",
        "事故坐标",
        "严重程度",
        "事故形态",
        "备注",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    have = [r for r in rows if r["有数据"] == "有"]
    none = [r for r in rows if r["有数据"] == "无"]
    print(f"wrote {OUT}")
    print(f"有数据={len(have)} 无={len(none)}")
    print("无:", " ".join(r["缩写"] for r in none))
    for r in rows:
        flag = r["有数据"]
        print(
            f"{r['缩写']:2s} {flag} {r['时间跨度']:12s} "
            f"t={r['事故时间']} c={r['事故坐标']} s={r['严重程度']} m={r['事故形态']} | {r['数据来源'][:50]}"
        )


if __name__ == "__main__":
    main()
