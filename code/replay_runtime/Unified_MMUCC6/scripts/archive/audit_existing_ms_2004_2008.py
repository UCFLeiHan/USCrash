import os as _uscrash_paths_os
import csv
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(_uscrash_paths_os.environ['USCRASH_ROOT'])
OUT = ROOT / "Unified_MMUCC6" / "manifests"

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def line_count(path):
    lines = 0
    last = b""
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            lines += block.count(b"\n")
            last = block[-1:] or last
    return max(0, lines - 1 + (1 if last and last != b"\n" else 0))

records = []
for year in range(2004, 2009):
    year_dir = ROOT / "States" / "MS" / str(year)
    source = year_dir / f"mississippi_reportbeam_{year}.zip"
    source_hash = digest(source)
    with zipfile.ZipFile(source) as zf:
        members = zf.namelist()
    files = sorted((year_dir / "CSV").glob("*.csv"))
    if len(files) != 5:
        raise RuntimeError(f"MS {year}: expected 5 CSVs, found {len(files)}")
    for output in files:
        with output.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
            columns = len(next(csv.reader(f)))
        records.append({
            "state": "MS", "year": year, "source_file": str(source),
            "source_member_or_layer": " | ".join(members), "output_file": str(output),
            "rows": line_count(output), "columns": columns,
            "source_sha256": source_hash, "output_sha256": digest(output),
            "status": "created_and_audited",
        })
    print(f"MS {year}: audited {len(files)} CSV files", flush=True)

csv_path = OUT / "source_format_conversion_MS_2004_2008.csv"
json_path = OUT / "source_format_conversion_MS_2004_2008.json"
fields = list(records[0])
with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
    w.writeheader(); w.writerows(records)
json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
print(csv_path)
