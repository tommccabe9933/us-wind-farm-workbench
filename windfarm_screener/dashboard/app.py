"""
Wind Farm Deal Desk — Distressed Wind Farm Investment Screener
Institutional-grade dashboard for screening U.S. wind farms for PE acquisition.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="U.S. Wind Farm Workbench",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OLIVE = "#4A5D23"
OLIVE_BG = "#F0F4E8"

# Full NERC region names — no abbreviations
NERC_FULL_NAMES = {
    "WECC": "Western Electricity Coordinating Council",
    "MRO": "Midwest Reliability Organization",
    "TRE": "Texas Reliability Entity",
    "SERC": "SERC Reliability Corporation",
    "NPCC": "Northeast Power Coordinating Council",
    "RFC": "ReliabilityFirst Corporation",
    "SPP": "Southwest Power Pool",
    "HI": "Hawaii",
    "AK": "Alaska",
    "FRCC": "Florida Reliability Coordinating Council",
}

# ---------------------------------------------------------------------------
# Theme — Blackstone / Palantir monochromatic + olive accent
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Global */
    .stApp { background-color: #FFFFFF; font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
    section[data-testid="stSidebar"] { background-color: #F7F8FA; border-right: 1px solid #E5E7EB; }
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #1A1A1A; font-size: 11px; font-weight: 700;
        text-transform: uppercase; letter-spacing: 1.2px; margin-top: 18px; margin-bottom: 4px;
        border-bottom: 1px solid #E5E7EB; padding-bottom: 4px;
    }
    section[data-testid="stSidebar"] .stMarkdown p { font-size: 13px; color: #6B7280; }
    section[data-testid="stSidebar"] label { font-size: 12px !important; color: #1A1A1A !important; }

    /* Headers */
    h1 { color: #FFFFFF !important; font-weight: 700 !important; font-size: 22px !important;
         letter-spacing: 0.5px !important; }
    h2 { color: #1A1A1A !important; font-weight: 700 !important; font-size: 16px !important;
         text-transform: uppercase !important; letter-spacing: 0.8px !important; }
    h3 { color: #1A1A1A !important; font-weight: 600 !important; font-size: 14px !important; }

    /* Black header bar */
    .header-bar { background: #000000; color: #FFFFFF; padding: 18px 24px; margin: -1rem -1rem 0 -1rem;
        border-bottom: 1px solid #333; }
    .header-bar h1 { margin: 0 !important; padding: 0 !important; }
    .header-subtitle { color: #9CA3AF; font-size: 12px; margin-top: 4px; letter-spacing: 0.3px; }
    .header-badge { background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2);
        color: #9CA3AF; padding: 4px 12px; border-radius: 2px; font-size: 10px;
        font-weight: 600; letter-spacing: 0.5px; float: right; margin-top: -30px; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 0; border-bottom: 2px solid #E5E7EB; }
    .stTabs [data-baseweb="tab"] { background: transparent; border: none; padding: 10px 24px;
        font-size: 12px; font-weight: 600; color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.8px; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { color: #1A1A1A;
        border-bottom: 2px solid #1A1A1A; }

    /* Metrics */
    [data-testid="stMetricValue"] { font-size: 20px; font-weight: 700; color: #1A1A1A;
        font-family: 'Inter', sans-serif; }
    [data-testid="stMetricLabel"] { font-size: 10px; font-weight: 700; color: #6B7280;
        text-transform: uppercase; letter-spacing: 0.8px; }
    [data-testid="stMetricDelta"] { font-size: 11px; }

    /* Dataframe */
    .stDataFrame { border: 1px solid #E5E7EB; border-radius: 4px; }

    /* glide-data-grid header styling (canvas-based — limited CSS reach) */
    [data-testid="stDataFrameResizable"] { border: 1px solid #E5E7EB; border-radius: 4px; }
    [data-testid="stDataFrameResizable"] canvas { border-radius: 4px; }

    /* Cards */
    .info-card { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 4px;
        padding: 14px; margin: 4px 0; }
    .info-label { font-size: 10px; color: #9CA3AF; text-transform: uppercase;
        letter-spacing: 0.8px; font-weight: 700; margin-bottom: 2px; }
    .info-value { font-size: 15px; color: #1A1A1A; font-weight: 600;
        font-family: 'Inter', sans-serif; }
    .info-source { font-size: 10px; color: #9CA3AF; margin-top: 2px; }

    /* Provenance card */
    .provenance-card { background: #FFFFFF; border: 1px solid #E5E7EB; border-left: 4px solid """ + OLIVE + """;
        border-radius: 4px; padding: 16px; margin: 8px 0; }
    .provenance-card strong { color: #1A1A1A; }
    .provenance-card p { font-size: 13px; color: #6B7280; margin: 4px 0; }

    /* Badges */
    .badge-black { background: #1A1A1A; color: #FFFFFF; padding: 2px 10px; border-radius: 2px;
        font-size: 11px; font-weight: 700; display: inline-block; }
    .badge-gray { background: #6B7280; color: #FFFFFF; padding: 2px 10px; border-radius: 2px;
        font-size: 11px; font-weight: 700; display: inline-block; }
    .badge-olive { background: """ + OLIVE + """; color: #FFFFFF; padding: 2px 10px; border-radius: 2px;
        font-size: 11px; font-weight: 700; display: inline-block; }

    /* Expander */
    .streamlit-expanderHeader { font-size: 13px; font-weight: 600; color: #1A1A1A; }

    /* Footer */
    .footer-provenance { font-size: 11px; color: #9CA3AF; border-top: 1px solid #E5E7EB;
        padding-top: 12px; margin-top: 24px; }

    /* Hide Streamlit branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Plotly theme — monochromatic
# ---------------------------------------------------------------------------
PLOTLY_LAYOUT = dict(
    plot_bgcolor="#FFFFFF",
    paper_bgcolor="#FFFFFF",
    font=dict(family="Inter, -apple-system, BlinkMacSystemFont, sans-serif", size=12, color="#1A1A1A"),
    margin=dict(t=40, b=40, l=60, r=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
    hoverlabel=dict(bgcolor="#1A1A1A", font_size=12, font_color="white"),
)
AXIS_STYLE = dict(gridcolor="#F3F4F6", linecolor="#E5E7EB", linewidth=1, zerolinecolor="#E5E7EB")

# ---------------------------------------------------------------------------
# Distress signal definitions
# ---------------------------------------------------------------------------
DISTRESS_SIGNALS = [
    {"code": "flag_declining_3yr", "label": "Declining 3-Year Average",
     "desc": "3-year rolling average capacity factor is lower than prior year",
     "source": "EIA-923 / EPM generation data",
     "why": "Persistent decline suggests structural degradation, not just a bad wind year"},
    {"code": "flag_bottom_quartile", "label": "Bottom Quartile in Region",
     "desc": "Plant's latest capacity factor is in the bottom 25% of all plants in same NERC region",
     "source": "EIA-923 / EPM + eGRID region",
     "why": "Regional context separates site-specific problems from wind resource variability"},
    {"code": "flag_below_peak", "label": "15%+ Below Peak Generation",
     "desc": "Latest generation per MW is 15%+ below the plant's historical peak",
     "source": "EIA-923 / EPM generation data",
     "why": "Large decline from peak suggests operational degradation or curtailment issues"},
    {"code": "flag_consecutive_decline", "label": "3+ Consecutive Years of Decline",
     "desc": "Generation per MW has decreased for 3 or more consecutive years",
     "source": "EIA-923 / EPM generation data",
     "why": "Consecutive decline is a stronger distress signal than volatile year-over-year changes"},
    {"code": "flag_ptc_expired", "label": "Production Tax Credit Expired",
     "desc": "Plant age > 12 years (PTC provides 10 years of credits; 2-year buffer)",
     "source": "EIA-860 commissioning year",
     "why": "PTC expiration reduces revenue by ~$26/MWh — the most common trigger for distressed sales"},
    {"code": "flag_repower_candidate", "label": "Repower Candidate",
     "desc": "Turbine age >= 15 AND plant age >= 10",
     "source": "USWTDB + EIA-860",
     "why": "Modern turbines produce 2-3x more energy — core PE value creation thesis"},
    {"code": "flag_independent_owner", "label": "Small Owner (3 or Fewer Plants)",
     "desc": "Owner operates 3 or fewer plants in the dataset",
     "source": "EIA-860 operator name",
     "why": "Small operators lack scale economies — more likely to sell"},
    {"code": "flag_capacity_changed", "label": "Capacity Changed in 2025",
     "desc": "Capacity reported in EIA-860M differs from EIA-860 annual",
     "source": "EIA-860 vs EIA-860M",
     "why": "Capacity changes may indicate partial retirement or repowering activity"},
    {"code": "flag_high_cf", "label": "Data Quality Flag (Capacity Factor > 65%)",
     "desc": "CF > 0.65 is physically implausible for wind — likely a data error",
     "source": "Computed from generation / (capacity x 8,760)",
     "why": "Flags plants whose data should be verified before drawing conclusions"},
    {"code": "flag_data_gap", "label": "Limited History (< 3 Years of Data)",
     "desc": "Plant has less than 3 years of generation data, limiting trend analysis",
     "source": "EIA-923 / EPM coverage",
     "why": "Trend-based distress signals are unreliable without sufficient history"},
]

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


@st.cache_data(show_spinner="Loading wind farm data...")
def load_data():
    path = BASE_DIR / "data" / "processed" / "wind_plants_kpis.parquet"
    df = pd.read_parquet(path)

    # Owner display: use utility_name as fallback
    if "owner_name" in df.columns and "utility_name" in df.columns:
        df["owner_display"] = df["owner_name"].fillna(df["utility_name"])
    elif "utility_name" in df.columns:
        df["owner_display"] = df["utility_name"]
    else:
        df["owner_display"] = "Unknown"

    # Full NERC region names
    if "nerc_region" in df.columns:
        df["nerc_region_full"] = df["nerc_region"].map(NERC_FULL_NAMES).fillna(df["nerc_region"])

    # Potential generation (theoretical max MWh) for 2024
    cap_col = "capacity_mw_2024" if "capacity_mw_2024" in df.columns else "capacity_mw_2023"
    if cap_col in df.columns:
        df["potential_gen_mwh_2024"] = df[cap_col] * 8760

    # 2025 vs 2024 production change (%)
    if "gen_mwh_2025" in df.columns and "gen_mwh_2024" in df.columns:
        mask = df["gen_mwh_2024"].notna() & df["gen_mwh_2024"] > 0 & df["gen_mwh_2025"].notna()
        df.loc[mask, "gen_change_2025_vs_2024"] = (
            (df.loc[mask, "gen_mwh_2025"] - df.loc[mask, "gen_mwh_2024"])
            / df.loc[mask, "gen_mwh_2024"] * 100
        )

    # Month-over-month: latest 2025 month vs same month 2024
    for m in range(12, 0, -1):
        col_25 = f"gen_mwh_2025_{m:02d}"
        col_24 = f"gen_mwh_2024_{m:02d}"
        if col_25 in df.columns and col_24 in df.columns:
            has_data = df[col_25].notna() & df[col_24].notna() & (df[col_24] > 0)
            if has_data.any():
                df["latest_month_num"] = m
                df["latest_month_gen_2025"] = df[col_25]
                df["latest_month_gen_2024"] = df[col_24]
                df.loc[has_data, "month_vs_prior_year"] = (
                    (df.loc[has_data, col_25] - df.loc[has_data, col_24])
                    / df.loc[has_data, col_24] * 100
                )
                break

    # Pre-multiply decimal columns to percentage scale for display
    # CF values: 0.285 → 28.5 so printf format "%.1f%%" shows "28.5%"
    pct_cols = [f"cf_{y}" for y in range(2018, 2026)]
    pct_cols += [
        "cf_3yr_2022_2024", "cf_3yr_2023_2025",
        "cf_5yr_2020_2024", "cf_7yr_2018_2024",
        "cf_latest", "regional_median_cf",
        "underperformance_gap",
    ]
    for col in pct_cols:
        if col in df.columns:
            df[col] = df[col] * 100

    # EIA Plant Browser URL
    if "plant_id" in df.columns:
        df["eia_browser_url"] = df["plant_id"].apply(
            lambda x: f"https://www.eia.gov/electricity/data/browser/#/plant/{int(x)}" if pd.notna(x) else None
        )

    return df


df = load_data()
CAP_COL = "capacity_mw_2024" if "capacity_mw_2024" in df.columns else "capacity_mw_2023"


def safe_val(series):
    return sorted(series.dropna().unique().tolist())


def fmt_pct(v, decimals=1):
    if pd.isna(v): return "—"
    return f"{v:.{decimals}f}%"


def fmt_pp(v):
    if pd.isna(v): return "—"
    return f"{v:+.1f} pp"


def fmt_num(v, decimals=0):
    if pd.isna(v): return "—"
    return f"{v:,.{decimals}f}"


def fmt_int(v):
    if pd.isna(v): return "—"
    return f"{int(v)}"


# ---------------------------------------------------------------------------
# Sidebar — Filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Screening Filters")
    st.caption(f"{len(df):,} U.S. wind plants in dataset (>= 10 MW)")
    mask = pd.Series(True, index=df.index)

    st.markdown("### Geography")
    states = safe_val(df["state"]) if "state" in df.columns else []
    if states:
        sel_states = st.multiselect("State", states, default=[], key="states",
                                    placeholder="All states")
        if sel_states:
            mask &= df["state"].isin(sel_states)

    regions = safe_val(df["nerc_region"]) if "nerc_region" in df.columns else []
    if regions:
        # Show full names in the filter
        region_display = {r: NERC_FULL_NAMES.get(r, r) for r in regions}
        sel_regions = st.multiselect("NERC Region", regions, default=[], key="nerc",
                                     format_func=lambda x: NERC_FULL_NAMES.get(x, x),
                                     placeholder="All regions")
        if sel_regions:
            mask &= df["nerc_region"].isin(sel_regions)

    st.markdown("### Plant Characteristics")
    if CAP_COL in df.columns:
        cap_min, cap_max = float(df[CAP_COL].min()), float(df[CAP_COL].max())
        cap_range = st.slider("Nameplate Capacity (MW)", cap_min, max(cap_max, 500.0),
                              (cap_min, max(cap_max, 500.0)), step=5.0)
        mask &= df[CAP_COL].fillna(0).between(cap_range[0], cap_range[1])

    if "asset_age" in df.columns:
        age_min, age_max = int(df["asset_age"].min()), int(df["asset_age"].max())
        age_range = st.slider("Plant Age (Years)", age_min, max(age_max, 40),
                              (age_min, max(age_max, 40)))
        mask &= df["asset_age"].fillna(0).between(age_range[0], age_range[1])

    st.markdown("### Distress Signals")
    flag_filters = [
        ("Declining 3-year average", "flag_declining_3yr"),
        ("Bottom quartile in region", "flag_bottom_quartile"),
        ("15%+ below peak generation", "flag_below_peak"),
        ("3+ consecutive years of decline", "flag_consecutive_decline"),
        ("Production Tax Credit expired", "flag_ptc_expired"),
        ("Repower candidate", "flag_repower_candidate"),
        ("Small owner (3 or fewer plants)", "flag_independent_owner"),
        ("Capacity changed in 2025", "flag_capacity_changed"),
        ("Data quality flag (CF > 65%)", "flag_high_cf"),
        ("Limited history (< 3 years)", "flag_data_gap"),
    ]
    for label, col in flag_filters:
        if col in df.columns:
            if st.checkbox(label, value=False, key=f"ff_{col}"):
                mask &= df[col].fillna(False).astype(bool)

    st.markdown("### Owner")
    owner_search = st.text_input("Search by owner", "", placeholder="e.g. NextEra")
    if owner_search:
        mask &= df["owner_display"].fillna("").str.contains(owner_search, case=False, na=False)

    filtered = df.loc[mask].copy()
    st.markdown("---")
    st.markdown(f"**{len(filtered):,} plants** match filters")
    if CAP_COL in filtered.columns:
        st.caption(f"{filtered[CAP_COL].sum():,.0f} MW total capacity")

# ---------------------------------------------------------------------------
# Header — Black bar with white text
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="header-bar">'
    '<h1>U.S. WIND FARM WORKBENCH</h1>'
    '<div class="header-subtitle">For Dad &amp; Sequitur&ensp;·&ensp;U.S. Utility-Scale Wind Farms (&ge; 10 MW)&ensp;·&ensp;'
    'Sources: EIA-860, EIA-923, Electric Power Monthly, USWTDB, eGRID, LBNL</div>'
    '<div class="header-badge">100% FEDERAL DATA · ZERO AI GENERATION</div>'
    '</div>', unsafe_allow_html=True
)

# KPI strip
if not filtered.empty:
    st.markdown("")
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Plants", f"{len(filtered):,}")
    if CAP_COL in filtered.columns:
        k2.metric("Total Capacity", f"{filtered[CAP_COL].sum():,.0f} MW")
    if "cf_3yr_2022_2024" in filtered.columns:
        k3.metric("Median Capacity Factor", f"{filtered['cf_3yr_2022_2024'].median():.1f}%")
    if "distress_signal_count" in filtered.columns:
        k4.metric("Median Distress Signals", f"{filtered['distress_signal_count'].median():.0f} / 10")
    if "flag_ptc_expired" in filtered.columns:
        k5.metric("Tax Credit Expired", f"{filtered['flag_ptc_expired'].sum():,}")
    if "flag_repower_candidate" in filtered.columns:
        k6.metric("Repower Candidates", f"{filtered['flag_repower_candidate'].sum():,}")

st.markdown("---")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["SCREENER TABLE", "PLANT DETAIL", "MARKET OVERVIEW", "TRENDS"])

# ========================== TAB 1: Screener Table ============================
with tab1:
    if filtered.empty:
        st.info("No plants match the current filters. Adjust the sidebar filters to see results.")
    else:
        # Build display dataframe with proper column order:
        # Identity → Physical Facts → Raw Data → Derived Metrics → Signals
        screener_cols = [
            # Identity + Owner
            "plant_name", "owner_display", "state", "nerc_region",
            # Physical Facts
            "turbine_count", "asset_age", "turbine_age",
            # Capacity & Generation
            "potential_gen_mwh_2024", "gen_mwh_2024",
            # Capacity Factors
            "cf_2024", "cf_2025",
            # 3-year averages and changes (after CF 2025)
            "cf_3yr_2022_2024", "yoy_3yr_avg",
            # Production change
            "gen_change_2025_vs_2024",
            # Peer comparison
            "regional_median_cf", "underperformance_gap",
            "cf_regional_percentile", "national_pctile",
            # Trend
            "trend_direction",
            # Owner portfolio
            "owner_plant_count",
            # Signals
            "distress_signal_count", "ptc_status",
            # Link
            "eia_browser_url",
        ]
        available_cols = [c for c in screener_cols if c in filtered.columns]
        display_df = filtered[available_cols].copy()

        # Sort by underperformance gap ascending (worst performers first)
        if "underperformance_gap" in display_df.columns:
            display_df = display_df.sort_values("underperformance_gap", ascending=True, na_position="last")

        # Pre-format numbers with commas (Streamlit printf doesn't support comma grouping)
        def comma(v, decimals=0):
            if pd.isna(v): return ""
            return f"{v:,.{decimals}f}"

        def pct(v, decimals=1):
            if pd.isna(v): return ""
            return f"{v:.{decimals}f}%"

        def signed_pct(v, decimals=1):
            if pd.isna(v): return ""
            return f"{v:+.{decimals}f}%"

        def signed_pp(v):
            if pd.isna(v): return ""
            return f"{v:+.1f} pp"

        # Format numeric columns as strings with proper formatting
        for col in ["gen_mwh_2024", "potential_gen_mwh_2024"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(comma)
        for col in ["cf_2024", "cf_2025", "cf_3yr_2022_2024", "regional_median_cf"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(pct)
        if "underperformance_gap" in display_df.columns:
            display_df["underperformance_gap"] = display_df["underperformance_gap"].apply(signed_pp)
        if "yoy_3yr_avg" in display_df.columns:
            display_df["yoy_3yr_avg"] = display_df["yoy_3yr_avg"].apply(signed_pct)
        if "gen_change_2025_vs_2024" in display_df.columns:
            display_df["gen_change_2025_vs_2024"] = display_df["gen_change_2025_vs_2024"].apply(signed_pct)
        for col in ["turbine_count", "asset_age", "turbine_age", "owner_plant_count", "distress_signal_count"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda v: "" if pd.isna(v) else f"{int(v)}")
        for col in ["cf_regional_percentile", "national_pctile"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda v: "" if pd.isna(v) else f"{v:.0f}")

        # Column config — all TextColumns since data is pre-formatted
        col_config = {
            "plant_name": st.column_config.TextColumn("Plant Name", width="large",
                help="Source: EIA Form 860 — https://www.eia.gov/electricity/data/eia860/"),
            "owner_display": st.column_config.TextColumn("Owner", width="medium",
                help="Plant owner or operating utility. Source: EIA Form 860 — https://www.eia.gov/electricity/data/eia860/"),
            "state": st.column_config.TextColumn("State", width="small",
                help="Source: EIA Form 860 — https://www.eia.gov/electricity/data/eia860/"),
            "nerc_region": st.column_config.TextColumn("NERC Region", width="small",
                help="North American Electric Reliability Corporation region. Source: EPA eGRID — https://www.epa.gov/egrid"),
            "turbine_count": st.column_config.TextColumn("Turbines", width="small",
                help="Number of turbines at this plant. Source: U.S. Wind Turbine Database (USWTDB) — https://eerscmap.usgs.gov/uswtdb/"),
            "asset_age": st.column_config.TextColumn("Plant Age (Years)", width="small",
                help="Formula: 2024 − commissioning year. Source: EIA Form 860 — https://www.eia.gov/electricity/data/eia860/"),
            "turbine_age": st.column_config.TextColumn("Turbine Age (Years)", width="small",
                help="Age of oldest turbines on site. Source: USWTDB — https://eerscmap.usgs.gov/uswtdb/"),
            "potential_gen_mwh_2024": st.column_config.TextColumn("Nameplate Capacity (MWh/yr)", width="medium",
                help="Formula: Nameplate Capacity (MW) × 8,760 hours/year. Maximum theoretical output per year. Source: derived from EIA-860"),
            "gen_mwh_2024": st.column_config.TextColumn("Actual Generation 2024 (MWh)", width="medium",
                help="Total net electricity generated in calendar year 2024. Source: EIA Form 923 — https://www.eia.gov/electricity/data/eia923/"),
            "cf_2024": st.column_config.TextColumn("Capacity Factor 2024", width="medium",
                help="Formula: Actual Generation (MWh) ÷ Nameplate Capacity (MWh/yr). U.S. wind fleet average ≈ 34%. Source: EIA-923 / EIA-860"),
            "cf_2025": st.column_config.TextColumn("Capacity Factor 2025 (Preliminary)", width="medium",
                help="Formula: Actual Generation ÷ Nameplate Capacity using 2025 data. Preliminary — may be revised. Source: EIA Electric Power Monthly — https://www.eia.gov/electricity/monthly/"),
            "cf_3yr_2022_2024": st.column_config.TextColumn("Capacity Factor 3-Year Average (2022-2024)", width="medium",
                help="Formula: mean(CF 2022, CF 2023, CF 2024). Smooths annual wind variability. Source: EIA-923"),
            "regional_median_cf": st.column_config.TextColumn("NERC Region Median Capacity Factor", width="medium",
                help="Formula: median capacity factor for all plants in same NERC region. Source: derived from EIA-923 + EPA eGRID"),
            "underperformance_gap": st.column_config.TextColumn("Gap vs. NERC Region Median", width="medium",
                help="Formula: Plant Capacity Factor − NERC Region Median. Negative = underperforming regional peers. Source: derived from EIA-923 + EPA eGRID"),
            "cf_regional_percentile": st.column_config.TextColumn("Capacity Factor Percentile (NERC Region)", width="medium",
                help="Where this plant ranks on capacity factor among all plants in same NERC region. 0 = worst, 100 = best. Source: derived from EIA-923"),
            "national_pctile": st.column_config.TextColumn("Capacity Factor Percentile (National)", width="medium",
                help="Where this plant ranks on capacity factor among all ~1,086 U.S. wind plants. 0 = worst, 100 = best. Source: derived from EIA-923"),
            "trend_direction": st.column_config.TextColumn("Generation Trend (3-Year)", width="medium",
                help="Whether generation per MW is Declining / Stable / Improving over the last 3 years. Source: derived from EIA-923"),
            "yoy_3yr_avg": st.column_config.TextColumn("Generation Change Year-over-Year (3-Year Avg)", width="medium",
                help="Formula: mean of annual % change in generation per MW from 2022 to 2024. Source: EIA-923"),
            "owner_plant_count": st.column_config.TextColumn("Owner Portfolio Size", width="small",
                help="Number of wind plants in this dataset owned by same entity. Source: derived from EIA-860"),
            "distress_signal_count": st.column_config.TextColumn("Distress Signals (of 10)", width="medium",
                help="Count of 10 boolean distress flags triggered. Each flag uses a specific threshold against government data. See Plant Detail tab for details."),
            "ptc_status": st.column_config.TextColumn("Production Tax Credit Status", width="medium",
                help="Active (plant age < 10 yrs) / Expiring (10–12 yrs) / Expired (> 12 yrs). Production Tax Credit provides ~$26/MWh for 10 years. Source: EIA-860 commissioning year"),
            "gen_change_2025_vs_2024": st.column_config.TextColumn("2025 vs 2024 Production Change",
                width="medium",
                help="Formula: (Generation 2025 − Generation 2024) / Generation 2024 × 100. Positive = production increased year-over-year. Source: EIA-923 + EIA Electric Power Monthly"),
            "eia_browser_url": st.column_config.LinkColumn("EIA Source",
                display_text="View on EIA", help="Click to verify this plant's data directly on the EIA website — https://www.eia.gov/electricity/data/browser/"),
        }

        # Column display config: short header name + full tooltip
        _col_cfg = {
            # (header_name, tooltip, min_width)
            "plant_name": ("Plant Name", "EIA Form 860", 240),
            "owner_display": ("Owner", "Plant owner or operating utility. Source: EIA Form 860", 180),
            "state": ("State", "Source: EIA Form 860", 70),
            "nerc_region": ("NERC", "North American Electric Reliability Corporation region. Source: EPA eGRID", 70),
            "turbine_count": ("Turbines", "Source: U.S. Wind Turbine Database (USWTDB)", 90),
            "asset_age": ("Age (yrs)", "Plant age in years. Formula: 2024 − commissioning year. Source: EIA Form 860", 80),
            "turbine_age": ("Turb Age", "Turbine age in years. Source: USWTDB", 80),
            "potential_gen_mwh_2024": ("Capacity MWh/yr", "Nameplate Capacity (MW) × 8,760 hrs. Source: EIA-860", 140),
            "gen_mwh_2024": ("Gen 2024 MWh", "Actual generation in 2024. Source: EIA Form 923", 130),
            "cf_2024": ("CF 2024", "Capacity Factor 2024. Formula: Actual ÷ Potential. Source: EIA-923 / EIA-860", 90),
            "cf_2025": ("CF 2025", "Capacity Factor 2025 (Preliminary). Source: EIA Electric Power Monthly", 90),
            "cf_3yr_2022_2024": ("CF 3yr Avg", "Capacity Factor 3-Year Average (2022-2024). Source: EIA-923", 100),
            "yoy_3yr_avg": ("YoY 3yr", "Generation change year-over-year (3-year avg). Source: EIA-923", 85),
            "gen_change_2025_vs_2024": ("2025 vs 2024 Chg", "2025 vs 2024 production change (%). Source: EIA-923 + EPM", 120),
            "regional_median_cf": ("Region Median", "NERC region median capacity factor. Source: EIA-923 + EPA eGRID", 110),
            "underperformance_gap": ("Gap vs Region", "Gap vs. NERC region median (pp). Negative = underperforming. Source: EIA-923", 100),
            "cf_regional_percentile": ("Region Pctile", "CF percentile within NERC region. 0=worst, 100=best", 100),
            "national_pctile": ("Nat'l Pctile", "CF percentile nationally. 0=worst, 100=best", 100),
            "trend_direction": ("Trend", "3-year generation trend: Declining / Stable / Improving", 100),
            "owner_plant_count": ("Portfolio", "Number of wind plants owned by same entity", 80),
            "distress_signal_count": ("Distress (of 10)", "Distress signals triggered (of 10)", 100),
            "ptc_status": ("PTC Status", "Production Tax Credit status: Active / Expiring / Expired", 90),
            "eia_browser_url": ("EIA Link", "Click to verify on EIA website", 110),
        }

        # Rename columns for display
        rename_map = {c: _col_cfg[c][0] for c in display_df.columns if c in _col_cfg}
        ag_df = display_df.rename(columns=rename_map)

        gb = GridOptionsBuilder.from_dataframe(ag_df)
        gb.configure_default_column(
            sortable=True, filterable=True, resizable=True,
            minWidth=70, wrapHeaderText=False, autoHeaderHeight=False,
            suppressMenu=True,
        )

        # Configure each column with width and tooltip
        for col_key, (header, tooltip, min_w) in _col_cfg.items():
            if header in ag_df.columns:
                extra = {"headerTooltip": tooltip, "minWidth": min_w}
                if col_key == "plant_name":
                    extra["pinned"] = "left"
                    extra["maxWidth"] = 400
                    extra["cellRenderer"] = JsCode("""
                        class PlantNameRenderer {
                            init(params) {
                                this.eGui = document.createElement('span');
                                this.eGui.innerText = params.value || '';
                                this.eGui.style.cursor = 'pointer';
                                this.eGui.style.color = '#1A1A1A';
                                this.eGui.style.fontWeight = '500';
                                this.eGui.style.textDecoration = 'underline';
                                this.eGui.style.textDecorationColor = '#9CA3AF';
                            }
                            getGui() { return this.eGui; }
                        }
                    """)
                elif col_key == "eia_browser_url":
                    extra["cellRenderer"] = JsCode("""
                        class UrlRenderer {
                            init(params) {
                                this.eGui = document.createElement('a');
                                if (params.value) {
                                    this.eGui.href = params.value;
                                    this.eGui.innerText = 'View on EIA';
                                    this.eGui.target = '_blank';
                                    this.eGui.style.color = '#4A5D23';
                                    this.eGui.style.textDecoration = 'underline';
                                } else {
                                    this.eGui.innerText = '';
                                }
                            }
                            getGui() { return this.eGui; }
                        }
                    """)
                gb.configure_column(header, **extra)

        gb.configure_selection(selection_mode="single", use_checkbox=False)
        grid_options = gb.build()

        # Custom CSS for black headers — must use custom_css param (iframe)
        custom_css = {
            "#gridToolBar": {"display": "none"},
            ".ag-header": {"background-color": "#000000 !important", "border-bottom": "2px solid #333333 !important"},
            ".ag-header-row": {"background-color": "#000000 !important", "color": "#FFFFFF !important"},
            ".ag-header-cell": {"background-color": "#000000 !important", "color": "#FFFFFF !important", "font-size": "11px !important", "font-weight": "600 !important", "text-transform": "uppercase !important", "letter-spacing": "0.3px !important"},
            ".ag-header-cell-text": {"color": "#FFFFFF !important"},
            ".ag-header-cell-label .ag-header-cell-text": {"color": "#FFFFFF !important"},
            ".ag-header-viewport": {"background-color": "#000000 !important"},
            ".ag-pinned-left-header": {"background-color": "#000000 !important"},
            ".ag-header-cell-resize": {"background-color": "#000000 !important"},
            ".ag-icon": {"color": "#FFFFFF !important"},
            ".ag-row-even": {"background-color": "#FFFFFF !important"},
            ".ag-row-odd": {"background-color": "#F9FAFB !important"},
            ".ag-row-hover": {"background-color": "#F0F4E8 !important"},
            ".ag-cell": {"font-size": "12px !important", "color": "#1A1A1A !important", "font-family": "'Inter', -apple-system, sans-serif !important"},
            ".ag-root-wrapper": {"border": "1px solid #E5E7EB !important", "border-radius": "4px !important"},
        }

        grid_response = AgGrid(
            ag_df, gridOptions=grid_options, custom_css=custom_css,
            height=650, theme="alpine",
            allow_unsafe_jscode=True,
            update_mode="SELECTION_CHANGED",
        )

        # Handle row selection for cross-tab navigation
        selected_rows = grid_response.get("selected_rows", None)
        if selected_rows is not None and len(selected_rows) > 0:
            if isinstance(selected_rows, pd.DataFrame):
                selected_name = selected_rows.iloc[0].get("Plant Name", "")
            else:
                selected_name = selected_rows[0].get("Plant Name", "")
            if selected_name:
                st.session_state["selected_plant"] = selected_name
                st.info(f"**{selected_name}** selected — click the **PLANT DETAIL** tab above to view full analysis.")

        # Column definitions
        with st.expander("Column Definitions"):
            defs = [
                {"Column": "Plant Name", "Description": "EIA-registered facility name", "Source": "EIA Form 860"},
                {"Column": "State", "Description": "U.S. state where the plant is located", "Source": "EIA Form 860"},
                {"Column": "NERC Region", "Description": "North American Electric Reliability Corporation region", "Source": "EPA eGRID"},
                {"Column": "Turbine Count", "Description": "Number of wind turbines at this site", "Source": "U.S. Wind Turbine Database (USGS)"},
                {"Column": "Plant Age (Years)", "Description": "Years since first generator was commissioned", "Source": "EIA Form 860"},
                {"Column": "Turbine Age (Years)", "Description": "Age of oldest turbines at site", "Source": "USWTDB"},
                {"Column": "Nameplate Capacity (MW)", "Description": "Total nameplate capacity of all generators", "Source": "EIA Form 860"},
                {"Column": "Actual Generation 2024 (MWh)", "Description": "Total net electricity generated in calendar year 2024", "Source": "EIA Form 923"},
                {"Column": "Potential Generation 2024 (MWh)", "Description": "Theoretical maximum output if running at 100% capacity for all 8,760 hours in a year. Formula: Nameplate Capacity (MW) x 8,760 hours", "Source": "Derived from EIA-860"},
                {"Column": "Capacity Factor 2024", "Description": "Actual Generation / Potential Generation. The core efficiency metric. U.S. wind fleet average is ~34%.", "Source": "EIA-923 / EIA-860"},
                {"Column": "Capacity Factor 2025 (Preliminary)", "Description": "Same calculation using 2025 data from EIA Electric Power Monthly API. Preliminary — may be revised.", "Source": "EIA Electric Power Monthly"},
                {"Column": "Capacity Factor (3-Year Average)", "Description": "Average of 2022, 2023, and 2024 capacity factors. Smooths annual wind variability.", "Source": "EIA-923"},
                {"Column": "Gap vs. Regional Average", "Description": "Plant capacity factor minus median for all plants in same NERC region. Negative values = underperforming peers.", "Source": "Derived"},
                {"Column": "Distress Signals", "Description": "Count of 10 boolean flags triggered (each independently verifiable)", "Source": "Multiple"},
                {"Column": "Production Tax Credit Status", "Description": "Active (plant age < 10 years) / Expiring (10-12 years) / Expired (> 12 years)", "Source": "EIA-860"},
            ]
            st.dataframe(pd.DataFrame(defs), hide_index=True, use_container_width=True)

        # Methodology
        with st.expander("Methodology"):
            st.markdown("""
