"""Comprehensive national analysis of the multi-state crash archive.

Produces Arial-font figures + LaTeX-ready tables for:
  - geography (hexbin / centroids / volume / year coverage)
  - schema completeness
  - severity mix vs published FARS/CRSS 2023 national shares
  - hour-of-day profiles where event times exist
  - coordinate fill rates from reservoir samples
"""
from __future__ import annotations
import os as _uscrash_paths_os

import csv
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(_uscrash_paths_os.environ['USCRASH_ROOT'])
STATES = ROOT / "States"
FIELD_MAP = STATES / "field_schemas" / "ALL_states_field_map.csv"
OVERVIEW = ROOT / "manifests/acquisition" / "US_state_data_overview_2026-10-13.csv"
OUT = ROOT / "Paper" / "us_crash_dataset"
FIG = OUT / "figures"
TAB = OUT / "tables"
CACHE = OUT / "cache"
for p in (FIG, TAB, CACHE):
    p.mkdir(parents=True, exist_ok=True)

SAMPLE_PER_STATE = 8000
ATTR_SAMPLE = 12000
RANDOM_SEED = 42
CONUS = dict(lon=(-125.0, -66.0), lat=(24.0, 50.0))

# NHTSA Quick Facts / Traffic Safety Facts 2023 (FARS + CRSS)
# Fatal crashes are FARS counts; injury/PDO are CRSS estimates.
FARS_CRSS_2023 = {
    "year": 2023,
    "fatal_crashes": 37654,
    "injury_crashes": 1697252,
    "pdo_crashes": 4403453,
    "total_police_reported": 6138359,
    "fatalities": 40901,
    "source": "NHTSA Quick Facts 2023 / Traffic Safety Facts 2023 (DOT HS 813720 / 813762)",
}

plt.rcParams.update(
    {
        "font.family": "Arial",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
    }
)


def load_field_map() -> dict[str, dict]:
    with FIELD_MAP.open(encoding="utf-8-sig", newline="") as f:
        return {r["abbr"]: r for r in csv.DictReader(f)}


def count_rows(path: Path) -> int:
    n = 0
    with path.open("rb") as f:
        for _ in f:
            n += 1
    return max(0, n - 1)


def resolve_col(fields: list[str], wanted: str) -> str | None:
    if not wanted:
        return None
    fmap = {c.lower().strip().lstrip("\ufeff"): c for c in fields}
    key = wanted.lower().strip().lstrip("\ufeff")
    if key in fmap:
        return fmap[key]
    for a, b in fmap.items():
        if a == key or a.replace(" ", "") == key.replace(" ", ""):
            return b
    return None


def bucket_severity(raw: str) -> str:
    s = (raw or "").strip().lower()
    if not s or s in {"nan", "none", "null", ".", "-", "unknown", "unk", "u"}:
        return "unknown"
    if any(
        k in s
        for k in (
            "fatal",
            "killed",
            "death",
            "kabco_k",
            "k -",
            "(k)",
            "severity k",
            "fatality",
        )
    ) or s in {"k", "4", "5"}:
        # numeric KABCO often: 4=fatal or 1=fatal depending on agency; keep text-first
        if s in {"4", "5"} and not any(x in s for x in ("fatal", "k")):
            pass
        else:
            if "fatal" in s or "killed" in s or "death" in s or "fatality" in s:
                return "fatal"
            if s in {"k"} or re.search(r"\bk\b", s) or "kabco_k" in s:
                return "fatal"
    if re.search(r"\bfatal", s) or "killed" in s or "fatality" in s:
        return "fatal"
    if s in {"k", "1-fatal", "01"} and "injury" not in s:
        if s == "k":
            return "fatal"
    if any(
        k in s
        for k in (
            "property damage",
            "pdo",
            "no injury",
            "none injured",
            "o -",
            "possible? no",
            "damage only",
            "prop damage",
            "non-injury",
            "noninjury",
        )
    ) or s in {"o", "0", "pdo", "c"}:
        # "c" is ambiguous (possible injury in KABCO); only take explicit PDO tokens above
        if s in {"c"}:
            return "injury"  # KABCO C = possible injury in many states
        if "property" in s or "pdo" in s or "damage only" in s or s in {"o", "0"}:
            return "pdo"
    if any(
        k in s
        for k in (
            "injur",
            "possible",
            "suspected",
            "incapacit",
            "serious",
            "minor",
            "complaint",
            "a -",
            "b -",
            "kabco",
        )
    ) or s in {"a", "b", "c", "1", "2", "3"}:
        return "injury"
    if "fatal" in s:
        return "fatal"
    if "pdo" in s or "property" in s:
        return "pdo"
    return "other"


