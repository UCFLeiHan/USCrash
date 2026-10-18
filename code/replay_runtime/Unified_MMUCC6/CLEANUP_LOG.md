# Storage cleanup log

## 2026-10-14

The source and unified-data trees were audited before cleanup.

Kept:

- All official downloads, unique raw files, codebooks, request records, and access notes.
- All files referenced by formal state configurations.
- All 511 formal annual crash CSV files.
- All state configurations, crosswalks, prerequisite builders, manifests, final QA, and reference material.
- Seventy-two prepared/enriched source-side files whose lossless reconstruction was not sufficiently proven. They are listed in `docs/retained_review_required_files.csv`.

Removed:

- Seven explicitly named `_tmp_*` audit/regression scripts after their formal QA outputs had been retained.
- One incomplete migration audit artifact: `migration_batch1_74_to_77_result.partial.json`.

Archived under `scripts/archive/`:

- `migrate_batch1_74_to_77.py`
- `audit_existing_ms_2004_2008.py`

Not removed:

- Python bytecode cache files. Automatic recursive deletion was rejected by the execution approval layer; these files are harmless and reproducible.
- Source-side files named `prepared`, `enriched`, or `Derived` when there was insufficient proof that they could be regenerated losslessly from retained inputs.

The authoritative cleanup candidate records are `docs/cleanup_candidates.csv`, `docs/retained_review_required_files.csv`, and `qa/cross_state/storage_cleanup_candidates_2026-10-14.json`.

After cleanup, the preserved `States` tree was hashed into `manifests/source_files_sha256.csv` and `.json`: 5,189 files and 90,293,298,020 bytes, using SHA-256.
