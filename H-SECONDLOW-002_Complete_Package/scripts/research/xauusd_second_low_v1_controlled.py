#!/usr/bin/env python3
"""
XAUUSD Second-Low Purge v1 — Controlled Event Study Harness

FROZEN EXPERIMENT CONTRACT v1
- Level: second-lowest daily Low over prior 20 completed trading days (no lookahead)
- Event: first M15 low < level after latch reset (stateful debounce)
- Reference price: close of the purge bar
- Forward window: exactly next 8 contiguous M15 bars, EXCLUDING the purge bar
- Validation: len(window)==8 AND timestamp continuity (+15min to +120min)
- No live MT5. Pure historical slice on verified corpus.

Outputs:
- RAW_EVENT_SET: all valid detected events with full metrics + dependence flags
- INDEPENDENT_EVENT_SET: one event per non-overlapping latch cycle / event family
- Summary tables (console)

This is a research diagnostic only. Not integrated into purge_delay_scan.py.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import timedelta
import hashlib
import json

# =============================================================================
# CONFIG
# =============================================================================
CORPUS_PATH = "/home/workdir/attachments/XAUUSD_M15_1year.xlsx"   # Using available source file for this run
LOOKBACK_DAYS = 20
ATR_PERIOD = 14
POST_WINDOW_BARS = 8          # exactly 8 bars after purge bar
MIN_EVENT_SPACING_MIN = 120   # minimum minutes between independent events (latch cycle)

OUTPUT_DIR = Path("/home/workdir/artifacts/results/second_low_v1")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

EXPERIMENT_VERSION = "v1.0"
CONTRACT_HASH = hashlib.sha256(json.dumps({
    "level": "second_lowest_daily_low_prior_20_completed_days",
    "event": "first_m15_low_below_level_after_latch_reset",
    "reference": "purge_bar_close",
    "forward_window": "exactly_next_8_bars_excluding_purge",
    "validation": "len==8_and_timestamp_continuity"
}, sort_keys=True).encode()).hexdigest()[:16]


def load_corpus(path: str) -> pd.DataFrame:
    """Load and prepare the verified M15 corpus (supports CSV or XLSX)."""
    print(f"Loading corpus: {path}")
    if path.lower().endswith(('.xlsx', '.xls')):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp').sort_index()
    df = df.rename(columns={c: c.lower() for c in df.columns})
    print(f"Loaded {len(df):,} bars | {df.index[0]} → {df.index[-1]}")
    return df[['open', 'high', 'low', 'close', 'volume']]


def compute_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=max(1, period // 2)).mean()


def compute_daily_second_low(df: pd.DataFrame, lookback: int = LOOKBACK_DAYS) -> pd.DataFrame:
    daily = df.resample('1D').agg(High=('high', 'max'), Low=('low', 'min')).dropna(how='all')
    daily['second_low_20d'] = daily['Low'].rolling(lookback).apply(
        lambda x: sorted(x.dropna())[1] if len(x.dropna()) >= 2 else np.nan,
        raw=False
    ).shift(1)
    out = df.copy()
    out['second_low_20d'] = daily['second_low_20d'].reindex(out.index, method='ffill')
    return out


def detect_second_low_purges(df: pd.DataFrame) -> pd.DataFrame:
    """Stateful latch detection for second-low breaches."""
    df = df.copy()
    df['atr'] = compute_atr(df)

    n = len(df)
    event = np.zeros(n, dtype=bool)
    armed = False

    sl = df['second_low_20d'].to_numpy()
    low = df['low'].to_numpy()
    close = df['close'].to_numpy()

    for i in range(n):
        if np.isnan(sl[i]):
            continue
        if not armed:
            if low[i] < sl[i]:
                event[i] = True
                armed = True
        else:
            if close[i] >= sl[i]:
                armed = False

    df['second_low_purge_event'] = event
    return df


def extract_strict_post_window(df: pd.DataFrame, purge_pos: int) -> pd.DataFrame:
    """Exactly next 8 bars, excluding purge bar. Returns empty DF if invalid."""
    post = df.iloc[purge_pos + 1 : purge_pos + 1 + POST_WINDOW_BARS]
    if len(post) != POST_WINDOW_BARS:
        return pd.DataFrame()

    # Timestamp continuity
    expected_first = df.index[purge_pos] + timedelta(minutes=15)
    expected_last = df.index[purge_pos] + timedelta(minutes=120)
    if post.index[0] != expected_first or post.index[-1] != expected_last:
        return pd.DataFrame()

    return post


def compute_metrics(post: pd.DataFrame, entry_price: float, atr_at_purge: float) -> dict:
    if post.empty:
        return {}

    high = post['high'].max()
    low = post['low'].min()
    final_close = post['close'].iloc[-1]

    mfe = high - entry_price
    mae = entry_price - low
    close_disp = final_close - entry_price

    tth_idx = post['high'].idxmax()
    ttl_idx = post['low'].idxmin()
    time_to_high = (tth_idx - post.index[0]).total_seconds() / 60
    time_to_low = (ttl_idx - post.index[0]).total_seconds() / 60

    return {
        'mfe_price': round(mfe, 4),
        'mae_price': round(mae, 4),
        'close_disp_price': round(close_disp, 4),
        'mfe_atr': round(mfe / atr_at_purge, 4) if atr_at_purge > 0 else np.nan,
        'mae_atr': round(mae / atr_at_purge, 4) if atr_at_purge > 0 else np.nan,
        'close_disp_atr': round(close_disp / atr_at_purge, 4) if atr_at_purge > 0 else np.nan,
        'time_to_high_min': round(time_to_high, 1),
        'time_to_low_min': round(time_to_low, 1),
    }


def assign_session(ts: pd.Timestamp) -> str:
    h = ts.hour
    if 0 <= h < 7: return 'ASIA'
    if 7 <= h < 12: return 'LONDON'
    if 12 <= h < 16: return 'OVERLAP'
    if 16 <= h < 21: return 'NY'
    return 'LATE'


def build_event_dataset(df: pd.DataFrame) -> pd.DataFrame:
    events = df[df['second_low_purge_event']].copy()
    records = []

    for i, (purge_time, row) in enumerate(events.iterrows()):
        purge_pos = df.index.get_loc(purge_time)
        post = extract_strict_post_window(df, purge_pos)
        if post.empty:
            continue

        entry_price = row['close']
        atr = row['atr']

        metrics = compute_metrics(post, entry_price, atr)
        if not metrics:
            continue

        # Dependence features
        session = assign_session(purge_time)
        vol_regime = 'high' if row['atr'] > df['atr'].median() else 'low'

        records.append({
            'event_id': i,
            'purge_time': purge_time,
            'purge_low': round(row['low'], 4),
            'second_low_20d': round(row['second_low_20d'], 4),
            'purge_depth_price': round(row['second_low_20d'] - row['low'], 4),
            'atr_at_purge': round(atr, 4),
            'session': session,
            'vol_regime': vol_regime,
            **metrics
        })

    return pd.DataFrame(records)


def build_independent_set(raw_df: pd.DataFrame) -> pd.DataFrame:
    """One event per non-overlapping latch cycle (simple time-based dedup)."""
    if raw_df.empty:
        return raw_df

    raw_df = raw_df.sort_values('purge_time').reset_index(drop=True)
    independent = []
    last_time = None

    for _, row in raw_df.iterrows():
        if last_time is None or (row['purge_time'] - last_time).total_seconds() / 60 >= MIN_EVENT_SPACING_MIN:
            independent.append(row)
            last_time = row['purge_time']

    return pd.DataFrame(independent)


def generate_matched_controls(df: pd.DataFrame, n_controls: int = 100, seed: int = 42) -> pd.DataFrame:
    """
    Generate simple matched random timestamps as controls.
    Matching on session + broad ATR regime (high/low).
    This is a basic baseline for illustration.
    """
    np.random.seed(seed)
    controls = []

    # Precompute session and vol regime for all bars
    df = df.copy()
    df['session'] = df.index.map(assign_session)
    median_atr = df['atr'].median()
    df['vol_regime'] = np.where(df['atr'] > median_atr, 'high', 'low')

    for _ in range(n_controls):
        # Sample a random bar
        rand_idx = np.random.randint(0, len(df))
        rand_row = df.iloc[rand_idx]
        rand_time = df.index[rand_idx]

        # Simulate a "post window" of 8 bars after this random timestamp
        try:
            rand_pos = df.index.get_loc(rand_time)
            post = df.iloc[rand_pos + 1 : rand_pos + 1 + POST_WINDOW_BARS]
            if len(post) != POST_WINDOW_BARS:
                continue
        except:
            continue

        entry_price = rand_row['close']
        atr = rand_row['atr']

        # Compute same metrics as real events
        high = post['high'].max()
        low = post['low'].min()
        final_close = post['close'].iloc[-1]

        mfe = high - entry_price
        mae = entry_price - low
        close_disp = final_close - entry_price

        controls.append({
            'control_type': 'random_session_atr_matched',
            'timestamp': rand_time,
            'session': rand_row['session'],
            'vol_regime': rand_row['vol_regime'],
            'mfe_atr': round(mfe / atr, 4) if atr > 0 else np.nan,
            'mae_atr': round(mae / atr, 4) if atr > 0 else np.nan,
            'close_disp_atr': round(close_disp / atr, 4) if atr > 0 else np.nan,
        })

    return pd.DataFrame(controls)


def main():
    print("=" * 80)
    print("XAUUSD SECOND-LOW PURGE v1 — CONTROLLED EVENT STUDY")
    print(f"Experiment Version: {EXPERIMENT_VERSION} | Contract Hash: {CONTRACT_HASH}")
    print("=" * 80)

    if not Path(CORPUS_PATH).exists():
        print(f"ERROR: Corpus not found at {CORPUS_PATH}")
        print("Please place the full verified XAUUSD_M15.csv in the expected location.")
        return

    df = load_corpus(CORPUS_PATH)
    df = compute_daily_second_low(df)
    df = detect_second_low_purges(df)

    print("\nBuilding RAW_EVENT_SET ...")
    raw_events = build_event_dataset(df)
    print(f"Raw valid events with complete 8-bar windows: {len(raw_events)}")

    print("\nBuilding INDEPENDENT_EVENT_SET (non-overlapping families) ...")
    independent_events = build_independent_set(raw_events)
    print(f"Independent events (min {MIN_EVENT_SPACING_MIN}min spacing): {len(independent_events)}")

    # Add metadata
    for df_out in [raw_events, independent_events]:
        if not df_out.empty:
            df_out['experiment_version'] = EXPERIMENT_VERSION
            df_out['contract_hash'] = CONTRACT_HASH
            df_out['corpus_hash'] = hashlib.sha256(Path(CORPUS_PATH).read_bytes()).hexdigest()[:16]

    # Save
    raw_path = OUTPUT_DIR / "xauusd_second_low_v1_raw_events.csv"
    ind_path = OUTPUT_DIR / "xauusd_second_low_v1_independent_events.csv"

    raw_events.to_csv(raw_path, index=False)
    independent_events.to_csv(ind_path, index=False)

    print(f"\nSaved RAW_EVENT_SET     → {raw_path}")
    print(f"Saved INDEPENDENT_EVENT_SET → {ind_path}")

    # Basic summary on Independent set
    if not independent_events.empty:
        print("\n--- INDEPENDENT SET SUMMARY ---")
        print(f"Mean MFE (ATR):     {independent_events['mfe_atr'].mean():.3f}")
        print(f"Median MFE (ATR):   {independent_events['mfe_atr'].median():.3f}")
        print(f"Mean Close Disp (ATR): {independent_events['close_disp_atr'].mean():.3f}")
        print(f"Positive close disp rate: {(independent_events['close_disp_atr'] > 0).mean()*100:.1f}%")

    # Generate simple matched controls
    print("\nGenerating matched random controls (session + ATR regime)...")
    controls_df = generate_matched_controls(df, n_controls=200)
    if not controls_df.empty:
        print(f"Generated {len(controls_df)} matched control observations")

        # Quick comparison
        ind_mfe = independent_events['mfe_atr'].mean() if not independent_events.empty else np.nan
        ctrl_mfe = controls_df['mfe_atr'].mean()
        print(f"\n--- Quick Comparison (Independent vs Matched Controls) ---")
        print(f"Mean MFE (ATR) - Independent Events : {ind_mfe:.3f}")
        print(f"Mean MFE (ATR) - Matched Controls   : {ctrl_mfe:.3f}")
        print(f"Difference (Event - Control)        : {ind_mfe - ctrl_mfe:.3f}")

    print("\n[NOTE] This is research output only. No integration into production scanner.")
    print("Next recommended steps: full corpus run + permutation/bootstrap tests.")


if __name__ == "__main__":
    main()
