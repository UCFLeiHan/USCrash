# Schema and field mappings

- [Canonical schema](../code/config/canonical_crash_schema.csv): 77 fields, order, and definitions.
- [State configurations](../code/config/states/): source/version field bindings.
- [Category crosswalks](../code/config/): state-specific category mappings and enrichment crosswalks.
- [Source schemas](../dataset/source_schemas/): heterogeneous source headers and field inventories.
- [Annual input/output links](../dataset/manifests/configured_input_output_links.csv): logical paths in the separate research data workspace.
- [Field dictionary](../dataset/docs/data_dictionary.csv): human-readable field definitions.

Historical notes do not override the active schema and executable mappings. Preserved replay configurations live in `code/replay_runtime/Unified_MMUCC6/config/` and are maintained separately from the current configuration for reproduction of recorded results.
