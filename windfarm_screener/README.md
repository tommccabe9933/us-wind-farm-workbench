# Wind Farm Investment Screener

## What This Is

A data pipeline and interactive Streamlit dashboard that screens approximately 1,500 U.S. wind farms (10 MW and above) for distressed investment signals relevant to private equity acquisition. All underlying data is sourced exclusively from U.S. federal government agencies, including the Energy Information Administration (EIA), the U.S. Geological Survey (USGS), the Environmental Protection Agency (EPA), and the Department of Energy (DOE). Every data point displayed in the dashboard links directly to its original government source for independent verification.

---

## Setup

Install Python dependencies:

```bash
pip install -r requirements.txt
```

You will also need an EIA API key. Register for a free key at:

https://www.eia.gov/opendata/register.php

Then set the key as an environment variable:

```bash
export EIA_API_KEY=your_key_here
```

Or create a `.env` file in the project root:

```
EIA_API_KEY=your_key_here
```

---

## Run Order

Execute the pipeline scripts in sequence, then launch the dashboard:

```bash
python scripts/01_download.py        # Download raw data from federal sources
python scripts/02_clean_merge.py     # Clean, normalize, and merge datasets
python scripts/03_kpis.py            # Compute all screening KPIs
python scripts/04_export_excel.py    # Export results to Excel with source links
python scripts/05_verify.py          # Run data integrity checks
streamlit run dashboard/app.py       # Launch the interactive dashboard
```

---

## Data Sources

| Source | Publisher | URL | Years | Fields Used |
|--------|-----------|-----|-------|-------------|
| EIA-860 | U.S. Energy Information Administration | https://www.eia.gov/electricity/data/eia860/ | 2001--2024 | Plant metadata, nameplate capacity, turbine counts, installation year, operating status, ownership stakes, utility affiliations |
| EIA-923 | U.S. Energy Information Administration | https://www.eia.gov/electricity/data/eia923/ | 2001--2024 | Annual net generation (MWh) by plant and prime mover, fuel consumption, capacity factor inputs |
| Electric Power Monthly (EPM) | U.S. Energy Information Administration | https://www.eia.gov/electricity/monthly/ | 2024--2025 (monthly) | Monthly net generation by plant, used to extend annual EIA-923 with recent monthly production data |
| EIA-860M | U.S. Energy Information Administration | https://www.eia.gov/electricity/data/eia860m/ | Current month | Preliminary operating status updates, planned retirements, capacity changes not yet in annual filings |
| U.S. Wind Turbine Database (USWTDB) | U.S. Geological Survey / DOE / LBNL | https://eerscmap.usgs.gov/uswtdb/ | Through 2024 | Individual turbine locations, hub heights, rotor diameters, turbine models, manufacturer, project boundaries |
| eGRID | U.S. Environmental Protection Agency | https://www.epa.gov/egrid | 2022 | Emissions rates, heat rates, grid region mappings, plant-level environmental performance benchmarks |
| LBNL Wind Technologies Market Report | Lawrence Berkeley National Laboratory / DOE | https://emp.lbl.gov/wind-technologies-market-report | Annual | Benchmark capacity factors by vintage and region, PPA price trends, cost benchmarks for contextual comparison |

---

## How to Verify Any Number

Every figure in the dashboard and Excel output can be traced back to its original government source through three methods:

1. **EIA Plant Page link** -- Each plant row includes a direct URL to its EIA plant detail page (e.g., `https://www.eia.gov/electricity/data/browser/#/plant/XXXXX`). Click through to confirm reported capacity and generation.

2. **Sources tab in Excel** -- The exported Excel workbook includes a Sources tab listing, for each data field, the originating dataset, file name, and download URL.

3. **Raw files in `data/raw/`** -- All downloaded source files are preserved unmodified in `data/raw/`. Any computed value can be retraced to the specific rows in these files.

---

## KPI Definitions

### Capacity Factor

| KPI | Formula | Source Fields |
|-----|---------|---------------|
| Annual Capacity Factor | `net_generation_mwh / (nameplate_capacity_mw * 8,760)` | EIA-923 net generation, EIA-860 nameplate capacity |
| Lifetime Average Capacity Factor | Mean of all annual capacity factors since commercial operation date | EIA-923 net generation (all years), EIA-860 nameplate capacity and COD |
| Capacity Factor vs. Regional Benchmark | `plant_cf / lbnl_regional_benchmark_cf` | Computed CF, LBNL benchmark by vintage and region |
| Capacity Factor Percentile | Percentile rank among all plants of same vintage (install year) | Computed CF, EIA-860 install year |

### Production Trend

