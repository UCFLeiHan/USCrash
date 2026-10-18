# Repository structure

The repository separates the website, executable code, dataset metadata, and project documentation.

| Location | Contents |
| --- | --- |
| `index.html` | Static project website entry, published by GitHub Pages |
| `assets/css/`, `assets/js/` | Website styling and interactions |
| `assets/data/` | Lightweight JSON aggregates for website charts |
| `assets/` | Figures, maps, and animation |
| `papers/` | Manuscript and supplementary previews |
| `code/acquisition/` | Source acquisition and state preparation |
| `code/processing/` | Harmonization, enrichment, and validation |
| `code/config/` | Current schema and state/version mappings; one maintained copy |
| `code/reproducibility/` | Verification and isolated replay entry points |
| `code/replay_runtime/` | Preserved replay modules and configurations |
| `dataset/docs/` | Field dictionary, sources, and state coverage |
| `dataset/source_schemas/` | Original source field definitions and inventories |
| `dataset/manifests/` | Dataset catalogs and integrity manifests |
| `docs/` | Repository guides and supporting inventories |
| `docs/archive/` | Historical release notes, retained for context |

## Research data layout

Full crash records, original source tables, and detailed verification evidence are not included in GitHub. Research scripts retain the logical `States/<STATE>/<YEAR>/` source layout and `Unified_MMUCC6/data/crash/` output layout used in the separate data distribution. These names in catalogs describe that research workspace, not missing directories in this repository.

Source field definitions previously under `States/field_schemas/` are now in `dataset/source_schemas/`. Duplicate root-level `Unified_MMUCC6/` documentation has been consolidated into `dataset/`. Configurations are maintained in `code/config/`; the replay runtime retains its own preserved configuration snapshot for reproducibility.

`dataset/manifests/repository_file_manifest.csv` checks the current repository snapshot. `research_file_manifest.csv` and `research_annual_data_catalog.csv` preserve the original research-workspace inventory. `file_manifest.csv` retains the separately distributed canonical data checksums. Historical path strings in source inventories are provenance, not links to be rewritten.

See [code instructions](../code/README.md), [field mappings](FIELD_MAPPING.md), and [data access](../DATA_ACCESS.md).
