# USCrash dataset

USCrash contains **65,756,924 crash-level records** in **511 annual CSV files**, covering **41 U.S. states and the District of Columbia** from **2001 through 2026**. Every file uses the same **77-column MMUCC-guided harmonized schema**.

## Files

- `data/crash/ST/ST_crashes_harmonized_YYYY.csv`: final crash records; one retained record per source crash under the state-specific identifier rules.
- `docs/data_dictionary.csv`: the 77 field names, types and definitions.
- `docs/state_coverage.csv`: retained years and record counts by state.
- `docs/data_sources.csv`: official sources and acquisition notes for included states.
- `config/`: current schema, state/version bindings, categorical crosswalks and supported enrichment mappings.
- `manifests/annual_data_catalog.csv`: all 511 annual files and recorded validation results.
- `manifests/file_manifest.csv`: SHA-256 checksums for the 511 final crash files. Paths are relative to this dataset directory.

## Reading the data

CSV files use UTF-8 encoding. Retain identifier/code columns as strings. Field groups cover identifiers and provenance, time, location, severity and outcomes, vehicles and road users, collision and event characteristics, environmental conditions, and roadway and behavior context.

Coverage and attribute availability differ by state and year. Files for 2026 are partial-year snapshots. Source-reported, unknown and missing information are distinguished through the applicable fields and provenance. Reported month-only dates are retained without an invented day. The source population and applicable transformations are recorded in the state configurations.

## Code and evidence

The accompanying project keeps processing and reproduction code in `../code/`, original sources in `../States/`, and revision/reproduction evidence in `../verification/`. These working resources are separate from this data distribution. Extended Washington attributes, historical analysis products, temporary reports and unpublished entity placeholders are not part of the 77-column crash release.

## Integrity

Every final annual file was checked against its retained SHA-256 baseline during publication-folder review. All 511 annual headers match the ordered 77-column schema. Counts and executed validation scope are documented in the supplied catalogs and dataset card.
