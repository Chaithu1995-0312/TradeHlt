"""Check what data is available via yfinance."""
import pandas as pd
import yfinance as yf

tests = {
    "AUDUSD": "6A=F",
    "GBPUSD": "6B=F", 
    "USDJPY": "6J=F",
    "XAUUSD": "GC=F",
}

for name, ticker in tests.items():
    print(f"\n=== {name} ({ticker}) ===")
    
    # 15m data (last ~60 days)
    df = yf.download(ticker, period="2mo", interval="15m", progress=False)
    if not df.empty:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        print(f"  15m: {len(df)} rows, {df.index[0]} -> {df.index[-1]}, vol_sum={df['Volume'].sum()}")
    else:
        print(f"  15m: empty")

    # 1h data (full year possible)
    df = yf.download(ticker, start="2025-05-22", end="2026-05-22", interval="1h", progress=False)
    if not df.empty:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        print(f"  1h:  {len(df)} rows, {df.index[0]} -> {df.index[-1]}, vol_sum={df['Volume'].sum()}")
    else:
        print(f"  1h:  empty")

# Also test EURCAD derivation sources
print("\n=== EURCAD sources ===")
for ticker in ["6E=F", "6C=F"]:
    df = yf.download(ticker, period="2mo", interval="15m", progress=False)
    if not df.empty:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        print(f"  {ticker} 15m: {len(df)} rows, vol_sum={df['Volume'].sum()}")