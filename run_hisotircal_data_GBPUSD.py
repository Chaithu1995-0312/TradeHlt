import pandas as pd
import glob
import os

# Resolve absolute path
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "data", "DAT_ASCII_GBPUSD_M1_*.csv")

files = glob.glob(DATA_PATH)

print("FILES FOUND:", files)

if not files:
    raise ValueError("❌ No M1 files found. Check path.")

dfs = []

for f in files:
    print("Loading:", f)

    df = pd.read_csv(f, sep=";", header=None,
        names=["timestamp","open","high","low","close","volume"])

    # FIXED timestamp parsing
    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        format="%Y%m%d %H%M%S"
    )

    dfs.append(df)

# Combine all years
df = pd.concat(dfs, ignore_index=True).sort_values("timestamp")

# Resample to M15
df = df.set_index("timestamp").resample("15T").agg({
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum"
}).dropna().reset_index()

# Save output
output_path = os.path.join(BASE_DIR, "data", "GBPUSD_M15.csv")
df.to_csv(output_path, index=False)

print(f"✅ Generated: {output_path}")