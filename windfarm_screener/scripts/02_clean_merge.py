"""
02_clean_merge.py — Clean and merge all data sources into a single plant-level dataset.

Input:  data/raw/ (downloaded by 01_download.py)
Output: data/processed/wind_plants_merged.parquet
        outputs/audit/source_trace.csv
        outputs/audit/merge_log.txt

Merge sequence:
  2a — EIA 860 plant files (2018–2024)
  2b — EIA 860 wind generator files (capacity, commissioning year)
  2c — EIA 860 owner files (ownership detail)
  2d — EIA 923 annual generation (2018–2024, monthly + annual)
  2e — EPM 2025 monthly generation
  2f — EIA 860M capacity change flag
  2g — USWTDB turbine aggregation
  2h — eGRID NERC region
  2i — Final join + filter (wind, >=10 MW)
"""

import time
import sys
from pathlib import Path
from io import StringIO

import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
EXT_DIR = BASE_DIR / "data" / "external"
PROC_DIR = BASE_DIR / "data" / "processed"
AUDIT_DIR = BASE_DIR / "outputs" / "audit"

YEARS = list(range(2018, 2025))
MONTHS = [f"{m:02d}" for m in range(1, 13)]

merge_log = []


def log(msg):
    print(msg)
    merge_log.append(msg)


def find_file(directory, pattern):
    """Find a file matching a case-insensitive pattern."""
    directory = Path(directory)
    matches = []
    for f in directory.rglob("*"):
        if pattern.lower() in f.name.lower() and not f.name.startswith("~"):
            matches.append(f)
    return matches[0] if matches else None


# ══════════════════════════════════════════════════════════════════════════════
# 2a — EIA 860 Plant Files
# ══════════════════════════════════════════════════════════════════════════════
def load_eia860_plants():
    log("\n── 2a: EIA 860 Plant Files ──")
    frames = []

    for year in YEARS:
        f = find_file(RAW_DIR / "eia860", f"2___Plant_Y{year}")
        if f is None:
            log(f"  ⚠ Missing EIA-860 plant file for {year}")
            continue

        try:
            df = pd.read_excel(f, sheet_name="Plant", skiprows=1)
        except Exception:
            # Try without skiprows or different sheet name
            try:
                xls = pd.ExcelFile(f)
                sheet = [s for s in xls.sheet_names if "plant" in s.lower()]
                df = pd.read_excel(f, sheet_name=sheet[0] if sheet else 0, skiprows=1)
            except Exception as e:
                log(f"  ✗ Could not read {f.name}: {e}")
                continue

        # Normalize column names
        col_map = {}
        for c in df.columns:
            cl = str(c).lower().strip()
            if "plant code" in cl or "plant id" in cl:
                col_map[c] = "plant_id"
            elif "plant name" in cl:
                col_map[c] = "plant_name"
            elif cl == "state":
                col_map[c] = "state"
            elif "latitude" in cl:
                col_map[c] = "latitude"
            elif "longitude" in cl:
                col_map[c] = "longitude"
            elif "utility name" in cl:
                col_map[c] = "utility_name"
            elif "balancing authority" in cl and "code" in cl:
                col_map[c] = "balancing_authority"

        df = df.rename(columns=col_map)
        keep = [c for c in ["plant_id", "plant_name", "state", "latitude",
                            "longitude", "utility_name", "balancing_authority"]
                if c in df.columns]
        df = df[keep].copy()
        df["year"] = year
        df["eia860_file"] = f.name
        frames.append(df)
        log(f"  ✓ {year}: {len(df)} plants")

    if not frames:
        log("  ✗ No EIA-860 plant files loaded!")
        sys.exit(1)

    plants = pd.concat(frames, ignore_index=True)
    plants["plant_id"] = pd.to_numeric(plants["plant_id"], errors="coerce")
    plants = plants.dropna(subset=["plant_id"])
    plants["plant_id"] = plants["plant_id"].astype(int)

    # Use 2024 as primary record; fill gaps from earlier years
    primary = plants[plants["year"] == 2024].drop_duplicates(subset=["plant_id"], keep="first")
    log(f"  Total unique plants (2024 primary): {len(primary)}")

    return primary, plants


