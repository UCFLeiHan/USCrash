from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path


DATA_ROOT = Path(os.environ.get("USCRASH_ROOT", r"F:\LH_Research\USCrash\Crash"))
ROOT = DATA_ROOT / "Unified_MMUCC6"


def main() -> None:
    rows = []
    for path in sorted((ROOT / "qa" / "post_harmonization").glob("*/validation_report.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        rows.append({
            "state": report["state"],
            "files": report["files"],
            "rows": report["rows"],
            "unique_crash_uids": report["unique_crash_uids"],
            "result": report["result"],
            "issue_types": ";".join(sorted(report.get("issues", {}))),
            "validation_report": str(path),
        })

    output_dir = ROOT / "qa"
    csv_path = output_dir / "harmonization_progress.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "states": len(rows),
        "files": sum(int(row["files"]) for row in rows),
        "rows": sum(int(row["rows"]) for row in rows),
        "unique_crash_uids_within_states": sum(int(row["unique_crash_uids"]) for row in rows),
        "passing_states": sum(row["result"] == "PASS" for row in rows),
        "failing_states": sum(row["result"] != "PASS" for row in rows),
        "state_results": rows,
    }
    (output_dir / "harmonization_progress.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
