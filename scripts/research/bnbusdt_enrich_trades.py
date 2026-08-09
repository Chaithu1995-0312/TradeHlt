"""
bnbusdt_enrich_trades.py — Stage 2: Enrich trades CSV with MFE/MAE/return horizons.

Reads the fresh production backtest CSV + M15 candle history.
Computes per-trade:
  - MFE (max favorable excursion)
  - MAE (max adverse excursion)
  - time_to_peak (candles to best price)
  - time_to_bottom (candles to worst price)
  - return_15m, 30m, 45m, 60m, 90m (returns at each horizon)

Outputs enriched dataset as CSV + JSONL + Parquet.
Uses zero lookahead: only candles up to trade close.
"""

import csv
import json
import os
import sys
from datetime import datetime
from collections import OrderedDict

# --- Config ---
TRADES_CSV = r"results/research/bnbusdt_authoritative/run_20260613_025416_BNBUSDT/BNBUSDT_trades.csv"
CANDLES_CSV = r"data/BNBUSDT_M15.csv"
OUTPUT_CSV = r"results/research/bnbusdt_trade_dataset.csv"
OUTPUT_JSONL = r"results/research/bnbusdt_trade_dataset.jsonl"
OUTPUT_PARQUET = r"results/research/bnbusdt_trade_dataset.parquet"

# --- Load candle history ---
print("Loading candle history...")
candle_rows = []  # list of dicts with all columns
with open(CANDLES_CSV, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        candle_rows.append(row)

print(f"Loaded {len(candle_rows)} candles")

# Build a timestamp-indexed lookup for fast forward-scanning
# Each candle: { 'timestamp': ..., 'high': ..., 'low': ..., 'close': ... }
candle_by_idx = {}
for i, row in enumerate(candle_rows):
    candle_by_idx[i] = {
        'ts': row.get('timestamp', row.get('date', '')),
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row.get('volume', 0)),
    }

