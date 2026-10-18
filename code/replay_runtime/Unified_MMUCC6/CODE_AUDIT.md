# Code and reproducibility audit

Audit date: 2026-10-14. No file was deleted during this audit.

## Formal assets to retain

- `harmonize_crash.py`, `validate_harmonized_crash.py`, `profile_state_codes.py`, `summarize_harmonization.py`, `run_state_pipeline.ps1`.
- All 42 `config/states/*.json` files and their 42 state crosswalks. The audit found no missing or orphan state crosswalk.
- `canonical_crash_schema.csv`, `analysis_category_codebook.csv`, optional manner-detail crosswalks, official references, source/conversion manifests, formal annual outputs, and post-harmonization QA.
- State-specific builders/enrichers listed in `PIPELINE.md` and their per-year metadata. Their outputs are not disposable duplicates when a formal state config references them.
- Acquisition scripts and successful acquisition logs until download URLs, request parameters, timestamps, licenses/terms, and hashes have been captured in a durable source manifest.

## Safe cleanup candidates after review

The following are generated caches or explicitly temporary review programs. They are not formal pipeline inputs:

- `scripts/__pycache__/` and all `*.pyc` files.
- `scripts/_tmp_dup.py`, `_tmp_ut_audit.py`, `_tmp_ut_qa.py`, `_tmp_va_audit.py`, `_tmp_va_qa.py`, `_tmp_wa_audit.py`, `_tmp_wa_qa.py`.
- Abandoned `.partial`, `.tmp`, or `.bak` files only after confirming no process is active and a complete final file exists.
- Empty `*.err.log` files after their associated successful acquisition run is represented in a manifest.

These are recommendations only; this audit did not remove them.

## Archive rather than delete

- `migrate_batch1_74_to_77.py` is a completed migration driver. Move it to an archival/history directory after the final 77-column audit, since it explains a past schema migration but is not a normal entry point.
- `audit_existing_ms_2004_2008.py` and narrowly scoped one-time audit scripts should be archived with the QA artifacts they produced.
- Download/resume logs can be compressed after acquisition metadata and hashes are durable. Logs containing credentials, tokens, signed URLs, or personal information require redaction and must never be committed.

## Items requiring manual confirmation

- Do not delete `CRASH_enriched_*`, `*_enriched.csv`, `*_safe.csv`, or prepared crash-level tables merely because they look intermediate. Many are explicit inputs in `config/states/*.json` and encode audited joins or PII removal.
- Do not delete older schema partitions such as Texas 2023 schema-2018/schema-2023 files; the safe builder combines non-overlapping partitions.
- Do not publish raw restricted tables. Texas raw CRIS tables contain VIN/owner ZIP/narrative fields; other states may have similar fields. Publish only disclosure-reviewed canonical or safe derivatives where redistribution terms allow it.
- `logs/` and `quarantine/` should be assessed against their manifests before cleanup.

## Reproducibility risks found

1. Many state builders and audit scripts hard-code `F:\LH_Research\USCrash\Crash`. The core profile/harmonize/validate scripts honor `USCRASH_ROOT`, but upstream builders are not uniformly portable.
2. The current wrapper assumes prerequisite state builders already ran. It does not derive or execute them from config.
3. A year-filtered harmonization run writes the same formal summary and run manifest as a full run. Representative tests can therefore replace formal state metadata. The documented rule is to test under a separate root; a future implementation should add an explicit output root or non-mutating dry-run mode.
4. Only the XLSX utilities declare a third-party need implicitly through imports. There is no pinned environment/lock file.
5. Some QA warnings are nonfatal by design. National release automation must inspect both `result` and `issues`, not only the process exit code.
6. Upstream acquisition code and semantic harmonization code are split between `Unified_MMUCC6/scripts` and `../acquisition`; a future refactor should expose one registry of prerequisite builders without moving files until hashes and provenance references are updated.

## Recommended next maintenance steps

1. Add `USCRASH_ROOT` support to every retained builder and audit script.
2. Add `--output-root` or `--dry-run` to prevent representative tests from modifying formal output/QA.
3. Add a machine-readable state prerequisite registry keyed by schema ID.
4. Add a minimal optional dependency file pinning `openpyxl` and document Python/PowerShell versions.
5. Add a cleanup script with report-only default and explicit `--apply`; it should refuse to remove config-referenced files.
6. Run `audit_all_state_annual_integrity.py`, `audit_cross_state_consistency.py`, and `build_final_42_state_integrity_audit.py` after all formal state manifests use the same schema hash.
