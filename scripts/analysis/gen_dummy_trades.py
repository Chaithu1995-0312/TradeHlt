"""
gen_dummy_trades.py
Generate a dummy trade CSV from OHLCV data that includes all 32 canonical features.
Usage: python gen_dummy_trades.py <ohlcv.csv> [output_dir]
"""

import pandas as pd
from features.feature_pipeline import FeaturePipeline
from features.feature_schema import CANONICAL_FEATURES

def main(ohlcv_path, output_dir="results/dummy"):
    df = pd.read_csv(ohlcv_path)
    pipeline = FeaturePipeline(df)
    enriched, _ = pipeline.run()
    
    # Simple rule: long at close, exit at next close
    enriched['rr'] = enriched['close'].pct_change().shift(-1) * 100
    enriched['win'] = (enriched['rr'] > 0).astype(int)
    enriched['pnl_rr_net'] = enriched['rr']
    enriched['entry_time'] = enriched['timestamp']
    
    # Select all canonical features + label columns
    columns_to_write = list(CANONICAL_FEATURES) + ['entry_time', 'pnl_rr_net', 'win']
    trades = enriched[columns_to_write].dropna()
    
    import os
    os.makedirs(output_dir, exist_ok=True)
    out_path = f"{output_dir}/dummy_trades.csv"
    trades.to_csv(out_path, index=False)
    print(f"Wrote {len(trades)} dummy trades (with 32 features) to {out_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python gen_dummy_trades.py <ohlcv.csv> [output_dir]")
        sys.exit(1)
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "results/dummy"
    main(sys.argv[1], output_dir)