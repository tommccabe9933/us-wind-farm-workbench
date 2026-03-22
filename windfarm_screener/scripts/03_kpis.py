"""
03_kpis.py — Compute all KPIs for the Wind Farm Investment Screener.

Input:  data/processed/wind_plants_merged.parquet
Output: data/processed/wind_plants_kpis.parquet
        outputs/wind_plants.csv

Blocks:
  A — Capacity Factor (efficiency)
  B — Production Trend (direction)
  C — Asset Profile (what kind of asset)
  D — Owner & Acquisition Signals
  E — Seasonality & Variability
  F — KPI Summary Flags
  G — Validation (console output)
"""

import time
import sys
from pathlib import Path
from calendar import monthrange

import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
PROC_DIR = BASE_DIR / "data" / "processed"
EXT_DIR = BASE_DIR / "data" / "external"
OUT_DIR = BASE_DIR / "outputs"

# ── Constants (all adjustable) ─────────────────────────────────────────────────
HOURS_PER_YEAR = 8760
CURRENT_YEAR = 2026
MIN_CAPACITY_MW = 10
CF_CAP = 0.65          # Above this = data error flag
REFERENCE_PRICE_PER_MWH = 30  # USD, for cumulative revenue loss estimate

YEARS = list(range(2018, 2025))  # 2018–2024
ALL_YEARS = list(range(2018, 2026))  # Including 2025
MONTHS = [f"{m:02d}" for m in range(1, 13)]