def parse_hour(raw: str) -> int | None:
    s = (raw or "").strip()
    if not s:
        return None
    # military 0-2359 or 0-23
    if re.fullmatch(r"\d{1,4}", s):
        v = int(s)
        if v <= 23:
            return v
        if v <= 2359:
            return min(23, v // 100)
    # HH:MM / HHMMSS / ISO
    m = re.search(r"(\d{1,2})[:\.](\d{2})", s)
    if m:
        h = int(m.group(1))
        return h if 0 <= h <= 23 else None
    m = re.search(r"[T\s](\d{2})", s)
    if m:
        h = int(m.group(1))
        return h if 0 <= h <= 23 else None
    return None


def sample_attributes(
    path: Path, meta: dict, n: int
) -> dict:
    """Reservoir-sample rows; collect coords, severity buckets, hours."""
    rng = random.Random(RANDOM_SEED ^ (hash(path.name) & 0xFFFFFFFF))
    coords: list[tuple[float, float]] = []
    sev_counts: Counter[str] = Counter()
    hour_counts: Counter[int] = Counter()
    n_rows_seen = 0
    n_coord_ok = 0
    n_sev_ok = 0
    n_hour_ok = 0
    sev_raw_top: Counter[str] = Counter()

    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return {
                "coords": coords,
                "sev": sev_counts,
                "hours": hour_counts,
                "n_rows_seen": 0,
                "n_coord_ok": 0,
                "n_sev_ok": 0,
                "n_hour_ok": 0,
                "sev_raw_top": sev_raw_top,
            }
        fields = [c.lstrip("\ufeff") for c in reader.fieldnames]
        # rebuild row keys safely via DictReader original names
        lat_c = resolve_col(reader.fieldnames, meta.get("latitude") or "")
        lon_c = resolve_col(reader.fieldnames, meta.get("longitude") or "")
        sev_c = resolve_col(reader.fieldnames, meta.get("severity") or "")
        time_c = resolve_col(reader.fieldnames, meta.get("crash_time") or "")
        dt_c = resolve_col(reader.fieldnames, meta.get("crash_datetime") or "")

        kept_idx: list[int] = []
        reservoir: list[dict] = []

        for row in reader:
            n_rows_seen += 1
            # coord fill
            if lat_c and lon_c:
                try:
                    lat = float(str(row.get(lat_c, "")).strip())
                    lon = float(str(row.get(lon_c, "")).strip())
                    if (
                        math.isfinite(lat)
                        and math.isfinite(lon)
                        and -90 <= lat <= 90
                        and -180 <= lon <= 180
                        and not (lat == 0 and lon == 0)
                    ):
                        n_coord_ok += 1
                        # reservoir for map points separately handled below
                        if len(coords) < SAMPLE_PER_STATE:
                            coords.append((lat, lon))
                        else:
                            j = rng.randrange(n_coord_ok)
                            if j < SAMPLE_PER_STATE:
                                coords[j] = (lat, lon)
                except (TypeError, ValueError):
                    pass

            # attribute reservoir
            if len(reservoir) < ATTR_SAMPLE:
                reservoir.append(row)
                kept_idx.append(n_rows_seen)
            else:
                j = rng.randrange(n_rows_seen)
                if j < ATTR_SAMPLE:
                    reservoir[j] = row

        for row in reservoir:
            if sev_c:
                raw = str(row.get(sev_c, "") or "").strip()
                if raw:
                    n_sev_ok += 1
                    sev_raw_top[raw[:80]] += 1
                    sev_counts[bucket_severity(raw)] += 1
            hour = None
            if time_c:
                hour = parse_hour(str(row.get(time_c, "") or ""))
            if hour is None and dt_c:
                hour = parse_hour(str(row.get(dt_c, "") or ""))
            if hour is not None:
                n_hour_ok += 1
                hour_counts[hour] += 1

    return {
        "coords": coords,
        "sev": sev_counts,
        "hours": hour_counts,
        "n_rows_seen": n_rows_seen,
        "n_coord_ok": n_coord_ok,
        "n_sev_ok": n_sev_ok,
        "n_hour_ok": n_hour_ok,
        "sev_raw_top": sev_raw_top,
        "n_attr_sample": len(reservoir) if n_rows_seen else 0,
    }


def count_all_year_crash_rows(st: str) -> tuple[int, int]:
    """Sum rows across preferred annual crash tables; return (rows, n_year_files)."""
    d = STATES / st
    if not d.exists():
        return 0, 0
    total = 0
    nfiles = 0
    for ydir in sorted(p for p in d.iterdir() if p.is_dir() and p.name.isdigit()):
        cands = []
        for p in ydir.glob("*.csv"):
            if p.stat().st_size < 20_000:
                continue
            low = p.name.lower()
            if any(x in low for x in ("vehicle", "person", "involved", "unit", "driver")):
                continue
            if re.search(r"(crash|incident|accident|portal|mtcf|dt4000)", low):
                cands.append(p)
        if not cands:
            continue
        # prefer named crash tables
        primary = max(
            cands,
            key=lambda p: (
                2 if re.search(r"(wy_crash_|_crashes?_|incident_|portal_crash)", p.name, re.I) else 1,
                p.stat().st_size,
            ),
        )
        total += count_rows(primary)
        nfiles += 1
    return total, nfiles


def analyze_state(st: str, meta: dict) -> dict:
    rel = (meta.get("primary_file") or "").strip()
    primary = STATES / rel if rel else None
    out = {
        "abbr": st,
        "state": meta.get("state", st),
        "span": meta.get("span", ""),
        "primary_file": rel,
        "n_rows_primary": 0,
        "n_rows_all_years": 0,
        "n_year_files": 0,
        "n_sampled_coords": 0,
        "coord_fill_primary": None,
        "sev_fatal": 0,
        "sev_injury": 0,
        "sev_pdo": 0,
        "sev_other": 0,
        "sev_unknown": 0,
        "n_sev_labeled": 0,
        "n_hour_labeled": 0,
        "lat_med": None,
        "lon_med": None,
        "has_latlon_map": bool(meta.get("latitude") and meta.get("longitude")),
        "has_severity_map": bool(meta.get("severity")),
        "has_time_map": bool(
            meta.get("crash_time") or meta.get("crash_datetime") or meta.get("crash_date")
        ),
        "ok_coords": False,
        "error": "",
    }
    all_rows, n_yf = count_all_year_crash_rows(st)
    out["n_rows_all_years"] = all_rows
    out["n_year_files"] = n_yf

    if not primary or not primary.exists():
        out["error"] = "no primary"
        return out
    try:
        n_rows = count_rows(primary)
        out["n_rows_primary"] = n_rows
        attr = sample_attributes(primary, meta, ATTR_SAMPLE)
        coords = attr["coords"]
        out["n_sampled_coords"] = len(coords)
        if n_rows > 0 and attr["n_rows_seen"] > 0:
            # coord fill estimated from full scan of primary
            out["coord_fill_primary"] = attr["n_coord_ok"] / attr["n_rows_seen"]
        out["sev_fatal"] = int(attr["sev"].get("fatal", 0))
        out["sev_injury"] = int(attr["sev"].get("injury", 0))
        out["sev_pdo"] = int(attr["sev"].get("pdo", 0))
        out["sev_other"] = int(attr["sev"].get("other", 0))
        out["sev_unknown"] = int(attr["sev"].get("unknown", 0))
        out["n_sev_labeled"] = int(attr["n_sev_ok"])
        out["n_hour_labeled"] = int(attr["n_hour_ok"])
        if coords:
            df = pd.DataFrame(coords, columns=["lat", "lon"])
            out["lat_med"] = float(df["lat"].median())
            out["lon_med"] = float(df["lon"].median())
            out["ok_coords"] = True
            df["abbr"] = st
            df.to_parquet(CACHE / f"{st}_sample.parquet", index=False)
        # persist hour + severity sample details
        (CACHE / f"{st}_attr.json").write_text(
            json.dumps(
                {
                    "sev": dict(attr["sev"]),
                    "hours": {str(k): v for k, v in sorted(attr["hours"].items())},
                    "sev_raw_top": attr["sev_raw_top"].most_common(15),
                    "n_rows_seen": attr["n_rows_seen"],
                    "n_coord_ok": attr["n_coord_ok"],
                    "n_attr_sample": attr["n_attr_sample"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)[:240]
    return out


def load_all_samples(ok_states: list[str]) -> pd.DataFrame:
    frames = []
    for st in ok_states:
        p = CACHE / f"{st}_sample.parquet"
        if p.exists():
            frames.append(pd.read_parquet(p))
    if not frames:
        return pd.DataFrame(columns=["lat", "lon", "abbr"])
    return pd.concat(frames, ignore_index=True)


def plot_national_density(df: pd.DataFrame) -> None:
    conus = df[
        (df["lon"] >= CONUS["lon"][0])
        & (df["lon"] <= CONUS["lon"][1])
        & (df["lat"] >= CONUS["lat"][0])
        & (df["lat"] <= CONUS["lat"][1])
    ]
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    hb = ax.hexbin(
        conus["lon"],
        conus["lat"],
        gridsize=90,
        mincnt=1,
        cmap="YlOrRd",
        linewidths=0.05,
        bins="log",
    )
    cb = fig.colorbar(hb, ax=ax, shrink=0.82, pad=0.02)
    cb.set_label("Sample density (log count)")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("U.S. crash locations (reservoir sample of statewide extracts)")
    ax.set_xlim(CONUS["lon"])
    ax.set_ylim(CONUS["lat"])
    ax.set_aspect("equal", adjustable="box")
    ax.text(
        0.01,
        0.02,
        f"CONUS n={len(conus):,} from {conus['abbr'].nunique()} jurisdictions; coverage QA, not incidence",
        transform=ax.transAxes,
        fontsize=8,
        color="#444",
    )
    fig.tight_layout()
    fig.savefig(FIG / "fig_national_hexbin.pdf")
    fig.savefig(FIG / "fig_national_hexbin.png")
    plt.close(fig)


def plot_state_volume(summary: pd.DataFrame) -> None:
    s = summary[summary["n_rows_primary"] > 0].sort_values("n_rows_primary", ascending=True)
    fig, ax = plt.subplots(figsize=(8.2, 10.8))
    ax.barh(s["abbr"], s["n_rows_primary"], color="#1f4e79")
    ax.set_xlabel("Rows in latest primary crash table")
    ax.set_ylabel("Jurisdiction")
    ax.set_title("Archive size by jurisdiction (latest primary file)")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))
    fig.tight_layout()
    fig.savefig(FIG / "fig_state_volume.pdf")
    fig.savefig(FIG / "fig_state_volume.png")
    plt.close(fig)

    s2 = summary[summary["n_rows_all_years"] > 0].sort_values(
        "n_rows_all_years", ascending=True
    )
    fig, ax = plt.subplots(figsize=(8.2, 10.8))
    ax.barh(s2["abbr"], s2["n_rows_all_years"], color="#2e7d32")
    ax.set_xlabel("Sum of annual crash-table rows (all local years)")
    ax.set_ylabel("Jurisdiction")
    ax.set_title("Multi-year archive volume by jurisdiction")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))
    fig.tight_layout()
    fig.savefig(FIG / "fig_state_volume_allyears.pdf")
    fig.savefig(FIG / "fig_state_volume_allyears.png")
    plt.close(fig)


