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
- **AL**: `acquisition/download_alabama_crashes.py`
- **AR**: `acquisition/download_arkansas_acat.py`
- **AZ**: (none / manual)
- **CA**: `acquisition/download_ca_fast.py`, `acquisition/download_us_crashes.py`
- **CO**: `acquisition/download_expansionCO.py`, `acquisition/download_us_crashes.py`
- **CT**: `acquisition/download_us_crashes.py`
- **DC**: `acquisition/download_district_of_columbia.py`
- **DE**: `acquisition/download_us_crashes.py`
- **FL**: `acquisition/download_us_crashes.py`, `acquisition/prefill_fdot.py`
- **GA**: `acquisition/download_georgia_dashboard.py`
- **IA**: `acquisition/download_us_crashes.py`
- **ID**: `acquisition/download_us_crashes.py`
- **IL**: `acquisition/download_us_crashes.py`
- **KS**: `acquisition/download_us_crashes.py`
- **KY**: `acquisition/kentucky_crash_downloader.py`
- **MA**: `acquisition/download_us_crashes.py`
- **MD**: (none / manual)
- **ME**: `acquisition/maine_crash_public_downloader.py`, `acquisition/download_maine_public.py`
- **MI**: `acquisition/michigan_crash_downloader.py`, `acquisition/download_michigan_arcgis.py`
- **MN**: `acquisition/download_us_crashes.py`
- **MO**: `acquisition/download_missouri.py`
- **MS**: `acquisition/download_mississippi.py`
- **MT**: `acquisition/download_us_crashes.py`, `acquisition/split_mt_years.py`
- **NC**: `acquisition/download_us_crashes.py`
- **NE**: `acquisition/download_nebraska_portal.py`, `acquisition/download_nebraska_2021_current.py`
- **NJ**: `acquisition/download_new_jersey_2001_2018.py`, `acquisition/download_new_jersey_2020_2023.py`, `acquisition/download_new_jersey_portal_api.py`
- **NM**: `acquisition/download_new_mexico_2019.py`
- **NV**: `acquisition/download_nevada_arcgis_2019_2023.py`
- **NY**: `acquisition/download_expansionNY.py`, `acquisition/download_us_crashes.py`
- **OH**: `acquisition/download_us_crashes.py`
- **OK**: `acquisition/download_ok_remaining.py`, `acquisition/download_us_crashes.py`
- **OR**: `acquisition/download_us_crashes.py`
- **PA**: `acquisition/download_pa.py`
- **SD**: `States/SD/acquisition/download_sd_crashes.py`
- **TN**: `States/TN/acquisition/download_tn_arcgis.py`, `States/TN/acquisition/partition_titan_extract.py`
- **TX**: `acquisition/download_us_crashes.py`
- **UT**: `States/UT/acquisition/download_ut_crashes.py`
- **VA**: `States/VA/acquisition/download_va_crashes.py`
- **VT**: `States/VT/acquisition/download_vt_crashes.py`
- **WA**: `acquisition/download_wa.py`
- **WI**: `acquisition/download_wisconsin_box_annual.py`

Shared framework: `acquisition/download_us_crashes.py`
