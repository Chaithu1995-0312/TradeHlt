"""Test what period ranges work for 15m data."""
import pandas as pd
import yfinance as yf

for ticker in ['6A=F', '6B=F', '6J=F', 'GC=F', '6E=F', '6C=F']:
    for period in ['1d', '5d', '1mo', '2mo']:
        df = yf.download(ticker, period=period, interval='15m', progress=False)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]
            vol = df['Volume'].sum()
            print(f"{ticker} period={period}: {len(df)} rows, vol={vol:.0f}")
        else:
            print(f"{ticker} period={period}: empty")