def plot_centroid_map(summary: pd.DataFrame) -> None:
    s = summary.dropna(subset=["lat_med", "lon_med"])
    fig, ax = plt.subplots(figsize=(10.5, 6.0))
    sc = ax.scatter(
        s["lon_med"],
        s["lat_med"],
        s=np.sqrt(s["n_rows_primary"].clip(lower=1)) / 8.0,
        c=np.log10(s["n_rows_primary"].clip(lower=1)),
        cmap="viridis",
        alpha=0.85,
        edgecolors="white",
        linewidths=0.4,
    )
    for _, r in s.iterrows():
        ax.text(r["lon_med"] + 0.15, r["lat_med"] + 0.15, r["abbr"], fontsize=7, color="#222")
    cb = fig.colorbar(sc, ax=ax, shrink=0.8)
    cb.set_label("log10(primary-table rows)")
    ax.set_xlim(CONUS["lon"])
    ax.set_ylim(CONUS["lat"])
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Sample centroids (marker size ~ sqrt archive volume)")
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout()
    fig.savefig(FIG / "fig_state_centroids.pdf")
    fig.savefig(FIG / "fig_state_centroids.png")
    plt.close(fig)


def plot_year_coverage() -> None:
    rows = list(csv.DictReader(OVERVIEW.open(encoding="utf-8-sig")))
    years = list(range(2000, 2027))
    mat, labels = [], []
    for r in rows:
        if r["有数据"] != "有":
            continue
        yset = {
            int(tok.strip())
            for tok in (r.get("年份明细") or "").split(",")
            if tok.strip().isdigit()
        }
        labels.append(r["缩写"])
        mat.append([1 if y in yset else 0 for y in years])
    arr = np.array(mat)
    order = np.argsort([-np.argmax(row) if row.any() else 999 for row in arr])
    arr = arr[order]
    labels = [labels[i] for i in order]
    fig, ax = plt.subplots(figsize=(11, 9.5))
    ax.imshow(arr, aspect="auto", cmap="Blues", interpolation="nearest", vmin=0, vmax=1)
    ax.set_xticks(range(len(years)))
    ax.set_xticklabels([str(y) if y % 2 == 0 else "" for y in years], fontsize=7)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("Year")
    ax.set_title("Local annual file coverage by jurisdiction")
    fig.tight_layout()
    fig.savefig(FIG / "fig_year_coverage.pdf")
    fig.savefig(FIG / "fig_year_coverage.png")
    plt.close(fig)


