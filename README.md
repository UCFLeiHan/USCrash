# USCrash

A Harmonized U.S. Nationwide Traffic Crash Dataset.

The corrected dataset contains **65,756,924 crash records**, **511 state–year CSV files**, and **77 fields**, covering **41 states and the District of Columbia**. Available years span **2001–2026**; coverage varies by source and 2026 is partial.

## Contents

- Root HTML/CSS/JavaScript: static academic project website.
- `assets/`, `data/`, `papers/`: website figures, lightweight aggregate JSON, manuscript preview PDFs.
- `code/`: acquisition, processing, configuration, and replay tools.
- `dataset/docs/`: field dictionary, official sources and coverage.
- `dataset/config/`: schema and state/version mappings.
- `dataset/manifests/`: catalog and per-file SHA-256 checksums.
- `dataset/DATASET_CARD.md`: data scope and interpretation.

Full crash CSV files are distributed separately. Project website: https://ucfleihan.github.io/USCrash/

Source repository: https://github.com/UCFLeiHan/USCrash

Full data download URLs will be added after the data release.

## Preview and GitHub Pages

Run `python -m http.server 8765 --bind 127.0.0.1` from the repository root and open http://127.0.0.1:8765/ . All website URLs are relative.

Push the contents of this directory to GitHub. In Settings > Pages, choose Deploy from a branch and the published branch's `/ (root)`. Keep `.nojekyll`. A repository named `<username>.github.io` uses the account-root URL; other names use a project URL. Full data release is in preparation.

## Data downloads

Download `USCrash_metadata_2026-10-18.zip` plus the state ZIPs you need. Extract them into one directory, where they combine under `USCrash/Unified_MMUCC6/`. Annual CSVs reside at `data/crash/<STATE>/` below that root. The optional code ZIP supplies the surrounding `USCrash/code/` layout.

Verify downloaded archives against SHA256SUMS.txt. Uncompressed canonical-file hashes are in the metadata ZIP. Use pandas chunked reading for large analyses.

## Scope and interpretation

Blank or unknown values are not negative observations. Oklahoma includes a K/A/B subset; North Carolina 2016–2020 includes fatal and serious-injury crashes. Attribute availability measures valid analytical field–record cells, not complete crash records or accuracy.

Website counts reflect the Florida 2017–2019 correction. Original manuscript PDFs and figure images are previews and may contain earlier values. The website uses original workflow/schema artwork, linked state coverage, descriptive distributions, a 40-area 2021 benchmark and 12-area map comparison.

## Access terms, code and citation

Original USCrash documentation and eligible compilation contributions use CC BY-NC 4.0; see DATA_LICENSE.md. Source-record redistribution conditions and the code license remain under review. No blanket license for all upstream state records is asserted; consult `dataset/docs/data_sources.csv` and the source agencies' terms. Publication metadata, DOI, public download URLs and the final citation remain pending.

Code includes source-specific and historical acquisition scripts. Some require local raw inputs, dependency years and environment path configuration. See `code/README.md`. Full raw archives and historical verification evidence remain in the author's local research project.

The annual hero map includes Alaska and Hawaii insets. Alaska has records for 2021–2025; Hawaii is not included. Insets use independent display scales; the lower-right distance scale applies to the contiguous U.S. only. Both plotted regions use 25 km² cells and the same crash-count color scale.
