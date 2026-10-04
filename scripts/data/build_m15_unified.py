# build_m15_unified.py

import pandas as pd
import glob
import os

# ─────────────────────────────────────────────
# CONFIG — ADD ALL INSTRUMENTS HERE
# ─────────────────────────────────────────────

INSTRUMENTS = [
    {
        "name": "EURUSD",
        "pattern": "data/DAT_ASCII_EURUSD_M1_*.csv",
        "type": "forex",
        "tz": "Etc/GMT-2"   # 🔥 adjust once after detection
    },
    {
        "name": "GBPUSD",
        "pattern": "data/DAT_ASCII_GBPUSD_M1_*.csv",
        "type": "forex",
        "tz": "Etc/GMT-2"
    },
    {
        "name": "USDJPY",
        "pattern": "data/DAT_ASCII_USDJPY_M1_*.csv",
        "type": "forex",
        "tz": "Etc/GMT-2"
    },
    {
        "name": "AUDUSD",
        "pattern": "data/DAT_ASCII_AUDUSD_M1_*.csv",
        "type": "forex",
        "tz": "Etc/GMT-2"
    },
    {
        "name": "XAUUSD",
        "pattern": "data/DAT_ASCII_XAUUSD_M1_*.csv",
        "type": "forex",
        "tz": "Etc/GMT-2"
    },
    {
        "name": "BTCUSDT",
        "pattern": "data/BTCUSDT-1m-*.csv",
        "type": "crypto",
        "tz": "UTC"
    },
    {
        "name": "ETHUSDT",
        "pattern": "data/ETHUSDT-1m-*.csv",
        "type": "crypto",
        "tz": "UTC"
    },
]

OUTPUT_DIR = "data"

# ─────────────────────────────────────────────
# CORE BUILDER
# ─────────────────────────────────────────────

def load_files(pattern, instrument_type):
    files = glob.glob(pattern)
    if not files:
        raise ValueError(f"❌ No files found for pattern: {pattern}")

    dfs = []

    for f in files:
        print(f"Loading: {f}")

        if instrument_type == "forex":
            df = pd.read_csv(
                f,
                sep=";",
                header=None,
                names=["timestamp","open","high","low","close","volume"]
            )

            df["timestamp"] = pd.to_datetime(
                df["timestamp"],
                format="%Y%m%d %H%M%S"
            )

        else:  # crypto
            df = pd.read_csv(f)

            # Binance format
            if "open_time" in df.columns:
                df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
            else:
                df["timestamp"] = pd.to_datetime(df.iloc[:,0])

            df = df.rename(columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume"
            })

        dfs.append(df[["timestamp","open","high","low","close","volume"]])

    df = pd.concat(dfs, ignore_index=True)
    df = df.sort_values("timestamp").drop_duplicates()

    return df


# ─────────────────────────────────────────────
# TIMEZONE NORMALIZATION
# ─────────────────────────────────────────────

def normalize_timezone(df, tz):
    print(f"→ Normalizing timezone: {tz}")

    df["timestamp"] = df["timestamp"].dt.tz_localize(tz)
    df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")

    return df


# ─────────────────────────────────────────────
# RESAMPLING
# ─────────────────────────────────────────────

def resample_m15(df):
    df = df.set_index("timestamp")

    df = df.resample("15T").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna()

    return df.reset_index()


# ─────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────

def validate(df, name):
    print(f"\nValidating {name}...")

    # 1. timezone check
    assert df["timestamp"].dt.tz is not None, "❌ Not timezone-aware"

    # 2. alignment check
    minutes = set(df["timestamp"].dt.minute.unique())
    assert minutes == {0, 15, 30, 45}, f"❌ Misaligned candles: {minutes}"

    # 3. monotonic time
    assert df["timestamp"].is_monotonic_increasing, "❌ Timestamp not sorted"

    # 4. duplicates
    assert not df["timestamp"].duplicated().any(), "❌ Duplicate timestamps"

    print("✅ Passed")


# ─────────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────────

def build_instrument(cfg):
    print(f"\n{'='*60}")
    print(f"Processing: {cfg['name']}")
    print(f"{'='*60}")

    df = load_files(cfg["pattern"], cfg["type"])
    df = normalize_timezone(df, cfg["tz"])
    df = resample_m15(df)

    validate(df, cfg["name"])

    out_path = os.path.join(OUTPUT_DIR, f"{cfg['name']}_M15.csv")
    df.to_csv(out_path, index=False)

    print(f"✅ Saved: {out_path}")


def main():
    for cfg in INSTRUMENTS:
        try:
            build_instrument(cfg)
        except Exception as e:
            print(f"❌ FAILED: {cfg['name']} → {e}")


if __name__ == "__main__":
    main()