def plot_schema_completeness(summary: pd.DataFrame) -> None:
    s = summary[summary["n_rows_primary"] > 0].copy()
    s = s.sort_values("abbr")
    feats = [
        ("has_latlon_map", "Lat/Lon mapped"),
        ("ok_coords", "Coords usable"),
        ("has_severity_map", "Severity mapped"),
        ("n_sev_labeled", "Severity filled"),
        ("has_time_map", "Time/date mapped"),
        ("n_hour_labeled", "Hour parseable"),
    ]
    mat = []
    for _, r in s.iterrows():
        row = []
        for key, _ in feats:
            v = r[key]
            if key.startswith("n_"):
                row.append(1 if int(v or 0) > 0 else 0)
            else:
                row.append(1 if bool(v) else 0)
        mat.append(row)
    arr = np.array(mat)
    fig, ax = plt.subplots(figsize=(8.5, 10.5))
    ax.imshow(arr, aspect="auto", cmap="Greens", vmin=0, vmax=1, interpolation="nearest")
    ax.set_xticks(range(len(feats)))
    ax.set_xticklabels([f[1] for f in feats], rotation=35, ha="right")
    ax.set_yticks(range(len(s)))
    ax.set_yticklabels(s["abbr"].tolist(), fontsize=7)
    ax.set_title("Schema / field usability by jurisdiction")
    fig.tight_layout()
    fig.savefig(FIG / "fig_schema_completeness.pdf")
    fig.savefig(FIG / "fig_schema_completeness.png")
    plt.close(fig)


