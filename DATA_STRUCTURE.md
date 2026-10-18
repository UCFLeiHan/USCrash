# USCrash

Final data: 65,756,924 crash records, 511 annual CSV files, 77 columns, 41 states and DC.

| Resource | Location |
| --- | --- |
| Acquisition and state preparation code | `code/acquisition/` |
| Harmonization, enrichment and validation | `code/processing/` |
| Schema, source bindings and category mappings | `code/config/` |
| Reproduction entry points | `code/reproducibility/` |
| Validated isolated-replay runtime | `code/replay_runtime/` |
| Required correction patch | `code/patches/` |
| Original sources and required prepared inputs | `States/`, `Cities/`, `Nationwide/` |
| Final harmonized crash records | `Unified_MMUCC6/data/crash/` |
| Documentation and current inventories | `docs/`, `manifests/` |
| Recorded replay and verification evidence | `verification/` |

See `code/README.md` for commands and `FIELD_MAPPING.md` for schema entry points. The previous dated release directory has been integrated into these resources.

Dataset configurations are physically stored in Unified_MMUCC6/config, with code/config as a compatibility junction. Processing scripts are in code/processing. The public dataset directory contains no external junctions. Original sources and final crash records were not rewritten.

Acquisition inventories are in `manifests/acquisition/`. Source field dictionaries and service metadata are in `docs/source_metadata/`. Acquisition scripts use `code/acquisition/` directly.
