import pandas as pd
import glob
import os
import sys

# ===== INPUT =====
# Example: python run_historical_data.py EURCAD
if len(sys.argv) < 2:
    raise ValueError("❌ Provide instrument name. Example: EURCAD")

INSTRUMENT = sys.argv[1].upper()

# ===== PATH =====
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "data", f"DAT_ASCII_{INSTRUMENT}_M1_*.csv")

files = glob.glob(DATA_PATH)

print(f"\n🔍 Instrument: {INSTRUMENT}")
print("FILES FOUND:", files)

if not files:
    raise ValueError(f"❌ No M1 files found for {INSTRUMENT}")

dfs = []

for f in files:
    print("Loading:", f)

    df = pd.read_csv(
        f,
        sep=";",
        header=None,
        names=["timestamp", "open", "high", "low", "close", "volume"]
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        format="%Y%m%d %H%M%S"
    )

    dfs.append(df)

# ===== MERGE =====
df = pd.concat(dfs, ignore_index=True).sort_values("timestamp")

# ===== RESAMPLE =====
df = df.set_index("timestamp").resample("15min").agg({
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum"
}).dropna().reset_index()

# ===== SAVE =====
output_path = os.path.join(BASE_DIR, "data", f"{INSTRUMENT}_M15.csv")
df.to_csv(output_path, index=False)

print(f"\n✅ Generated: {output_path}")