def plot_coord_fill(summary: pd.DataFrame) -> None:
    s = summary.dropna(subset=["coord_fill_primary"]).sort_values(
        "coord_fill_primary", ascending=True
    )
    fig, ax = plt.subplots(figsize=(8.2, 10.5))
    colors = ["#1b5e20" if v >= 0.95 else "#f9a825" if v >= 0.5 else "#c62828" for v in s["coord_fill_primary"]]
    ax.barh(s["abbr"], s["coord_fill_primary"] * 100, color=colors)
    ax.set_xlabel("Share of primary-table rows with usable coordinates (%)")
    ax.set_title("Coordinate completeness in latest primary crash table")
    ax.set_xlim(0, 105)
    fig.tight_layout()
    fig.savefig(FIG / "fig_coord_fill.pdf")
    fig.savefig(FIG / "fig_coord_fill.png")
    plt.close(fig)


def plot_severity_vs_national(summary: pd.DataFrame) -> dict:
    # Pool attribute samples across states with severity labels
    pool = Counter()
    state_shares = []
    for _, r in summary.iterrows():
        n = r["sev_fatal"] + r["sev_injury"] + r["sev_pdo"]
        if n < 200:
            continue
        pool["fatal"] += int(r["sev_fatal"])
        pool["injury"] += int(r["sev_injury"])
        pool["pdo"] += int(r["sev_pdo"])
        state_shares.append(
            {
                "abbr": r["abbr"],
                "fatal": r["sev_fatal"] / n,
                "injury": r["sev_injury"] / n,
                "pdo": r["sev_pdo"] / n,
                "n": n,
            }
        )
    nat_total = (
        FARS_CRSS_2023["fatal_crashes"]
        + FARS_CRSS_2023["injury_crashes"]
        + FARS_CRSS_2023["pdo_crashes"]
    )
    nat = {
        "fatal": FARS_CRSS_2023["fatal_crashes"] / nat_total,
        "injury": FARS_CRSS_2023["injury_crashes"] / nat_total,
        "pdo": FARS_CRSS_2023["pdo_crashes"] / nat_total,
    }
    pool_n = sum(pool.values()) or 1
    arch = {k: pool[k] / pool_n for k in ("fatal", "injury", "pdo")}

    cats = ["Fatal", "Injury", "PDO"]
    keys = ["fatal", "injury", "pdo"]
    x = np.arange(len(cats))
    w = 0.35
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.bar(x - w / 2, [nat[k] * 100 for k in keys], w, label="FARS/CRSS 2023 national", color="#455a64")
    ax.bar(x + w / 2, [arch[k] * 100 for k in keys], w, label="Local archive (pooled samples)", color="#c62828")
    ax.set_xticks(x)
    ax.set_xticklabels(cats)
    ax.set_ylabel("Share of police-reported crashes (%)")
    ax.set_title("Severity mix: national FARS/CRSS vs local archive samples")
    ax.legend(frameon=False)
    for i, k in enumerate(keys):
        ax.text(i - w / 2, nat[k] * 100 + 1.2, f"{nat[k]*100:.1f}%", ha="center", fontsize=8)
        ax.text(i + w / 2, arch[k] * 100 + 1.2, f"{arch[k]*100:.1f}%", ha="center", fontsize=8)
    ax.set_ylim(0, max(nat["pdo"], arch["pdo"]) * 100 + 12)
    fig.tight_layout()
    fig.savefig(FIG / "fig_severity_vs_fars_crss.pdf")
    fig.savefig(FIG / "fig_severity_vs_fars_crss.png")
    plt.close(fig)

    # stacked bars by state
    if state_shares:
        sdf = pd.DataFrame(state_shares).sort_values("pdo")
        fig, ax = plt.subplots(figsize=(9.5, 10.5))
        y = np.arange(len(sdf))
        ax.barh(y, sdf["pdo"] * 100, color="#90caf9", label="PDO")
        ax.barh(y, sdf["injury"] * 100, left=sdf["pdo"] * 100, color="#ffb74d", label="Injury")
        ax.barh(
            y,
            sdf["fatal"] * 100,
            left=(sdf["pdo"] + sdf["injury"]) * 100,
            color="#e53935",
            label="Fatal",
        )
        ax.axvline(nat["pdo"] * 100, color="#1565c0", ls="--", lw=1, label="CRSS PDO share")
        ax.set_yticks(y)
        ax.set_yticklabels(sdf["abbr"], fontsize=7)
        ax.set_xlabel("Share within severity-labeled sample (%)")
        ax.set_title("State severity composition (sample; coding differs by agency)")
        ax.legend(frameon=False, loc="lower right")
        fig.tight_layout()
        fig.savefig(FIG / "fig_severity_by_state.pdf")
        fig.savefig(FIG / "fig_severity_by_state.png")
        plt.close(fig)

    return {
        "national": nat,
        "archive_pooled": arch,
        "archive_n_labeled": int(pool_n),
        "n_states_in_pool": len(state_shares),
        "fars_crss_2023": FARS_CRSS_2023,
    }