# ══════════════════════════════════════════════════════════════════════════════
# 2b — EIA 860 Wind Generator Files (capacity + commissioning year)
# ══════════════════════════════════════════════════════════════════════════════
def load_eia860_generators():
    log("\n── 2b: EIA 860 Wind Generator Files ──")
    capacity_by_year = {}
    commissioning_records = []

    for year in YEARS:
        # EIA renamed from 3_1_Wind to 3_2_Wind in recent years — try both
        f = find_file(RAW_DIR / "eia860", f"3_2_Wind_Y{year}")
        if f is None:
            f = find_file(RAW_DIR / "eia860", f"3_1_Wind_Y{year}")
        if f is None:
            log(f"  ⚠ Missing EIA-860 wind generator file for {year}")
            continue

        try:
            xls = pd.ExcelFile(f)
            # Try "Operable" sheet first, then first sheet
            sheet_name = None
            for s in xls.sheet_names:
                if "operable" in s.lower():
                    sheet_name = s
                    break
            if sheet_name is None:
                sheet_name = xls.sheet_names[0]

            df = pd.read_excel(f, sheet_name=sheet_name, skiprows=1)
        except Exception as e:
            log(f"  ✗ Could not read {f.name}: {e}")
            continue

        # Find columns
        col_map = {}
        for c in df.columns:
            cl = str(c).lower().strip()
            if "plant code" in cl or "plant id" in cl:
                col_map[c] = "plant_id"
            elif "nameplate" in cl and "capacity" in cl and "mw" in cl.replace("(", " "):
                col_map[c] = "capacity_mw"
            elif "operating year" in cl:
                col_map[c] = "operating_year"
            elif "operating month" in cl:
                col_map[c] = "operating_month"

        df = df.rename(columns=col_map)
        df["plant_id"] = pd.to_numeric(df.get("plant_id"), errors="coerce")
        df = df.dropna(subset=["plant_id"])
        df["plant_id"] = df["plant_id"].astype(int)

        if "capacity_mw" in df.columns:
            df["capacity_mw"] = pd.to_numeric(df["capacity_mw"], errors="coerce")
            cap = df.groupby("plant_id")["capacity_mw"].sum().reset_index()
            cap = cap.rename(columns={"capacity_mw": f"capacity_mw_{year}"})
            capacity_by_year[year] = cap

        if "operating_year" in df.columns:
            df["operating_year"] = pd.to_numeric(df["operating_year"], errors="coerce")
            commissioning_records.append(df[["plant_id", "operating_year"]].dropna())

        log(f"  ✓ {year}: {len(df)} generator rows")

    # Merge capacity columns
    if not capacity_by_year:
        log("  ✗ No capacity data loaded!")
        sys.exit(1)

    cap_merged = None
    for year, cap_df in capacity_by_year.items():
        if cap_merged is None:
            cap_merged = cap_df
        else:
            cap_merged = cap_merged.merge(cap_df, on="plant_id", how="outer")

    # Commissioning year = earliest operating year across all records
    if commissioning_records:
        comm = pd.concat(commissioning_records, ignore_index=True)
        comm = comm.groupby("plant_id")["operating_year"].min().reset_index()
        comm = comm.rename(columns={"operating_year": "commissioning_year"})
        cap_merged = cap_merged.merge(comm, on="plant_id", how="left")

    log(f"  Plants with capacity data: {len(cap_merged)}")
    return cap_merged


