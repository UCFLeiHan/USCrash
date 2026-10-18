# Unified U.S. crash dataset

## Release snapshot

- Snapshot date: 2026-10-15 (WA SRFF revision; other states retain their prior snapshots)
- Formal jurisdictions: 42 (including the District of Columbia)
- Annual crash CSV files: 511
- Unique crash records: 65,541,414
- Canonical columns: 77
- Canonical schema SHA-256: `972609b90f887171d309cde8f31a66d4050e21a3691064d4cb871c928ec5ebf5`
- Final integrity result: `PASS`

The formal outputs are under `data/crash/<ST>/`. Official downloads and documented loss-minimized source derivatives remain under `../States/<ST>/`. The harmonization pipeline never treats a missing value as an observed fact and never imputes an unreported accident day, coordinate, severity, or collision geometry.

## Jurisdiction coverage

Formal harmonized data are available for:

`AK AL AR AZ CA CO CT DC DE FL GA IA ID IL KS KY MA ME MI MN MO MS MT NC NE NJ NM NV NY OH OK OR PA SD TN TX UT VA VT WA WI WY`

No formal output is currently published for nine states:

- `HI`, `IN`, `LA`: no verified local statewide crash-level source suitable for this pipeline.
- `MD`: local 2024–2026 official map records are partial and lack per-crash time; not formally harmonized.
- `ND`, `NH`: access request required.
- `RI`: application required.
- `SC`: paid custom request required; public layers are selected crash subsets.
- `WV`: application pending and no local crash data received.

See `docs/SOURCE_INVENTORY.md`, `docs/source_inventory.csv`, and `docs/state_source_matrix.csv` for the source URL, agency, local files, year range, table levels, field availability, access limitations, and configured source pattern for each jurisdiction.

## Canonical content

The crash table standardizes identifiers, temporal precision, location and coordinate status, KABCO severity, MMUCC-aligned collision manner, first harmful event, collision partner, weather, light, roadway surface, roadway context, involvement flags, counts, source values, and mapping provenance. Field availability varies by state and year. A nonempty canonical value can be source-reported or derived; provenance columns distinguish those cases.

Month-only public dates use `crash_year`, `crash_month`, and `date_precision=MONTH`; `crash_date` remains blank. `U` severity can mean an official unknown/unspecified category or a missing source observation; use `severity_provenance` and state QA before analysis.

## Processing and reproducibility

1. Preserve official downloads, codebooks, acquisition notes, and request correspondence under `../States`.
2. Run any state prerequisite builder named in `PIPELINE.md` when the configured input does not yet exist.
3. Profile observed categorical values.
4. Harmonize all configured years with `scripts/harmonize_crash.py`.
5. Validate with `scripts/validate_harmonized_crash.py`.
6. Require complete annual coverage, closed row accounting, unique crash IDs, 77 ordered columns, the canonical schema hash, and a `PASS` validation report.
7. Run the national integrity audit.

The standard state entry point is:

```powershell
.\run_state_pipeline.ps1 -State OR -DataRoot 'F:\LH_Research\USCrash\Crash' -Python 'D:\Anaconda\python.exe'
```

Do not run representative-year experiments against the formal output directory because a filtered run replaces the formal summary and manifest. Use an isolated `USCRASH_ROOT` for tests.

## Quality and known limitations

The 2026-10-14 external review is separate from internal integrity validation. Florida 2020–2025 canonical outputs now select raw `CODEABLE=Y`; 1,798,774 CODEABLE=N reports were excluded from this research population, with original sources, excluded-ID ledgers and preceding outputs retained. N does not itself mean invalid or duplicate. Legacy FDOT years have no equivalent verified filter and retain their original source populations. FL 2023 retains 393,241 codeable reports against 395,175 in the official annual snapshot; the remaining 1,934-report difference is unresolved and was not force-adjusted.

Florida 2011–2019 no longer maps `MOST_HARM_EVNT_CD` into first harmful event. First-event values and dependent groups are blank with UNAVAILABLE provenance; most-event observations remain available in the versioned correction sidecar and raw inputs. All other retained canonical cells were checked for exact equality against the preceding output.

Missouri public-layer/local counts for 2024 and 2025 are substantially below the preserved preliminary annual-report snapshots (−42.51% and −67.36% respectively). Those files remain available as source extracts, but are excluded from complete-state annual totals. MO 2026 is YTD with unverified source completeness, not a verified full-state sample. North Carolina remains unchanged under its accepted public-table population; its counts must not be described as the distinct published reportable-crash totals. See `qa/external_validation_2026-10-14/` and `qa/revisions/2026-10-14_FL_codeable_fhe/` for definitions, reference versions, row-level evidence and executable rules.

The final audit confirms that all 42 jurisdictions have complete configured annual sets, 77 columns in the same order, matching schema hashes, closed source/duplicate/exclusion/output accounting, unique crash IDs, and `PASS` validation. No direct PII columns were found in canonical outputs.

Field completeness is not uniform. Examples include limited coordinates in New Jersey, no public coordinates in New York, month-only dates in Pennsylvania and New Mexico, CAT-only collision-manner/surface gaps in Washington (2020–2026 SRFF-linked rows are now enriched), and partially observed severity in Vermont. State-level QA reports under `qa/post_harmonization/<ST>/` are authoritative for inclusion decisions.

Small source inconsistencies are preserved as warnings rather than silently rewritten. Mississippi excludes four demonstrably corrupted/misaligned CSV rows. Source-specific partial years and YTD releases are documented in state quality notes.

## Privacy and redistribution

Canonical outputs exclude direct identifiers such as names, dates of birth, driver-license numbers, phone numbers, email addresses, VINs, license plates, exact personal addresses, and narratives. Some raw restricted files, especially Texas source tables, contain sensitive or contract-restricted fields and must not be redistributed without agency authorization.

Technical validation does not establish redistribution rights. Review every agency's current license, terms, records-request agreement, and privacy requirements before publishing raw or derived data.

## Authoritative QA artifacts

- `qa/cross_state/final_42_state_integrity_audit.json`
- `qa/cross_state/final_42_state_integrity_audit.csv`
- `qa/cross_state/unified_data_readonly_audit_2026-10-14.json`
- `qa/post_harmonization/<ST>/validation_report.json`
- `qa/post_harmonization/<ST>/harmonization_summary.csv`
- `qa/post_harmonization/<ST>/run_manifest.json`

## Washington detailed-source revision

WA now contains 1,168,229 unique crashes in ten annual files, including 639 newly linked distinct IDs. The detailed 2020–2026 SRFF source supplements severity, collision, weather/light/surface, counts and involvement flags. CAT-only Minor is unspecified injury severity, not automatically B. Raw ObjectStruck does not establish a first harmful event. Existing CAT coordinates are retained; SRFF-only XY awaits documented datum confirmation. See [revision rules](docs/WA_SRFF_REVISION_2026-10-15.md) and `qa/revisions/WA_SRFF_2026-10-15_v1/`. Historical figure/analysis snapshots predate this revision and require regeneration.
