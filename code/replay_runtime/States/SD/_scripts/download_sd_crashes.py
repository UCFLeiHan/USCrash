import os as _uscrash_paths_os
import csv
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

csv.field_size_limit(10_000_000)

ROOT = (Path(_uscrash_paths_os.environ['USCRASH_ROOT']) / 'States/SD')
BASE = "https://www.safesd.gov/downloads/raw-data/SDARSFiles{year}.zip"


def convert_pipe_file(source: Path, target: Path) -> int:
    rows = 0
    with source.open("r", encoding="utf-8-sig", errors="replace", newline="") as src:
        reader = csv.reader(src, delimiter="|")
        with target.open("w", encoding="utf-8-sig", newline="") as dst:
            writer = csv.writer(dst)
            for row in reader:
                if row and row[-1] == "":
                    row = row[:-1]
                writer.writerow(row)
                rows += 1
    return max(rows - 1, 0)


def main() -> None:
    manifest = []
    for year in range(2011, 2026):
        year_dir = ROOT / str(year)
        raw_dir = year_dir / "Raw"
        extract_dir = raw_dir / "extracted"
        csv_dir = year_dir / "CSV"
        raw_dir.mkdir(parents=True, exist_ok=True)
        csv_dir.mkdir(parents=True, exist_ok=True)
        archive = raw_dir / f"SDARSFiles{year}.zip"
        if not archive.exists() or archive.stat().st_size == 0:
            print(f"Downloading {year}", flush=True)
            with urllib.request.urlopen(BASE.format(year=year), timeout=120) as response:
                with archive.open("wb") as out:
                    shutil.copyfileobj(response, out)
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(extract_dir)
        for txt in sorted(extract_dir.rglob("*.txt")):
            target = csv_dir / f"{txt.stem}.csv"
            count = convert_pipe_file(txt, target)
            manifest.append({
                "year": year,
                "table": txt.stem,
                "rows": count,
                "csv": str(target),
                "source_zip": str(archive),
            })
        print(f"Completed {year}", flush=True)
    meta = ROOT / "Metadata"
    meta.mkdir(exist_ok=True)
    with (meta / "sd_file_manifest.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "table", "rows", "csv", "source_zip"])
        writer.writeheader()
        writer.writerows(manifest)
    (meta / "sd_file_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