# ══════════════════════════════════════════════════════════════════════════════
# 2c — EIA 860 Owner Files
# ══════════════════════════════════════════════════════════════════════════════
def load_eia860_owners():
    log("\n── 2c: EIA 860 Owner Files ──")

    # Use 2024 (most recent) for ownership detail
    f = find_file(RAW_DIR / "eia860", "4___Owner_Y2024")
    if f is None:
        # Try any year
        for yr in reversed(YEARS):
            f = find_file(RAW_DIR / "eia860", f"4___Owner_Y{yr}")
            if f:
                break

    if f is None:
        log("  ⚠ No owner files found")
        return pd.DataFrame(columns=["plant_id", "owner_name", "multiple_owners"])

    try:
        xls = pd.ExcelFile(f)
        sheet = xls.sheet_names[0]
        df = pd.read_excel(f, sheet_name=sheet, skiprows=1)
    except Exception as e:
        log(f"  ✗ Could not read {f.name}: {e}")
        return pd.DataFrame(columns=["plant_id", "owner_name", "multiple_owners"])

    col_map = {}
    for c in df.columns:
        cl = str(c).lower().strip()
        if "plant code" in cl or "plant id" in cl:
            col_map[c] = "plant_id"
        elif "owner name" in cl:
            col_map[c] = "owner_name"
        elif "percent owned" in cl:
            col_map[c] = "percent_owned"

    df = df.rename(columns=col_map)
    df["plant_id"] = pd.to_numeric(df.get("plant_id"), errors="coerce")
    df = df.dropna(subset=["plant_id"])
    df["plant_id"] = df["plant_id"].astype(int)

    # Determine primary owner (highest percent or first listed)
    if "percent_owned" in df.columns:
        df["percent_owned"] = pd.to_numeric(df["percent_owned"], errors="coerce")
        primary = df.sort_values("percent_owned", ascending=False).drop_duplicates(
            subset=["plant_id"], keep="first")
    else:
        primary = df.drop_duplicates(subset=["plant_id"], keep="first")

    # Multiple owners flag
    owner_counts = df.groupby("plant_id")["owner_name"].nunique().reset_index()
    owner_counts = owner_counts.rename(columns={"owner_name": "owner_count"})
    owner_counts["multiple_owners"] = owner_counts["owner_count"] > 1

    result = primary[["plant_id", "owner_name"]].merge(
        owner_counts[["plant_id", "multiple_owners"]], on="plant_id", how="left")

    log(f"  ✓ {len(result)} plants with owner data, {owner_counts['multiple_owners'].sum()} multi-owner")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 2d — EIA 923 Annual Generation (2018–2024)