**Data Sources**

| Source | Publisher | Fields Used |
|--------|-----------|-------------|
| EIA Form 860 (Annual) | U.S. Energy Information Administration | Plant name, location, capacity, commissioning year, owner |
| EIA Form 923 (Annual) | U.S. Energy Information Administration | Annual generation (2018-2024) |
| EIA Electric Power Monthly (API) | U.S. Energy Information Administration | Monthly generation (2025) |
| U.S. Wind Turbine Database | U.S. Geological Survey | Turbine count, age, manufacturer, hub height, rotor diameter |
| EPA eGRID | U.S. Environmental Protection Agency | NERC region assignment |
| LBNL Wind Technologies Market Report | Lawrence Berkeley National Laboratory | Regional capacity factor benchmarks |

**Key Formulas**

| Metric | Formula | Example |
|--------|---------|---------|
| Capacity Factor | Actual Generation (MWh) / Potential Generation (MWh) | 450,000 / 1,752,600 = 25.7% |
| Potential Generation | Nameplate Capacity (MW) x 8,760 hours/year | 200 MW x 8,760 = 1,752,000 MWh |
| Gap vs. Regional Average | Plant CF - Median CF for NERC region | 25.7% - 33.2% = -7.5 percentage points |

**What This Tool Does NOT Do**
- Does NOT predict future performance
- Does NOT estimate values for missing data (gaps are shown as gaps)
- Does NOT use AI or machine learning to generate any data points
- Does NOT provide investment recommendations
- Does NOT replace site-level engineering diligence
""")

        csv = display_df.to_csv(index=False).encode("utf-8")
        st.download_button("Export Filtered Data (CSV)", csv, "wind_deal_desk_export.csv", "text/csv")


# ========================== TAB 2: Plant Detail ============================
with tab2:
    if filtered.empty:
        st.info("No plants match the current filters.")
    else:
        plant_names = sorted(filtered["plant_name"].dropna().unique().tolist())

        default_idx = 0
        if "selected_plant" in st.session_state:
            sel = st.session_state["selected_plant"]
            if sel in plant_names:
                default_idx = plant_names.index(sel)

        selected_plant = st.selectbox("Select a plant", plant_names, index=default_idx, key="plant_select")

        plant_row = filtered[filtered["plant_name"] == selected_plant]
        if plant_row.empty:
            st.warning("Plant not found in filtered data.")
        else:
            plant = plant_row.iloc[0]
            plant_id = plant.get("plant_id", None)
            eia_url = plant.get("eia_browser_url", None)

            # Provenance card
            st.markdown(
                '<div class="provenance-card">'
                '<strong>All data on this page comes directly from U.S. federal government databases.</strong>'
                '<p>No values are estimated, predicted, or generated by AI. '
                'Every number can be verified at the linked government source.</p>'
                '</div>', unsafe_allow_html=True
            )

            # Source links
            with st.expander("Data Sources for This Plant"):
                source_data = [
                    {"Data Point": "Plant name, location, capacity",
                     "Source": "EIA Form 860 (Annual)",
                     "Link": "https://www.eia.gov/electricity/data/eia860/",
                     "Reference": f"Plant file, Plant ID {fmt_int(plant_id)}"},
                    {"Data Point": "Annual energy production (2018-2024)",
                     "Source": "EIA Form 923 (Annual)",
                     "Link": "https://www.eia.gov/electricity/data/eia923/",
                     "Reference": "Schedule 2/3/4/5, filtered to wind"},
                    {"Data Point": "Monthly energy production (2025)",
                     "Source": "EIA Electric Power Monthly",
                     "Link": "https://www.eia.gov/electricity/monthly/",
                     "Reference": "Plant-level generation via API"},
                    {"Data Point": "Turbine details (age, manufacturer, model)",
                     "Source": "U.S. Wind Turbine Database",
                     "Link": "https://eerscmap.usgs.gov/uswtdb/",
                     "Reference": f"Turbine records for Plant ID {fmt_int(plant_id)}"},
                    {"Data Point": "Grid region",
                     "Source": "EPA eGRID",
                     "Link": "https://www.epa.gov/egrid",
                     "Reference": "Plant-level NERC region assignment"},
                ]
                if eia_url:
                    source_data.append({
                        "Data Point": "EIA Plant Browser (interactive)",
                        "Source": "EIA",
                        "Link": eia_url,
                        "Reference": "Interactive plant data page — verify any number here",
                    })
                st.dataframe(
                    pd.DataFrame(source_data),
                    column_config={"Link": st.column_config.LinkColumn("Direct Link", display_text="View on source")},
                    hide_index=True, use_container_width=True,
                )

            # Plant Profile
            st.markdown("## Plant Profile")
            c1, c2, c3 = st.columns(3)

            def card(container, label, value, source="", source_url=None):
                if value is None or (isinstance(value, float) and np.isnan(value)):
                    value = "—"
                source_html = source
                if source_url:
                    source_html = f'<a href="{source_url}" target="_blank" style="color:#4A5D23;text-decoration:underline;">{source}</a>'
                container.markdown(
                    f'<div class="info-card"><div class="info-label">{label}</div>'
                    f'<div class="info-value">{value}</div>'
                    f'<div class="info-source">{source_html}</div></div>',
                    unsafe_allow_html=True
                )

            eia_860_url = "https://www.eia.gov/electricity/data/eia860/"
            eia_923_url = "https://www.eia.gov/electricity/data/eia923/"
            epm_url = "https://www.eia.gov/electricity/monthly/"
            uswtdb_url = "https://eerscmap.usgs.gov/uswtdb/"
            egrid_url = "https://www.epa.gov/egrid"

            with c1:
                card(c1, "Plant Name", plant.get("plant_name"), "EIA Form 860", eia_860_url)
                card(c1, "State", plant.get("state"), "EIA Form 860", eia_860_url)
                nerc_code = plant.get("nerc_region")
                nerc_full = NERC_FULL_NAMES.get(nerc_code, nerc_code) if pd.notna(nerc_code) else "—"
                card(c1, "NERC Region", nerc_full, "EPA eGRID", egrid_url)
                card(c1, "Owner", plant.get("owner_display"), "EIA Form 860", eia_860_url)
                if eia_url:
                    st.markdown(
                        f'<a href="{eia_url}" target="_blank" style="display:inline-block;background:#1A1A1A;color:#FFF;'
                        f'padding:8px 16px;border-radius:4px;text-decoration:none;font-size:12px;font-weight:600;'
                        f'letter-spacing:0.5px;text-transform:uppercase;margin-top:8px;">'
                        f'View on EIA Plant Browser →</a>',
                        unsafe_allow_html=True)

            with c2:
                card(c2, "Nameplate Capacity (MW)", fmt_num(plant.get(CAP_COL)), "EIA Form 860", eia_860_url)
                card(c2, "Commissioning Year", fmt_int(plant.get("commissioning_year")), "EIA Form 860", eia_860_url)
                card(c2, "Plant Age (Years)", fmt_int(plant.get("asset_age")), "Derived from EIA-860", eia_860_url)
                tc = plant.get("turbine_count")
                if pd.notna(tc):
                    card(c2, "Turbine Count", fmt_int(tc), "U.S. Wind Turbine Database", uswtdb_url)
                else:
                    card(c2, "Turbine Count", "No USWTDB match for this plant", "")
                card(c2, "Turbine Manufacturer", plant.get("turbine_manufacturer", "—"), "USWTDB", uswtdb_url)

            with c3:
                # Raw data first, then derived
                card(c3, "Actual Generation 2024 (MWh)", fmt_num(plant.get("gen_mwh_2024")), "EIA Form 923", eia_923_url)
                card(c3, "Potential Generation 2024 (MWh)", fmt_num(plant.get("potential_gen_mwh_2024")), "Capacity × 8,760 hrs", eia_860_url)
                card(c3, "Capacity Factor 2024", fmt_pct(plant.get("cf_2024")), "Formula: Actual ÷ Potential", eia_url)

                # PTC status badge
                ptc = plant.get("ptc_status", "Unknown")
                if ptc == "Expired":
                    badge_class = "badge-black"
                elif ptc == "Expiring":
                    badge_class = "badge-gray"
                elif ptc == "Active":
                    badge_class = "badge-olive"
                else:
                    badge_class = "badge-gray"
                ptc_source_html = f'<a href="{eia_860_url}" target="_blank" style="color:#4A5D23;text-decoration:underline;">EIA-860 commissioning year</a>'
                st.markdown(f'<div class="info-card"><div class="info-label">Production Tax Credit Status</div>'
                            f'<div style="margin-top:4px;"><span class="{badge_class}">{ptc}</span></div>'
                            f'<div class="info-source">{ptc_source_html}</div></div>',
                            unsafe_allow_html=True)

            st.markdown("---")
            st.markdown(
                '<div style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:4px;padding:12px;margin:8px 0;">'
                '<span style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;color:#6B7280;">'
                'How to verify these numbers</span>'
                '<p style="font-size:12px;color:#1A1A1A;margin-top:4px;">'
                'Every data point comes from a U.S. federal government database. Click any source link to go directly to the dataset. '
                'The <strong>EIA Plant Browser</strong> shows this plant\'s generation, capacity, and owner data in one view. '
                'Capacity Factor = Actual Generation (MWh) &divide; [Nameplate Capacity (MW) &times; 8,760 hours].</p>'
                '</div>', unsafe_allow_html=True
            )

            # Performance vs. Peers
            st.markdown("---")
            st.markdown("## Performance vs. Peers")

            region = plant.get("nerc_region")
            if region and pd.notna(region) and "cf_2024" in df.columns:
                region_plants = df[df["nerc_region"] == region].copy()
                region_cf = region_plants["cf_2024"].dropna()
                plant_cf = plant.get("cf_2024")

                bp_col, tbl_col = st.columns([1, 1])

                with bp_col:
                    if not region_cf.empty:
                        region_name = NERC_FULL_NAMES.get(region, region)
                        # Scatter: all plants in region (age vs CF)
                        region_scatter = region_plants[["asset_age", "cf_2024", "plant_name"]].dropna()
                        fig = go.Figure()
                        # All peers as gray dots
                        fig.add_trace(go.Scatter(
                            x=region_scatter["asset_age"],
                            y=region_scatter["cf_2024"],
                            mode="markers",
                            name=f"{region_name} Plants",
                            marker=dict(color="#D1D5DB", size=7, opacity=0.6,
                                        line=dict(color="#9CA3AF", width=0.5)),
                            text=region_scatter["plant_name"],
                            hovertemplate="%{text}<br>Age: %{x} yrs<br>CF: %{y:.1f}%<extra></extra>",
                        ))
                        # Selected plant as olive diamond
                        plant_age = plant.get("asset_age")
                        if pd.notna(plant_cf) and pd.notna(plant_age):
                            fig.add_trace(go.Scatter(
                                x=[plant_age], y=[plant_cf],
                                mode="markers", name=selected_plant,
                                marker=dict(color=OLIVE, size=16, symbol="diamond",
                                            line=dict(color="#1A1A1A", width=1.5)),
                                hovertemplate=f"{selected_plant}<br>Age: %{{x}} yrs<br>CF: %{{y:.1f}}%<extra></extra>",
                            ))
                        # Regional median dotted line
                        median_cf = region_cf.median()
                        if pd.notna(median_cf):
                            fig.add_hline(y=median_cf, line_dash="dot", line_color="#4A5D23",
                                          line_width=1.5,
                                          annotation_text=f"Region Median: {median_cf:.1f}%",
                                          annotation_position="top right",
                                          annotation_font_size=10, annotation_font_color="#4A5D23")
                        # Regression line
                        if len(region_scatter) > 5:
                            x_vals = region_scatter["asset_age"].values
                            y_vals = region_scatter["cf_2024"].values
                            mask = ~(np.isnan(x_vals) | np.isnan(y_vals))
                            if mask.sum() > 5:
                                z = np.polyfit(x_vals[mask], y_vals[mask], 1)
                                p = np.poly1d(z)
                                x_line = np.linspace(x_vals[mask].min(), x_vals[mask].max(), 50)
                                fig.add_trace(go.Scatter(
                                    x=x_line, y=p(x_line),
                                    mode="lines", name="Age Trend",
                                    line=dict(color="#6B7280", width=1.5, dash="dash"),
                                    hoverinfo="skip",
                                ))
                        fig.update_layout(
                            **PLOTLY_LAYOUT, height=400,
                            title=f"Age vs. Capacity Factor — {region_name}",
                            xaxis=dict(title="Plant Age (Years)", **AXIS_STYLE),
                            yaxis=dict(title="Capacity Factor (%)", **AXIS_STYLE),
                            showlegend=True,
                        )
                        st.plotly_chart(fig, use_container_width=True)

                with tbl_col:
                    region_3yr = region_plants["cf_3yr_2022_2024"].dropna()
                    region_gen = region_plants["gen_per_mw_2024"].dropna() if "gen_per_mw_2024" in region_plants.columns else pd.Series(dtype=float)
                    region_yoy = region_plants["yoy_3yr_avg"].dropna() if "yoy_3yr_avg" in region_plants.columns else pd.Series(dtype=float)

                    peer_data = [
                        {"Metric": "Capacity Factor 2024",
                         "This Plant": fmt_pct(plant_cf),
                         "Region Median": fmt_pct(region_cf.median()),
                         "Region Top 25%": fmt_pct(region_cf.quantile(0.75)),
                         "Formula": "Actual MWh / (Capacity MW x 8,760 hrs)"},
                        {"Metric": "Capacity Factor (3-Year Average)",
                         "This Plant": fmt_pct(plant.get("cf_3yr_2022_2024")),
                         "Region Median": fmt_pct(region_3yr.median()) if not region_3yr.empty else "—",
                         "Region Top 25%": fmt_pct(region_3yr.quantile(0.75)) if not region_3yr.empty else "—",
                         "Formula": "mean(CF 2022, CF 2023, CF 2024)"},
                        {"Metric": "Annual Generation per MW (MWh/MW)",
                         "This Plant": fmt_num(plant.get("gen_per_mw_2024")),
                         "Region Median": fmt_num(region_gen.median()) if not region_gen.empty else "—",
                         "Region Top 25%": fmt_num(region_gen.quantile(0.75)) if not region_gen.empty else "—",
                         "Formula": "Total MWh / Nameplate MW"},
                        {"Metric": "Production Trend (3-Year Average)",
                         "This Plant": f"{plant.get('yoy_3yr_avg', np.nan):+.1f}%" if pd.notna(plant.get("yoy_3yr_avg")) else "—",
                         "Region Median": f"{region_yoy.median():+.1f}%" if not region_yoy.empty else "—",
                         "Region Top 25%": f"{region_yoy.quantile(0.75):+.1f}%" if not region_yoy.empty else "—",
                         "Formula": "mean(YoY change 2022, 2023, 2024)"},
                    ]
                    st.dataframe(pd.DataFrame(peer_data), hide_index=True, use_container_width=True)

                    pctile = plant.get("cf_regional_percentile")
                    if pd.notna(pctile):
                        st.markdown(f"This plant is at the **{int(pctile)}th percentile** among "
                                    f"{len(region_cf)} plants in the {NERC_FULL_NAMES.get(region, region)} region.")
            else:
                st.info("Regional comparison data not available for this plant.")

            # Generation History
            st.markdown("---")
            st.markdown("## Generation History")

            gen_years = list(range(2018, 2026))
            gen_data = []
            for y in gen_years:
                gen_per_mw = plant.get(f"gen_per_mw_{y}")
                if pd.notna(gen_per_mw):
                    gen_data.append({
                        "Year": y,
                        "Generation per MW (MWh/MW)": float(gen_per_mw),
                        "label": f"{y}" + (" (EPM)" if y == 2025 else ""),
                    })

            if gen_data:
                gdf = pd.DataFrame(gen_data)

                reg_medians = {}
                if region and pd.notna(region):
                    for y in gen_years:
                        col = f"gen_per_mw_{y}"
                        if col in df.columns:
                            rmed = df.loc[df["nerc_region"] == region, col].dropna().median()
                            if pd.notna(rmed):
                                reg_medians[y] = rmed

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=gdf["label"], y=gdf["Generation per MW (MWh/MW)"],
                    marker_color=["#4A5D23" if r["Year"] != 2025 else "#B8C9A3" for _, r in gdf.iterrows()],
                    name="This Plant",
                    hovertemplate="Year: %{x}<br>Generation per MW: %{y:,.0f} MWh/MW<extra></extra>",
                ))

                if reg_medians:
                    rm_df = pd.DataFrame({"Year": list(reg_medians.keys()), "Median": list(reg_medians.values())})
                    rm_df["label"] = rm_df["Year"].apply(lambda y: f"{y}" + (" (EPM)" if y == 2025 else ""))
                    fig.add_trace(go.Scatter(
                        x=rm_df["label"], y=rm_df["Median"],
                        mode="lines+markers",
                        name=f"{NERC_FULL_NAMES.get(region, region)} Regional Median",
                        line=dict(color="#9CA3AF", width=2, dash="dash"),
                        marker=dict(size=5, color="#9CA3AF"),
                    ))

                # National median dotted line
                if "cf_2024" in df.columns:
                    nat_med = df["gen_per_mw_2024"].dropna().median()
                    if pd.notna(nat_med):
                        fig.add_hline(y=nat_med, line_dash="dot", line_color="#9CA3AF",
                                      line_width=1, annotation_text=f"National Median: {nat_med:,.0f}",
                                      annotation_position="top right",
                                      annotation_font_size=9, annotation_font_color="#9CA3AF")

                fig.update_layout(
                    **PLOTLY_LAYOUT, height=380,
                    yaxis=dict(title="Generation per MW (MWh/MW)", **AXIS_STYLE),
                    xaxis=AXIS_STYLE,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                cy = plant.get("commissioning_year")
                if pd.notna(cy) and int(cy) >= 2024:
                    st.info(f"This plant was commissioned in {int(cy)} — insufficient generation history for trend analysis.")
                else:
                    st.info("No generation history available for this plant in the EIA-923 dataset.")

            # Monthly Generation (EIA-style)
            if "gen_mwh_2025_01" in df.columns:
                monthly_data = []
                month_names = ["January", "February", "March", "April", "May", "June",
                               "July", "August", "September", "October", "November", "December"]
                for m in range(1, 13):
                    col = f"gen_mwh_2025_{m:02d}"
                    val = plant.get(col)
                    if pd.notna(val):
                        monthly_data.append({"Month": month_names[m-1], "Generation (MWh)": float(val)})

                if monthly_data:
                    st.markdown("### Monthly Generation — 2025 (EIA Electric Power Monthly)")
                    mdf = pd.DataFrame(monthly_data)
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=mdf["Month"], y=mdf["Generation (MWh)"],
                        marker_color="#4A5D23",
                        hovertemplate="%{x}: %{y:,.0f} MWh<extra></extra>",
                    ))
                    fig.update_layout(**PLOTLY_LAYOUT, height=300,
                                      yaxis=dict(title="Generation (MWh)", **AXIS_STYLE),
                                      xaxis=AXIS_STYLE, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)

                    mdf_display = mdf.copy()
                    mdf_display["Generation (MWh)"] = mdf_display["Generation (MWh)"].apply(
                        lambda v: f"{v:,.0f}" if pd.notna(v) else "")
                    st.dataframe(mdf_display, hide_index=True, use_container_width=True)

            # Month-over-Month: 2025 vs Same Month 2024
            if "gen_mwh_2025_01" in df.columns and "gen_mwh_2024_01" in df.columns:
                mom_data = []
                month_names = ["January", "February", "March", "April", "May", "June",
                               "July", "August", "September", "October", "November", "December"]
                for m in range(1, 13):
                    col_25 = f"gen_mwh_2025_{m:02d}"
                    col_24 = f"gen_mwh_2024_{m:02d}"
                    val_25 = plant.get(col_25)
                    val_24 = plant.get(col_24)
                    if pd.notna(val_25) and pd.notna(val_24):
                        change = ((val_25 - val_24) / val_24 * 100) if val_24 > 0 else None
                        mom_data.append({
                            "Month": month_names[m-1],
                            "2024 Generation (MWh)": val_24,
                            "2025 Generation (MWh)": val_25,
                            "Change vs. Prior Year": change,
                        })

                if mom_data:
                    st.markdown("### Month-over-Month: 2025 vs 2024")
                    st.markdown("_Each month's generation compared to the same month in the prior year._")
                    mom_df = pd.DataFrame(mom_data)

                    # Chart: side-by-side bars
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=mom_df["Month"], y=mom_df["2024 Generation (MWh)"],
                        name="2024", marker_color="#B8C9A3",
                        hovertemplate="%{x} 2024: %{y:,.0f} MWh<extra></extra>",
                    ))
                    fig.add_trace(go.Bar(
                        x=mom_df["Month"], y=mom_df["2025 Generation (MWh)"],
                        name="2025", marker_color="#4A5D23",
                        hovertemplate="%{x} 2025: %{y:,.0f} MWh<extra></extra>",
                    ))
                    fig.update_layout(
                        **PLOTLY_LAYOUT, height=350, barmode="group",
                        yaxis=dict(title="Generation (MWh)", **AXIS_STYLE),
                        xaxis=AXIS_STYLE, showlegend=True,
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # Table
                    mom_display = mom_df.copy()
                    mom_display["2024 Generation (MWh)"] = mom_display["2024 Generation (MWh)"].apply(
                        lambda v: f"{v:,.0f}" if pd.notna(v) else "")
                    mom_display["2025 Generation (MWh)"] = mom_display["2025 Generation (MWh)"].apply(
                        lambda v: f"{v:,.0f}" if pd.notna(v) else "")
                    mom_display["Change vs. Prior Year"] = mom_display["Change vs. Prior Year"].apply(
                        lambda v: f"{v:+.1f}%" if pd.notna(v) else "")
                    st.dataframe(mom_display, hide_index=True, use_container_width=True)

            # Distress Signals
            st.markdown("---")
            st.markdown("## Distress Signals")

            signal_count = plant.get("distress_signal_count", 0)
            if pd.isna(signal_count): signal_count = 0
            st.markdown(f"**{int(signal_count)} of 10** distress signals triggered for this plant.")

            signal_rows = []
            for sig in DISTRESS_SIGNALS:
                col = sig["code"]
                val = plant.get(col, False)
                status = bool(val) if pd.notna(val) else False

                calc_detail = sig["desc"]
                if col == "flag_declining_3yr" and status:
                    yoy = plant.get("yoy_3yr_avg")
                    if pd.notna(yoy):
                        calc_detail = f"3-year rolling average change: {yoy:+.1f}% (threshold: < -2.0%)"
                elif col == "flag_below_peak" and status:
                    dpeak = plant.get("decline_from_peak_pct")
                    pk_yr = plant.get("peak_year")
                    if pd.notna(dpeak) and pd.notna(pk_yr):
                        calc_detail = f"Current generation per MW is {dpeak:.1f}% vs. peak year {int(pk_yr)} (threshold: -15%)"
                elif col == "flag_consecutive_decline" and status:
                    yrs = plant.get("consecutive_decline_years")
                    if pd.notna(yrs):
                        calc_detail = f"{int(yrs)} consecutive years of declining generation per MW (threshold: >= 3)"
                elif col == "flag_ptc_expired" and status:
                    age = plant.get("asset_age")
                    cy = plant.get("commissioning_year")
                    if pd.notna(age) and pd.notna(cy):
                        calc_detail = f"Commissioned {int(cy)}, age = {int(age)} years. Production Tax Credit provides 10 years of credits."
                elif col == "flag_repower_candidate" and status:
                    ta = plant.get("turbine_age")
                    aa = plant.get("asset_age")
                    if pd.notna(ta) and pd.notna(aa):
                        calc_detail = f"Turbine age = {int(ta)} years (>= 15) AND plant age = {int(aa)} years (>= 10)"

                signal_rows.append({
                    "Signal": sig["label"],
                    "Status": "YES" if status else "—",
                    "How It's Calculated": calc_detail,
                    "Why It Matters": sig["why"],
                    "Data Source": sig["source"],
                })

            st.dataframe(pd.DataFrame(signal_rows), hide_index=True, use_container_width=True,
                         column_config={
                             "Status": st.column_config.TextColumn("Status", width="small"),
                             "Signal": st.column_config.TextColumn("Signal", width="medium"),
                         })


# ========================= TAB 3: Market Overview ===========================
with tab3:
    if filtered.empty or "nerc_region" not in filtered.columns:
        st.info("No data available for market overview.")
    else:
        st.markdown("## Regional Performance")

        agg_dict = {"plant_name": "count"}
        if CAP_COL in filtered.columns:
            agg_dict[CAP_COL] = "sum"
        if "cf_3yr_2022_2024" in filtered.columns:
            agg_dict["cf_3yr_2022_2024"] = "median"

        regional = filtered.groupby("nerc_region", dropna=False).agg(agg_dict).reset_index()
        col_names = ["NERC Region Code", "Plants"]
        if CAP_COL in agg_dict:
            col_names.append("Total Capacity (MW)")
        if "cf_3yr_2022_2024" in agg_dict:
            col_names.append("Median Capacity Factor (3-Year)")
        regional.columns = col_names

        # Add full region name
        regional.insert(1, "Region Name",
                        regional["NERC Region Code"].map(NERC_FULL_NAMES).fillna(regional["NERC Region Code"]))

        for flag_col, flag_label in [("flag_declining_3yr", "% Declining"),
                                      ("flag_ptc_expired", "% Tax Credit Expired")]:
            if flag_col in filtered.columns:
                pct = (filtered.groupby("nerc_region", dropna=False)[flag_col]
                       .apply(lambda s: s.fillna(False).astype(bool).mean() * 100).reset_index())
                pct.columns = ["NERC Region Code", flag_label]
                regional = regional.merge(pct, on="NERC Region Code", how="left")

        regional = regional.sort_values("Median Capacity Factor (3-Year)" if "Median Capacity Factor (3-Year)" in regional.columns else "Plants")

        # Pre-format numbers with commas and percentages
        if "Total Capacity (MW)" in regional.columns:
            regional["Total Capacity (MW)"] = regional["Total Capacity (MW)"].apply(
                lambda v: f"{v:,.0f}" if pd.notna(v) else "")
        if "Median Capacity Factor (3-Year)" in regional.columns:
            regional["Median Capacity Factor (3-Year)"] = regional["Median Capacity Factor (3-Year)"].apply(
                lambda v: f"{v:.1f}%" if pd.notna(v) else "")
        for pct_col in ["% Declining", "% Tax Credit Expired"]:
            if pct_col in regional.columns:
                regional[pct_col] = regional[pct_col].apply(
                    lambda v: f"{v:.1f}%" if pd.notna(v) else "")

        st.dataframe(regional, hide_index=True, use_container_width=True)

        ch1, ch2 = st.columns(2)

        with ch1:
            if "cf_3yr_2022_2024" in filtered.columns:
                plot_df = filtered.dropna(subset=["nerc_region", "cf_3yr_2022_2024"]).copy()
                plot_df["Capacity Factor (%)"] = plot_df["cf_3yr_2022_2024"]
                plot_df["Region"] = plot_df["nerc_region"].map(NERC_FULL_NAMES).fillna(plot_df["nerc_region"])
                if not plot_df.empty:
                    region_order = plot_df.groupby("Region")["Capacity Factor (%)"].median().sort_values().index.tolist()
                    fig = go.Figure()
                    for reg in region_order:
                        reg_data = plot_df[plot_df["Region"] == reg]["Capacity Factor (%)"]
                        fig.add_trace(go.Box(
                            y=reg_data, name=reg,
                            marker_color="#4A5D23", line_color="#2D3A14",
                            fillcolor="#F0F4E8",
                        ))
                    fig.update_layout(
                        **PLOTLY_LAYOUT, height=420,
                        title="Capacity Factor Distribution by Region",
                        yaxis=dict(title="Capacity Factor (3-Year Average, %)", **AXIS_STYLE),
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True)

        with ch2:
            if "asset_age" in filtered.columns:
                age_data = filtered["asset_age"].dropna()
                if not age_data.empty:
                    fig = px.histogram(
                        age_data, nbins=25,
                        color_discrete_sequence=["#4A5D23"],
                        labels={"value": "Plant Age (Years)", "count": "Number of Plants"},
                    )
                    fig.update_layout(
                        **PLOTLY_LAYOUT, height=420,
                        title="Plant Age Distribution",
                        showlegend=False,
                        xaxis=dict(title="Plant Age (Years)", **AXIS_STYLE),
                        yaxis=dict(title="Number of Plants", **AXIS_STYLE),
                    )
                    st.plotly_chart(fig, use_container_width=True)


# ========================= TAB 4: Trends ===================================
with tab4:
    if filtered.empty:
        st.info("No plants match the current filters.")
    else:
        st.markdown(
            '<div class="info-card">'
            '<div class="info-label">Data Coverage</div>'
            '<div class="info-value">EIA-860/923 Annual: 2018-2024&ensp;·&ensp;'
            'Electric Power Monthly: 2025 (all 12 months)</div>'
            '<div class="info-source">Source: U.S. Energy Information Administration</div>'
            '</div>', unsafe_allow_html=True
        )
        st.markdown("")

        show_2025 = st.toggle("Include 2025 Electric Power Monthly data (preliminary)", value=True, key="show_2025")
        year_range = list(range(2018, 2026 if show_2025 else 2025))

        ch1, ch2 = st.columns(2)

        with ch1:
            st.markdown("### Median Capacity Factor by Year")
            cf_by_year = {}
            for y in year_range:
                c = f"cf_{y}"
                if c in filtered.columns:
                    med = filtered[c].dropna().median()
                    if pd.notna(med):
                        cf_by_year[y] = med
            if cf_by_year:
                cdf = pd.DataFrame({"Year": list(cf_by_year.keys()),
                                    "Median Capacity Factor (%)": list(cf_by_year.values())})
                fig = px.line(cdf, x="Year", y="Median Capacity Factor (%)", markers=True,
                              color_discrete_sequence=["#4A5D23"])
                fig.update_layout(**PLOTLY_LAYOUT, height=340)
                fig.update_xaxes(dtick=1, **AXIS_STYLE)
                fig.update_yaxes(**AXIS_STYLE)
                st.plotly_chart(fig, use_container_width=True)

        with ch2:
            st.markdown("### Percentage of Plants Declining Year-over-Year")
            decline_pct = {}
            for y in year_range:
                c = f"yoy_pct_{y}"
                if c in filtered.columns:
                    valid = filtered[c].dropna()
                    if len(valid) > 0:
                        decline_pct[y] = (valid < 0).mean() * 100
            if decline_pct:
                ddf = pd.DataFrame({"Year": list(decline_pct.keys()),
                                    "Plants Declining (%)": list(decline_pct.values())})
                fig = px.line(ddf, x="Year", y="Plants Declining (%)", markers=True,
                              color_discrete_sequence=["#4A5D23"])
                fig.update_layout(**PLOTLY_LAYOUT, height=340)
                fig.update_xaxes(dtick=1, **AXIS_STYLE)
                fig.update_yaxes(**AXIS_STYLE)
                st.plotly_chart(fig, use_container_width=True)

        if "cf_3yr_2022_2024" in filtered.columns:
            st.markdown("### Capacity Factor Distribution (3-Year Average, 2022-2024)")
            cf_hist = filtered["cf_3yr_2022_2024"].dropna()
            if not cf_hist.empty:
                fig = px.histogram(cf_hist, nbins=40, color_discrete_sequence=["#4A5D23"],
                                   labels={"value": "Capacity Factor (%)", "count": "Number of Plants"})
                fig.update_layout(**PLOTLY_LAYOUT, height=300, showlegend=False,
                                  xaxis=dict(title="Capacity Factor (%)", **AXIS_STYLE),
                                  yaxis=dict(title="Number of Plants", **AXIS_STYLE))
                st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Global Footer
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="footer-provenance">'
    '<strong>Data Provenance:</strong> All data sourced from U.S. Energy Information Administration (EIA), '
    'U.S. Geological Survey (USGS), and U.S. Environmental Protection Agency (EPA). '
    'No AI-generated, estimated, or predicted values. Calculations use published formulas only.'
    '</div>', unsafe_allow_html=True
)
