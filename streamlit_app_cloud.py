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
    Parses 'bedroom_rent_summary' column which looks like:
    'Studio | units: 10 | rent: 1200; 1-BR | units: 5 | rent: 1500'
    Returns a long-format DataFrame for visualization.
    """
    data_list = []
    
    for idx, row in df.iterrows():
        summary_str = row.get('bedroom_rent_summary', '')
        if not isinstance(summary_str, str) or not summary_str:
            continue
            
        # Split by ';' to get each bedroom type group
        items = summary_str.split(';')
        for item in items:
            # Example item: "1-BR | units: 5 | rent: 1500"
            # We use regex to extract the parts safely
            # Structure: [Name] | units: [Number] | rent: [Number or N/A]
            
            # Simple parsing strategy: split by '|'
            parts = item.split('|')
            if len(parts) >= 3:
                bd_name = parts[0].strip()
                
                # Extract units count
                units_part = parts[1].replace('units:', '').strip()
                try:
                    units_val = int(float(units_part)) # handle '5.0' or '5'
                except:
                    units_val = 0
                
                # Extract rent
                rent_part = parts[2].replace('rent:', '').strip()
                if rent_part.upper() == 'N/A' or not rent_part:
                    rent_val = None
                else:
                    try:
                        rent_val = float(rent_part)
                    except:
                        rent_val = None
                
                if units_val > 0:
                    data_list.append({
                        'building_id': idx, # use index as temp ID
                        'borough': row['borough'],
                        'address': row['address'],
                        'bedroom_type': bd_name,
                        'units': units_val,
                        'rent': rent_val
                    })
    
    return pd.DataFrame(data_list)

# -----------------------------------------------------------------------------
# 4. Data Loading
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    """
    Connect to PostgreSQL (Neon) and fetch the materialized view data.
    Added explicit parsing for lat/lon from PostGIS geometry.
    """
    # Create connection engine
    # Use standard psycopg2 connection string format
    db_url = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(db_url)
    
    # Query the materialized view
    # We use ST_Y (lat) and ST_X (lon) to get coordinates for Pydeck
    query = """
    SELECT 
        borough,
        address,
        zipcode,
        min_effective_median_rent,
        total_ll44_units,
        bedroom_rent_summary,
        ST_Y(ST_Centroid(geom)) as latitude,
        ST_X(ST_Centroid(geom)) as longitude
    FROM building_map_fact
    """
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
            
        # Data Cleaning
        # 1. Ensure numeric types
        df['min_effective_median_rent'] = pd.to_numeric(df['min_effective_median_rent'], errors='coerce')
        df['total_ll44_units'] = pd.to_numeric(df['total_ll44_units'], errors='coerce').fillna(0)
        df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
        df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
        
        # 2. Drop rows with missing coordinates (cannot map them)
        df = df.dropna(subset=['latitude', 'longitude'])
        
        return df

    except Exception as e:
        st.error(f"Error loading data from database: {e}")
        return pd.DataFrame() # return empty DF on error

# Load the data
df = load_data()

# -----------------------------------------------------------------------------
# 5. Sidebar Filters
# -----------------------------------------------------------------------------
st.sidebar.header("🔍 Filter Options")

if df.empty:
    st.warning("No data loaded. Please check database connection.")
    st.stop()

# --- Filter A: Borough ---
boroughs = sorted(df['borough'].astype(str).unique().tolist())
selected_boroughs = st.sidebar.multiselect(
    "Select Borough(s)",
    options=boroughs,
    default=boroughs
)

# --- Filter B: Rent Range (Text Inputs) ---
st.sidebar.subheader("💰 Monthly Budget")
col_min, col_max = st.sidebar.columns(2)

# Determine global min/max for defaults
global_min_rent = int(df['min_effective_median_rent'].min()) if not df['min_effective_median_rent'].isnull().all() else 0
global_max_rent = int(df['min_effective_median_rent'].max()) if not df['min_effective_median_rent'].isnull().all() else 5000

with col_min:
    input_min = st.number_input("Min Rent ($)", min_value=0, value=global_min_rent, step=100)
with col_max:
    input_max = st.number_input("Max Rent ($)", min_value=0, value=global_max_rent, step=100)

# --- Filter C: Search Address ---
st.sidebar.subheader("📍 Search Location")
address_search = st.sidebar.text_input("Search Address or Zipcode", "")

# --- Filter D: Income Calculator (Optional) ---
st.sidebar.markdown("---")
st.sidebar.subheader("🧮 Affordability Calculator")
annual_income = st.sidebar.number_input("Your Annual Household Income ($)", min_value=0, value=60000, step=1000)
# 30% rule: Monthly Rent <= (Annual Income / 12) * 0.3  => Annual Income / 40
calculated_max_rent = annual_income / 40 
st.sidebar.caption(f"Suggested Max Rent (30% Rule): **${calculated_max_rent:,.0f}**")


# -----------------------------------------------------------------------------
# 6. Apply Filters
# -----------------------------------------------------------------------------
mask = (
    (df['borough'].isin(selected_boroughs)) &
    (df['min_effective_median_rent'] >= input_min) &
    (df['min_effective_median_rent'] <= input_max)
)

if address_search:
    # Search in address OR zipcode columns
    mask &= (
        df['address'].astype(str).str.contains(address_search, case=False) | 
        df['zipcode'].astype(str).str.contains(address_search, case=False)
    )

df_filtered = df[mask].copy()

# Calculate savings if income is entered
if calculated_max_rent > 0:
    # How much money you save per month compared to your max budget
    # Saving = Your Max Budget - Actual Rent
    # If rent is higher than budget, saving is negative (cost).
    df_filtered['monthly_saving'] = calculated_max_rent - df_filtered['min_effective_median_rent']
else:
    df_filtered['monthly_saving'] = 0


# -----------------------------------------------------------------------------
# 7. Main Dashboard Layout
# -----------------------------------------------------------------------------
st.title("🏙️ NYC Affordable Housing Explorer")
st.markdown("""
Find affordable housing options in NYC based on **LL44** and **HPD** data.
Use the filters on the left to narrow down your search.
""")

# Top Key Metrics
m1, m2, m3 = st.columns(3)
m1.metric("Buildings Found", f"{len(df_filtered):,}")
m2.metric("Total Affordable Units", f"{int(df_filtered['total_ll44_units'].sum()):,}")
avg_rent_val = df_filtered['min_effective_median_rent'].mean()
m3.metric("Avg Minimum Rent", f"${avg_rent_val:,.0f}" if pd