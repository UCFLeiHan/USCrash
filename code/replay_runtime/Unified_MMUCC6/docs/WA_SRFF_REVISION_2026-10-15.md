# Washington CAT–SRFF revision, 2026-10-15

## Inputs and scope

The CAT baseline consists of ten 2017–2026 crash CSVs. The additional
agency-supplied SRFF files contain 307 source columns per year, 2020–2026,
and 663,433 rows. Originals are copied byte-for-byte to
`../States/WA/<year>/SRFF/`. The supplied September 2026 dictionary is retained
under `../States/WA/docs/source_metadata/`. Filenames contain the snapshot dates;
the 2026 extract is not a complete calendar year.

SRFF CSVs are CP1252, have a disclaimer on the first CSV record and a header
on the second. Data-row numbers below exclude both the disclaimer and header.
Do not let the disclaimer become a header or silently replace invalid bytes.

The baseline is archived under
`qa/revisions/WA_SRFF_2026-10-15_v1/baseline/` before promotion. Source SHA-256,
baseline/output SHA-256, mapping SHA-256 and script SHA-256 are recorded in
the revision manifest. Source records and all 307 attributes remain intact.

## Linkage, population and conflicting snapshots

Link on stripped original REPORT NUMBER; do not convert identifiers to numbers.
The intended population is the union of CAT and SRFF report identifiers, not
an inner join and not replacement by the smaller SRFF population. Preserve
every baseline identifier. SRFF-only identifiers are added after validation.

The initial same-year comparison found 641 apparently additional records.
A subsequent cross-year ID check found two already present in other CAT years:
EA41847 (SRFF 2021, CAT 2020) and 3926011 (SRFF 2025, CAT 2026). Retain the
original CAT year/date for those identifiers, record the alternate date and
source-row exception, and do not create a second accident. Their SRFF values
are retained in the raw extract pending date adjudication. Thus 639 distinct
new IDs are eligible for addition, not 641.

For same-year linked rows, retain CAT dates, times and existing coordinates.
Do not infer that a different snapshot's date or geocode is automatically more
accurate. The revision report counts date/time disagreements, and source rows
allow reconstruction of both alternatives. For an added SRFF record, use its
reported date and minute-level local time without inventing seconds precision
or a UTC offset.

## Explicit mapping rules

`config/enrichment/WA_SRFF_crosswalk.csv` is the executable label crosswalk.
It was reviewed against the source labels, agency dictionary and existing
MMUCC-aligned project categories. Unknown new labels stop processing.

* Severity: Dead at Scene / Dead on Arrival / Died in Hospital → K;
  Suspected Serious Injury → A; Suspected Minor Injury → B;
  Possible Injury → C; No Apparent Injury → O; Unknown → U.
  Unknown SRFF labels do not replace a known CAT grade. A positive reported
  fatality count establishes K and receives derived-count provenance.
* CAT Minor demonstrably combines B and C. Without a linked detailed grade,
  represent it as U with `INJURY_PRESENT_SEVERITY_UNSPECIFIED`; retain Minor
  as the source label. This applies to CAT-only rows, including 2017–2019.
* Casualties: fatalities are reported directly. Injuries are the sum of
  serious + minor + possible injury counts, excluding deaths. Do not treat
  missing component counts as zero. Vehicle, pedestrian and bicycle counts
  are exact reported counts.
* Collision: only explicit first-collision descriptions populate first-event
  groups. Rear-end → C09 1; head-on → 2; angle → 6; same-direction sideswipe
  → 7; opposite-direction sideswipe → 8. An explicitly non-motor-vehicle-
  in-transport first event → 0. A vague motor-vehicle collision does not imply
  an impact geometry. Unknown or ambiguous pairings remain unresolved.
  First-event groups are analytical groups, not newly invented official
  numerical event codes. Preserve source labels in the raw-label columns.
* CAT ObjectStruck does not establish event order. Withdraw its former
  heuristic first-event/partner mappings, preserve its raw text, and mark
  `OBJECT_STRUCK_EVENT_ORDER_UNSPECIFIED`. In particular, guardrail must not
  become a train collision merely because it contains the substring "rail".
* Weather/light/surface: exact dictionary labels have explicit mappings.
  Combined Clear or Partly Cloudy, Blowing Sand or Dirt or Snow, and Snow/Slush
  remain identifiable in source labels; use OTHER in the broad canonical
  variable rather than arbitrarily choose one component. Dark with unknown
  lighting → DARK_UNKNOWN, not DARK_UNLIGHTED.
