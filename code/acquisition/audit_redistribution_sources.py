"""Collect per-state SOURCE.md URLs and overview notes for redistribution audit."""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(r"F:\LH_Research\USCrash\Crash")
STATES = ROOT / "States"
OV = ROOT / "manifests/acquisition" / "US_state_data_overview_2026-10-13.csv"
OUT = ROOT / "manifests/acquisition" / "redistribution_source_snapshot.csv"

rows = list(csv.DictReader(OV.open(encoding="utf-8-sig")))
out_rows = []
for r in rows:
    st = r["缩写"]
    src = STATES / st / "SOURCE.md"
    text = src.read_text(encoding="utf-8", errors="replace") if src.exists() else ""
    urls = re.findall(r"https?://[^\s\)>\"]+", text)
    out_rows.append(
        {
            "abbr": st,
            "has_data": r["有数据"],
            "span": r["时间跨度"],
            "source": r["数据来源"],
            "notes": r["备注"],
            "n_urls": len(urls),
            "url1": urls[0] if urls else "",
            "url2": urls[1] if len(urls) > 1 else "",
            "source_md_excerpt": " | ".join(
                ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")
            )[:400],
        }
    )

with OUT.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
    w.writeheader()
    w.writerows(out_rows)

for r in out_rows:
    if r["has_data"] != "有":
        continue
    print(f"{r['abbr']:2s} | {r['source'][:70]}")
    if r["url1"]:
        print(f"     {r['url1']}")
print("wrote", OUT)