def plot_hour_profiles() -> dict:
    # aggregate hours across states
    total = Counter()
    per_state = {}
    for p in CACHE.glob("*_attr.json"):
        st = p.name.split("_")[0]
        data = json.loads(p.read_text(encoding="utf-8"))
        hours = {int(k): v for k, v in data.get("hours", {}).items()}
        if sum(hours.values()) < 200:
            continue
        per_state[st] = hours
        for h, v in hours.items():
            total[h] += v
    if not total:
        return {"n_states": 0, "n_events": 0}

    xs = list(range(24))
    ys = [total.get(h, 0) for h in xs]
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ax.fill_between(xs, ys, color="#1f4e79", alpha=0.25)
    ax.plot(xs, ys, color="#1f4e79", lw=2)
    ax.set_xticks(xs)
    ax.set_xlabel("Hour of day (local agency coding)")
    ax.set_ylabel("Sampled crash count")
    ax.set_title(f"Pooled hour-of-day profile ({len(per_state)} jurisdictions with parseable times)")
    fig.tight_layout()
    fig.savefig(FIG / "fig_hour_of_day.pdf")
    fig.savefig(FIG / "fig_hour_of_day.png")
    plt.close(fig)

    # heatmap states x hour
    states = sorted(per_state)
    mat = []
    for st in states:
        row = np.array([per_state[st].get(h, 0) for h in xs], dtype=float)
        row = row / row.sum() if row.sum() else row
        mat.append(row)
    arr = np.array(mat)
    fig, ax = plt.subplots(figsize=(10.5, max(6.0, 0.22 * len(states))))
    im = ax.imshow(arr, aspect="auto", cmap="YlOrRd", interpolation="nearest")
    ax.set_xticks(xs)
    ax.set_yticks(range(len(states)))
    ax.set_yticklabels(states, fontsize=7)
    ax.set_xlabel("Hour of day")
    ax.set_title("Normalized hour-of-day share by jurisdiction")
    fig.colorbar(im, ax=ax, shrink=0.7, label="Share of sampled crashes")
    fig.tight_layout()
    fig.savefig(FIG / "fig_hour_heatmap.pdf")
    fig.savefig(FIG / "fig_hour_heatmap.png")
    plt.close(fig)
    return {"n_states": len(per_state), "n_events": int(sum(total.values()))}


