from __future__ import annotations

import csv
import gzip
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(r"F:\LH_Research\USCrash\Crash")

STATES = {
    "CA", "CO", "CT", "DE", "FL", "IA", "IL", "MA", "MD", "MN", "MT",
    "NC", "NV", "NY", "OH", "OK", "OR", "PA", "SD", "TN", "TX", "UT",
    "VA", "VT", "WA",
}

CITIES = {
    "Austin", "BatonRouge", "Chicago", "Cincinnati", "Denver", "Indianapolis",
    "Charlotte", "Nashville", "NewYorkCity", "SanFrancisco", "SanJose", "Seattle", "Tempe",
    "WashingtonDC",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def move_directory(name: str, category: str) -> None:
    source = ROOT / name
    destination = ROOT / category / name
    if destination.exists():
        if source.exists():
            raise RuntimeError(f"Both source and destination exist: {name}")
        return
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))


def move_raw_file(path: Path) -> Path:
    raw_dir = path.parent / "Raw"
    raw_dir.mkdir(exist_ok=True)
    destination = raw_dir / path.name
    if destination.exists():
        if sha256(destination) != sha256(path):
            raise RuntimeError(f"Raw-file collision: {destination}")
        path.unlink()
    else:
        shutil.move(str(path), str(destination))
    metadata = path.with_name(path.name + ".metadata.json")
    if metadata.exists():
        metadata_destination = raw_dir / metadata.name
        if metadata_destination.exists():
            if sha256(metadata_destination) != sha256(metadata):
                raise RuntimeError(f"Metadata collision: {metadata_destination}")
            metadata.unlink()
        else:
            shutil.move(str(metadata), str(metadata_destination))
    return destination


def atomic_gunzip(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=destination.name + ".", suffix=".tmp", dir=destination.parent, delete=False
    ) as temp:
        temp_path = Path(temp.name)
        with gzip.open(source, "rb") as compressed:
            shutil.copyfileobj(compressed, temp, length=1024 * 1024)
    if temp_path.stat().st_size == 0:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Empty decompressed output: {source}")
    temp_path.replace(destination)


def unique_csv_target(directory: Path, name: str, archive_stem: str) -> Path:
    target = directory / name
    if not target.exists():
        return target
    return directory / f"{archive_stem}__{name}"


def extract_csv_zip(source: Path) -> list[Path]:
    outputs: list[Path] = []
    with zipfile.ZipFile(source) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"ZIP CRC failure in {source}: {bad}")
        csv_entries = [
            entry for entry in archive.infolist()
            if not entry.is_dir() and Path(entry.filename).suffix.lower() == ".csv"
        ]
        for entry in csv_entries:
            base_name = Path(entry.filename).name
            if source.name.startswith("MnCrash_public_collisions_"):
                base_name = source.with_suffix("").name + ".csv"
            target = unique_csv_target(source.parent, base_name, source.stem)
            if target.exists() and target.stat().st_size == entry.file_size:
                outputs.append(target)
                continue
            with archive.open(entry) as incoming, tempfile.NamedTemporaryFile(
                prefix=target.name + ".", suffix=".tmp", dir=target.parent, delete=False
            ) as temp:
                temp_path = Path(temp.name)
                shutil.copyfileobj(incoming, temp, length=1024 * 1024)
            if temp_path.stat().st_size != entry.file_size:
                temp_path.unlink(missing_ok=True)
                raise RuntimeError(f"ZIP extraction size mismatch: {source}!{entry.filename}")
            temp_path.replace(target)
            outputs.append(target)
    return outputs


def convert_oregon_gdb(source: Path) -> Path:
    import fiona
    import geopandas as gpd

    vsi_path = f"zip://{source}"
    layers = fiona.listlayers(vsi_path)
    if not layers:
        raise RuntimeError(f"No readable layer in {source}")
    frame = gpd.read_file(vsi_path, layer=layers[0])
    if frame.empty:
        raise RuntimeError(f"Empty Oregon layer in {source}")
    target = source.parent / f"{source.stem.removesuffix('.gdb')}.csv"
    with tempfile.NamedTemporaryFile(
        prefix=target.name + ".", suffix=".tmp", dir=target.parent, delete=False
    ) as temp:
        temp_path = Path(temp.name)
    frame.to_csv(temp_path, index=False)
    if temp_path.stat().st_size == 0:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Empty Oregon CSV output: {source}")
    temp_path.replace(target)
    return target