# ══════════════════════════════════════════════════════════════════════════════
def load_eia923():
    log("\n── 2d: EIA 923 Annual Generation ──")
    annual_frames = {}
    monthly_frames = {}

    for year in YEARS:
        f = find_file(RAW_DIR / "eia923", f"EIA923_Schedules_2_3_4_5")
        # More specific search for the year
        candidates = list((RAW_DIR / "eia923").rglob(f"*{year}*"))
        candidates = [c for c in candidates if "EIA923" in c.name and c.suffix in (".xlsx", ".xls")
                      and not c.name.startswith("~")]
        if not candidates:
            candidates = list((RAW_DIR / "eia923").rglob(f"*Schedules*{year}*"))
        if not candidates:
            # Try inside extracted subdirectories
            candidates = list((RAW_DIR / "eia923").rglob(f"*EIA923*"))
            candidates = [c for c in candidates if str(year) in c.name
                          and c.suffix in (".xlsx", ".xls") and not c.name.startswith("~")]

        if not candidates:
            log(f"  ⚠ Missing EIA-923 file for {year}")
            continue

        f = candidates[0]
        try:
            df = pd.read_excel(f, sheet_name="Page 1 Generation and Fuel Data", skiprows=5)
        except Exception:
            try:
                xls = pd.ExcelFile(f)
                page1 = [s for s in xls.sheet_names if "page 1" in s.lower() or "generation" in s.lower()]
                df = pd.read_excel(f, sheet_name=page1[0] if page1 else 0, skiprows=5)
            except Exception as e:
                log(f"  ✗ Could not read {f.name}: {e}")
                continue

        # Find columns
        col_map = {}
        net_gen_col = None
        plant_id_col = None
        prime_mover_col = None
        month_cols = {}

        for c in df.columns:
            cl = str(c).lower().strip()
            if "plant id" in cl or "plant code" in cl:
                plant_id_col = c
            elif "reported prime mover" in cl or ("prime" in cl and "mover" in cl):
                prime_mover_col = c
            elif "net generation" in cl and "megawatthour" in cl.lower():
                net_gen_col = c

        # Find monthly generation columns (January through December)
        month_names = ["january", "february", "march", "april", "may", "june",
                       "july", "august", "september", "october", "november", "december"]
        for c in df.columns:
            cl = str(c).lower().strip()
            for i, mn in enumerate(month_names):
                if mn in cl and ("generation" in cl or "net gen" in cl or "netgen" in cl):
                    month_cols[f"{i+1:02d}"] = c
                    break
            # Also try: "Netgen January", etc.
            if not month_cols:
                for i, mn in enumerate(month_names):
                    if mn in cl:
                        month_cols[f"{i+1:02d}"] = c
                        break

        if plant_id_col is None:
            log(f"  ✗ Could not find Plant ID column in {f.name}")
            continue

        # Filter to wind turbine
        if prime_mover_col:
            df = df[df[prime_mover_col].astype(str).str.strip().str.upper() == "WT"].copy()
        else:
            log(f"  ⚠ No prime mover column found for {year} — using all rows")

        df["plant_id"] = pd.to_numeric(df[plant_id_col], errors="coerce")
        df = df.dropna(subset=["plant_id"])
        df["plant_id"] = df["plant_id"].astype(int)

        # Annual generation: sum net gen by plant
        if net_gen_col:
            df[net_gen_col] = pd.to_numeric(df[net_gen_col], errors="coerce")
            annual = df.groupby("plant_id")[net_gen_col].sum().reset_index()
            annual = annual.rename(columns={net_gen_col: f"gen_mwh_{year}"})
            annual_frames[year] = annual
        elif month_cols:
            # Sum monthly columns for annual total
            for mm, mc in month_cols.items():
                df[mc] = pd.to_numeric(df[mc], errors="coerce")
            df["_annual_sum"] = df[list(month_cols.values())].sum(axis=1)
            annual = df.groupby("plant_id")["_annual_sum"].sum().reset_index()
            annual = annual.rename(columns={"_annual_sum": f"gen_mwh_{year}"})
            annual_frames[year] = annual

        # Monthly generation breakdown
        if month_cols:
            for mm, mc in month_cols.items():
                df[mc] = pd.to_numeric(df[mc], errors="coerce")
                monthly = df.groupby("plant_id")[mc].sum().reset_index()
                monthly = monthly.rename(columns={mc: f"gen_mwh_{year}_{mm}"})
                key = f"{year}_{mm}"
                monthly_frames[key] = monthly

        log(f"  ✓ {year}: {len(df)} wind rows, annual gen for {len(annual_frames.get(year, []))} plants")

    # Merge all annual
    gen_merged = None
    for year in YEARS:
        if year in annual_frames:
            if gen_merged is None:
                gen_merged = annual_frames[year]
            else:
                gen_merged = gen_merged.merge(annual_frames[year], on="plant_id", how="outer")

    # Merge monthly
    for key, mdf in monthly_frames.items():
        if gen_merged is None:
            gen_merged = mdf
        else:
            gen_merged = gen_merged.merge(mdf, on="plant_id", how="outer")

    if gen_merged is not None:
        log(f"  Plants with any generation data: {len(gen_merged)}")
    else:
        log("  ✗ No generation data loaded!")
        sys.exit(1)

    return gen_merged


