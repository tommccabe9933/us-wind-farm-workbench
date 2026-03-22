# Wind Farm Investment Screener — Claude Code Prompt

You are building a data pipeline and interactive dashboard for a private equity fund that screens U.S. wind farms for distressed investment opportunities. The deliverable is a locally runnable Streamlit dashboard backed by clean, sourced data from U.S. federal government datasets.

**Core principles:**
1. Every data point must link directly to its government source — one click from any value to the page that published it.
2. No composite scores, no black-box rankings, no arbitrary weighting. Every column in the dashboard is a direct, auditable KPI derived from raw data with a clear formula.
3. The dashboard is the product. The Excel file is the audit trail. There is no presentation deliverable.
4. Rolling averages are required wherever year-over-year figures are computed — single-year anomalies (bad wind year, one-time curtailment event) must not drive conclusions.
5. All data is sortable. Every column in every table is sortable ascending and descending with a single click.

**Do not produce placeholder outputs. Do not leave TODOs. Every script must run to completion.**

---

## DATA VINTAGE

| Year(s) | Source | Status |
|---|---|---|
| 2018–2024 | EIA-923 annual + EIA-860 annual | Final, fully validated by EIA |
| 2025 Jan–Dec | EIA Electric Power Monthly (EPM) | All 12 months available as of Feb 24, 2026. Minor revisions possible at annual reconciliation (expected late 2026), typically <3% for large plants. No warning labels needed — one factual note in Sources tab only. |
| 2026 Jan+ | EIA EPM — releases on the 24th of each month | January 2026 drops March 24, 2026. Pipeline refreshes by re-running `01_download.py`. |

---

## FOLDER STRUCTURE

```
windfarm_screener/
├── data/
│   ├── raw/
│   │   ├── eia860/        # Annual ZIPs 2018–2024
│   │   ├── eia923/        # Annual ZIPs 2018–2024
│   │   ├── epm/           # Monthly EPM files Jan–Dec 2025
│   │   ├── eia860m/       # Latest monthly — retirement/addition flags only
│   │   ├── uswtdb/        # Turbine database
│   │   ├── egrid/         # NERC region labels only
│   │   └── lbnl/          # Regional CF benchmarks
│   ├── processed/
│   └── external/
├── scripts/
│   ├── 01_download.py
│   ├── 02_clean_merge.py
│   ├── 03_kpis.py
│   ├── 04_export_excel.py
│   └── 05_verify.py
├── dashboard/
│   └── app.py
├── outputs/
│   ├── wind_plants.csv          # Full dataset, all KPIs
│   ├── wind_screener.xlsx
│   └── audit/
│       ├── download_manifest.csv
│       ├── merge_log.txt
│       ├── validation_report.txt
│       └── source_trace.csv
└── README.md
```

---

## DATA SOURCES

Use only these sources. Every URL is verified. Do not substitute or guess.

### Source 1 — EIA Form 860: Plant & Generator Metadata
- **Publisher:** U.S. Energy Information Administration
- **Landing page:** https://www.eia.gov/electricity/data/eia860/
- **Contains:** Plant name, operator, owner name, state, lat/lon, nameplate capacity (MW) per generator, commissioning year, technology type, balancing authority
- **ZIP pattern:** `https://www.eia.gov/electricity/data/eia860/xls/eia860{YEAR}.zip`
- **Years:** 2018–2024
- **Extract only:** `2___Plant_Y{year}.xlsx` (plant-level) and `3_1_Wind_Y{year}.xlsx` (wind generator-level) and `4___Owner_Y{year}.xlsx` (ownership detail)
- **Store:** `data/raw/eia860/`
- **Plant page URL for hyperlinks:** `https://www.eia.gov/electricity/data/browser/#/plant/{PLANT_ID}`

### Source 2 — EIA Form 923: Annual Generation
- **Publisher:** U.S. Energy Information Administration
- **Landing page:** https://www.eia.gov/electricity/data/eia923/
- **Contains:** Net generation (MWh) by plant, by month, by prime mover
- **ZIP pattern:** `https://www.eia.gov/electricity/data/eia923/xls/f923_{YEAR}.zip`
- **Years:** 2018–2024
- **Extract only:** File matching `EIA923_Schedules_2_3_4_5_*_Final.xlsx`
- **Sheet:** `Page 1 Generation and Fuel Data` — column `Net Generation (Megawatthours)`
- **Filter to:** `Reported Prime Mover = WT` (wind turbine only)
- **Store:** `data/raw/eia923/`

