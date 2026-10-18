# US crash data harmonization (MMUCC 6)

This directory contains the reproducible semantic harmonization pipeline and derived QA products. Official state source files remain under `../States`; semantic harmonization writes new files under `data/` and does not overwrite raw state data.

The current formal release is crash-level only. `data/person/` and `data/vehicle/` are documented placeholders for possible future normalized entity-level releases; person and vehicle source evidence remains under `../States` and reviewed aggregates are already included in the crash table where defensible.

The canonical crash table currently has **77 ordered columns**. Forty-two state configurations and forty-two reviewed state crosswalks are present. Missing values remain missing unless a documented, auditable derivation exists.

## Start here

- `qa/external_validation_2026-10-14/index.html`: external count comparisons and the provisional 511 state-year analysis eligibility matrix. Internal integrity PASS is not an external completeness certification.
- `analysis_views/FL_CODEABLE_Y/`: earlier Florida comparison copies. Current formal 2020–2025 outputs already select CODEABLE=Y; these copies must never be appended to canonical data.
- `qa/revisions/2026-10-14_FL_codeable_fhe/`: population-selection and first-event correction audit, excluded IDs, most-event sidecar and preceding outputs.
- [DATASET_CARD.md](DATASET_CARD.md): release scope, coverage, content, limitations, privacy, and authoritative QA.
- [PIPELINE.md](PIPELINE.md): directory contract, dependencies, state prerequisites, commands, run order, and failure behavior.
- [CODE_AUDIT.md](CODE_AUDIT.md): formal assets, cleanup recommendations, portability risks, and maintenance work.
- [CLEANUP_LOG.md](CLEANUP_LOG.md): retained, removed, and archived files.
- `docs/SOURCE_INVENTORY.md`: 51-jurisdiction source and access inventory.
- `manifests/source_files_sha256.csv`: preserved-source file sizes, timestamps, and SHA-256 checksums.
- `docs/state_source_matrix.csv`: configured schemas, years, and source patterns.
- `docs/config_inventory.json`: config/crosswalk coverage and canonical schema hash.
- `config/canonical_crash_schema.csv`: authoritative output column order and definitions.

## Standard state run

After any required state-specific builder has produced the exact configured input:

```powershell
.\run_state_pipeline.ps1 -State OR -DataRoot 'F:\LH_Research\USCrash\Crash' -Python 'D:\Anaconda\python.exe'
```

The wrapper profiles observed source codes, harmonizes the complete configured range, and runs independent validation. A formal run is complete only when every configured year is present in the run manifest, the validator reports `PASS`, every annual file has 77 columns, and the manifest schema hash matches the canonical schema.

Do not run representative-year tests against the formal output directory: a filtered run replaces the state summary and run manifest. Use a separate `USCRASH_ROOT` for experiments.

## Core interpretation rules

- CSV is a physical format, not a common semantic schema.
- Blank, unknown, unavailable, and not applicable are distinct.
- Never fabricate an unreported date, coordinate, severity, or collision geometry.
- Derived fields retain provenance and the original supporting fields.
- Month-only public dates retain reported year/month with `date_precision=MONTH`; no day is imputed.
- Personally identifying or restricted fields are excluded from research-release outputs even when present in the official source.
- Raw data redistribution depends on each source's terms; a technically valid output is not automatically licensed for public redistribution.
