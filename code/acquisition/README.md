# Extract / utility scripts

Canonical state downloaders and shared utilities kept for GitHub.
Probe/explore one-offs are removed by `organize_for_github.py`.

## Kept scripts
- `build_current_inventory.py`
- `build_state_overview.py`
- `consolidate_and_verify.py`
- `download_alabama_crashes.py`
- `download_arkansas_acat.py`
- `download_ca_fast.py`
- `download_district_of_columbia.py`
- `download_expansion1.py`
- `download_expansion2.py`
- `download_expansion3.py`
- `download_expansion4.py`
- `download_expansion5.py`
- `download_expansionCO.py`
- `download_expansionNY.py`
- `download_fars.py`
- `download_georgia_dashboard.py`
- `download_maine_public.py`
- `download_michigan_arcgis.py`
- `download_mississippi.py`
- `download_missouri.py`
- `download_nebraska_2021_current.py`
- `download_nebraska_portal.py`
- `download_nevada_arcgis_2019_2023.py`
- `download_new_jersey_2001_2018.py`
- `download_new_jersey_2020_2023.py`
- `download_new_jersey_portal_api.py`
- `download_new_mexico_2019.py`
- `download_ok_remaining.py`
- `download_pa.py`
- `download_supplement.py`
- `download_us_crashes.py`
- `download_wa.py`
- `download_wisconsin_box_annual.py`
- `kentucky_crash_downloader.py`
- `maine_crash_public_downloader.py`
- `michigan_crash_downloader.py`
- `organize_crash_data.py`
- `organize_for_github.py`
- `prefill_fdot.py`
- `split_mt_years.py`

## Per-state script map
- **AL**: `code/acquisition/download_alabama_crashes.py`
- **AR**: `code/acquisition/download_arkansas_acat.py`
- **AZ**: (none / manual)
- **CA**: `code/acquisition/download_ca_fast.py`, `code/acquisition/download_us_crashes.py`
- **CO**: `code/acquisition/download_expansionCO.py`, `code/acquisition/download_us_crashes.py`
- **CT**: `code/acquisition/download_us_crashes.py`
- **DC**: `code/acquisition/download_district_of_columbia.py`
- **DE**: `code/acquisition/download_us_crashes.py`
- **FL**: `code/acquisition/download_us_crashes.py`, `code/acquisition/prefill_fdot.py`
- **GA**: `code/acquisition/download_georgia_dashboard.py`
- **IA**: `code/acquisition/download_us_crashes.py`
- **ID**: `code/acquisition/download_us_crashes.py`
- **IL**: `code/acquisition/download_us_crashes.py`
- **KS**: `code/acquisition/download_us_crashes.py`
- **KY**: `code/acquisition/kentucky_crash_downloader.py`
- **MA**: `code/acquisition/download_us_crashes.py`
- **MD**: (none / manual)
- **ME**: `code/acquisition/maine_crash_public_downloader.py`, `code/acquisition/download_maine_public.py`
- **MI**: `code/acquisition/michigan_crash_downloader.py`, `code/acquisition/download_michigan_arcgis.py`
- **MN**: `code/acquisition/download_us_crashes.py`
- **MO**: `code/acquisition/download_missouri.py`
- **MS**: `code/acquisition/download_mississippi.py`
- **MT**: `code/acquisition/download_us_crashes.py`, `code/acquisition/split_mt_years.py`
- **NC**: `code/acquisition/download_us_crashes.py`
- **NE**: `code/acquisition/download_nebraska_portal.py`, `code/acquisition/download_nebraska_2021_current.py`
- **NJ**: `code/acquisition/download_new_jersey_2001_2018.py`, `code/acquisition/download_new_jersey_2020_2023.py`, `code/acquisition/download_new_jersey_portal_api.py`
- **NM**: `code/acquisition/download_new_mexico_2019.py`
- **NV**: `code/acquisition/download_nevada_arcgis_2019_2023.py`
- **NY**: `code/acquisition/download_expansionNY.py`, `code/acquisition/download_us_crashes.py`
- **OH**: `code/acquisition/download_us_crashes.py`
- **OK**: `code/acquisition/download_ok_remaining.py`, `code/acquisition/download_us_crashes.py`
- **OR**: `code/acquisition/download_us_crashes.py`
- **PA**: `code/acquisition/download_pa.py`
- **SD**: `States/SD/code/acquisition/download_sd_crashes.py`
- **TN**: `States/TN/code/acquisition/download_tn_arcgis.py`, `States/TN/code/acquisition/partition_titan_extract.py`
- **TX**: `code/acquisition/download_us_crashes.py`
- **UT**: `States/UT/code/acquisition/download_ut_crashes.py`
- **VA**: `States/VA/code/acquisition/download_va_crashes.py`
- **VT**: `States/VT/code/acquisition/download_vt_crashes.py`
- **WA**: `code/acquisition/download_wa.py`
- **WI**: `code/acquisition/download_wisconsin_box_annual.py`

Shared framework: `code/acquisition/download_us_crashes.py`