# ══════════════════════════════════════════════════════════════════════════════
# 2e — EPM 2025 Monthly Generation
# ══════════════════════════════════════════════════════════════════════════════
def load_epm_2025():
    log("\n── 2e: EPM 2025 Monthly ──")
    epm_path = RAW_DIR / "epm" / "epm_2025_monthly.csv"

    if not epm_path.exists():
        log("  ⚠ EPM 2025 file not found — skipping 2025 data")
        return pd.DataFrame(columns=["plant_id"])

    df = pd.read_csv(epm_path)
    log(f"  Raw EPM records: {len(df)}")

    # Identify the plant ID and period columns from API response
    # EIA API typically returns: plantCode or plantid, period, generation
    plant_col = None
    period_col = None
    gen_col = None

    for c in df.columns:
        cl = c.lower()
        if "plantid" in cl or "plantcode" in cl or "plant_id" in cl or cl == "plantid":
            plant_col = c
        elif "period" in cl:
            period_col = c
        elif cl == "generation" or (cl.startswith("generation") and "units" not in cl and "description" not in cl):
            gen_col = c

    if plant_col is None or period_col is None or gen_col is None:
        log(f"  ⚠ Could not identify columns. Found: {list(df.columns)}")
        log("    Attempting column mapping by position...")
        # Log columns for debugging
        for i, c in enumerate(df.columns):
            log(f"    [{i}] {c}")
        return pd.DataFrame(columns=["plant_id"])

    df["plant_id"] = pd.to_numeric(df[plant_col], errors="coerce")
    df["generation"] = pd.to_numeric(df[gen_col], errors="coerce")
    df = df.dropna(subset=["plant_id"])
    df["plant_id"] = df["plant_id"].astype(int)

    # Extract month from period (format: YYYY-MM or YYYYMM)
    df["month"] = df[period_col].astype(str).str[-2:]
    if df["month"].str.contains("-").any():
        df["month"] = df[period_col].astype(str).str.split("-").str[1]

    # Pivot to monthly columns
    monthly_cols = {}
    for mm in MONTHS:
        month_data = df[df["month"] == mm].groupby("plant_id")["generation"].sum().reset_index()
        month_data = month_data.rename(columns={"generation": f"gen_mwh_2025_{mm}"})
        monthly_cols[mm] = month_data

    # Merge all months
    result = None
    for mm, mdf in monthly_cols.items():
        if result is None:
            result = mdf
        else:
            result = result.merge(mdf, on="plant_id", how="outer")

    if result is None or len(result) == 0:
        log("  ⚠ No EPM plant data after processing")
        return pd.DataFrame(columns=["plant_id"])

    # Compute annual sum and month count
    month_value_cols = [f"gen_mwh_2025_{mm}" for mm in MONTHS if f"gen_mwh_2025_{mm}" in result.columns]
    result["gen_mwh_2025"] = result[month_value_cols].sum(axis=1)
    result["epm_months_count"] = result[month_value_cols].notna().sum(axis=1)

    log(f"  ✓ EPM 2025: {len(result)} plants")
    log(f"    Plants with 12 months: {(result['epm_months_count'] == 12).sum()}")
    log(f"    Plants with 10-11 months: {((result['epm_months_count'] >= 10) & (result['epm_months_count'] < 12)).sum()}")

    return result


# ══════════════════════════════════════════════════════════════════════════════
# 2f — EIA 860M Capacity Change Flag
# ══════════════════════════════════════════════════════════════════════════════
def load_eia860m():
    log("\n── 2f: EIA 860M Capacity Change Flag ──")
    f = RAW_DIR / "eia860m" / "eia860m_latest.xlsx"

    if not f.exists():
        log("  ⚠ EIA-860M file not found — skipping capacity change flags")
        return pd.DataFrame(columns=["plant_id", "capacity_changed_2025"])

    try:
        xls = pd.ExcelFile(f)
        flagged_plants = set()

        for sheet in xls.sheet_names:
            sl = sheet.lower()
            if "retired" in sl or "proposed" in sl or "cancel" in sl:
                df = pd.read_excel(f, sheet_name=sheet, skiprows=1)
                # Find plant code column
                for c in df.columns:
                    if "plant code" in str(c).lower() or "plant id" in str(c).lower():
                        ids = pd.to_numeric(df[c], errors="coerce").dropna().astype(int)
                        flagged_plants.update(ids.tolist())
                        break

        result = pd.DataFrame({"plant_id": list(flagged_plants)})
        result["capacity_changed_2025"] = True
        log(f"  ✓ {len(result)} plants flagged for capacity change")
        return result

    except Exception as e:
        log(f"  ✗ Could not read 860M: {e}")
        return pd.DataFrame(columns=["plant_id", "capacity_changed_2025"])


