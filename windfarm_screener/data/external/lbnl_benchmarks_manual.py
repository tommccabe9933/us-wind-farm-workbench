"""
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
