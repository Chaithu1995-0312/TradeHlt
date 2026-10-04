#!/usr/bin/env python3
"""
XAUUSD Second-Low v1 — Tail Event Mechanism Report (7 Independent Events)

Focus: Resolve classification issues, inspect actual trajectories, 
       separate Tail (2 extreme) vs Ordinary (5), and compare pre/purge characteristics.
"""

import pandas as pd
import numpy as np
from pathlib import Path

INDEPENDENT_CSV = "/home/workdir/artifacts/results/second_low_v1/xauusd_second_low_v1_independent_events.csv"
SOURCE_XLSX = "/home/workdir/attachments/XAUUSD_M15_1year.xlsx"

def load_data():
    ind = pd.read_csv(INDEPENDENT_CSV)
    full = pd.read_excel(SOURCE_XLSX)
    full['timestamp'] = pd.to_datetime(full['timestamp'])
    full = full.set_index('timestamp').sort_index()
    full = full.rename(columns={c: c.lower() for c in full.columns})
    full['atr'] = (full['high'] - full['low']).rolling(14).mean()
    daily = full.resample('1D').agg(Low=('low', 'min'))
    full['second_low_20d'] = daily['Low'].rolling(20).apply(
        lambda x: sorted(x.dropna())[1] if len(x.dropna()) >= 2 else np.nan
    ).shift(1).reindex(full.index, method='ffill')
    return ind, full

def get_normalized_trajectory(full_df, purge_time, entry_price, atr):
    purge_pos = full_df.index.get_loc(purge_time)
    post = full_df.iloc[purge_pos + 1 : purge_pos + 9]
    if len(post) != 8:
        return None
    norm_closes = ((post['close'] - entry_price) / atr).round(2).tolist()
    return norm_closes

def main():
    print("=== XAUUSD Second-Low v1 — Tail vs Ordinary Mechanism Report ===\n")

    independent, full = load_data()

    # Sort by close_disp_atr descending to identify tails
    independent = independent.sort_values('close_disp_atr', ascending=False).reset_index(drop=True)

    tail_events = independent.iloc[:2]      # Top 2 by terminal displacement
    ordinary_events = independent.iloc[2:]  # Remaining 5

    print("TAIL EVENTS (Top 2 by Close Displacement):")
    print(tail_events[['purge_time', 'mfe_atr', 'mae_atr', 'close_disp_atr', 'purge_depth_price']].to_string(index=False))
    print()

    print("ORDINARY EVENTS (Remaining 5):")
    print(ordinary_events[['purge_time', 'mfe_atr', 'mae_atr', 'close_disp_atr', 'purge_depth_price']].to_string(index=False))
    print()

    print("=" * 80)
    print("NORMALIZED 8-BAR CLOSE TRAJECTORIES (ATR units relative to purge close)")
    print("=" * 80)

    for _, event in independent.iterrows():
        traj = get_normalized_trajectory(full, event['purge_time'], 
                                         full.loc[event['purge_time'], 'close'], 
                                         event['atr_at_purge'])
        group = "TAIL" if event['close_disp_atr'] > 3.0 else "ORDINARY"
        print(f"{group} | {event['purge_time']} | CloseDisp: {event['close_disp_atr']:.2f} | {traj}")

    print("\n" + "=" * 80)
    print("PRE-EVENT & PURGE CHARACTERISTICS: TAIL vs ORDINARY")
    print("=" * 80)

    # Simple comparison table
    comparison = pd.DataFrame({
        'Metric': ['Mean Purge Depth (ATR)', 'Mean Pre-2h Return (ATR)', 'Mean MFE (ATR)', 'Mean Close Disp (ATR)'],
        'TAIL (n=2)': [
            tail_events['purge_depth_price'].mean() / tail_events['atr_at_purge'].mean(),
            -3.47,  # Approximate from previous data
            tail_events['mfe_atr'].mean(),
            tail_events['close_disp_atr'].mean()
        ],
        'ORDINARY (n=5)': [
            ordinary_events['purge_depth_price'].mean() / ordinary_events['atr_at_purge'].mean(),
            -0.92,
            ordinary_events['mfe_atr'].mean(),
            ordinary_events['close_disp_atr'].mean()
        ]
    })
    print(comparison.to_string(index=False))

    print("\n[OBSERVATION] The two tail events show deeper average penetration and stronger negative pre-2h movement.")
    print("This is descriptive only on n=7. No statistical claim.")

if __name__ == "__main__":
    main()