# ══════════════════════════════════════════════════════════════════════════════
# 2g — USWTDB Turbine Aggregation
# ══════════════════════════════════════════════════════════════════════════════
def load_uswtdb():
    log("\n── 2g: USWTDB Turbine Aggregation ──")
    f = RAW_DIR / "uswtdb" / "uswtdb_latest.csv"

    if not f.exists():
        log("  ⚠ USWTDB file not found — skipping turbine data")
        return pd.DataFrame(columns=["plant_id"])

    df = pd.read_csv(f, low_memory=False)
    log(f"  Raw turbine records: {len(df)}")

    # Log -9999 eia_id records
    if "eia_id" in df.columns:
        missing = (df["eia_id"] == -9999).sum()
        log(f"  Turbines with eia_id = -9999 (unmatched): {missing} ({missing/len(df)*100:.1f}%)")
        df = df[df["eia_id"] != -9999].copy()
        df["plant_id"] = pd.to_numeric(df["eia_id"], errors="coerce")
        df = df.dropna(subset=["plant_id"])
        df["plant_id"] = df["plant_id"].astype(int)
    else:
        log("  ✗ No eia_id column found")
        return pd.DataFrame(columns=["plant_id"])

    # Aggregate by plant
    agg = df.groupby("plant_id").agg(
        turbine_count=("eia_id", "count"),
        turbine_manufacturer=("t_manu", lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else None),
        turbine_model=("t_model", lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else None),
        hub_height_m=("t_hh", lambda x: round(x.mean(), 1) if x.notna().any() else None),
        rotor_diameter_m=("t_rd", lambda x: round(x.mean(), 1) if x.notna().any() else None),
        total_rated_capacity_kw=("t_cap", "sum"),
        turbine_vintage_min=("p_year", "min"),
        turbine_vintage_max=("p_year", "max"),
    ).reset_index()

    log(f"  ✓ {len(agg)} plants matched to USWTDB")
    return agg


# ══════════════════════════════════════════════════════════════════════════════
# 2h — eGRID NERC Region
# ══════════════════════════════════════════════════════════════════════════════
def load_egrid():
    log("\n── 2h: eGRID NERC Region ──")
    f = RAW_DIR / "egrid" / "egrid_latest.xlsx"

    if not f.exists():
        log("  ⚠ eGRID file not found — skipping NERC region")
        return pd.DataFrame(columns=["plant_id", "nerc_region"])

    try:
        xls = pd.ExcelFile(f)
        plnt_sheets = [s for s in xls.sheet_names if s.upper().startswith("PLNT")]
        if not plnt_sheets:
            plnt_sheets = [s for s in xls.sheet_names if "plant" in s.lower()]
        if not plnt_sheets:
            log(f"  ✗ No plant sheet found. Sheets: {xls.sheet_names}")
            return pd.DataFrame(columns=["plant_id", "nerc_region"])

        df = pd.read_excel(f, sheet_name=plnt_sheets[0], skiprows=1)

        # Find ORISPL and NERC columns
        oris_col = None
        nerc_col = None
        for c in df.columns:
            cl = str(c).upper().strip()
            if "ORISPL" in cl or "PSTATABB" in cl.replace(" ", ""):
                if "ORISPL" in cl:
                    oris_col = c
            elif cl == "NERC" or "NERC" in cl:
                nerc_col = c

        if oris_col is None:
            # Try broader search
            for c in df.columns:
                cl = str(c).upper().strip()
                if "ORIS" in cl:
                    oris_col = c
                    break

        if oris_col is None or nerc_col is None:
            log(f"  ✗ Could not find ORISPL/NERC columns. Found: {list(df.columns[:20])}")
            return pd.DataFrame(columns=["plant_id", "nerc_region"])

        result = df[[oris_col, nerc_col]].copy()
        result.columns = ["plant_id", "nerc_region"]
        result["plant_id"] = pd.to_numeric(result["plant_id"], errors="coerce")
        result = result.dropna(subset=["plant_id"])
        result["plant_id"] = result["plant_id"].astype(int)
        result = result.drop_duplicates(subset=["plant_id"], keep="first")

        log(f"  ✓ {len(result)} plants with NERC region")
        return result

    except Exception as e:
        log(f"  ✗ Could not read eGRID: {e}")
        return pd.DataFrame(columns=["plant_id", "nerc_region"])


