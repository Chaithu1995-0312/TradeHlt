"""Check full data availability for all instruments."""
import pandas as pd
import yfinance as yf

# Check existing files
print("=== EXISTING CSV FILES ===")
for inst in ['AUDUSD_M15', 'EURCAD_M15', 'GBPUSD_M15', 'USDJPY_M15', 'XAUUSD_M15']:
    try:
        df = pd.read_csv(f'data/{inst}.csv')
        dt0 = df['timestamp'].iloc[0][:10]
        dt1 = df['timestamp'].iloc[-1][:10]
        print(f"  {inst}: {len(df)} rows, {dt0} -> {dt1}, vol_sum={df['volume'].sum()}")
    except Exception as e:
        print(f"  {inst}: {e}")

print("\n=== YAHOO FULL YEAR (1h) WITH REAL VOLUME ===")
tests = {
    "AUDUSD": "6A=F",
    "GBPUSD": "6B=F",
    "USDJPY": "6J=F", 
    "XAUUSD": "GC=F",
    "EURUSD": "6E=F",
    "CADUSD": "6C=F",
}
for name, ticker in tests.items():
    df = yf.download(ticker, start="2025-05-22", end="2026-05-22", interval="1h", progress=False)
    if not df.empty:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        print(f"  {name} ({ticker}): {len(df)} rows, vol_sum={df['Volume'].sum():.0f}")
    else:
        print(f"  {name} ({ticker}): EMPTY")