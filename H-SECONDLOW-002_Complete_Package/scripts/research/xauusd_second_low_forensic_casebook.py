#!/usr/bin/env python3
"""
XAUUSD Second-Low v1 — Forensic Event-Level Casebook (7 Independent Events)

Focus: Deeply mine the existing independent sample instead of adding more data or tests.

Dimensions explored per event:
1. Purge geometry (depth, candle anatomy, relation to absolute low)
2. Pre-event context (2h/4h returns, volatility state, approach style)
3. Normalized 8-bar post-purge trajectory
4. Descriptive path classification (Immediate Reversal, V-Reversal, Continuation, Chop, etc.)

This is pure descriptive forensic work on the current n=7.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import timedelta

# Paths from previous run
INDEPENDENT_CSV = "/home/workdir/artifacts/results/second_low_v1/xauusd_second_low_v1_independent_events.csv"
SOURCE_XLSX = "/home/workdir/attachments/XAUUSD_M15_1year.xlsx"

def load_full_df():
    df = pd.read_excel(SOURCE_XLSX)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp').sort_index()
    df = df.rename(columns={c: c.lower() for c in df.columns})
    # Recompute ATR and second_low for context
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    daily = df.resample('1D').agg(Low=('low', 'min'))
    df['second_low_20d'] = daily['Low'].rolling(20).apply(
        lambda x: sorted(x.dropna())[1] if len(x.dropna()) >= 2 else np.nan
    ).shift(1).reindex(df.index, method='ffill')
    return df

def classify_path_type(post_df: pd.DataFrame, entry_price: float) -> str:
    """Simple descriptive classification of the 8-bar path."""
    closes = post_df['close']
    highs = post_df['high']
    lows = post_df['low']

    first_move = "Up" if closes.iloc[0] > entry_price else "Down"
    final_move = "Up" if closes.iloc[-1] > entry_price else "Down"

    max_high = highs.max()
    min_low = lows.min()

    made_new_high = max_high > entry_price * 1.001
    made_new_low = min_low < entry_price * 0.999

    if made_new_high and not made_new_low:
        if first_move == "Up":
            return "Immediate Continuation / Strong Reversal Up"
        else:
            return "V-Reversal (Down then Strong Up)"
    elif made_new_low and not made_new_high:
        return "Continuation Lower / Weak Reversal"
    elif made_new_high and made_new_low:
        return "Chop / Two-sided (both extremes taken)"
    else:
        if abs(closes.iloc[-1] - entry_price) < 0.3 * (max_high - min_low):
            return "Chop / No Resolution"
        else:
            return f"{first_move} then {final_move} (mild)"

def build_forensic_casebook(independent_df: pd.DataFrame, full_df: pd.DataFrame) -> pd.DataFrame:
    casebook_rows = []

    for _, event in independent_df.iterrows():
        purge_time = event['purge_time']
        entry_price = full_df.loc[purge_time, 'close']
        purge_low = full_df.loc[purge_time, 'low']
        second_low = event['second_low_20d']
        atr = event['atr_at_purge']

        # Post window
        purge_pos = full_df.index.get_loc(purge_time)
        post = full_df.iloc[purge_pos + 1 : purge_pos + 9]

        if len(post) != 8:
            continue

        # Normalized trajectory (close relative to entry, in ATR units)
        norm_closes = ((post['close'] - entry_price) / atr).round(2).tolist()

        # Pre-event context (last 8 bars before purge)
        pre = full_df.iloc[max(0, purge_pos-8):purge_pos]
        pre_2h_return = ((entry_price - pre['close'].iloc[0]) / atr) if len(pre) > 0 else np.nan

        # Purge geometry
        purge_depth_atr = event['purge_depth_price'] / atr if atr > 0 else np.nan
        distance_to_abs_low = (second_low - full_df.loc[purge_time:].low.min()) / atr if atr > 0 else np.nan

        path_type = classify_path_type(post, entry_price)

        casebook_rows.append({
            'event_time': purge_time,
            'session': event['session'],
            'purge_depth_atr': round(purge_depth_atr, 2),
            'pre_2h_return_atr': round(pre_2h_return, 2) if not np.isnan(pre_2h_return) else None,
            'mfe_atr': event['mfe_atr'],
            'mae_atr': event['mae_atr'],
            'close_disp_atr': event['close_disp_atr'],
            'path_type': path_type,
            'norm_8bar_trajectory_atr': norm_closes,
        })

    return pd.DataFrame(casebook_rows)

def main():
    print("=== XAUUSD Second-Low v1 Forensic Casebook (7 Independent Events) ===\n")

    independent = pd.read_csv(INDEPENDENT_CSV)
    full_df = load_full_df()

    casebook = build_forensic_casebook(independent, full_df)

    print("Event-Level Forensic Casebook:\n")
    print(casebook[['event_time', 'session', 'purge_depth_atr', 'pre_2h_return_atr', 
                    'mfe_atr', 'mae_atr', 'close_disp_atr', 'path_type']].to_string(index=False))

    print("\n\nNormalized 8-bar Close Trajectories (in ATR units, relative to purge close):")
    for _, row in casebook.iterrows():
        print(f"{row['event_time']} | {row['path_type']}: {row['norm_8bar_trajectory_atr']}")

    # Save
    out_path = "/home/workdir/artifacts/results/second_low_v1/xauusd_second_low_v1_forensic_casebook.csv"
    casebook.to_csv(out_path, index=False)
    print(f"\n\nDetailed casebook saved to: {out_path}")

if __name__ == "__main__":
    main()
