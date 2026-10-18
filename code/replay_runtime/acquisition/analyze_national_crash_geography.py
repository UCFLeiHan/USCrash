"""Sample crash coordinates nationwide and produce analysis figures + summary tables."""
from __future__ import annotations
import os as _uscrash_paths_os

import csv
import json
import math
import random
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(_uscrash_paths_os.environ['USCRASH_ROOT'])
STATES = ROOT / "States"
FIELD_MAP = STATES / "field_schemas" / "ALL_states_field_map.csv"
OUT = ROOT / "Paper" / "us_crash_dataset"
FIG = OUT / "figures"
TAB = OUT / "tables"
CACHE = OUT / "cache"
for p in (FIG, TAB, CACHE):
    p.mkdir(parents=True, exist_ok=True)

SAMPLE_PER_STATE = 8000
RANDOM_SEED = 42
CONUS = dict(lon=(-125.0, -66.0), lat=(24.0, 50.0))

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
    }
)


def load_field_map() -> dict[str, dict]:
    with FIELD_MAP.open(encoding="utf-8-sig", newline="") as f:
        return {r["abbr"]: r for r in csv.DictReader(f)}


def count_rows(path: Path) -> int:
    # fast-ish line count
    n = 0
    with path.open("rb") as f:
        for _ in f:
            n += 1
    return max(0, n - 1)


def sample_coords(path: Path, lat_col: str, lon_col: str, n: int) -> pd.DataFrame:
    """Reservoir-sample up to n rows with usable lat/lon."""
    rng = random.Random(RANDOM_SEED ^ hash(path.name) & 0xFFFFFFFF)
    kept: list[tuple[float, float]] = []
    seen = 0
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return pd.DataFrame(columns=["lat", "lon"])
        # fuzzy column resolve
        fields = {c.lower().strip(): c for c in reader.fieldnames}
        lat_c = fields.get(lat_col.lower().strip(), lat_col)
        lon_c = fields.get(lon_col.lower().strip(), lon_col)
        if lat_c not in reader.fieldnames or lon_c not in reader.fieldnames:
            # try common fallbacks
            for a in ("latitude", "lat", "latdecdg", "dec_latitude"):
                if a in fields:
                    lat_c = fields[a]
                    break
            for a in ("longitude", "lon", "lng", "londecdg", "dec_longitude"):
                if a in fields:
                    lon_c = fields[a]
                    break
        for row in reader:
            try:
                lat = float(str(row.get(lat_c, "")).strip())
                lon = float(str(row.get(lon_c, "")).strip())
            except (TypeError, ValueError):
                continue
            if not (math.isfinite(lat) and math.isfinite(lon)):
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            if lat == 0 and lon == 0:
                continue
            seen += 1
            if len(kept) < n:
                kept.append((lat, lon))
            else:
                j = rng.randrange(seen)
                if j < n:
                    kept[j] = (lat, lon)
    return pd.DataFrame(kept, columns=["lat", "lon"])


def resolve_primary(st: str, meta: dict) -> Path | None:
    rel = (meta.get("primary_file") or "").strip()
    if rel:
        p = STATES / rel
        if p.exists():
            return p
    # fallback newest large csv
    d = STATES / st
    if not d.exists():
        return None
    cands = []
    for p in d.rglob("*.csv"):
        if p.stat().st_size < 50_000:
            continue
        low = str(p).lower()
        if "daily_zips" in low or "\\raw\\" in low:
            continue
        cands.append(p)
    if not cands:
        return None
    return max(cands, key=lambda x: x.stat().st_size)


def analyze_state(st: str, meta: dict) -> dict:
    primary = resolve_primary(st, meta)
    out = {
        "abbr": st,
        "state": meta.get("state", st),
        "span": meta.get("span", ""),
        "primary_file": str(primary.relative_to(STATES)).replace("\\", "/") if primary else "",
        "n_rows_file": 0,
        "n_sampled": 0,
        "n_with_coords_sample": 0,
        "lat_med": None,
        "lon_med": None,
        "ok": False,
        "error": "",
    }
    if not primary:
        out["error"] = "no primary"
        return out
    try:
        n_rows = count_rows(primary)
        out["n_rows_file"] = n_rows
        lat_col = meta.get("latitude") or ""
        lon_col = meta.get("longitude") or ""
        if not lat_col or not lon_col:
            out["error"] = "no lat/lon mapping"
            return out
        df = sample_coords(primary, lat_col, lon_col, SAMPLE_PER_STATE)
        out["n_sampled"] = len(df)
        out["n_with_coords_sample"] = len(df)
        if len(df):
            out["lat_med"] = float(df["lat"].median())
            out["lon_med"] = float(df["lon"].median())
            out["ok"] = True
            df["abbr"] = st
            df.to_parquet(CACHE / f"{st}_sample.parquet", index=False)
        else:
            out["error"] = "zero usable coords in sample"
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)[:200]
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
    ax.set_title("U.S. crash locations (reservoir sample of local statewide extracts)")
    ax.set_xlim(CONUS["lon"])
    ax.set_ylim(CONUS["lat"])
    ax.set_aspect("equal", adjustable="box")
    ax.text(
        0.01,
        0.02,
        f"CONUS sample n={len(conus):,} from {conus['abbr'].nunique()} jurisdictions; not a complete national census",
        transform=ax.transAxes,
        fontsize=8,
        color="#444",
    )
    fig.tight_layout()
    fig.savefig(FIG / "fig_national_hexbin.pdf")
    fig.savefig(FIG / "fig_national_hexbin.png")
    plt.close(fig)


