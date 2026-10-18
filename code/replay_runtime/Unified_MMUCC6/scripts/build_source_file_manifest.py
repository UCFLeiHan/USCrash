#!/usr/bin/env python3
"""Build a deterministic SHA-256 manifest for the preserved source tree."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    root = args.source_root.resolve()
    files = sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.as_posix().lower())
    rows = []
    for index, path in enumerate(files, 1):
        stat = path.stat()
        rows.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "size_bytes": stat.st_size,
                "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "sha256": sha256_file(path),
            }
        )
        if index % 100 == 0:
            print(f"hashed {index}/{len(files)}", flush=True)

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["relative_path", "size_bytes", "modified_utc", "sha256"])
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(root),
        "file_count": len(rows),
        "total_bytes": sum(row["size_bytes"] for row in rows),
        "hash_algorithm": "SHA-256",
        "files": rows,
    }
    args.output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {len(rows)} files / {payload['total_bytes']} bytes", flush=True)


if __name__ == "__main__":
    main()