def load_lbnl_benchmarks():
    """Load LBNL regional CF benchmarks."""
    # Try importing the fallback module
    fallback_path = EXT_DIR / "lbnl_benchmarks_manual.py"
    if fallback_path.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("lbnl_benchmarks", fallback_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.get_benchmark
    return None


def main():
    start = time.time()
    print("=" * 70)
    print("  Wind Farm Screener — KPI Computation")
    print("=" * 70)

    # Load merged data
    input_path = PROC_DIR / "wind_plants_merged.parquet"
    if not input_path.exists():
        print(f"✗ Input not found: {input_path}")
        print("  Run 02_clean_merge.py first.")
        sys.exit(1)

    df = pd.read_parquet(input_path)
    input_rows = len(df)
    print(f"\nLoaded {input_rows} plants from merged dataset")

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK A — Capacity Factor
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── Block A: Capacity Factor ──")

    # Annual CF per year (2018–2024)
    # CF = gen_mwh / (capacity_mw * 8760)
    for year in YEARS:
        gen_col = f"gen_mwh_{year}"
        cap_col = f"capacity_mw_{year}"
        cf_col = f"cf_{year}"

        if gen_col in df.columns and cap_col in df.columns:
            df[cf_col] = df[gen_col] / (df[cap_col] * HOURS_PER_YEAR)
        elif gen_col in df.columns:
            # Fall back to nearest available capacity
            for fallback_year in [year - 1, year + 1, year - 2, 2024]:
                fb_col = f"capacity_mw_{fallback_year}"
                if fb_col in df.columns:
                    df[cf_col] = df[gen_col] / (df[fb_col] * HOURS_PER_YEAR)
                    break

        # Data error flags
        if cf_col in df.columns:
            df[f"cf_data_error_{year}"] = df[cf_col] > CF_CAP
            df[f"cf_zero_{year}"] = df[cf_col] <= 0
            # Cap at CF_CAP for display but keep flag
            errors = df[f"cf_data_error_{year}"].sum()
            if errors > 0:
                print(f"  cf_{year}: {errors} plants with CF > {CF_CAP} (flagged)")

    # CF 2025: uses 2024 capacity as denominator
    if "gen_mwh_2025" in df.columns and "capacity_mw_2024" in df.columns:
        df["cf_2025"] = df["gen_mwh_2025"] / (df["capacity_mw_2024"] * HOURS_PER_YEAR)
        df["cf_data_error_2025"] = df["cf_2025"] > CF_CAP
        df["cf_zero_2025"] = df["cf_2025"] <= 0

    # Rolling average CFs
    # 3-year rolling: require min 2 valid years
    cf_2022_2024 = df[[f"cf_{y}" for y in [2022, 2023, 2024] if f"cf_{y}" in df.columns]]
    if len(cf_2022_2024.columns) >= 2:
        valid_count = cf_2022_2024.notna().sum(axis=1)
        df["cf_3yr_2022_2024"] = cf_2022_2024.mean(axis=1)
        df.loc[valid_count < 2, "cf_3yr_2022_2024"] = np.nan

    cf_2023_2025 = df[[f"cf_{y}" for y in [2023, 2024, 2025] if f"cf_{y}" in df.columns]]
    if len(cf_2023_2025.columns) >= 2:
        valid_count = cf_2023_2025.notna().sum(axis=1)
        df["cf_3yr_2023_2025"] = cf_2023_2025.mean(axis=1)
        df.loc[valid_count < 2, "cf_3yr_2023_2025"] = np.nan

    # 5-year rolling: require min 3 valid years
    cf_5yr_cols = [f"cf_{y}" for y in range(2020, 2025) if f"cf_{y}" in df.columns]
    if len(cf_5yr_cols) >= 3:
        cf_5yr = df[cf_5yr_cols]
        valid_count = cf_5yr.notna().sum(axis=1)
        df["cf_5yr_2020_2024"] = cf_5yr.mean(axis=1)
        df.loc[valid_count < 3, "cf_5yr_2020_2024"] = np.nan

    # 7-year rolling: require min 5 valid years
    cf_7yr_cols = [f"cf_{y}" for y in YEARS if f"cf_{y}" in df.columns]
    if len(cf_7yr_cols) >= 5:
        cf_7yr = df[cf_7yr_cols]
        valid_count = cf_7yr.notna().sum(axis=1)
        df["cf_7yr_2018_2024"] = cf_7yr.mean(axis=1)
        df.loc[valid_count < 5, "cf_7yr_2018_2024"] = np.nan

    # Determine "latest" CF column: prefer 2025 if available, else 2024
    cf_latest_col = "cf_2025" if "cf_2025" in df.columns and df["cf_2025"].notna().sum() > 100 else "cf_2024"
    df["cf_latest"] = df[cf_latest_col] if cf_latest_col in df.columns else np.nan

    # CF vs. regional peers (percentile rank within NERC region)
    if "cf_3yr_2022_2024" in df.columns and "nerc_region" in df.columns:
        df["cf_regional_percentile"] = df.groupby("nerc_region")["cf_3yr_2022_2024"].rank(pct=True) * 100
        df.loc[df["nerc_region"].isna(), "cf_regional_percentile"] = np.nan

    # National percentile (rank across ALL plants)
    if "cf_3yr_2022_2024" in df.columns:
        df["national_pctile"] = df["cf_3yr_2022_2024"].rank(pct=True) * 100

    # Regional median CF (for underperformance gap)
    if "cf_latest" in df.columns and "nerc_region" in df.columns:
        regional_medians = df.groupby("nerc_region")["cf_latest"].median()
        df["regional_median_cf"] = df["nerc_region"].map(regional_medians)
        df["underperformance_gap"] = df["cf_latest"] - df["regional_median_cf"]
        df.loc[df["nerc_region"].isna(), "underperformance_gap"] = np.nan
        df.loc[df["nerc_region"].isna(), "regional_median_cf"] = np.nan

    # CF vs. LBNL benchmark
    get_benchmark = load_lbnl_benchmarks()
    if get_benchmark and "cf_3yr_2022_2024" in df.columns:
        df["lbnl_benchmark_cf"] = df.apply(
            lambda row: get_benchmark(
                row.get("nerc_region"),
                row.get("commissioning_year")
            ), axis=1)
        df["cf_vs_lbnl_benchmark"] = df["cf_3yr_2022_2024"] - df["lbnl_benchmark_cf"]
    else:
        df["lbnl_benchmark_cf"] = np.nan
        df["cf_vs_lbnl_benchmark"] = np.nan

    print(f"  ✓ Capacity factors computed for {ALL_YEARS}")

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK B — Production Trend
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── Block B: Production Trend ──")

    # Capacity-normalized generation per year
    # gen_per_mw = gen_mwh / capacity_mw — removes capacity-change distortion
    for year in YEARS:
        gen_col = f"gen_mwh_{year}"
        cap_col = f"capacity_mw_{year}"
        if gen_col in df.columns and cap_col in df.columns:
            df[f"gen_per_mw_{year}"] = df[gen_col] / df[cap_col]

    if "gen_mwh_2025" in df.columns and "capacity_mw_2024" in df.columns:
        df["gen_per_mw_2025"] = df["gen_mwh_2025"] / df["capacity_mw_2024"]

    # Year-over-year change (capacity-adjusted)
    for year in range(2019, 2026):
        curr = f"gen_per_mw_{year}"
        prev = f"gen_per_mw_{year - 1}"
        if curr in df.columns and prev in df.columns:
            df[f"yoy_pct_{year}"] = ((df[curr] - df[prev]) / df[prev]) * 100

    # Rolling average YoY (3 years)
    yoy_cols_3yr = [f"yoy_pct_{y}" for y in [2022, 2023, 2024] if f"yoy_pct_{y}" in df.columns]
    if yoy_cols_3yr:
        df["yoy_3yr_avg"] = df[yoy_cols_3yr].mean(axis=1)
    else:
        df["yoy_3yr_avg"] = np.nan

    # Trend direction
    df["trend_direction"] = "FLAT"
    df.loc[df["yoy_3yr_avg"] > 2, "trend_direction"] = "IMPROVING"
    df.loc[df["yoy_3yr_avg"] < -2, "trend_direction"] = "DECLINING"
    df.loc[df["yoy_3yr_avg"].isna(), "trend_direction"] = np.nan

    # Peak generation and decline from peak
    gen_per_mw_cols = [f"gen_per_mw_{y}" for y in YEARS if f"gen_per_mw_{y}" in df.columns]
    if gen_per_mw_cols:
        gen_per_mw_df = df[gen_per_mw_cols]
        df["peak_gen_per_mw"] = gen_per_mw_df.max(axis=1)
        df["peak_year"] = gen_per_mw_df.idxmax(axis=1).str.extract(r"(\d{4})").astype(float)

        if "gen_per_mw_2024" in df.columns:
            df["decline_from_peak_pct"] = (
                (df["gen_per_mw_2024"] - df["peak_gen_per_mw"]) / df["peak_gen_per_mw"] * 100
            )

        if "gen_per_mw_2025" in df.columns:
            df["decline_from_peak_pct_with_2025"] = (
                (df["gen_per_mw_2025"] - df["peak_gen_per_mw"]) / df["peak_gen_per_mw"] * 100
            )

    # Consecutive decline years (count backward from 2024)
    def count_consecutive_declines(row):
        count = 0
        for year in range(2024, 2018, -1):
            curr = row.get(f"gen_per_mw_{year}")
            prev = row.get(f"gen_per_mw_{year - 1}")
            if pd.notna(curr) and pd.notna(prev) and curr < prev:
                count += 1
            else:
                break
        return count

    df["consecutive_decline_years"] = df.apply(count_consecutive_declines, axis=1)

    # Cumulative production loss vs. peak (2022–2024)
    # MWh lost = (peak_gen_per_mw * capacity * 8760) - actual gen
    # Only count years where actual < peak
    df["cumulative_mwh_lost_2022_2024"] = 0.0
    for year in [2022, 2023, 2024]:
        gen_col = f"gen_mwh_{year}"
        cap_col = f"capacity_mw_{year}"
        if gen_col in df.columns and cap_col in df.columns and "peak_gen_per_mw" in df.columns:
            peak_theoretical = df["peak_gen_per_mw"] * df[cap_col]
            shortfall = peak_theoretical - df[gen_col]
            shortfall = shortfall.clip(lower=0)  # Only count underperformance
            df["cumulative_mwh_lost_2022_2024"] += shortfall.fillna(0)

    df["cumulative_revenue_lost_usd"] = df["cumulative_mwh_lost_2022_2024"] * REFERENCE_PRICE_PER_MWH

    print(f"  ✓ Production trends computed")

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK C — Asset Profile
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── Block C: Asset Profile ──")

    if "commissioning_year" in df.columns:
        df["asset_age"] = CURRENT_YEAR - df["commissioning_year"]
    else:
        df["asset_age"] = np.nan

    if "turbine_vintage_min" in df.columns:
        df["turbine_age"] = CURRENT_YEAR - df["turbine_vintage_min"]
    else:
        df["turbine_age"] = np.nan

    # PTC expiry: 10-year federal Production Tax Credit
    # Active: age < 10, Expiring: age 10-12, Expired: age > 12
    df["ptc_expired"] = df["asset_age"] > 12
    df.loc[df["asset_age"].isna(), "ptc_expired"] = False

    # PTC status text column
    df["ptc_status"] = "Active"
    df.loc[(df["asset_age"] >= 10) & (df["asset_age"] <= 12), "ptc_status"] = "Expiring"
    df.loc[df["asset_age"] > 12, "ptc_status"] = "Expired"
    df.loc[df["asset_age"].isna(), "ptc_status"] = "Unknown"

    # Repowering candidate: turbines old enough for full repower + proven wind resource
    df["repower_candidate"] = False
    if "turbine_age" in df.columns:
        df["repower_candidate"] = (
            (df["turbine_age"] >= 15) & (df["asset_age"] >= 10)
        )
        df.loc[df["turbine_age"].isna() | df["asset_age"].isna(), "repower_candidate"] = False

    print(f"  ✓ Asset profiles computed")

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK D — Owner & Acquisition Signals
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── Block D: Owner & Acquisition Signals ──")

    if "owner_name" in df.columns:
        # Owner portfolio size
        owner_stats = df.groupby("owner_name").agg(
            owner_plant_count=("plant_id", "count"),
            owner_total_mw=("capacity_mw_2024", "sum")
        ).reset_index()

        df = df.merge(owner_stats, on="owner_name", how="left")

        # Independent owner: ≤3 plants
        df["independent_owner"] = df["owner_plant_count"] <= 3
        df.loc[df["owner_name"].isna(), "independent_owner"] = False
    else:
        df["owner_plant_count"] = np.nan
        df["owner_total_mw"] = np.nan
        df["independent_owner"] = False

    if "multiple_owners" not in df.columns:
        df["multiple_owners"] = False

    # Rename for consistency
    if "multiple_owners" in df.columns:
        df["multiple_owners_flag"] = df["multiple_owners"]

    print(f"  ✓ Owner signals computed")

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK E — Seasonality & Variability
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── Block E: Seasonality & Variability ──")

    # Monthly CF for each month across available years
    for year in ALL_YEARS:
        cap_col = f"capacity_mw_{year}" if year < 2025 else "capacity_mw_2024"
        if cap_col not in df.columns:
            continue

        for mm_int in range(1, 13):
            mm = f"{mm_int:02d}"
            gen_col = f"gen_mwh_{year}_{mm}"
            if gen_col in df.columns:
                days = monthrange(year, mm_int)[1]
                hours = days * 24
                df[f"cf_month_{mm}_{year}"] = df[gen_col] / (df[cap_col] * hours)

    # Average monthly CF across 2021–2024
    for mm_int in range(1, 13):
        mm = f"{mm_int:02d}"
        yearly_cf_cols = [f"cf_month_{mm}_{y}" for y in range(2021, 2025) if f"cf_month_{mm}_{y}" in df.columns]
        if yearly_cf_cols:
            df[f"cf_monthly_avg_{mm}"] = df[yearly_cf_cols].mean(axis=1)

    # Summer/winter ratio
    summer_cols = [f"cf_monthly_avg_{mm}" for mm in ["04", "05", "06", "07", "08", "09"]
                   if f"cf_monthly_avg_{mm}" in df.columns]
    winter_cols = [f"cf_monthly_avg_{mm}" for mm in ["10", "11", "12", "01", "02", "03"]
                   if f"cf_monthly_avg_{mm}" in df.columns]

    if summer_cols:
        df["cf_summer_avg"] = df[summer_cols].mean(axis=1)
    if winter_cols:
        df["cf_winter_avg"] = df[winter_cols].mean(axis=1)

    print(f"  ✓ Seasonality metrics computed")

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK F — KPI Summary Flags
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── Block F: Summary Flags ──")

    # ── 10 Distress Signal Flags (design doc naming) ─────────────────────────

    # 1. flag_declining_3yr: rolling 3yr avg generation declining > 2%
    df["flag_declining_3yr"] = df.get("yoy_3yr_avg", pd.Series(dtype=float)) < -2.0

    # 2. flag_bottom_quartile: bottom 25th percentile in NERC region
    df["flag_bottom_quartile"] = df.get("cf_regional_percentile",
                                        pd.Series(dtype=float)) < 25

    # 3. flag_below_peak: 15%+ below peak generation
    df["flag_below_peak"] = df.get("decline_from_peak_pct",
                                    pd.Series(dtype=float)) < -15

    # 4. flag_consecutive_decline: 3+ consecutive declining years
    df["flag_consecutive_decline"] = df.get("consecutive_decline_years",
                                            pd.Series(dtype=int)) >= 3

    # 5. flag_ptc_expired
    df["flag_ptc_expired"] = df["ptc_expired"]

    # 6. flag_repower_candidate
    df["flag_repower_candidate"] = df["repower_candidate"]

    # 7. flag_independent_owner
    df["flag_independent_owner"] = df["independent_owner"]

    # 8. flag_capacity_changed
    df["flag_capacity_changed"] = df.get("capacity_changed_2025", False)

    # 9. flag_high_cf: any CF data error (> 0.65) in recent 3 years
    error_cols = [f"cf_data_error_{y}" for y in [2022, 2023, 2024] if f"cf_data_error_{y}" in df.columns]
    if error_cols:
        df["flag_high_cf"] = df[error_cols].any(axis=1)
    else:
        df["flag_high_cf"] = False

    # 10. flag_data_gap: any generation year 2021–2024 is null
    gap_cols = [f"gen_mwh_{y}" for y in range(2021, 2025) if f"gen_mwh_{y}" in df.columns]
    if gap_cols:
        df["flag_data_gap"] = df[gap_cols].isna().any(axis=1)
    else:
        df["flag_data_gap"] = True

    # Ensure all flag columns are boolean, not object
    flag_cols = [c for c in df.columns if c.startswith("flag_")]
    for fc in flag_cols:
        df[fc] = df[fc].fillna(False).astype(bool)

    # Distress signal count: sum of the 10 core flags
    distress_flags = [
        "flag_declining_3yr", "flag_bottom_quartile", "flag_below_peak",
        "flag_consecutive_decline", "flag_ptc_expired", "flag_repower_candidate",
        "flag_independent_owner", "flag_capacity_changed", "flag_high_cf", "flag_data_gap"
    ]
    existing_flags = [f for f in distress_flags if f in df.columns]
    df["distress_signal_count"] = df[existing_flags].sum(axis=1).astype(int)

    print(f"  ✓ {len(flag_cols)} flag columns created")
    print(f"  ✓ distress_signal_count: median={df['distress_signal_count'].median():.0f}, max={df['distress_signal_count'].max()}")

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK G — Validation
    # ══════════════════════════════════════════════════════════════════════════
    print("\n── Block G: Validation ──")

    v = {
        "valid_cf_3yr_2022_2024": df["cf_3yr_2022_2024"].notna().sum() if "cf_3yr_2022_2024" in df.columns else 0,
        "valid_cf_2025": df["cf_2025"].notna().sum() if "cf_2025" in df.columns else 0,
        "declining_3yr": df["flag_declining_3yr"].sum(),
        "bottom_quartile": df["flag_bottom_quartile"].sum(),
        "below_peak": df["flag_below_peak"].sum(),
        "consecutive_decline": df["flag_consecutive_decline"].sum(),
        "ptc_expired": df["flag_ptc_expired"].sum(),
        "repower_candidate": df["flag_repower_candidate"].sum(),
        "independent_owner": df["flag_independent_owner"].sum(),
        "capacity_changed": df["flag_capacity_changed"].sum(),
        "high_cf": df["flag_high_cf"].sum(),
        "data_gap": df["flag_data_gap"].sum(),
    }

    # Total capacity
    cap_col = "capacity_mw_2024" if "capacity_mw_2024" in df.columns else None
    total_cap = df[cap_col].sum() if cap_col else 0

    # Median CF
    median_cf = df["cf_3yr_2022_2024"].median() if "cf_3yr_2022_2024" in df.columns else 0

    # New column stats
    gap_median = df["underperformance_gap"].median() if "underperformance_gap" in df.columns else 0

    print(f"Plants with valid cf_3yr_2022_2024:       {v['valid_cf_3yr_2022_2024']}")
    print(f"Plants with valid cf_2025:                {v['valid_cf_2025']}")
    print(f"Plants flagged declining_3yr:             {v['declining_3yr']}")
    print(f"Plants flagged bottom_quartile:           {v['bottom_quartile']}")
    print(f"Plants flagged below_peak:                {v['below_peak']}")
    print(f"Plants flagged consecutive_decline:       {v['consecutive_decline']}")
    print(f"Plants flagged ptc_expired:               {v['ptc_expired']}")
    print(f"Plants flagged repower_candidate:         {v['repower_candidate']}")
    print(f"Plants flagged independent_owner:         {v['independent_owner']}")
    print(f"Plants flagged capacity_changed:          {v['capacity_changed']}")
    print(f"Plants with high_cf flag:                 {v['high_cf']}")
    print(f"Plants with data_gap flag:                {v['data_gap']}")
    print(f"Median underperformance gap:              {gap_median:.4f}")

    # List plants with high CF flag
    if v['high_cf'] > 0 and "plant_name" in df.columns:
        error_plants = df[df["flag_high_cf"]]["plant_name"].tolist()[:20]
        print(f"  High CF plants: {', '.join(str(p) for p in error_plants)}")

    print(f"Total installed capacity in dataset:      {total_cap:,.0f} MW (expected 150,000–165,000 MW)")
    print(f"Median cf_3yr_2022_2024:                  {median_cf:.4f} (expected 0.28–0.40)")

    # Capacity sanity check
    if total_cap < 110000:
        print(f"  ⚠ WARNING: Total capacity {total_cap:,.0f} MW is below 110,000 MW threshold")

    # ══════════════════════════════════════════════════════════════════════════
    # Output
    # ══════════════════════════════════════════════════════════════════════════
    # Save KPI parquet
    kpi_path = PROC_DIR / "wind_plants_kpis.parquet"
    df.to_parquet(kpi_path, index=False)

    # Save full CSV
    csv_path = OUT_DIR / "wind_plants.csv"
    df.to_csv(csv_path, index=False)

    elapsed = time.time() - start
    print(f"\n✓ 03_kpis.py complete")
    print(f"  Input rows:           {input_rows}")
    print(f"  Output rows:          {len(df)}")
    print(f"  Rows dropped:         0")
    print(f"  Warnings:             {1 if total_cap < 110000 else 0}")
    print(f"  Elapsed:              {elapsed:.1f}s")
    print(f"  Output:               {kpi_path}")
    print(f"                        {csv_path}")


if __name__ == "__main__":
    main()
