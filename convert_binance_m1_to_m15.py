import pandas as pd
import glob
import os

BASE_DIR = os.path.dirname(__file__)
files = glob.glob(os.path.join(BASE_DIR, "data", "BTCUSDT-1m-*.csv"))

print("FILES FOUND:", files)

dfs = []

for f in files:
    df = pd.read_csv(f)

    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")

    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
    dfs.append(df)

df = pd.concat(dfs).sort_values("timestamp")

df = df.set_index("timestamp").resample("15min").agg({
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum"
}).dropna().reset_index()

output = os.path.join(BASE_DIR, "data", "BTCUSDT_M15.csv")
df.to_csv(output, index=False)

print("✅ Generated:", output)