### Source 3 — EIA Electric Power Monthly (EPM): 2025 Generation
- **Publisher:** U.S. Energy Information Administration
- **Landing page:** https://www.eia.gov/electricity/monthly/
- **Contains:** Plant-level net generation (MWh) by month for 2025
- **Why:** EIA-923 2025 annual does not exist yet (earliest release: June 2026). EPM is the only current-year plant-level source.
- **Coverage:** All utility-scale plants ≥1 MW — your ≥10 MW universe is fully covered.
- **Download:** Use EIA Open Data API at `https://api.eia.gov/v2/electricity/electric-power-operational-data/data/` with params: `frequency=monthly`, `data[]=generation`, `facets[fueltypeid][]=WND`, `start=2025-01`, `end=2025-12`. Requires free API key from https://www.eia.gov/opendata/register.php
- **Store:** `data/raw/epm/epm_2025_monthly.csv`
- **Processing:** Store each month as `gen_mwh_2025_{MM}`. Sum all 12 for `gen_mwh_2025`. Store `epm_months_count` = number of non-null months per plant (must be 12 for inclusion).

### Source 4 — EIA Form 860M: 2025 Capacity Change Detection Only
- **Publisher:** U.S. Energy Information Administration
- **Landing page:** https://www.eia.gov/electricity/data/eia860m/
- **Use:** Boolean flag `capacity_changed_2025` only. Do NOT use 860M capacity figures in any KPI calculation — EIA warns these are often retroactively corrected. All capacity calculations use EIA-860 annual final only.
- **Download:** Most recent monthly XLS from landing page
- **Store:** `data/raw/eia860m/eia860m_latest.xlsx`

### Source 5 — U.S. Wind Turbine Database (USWTDB)
- **Publisher:** USGS + NREL
- **Landing page:** https://eerscmap.usgs.gov/uswtdb/
- **Contains:** Per-turbine: manufacturer (`t_manu`), model (`t_model`), hub height (`t_hh`, meters), rotor diameter (`t_rd`, meters), rated capacity (`t_cap`, kW), EIA plant code (`eia_id`)
- **Download:** https://eerscmap.usgs.gov/uswtdb/assets/data/uswtdbCSV.zip
- **Store:** `data/raw/uswtdb/uswtdb_latest.csv`
- **Join:** `eia_id` → EIA Plant Code. ~10–15% will be `eia_id = -9999` — log but do not drop.

### Source 6 — EPA eGRID: NERC Region Only
- **Publisher:** U.S. Environmental Protection Agency
- **Landing page:** https://www.epa.gov/egrid/download-data
- **Use:** Extract `ORISPL` (= EIA Plant Code) and `NERC` (region label) only. No other eGRID fields — all other data is derived from EIA and creates circular references.
- **Download:** Excel file `eGRID{YEAR}_data.xlsx`, sheet `PLNT{YY}`
- **Store:** `data/raw/egrid/egrid_latest.xlsx`

### Source 7 — LBNL Wind Technologies Market Report
- **Publisher:** Lawrence Berkeley National Laboratory (U.S. DOE)
- **Landing page:** https://emp.lbl.gov/wind-technologies-market-report
- **Use:** Regional average capacity factor benchmarks by NERC region and installation vintage decade. One lookup row per region/vintage combination — used to compute `cf_vs_regional_benchmark`.
- **Download:** Excel "Data file" from most recent report
- **Store:** `data/external/lbnl_wind_market.xlsx`
- **Fallback:** If file cannot be parsed automatically, write benchmarks as a hardcoded dict in `data/external/lbnl_benchmarks_manual.py` with a comment citing source table, page, and report year.

---

## STEP 1 — DOWNLOAD (`scripts/01_download.py`)

1. Create all directories.
2. Download all sources with `requests` + `tqdm` progress bars.
3. Compute MD5 hash of each downloaded file.
4. Extract only the listed files from each ZIP.
5. Write `outputs/audit/download_manifest.csv`:

```
source_name | description | landing_page_url | download_url | local_path | file_size_bytes | md5_hash | download_timestamp | http_status_code | rows_in_file
```

**Failure handling:** On any failure, log to manifest as FAILED, continue, print summary at end. Halt the pipeline if EIA-860 or EIA-923 fail for any year 2018–2024, or if EPM 2025 cannot produce all 12 months.

**Post-download spot checks — print to console:**
```
EIA 860 (2024):   Expected ~1,800+ wind plants.        Actual: {N}
EIA 923 (2024):   Expected ~1,600+ wind plant rows.    Actual: {N}
EPM 2025:         Expected 12 monthly files.           Loaded: {N}
USWTDB:           Expected ~75,000+ turbine records.   Actual: {N}
eGRID:            Expected ~10,000+ plant rows.        Actual: {N}
```

Halt if any count is below 50% of expected.

**2026 refresh:** Script checks for existing monthly EPM files before downloading. Re-run on or after the 24th of each month to pick up the prior month's data. January 2026 available March 24, 2026.

---

## STEP 2 — CLEAN & MERGE (`scripts/02_clean_merge.py`)

Output: `data/processed/wind_plants_merged.parquet` + `outputs/audit/source_trace.csv`

### Merge sequence

