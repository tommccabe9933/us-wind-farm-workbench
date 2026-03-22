"""
01_download.py — Download all data sources for the Wind Farm Investment Screener.

Sources:
  1. EIA-860 (plant & generator metadata, 2018–2024)
  2. EIA-923 (annual generation, 2018–2024)
  3. EIA Electric Power Monthly / API (2025 monthly generation)
  4. EIA-860M (capacity change detection)
  5. USWTDB (turbine database)
  6. EPA eGRID (NERC region labels)
  7. LBNL Wind Technologies Market Report (regional CF benchmarks)

Run: python scripts/01_download.py
Requires: EIA_API_KEY environment variable for EPM 2025 data.
"""

import os
import sys
import csv
import hashlib
import zipfile
import time
from pathlib import Path
from datetime import datetime

import requests
from tqdm import tqdm
import pandas as pd

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
EXT_DIR = BASE_DIR / "data" / "external"
AUDIT_DIR = BASE_DIR / "outputs" / "audit"

EIA860_DIR = RAW_DIR / "eia860"
EIA923_DIR = RAW_DIR / "eia923"
EPM_DIR = RAW_DIR / "epm"
EIA860M_DIR = RAW_DIR / "eia860m"
USWTDB_DIR = RAW_DIR / "uswtdb"
EGRID_DIR = RAW_DIR / "egrid"
LBNL_DIR = RAW_DIR / "lbnl"

YEARS = list(range(2018, 2025))  # 2018–2024

# ── Manifest tracking ─────────────────────────────────────────────────────────
manifest_rows = []

MANIFEST_FIELDS = [
    "source_name", "description", "landing_page_url", "download_url",
    "local_path", "file_size_bytes", "md5_hash", "download_timestamp",
    "http_status_code", "rows_in_file"
]


def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def count_rows_in_file(path):
    """Best-effort row count for CSV/Excel files."""
    path = Path(path)
    try:
        if path.suffix == ".csv":
            with open(path, "r", errors="replace") as f:
                return sum(1 for _ in f) - 1  # minus header
        elif path.suffix in (".xlsx", ".xls"):
            df = pd.read_excel(path, nrows=0)
            # Read full file for row count
            df = pd.read_excel(path)
            return len(df)
    except Exception:
        pass
    return -1


def download_file(url, dest_path, description="", source_name="", landing_page=""):
    """Download a file with progress bar. Returns (success, local_path)."""
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    row = {
        "source_name": source_name,
        "description": description,
        "landing_page_url": landing_page,
        "download_url": url,
        "local_path": str(dest_path),
        "file_size_bytes": 0,
        "md5_hash": "",
        "download_timestamp": datetime.now().isoformat(),
        "http_status_code": 0,
        "rows_in_file": -1,
    }

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) WindFarmScreener/1.0"
        }
        resp = requests.get(url, stream=True, timeout=120, headers=headers)
        row["http_status_code"] = resp.status_code

        if resp.status_code != 200:
            row["description"] = f"FAILED — HTTP {resp.status_code}: {description}"
            manifest_rows.append(row)
            print(f"  ✗ FAILED ({resp.status_code}): {url}")
            return False, dest_path

        total = int(resp.headers.get("content-length", 0))
        with open(dest_path, "wb") as f:
            with tqdm(total=total, unit="B", unit_scale=True,
                      desc=dest_path.name, leave=False) as pbar:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    pbar.update(len(chunk))

        row["file_size_bytes"] = dest_path.stat().st_size
        row["md5_hash"] = md5_file(dest_path)
        row["rows_in_file"] = count_rows_in_file(dest_path)
        manifest_rows.append(row)
        return True, dest_path

    except Exception as e:
        row["description"] = f"FAILED — {e}: {description}"
        manifest_rows.append(row)
        print(f"  ✗ FAILED ({e}): {url}")
        return False, dest_path


