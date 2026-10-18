from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DATA_ROOT = Path(os.environ.get("USCRASH_ROOT", r"F:\LH_Research\USCrash\Crash"))
ROOT = DATA_ROOT / "Unified_MMUCC6"
SEVERITY = {"K", "A", "B", "C", "O", "U", ""}
MANNER = {"0", "1", "2", "6", "7", "8", "9", "10", "11", "99", ""}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    args = ap.parse_args(); state = args.state.upper()
    state_config = json.loads((ROOT / "config" / "states" / f"{state}.json").read_text(encoding="utf-8"))
    bounds = state_config.get("coordinate_bounds", [-125.0, 41.0, -116.0, 47.0])
    allow_date_year_mismatch = bool(state_config.get("allow_date_year_mismatch", False))
    allow_missing_crash_date = bool(state_config.get("allow_missing_crash_date", False))
    allow_fatality_severity_mismatch = bool(state_config.get("allow_fatality_severity_mismatch", False))
    data_dir = ROOT / "data" / "crash" / state
    qa_dir = ROOT / "qa" / "post_harmonization" / state
    summary_path = qa_dir / "harmonization_summary.csv"
    summaries = list(csv.DictReader(summary_path.open(encoding="utf-8-sig", newline="")))
    issues = Counter(); severity_counts = Counter(); manner_counts = Counter(); provenance = Counter()
    uids = set(); total = 0
    for summary in summaries:
        year = int(summary["year"]); path = Path(summary["output_file"]); rows = 0
        with path.open(encoding="utf-8-sig", errors="strict", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows += 1; total += 1
                uid = row["crash_uid"]
                if uid in uids: issues["duplicate_crash_uid"] += 1
                uids.add(uid)
                if row["crash_date"]:
                    if not row["crash_date"].startswith(str(year)): issues["date_year_mismatch"] += 1
                elif allow_missing_crash_date:
                    if row.get("date_precision") != "MONTH": issues["missing_date_without_month_precision"] += 1
                    if row.get("crash_year") != str(year): issues["date_year_mismatch"] += 1
                    try:
                        month = int(row.get("crash_month", ""))
                        if not 1 <= month <= 12: issues["invalid_crash_month"] += 1
                    except ValueError:
                        issues["invalid_crash_month"] += 1
                else:
                    issues["missing_crash_date"] += 1
                sev = row["severity_kabco"]; severity_counts[sev] += 1
                if sev not in SEVERITY: issues["invalid_severity_code"] += 1
                if row["fatalities"]:
                    fat = int(row["fatalities"])
                    if fat > 0 and sev != "K": issues["fatality_positive_but_not_K"] += 1
                    if sev == "K" and fat <= 0: issues["K_but_fatality_not_positive"] += 1
                manner = row["manner_of_collision_mmucc"]; manner_counts[manner] += 1
                if manner not in MANNER: issues["invalid_manner_code"] += 1
                provenance[("severity", row["severity_provenance"])] += 1
                provenance[("manner", row["manner_provenance"])] += 1
                status = row["coordinate_status"]
                if status == "VALID":
                    try:
                        lat, lon = float(row["latitude"]), float(row["longitude"])
                        if not (bounds[1] <= lat <= bounds[3] and bounds[0] <= lon <= bounds[2]): issues["valid_coordinate_out_of_bounds"] += 1
                    except ValueError: issues["valid_coordinate_not_numeric"] += 1
                elif row["latitude"] or row["longitude"]:
                    issues["invalid_coordinate_not_blank"] += 1
        if rows != int(summary["output_rows"]): issues["manifest_row_count_mismatch"] += 1
    partials = list(data_dir.glob("*.partial"))
    if partials: issues["partial_files_present"] = len(partials)
    critical_names = {"duplicate_crash_uid", "invalid_severity_code",
                      "fatality_positive_but_not_K", "invalid_manner_code",
                      "missing_crash_date", "missing_date_without_month_precision", "invalid_crash_month",
                      "valid_coordinate_out_of_bounds", "valid_coordinate_not_numeric",
                      "invalid_coordinate_not_blank", "manifest_row_count_mismatch", "partial_files_present"}
    if not allow_date_year_mismatch:
        critical_names.add("date_year_mismatch")
    if allow_fatality_severity_mismatch:
        critical_names.discard("fatality_positive_but_not_K")
    critical = sum(issues[x] for x in critical_names)
    result = {
        "state": state, "executed_utc": datetime.now(timezone.utc).isoformat(), "files": len(summaries),
        "rows": total, "unique_crash_uids": len(uids), "issues": dict(issues),
        "severity_counts": dict(severity_counts), "manner_counts": dict(manner_counts),
        "provenance_counts": {f"{k[0]}:{k[1]}": v for k, v in provenance.items()},
        "result": "PASS" if critical == 0 else "FAIL",
    }
    out = qa_dir / "validation_report.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if critical == 0 else 1)


if __name__ == "__main__":
    main()