**2a — EIA 860 plant files (2018–2024)**
Load `2___Plant_Y{year}.xlsx`, sheet `Plant`. Keep: `Plant Code`, `Plant Name`, `State`, `Latitude`, `Longitude`, `Utility Name`, `Owner Name`, `Balancing Authority Code`. Add `year` column.

**2b — EIA 860 wind generator files (2018–2024)**
Load `3_1_Wind_Y{year}.xlsx`, sheet `Operable`. Keep: `Plant Code`, `Nameplate Capacity (MW)`, `Operating Year`, `Operating Month`. Sum capacity by Plant Code per year → `capacity_mw_{year}`. Min `Operating Year` → `commissioning_year`.

**2c — EIA 860 owner files (2018–2024)**
Load `4___Owner_Y{year}.xlsx`. Keep: `Plant Code`, `Owner Name`, `Percent Owned`. Use most recent year (2024) to determine primary owner and ownership structure. Flag `multiple_owners = True` if more than one owner entity is listed. This is a useful acquisition signal — complex ownership structures can accelerate or complicate a sale.

**2d — EIA 923 annual generation (2018–2024)**
Sheet `Page 1 Generation and Fuel Data`. Filter `Reported Prime Mover = WT`. Group by `Plant Id` + year, sum `Net Generation (Megawatthours)`. Rename `Plant Id` → `Plant Code`. Store as `gen_mwh_{year}` (e.g. `gen_mwh_2018` through `gen_mwh_2024`). Also store monthly breakdown per year: `gen_mwh_{year}_{MM}` for all 12 months — these are used for seasonality analysis.

**2e — EPM 2025 monthly**
From `epm_2025_monthly.csv`: store `gen_mwh_2025_01` through `gen_mwh_2025_12`. Sum → `gen_mwh_2025`. `epm_months_count` = count of non-null months. Exclude plant from 2025 KPIs if `epm_months_count < 10`.

**2f — EIA 860M capacity change flag**
Flag `capacity_changed_2025 = True` for any Plant Code appearing on the Retired or Proposed tabs of 860M with a date after Jan 1, 2025. Boolean only — no capacity values.

**2g — USWTDB aggregation**
Group by `eia_id`. Compute: `turbine_count` (row count), `turbine_manufacturer` (mode of `t_manu`), `turbine_model` (mode of `t_model`), `hub_height_m` (mean `t_hh`, 1dp), `rotor_diameter_m` (mean `t_rd`, 1dp), `total_rated_capacity_kw` (sum `t_cap`), `turbine_vintage_min` (min commissioning year in USWTDB), `turbine_vintage_max` (max). Rename `eia_id` → `Plant Code`.

**2h — eGRID NERC**
Keep `ORISPL`, `NERC` only. Rename `ORISPL` → `Plant Code`.

**2i — Final join**
```
base = EIA 860 plant (2024 as primary static record)
+ left join EIA 860 generator (capacity_mw_2018 ... capacity_mw_2024, commissioning_year)
+ left join EIA 860 owner (owner detail, multiple_owners flag)
+ left join EIA 923 (gen_mwh_2018 ... gen_mwh_2024, plus monthly breakdowns)
+ left join EPM 2025 (gen_mwh_2025 and monthly columns)
+ left join EIA 860M (capacity_changed_2025)
+ left join USWTDB (turbine metadata)
+ left join eGRID (nerc_region)
```

Filter: `technology = Wind Turbine` AND `capacity_mw_2024 >= 10` (fall back to `capacity_mw_2023` if 2024 null).

### Source trace
`outputs/audit/source_trace.csv` — one row per plant:
```
plant_id | plant_name | eia860_file | eia860_row | eia923_files | eia923_rows_summed | epm_months_count | uswtdb_matched | egrid_matched | capacity_changed_2025
```

### Merge quality log (print + save to merge_log.txt)
```
Plants in EIA 860 2024 (wind, >=10MW):             {N}
Plants with full annual data (all 7 years):         {N}
Plants with partial annual data:                    {N}
Plants with no generation data (excluded):          {N}
Plants with full 2025 EPM (12 months):              {N}
Plants with partial 2025 EPM (10-11 months):        {N}
Plants with no 2025 EPM data:                       {N}
Plants matched to USWTDB:                           {N} ({pct}%)
Plants NOT in USWTDB (list names):                  {N}
Plants with NERC region:                            {N} ({pct}%)
Plants with capacity_changed_2025:                  {N}
Plants with multiple owners:                        {N}
```

---

## STEP 3 — KPI COMPUTATION (`scripts/03_kpis.py`)

Input: `data/processed/wind_plants_merged.parquet`
Output: `data/processed/wind_plants_kpis.parquet`

This is the core step. Every KPI listed below must:
- Have a Python comment explaining its exact formula and what it measures
- Handle nulls explicitly — never drop rows, set metric to null and log
- Be named clearly so a non-technical user knows what the column means

