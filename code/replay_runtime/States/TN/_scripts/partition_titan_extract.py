import os as _uscrash_paths_os
import csv
import io
import json
import zipfile
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

csv.field_size_limit(50_000_000)
ROOT = (Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/TN')
ARCHIVE = ROOT / "Raw" / "TITAN_Extract_CrashData_10_years.zip"
PREFIX = "De-ID 5.11.2026/"


def clean_row(row):
    if row and None in row:
        row.pop(None, None)
    return row


def main():
    master_year = {}
    manifest = []
    with zipfile.ZipFile(ARCHIVE) as z:
        collision_name = PREFIX + "vwCollision.txt"
        with z.open(collision_name) as raw, io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="") as text:
            reader = csv.DictReader(text, delimiter="|")
            fieldnames = reader.fieldnames
            with ExitStack() as stack:
                writers = {}
                counts = Counter()
                for row in reader:
                    row = clean_row(row)
                    master = (row.get("MstrRecNbrTxt") or "").strip()
                    year = (row.get("CollisionDte") or "")[:4]
                    if not master or not year.isdigit():
                        continue
                    master_year[master] = year
                    if year not in writers:
                        out_dir = ROOT / year / "CSV"
                        out_dir.mkdir(parents=True, exist_ok=True)
                        f = stack.enter_context((out_dir / "TITAN_vwCollision.csv").open("w", encoding="utf-8-sig", newline=""))
                        writers[year] = csv.DictWriter(f, fieldnames=fieldnames)
                        writers[year].writeheader()
                    writers[year].writerow(row)
                    counts[year] += 1
                    if sum(counts.values()) % 250000 == 0:
                        print(f"vwCollision: {sum(counts.values()):,}", flush=True)
            for year, count in sorted(counts.items()):
                manifest.append({"table": "vwCollision", "year": year, "rows": count, "unlinked": 0})
        print(f"Indexed {len(master_year):,} collisions", flush=True)

        lookup_dir = ROOT / "Metadata" / "Lookups"
        lookup_dir.mkdir(parents=True, exist_ok=True)
        unlinked_dir = ROOT / "Metadata" / "Unlinked"
        unlinked_dir.mkdir(parents=True, exist_ok=True)
        for name in sorted(n for n in z.namelist() if n.lower().endswith(".txt") and n != collision_name):
            table = Path(name).stem
            with z.open(name) as raw, io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="") as text:
                reader = csv.DictReader(text, delimiter="|")
                fieldnames = reader.fieldnames or []
                if not fieldnames:
                    continue
                if "MstrRecNbrTxt" not in fieldnames and "MstrrecNbrTxt" not in fieldnames:
                    out = lookup_dir / f"{table}.csv"
                    count = 0
                    with out.open("w", encoding="utf-8-sig", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        for row in reader:
                            writer.writerow(clean_row(row)); count += 1
                    manifest.append({"table": table, "year": "LOOKUP", "rows": count, "unlinked": 0})
                    print(f"{table}: lookup {count:,}", flush=True)
                    continue
                key_name = "MstrRecNbrTxt" if "MstrRecNbrTxt" in fieldnames else "MstrrecNbrTxt"
                with ExitStack() as stack:
                    writers = {}
                    counts = Counter()
                    unlinked = 0
                    unlinked_file = stack.enter_context((unlinked_dir / f"{table}.csv").open("w", encoding="utf-8-sig", newline=""))
                    unlinked_writer = csv.DictWriter(unlinked_file, fieldnames=fieldnames)
                    unlinked_writer.writeheader()
                    for row in reader:
                        row = clean_row(row)
                        year = master_year.get((row.get(key_name) or "").strip())
                        if not year:
                            unlinked_writer.writerow(row); unlinked += 1
                            continue
                        if year not in writers:
                            out_dir = ROOT / year / "CSV"
                            out_dir.mkdir(parents=True, exist_ok=True)
                            f = stack.enter_context((out_dir / f"TITAN_{table}.csv").open("w", encoding="utf-8-sig", newline=""))
                            writers[year] = csv.DictWriter(f, fieldnames=fieldnames)
                            writers[year].writeheader()
                        writers[year].writerow(row); counts[year] += 1
                if unlinked == 0:
                    (unlinked_dir / f"{table}.csv").unlink(missing_ok=True)
                for year, count in sorted(counts.items()):
                    manifest.append({"table": table, "year": year, "rows": count, "unlinked": unlinked})
                if not counts:
                    manifest.append({"table": table, "year": "EMPTY", "rows": 0, "unlinked": unlinked})
                print(f"{table}: {sum(counts.values()):,} linked, {unlinked:,} unlinked", flush=True)

    meta = ROOT / "Metadata"
    with (meta / "titan_partition_manifest.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["table", "year", "rows", "unlinked"])
        writer.writeheader(); writer.writerows(manifest)
    (meta / "titan_partition_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
