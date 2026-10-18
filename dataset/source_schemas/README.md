# Current source-field inventory

This index covers all 511 configured annual inputs across 41 states and DC.
It reads each actual input header and the applicable current state configuration.
Prepared harmonization inputs are distinguished from untouched original downloads.

- `ST_fields.json`: every annual input header and configured binding for a state.
- `annual_source_schemas.csv`: all annual input paths, schema versions, field counts and header hashes.
- `ALL_states_field_map.csv`: annual source bindings, including preparation/helper bindings.

`exact_source_header_match=false` is a diagnostic, not necessarily an error: some bindings represent unavailable fields or configured expressions. Bindings are not invented or inferred from column names. Derived attributes and entity aggregation remain defined by processing code. The final 77-column schema is `code/config/canonical_crash_schema.csv`, separate from these heterogeneous source headers.

Regenerate from the Crash root with `python code/processing/build_source_field_inventory.py`.