Constants at top of script — all adjustable:
```python
HOURS_PER_YEAR   = 8760
CURRENT_YEAR     = 2026
MIN_CAPACITY_MW  = 10
CF_CAP           = 0.65    # Above this = data error flag
```

---

### BLOCK A — Capacity Factor (the core efficiency metric)

**Annual CF per year (2018–2025)**
```python
# CF = how much of the plant's maximum possible output it actually produced
# A 100 MW plant running at 35% CF generates 35 * 8760 = 306,600 MWh/year
# Source: gen_mwh_{year} from EIA-923; capacity_mw_{year} from EIA-860
cf_{year} = gen_mwh_{year} / (capacity_mw_{year} * HOURS_PER_YEAR)

# 2025 uses EIA-860 2024 capacity as denominator (2025 annual not yet published)
cf_2025 = gen_mwh_2025 / (capacity_mw_2024 * HOURS_PER_YEAR)
```
Flag `cf_data_error_{year} = True` if `cf > CF_CAP` (0.65). These are data entry errors.
Flag `cf_zero_{year} = True` if `cf <= 0`.

**Rolling average CFs**
```python
# 3-year rolling CF — smooths out single bad wind years
# PRIMARY metric for performance assessment — use this, not any single year
cf_3yr_2022_2024 = mean(cf_2022, cf_2023, cf_2024)   # Final annual data only
cf_3yr_2023_2025 = mean(cf_2023, cf_2024, cf_2025)   # Includes EPM 2025
cf_5yr_2020_2024 = mean(cf_2020, cf_2021, cf_2022, cf_2023, cf_2024)
cf_7yr_2018_2024 = mean(cf_2018, cf_2019, cf_2020, cf_2021, cf_2022, cf_2023, cf_2024)
```
Require minimum 2 valid years for 3-year averages, 3 valid years for 5-year, 5 valid years for 7-year. Set null otherwise.

**CF vs. regional peers**
```python
# Percentile rank within same NERC region using cf_3yr_2022_2024
# 10th percentile = bottom 10% of plants in that region
cf_regional_percentile = percentile rank of cf_3yr_2022_2024 within nerc_region (0–100)
```

**CF vs. LBNL benchmark**
```python
# How far above or below the regional average for plants of similar age?
# Negative = underperforming vs. what wind resource quality would predict
cf_vs_lbnl_benchmark = cf_3yr_2022_2024 - lbnl_regional_benchmark_cf
```

---

### BLOCK B — Production Trend (is the plant getting better or worse?)

All trend metrics use capacity-adjusted generation (MWh per MW of installed capacity). This removes the distortion from capacity changes — a plant that retired 10 turbines will show lower MWh but that is not operational underperformance.

```python
# Capacity-normalized generation per year
gen_per_mw_{year} = gen_mwh_{year} / capacity_mw_{year}   # 2018–2024
gen_per_mw_2025   = gen_mwh_2025 / capacity_mw_2024
```

**Year-over-year change (capacity-adjusted)**
```python
yoy_pct_{year} = (gen_per_mw_{year} - gen_per_mw_{year-1}) / gen_per_mw_{year-1} * 100
# Compute for 2019, 2020, 2021, 2022, 2023, 2024, 2025
```

**Rolling average YoY — REQUIRED to avoid single-year noise**
```python
# Average of the past 3 years' YoY changes
# This is more reliable than any single YoY figure
yoy_3yr_avg = mean(yoy_pct_2022, yoy_pct_2023, yoy_pct_2024)

# Is the rolling trend positive or negative?
trend_direction = 'IMPROVING' if yoy_3yr_avg > 2 else ('DECLINING' if yoy_3yr_avg < -2 else 'FLAT')
```

**Peak and decline from peak**
```python
peak_gen_per_mw  = max(gen_per_mw_2018 ... gen_per_mw_2024)
peak_year        = argmax(gen_per_mw_2018 ... gen_per_mw_2024)

# Decline from peak to 2024 (final annual data)
decline_from_peak_pct = (gen_per_mw_2024 - peak_gen_per_mw) / peak_gen_per_mw * 100
# Negative = below peak. E.g. -22.4 means 22.4% below best year.

# Decline including 2025 EPM signal
decline_from_peak_pct_with_2025 = (gen_per_mw_2025 - peak_gen_per_mw) / peak_gen_per_mw * 100
```

**Consecutive decline years**
```python
# How many years in a row has capacity-normalized generation fallen?
# 3+ consecutive declining years is a much stronger signal than a single bad year
consecutive_decline_years = count of trailing years where gen_per_mw_{year} < gen_per_mw_{year-1}
# Count backward from 2024. Stop at first year that is higher than prior year.
```