def data_year_directories() -> list[Path]:
    directories: list[Path] = []
    for category in ("States", "Cities", "Nationwide"):
        category_dir = ROOT / category
        if not category_dir.exists():
            continue
        for path in category_dir.rglob("*"):
            if path.is_dir() and (path.name.isdigit() and len(path.name) == 4 or path.name == "_undated"):
                directories.append(path)
    return sorted(directories)


def count_csv_rows(path: Path) -> int:
    rows = 0
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        for _ in reader:
            rows += 1
    return max(rows - 1, 0)


def build_inventory() -> tuple[Path, dict]:
    inventory_path = ROOT / "manifests/acquisition" / "organized_inventory.csv"
    inventory_path.parent.mkdir(exist_ok=True)
    rows: list[dict[str, object]] = []
    for category in ("States", "Cities", "Nationwide"):
        category_dir = ROOT / category
        if not category_dir.exists():
            continue
        for path in sorted(category_dir.rglob("*.csv")):
            if "Raw" in path.parts or "_source" in path.parts:
                continue
            relative = path.relative_to(ROOT)
            jurisdiction = relative.parts[1]
            year = next((part for part in relative.parts if part.isdigit() and len(part) == 4), "undated")
            rows.append({
                "category": category,
                "jurisdiction": jurisdiction,
                "year": year,
                "file": str(relative),
                "bytes": path.stat().st_size,
                "records_excluding_header": count_csv_rows(path),
                "sha256": sha256(path),
            })
    with inventory_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["category"])
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "csv_files": len(rows),
        "csv_bytes": sum(int(row["bytes"]) for row in rows),
        "states": sorted({str(row["jurisdiction"]) for row in rows if row["category"] == "States"}),
        "cities": sorted({str(row["jurisdiction"]) for row in rows if row["category"] == "Cities"}),
        "nationwide": sorted({str(row["jurisdiction"]) for row in rows if row["category"] == "Nationwide"}),
    }
    summary_path = ROOT / "manifests/acquisition" / "organized_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return inventory_path, summary


def main() -> None:
    if not ROOT.is_dir():
        raise RuntimeError(f"Root does not exist: {ROOT}")

    for name in sorted(STATES):
        move_directory(name, "States")
    for name in sorted(CITIES):
        move_directory(name, "Cities")
    move_directory("FARS_Nationwide", "Nationwide")

    converted_gzip = 0
    extracted_zip_csv = 0
    converted_oregon = 0
    retained_oregon_gdb = 0
    for year_dir in data_year_directories():
        for gz_path in sorted(year_dir.glob("*.csv.gz")):
            csv_path = gz_path.with_suffix("")
            if not csv_path.exists():
                atomic_gunzip(gz_path, csv_path)
            move_raw_file(gz_path)
            converted_gzip += 1

        for zip_path in sorted(year_dir.glob("*.zip")):
            outputs = extract_csv_zip(zip_path)
            if outputs:
                extracted_zip_csv += len(outputs)
            elif "States\\OR" in str(zip_path):
                # File geodatabases remain authoritative raw files. Earlier
                # successful conversions are kept; large remaining archives
                # are retained rather than delaying the whole reorganization.
                retained_oregon_gdb += 1
            else:
                raise RuntimeError(f"ZIP has no CSV and no converter: {zip_path}")
            move_raw_file(zip_path)

    inventory_path, summary = build_inventory()
    print(json.dumps({
        "converted_gzip": converted_gzip,
        "extracted_zip_csv": extracted_zip_csv,
        "converted_oregon": converted_oregon,
        "retained_oregon_gdb": retained_oregon_gdb,
        "inventory": str(inventory_path),
        **summary,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