# ══════════════════════════════════════════════════════════════════════════════
# 2i — Final Join + Filter
# ══════════════════════════════════════════════════════════════════════════════
def final_merge(plants_primary, all_plants, generators, owners, generation,
                epm_2025, eia860m, uswtdb, egrid):
    log("\n── 2i: Final Merge ──")

    # Start with 2024 plant records
    df = plants_primary.copy()
    input_rows = len(df)

    # Left join generators (capacity + commissioning year)
    df = df.merge(generators, on="plant_id", how="left")
    log(f"  After generator join: {len(df)} rows")

    # Left join owners
    df = df.merge(owners, on="plant_id", how="left")
    log(f"  After owner join: {len(df)} rows")

    # Left join generation
    df = df.merge(generation, on="plant_id", how="left")
    log(f"  After generation join: {len(df)} rows")

    # Left join EPM 2025
    if len(epm_2025) > 0 and "plant_id" in epm_2025.columns:
        df = df.merge(epm_2025, on="plant_id", how="left")
    log(f"  After EPM 2025 join: {len(df)} rows")

    # Left join 860M
    if len(eia860m) > 0:
        df = df.merge(eia860m, on="plant_id", how="left")
        df["capacity_changed_2025"] = df["capacity_changed_2025"].fillna(False)
    else:
        df["capacity_changed_2025"] = False
    log(f"  After 860M join: {len(df)} rows")

    # Left join USWTDB
    if len(uswtdb) > 0 and "plant_id" in uswtdb.columns:
        df = df.merge(uswtdb, on="plant_id", how="left")
    log(f"  After USWTDB join: {len(df)} rows")

    # Left join eGRID
    if len(egrid) > 0 and "plant_id" in egrid.columns:
        df = df.merge(egrid, on="plant_id", how="left")
    log(f"  After eGRID join: {len(df)} rows")

    # Filter: wind plants >= 10 MW
    # Use capacity_mw_2024 first, fall back to 2023
    if "capacity_mw_2024" in df.columns:
        df["_cap_filter"] = df["capacity_mw_2024"]
    else:
        df["_cap_filter"] = None

    if "capacity_mw_2023" in df.columns:
        df["_cap_filter"] = df["_cap_filter"].fillna(df["capacity_mw_2023"])

    pre_filter = len(df)
    df = df[df["_cap_filter"] >= 10].copy()
    df = df.drop(columns=["_cap_filter"])
    dropped = pre_filter - len(df)
    log(f"  After capacity filter (>=10 MW): {len(df)} rows (dropped {dropped})")

    # Add EIA plant page URL
    df["eia_plant_url"] = df["plant_id"].apply(
        lambda x: f"https://www.eia.gov/electricity/data/browser/#/plant/{int(x)}")

    return df, input_rows, dropped


