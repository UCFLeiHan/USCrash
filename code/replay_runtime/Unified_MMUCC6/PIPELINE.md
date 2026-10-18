# Reproducible MMUCC 6 pipeline

## Scope and invariants

The pipeline creates crash-level canonical CSV files from read-only state source data. The canonical contract is `config/canonical_crash_schema.csv` (77 columns; SHA-256 `972609b90f887171d309cde8f31a66d4050e21a3691064d4cb871c928ec5ebf5`). A successful state run must preserve the reviewed source-to-output relationship, produce one stable `crash_uid` per output crash, resolve every categorical source value through the reviewed crosswalk or an explicitly documented unavailable/missing path, and pass `validate_harmonized_crash.py`.

Blank means the source did not provide a defensible value. Never infer an unreported day, coordinate, severity class, or collision geometry. Month-only dates use `crash_year`, `crash_month`, and `date_precision=MONTH` while `crash_date` stays blank.

## Directory contract

- `../States/<ST>/<YYYY>/`: read-only official source and documented loss-minimized derivatives.
- `config/canonical_crash_schema.csv`: ordered canonical columns.
- `config/states/<ST>.json`: reviewed source versions, years, paths, fields, bounds, and explicit exceptions.
- `config/code_crosswalk_<ST>.csv`: reviewed categorical mappings and provenance.
- `config/code_crosswalk_<ST>_manner_detail.csv`: optional conditional C09 detail mapping.
- `data/crash/<ST>/`: formal annual 77-column output.
- `qa/code_profiles/<ST>/`: observed source-code profiles.
- `qa/post_harmonization/<ST>/`: summary, run manifest, validator report, and state-specific QA.
- `manifests/`: source-format conversion and source-file inventories.
- `reference/`: official MMUCC materials and exported reference dictionary.

`docs/state_source_matrix.csv` is the machine-readable index of all configured source versions and patterns. `docs/config_inventory.json` verifies configuration/crosswalk symmetry and records the schema hash.

`manifests/source_files_sha256.csv` and `.json` record the preserved source tree byte-for-byte. Rebuild them after an intentional source acquisition or correction with `scripts/build_source_file_manifest.py`; a changed hash must be reviewed before a formal rerun.

## Dependencies

The formal stages use Python 3.11+. Montana's explicit projected-coordinate conversion additionally requires `pyproj` (validated with 3.6.1 / PROJ 9.3.0); other states without a configured projection do not import it. PowerShell 7 is used by `run_state_pipeline.ps1`. `openpyxl` is optional and is needed only for XLSX discovery/conversion and exporting the MMUCC workbook (`normalize_source_formats.py`, `discover_state_schemas.py`, `export_mmucc6_dictionary.py`). Some original acquisition/conversion workflows may require agency-specific portals, GDAL/FileGDB support, or network access; those are upstream of semantic harmonization.

Recommended optional install:

```powershell
python -m pip install openpyxl pyproj==3.6.1
```

## Formal execution order

Montana 2016–2025 additionally has an explicit `coordinate_transform` in its source version: EPSG:32100 (State Plane metres) to EPSG:4326 with XY axis order. `scripts/project_source_coordinates.py` runs identically in profiling and harmonization; zeros remain missing and out-of-bounds results are flagged rather than repaired. Nevada's existing EPSG:26911 conversions were independently reviewed. Metadata, county/state screens, hosted sample checks and unchanged-source hashes are recorded in `qa/coordinate_revision_2026-10-14/`. The coordinate review does not guarantee positional accuracy or population completeness.

1. Preserve the official download and its acquisition metadata under `../States`.
2. Run a state-specific builder/enrichment only when the state config points to its derived output. Builders must record row counts, join keys, conflicts, and SHA-256 values. Do not overwrite the official raw file.
3. Profile all observed codes:

```powershell
python scripts/profile_state_codes.py --state PA
```

4. Harmonize the complete configured year range. Do not use a representative-year run in the formal state directory because it replaces the formal summary/run manifest:

```powershell
python scripts/harmonize_crash.py --state PA
```

5. Validate immediately:

```powershell
python scripts/validate_harmonized_crash.py --state PA
```

6. Confirm `run_manifest.json` has every configured year, `validation_report.json` is `PASS`, every annual header has 77 columns, and the manifest schema hash equals the canonical hash.
7. After all states pass, run the national integrity/consistency audits and summary scripts.

The wrapper performs steps 3–5:

```powershell
.\run_state_pipeline.ps1 -State PA -DataRoot 'F:\LH_Research\USCrash\Crash' -Python 'D:\Anaconda\python.exe'
```

## State-specific prerequisite scripts

These scripts create reviewed crash-level inputs required by particular configs. Run only for their named state and retain their manifests:

- In `scripts/`: `build_ca_crash_level.py`, `build_oh_crash_level.py`, `build_sd_crash_level.py`, `build_ut_crash_level.py`, `build_va_crash_level.py`, `build_wa_crash_level.py`, `prepare_nj_crash_level.py`, `prepare_vt_crash_level.py`, `enrich_ct_entity_counts.py`, `enrich_id_from_units.py`, and `enrich_ms_from_vehicle_events.py`.
- In `../acquisition/`: `enrich_kentucky_incidents.py`, `enrich_mn_rsic_2025.py`, `enrich_montana_crashes.py`, `enrich_nevada_official.py`, `enrich_pennsylvania_flags.py`, `enrich_tennessee_titan.py`, `enrich_texas_cris.py`, and `process_wy_official_2016_2025.py`.

The exact configured filenames, schemas, and year ranges remain authoritative in each state JSON. A builder name alone is not evidence that it must be rerun.

## QA and failure behavior

`harmonize_crash.py` writes `.partial` and renames only after the year completes and all categorical values are reviewed. Unmapped source codes stop the run. The validator checks IDs, dates/date precision, coordinate status, severity consistency, annual file coverage, and configured exceptions. Warnings in `issues` must be described in state quality notes even when the final result remains `PASS`.

For a representative-year experiment, use a copied configuration and a separate `USCRASH_ROOT`; never point the experiment at `data/crash/<ST>` or `qa/post_harmonization/<ST>`.

## WA detailed SRFF enrichment

The WA wrapper now builds CAT inputs and runs `scripts/enrich_wa_from_srff.py --promote` after harmonization, before validation. Retain `States/WA/<year>/SRFF/` and the dictionary. Running the generic harmonizer alone does not reproduce the enriched outputs. See `docs/WA_SRFF_REVISION_2026-10-15.md`.