# --- Load trades ---
print("Loading trades...")
trades = []
with open(TRADES_CSV, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        trades.append(row)

print(f"Loaded {len(trades)} trades")

# --- Enrich each trade ---
enriched = []
M15_MINUTES = 15

for trade in trades:
    entry_idx = int(trade['candle_idx'])
    exit_idx = int(trade['candle_idx']) + int(trade['duration_candles'])
    direction = trade['direction']
    entry_price = float(trade['entry_raw'])
    exit_price = float(trade['exit_price_raw'] if trade.get('exit_price_raw') else trade['exit_fill'])

    # --- MFE / MAE ---
    # Scan from entry_candle+1 to exit_candle (inclusive)
    # Zero lookahead: we only look at candles up to trade close
    best_price = entry_price
    worst_price = entry_price
    time_to_peak = 0  # candles from entry to best price
    time_to_bottom = 0  # candles from entry to worst price

    for offset in range(0, int(trade['duration_candles']) + 1):
        idx = entry_idx + offset
        if idx >= len(candle_rows):
            break
        c = candle_by_idx[idx]
        if direction == 'LONG':
            # Favorable = higher price
            if c['high'] > best_price:
                best_price = c['high']
                time_to_peak = offset
            # Adverse = lower price
            if c['low'] < worst_price:
                worst_price = c['low']
                time_to_bottom = offset
        else:  # SHORT
            # Favorable = lower price
            if c['low'] < best_price:
                best_price = c['low']
                time_to_peak = offset
            # Adverse = higher price
            if c['high'] > worst_price:
                worst_price = c['high']
                time_to_bottom = offset

    mfe = abs(best_price - entry_price)
    mae = abs(worst_price - entry_price)

    # --- Return at horizons ---
    # Compute returns at 15m, 30m, 45m, 60m, 90m from entry
    horizons = {15: None, 30: None, 45: None, 60: None, 90: None}
    for horizon_mins, label in [(15, '15m'), (30, '30m'), (45, '45m'), (60, '60m'), (90, '90m')]:
        horizon_candles = horizon_mins // M15_MINUTES
        target_idx = entry_idx + horizon_candles
        if target_idx < len(candle_rows):
            target_close = candle_by_idx[target_idx]['close']
            pnl_pct = ((target_close - entry_price) / entry_price * 100) if direction == 'LONG' \
                      else ((entry_price - target_close) / entry_price * 100)
            horizons[label] = round(pnl_pct, 4)
        else:
            horizons[label] = None

    # --- Build enriched row ---
    row = OrderedDict()
    row['trade_id'] = trade['trade_id']
    row['instrument'] = trade['instrument']
    row['direction'] = trade['direction']
    row['entry_price'] = float(trade['entry_raw'])
    row['exit_price'] = float(trade['exit_fill'])
    row['entry_fill'] = float(trade['entry_fill'])
    row['sl_price'] = float(trade['sl'])
    row['tp1_price'] = float(trade['tp1'])
    row['tp2_price'] = float(trade['tp2'])
    row['exit_reason'] = trade['exit_reason']
    row['opened_at'] = trade['opened_at']
    row['closed_at'] = trade['closed_at']
    row['duration_candles'] = int(trade['duration_candles'])
    row['pnl_rr_net'] = float(trade['pnl_rr_net'])
    row['pnl_pips_net'] = float(trade['pnl_pips_net'])
    row['session'] = float(trade['session'])
    row['day_of_week'] = int(trade['day_of_week'])
    row['hour_of_day'] = float(trade['hour_of_day'])
    row['candle_idx'] = int(trade['candle_idx'])
    row['htf_id'] = trade['htf_id']
    row['capital_before'] = float(trade['capital_before'])
    row['capital_after'] = float(trade['capital_after'])
    row['position_size'] = float(trade['position_size'])
    row['shadow_used'] = int(trade.get('shadow_used', 0))
    row['bitnet_score_at_entry'] = float(trade.get('bitnet_score_at_entry', 0))
    row['bitnet_decision_at_entry'] = trade.get('bitnet_decision_at_entry', '')

    # Feature vector (subset — key clustering features)
    row['open'] = float(trade.get('open', 0))
    row['high'] = float(trade.get('high', 0))
    row['low'] = float(trade.get('low', 0))
    row['close'] = float(trade.get('close', 0))
    row['volume'] = float(trade.get('volume', 0))
    row['volume_ratio'] = float(trade.get('volume_ratio', 0))
    row['ema_fast'] = float(trade.get('ema_fast', 0))
    row['ema_slow'] = float(trade.get('ema_slow', 0))
    row['ema_spread'] = float(trade.get('ema_spread', 0))
    row['trend_bias'] = float(trade.get('trend_bias', 0))
    row['trend_strength'] = float(trade.get('trend_strength', 0))
    row['momentum_score'] = float(trade.get('momentum_score', 0))
    row['atr'] = float(trade.get('atr', 0))
    row['volatility_ratio'] = float(trade.get('volatility_ratio', 0))
    row['rsi_14'] = float(trade.get('rsi_14', 0))
    row['body_size'] = float(trade.get('body_size', 0))
    row['wick_size'] = float(trade.get('wick_size', 0))
    row['body_ratio'] = float(trade.get('body_ratio', 0))
    row['volatility_regime'] = float(trade.get('volatility_regime', 0))
    row['disp_strength'] = float(trade.get('disp_strength', 0))
    row['retest_depth'] = float(trade.get('retest_depth', 0))
    row['candles_since_retest'] = float(trade.get('candles_since_retest', 0))
    row['liquidity_distance'] = float(trade.get('liquidity_distance', 0))
    row['liquidity_pressure_score'] = float(trade.get('liquidity_pressure_score', 0))
    row['double_sweep'] = float(trade.get('double_sweep', 0))
    row['live_atr'] = float(trade.get('live_atr', 0))

    # Derived metrics
    row['mfe'] = round(mfe, 6)
    row['mae'] = round(mae, 6)
    row['time_to_peak'] = time_to_peak
    row['time_to_bottom'] = time_to_bottom
    row['return_15m'] = horizons['15m'] if horizons['15m'] is not None else ''
    row['return_30m'] = horizons['30m'] if horizons['30m'] is not None else ''
    row['return_45m'] = horizons['45m'] if horizons['45m'] is not None else ''
    row['return_60m'] = horizons['60m'] if horizons['60m'] is not None else ''
    row['return_90m'] = horizons['90m'] if horizons['90m'] is not None else ''

    # Outcome label
    row['outcome'] = 1 if float(trade['pnl_rr_net']) > 0 else 0

    enriched.append(row)

# --- Write CSV ---
print(f"Writing enriched CSV: {OUTPUT_CSV}")
fieldnames = list(enriched[0].keys())
with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(enriched)

# --- Write JSONL ---
print(f"Writing enriched JSONL: {OUTPUT_JSONL}")
with open(OUTPUT_JSONL, 'w', encoding='utf-8') as f:
    for row in enriched:
        # Convert OrderedDict to plain dict, handle empty strings
        clean = {}
        for k, v in row.items():
            if v == '' or v is None:
                clean[k] = None
            else:
                clean[k] = v
        f.write(json.dumps(clean) + '\n')

# --- Write Parquet (if pandas+pyarrow available) ---
try:
    import pandas as pd
    df = pd.DataFrame(enriched)
    df.to_parquet(OUTPUT_PARQUET, index=False)
    print(f"Written Parquet: {OUTPUT_PARQUET}")
except ImportError:
    print("Parquet writer not available (install pandas+pyarrow). Skipping.")
    OUTPUT_PARQUET = "(not created)"

print(f"\nDone. Enriched {len(enriched)} trades.")
print(f"  CSV: {OUTPUT_CSV}")
print(f"  JSONL: {OUTPUT_JSONL}")
print(f"  Parquet: {OUTPUT_PARQUET}")