**Cumulative production loss**
```python
# Total MWh lost vs. what the plant would have produced at peak efficiency
# Gives a dollar-denominated sense of the underperformance
# Assume $30/MWh as reference price (store as a constant — analyst can change)
REFERENCE_PRICE_PER_MWH = 30

cumulative_mwh_lost_2022_2024 = sum over 2022–2024 of:
    (peak_gen_per_mw * capacity_mw_{year} * HOURS_PER_YEAR) - gen_mwh_{year}
# Only count years where actual < peak. Set floor at 0.

cumulative_revenue_lost_usd = cumulative_mwh_lost_2022_2024 * REFERENCE_PRICE_PER_MWH
# Label clearly in all outputs: "Est. revenue shortfall vs. peak at $30/MWh reference"
```

---

### BLOCK C — Asset Profile (what kind of asset is this?)

```python
asset_age         = CURRENT_YEAR - commissioning_year
turbine_age       = CURRENT_YEAR - turbine_vintage_min   # Oldest turbines on site

# PTC expiry: 10-year federal Production Tax Credit from commissioning date
# Plants commissioned 2010–2016 have had their PTC expire as of 2026
ptc_expired       = True if 10 <= asset_age <= 16

# Repowering candidacy: assets where turbines are old enough to justify full repower
# but plant has proven wind resource (>7 years of operating history)
repower_candidate = True if turbine_age >= 15 AND asset_age >= 10

# Capacity utilization rate: how close to nameplate is the plant actually running?
# Low CF relative to age suggests mechanical, not resource, issues
# Compare against cf_5yr benchmark
```

---

### BLOCK D — Owner & Acquisition Signals

```python
# How many wind plants does this owner operate in the full dataset?
owner_plant_count    = count of plants sharing same owner_name
owner_total_mw       = sum of capacity_mw for all plants with same owner_name

# Small independent owners are higher-probability sellers
independent_owner    = True if owner_plant_count <= 3

# Ownership complexity — harder/easier to negotiate
multiple_owners_flag = True if multiple owners listed in EIA-860 owner file

# Recent capacity event — worth investigating before outreach
capacity_changed_2025 = from EIA-860M flag
```

---

### BLOCK E — Seasonality & Variability

```python
# Within-year variability: how consistent is the plant's output month to month?
# High variability vs. regional peers may indicate mechanical issues
# (wind farms in the same region have similar seasonal patterns)

# Monthly CF for each month across available years (2018–2025)
cf_month_{MM}_{year} = gen_mwh_{year}_{MM} / (capacity_mw_{year} * days_in_month * 24)

# Average monthly CF across years (shows seasonal pattern)
cf_monthly_avg_{MM} = mean of cf_month_{MM} across 2021–2024

# Summer/winter ratio: Q2+Q3 CF vs Q4+Q1 CF
# Unusual ratios may indicate equipment issues in specific seasons
cf_summer_avg = mean(cf_monthly_avg_04, _05, _06, _07, _08, _09)
cf_winter_avg = mean(cf_monthly_avg_10, _11, _12, _01, _02, _03)
```

---

### BLOCK F — KPI Summary Flags (for dashboard filter panel — not scores)

These are plain boolean flags derived directly from the KPIs above. They are filters, not judgments.

```python
flag_declining_3yr      = True if yoy_3yr_avg < -2.0        # Rolling 3yr avg generation declining
flag_bottom_quartile_cf = True if cf_regional_percentile < 25
flag_peak_decline_15pct = True if decline_from_peak_pct < -15
flag_consec_decline_3yr = True if consecutive_decline_years >= 3
flag_ptc_expired        = True if ptc_expired
flag_repower_candidate  = True if repower_candidate
flag_independent_owner  = True if independent_owner
flag_capacity_change    = True if capacity_changed_2025
flag_data_gap           = True if any generation year 2021–2024 is null
flag_cf_data_error      = True if any cf_data_error_{year} = True in recent 3 years
```

---

### BLOCK G — Validation (print to console after KPI computation)
```
Plants with valid cf_3yr_2022_2024:       {N}
Plants with valid cf_2025:                {N}
Plants flagged declining_3yr:             {N}
Plants flagged bottom_quartile_cf:        {N}
Plants flagged peak_decline_15pct:        {N}
Plants flagged consec_decline_3yr:        {N}
Plants flagged ptc_expired:               {N}
Plants flagged repower_candidate:         {N}
Plants flagged independent_owner:         {N}
Plants flagged capacity_change_2025:      {N}
Plants with cf_data_error:                {N} — list names
Total installed capacity in dataset:      {X} MW (expected 150,000–165,000 MW)
Median cf_3yr_2022_2024:                  {X} (expected 0.28–0.40)
```

---

## STEP 4 — EXCEL MODEL (`scripts/04_export_excel.py`)

Use `openpyxl`. Primary purpose: auditable record, not the working tool. All metric cells in the Metrics tab must use Excel cell-reference formulas — never write Python-computed floats into formula cells.

### Tab 1: `Sources` (leftmost)

**Section A — Source registry.** One row per data source. All URLs clickable (`cell.hyperlink`):