* Involvement flags: 1/0 → TRUE/FALSE. Work-zone status comes from the explicit
  TZ flag, never from interpreting a blank WORKZONE subtype as FALSE.
  Alcohol involvement is the union of reported drinking and alcohol impairment;
  drug and speeding flags retain the scope of their reported TZ indicators.
* Commercial involvement is not an exact count: remove the legacy inferred
  count of 1 from a CAT positive boolean. Preserve the boolean. Heavy vehicle
  is not synonymous with commercial vehicle, so do not substitute its count.
* TZ motorcycle aggregates include mopeds and scooter bikes. Preserve that
  aggregate separately. An exact motorcycle-only count is derived from the
  three unit-type slots only if all involved units are represented and have
  known types. An observed Motorcycle gives a positive flag; a zero broad
  TZ motorcycle flag gives a negative flag. Incomplete coverage gives no
  invented exact count.
* A single crash-level speed limit is filled only when all involved units
  (at most three) have positive, valid, identical reported limits. Otherwise
  preserve unit limits in the extension; do not arbitrarily use vehicle 1.

## Coordinates and additional attributes

SRFF contains Washington State Plane South X/Y, not latitude/longitude.
The supplied dictionary does not specify datum realization. WSDOT publishes
other roadway products in NAD83(HARN) Washington South US survey feet, but
that alone does not confirm this extract's CRS. Candidate EPSG:2927 and 2286
both produce broadly plausible coordinates; the 2023 CAT comparison has a
median disagreement of about 14 m and a 95th percentile of about 1.09 km.
Those differences do not resolve the datum or prove a geocode correction.

Consequently existing valid CAT coordinates are retained. New SRFF-only rows
retain blank canonical latitude/longitude and MISSING status until the datum
is documented. Raw X/Y are preserved. This is a deliberate unresolved item,
not evidence that SRFF lacks location data.

`data/extensions/WA/WA_SRFF_extended_attributes_<year>.csv` retains source
links/rows, alternate date/time, target-zero/reportability indicators,
distraction, broader motorcycle and heavy-vehicle measures, second collision,
junction/workzone details, unit speed limits, and raw XY. The full source has
the remaining vehicle/person attributes. These are not separately normalized
complete vehicle/person tables; no such tables are claimed.

## Validation, evidence and reproducibility

Stage all ten outputs before promotion. Require 77 ordered columns; unique
state-scoped crash IDs across years; retention of all baseline IDs; exact union
row accounting; valid category domains; nonnegative integer counts; valid date
years; bounded existing coordinates; positive fatalities implying K; successful
CSV readback. Record every changed cell as old/new in compressed JSONL, including
the SRFF source file and data-row number for linked records. For mixed-source
rows, canonical source_file/source_row_number retain the CAT primary pointer;
the change ledger supplies the field-level SRFF pointers. For new rows, the
primary pointer is SRFF. Extensions keep a direct SRFF pointer for each row.

The normal complete rebuild, after copying the retained source package, is:

```powershell
.\run_state_pipeline.ps1 -State WA -DataRoot 'F:\LH_Research\USCrash\Crash' -Python 'D:\Anaconda\python.exe'
```

The wrapper builds CAT crash-level inputs, profiles, harmonizes, enriches from
SRFF, and validates. Running harmonize_crash.py alone recreates only the CAT
baseline and must not be mistaken for the enriched product.

To recreate a staged revision from the archived baseline:

```powershell
python scripts/enrich_wa_from_srff.py --baseline-dir qa/revisions/WA_SRFF_2026-10-15_v1/baseline/data
```

Add `--promote` to replace canonical outputs after all staging checks pass.
Enriched inputs are rejected to prevent compounding provenance on rerun.
National figures and old QA snapshots need regeneration before use in a paper.

The final structural validator passes with six noncritical warnings: K severity
with a reported fatality count of zero. They are listed with the source labels
in `fatality_severity_conflicts.json`. Preserve both observations; exclude them
from internally consistent fatality-count cohorts until adjudicated. PASS is
not a claim that these source inconsistencies have been resolved.

Reference for the provisional roadway CRS only:
https://data.wsdot.wa.gov/geospatial/DOT_TDO/LRS/500kLRS.htm
