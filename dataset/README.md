# Dataset metadata

USCrash contains **65,756,924 crash-level records** in **511 annual CSV files**, spanning **41 states and DC**, **2001–2026**, with **77 fields**. Coverage varies by source; 2026 is partial.

This directory contains metadata, not the full record-level CSVs.

| Resource | Location |
| --- | --- |
| Scope and interpretation | [Dataset card](DATASET_CARD.md) |
| Field definitions | [Data dictionary](docs/data_dictionary.csv) |
| Official source inventory | [Data sources](docs/data_sources.csv) |
| State/year coverage | [State coverage](docs/state_coverage.csv) |
| Source field definitions | [Source schemas](source_schemas/) |
| Executable mappings | [Current configuration](../code/config/) |
| Annual file catalog | [Annual catalog](manifests/annual_data_catalog.csv) |
| Canonical data checksums | [Data manifest](manifests/file_manifest.csv) |
| Repository checksums | [Repository manifest](manifests/repository_file_manifest.csv) |

The separate data distribution retains the research layout `USCrash/Unified_MMUCC6/data/crash/<STATE>/`. Manifest paths describe that distribution or the original research workspace as documented in [repository structure](../docs/STRUCTURE.md). Do not change them to match the website directories.

See [data access](../DATA_ACCESS.md) for release status. Original sources, full crash records, and detailed replay evidence are stored outside GitHub.