| Field | Content |
|---|---|
| Source Name | Full name |
| Publisher | Agency name |
| Years Covered | e.g. "2018–2024 (annual final)" |
| Description | One sentence |
| Landing Page | Clickable hyperlink |
| Download URL | Clickable hyperlink |
| Local File | Path in data/raw/ |
| Downloaded | Timestamp from manifest |
| MD5 Hash | From manifest |
| Row Count | Records in raw file |
| Data Note | Quality note if applicable |

**Section B — KPI lineage table.** One row per KPI column in wind_plants.csv:

| KPI Column | Formula | Source Fields | Source File |
|---|---|---|---|
| `cf_2024` | `gen_mwh_2024 / (capacity_mw_2024 * 8760)` | EIA-923 + EIA-860 | eia923_2024, eia860_2024 |
| `yoy_pct_2024` | `(gen_per_mw_2024 - gen_per_mw_2023) / gen_per_mw_2023 * 100` | EIA-923 | eia923_2024, eia923_2023 |
| ... (one row per KPI) | | | |

**Section C — Assumptions register:**
All constants (HOURS_PER_YEAR, REFERENCE_PRICE_PER_MWH, CF_CAP, etc.) listed with values and rationale. Analyst can change values in `scripts/03_kpis.py` and rerun.

### Tab 2: `Raw_Data`
Full merged dataset.
- Column `EIA Plant Page (click to verify)`: clickable hyperlink per row → `https://www.eia.gov/electricity/data/browser/#/plant/{plant_id}`
- Column `EIA 860 Source File`
- Column `EIA 923 Source File`
- Column `2025 Data`: "EPM {epm_months_count}/12 months"
- Freeze row 1. Auto-fit columns.

### Tab 3: `KPIs`
All computed KPI columns from `wind_plants_kpis.parquet`.
- Same EIA Plant Page hyperlink column.
- Conditional formatting:
  - Red: `flag_declining_3yr = True` AND `flag_bottom_quartile_cf = True` (both signals)
  - Amber: either flag alone
  - Blue highlight on all 2025 EPM-derived columns with header note
- Freeze row 1.

### Tab 4: `Metrics`
Live Excel formulas only — no hardcoded values. Assumptions block at top (rows 1–12) with named cells. Per-plant rows with CF, age, YoY formulas referencing KPIs tab. Cell A1 note: "All formulas reference source data. Change any value in Raw_Data and metrics update automatically."

### Tab 5: `Summary`
Stats using Excel formulas (not hardcoded):
- Total plants
- Flagged declining 3yr rolling
- Flagged bottom quartile CF
- Flagged PTC expired
- Flagged repower candidate
- Median CF (3yr rolling)
- Total capacity MW
- Bar charts: plants by state (flagged vs. total), CF distribution by NERC region, median CF trend 2018–2025

---

## STEP 5 — STREAMLIT DASHBOARD (`dashboard/app.py`)

`streamlit run dashboard/app.py`

This is the primary working tool. It must load fast, sort on every column, and make every data point verifiable.

### Data loading
```python
df = pd.read_parquet("data/processed/wind_plants_kpis.parquet")
```

### Sidebar — Filters only (no scoring weights)

```
--- PLANT CHARACTERISTICS ---
State:                Multi-select (default: all)
NERC Region:          Multi-select (default: all)
Balancing Authority:  Multi-select (default: all)
Capacity (MW):        Slider 10–500
Asset Age (years):    Slider 0–35
Commissioning Year:   Slider 1990–2024

--- TURBINE ---
Manufacturer:         Multi-select (default: all)
Turbine Age (years):  Slider 0–35
Min Hub Height (m):   Slider 0–150
Min Rotor Diameter:   Slider 0–150

--- DISTRESS FLAGS (checkboxes) ---
[ ] Declining 3yr rolling average
[ ] Bottom quartile CF in region
[ ] 15%+ below peak generation
[ ] 3+ consecutive declining years
[ ] PTC expired (commissioned 2010–2016)
[ ] Repowering candidate (turbines 15+ yrs)
[ ] Independent owner (≤3 plants)
[ ] Capacity change flagged in 2025
[ ] Exclude plants with data gaps

--- OWNER ---
Owner name search:    Text input (partial match)
Max owner portfolio:  Slider 1–50 plants
```

Show at bottom of sidebar: `{N} plants match current filters`

---

### Main Panel

#### Tab 1: Plant Table

Full sortable table of all plants matching sidebar filters.

**Column groups (user can toggle column groups on/off):**

*Identity (always visible):*
- `plant_name`, `state`, `nerc_region`, `owner_name`, `capacity_mw`, `commissioning_year`, `asset_age`
- `EIA Page`: `st.column_config.LinkColumn` — display text "View ↗", links to EIA plant browser