def plot_state_choropleth(summary: pd.DataFrame) -> None:
    # Simple bar + optional plotly geo if wanted; matplotlib horizontal bars by count
    s = summary[summary["n_rows_file"] > 0].sort_values("n_rows_file", ascending=True)
    fig, ax = plt.subplots(figsize=(8.2, 10.5))
    ax.barh(s["abbr"], s["n_rows_file"], color="#2f6fed")
    ax.set_xlabel("Rows in primary annual crash table (latest mapped year file)")
    ax.set_ylabel("State / DC")
    ax.set_title("Local archive size by jurisdiction (primary crash table)")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))
    fig.tight_layout()
    fig.savefig(FIG / "fig_state_volume.pdf")
    fig.savefig(FIG / "fig_state_volume.png")
    plt.close(fig)

    # Plotly choropleth for true map (HTML + static via kaleido if available)
    try:
        import plotly.express as px

        pdf = summary[summary["n_rows_file"] > 0].copy()
        fig = px.choropleth(
            pdf,
            locations="abbr",
            locationmode="USA-states",
            color="n_rows_file",
            scope="usa",
            color_continuous_scale="YlOrRd",
            labels={"n_rows_file": "Primary-table rows"},
            title="Local crash-table volume by state (latest mapped primary file)",
        )
        fig.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=520)
        fig.write_html(str(FIG / "fig_state_choropleth.html"))
        try:
            fig.write_image(str(FIG / "fig_state_choropleth.pdf"), scale=2)
            fig.write_image(str(FIG / "fig_state_choropleth.png"), scale=2)
        except Exception:
            # kaleido may be missing; HTML still useful
            pass
    except Exception as exc:  # noqa: BLE001
        print("plotly choropleth skipped:", exc)


def plot_coord_coverage(summary: pd.DataFrame) -> None:
    s = summary.copy()
    s["coord_ok"] = np.where(s["n_with_coords_sample"] > 0, "coords in sample", "no coords / unmapped")
    counts = s["coord_ok"].value_counts()
    fig, ax = plt.subplots(figsize=(5.5, 3.8))
    ax.bar(counts.index, counts.values, color=["#0a7a3e", "#a11"][: len(counts)])
    ax.set_ylabel("Number of jurisdictions")
    ax.set_title("Coordinate usability in sampled primary tables")
    for i, v in enumerate(counts.values):
        ax.text(i, v + 0.2, str(v), ha="center", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "fig_coord_coverage.pdf")
    fig.savefig(FIG / "fig_coord_coverage.png")
    plt.close(fig)


def plot_year_coverage() -> None:
    # from overview CSV
    overview = ROOT / "manifests/acquisition" / "US_state_data_overview_2026-10-13.csv"
    rows = list(csv.DictReader(overview.open(encoding="utf-8-sig")))
    years = list(range(2000, 2027))
    mat = []
    labels = []
    for r in rows:
        if r["有数据"] != "有":
            continue
        yset = set()
        detail = r.get("年份明细") or ""
        for tok in detail.split(","):
            tok = tok.strip()
            if tok.isdigit():
                yset.add(int(tok))
        labels.append(r["缩写"])
        mat.append([1 if y in yset else 0 for y in years])
    arr = np.array(mat)
    # sort by first year then abbr
    order = np.argsort([-np.argmax(row) if row.any() else 999 for row in arr])
    arr = arr[order]
    labels = [labels[i] for i in order]
    fig, ax = plt.subplots(figsize=(11, 9))
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


def plot_centroid_map(summary: pd.DataFrame) -> None:
    s = summary.dropna(subset=["lat_med", "lon_med"])
    fig, ax = plt.subplots(figsize=(10.5, 6.0))
    sc = ax.scatter(
        s["lon_med"],
        s["lat_med"],
        s=np.sqrt(s["n_rows_file"].clip(lower=1)) / 8.0,
        c=np.log10(s["n_rows_file"].clip(lower=1)),
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
    ax.set_title("State sample centroids (marker size ∝ sqrt archive volume)")
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout()
    fig.savefig(FIG / "fig_state_centroids.pdf")
    fig.savefig(FIG / "fig_state_centroids.png")
    plt.close(fig)


def main() -> None:
    fmap = load_field_map()
    results = []
    for st, meta in sorted(fmap.items()):
        print(f"analyze {st} ...", flush=True)
        results.append(analyze_state(st, meta))
        print(" ", results[-1]["n_rows_file"], results[-1]["n_sampled"], results[-1]["error"], flush=True)

    summary = pd.DataFrame(results)
    summary.to_csv(TAB / "state_geography_summary.csv", index=False)
    summary.to_json(TAB / "state_geography_summary.json", orient="records", indent=2)

    ok = summary[summary["ok"]]["abbr"].tolist()
    samples = load_all_samples(ok)
    samples.to_parquet(CACHE / "all_samples.parquet", index=False)
    print(f"total sample points: {len(samples):,} from {samples['abbr'].nunique()} states")

    plot_national_density(samples)
    plot_state_choropleth(summary)
    plot_coord_coverage(summary)
    plot_year_coverage()
    plot_centroid_map(summary)

    # paper-facing metrics
    metrics = {
        "n_jurisdictions_with_tables": int((summary["n_rows_file"] > 0).sum()),
        "n_with_coord_samples": int(summary["ok"].sum()),
        "total_primary_rows": int(summary["n_rows_file"].sum()),
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
    }
    (TAB / "paper_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print("figures ->", FIG)


if __name__ == "__main__":
    main()