def plot_product_comparison(metrics: dict) -> None:
    """Visual comparison of archive role vs FARS / CRSS."""
    labels = ["FARS", "CRSS", "This archive"]
    # qualitative / quantitative facets
    facets = [
        "All severities",
        "Statewide complete",
        "Public lat/lon common",
        "National weights",
        "Fatal census",
    ]
    # 1=yes, 0.5=partial, 0=no
    scores = np.array(
        [
            [0, 0, 0.5, 0, 1],  # FARS
            [1, 0, 0.5, 1, 0],  # CRSS
            [1, 0.7, 0.8, 0, 0],  # archive
        ]
    )
    fig, ax = plt.subplots(figsize=(8.8, 3.8))
    im = ax.imshow(scores, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(facets)))
    ax.set_xticklabels(facets, rotation=20, ha="right")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    for i in range(scores.shape[0]):
        for j in range(scores.shape[1]):
            txt = {1: "Yes", 0.7: "Mostly", 0.8: "Often", 0.5: "Partial", 0: "No"}.get(
                scores[i, j], f"{scores[i, j]:g}"
            )
            ax.text(j, i, txt, ha="center", va="center", fontsize=8, color="#111")
    ax.set_title("How the local archive complements FARS and CRSS")
    fig.colorbar(im, ax=ax, shrink=0.85, label="Capability score")
    fig.tight_layout()
    fig.savefig(FIG / "fig_product_comparison.pdf")
    fig.savefig(FIG / "fig_product_comparison.png")
    plt.close(fig)

    # scale bars: national CRSS total vs our multi-year / primary totals
    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    names = [
        "CRSS/FARS 2023\npolice-reported\n(national estimate)",
        "Local archive\nall-year crash rows\n(sum of annual tables)",
        "Local archive\nlatest primary files\n(sum across states)",
    ]
    vals = [
        FARS_CRSS_2023["total_police_reported"],
        metrics["total_all_year_rows"],
        metrics["total_primary_rows"],
    ]
    colors = ["#455a64", "#2e7d32", "#1f4e79"]
    bars = ax.bar(names, vals, color=colors)
    ax.set_ylabel("Crash records")
    ax.set_title("Scale: national 2023 estimate vs local multi-state holdings")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v * 1.01, f"{v:,.0f}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "fig_scale_vs_national.pdf")
    fig.savefig(FIG / "fig_scale_vs_national.png")
    plt.close(fig)


