"""Verify all output data/yfinance CSVs and data Excel files."""
import pandas as pd
from pathlib import Path

print("=== CSV files in data/yfinance/ ===")
for f in sorted(Path("data/yfinance").glob("*_M15.csv")):
    df = pd.read_csv(f)
    dt0 = df["timestamp"].iloc[0][:10]
    dt1 = df["timestamp"].iloc[-1][:10]
    print(f"  {f.stem}: {len(df):5d} rows, {dt0} -> {dt1}, vol={df['volume'].sum():>8,d}")

print("\n=== Excel files in data/ ===")
for f in sorted(Path("data").glob("*_M15_1year.xlsx")):
    df = pd.read_excel(f)
    dt0 = df["timestamp"].iloc[0][:10]
    dt1 = df["timestamp"].iloc[-1][:10]
    vol_ok = df["volume"].sum() > 0
    print(f"  {f.stem}: {len(df):5d} rows, {dt0} -> {dt1}, vol={df['volume'].sum():>8,d}, vol_ok={vol_ok}")