*Capacity Factor:*
- `cf_2024`, `cf_2023`, `cf_2022`
- `cf_3yr_2022_2024` ← highlight this as the primary CF metric
- `cf_3yr_2023_2025` (includes EPM 2025)
- `cf_5yr_2020_2024`
- `cf_7yr_2018_2024`
- `cf_regional_percentile`
- `cf_vs_lbnl_benchmark`

*Production Trend:*
- `yoy_pct_2024`, `yoy_pct_2023`, `yoy_pct_2022`, `yoy_pct_2021`
- `yoy_3yr_avg` ← highlight as primary trend metric
- `trend_direction` (IMPROVING / FLAT / DECLINING)
- `decline_from_peak_pct`
- `peak_year`
- `consecutive_decline_years`
- `cumulative_revenue_lost_usd`

*2025 Signal (EPM):*
- `cf_2025`, `gen_mwh_2025`, `yoy_pct_2025`
- `decline_from_peak_pct_with_2025`
- `epm_months_count`

*Asset Profile:*
- `turbine_manufacturer`, `turbine_model`, `turbine_count`
- `turbine_age`, `hub_height_m`, `rotor_diameter_m`
- `ptc_expired`, `repower_candidate`

*Owner:*
- `owner_name`, `owner_plant_count`, `owner_total_mw`
- `multiple_owners_flag`, `independent_owner`

*Flags:*
- All `flag_*` columns

**Table behavior:**
- Every column is sortable by clicking the header (ascending/descending)
- `st.dataframe` with `column_config` — use `st.column_config.NumberColumn` with `format="%.3f"` for CF columns, `format="%.1f%%"` for YoY columns, `format="$,.0f"` for revenue loss
- Row coloring via pandas Styler:
  - Red background: `flag_declining_3yr AND flag_bottom_quartile_cf`
  - Amber background: either flag alone
  - No color: no flags
- Pagination: 50 rows per page
- `st.download_button("Export this view as CSV")` — exports the current filtered, sorted view

#### Tab 2: Plant Detail

`st.selectbox`: "Select a plant"

On selection, show:

**Identity card** (2-column layout):
All identity fields + owner detail + turbine specs

**Generation history chart** (Plotly bar chart):
- Bars: `gen_mwh_2018` through `gen_mwh_2025`
- 2025 bar in different color with "(EPM)" label in x-axis
- Second y-axis line: `cf_{year}` (capacity factor trend)
- Horizontal dashed line: plant's own peak generation year
- Horizontal dashed line: regional CF median (from cf_regional_percentile calculation)
- On hover: year, MWh, CF, YoY change, capacity that year

**Rolling average chart** (Plotly line chart):
- Lines: `cf_3yr_2022_2024` trend plotted across all available 3yr windows
- Shaded band showing ±1 std dev of regional peers
- Labels each data point

**Monthly seasonality heatmap** (Plotly):
- X axis: months (Jan–Dec)
- Y axis: years (2018–2025)
- Color: CF for that month/year
- Gaps in data shown as gray
- Reveals seasonal anomalies (e.g., summer 2022 was unusually bad)

**Flag summary:**
Show all `flag_*` columns for this plant as a simple Yes/No table with a one-line explanation of what each flag means.

**Source verification panel** (st.expander: "Verify this plant's data"):
```
EIA Plant Page:     [link] https://www.eia.gov/electricity/data/browser/#/plant/{id}
EIA 860 source:     {eia860_file}, row {eia860_row}
EIA 923 sources:    eia923_2018.xlsx through eia923_2024.xlsx
2025 data:          EIA Electric Power Monthly — {epm_months_count}/12 months
USWTDB match:       {matched / not matched}
eGRID match:        {matched / not matched}
Capacity change:    {flagged / not flagged in 860M}
```
Every source name links to its landing page URL.

#### Tab 3: Regional Analysis

Aggregated view by NERC region + state.

- Table: NERC region | median CF 3yr | % plants declining | % PTC expired | total capacity MW | plant count
- Bar chart: median CF by region (sorted)
- Scatter: plant age vs. CF for all plants, colored by region — shows whether older plants in a given region have lower CF
- All charts use Plotly. All sortable/filterable by region selection.

#### Tab 4: Trend Analysis

Fleet-wide view over time.

- Line chart: median CF by year (2018–2025) across all plants in current filter
- Line chart: % of plants with declining YoY by year
- Bar chart: rolling 3yr avg CF distribution (histogram) — see the shape of the fleet
- Toggle: show/hide 2025 EPM data on all charts

**Data freshness panel** (always visible at top of this tab):
```
EIA 860/923 (2018–2024):    Final annual data — downloaded {date}
EPM 2025 (Jan–Dec 2025):    Monthly data — downloaded {date}  |  {N}/12 months
Next EPM release:            March 24, 2026 (January 2026 data)
```

---

## STEP 5 — VERIFICATION (`scripts/05_verify.py`)

Produces `outputs/audit/validation_report.txt`. Run after all other scripts.

