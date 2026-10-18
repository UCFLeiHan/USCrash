# USCrash dataset card

- Unit: crash-level record.
- Records: 65,756,924.
- Annual files: 511.
- Spatial coverage: 41 states and the District of Columbia.
- Temporal coverage: 2001–2026, varying by state; 2026 is partial-year.
- Ordered fields: 77.
- Format: UTF-8 CSV.
- Standard: MMUCC-guided semantic harmonization, with source-specific scope and provenance.

`docs/state_coverage.csv` and `manifests/annual_data_catalog.csv` describe retained coverage. `docs/data_sources.csv` identifies the included official sources. `docs/data_dictionary.csv` and `config/` define the common schema and executable mappings.

Blank values are not assumed to mean negative observations. Unknown or unresolved severity and other source limitations retain their documented coding. Not every source population includes all crash types or severities. Oklahoma contains a K/A/B subset; North Carolina 2016–2020 contains fatal and serious-injury crashes. These populations are retained as supplied, rather than expanded by imputation.

## Verification

All 511 annual file headers match the canonical schema; the retained catalog records ID, row-accounting and structural checks. Full-file SHA-256 verification during cleanup passed for all final annual crash files. The earlier 42 representative state-year replays matched retained outputs byte-for-byte; Washington additionally reran its ten dependency years. This cleanup did not regenerate or rewrite crash data.

The code, raw-source archive and detailed revision evidence are maintained separately in the surrounding USCrash project. Optional extensions and historical working artifacts are excluded from this directory.

## Florida source correction (2026-10-18)

Florida 2017–2019 now uses the designated Signal4 annual crash tables, with CODEABLE=Y selected consistently with 2020–2025. The three files were rebuilt and independently checked against selected report IDs and source row numbers. The dataset now contains 65,756,924 records; all other annual data files were retained. Previous raw inputs, outputs and manifests are recoverable in the surrounding project revision evidence. The earlier cleanup/replay checks above describe their respective historical snapshots. Original manuscript statistics and figures predate this correction.