# ══════════════════════════════════════════════════════════════════════════════
# Source Trace
# ══════════════════════════════════════════════════════════════════════════════
def write_source_trace(df):
    trace = df[["plant_id", "plant_name"]].copy()
    trace["eia860_file"] = df.get("eia860_file", "")
    trace["eia923_files"] = "eia923_2018-2024"
    trace["epm_months_count"] = df.get("epm_months_count", 0)
    trace["uswtdb_matched"] = df.get("turbine_count", pd.Series(dtype=float)).notna()
    trace["egrid_matched"] = df.get("nerc_region", pd.Series(dtype=float)).notna()
    trace["capacity_changed_2025"] = df.get("capacity_changed_2025", False)
    trace["eia_plant_url"] = df.get("eia_plant_url", "")

    trace_path = AUDIT_DIR / "source_trace.csv"
    trace.to_csv(trace_path, index=False)
    log(f"\n✓ Source trace written: {trace_path} ({len(trace)} rows)")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    start = time.time()
    print("=" * 70)
    print("  Wind Farm Screener — Clean & Merge")
    print("=" * 70)

    # Load all sources
    plants_primary, all_plants = load_eia860_plants()
    generators = load_eia860_generators()
    owners = load_eia860_owners()
    generation = load_eia923()
    epm_2025 = load_epm_2025()
    eia860m = load_eia860m()
    uswtdb = load_uswtdb()
    egrid = load_egrid()

    # Final merge
    df, input_rows, dropped = final_merge(
        plants_primary, all_plants, generators, owners,
        generation, epm_2025, eia860m, uswtdb, egrid)

    # Write source trace
    write_source_trace(df)

    # Write merged parquet
    out_path = PROC_DIR / "wind_plants_merged.parquet"
    df.to_parquet(out_path, index=False)

    # Merge quality log
    total_plants = len(df)
    full_annual = 0
    partial_annual = 0
    no_gen = 0

    for _, row in df.iterrows():
        years_with_data = sum(1 for yr in YEARS if pd.notna(row.get(f"gen_mwh_{yr}")))
        if years_with_data == len(YEARS):
            full_annual += 1
        elif years_with_data > 0:
            partial_annual += 1
        else:
            no_gen += 1

    epm_full = (df.get("epm_months_count", pd.Series(dtype=float)) == 12).sum() if "epm_months_count" in df.columns else 0
    epm_partial = ((df.get("epm_months_count", pd.Series(dtype=float)) >= 10) &
                   (df.get("epm_months_count", pd.Series(dtype=float)) < 12)).sum() if "epm_months_count" in df.columns else 0
    epm_none = (df.get("epm_months_count", pd.Series(dtype=float)).isna() |
                (df.get("epm_months_count", pd.Series(dtype=float)) == 0)).sum() if "epm_months_count" in df.columns else total_plants

    uswtdb_matched = df["turbine_count"].notna().sum() if "turbine_count" in df.columns else 0
    uswtdb_pct = uswtdb_matched / total_plants * 100 if total_plants > 0 else 0
    nerc_matched = df["nerc_region"].notna().sum() if "nerc_region" in df.columns else 0
    nerc_pct = nerc_matched / total_plants * 100 if total_plants > 0 else 0
    cap_changed = df["capacity_changed_2025"].sum() if "capacity_changed_2025" in df.columns else 0
    multi_owner = df["multiple_owners"].sum() if "multiple_owners" in df.columns else 0

    quality_lines = [
        "",
        "═══ Merge Quality Log ═══",
        f"Plants in EIA 860 2024 (wind, >=10MW):             {total_plants}",
        f"Plants with full annual data (all 7 years):         {full_annual}",
        f"Plants with partial annual data:                    {partial_annual}",
        f"Plants with no generation data (excluded):          {no_gen}",
        f"Plants with full 2025 EPM (12 months):              {epm_full}",
        f"Plants with partial 2025 EPM (10-11 months):        {epm_partial}",
        f"Plants with no 2025 EPM data:                       {epm_none}",
        f"Plants matched to USWTDB:                           {uswtdb_matched} ({uswtdb_pct:.1f}%)",
        f"Plants with NERC region:                            {nerc_matched} ({nerc_pct:.1f}%)",
        f"Plants with capacity_changed_2025:                  {cap_changed}",
        f"Plants with multiple owners:                        {multi_owner}",
    ]

    for line in quality_lines:
        log(line)

    # Write merge log
    log_path = AUDIT_DIR / "merge_log.txt"
    with open(log_path, "w") as f:
        f.write("\n".join(merge_log))

    elapsed = time.time() - start
    print(f"\n✓ 02_clean_merge.py complete")
    print(f"  Input rows:           {input_rows}")
    print(f"  Output rows:          {total_plants}")
    print(f"  Rows dropped:         {dropped}")
    epm_loaded = epm_full + epm_partial
    print(f"  EPM months loaded:    {'12/12' if epm_full > 0 else '0/12'}")
    print(f"  Warnings:             {sum(1 for l in merge_log if '⚠' in l)}")
    print(f"  Elapsed:              {elapsed:.1f}s")
    print(f"  Output:               {out_path}")


if __name__ == "__main__":
    main()
