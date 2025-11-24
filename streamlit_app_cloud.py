# -*- coding: utf-8 -*-
"""
Created on Thu Nov 13 03:48:41 2025

@author: Admin
"""
# streamlit_app.py
# NYC Affordable Housing Dashboard 5.1 (English Version)
# Features: Text Input Rent Filter, Zip Code Analytics, Price by Unit Type

import os
import pandas as pd
import streamlit as st
import pydeck as pdk
import altair as alt
import re
from sqlalchemy import create_engine, text

# -----------------------------------------------------------------------------
# 1. App Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    layout="wide", 
    page_title="NYC Housing | Affordable Explorer",
    page_icon="🏙️"
)

# -----------------------------------------------------------------------------
# 2. Database Configuration (Modified to use st.secrets)
# -----------------------------------------------------------------------------
# 这里的代码现在会去读取 Streamlit Cloud 后台配置的 Secrets
# 如果您在本地运行，需要在项目根目录下创建 .streamlit/secrets.toml 文件
try:
    DB_USER = st.secrets["DB_USER"]
    DB_PASSWORD = st.secrets["DB_PASSWORD"]
    DB_HOST = st.secrets["DB_HOST"]
    DB_PORT = st.secrets["DB_PORT"]
    DB_NAME = st.secrets["DB_NAME"]
