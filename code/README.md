# USCrash code

- `acquisition/`: source acquisition and state-level preparation.
- `processing/`: harmonization, enrichment, coordinate supplementation and validation.
- `config/`: schema, state/version bindings and category crosswalks.
- `reproducibility/`: isolated replay and verification tools.
- `replay_runtime/`: environment-configurable code used by the validated representative-year replay. It preserves the tested internal module structure.
- `patches/`: the documented collision-manner initialization correction used in selected replay cases.

Verify code and documentation from the repository root:

```powershell
python code/reproducibility/verify_snapshot.py --root . --scope code
```

For a new representative-year reproduction, select a fresh isolated workspace:

```powershell
$env:USCRASH_REPLAY_ROOT = 'F:/LH_Research/USCrash/Crash/verification/fresh_replay'
python code/reproducibility/run_representative_replay.py
```

This entry point reruns state preparation where configured, harmonization, selected overlays and validation. Washington requires all ten dependency years. The archived original 42 representative cases remain under `verification/replay_checks/representative_years/`. A fresh Alaska 2021 replay after code integration reproduced the final file byte-for-byte.

The replay runtime and working processing scripts have distinct documented roles. Classification rules and final data values were not changed during directory integration; only path resolution was adjusted in working scripts.

## Working layout

Current configurations are maintained once in `code/config/`. Source field inventories are in `dataset/source_schemas/`, and catalogs are in `dataset/manifests/`. The replay runtime intentionally retains its internal structure and configuration snapshot; it is not an alternative starting point for new code. Full replay requires the separate raw inputs and canonical data, placed in the documented research layout.

The verification command above checks repository hashes and writes its report to an ignored `verification/verification_runs/` directory. `--scope final` requires the downloaded canonical data under the research layout. See [repository structure](../docs/STRUCTURE.md).

## Florida source correction

The current configuration uses the designated Signal4 crash tables for 2017–2025. To rebuild the corrected 2017–2019 files in isolation, run `python code/processing/rebuild_fl_signal4_2017_2019.py --output-root <new-empty-path>`. The output path must not exist. Raw inputs retain all reports; the unified tables select CODEABLE=Y. See `verification/unified_revision_evidence/FL_signal4_2017_2019_2026-10-18/` for source hashes, excluded report IDs, record-level checks, and previous files.