| KPI | Formula | Source Fields |
|-----|---------|---------------|
| 3-Year Production Trend | Linear regression slope of annual net generation over the most recent 3 years, normalized by mean generation | EIA-923 net generation (3 most recent years) |
| 5-Year Production Trend | Linear regression slope of annual net generation over the most recent 5 years, normalized by mean generation | EIA-923 net generation (5 most recent years) |
| Year-over-Year Change | `(current_year_gen - prior_year_gen) / prior_year_gen` | EIA-923 net generation (2 most recent years) |
| Recent Monthly Trend | Linear regression slope of monthly net generation over trailing 12 months | EPM monthly net generation |

### Asset Profile

| KPI | Formula | Source Fields |
|-----|---------|---------------|
| Plant Age | `current_year - operating_year` | EIA-860 operating year |
| Nameplate Capacity (MW) | Direct from source | EIA-860 nameplate capacity |
| Number of Turbines | Count of turbines mapped to plant | USWTDB turbine records |
| Average Turbine Size (MW) | `nameplate_capacity_mw / turbine_count` | EIA-860 nameplate capacity, USWTDB turbine count |
| Turbine Model and Manufacturer | Direct from source | USWTDB turbine model, manufacturer |
| Hub Height (m) | Average hub height across turbines at site | USWTDB hub height |
| Rotor Diameter (m) | Average rotor diameter across turbines at site | USWTDB rotor diameter |

### Owner Signals

| KPI | Formula | Source Fields |
|-----|---------|---------------|
| Current Owner | Most recent owner of record | EIA-860 ownership schedule |
| Owner Type | Classification (utility, IPP, financial) | EIA-860 entity type |
| Ownership Change Count | Number of distinct owners across all EIA-860 filings | EIA-860 ownership history |
| Multi-Owner Flag | Whether plant has multiple concurrent ownership stakes | EIA-860 ownership percentages |
| Planned Retirement Date | Reported planned retirement, if any | EIA-860M retirement schedule |

### Seasonality

| KPI | Formula | Source Fields |
|-----|---------|---------------|
| Monthly Generation Profile | Net generation by calendar month (trailing 12 months) | EPM monthly net generation |
| Peak Month | Calendar month with highest average generation | EPM monthly net generation |
| Seasonal Ratio | `max_monthly_gen / min_monthly_gen` | EPM monthly net generation |
| Winter Capacity Factor | Capacity factor for Dec--Feb | EPM monthly net generation, EIA-860 nameplate capacity |
| Summer Capacity Factor | Capacity factor for Jun--Aug | EPM monthly net generation, EIA-860 nameplate capacity |

### Flags

| Flag | Condition | Source Fields |
|------|-----------|---------------|
| Underperforming | Capacity factor below 20% in most recent year | Computed annual CF |
| Declining Production | Negative 3-year production trend exceeding -10% | Computed 3-year trend |
| Aging Asset | Plant age exceeds 15 years | EIA-860 operating year |
| Below Benchmark | Capacity factor below 75% of regional vintage benchmark | Computed CF, LBNL benchmark |
| Retirement Risk | Planned retirement date within 5 years per EIA-860M | EIA-860M retirement schedule |
| Owner Turnover | Three or more ownership changes on record | Computed ownership change count |

---

## Monthly Refresh

The Electric Power Monthly (EPM) dataset is updated by EIA on or around the 24th of each month. To pull in the latest monthly generation data:

```bash
python scripts/01_download.py
python scripts/02_clean_merge.py
python scripts/03_kpis.py
python scripts/04_export_excel.py
python scripts/05_verify.py
```

Re-running the full pipeline will fetch the newest EPM release and recompute all KPIs. No configuration changes are needed.

---

## 2025 Annual Update

EIA publishes final annual EIA-923 generation data with a roughly 18-month lag. The 2025 annual EIA-923 release is expected in June 2026. When it becomes available:

1. Update the EIA-923 data path in `scripts/02_clean_merge.py` to include the 2025 annual file.
2. Re-run the full pipeline (`01_download.py` through `05_verify.py`).

The 2025 annual data will replace the monthly EPM estimates for that year, providing final audited generation figures.

---

## Known Limitations

- **Curtailment**: EIA data does not distinguish between low wind resource and grid-ordered curtailment. A plant showing low capacity factor may be curtailed rather than underperforming. This distinction requires SCADA or curtailment records not available in public data.

- **PPA terms**: Power purchase agreement pricing, tenor, and counterparty details are not published by EIA or any other federal source. PPA economics must be obtained through commercial data providers or direct negotiation.

- **SCADA downtime**: Planned and unplanned turbine downtime is not reported to EIA. Availability losses are embedded in generation figures and cannot be separated without operator-level data.

- **Transmission constraints**: Interconnection queue position, curtailment due to transmission congestion, and grid upgrade requirements are managed by regional ISOs/RTOs and are not captured in EIA plant-level data.

- **Ownership lag in EIA-860**: Ownership records in EIA-860 reflect the most recent annual filing (typically finalized 6--12 months after the reporting year). Recent transactions may not yet appear. The EIA-860M monthly supplement provides some interim updates but is limited in scope.
