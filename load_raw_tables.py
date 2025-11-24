# -*- coding: utf-8 -*-
"""
Created on Thu Nov 13 04:00:15 2025

@author: Admin
"""
# load_raw_tables.py
# Only task: download 6 Socrata datasets and load them into nyc_rent_map

import os
import io
import requests
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv  # <--- 新增这行

# 加载 .env 文件中的变量
load_dotenv()  # <--- 新增这行

# -----------------------------
# DB config (Modified to use .env)
# -----------------------------
# 使用 os.getenv 读取，如果读取不到(例如在云端没配置好)，可以给个默认值或者报错
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD") # 密码不给默认值，强制要求配置
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "nyc_rent_map")

# 检查密码是否存在，为了安全和排错
if not DB_PASSWORD:
    raise ValueError("DB_PASSWORD not found in environment variables!")

SOCRATA_APP_TOKEN = os.getenv("SOCRATA_APP_TOKEN", "")

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


def socrata_csv_url(base: str, limit: int = 500000) -> str:
    """Build a Socrata CSV URL with optional app token."""
    url = f"{base}?$limit={limit}"
    if SOCRATA_APP_TOKEN:
        url += f"&$$app_token={SOCRATA_APP_TOKEN}"
    return url


# 6 datasets you showed in the screenshot
DATASETS = {
    "hpd_affordable_building_raw": socrata_csv_url(
        "https://data.cityofnewyork.us/resource/hg8x-zxpr.csv", 500000
    ),
    "hpd_affordable_project_raw": socrata_csv_url(
        "https://data.cityofnewyork.us/resource/hq68-rnsi.csv", 500000
    ),
    "nycha_developments_raw": socrata_csv_url(
        "https://data.cityofnewyork.us/resource/phvi-damg.csv", 500000
    ),
    "ll44_rent_affordability_raw": socrata_csv_url(
        "https://data.cityofnewyork.us/resource/93d2-wh7s.csv", 500000
    ),
    "ll44_unit_income_rent_raw": socrata_csv_url(
        "https://data.cityofnewyork.us/resource/9ay9-xkek.csv", 1000000
    ),
    "mta_subway_stations_raw": socrata_csv_url(
        "https://data.ny.gov/resource/39hk-dx4f.csv", 50000
    ),
}


def load_one_dataset(table_name: str, url: str) -> None:
    """Download CSV with pandas, create a TEXT table, bulk load via COPY."""
    print(f"=== loading {table_name} ===")
    df = pd.read_csv(url)
    print(f"{table_name}: downloaded {len(df)} rows, {len(df.columns)} columns")

    cols = list(df.columns)
    cols_sql = ", ".join([f'"{c}" TEXT' for c in cols])

    # create empty table
    print(f"{table_name}: creating empty table via CREATE TABLE ...")
    with engine.begin() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS {table_name};'))
        conn.execute(text(f'CREATE TABLE {table_name} ({cols_sql});'))

    # bulk load via COPY
    print(f"{table_name}: bulk load via COPY ...")
    csv_buf = io.StringIO()
    df.to_csv(csv_buf, index=False)
    csv_buf.seek(0)

    raw_conn = engine.raw_connection()
    try:
        with raw_conn.cursor() as cur:
            cur.copy_expert(
                f'COPY {table_name} FROM STDIN WITH (FORMAT CSV, HEADER TRUE)',
                csv_buf,
            )
        raw_conn.commit()
    finally:
        raw_conn.close()

    print(f"{table_name}: finished loading\n")


def main():
    for tbl, url in DATASETS.items():
        load_one_dataset(tbl, url)


if __name__ == "__main__":
    main()

