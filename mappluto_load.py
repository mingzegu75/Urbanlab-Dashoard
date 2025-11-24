# -*- coding: utf-8 -*-
"""
Created on Mon Nov 24 15:10:33 2025

@author: Admin
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text

# 1. 你的 Neon 数据库连接 (直接填在这里)
# 注意：这里是你的 neondb 连接信息
DB_URL = "postgresql+psycopg2://neondb_owner:npg_Vmx9iqzZeAX4@ep-icy-bush-a4rz6rd1-pooler.us-east-1.aws.neon.tech/neondb"

# 2. CSV 文件路径 (你的桌面路径)
# Windows 用户通常是 C:\Users\你的用户名\Desktop\mappluto_lite.csv
# 为了方便，请手动把下面这行改成你真实的 CSV 路径：
csv_path = r"C:\Users\Admin\Desktop\mappluto.csv" 
# 注意：如果你的用户名不是 Admin，请修改上面的路径！

def upload_mappluto():
    print("正在连接 Neon 数据库...")
    engine = create_engine(DB_URL)
    
    print(f"正在读取 CSV 文件: {csv_path} ...")
    # 读取 CSV (注意：根据你的导出设置，可能不需要 header=0，如果有表头就保持默认)
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print("❌ 错误：找不到文件！请检查 csv_path 路径是否正确。")
        return

    print(f"读取成功！共 {len(df)} 行。准备上传...")

    # 3. 创建表结构 (为了保险，再次重置表结构)
    with engine.begin() as conn:
        print("重置表结构...")
        conn.execute(text("DROP TABLE IF EXISTS mappluto CASCADE;"))
        conn.execute(text("""
            CREATE TABLE mappluto (
                bbl bigint,
                borough text,
                address text,
                zipcode text,
                geom geometry
            );
        """))
    
    # 4. 分批上传 (Chunk Upload) - 防止内存溢出或超时
    chunk_size = 5000  # 每次传 5000 行
    total_rows = len(df)
    
    print("开始分批写入数据库 (请耐心等待，会打印进度)...")
    
    try:
        df.to_sql(
            'mappluto', 
            engine, 
            if_exists='append', 
            index=False, 
            method='multi', # 这是一个加速参数
            chunksize=chunk_size 
        )
        print("🎉 恭喜！mappluto 上传成功！")
    except Exception as e:
        print(f"❌ 上传失败: {e}")

if __name__ == "__main__":
    upload_mappluto()