# -*- coding: utf-8 -*-
"""
Created on Thu Nov 13 22:22:05 2025

@author: Admin
"""

"""
acs_rent5_nyc.py

Download ACS 5-year median gross rent by bedrooms (table B25031)
for NYC census tracts (state 36, counties 005,047,061,081,085)
for years 2013-2023, and store in Postgres table acs_rent5_nyc.
"""
import os
import requests
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
load_dotenv()

# ======= DB CONFIGURATION (Modified) =======

CENSUS_API_KEY = os.getenv("CENSUS_API_KEY")
if not CENSUS_API_KEY:
    raise RuntimeError("CENSUS_API_KEY env var is not set")

# 删除原来写死的 DB_USER = "postgres" 等行，改成：
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "nyc_rent_map")

if not DB_PASSWORD:
    raise ValueError("DB_PASSWORD not found! Make sure it's in your .env file.")

# ============================================

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# 只拉 2013-2023，避免早期没有这个表导致 400
YEARS = list(range(2013, 2024))

# B25031 列
ACS_VARS = [
    "NAME",
    "B25031_001E",
    "B25031_002E",
    "B25031_003E",
    "B25031_004E",
    "B25031_005E",
    "B25031_006E",
    "B25031_007E",
]

# NYC 五个 county
NYC_COUNTIES = ["005", "047", "061", "081", "085"]


def fetch_one_year(year: int) -> pd.DataFrame:
    base_url = f"https://api.census.gov/data/{year}/acs/acs5"
    get_vars = ",".join(ACS_VARS)
    results = []

    for county in NYC_COUNTIES:
        params = {
            "get": get_vars,
            "for": "tract:*",
            "in": f"state:36 county:{county}",
            "key": CENSUS_API_KEY,
        }
        resp = requests.get(base_url, params=params, timeout=60)
        resp.raise_for_status()  # 如果这一年/表不存在，会在这里抛 HTTPError

        data = resp.json()
        cols = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=cols)
        df["year"] = year
        results.append(df)

    out = pd.concat(results, ignore_index=True)

    # 重命名列
    out = out.rename(
        columns={
            "B25031_001E": "median_rent_all",
            "B25031_002E": "median_rent_0br",
            "B25031_003E": "median_rent_1br",
            "B25031_004E": "median_rent_2br",
            "B25031_005E": "median_rent_3br",
            "B25031_006E": "median_rent_4br",
            "B25031_007E": "median_rent_5plus",
        }
    )

    # 拼 tract_geoid（和 mappluto ct2010 对齐）
    out["state"] = out["state"].astype(str).str.zfill(2)
    out["county"] = out["county"].astype(str).str.zfill(3)
    out["tract"] = out["tract"].astype(str).str.zfill(6)
    out["tract_geoid"] = out["state"] + out["county"] + out["tract"]

    # 转成数值
    rent_cols = [
        "median_rent_all",
        "median_rent_0br",
        "median_rent_1br",
        "median_rent_2br",
        "median_rent_3br",
        "median_rent_4br",
        "median_rent_5plus",
    ]
    for c in rent_cols:
        out[c] = pd.to_numeric(out[c], errors="coerce")

    return out[
        [
            "year",
            "tract_geoid",
            "state",
            "county",
            "tract",
            "NAME",
            "median_rent_all",
            "median_rent_0br",
            "median_rent_1br",
            "median_rent_2br",
            "median_rent_3br",
            "median_rent_4br",
            "median_rent_5plus",
        ]
    ]


def main():
    all_years = []

    for y in YEARS:
        print(f"Fetching ACS {y} ...")
        try:
            df = fetch_one_year(y)
        except requests.HTTPError as e:
            # 某些年份如果表不存在，就跳过
            print(f"  Skipping {y} due to HTTP error: {e}")
            continue
        all_years.append(df)

    if not all_years:
        raise RuntimeError("No ACS data fetched; check YEARS or API key")

    full = pd.concat(all_years, ignore_index=True)
    print(f"Total rows fetched: {len(full)}")

    # 写入 Postgres，替换旧表
    full.to_sql(
        "acs_rent5_nyc",
        engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=1000,
    )

    print("acs_rent5_nyc written to Postgres")


if __name__ == "__main__":
    main()