**Check 1 — File integrity:** Re-compute MD5 for each raw file, compare to manifest.

**Check 2 — Plant count:** Total ≥10 MW wind plants should be 900–2,100. Total capacity 120,000–175,000 MW.

**Check 3 — 2024 generation cross-check:**
```
Sum gen_mwh_2024. EIA-published U.S. wind total 2024: ~451 TWh.
Expected dataset coverage: 85–95%.
Print: "Dataset 2024 total: {X} MWh ({pct}% of ~451 TWh)"
Flag < 70% as integrity issue.
```

**Check 4 — 2025 EPM cross-check:**
```
Sum gen_mwh_2025. EIA-published 2025 wind total: ~464 TWh.
Print: "Dataset 2025 EPM total: {X} MWh ({pct}% of ~464 TWh)"
```

**Check 5 — CF range:** No `cf_3yr_2022_2024 > 0.65`. Assert. Print median.

**Check 6 — Rolling average consistency:** For every plant where `cf_3yr_2022_2024` is non-null, verify it equals `mean(cf_2022, cf_2023, cf_2024)` within 0.001. Sample 100 random plants.

**Check 7 — Hyperlinks:** First 10 rows of EIA Plant Page column have valid `cell.hyperlink` objects following pattern `https://www.eia.gov/electricity/data/browser/#/plant/{integer}`.

**Check 8 — Source trace:** Every plant in `wind_plants.csv` has an entry in `source_trace.csv` with non-null `eia_plant_url` and `epm_months_count`.

**Check 9 — Flag logic consistency:**
- `flag_consec_decline_3yr = True` requires `consecutive_decline_years >= 3`. Assert.
- `flag_ptc_expired = True` requires `10 <= asset_age <= 16`. Assert.
- `flag_repower_candidate = True` requires `turbine_age >= 15 AND asset_age >= 10`. Assert.
- Any plant with `flag_declining_3yr = True` must have non-null `yoy_3yr_avg`. Assert.

**Report format:**
```
=== Wind Farm Screener Validation Report ===
Generated:      {timestamp}
Data coverage:  EIA-860/923 annual final 2018–2024 | EPM monthly Jan–Dec 2025

CHECK 1 — File integrity:            PASS / FAIL
CHECK 2 — Plant count:               PASS / WARN / FAIL  {N} plants, {X} MW
CHECK 3 — 2024 generation total:     PASS / WARN / FAIL  {pct}% coverage
CHECK 4 — 2025 EPM total:            PASS / WARN / FAIL  {pct}% coverage
CHECK 5 — CF range:                  PASS / WARN / FAIL  median={x}
CHECK 6 — Rolling avg consistency:   PASS / FAIL
CHECK 7 — Hyperlinks:                PASS / FAIL
CHECK 8 — Source trace:              PASS / FAIL
CHECK 9 — Flag logic:                PASS / FAIL

OVERALL: PASS / FAIL
```

---

## README (`README.md`)

Sections:
1. What this is (3 sentences)
2. Setup: `pip install -r requirements.txt`
3. Run order: `01_download.py` → `02_clean_merge.py` → `03_kpis.py` → `04_export_excel.py` → `05_verify.py` → `streamlit run dashboard/app.py`
4. Data sources table: name | publisher | URL | years | what fields are used
5. How to verify any number: click EIA Plant Page link → Sources tab in Excel → raw files in data/raw/
6. KPI definitions: every KPI, its formula, its source fields
7. Monthly refresh: re-run `01_download.py` on or after the 24th of each month for new EPM data
8. 2025 annual update: when EIA releases 2025 annual EIA-923 (expected June 2026), replace EPM data in `02_clean_merge.py` and re-run
9. Known limitations: curtailment (not in EIA data), PPA terms, SCADA downtime, transmission constraints, ownership lag

---

## REQUIREMENTS FILE

```
pandas==2.2.2
numpy==1.26.4
openpyxl==3.1.2
requests==2.31.0
streamlit==1.32.0
plotly==5.20.0
pyarrow==15.0.2
xlrd==2.0.1
tqdm==4.66.2
```

---

## EXECUTION ORDER AND GATES

```
01_download.py   → GATE: manifest written, all years downloaded, EPM 12/12 months, spot checks pass
02_clean_merge.py → GATE: merged parquet written, source_trace.csv written, merge_log.txt complete
03_kpis.py       → GATE: kpi parquet written, capacity check >110,000 MW, all flag assertions pass
04_export_excel.py → GATE: xlsx written, all 5 tabs present, hyperlinks verified
05_verify.py     → GATE: OVERALL: PASS in validation_report.txt
dashboard        → launch only after 05_verify.py PASS
```

After each script:
```
✓ {script_name} complete
  Input rows:           {N}
  Output rows:          {N}
  Rows dropped:         {N} — see merge_log.txt
  EPM months loaded:    {N}/12
  Warnings:             {N}
  Elapsed:              {X}s
```