except Exception as e:
    st.error("❌ 数据库连接配置缺失。请在 Streamlit Cloud 的 Advanced Settings -> Secrets 中配置数据库信息。")
    st.error(f"详细错误: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. Helper Functions (Updated to parse Rent)
# -----------------------------------------------------------------------------
def parse_bedroom_data(df):
    """
    Parses 'bedroom_rent_summary' to extract unit counts AND rent by type.
    Example string: "0br | units: 5 | rent: 1000; 1br | units: 10 | rent: 1500"
    """
    parsed_rows = []
    for _, row in df.iterrows():
        summary = row.get('bedroom_rent_summary', '')
        if not summary or pd.isna(summary):
            continue
            
        parts = summary.split(';')
        for part in parts:
            # Regex to extract type, count, AND optional rent
            # Pattern looks for: "TYPE | units: NUM" and optionally "| rent: NUM"
            match = re.search(r'([a-zA-Z0-9-]+)\s*\|\s*units:\s*(\d+)(?:\s*\|\s*rent:\s*(\d+))?', part)
            if match:
                unit_type = match.group(1).upper() # e.g., "1BR"
                count = int(match.group(2))
                rent_str = match.group(3)
                rent_val = int(rent_str) if rent_str else None
                
                parsed_rows.append({
                    'Borough': row['borough'],
                    'Unit Type': unit_type,
                    'Count': count,
                    'Est Rent': rent_val
                })
    
    if not parsed_rows:
        return pd.DataFrame(columns=['Borough', 'Unit Type', 'Count', 'Est Rent'])
        
    return pd.DataFrame(parsed_rows)

# -----------------------------------------------------------------------------
# 4. Data Loading
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner="Querying database...")
def load_filtered_data(boroughs, min_rent, max_rent, min_units, target_zipcode=None) -> pd.DataFrame:
    try:
        engine = create_engine(
            f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
        
        sql = """
            WITH transformed AS (
                SELECT
                    *,
                    ST_Transform(ST_SetSRID(ST_Centroid(geom), 2263), 4326) AS geom_wgs84
                FROM building_map_fact
            )
            SELECT
                building_id,
                borough,
                address,
                zipcode,
                ST_X(geom_wgs84) AS lon,
                ST_Y(geom_wgs84) AS lat,
                min_effective_median_rent,
                total_ll44_units,
                bedroom_rent_summary
            FROM transformed
            WHERE
                min_effective_median_rent BETWEEN :min_rent AND :max_rent
                AND total_ll44_units >= :min_units
                AND min_effective_median_rent > 0 
        """
        
        params = {
            "min_rent": min_rent,
            "max_rent": max_rent,
            "min_units": min_units
        }

        if boroughs:
            sql += " AND borough = ANY(:boroughs)"
            params["boroughs"] = list(boroughs)
        
        if target_zipcode and target_zipcode.strip():
            sql += " AND zipcode = :zipcode"
            params["zipcode"] = target_zipcode.strip()

        sql += ";"

        with engine.connect() as conn:
            df = pd.read_sql(text(sql), conn, params=params)

        df['address'] = df['address'].fillna('Unknown Address')
        df['bedroom_rent_summary'] = df['bedroom_rent_summary'].fillna('No details available')
        
        df = df.dropna(subset=["lon", "lat"])
        return df
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return pd.DataFrame()

# -----------------------------------------------------------------------------
# 5. Sidebar UI
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("🏙️ Housing Filters")
    st.markdown("---")
    
    # A. Income Calculator
    st.subheader("💰 Affordability Calculator")
    col_income, col_ratio = st.columns([2, 1])
    with col_income:
        monthly_income = st.number_input(
            "Monthly Income ($)", 
            min_value=0, max_value=100_000, value=6000, step=100
        )
    with col_ratio:
        rent_ratio_pct = st.number_input(
            "Burden(%)", 
            min_value=10, max_value=60, value=30, step=5,
            help="Recommended: < 30%"
        )

    calculated_max_rent = 0
    if monthly_income > 0:
        calculated_max_rent = monthly_income * (rent_ratio_pct / 100.0)
        st.success(f"Max Budget: **${calculated_max_rent:,.0f}**")
    else:
        st.warning("Enter income to start")

    st.markdown("---")

    # B. Specific Rent Filter (UPDATED: Number Input)
    st.subheader("🏷️ Specific Rent Range")
    st.caption("Manually set your price limits.")
    
    col_min_rent, col_max_rent = st.columns(2)
    
    with col_min_rent:
        min_rent_input = st.number_input(
            "Min Rent ($)", 
            min_value=0, 
            value=0, 
            step=100
        )
        
    with col_max_rent:
        # Default max is calculated budget or 5000
        default_max_val = int(calculated_max_rent) if calculated_max_rent > 0 else 5000
        max_rent_input = st.number_input(
            "Max Rent ($)", 
            min_value=0, 
            value=default_max_val, 
            step=100
        )
    
    st.markdown("---")

    # C. Location & Size
    st.subheader("📍 Location & Size")
    all_boros = ["BK", "BX", "MN", "QN", "SI"]
    selected_boros = st.multiselect("Boroughs", options=all_boros, default=all_boros)
    target_zip = st.text_input("Specific Zip Code (Optional)", placeholder="e.g., 10001")
    min_bldg_units = st.slider("Min Building Size (Units)", 0, 200, 0, step=10)

    st.markdown("---")
    
    # D. Display Settings
    st.subheader("⚙️ Display Settings")
    max_points = st.slider("Max Map Points", 1000, 50000, 10000)
    map_style_toggle = st.radio("Map Style", ["Light", "Dark"], horizontal=True)
    map_layer_type = st.radio("Map Mode", ["Scatter", "Heatmap"], horizontal=True)

# -----------------------------------------------------------------------------
# 6. Data Fetching
# -----------------------------------------------------------------------------
if monthly_income > 0 or max_rent_input > 0:
    df_filtered = load_filtered_data(
        boroughs=selected_boros,
        min_rent=min_rent_input,
        max_rent=max_rent_input,
        min_units=min_bldg_units,
        target_zipcode=target_zip
    )
    
    if not df_filtered.empty:
        if calculated_max_rent > 0:
            df_filtered["monthly_saving"] = calculated_max_rent - df_filtered["min_effective_median_rent"]
        else:
            df_filtered["monthly_saving"] = 0
else:
    df_filtered = pd.DataFrame()

# -----------------------------------------------------------------------------
# 7. Main Dashboard Area
# -----------------------------------------------------------------------------
st.title("NYC Affordable Housing Explorer")

if df_filtered.empty:
    st.info("👈 Please adjust filters in the sidebar to find buildings.")
    st.write(f"Current Rent Filter: ${min_rent_input} - ${max_rent_input}")
else:
    st.markdown(f"""
        Found **{len(df_filtered):,}** buildings with rent between **\${min_rent_input}** and **\${max_rent_input}**.
    """)

    # --- Top KPI Cards ---
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("🏠 Buildings", f"{len(df_filtered):,}")
    with kpi2:
        st.metric("🛏️ Total Units", f"{int(df_filtered['total_ll44_units'].sum()):,}")
    with kpi3:
        avg_rent = df_filtered['min_effective_median_rent'].mean()
        st.metric("💲 Avg Rent (Filtered)", f"${avg_rent:,.0f}")
    with kpi4:
        if calculated_max_rent > 0:
            max_saving = df_filtered['monthly_saving'].max()
            st.metric("💰 Max Potential Savings", f"${max_saving:,.0f}")
        else:
            st.metric("💰 Income Needed", "Enter Income")

    st.markdown("---")

    # --- Tabs ---
    tab_map, tab_analytics, tab_data = st.tabs(["🗺️ Map Explorer", "📈 Market Insights", "📋 Details"])

    # Downsample for map if needed
    if len(df_filtered) > max_points:
        df_plot = df_filtered.sample(n=max_points, random_state=42)
    else:
        df_plot = df_filtered

    # --- Tab 1: Map ---
    with tab_map:
        view_state = pdk.ViewState(
            latitude=df_plot["lat"].mean(),
            longitude=df_plot["lon"].mean(),
            zoom=10.5,
            pitch=0, 
        )

        layers = []
        tooltip = None

        if map_layer_type == "Scatter":
            scatter_layer = pdk.Layer(
                "ScatterplotLayer",
                data=df_plot,
                get_position="[lon, lat]",
                get_radius=30,
                get_fill_color=[255, 140, 0, 180],
                get_line_color=[255, 255, 255],
                pickable=True,
                auto_highlight=True,
            )
            layers.append(scatter_layer)
            
            tooltip = {
                "html": """
                <div style="color: white; font-family: sans-serif; width: 250px;">
                    <h4 style="margin: 0; padding-bottom: 5px; border-bottom: 1px solid #555;">{address}</h4>
                    <div style="margin-top: 5px;">
                        <strong>Borough:</strong> {borough}<br/>
                        <strong>Est. Rent:</strong> ${min_effective_median_rent}<br/>
                        <strong>Units:</strong> {total_ll44_units}
                    </div>
                    <div style="margin-top: 10px; font-size: 0.8em; color: #ccc; white-space: pre-wrap;">
                        {bedroom_rent_summary}
                    </div>
                </div>
                """,
                "style": {
                    "backgroundColor": "#1f2937",
                    "borderRadius": "5px",
                    "padding": "10px",
                    "boxShadow": "0 2px 4px rgba(0,0,0,0.3)"
                }
            }
        else:
            # Heatmap
            heatmap_layer = pdk.Layer(
                "HeatmapLayer",
                data=df_plot,
                get_position="[lon, lat]",
                opacity=0.9,
                get_weight="total_ll44_units",
                radius_pixels=50,
            )
            layers.append(heatmap_layer)

        map_style = "mapbox://styles/mapbox/dark-v10" if map_style_toggle == "Dark" else "mapbox://styles/mapbox/light-v9"

        st.pydeck_chart(pdk.Deck(
            map_style=map_style,
            initial_view_state=view_state,
            layers=layers,
            tooltip=tooltip,
        ), use_container_width=True)

    # --- Tab 2: Analytics (Enhanced) ---
    with tab_analytics:
        # Parse unit data for advanced charts
        unit_df = parse_bedroom_data(df_filtered)

        col_a, col_b = st.columns(2)
        
        # 1. Unit Type Counts
        with col_a:
            st.subheader("🛏️ Availability by Unit Type")
            st.caption("Which apartment sizes are most common?")
            if not unit_df.empty:
                unit_counts = unit_df.groupby('Unit Type')['Count'].sum().reset_index()
                chart_units = alt.Chart(unit_counts).mark_bar().encode(
                    x=alt.X('Unit Type', sort='-y'),
                    y='Count',
                    color=alt.value("#9b59b6"),
                    tooltip=['Unit Type', 'Count']
                ).properties(height=300)
                st.altair_chart(chart_units, use_container_width=True)
            else:
                st.write("No detailed unit data.")

        # 2. Average Rent by Unit Type (NEW!)
        with col_b:
            st.subheader("🏷️ Avg Price by Unit Type")
            st.caption("Estimated market rent for different apartment sizes.")
            if not unit_df.empty and unit_df['Est Rent'].notna().any():
                # Filter out rows where rent is None or 0 for this chart
                valid_rent_df = unit_df[unit_df['Est Rent'] > 0]
                if not valid_rent_df.empty:
                    avg_rent_chart = alt.Chart(valid_rent_df).mark_bar().encode(
                        x=alt.X('Unit Type', sort='-y'),
                        y=alt.Y('mean(Est Rent)', title='Avg Rent ($)'),
                        color=alt.value("#e67e22"),
                        tooltip=['Unit Type', alt.Tooltip('mean(Est Rent)', format=",.0f")]
                    ).properties(height=300)
                    st.altair_chart(avg_rent_chart, use_container_width=True)
                else:
                    st.info("Rent details per unit type are not available in current selection.")
            else:
                st.write("No specific unit rent data available.")

        st.markdown("---")
        
        col_c, col_d = st.columns(2)

        # 3. Top Zip Codes (NEW!)
        with col_c:
            st.subheader("📍 Hotspot Zip Codes")
            st.caption("Top 10 Zip Codes with the most matching buildings.")
            zip_counts = df_filtered['zipcode'].value_counts().reset_index()
            zip_counts.columns = ['Zip Code', 'Count']
            chart_zip = alt.Chart(zip_counts.head(10)).mark_bar().encode(
                x=alt.X('Count', title='Buildings'),
                y=alt.Y('Zip Code', sort='-x'),
                color=alt.value("#34495e"),
                tooltip=['Zip Code', 'Count']
            ).properties(height=400)
            st.altair_chart(chart_zip, use_container_width=True)

        # 4. Savings Distribution
        with col_d:
            st.subheader("💸 Savings Potential")
            st.caption("How much under budget are these apartments?")
            if calculated_max_rent > 0:
                chart_hist_savings = alt.Chart(df_filtered).mark_bar().encode(
                    x=alt.X('monthly_saving', bin=alt.Bin(maxbins=20), title='Monthly Savings ($)'),
                    y=alt.Y('count()', title='Count'),
                    color=alt.value("#2ecc71"), 
                    tooltip=['count()']
                ).properties(height=400)
                st.altair_chart(chart_hist_savings, use_container_width=True)
            else:
                st.write("Enter income to see savings analysis.")

    # --- Tab 3: Data Table ---
    with tab_data:
        st.subheader("📋 Detailed Building List")
        
        csv = df_filtered.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Data as CSV",
            data=csv,
            file_name='nyc_housing_filtered.csv',
            mime='text/csv',
        )
        
        display_df = df_filtered[[
            "borough", "address", "zipcode", 
            "min_effective_median_rent", "monthly_saving",
            "total_ll44_units", "bedroom_rent_summary"
        ]].sort_values("min_effective_median_rent", ascending=True)
        
        st.dataframe(
            display_df,
            use_container_width=True,
            height=600
        )