def write_latex_tables(summary: pd.DataFrame, sev_cmp: dict, metrics: dict) -> None:
    top = summary.nlargest(12, "n_rows_primary")[
        ["abbr", "state", "n_rows_primary", "n_rows_all_years", "n_year_files", "coord_fill_primary"]
    ]
    lines = [
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"Abbr & State & Primary rows & All-year rows & Years & Coord fill \\",
        r"\midrule",
    ]
    for _, r in top.iterrows():
        fill = f"{100*r['coord_fill_primary']:.1f}\\%" if pd.notna(r["coord_fill_primary"]) else "—"
        lines.append(
            f"{r['abbr']} & {r['state']} & {int(r['n_rows_primary']):,} & "
            f"{int(r['n_rows_all_years']):,} & {int(r['n_year_files'])} & {fill} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TAB / "top_states.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    miss = summary[(summary["n_rows_primary"] > 0) & (~summary["ok_coords"])][
        ["abbr", "state", "primary_file", "error"]
    ]
    lines = [
        r"\begin{tabular}{llp{6.5cm}}",
        r"\toprule",
        r"Abbr & State & Note \\",
        r"\midrule",
    ]
    for _, r in miss.iterrows():
        note = (r["error"] or "no usable coords").replace("&", r"\&")
        lines.append(f"{r['abbr']} & {r['state']} & {note} \\\\")
    if miss.empty:
        lines.append(r"\multicolumn{3}{l}{None in current snapshot.} \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TAB / "missing_coords.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    nat = sev_cmp["national"]
    arch = sev_cmp["archive_pooled"]
    lines = [
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Severity & FARS/CRSS 2023 & Local archive sample & Difference (pp) \\",
        r"\midrule",
        f"Fatal & {100*nat['fatal']:.2f}\\% & {100*arch['fatal']:.2f}\\% & "
        f"{100*(arch['fatal']-nat['fatal']):+.2f} \\\\",
        f"Injury & {100*nat['injury']:.2f}\\% & {100*arch['injury']:.2f}\\% & "
        f"{100*(arch['injury']-nat['injury']):+.2f} \\\\",
        f"PDO & {100*nat['pdo']:.2f}\\% & {100*arch['pdo']:.2f}\\% & "
        f"{100*(arch['pdo']-nat['pdo']):+.2f} \\\\",
        r"\bottomrule",
        r"\end{tabular}",
    ]
    (TAB / "severity_vs_national.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # field coverage counts
    n = int((summary["n_rows_primary"] > 0).sum())
    lines = [
        r"\begin{tabular}{lr}",
        r"\toprule",
        r"Attribute & Jurisdictions \\",
        r"\midrule",
        f"Primary crash table present & {n} \\\\",
        f"Lat/lon columns mapped & {int(summary['has_latlon_map'].sum())} \\\\",
        f"Usable coordinate sample & {int(summary['ok_coords'].sum())} \\\\",
        f"Severity column mapped & {int(summary['has_severity_map'].sum())} \\\\",
        f"Severity values observed in sample & {int((summary['n_sev_labeled']>0).sum())} \\\\",
        f"Date/time mapped & {int(summary['has_time_map'].sum())} \\\\",
        f"Hour-of-day parseable in sample & {int((summary['n_hour_labeled']>0).sum())} \\\\",
        r"\bottomrule",
        r"\end{tabular}",
    ]
    (TAB / "field_coverage.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    fmap = load_field_map()
    results = []
    for st, meta in sorted(fmap.items()):
        print(f"analyze {st} ...", flush=True)
        r = analyze_state(st, meta)
        results.append(r)
        print(
            f"  primary={r['n_rows_primary']:,} allyears={r['n_rows_all_years']:,} "
            f"coords={r['n_sampled_coords']} fill={r['coord_fill_primary']} "
            f"sev={r['n_sev_labeled']} hour={r['n_hour_labeled']} err={r['error']}",
            flush=True,
        )

    summary = pd.DataFrame(results)
    summary.to_csv(TAB / "state_geography_summary.csv", index=False)
    summary.to_json(TAB / "state_geography_summary.json", orient="records", indent=2)

    ok = summary[summary["ok_coords"]]["abbr"].tolist()
    samples = load_all_samples(ok)
    samples.to_parquet(CACHE / "all_samples.parquet", index=False)
    print(f"total sample points: {len(samples):,} from {samples['abbr'].nunique()} states")

    plot_national_density(samples)
    plot_state_volume(summary)
    plot_centroid_map(summary)
    plot_year_coverage()
    plot_schema_completeness(summary)
    plot_coord_fill(summary)
    sev_cmp = plot_severity_vs_national(summary)
    hour_meta = plot_hour_profiles()

    metrics = {
        "n_jurisdictions_with_tables": int((summary["n_rows_primary"] > 0).sum()),
        "n_with_coord_samples": int(summary["ok_coords"].sum()),
        "total_primary_rows": int(summary["n_rows_primary"].sum()),
        "total_all_year_rows": int(summary["n_rows_all_years"].sum()),
        "total_sample_points": int(len(samples)),
        "sample_per_state_cap": SAMPLE_PER_STATE,
        "conus_sample_points": int(
            (
                (samples["lon"] >= CONUS["lon"][0])
                & (samples["lon"] <= CONUS["lon"][1])
                & (samples["lat"] >= CONUS["lat"][0])
                & (samples["lat"] <= CONUS["lat"][1])
            ).sum()
        ),
        "n_severity_states": int((summary["n_sev_labeled"] > 0).sum()),
        "n_hour_states": int((summary["n_hour_labeled"] > 0).sum()),
        "hour_profile": hour_meta,
        "severity_comparison": sev_cmp,
        "fars_crss_2023": FARS_CRSS_2023,
        "font": "Arial",
        "includes_WY": "WY" in set(summary["abbr"]),
    }
    plot_product_comparison(metrics)
    write_latex_tables(summary, sev_cmp, metrics)
    (TAB / "paper_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({k: metrics[k] for k in metrics if k != "severity_comparison"}, indent=2))
    print("figures ->", FIG)


if __name__ == "__main__":
    main()
