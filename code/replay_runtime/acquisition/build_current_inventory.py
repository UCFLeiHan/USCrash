from __future__ import annotations
import os as _uscrash_paths_os

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(_uscrash_paths_os.environ['USCRASH_ROOT'])
MANIFEST = ROOT / "manifests/acquisition"
MANIFEST.mkdir(exist_ok=True)

categories = ["States", "Cities", "Nationwide"]
data_suffixes = {".csv", ".zip", ".json", ".xlsx", ".xls", ".shp", ".dbf", ".gpkg"}
inventory = []
summary = defaultdict(lambda: {"years": set(), "csv_files": 0, "raw_files": 0, "bytes": 0})

for category in categories:
    category_dir = ROOT / category
    if not category_dir.exists():
        continue
    for jurisdiction_dir in sorted(p for p in category_dir.iterdir() if p.is_dir()):
        for path in sorted(p for p in jurisdiction_dir.rglob("*") if p.is_file()):
            if path.name.endswith((".part", ".partial")):
                continue
            relative = path.relative_to(ROOT)
            year = next((part for part in relative.parts if len(part) == 4 and part.isdigit()), "")
            in_raw = "Raw" in relative.parts
            suffix = path.suffix.lower()
            if suffix not in data_suffixes and not path.name.endswith(".csv.gz"):
                continue
            kind = "csv.gz" if path.name.endswith(".csv.gz") else suffix.lstrip(".")
            inventory.append({
                "category": category,
                "jurisdiction": jurisdiction_dir.name,
                "year": year,
                "storage": "raw" if in_raw else "analysis",
                "kind": kind,
                "bytes": path.stat().st_size,
                "path": str(relative).replace("\\", "/"),
            })
            key = (category, jurisdiction_dir.name)
            if kind == "csv" and not in_raw:
                summary[key]["csv_files"] += 1
                if year:
                    summary[key]["years"].add(int(year))
            if in_raw:
                summary[key]["raw_files"] += 1
            summary[key]["bytes"] += path.stat().st_size

with (MANIFEST / "current_inventory.csv").open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.DictWriter(handle, fieldnames=["category", "jurisdiction", "year", "storage", "kind", "bytes", "path"])
    writer.writeheader()
    writer.writerows(inventory)

summary_rows = []
for (category, jurisdiction), values in sorted(summary.items()):
    years = sorted(values["years"])
    summary_rows.append({
        "category": category,
        "jurisdiction": jurisdiction,
        "first_year": years[0] if years else "",
        "last_year": years[-1] if years else "",
        "year_count": len(years),
        "years": ",".join(map(str, years)),
        "analysis_csv_files": values["csv_files"],
        "raw_files": values["raw_files"],
        "total_bytes": values["bytes"],
    })

with (MANIFEST / "jurisdiction_summary.csv").open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]) if summary_rows else ["category", "jurisdiction"])
    writer.writeheader()
    writer.writerows(summary_rows)

partial_scope = []
partial_root = ROOT / "_partial"
if partial_root.exists():
    for path in sorted(p for p in partial_root.rglob("*") if p.is_file()):
        partial_scope.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": path.stat().st_size})

report = {
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "root": str(ROOT),
    "inventory_files": len(inventory),
    "jurisdictions": len(summary_rows),
    "categories": {category: sum(1 for row in summary_rows if row["category"] == category) for category in categories},
    "transient_part_files": len(list(ROOT.rglob("*.part"))) + len(list(ROOT.rglob("*.partial"))),
    "partial_scope_files": len(partial_scope),
    "partial_scope": partial_scope,
}
(MANIFEST / "current_inventory_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