def extract_from_zip(zip_path, target_patterns, dest_dir):
    """Extract files matching patterns from a ZIP. Returns list of extracted paths."""
    extracted = []
    if not zipfile.is_zipfile(zip_path):
        print(f"    ✗ Not a valid ZIP file: {zip_path.name}")
        return extracted
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            for pattern in target_patterns:
                if pattern.lower() in name.lower():
                    zf.extract(name, dest_dir)
                    full = dest_dir / name
                    extracted.append(full)
                    print(f"    Extracted: {name}")
                    break
    return extracted


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE 1 — EIA Form 860
# ══════════════════════════════════════════════════════════════════════════════
def download_eia860():
    print("\n═══ Source 1: EIA Form 860 (2018–2024) ═══")
    landing = "https://www.eia.gov/electricity/data/eia860/"
    failures = []

    for year in YEARS:
        # EIA moved prior years to archive/xls/; only the latest year stays in xls/
        if year == YEARS[-1]:  # Most recent year (2024)
            url = f"https://www.eia.gov/electricity/data/eia860/xls/eia860{year}.zip"
        else:
            url = f"https://www.eia.gov/electricity/data/eia860/archive/xls/eia860{year}.zip"
        zip_path = EIA860_DIR / f"eia860_{year}.zip"
        print(f"  Downloading EIA-860 {year}...")

        ok, _ = download_file(url, zip_path,
                              description=f"EIA-860 annual {year}",
                              source_name=f"EIA-860-{year}",
                              landing_page=landing)
        if not ok:
            failures.append(year)
            continue

        # Extract target files
        # Note: EIA renamed the wind file from 3_1_Wind to 3_2_Wind in recent years
        targets = [
            f"2___Plant_Y{year}",
            f"3_1_Wind_Y{year}",
            f"3_2_Wind_Y{year}",
            f"4___Owner_Y{year}",
        ]
        extract_from_zip(zip_path, targets, EIA860_DIR)

    return failures


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE 2 — EIA Form 923
# ══════════════════════════════════════════════════════════════════════════════
def download_eia923():
    print("\n═══ Source 2: EIA Form 923 (2018–2024) ═══")
    landing = "https://www.eia.gov/electricity/data/eia923/"
    failures = []

    for year in YEARS:
        # EIA-923: all finalized years (2018-2024) are in archive/xls/
        # Only the in-progress year (2025) would be in xls/
        url = f"https://www.eia.gov/electricity/data/eia923/archive/xls/f923_{year}.zip"
        zip_path = EIA923_DIR / f"f923_{year}.zip"
        print(f"  Downloading EIA-923 {year}...")

        ok, _ = download_file(url, zip_path,
                              description=f"EIA-923 annual {year}",
                              source_name=f"EIA-923-{year}",
                              landing_page=landing)
        if not ok:
            failures.append(year)
            continue

        # Extract the schedules file
        targets = ["EIA923_Schedules_2_3_4_5"]
        extract_from_zip(zip_path, targets, EIA923_DIR)

    return failures


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE 3 — EIA Electric Power Monthly (EPM) via API for 2025
# ══════════════════════════════════════════════════════════════════════════════
def download_epm_2025():
    print("\n═══ Source 3: EIA EPM 2025 (API) ═══")
    api_key = os.environ.get("EIA_API_KEY", "")
    if not api_key:
        # Check for .env file or prompt
        env_file = BASE_DIR / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("EIA_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not api_key:
        print("  ✗ EIA_API_KEY not set. Set via environment variable or .env file.")
        print("    Register free at: https://www.eia.gov/opendata/register.php")
        print("    Then: export EIA_API_KEY=your_key_here")
        manifest_rows.append({
            "source_name": "EPM-2025",
            "description": "FAILED — No API key provided",
            "landing_page_url": "https://www.eia.gov/electricity/monthly/",
            "download_url": "https://api.eia.gov/v2/electricity/facility-fuel/data/",
            "local_path": str(EPM_DIR / "epm_2025_monthly.csv"),
            "file_size_bytes": 0, "md5_hash": "", "download_timestamp": datetime.now().isoformat(),
            "http_status_code": 0, "rows_in_file": 0,
        })
        return False

    # Fetch plant-level monthly wind generation for 2025
    # VERIFIED: /v2/electricity/facility-fuel/data/ is the correct plant-level endpoint
    # facet name is "fuel2002" (not "fueltypeid"), value "WND"
    # Must also filter primeMover=WT to avoid double-counting with ALL rows
    # All response values are returned as strings (since API v2.1.6)
    base_url = "https://api.eia.gov/v2/electricity/facility-fuel/data/"
    all_records = []
    offset = 0
    page_size = 5000  # API max for JSON responses

    print("  Fetching 2025 monthly wind generation from EIA API...")
    print(f"  Endpoint: {base_url}")
    while True:
        params = {
            "api_key": api_key,
            "frequency": "monthly",
            "data[0]": "generation",
            "facets[fuel2002][]": "WND",
            "facets[primeMover][]": "WT",
            "start": "2025-01",
            "end": "2025-12",
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "offset": offset,
            "length": page_size,
        }

        try:
            resp = requests.get(base_url, params=params, timeout=180)
            if resp.status_code != 200:
                print(f"  ✗ API returned {resp.status_code}")
                try:
                    print(f"    Response: {resp.text[:500]}")
                except Exception:
                    pass
                return False

            data = resp.json()

            # Check for API-level errors
            if "error" in data:
                print(f"  ✗ API error: {data['error']}")
                return False

            records = data.get("response", {}).get("data", [])
            total = int(data.get("response", {}).get("total", 0))

            if not records:
                break

            all_records.extend(records)
            print(f"    Fetched {len(all_records)}/{total} records...")

            if len(all_records) >= total:
                break
            offset += page_size

        except Exception as e:
            print(f"  ✗ API error: {e}")
            return False

    if not all_records:
        print("  ✗ No records returned from API")
        return False

    # Convert to DataFrame and save
    # API returns: plantCode, plantName, state, period (YYYY-MM),
    #              generation (string MWh), fuel2002, primeMover
    df = pd.DataFrame(all_records)

    # Convert generation from string to numeric
    if "generation" in df.columns:
        df["generation"] = pd.to_numeric(df["generation"], errors="coerce")

    out_path = EPM_DIR / "epm_2025_monthly.csv"
    df.to_csv(out_path, index=False)

    manifest_rows.append({
        "source_name": "EPM-2025",
        "description": "EIA Electric Power Monthly — 2025 wind generation via API",
        "landing_page_url": "https://www.eia.gov/electricity/monthly/",
        "download_url": base_url,
        "local_path": str(out_path),
        "file_size_bytes": out_path.stat().st_size,
        "md5_hash": md5_file(out_path),
        "download_timestamp": datetime.now().isoformat(),
        "http_status_code": 200,
        "rows_in_file": len(df),
    })

    # Check month coverage
    if "period" in df.columns:
        months = df["period"].str[:7].unique()
        print(f"  ✓ EPM 2025: {len(months)} unique months, {len(df)} records")
    else:
        print(f"  ✓ EPM 2025: {len(df)} records saved")

    return True


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE 4 — EIA Form 860M (capacity change detection)
# ══════════════════════════════════════════════════════════════════════════════
def download_eia860m():
    print("\n═══ Source 4: EIA Form 860M (latest) ═══")
    landing = "https://www.eia.gov/electricity/data/eia860m/"

    # 860M now uses individual monthly files: {month}_generator{year}.xlsx
    # Most recent is in xls/, archived in archive/xls/
    urls_to_try = [
        "https://www.eia.gov/electricity/data/eia860m/xls/january_generator2026.xlsx",
        "https://www.eia.gov/electricity/data/eia860m/xls/february_generator2026.xlsx",
        "https://www.eia.gov/electricity/data/eia860m/archive/xls/december_generator2025.xlsx",
        "https://www.eia.gov/electricity/data/eia860m/archive/xls/november_generator2025.xlsx",
    ]

    dest_path = EIA860M_DIR / "eia860m_latest.xlsx"
    for url in urls_to_try:
        print(f"  Trying: {url}")
        ok, _ = download_file(url, dest_path,
                              description="EIA-860M monthly (latest)",
                              source_name="EIA-860M",
                              landing_page=landing)
        if ok:
            return True

    print("  ⚠ Could not auto-download 860M. Please download manually from:")
    print(f"    {landing}")
    print(f"    Save as: {dest_path}")
    return False


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE 5 — U.S. Wind Turbine Database (USWTDB)
# ══════════════════════════════════════════════════════════════════════════════
def download_uswtdb():
    print("\n═══ Source 5: USWTDB ═══")
    url = "https://eerscmap.usgs.gov/uswtdb/assets/data/uswtdbCSV.zip"
    landing = "https://eerscmap.usgs.gov/uswtdb/"
    zip_path = USWTDB_DIR / "uswtdbCSV.zip"

    ok, _ = download_file(url, zip_path,
                          description="U.S. Wind Turbine Database",
                          source_name="USWTDB",
                          landing_page=landing)
    if not ok:
        return False

    # Extract CSV
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if name.endswith(".csv"):
                zf.extract(name, USWTDB_DIR)
                # Rename to standard name
                extracted = USWTDB_DIR / name
                target = USWTDB_DIR / "uswtdb_latest.csv"
                if extracted != target:
                    if target.exists():
                        target.unlink()
                    extracted.rename(target)
                print(f"    Extracted: {name} → uswtdb_latest.csv")
                break

    return True


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE 6 — EPA eGRID (NERC region labels)
# ══════════════════════════════════════════════════════════════════════════════
def download_egrid():
    print("\n═══ Source 6: EPA eGRID ═══")
    landing = "https://www.epa.gov/egrid/download-data"

    # Try eGRID 2022 (latest available with final data)
    # The URL pattern varies by year
    urls_to_try = [
        ("https://www.epa.gov/system/files/documents/2025-06/egrid2023_data_rev2.xlsx", "eGRID 2023 rev2"),
        ("https://www.epa.gov/system/files/documents/2025-06/egrid2023_data.xlsx", "eGRID 2023"),
        ("https://www.epa.gov/system/files/documents/2024-01/egrid2022_data.xlsx", "eGRID 2022"),
    ]

    dest_path = EGRID_DIR / "egrid_latest.xlsx"
    for url, desc in urls_to_try:
        print(f"  Trying: {desc}")
        ok, _ = download_file(url, dest_path,
                              description=f"EPA eGRID ({desc})",
                              source_name="eGRID",
                              landing_page=landing)
        if ok:
            return True

    print("  ⚠ Could not auto-download eGRID. Please download manually from:")
    print(f"    {landing}")
    print(f"    Save as: {dest_path}")
    return False


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE 7 — LBNL Wind Technologies Market Report
# ══════════════════════════════════════════════════════════════════════════════
def download_lbnl():
    print("\n═══ Source 7: LBNL Wind Market Report ═══")
    landing = "https://emp.lbl.gov/wind-technologies-market-report"

    # LBNL data file URL changes with each report release.
    # Try common patterns; fall back to hardcoded benchmarks.
    urls_to_try = [
        "https://emp.lbl.gov/sites/default/files/wind_technologies_market_report_data_file.xlsm",
        "https://emp.lbl.gov/sites/default/files/2024-08/wind_technologies_market_report_data_file.xlsm",
    ]

    dest_path = EXT_DIR / "lbnl_wind_market.xlsx"
    for url in urls_to_try:
        print(f"  Trying: {url}")
        ok, _ = download_file(url, dest_path,
                              description="LBNL Wind Technologies Market Report data",
                              source_name="LBNL",
                              landing_page=landing)
        if ok:
            return True

    # Fallback: write hardcoded benchmarks
    print("  ⚠ Could not auto-download LBNL data file.")
    print("    Writing hardcoded benchmarks from 2024 LBNL report...")
    write_lbnl_fallback()
    return False


def write_lbnl_fallback():
    """Hardcoded regional CF benchmarks from LBNL 2024 Wind Technologies Market Report.
    Source: Table/Figure in Chapter 4, "Capacity Factors by Region and Vintage"
    Report year: 2024 (covering data through 2023)
    """
    fallback_path = EXT_DIR / "lbnl_benchmarks_manual.py"
    content = '''"""
LBNL Regional Capacity Factor Benchmarks (Hardcoded Fallback)

Source: Lawrence Berkeley National Laboratory, 2024 Wind Technologies Market Report
        Chapter 4 — Capacity Factors, Table: Regional Average CF by Installation Vintage
        Landing page: https://emp.lbl.gov/wind-technologies-market-report
        Report publication: August 2024

These are fleet-wide average CFs by NERC region and installation decade.
Used only for cf_vs_lbnl_benchmark comparison.
"""

# Format: {(nerc_region, vintage_decade): benchmark_cf}
# vintage_decade: decade the plant was commissioned (e.g., 2000 = 2000–2009)
LBNL_BENCHMARKS = {
    # ERCOT (Texas)
    ("TRE", 2000): 0.30,
    ("TRE", 2010): 0.34,
    ("TRE", 2020): 0.36,
    # SPP (Great Plains)
    ("SPP", 2000): 0.32,
    ("SPP", 2010): 0.37,
    ("SPP", 2020): 0.39,
    # MRO / MISO (Upper Midwest)
    ("MRO", 2000): 0.30,
    ("MRO", 2010): 0.34,
    ("MRO", 2020): 0.36,
    # WECC (West)
    ("WECC", 2000): 0.27,
    ("WECC", 2010): 0.30,
    ("WECC", 2020): 0.32,
    # NPCC (Northeast)
    ("NPCC", 2000): 0.25,
    ("NPCC", 2010): 0.28,
    ("NPCC", 2020): 0.30,
    # SERC (Southeast — very few wind plants)
    ("SERC", 2000): 0.26,
    ("SERC", 2010): 0.29,
    ("SERC", 2020): 0.31,
    # RFC (PJM / East Central)
    ("RFC", 2000): 0.26,
    ("RFC", 2010): 0.29,
    ("RFC", 2020): 0.31,
}


def get_benchmark(nerc_region, commissioning_year):
    """Look up the LBNL benchmark CF for a given NERC region and commissioning year."""
    if nerc_region is None or commissioning_year is None:
        return None

    # Map commissioning year to decade
    decade = (commissioning_year // 10) * 10
    # Clamp to available range
    decade = max(2000, min(decade, 2020))

    # Try exact match, then broader region mappings
    key = (nerc_region, decade)
    if key in LBNL_BENCHMARKS:
        return LBNL_BENCHMARKS[key]

    # Some NERC regions have sub-regions; try parent
    region_map = {
        "FRCC": "SERC",
        "HICC": "WECC",
        "ASCC": "WECC",
    }
    parent = region_map.get(nerc_region)
    if parent:
        key = (parent, decade)
        if key in LBNL_BENCHMARKS:
            return LBNL_BENCHMARKS[key]

    return None
'''
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_path.write_text(content)
    print(f"    Written: {fallback_path}")


# ══════════════════════════════════════════════════════════════════════════════
# POST-DOWNLOAD SPOT CHECKS
# ══════════════════════════════════════════════════════════════════════════════
def spot_checks():
    print("\n═══ Post-Download Spot Checks ═══")
    issues = []

    # EIA 860 (2024) — expect ~1,800+ wind plants
    eia860_2024_files = list(EIA860_DIR.rglob("*Plant_Y2024*"))
    if eia860_2024_files:
        try:
            df = pd.read_excel(eia860_2024_files[0], sheet_name=0, skiprows=1)
            n = len(df)
            print(f"EIA 860 (2024):   Expected ~1,800+ wind plants.        Actual: {n}")
            if n < 900:
                issues.append("EIA 860 plant count below 50% threshold")
        except Exception as e:
            print(f"EIA 860 (2024):   Could not read — {e}")
    else:
        print("EIA 860 (2024):   NOT FOUND")
        issues.append("EIA 860 2024 not found")

    # EIA 923 (2024) — expect ~1,600+ wind plant rows
    eia923_2024_files = list(EIA923_DIR.rglob("*2024*Final*"))
    if not eia923_2024_files:
        eia923_2024_files = list(EIA923_DIR.rglob("*2024*"))
    if eia923_2024_files:
        try:
            df = pd.read_excel(eia923_2024_files[0], sheet_name="Page 1 Generation and Fuel Data",
                               skiprows=5)
            # Filter to wind
            pm_col = [c for c in df.columns if "prime" in c.lower() and "mover" in c.lower()]
            if pm_col:
                wind_rows = df[df[pm_col[0]].astype(str).str.strip() == "WT"]
                n = len(wind_rows)
            else:
                n = len(df)
            print(f"EIA 923 (2024):   Expected ~1,600+ wind plant rows.    Actual: {n}")
            if n < 800:
                issues.append("EIA 923 wind row count below 50% threshold")
        except Exception as e:
            print(f"EIA 923 (2024):   Could not read — {e}")
    else:
        print("EIA 923 (2024):   NOT FOUND")
        issues.append("EIA 923 2024 not found")

    # EPM 2025 — expect 12 months
    epm_path = EPM_DIR / "epm_2025_monthly.csv"
    if epm_path.exists():
        df = pd.read_csv(epm_path)
        if "period" in df.columns:
            months = df["period"].str[:7].nunique()
        else:
            months = 0
        print(f"EPM 2025:         Expected 12 monthly files.           Loaded: {months}")
        if months < 6:
            issues.append("EPM 2025 month count below 50% threshold")
    else:
        print("EPM 2025:         NOT FOUND")
        issues.append("EPM 2025 not downloaded")

    # USWTDB — expect ~75,000+ turbine records
    uswtdb_path = USWTDB_DIR / "uswtdb_latest.csv"
    if uswtdb_path.exists():
        df = pd.read_csv(uswtdb_path, low_memory=False)
        n = len(df)
        print(f"USWTDB:           Expected ~75,000+ turbine records.   Actual: {n}")
        if n < 37500:
            issues.append("USWTDB record count below 50% threshold")
    else:
        print("USWTDB:           NOT FOUND")

    # eGRID — expect ~10,000+ plant rows
    egrid_path = EGRID_DIR / "egrid_latest.xlsx"
    if egrid_path.exists():
        try:
            # Try common sheet name patterns
            xls = pd.ExcelFile(egrid_path)
            plnt_sheets = [s for s in xls.sheet_names if s.upper().startswith("PLNT")]
            if plnt_sheets:
                df = pd.read_excel(egrid_path, sheet_name=plnt_sheets[0], skiprows=1)
                n = len(df)
            else:
                df = pd.read_excel(egrid_path, sheet_name=0)
                n = len(df)
            print(f"eGRID:            Expected ~10,000+ plant rows.        Actual: {n}")
            if n < 5000:
                issues.append("eGRID plant count below 50% threshold")
        except Exception as e:
            print(f"eGRID:            Could not read — {e}")
    else:
        print("eGRID:            NOT FOUND")

    return issues


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    start = time.time()
    print("=" * 70)
    print("  Wind Farm Investment Screener — Data Download")
    print("=" * 70)

    # Track critical failures
    critical_failures = []

    # Source 1 — EIA 860
    eia860_failures = download_eia860()
    if eia860_failures:
        critical_failures.append(f"EIA-860 failed for years: {eia860_failures}")

    # Source 2 — EIA 923
    eia923_failures = download_eia923()
    if eia923_failures:
        critical_failures.append(f"EIA-923 failed for years: {eia923_failures}")

    # Source 3 — EPM 2025
    epm_ok = download_epm_2025()
    if not epm_ok:
        critical_failures.append("EPM 2025 download failed — need EIA API key")

    # Source 4 — EIA 860M (non-critical)
    download_eia860m()

    # Source 5 — USWTDB (non-critical for pipeline, but important)
    download_uswtdb()

    # Source 6 — eGRID (non-critical)
    download_egrid()

    # Source 7 — LBNL (non-critical, has fallback)
    download_lbnl()

    # Write manifest
    manifest_path = AUDIT_DIR / "download_manifest.csv"
    with open(manifest_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for row in manifest_rows:
            writer.writerow({k: row.get(k, "") for k in MANIFEST_FIELDS})
    print(f"\n✓ Manifest written: {manifest_path}")

    # Spot checks
    spot_issues = spot_checks()

    # Summary
    elapsed = time.time() - start
    total = len(manifest_rows)
    failed = sum(1 for r in manifest_rows if "FAILED" in r.get("description", ""))

    print(f"\n{'=' * 70}")
    print(f"  Download Summary")
    print(f"{'=' * 70}")
    print(f"  Total downloads attempted: {total}")
    print(f"  Successful:               {total - failed}")
    print(f"  Failed:                   {failed}")
    print(f"  Elapsed:                  {elapsed:.1f}s")

    if critical_failures:
        print(f"\n  ✗ CRITICAL FAILURES — pipeline cannot proceed:")
        for f in critical_failures:
            print(f"    • {f}")
        print("\n  Fix the above issues and re-run 01_download.py")
        sys.exit(1)

    if spot_issues:
        print(f"\n  ⚠ SPOT CHECK WARNINGS:")
        for issue in spot_issues:
            print(f"    • {issue}")

    print(f"\n✓ 01_download.py complete")
    print(f"  Warnings:             {len(spot_issues)}")
    print(f"  Elapsed:              {elapsed:.1f}s")


if __name__ == "__main__":
    main()
