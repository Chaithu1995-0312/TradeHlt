"""
Convert fetched M15 CSVs with real volume to Excel (.xlsx) files.

Reads from data/yfinance/ and writes to data/ as {INSTRUMENT}_M15_1year.xlsx
"""
import pandas as pd
from pathlib import Path

SRC = Path("data/yfinance")
DST = Path("data")
DST.mkdir(exist_ok=True)

for csv_path in sorted(SRC.glob("*_M15.csv")):
    instr = csv_path.stem.replace("_M15", "")
    df = pd.read_csv(csv_path)
    vol_ok = df["volume"].sum() > 0
    
    xlsx_path = DST / f"{instr}_M15_1year.xlsx"
    df.to_excel(xlsx_path, index=False, sheet_name="M15")
    
    print(f"{instr}:")
    print(f"  Rows: {len(df)}")
    print(f"  Range: {df['timestamp'].iloc[0]} -> {df['timestamp'].iloc[-1]}")
    print(f"  Volume sum: {df['volume'].sum():,}")
    print(f"  Non-zero volume: {vol_ok}")
    print(f"  Output: {xlsx_path}")
    print()