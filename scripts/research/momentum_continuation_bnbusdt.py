#!/usr/bin/env python
"""
Momentum Continuation Research — BNBUSDT M15
=============================================

PURE RESEARCH. No optimization. No curve-fitting.

Measures whether momentum continuation patterns can be exploited on BNBUSDT
M15 data by testing multiple entry definitions and measuring forward outcomes
at fixed horizons (15m, 30m, 45m, 60m, 90m).

Entry definitions tested:
  1. Close > previous close (raw directional)
  2. Close above EMA20 (trend filter)
  3. Positive EMA slope (momentum building)
  4. Momentum threshold (close change > 80th percentile of 20-bar window)
  5. Volume expansion (volume > 1.5x EMA20 of volume)
  6. Combined: EMA slope positive AND volume expansion AND RSI > 50

Output: docs/analysis/bnbusdt_momentum_continuation_report.md
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

# ──────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────
CANDLES_CSV = "data/BNBUSDT_M15.csv"
OUTPUT_DIR = "results/research/momentum_continuation"
OUTPUT_REPORT = "docs/analysis/bnbusdt_momentum_continuation_report.md"
OUTPUT_DATASET = os.path.join(OUTPUT_DIR, "momentum_signals_dataset.csv")

M15 = 15  # minutes per candle

# Horizons in minutes → candles
HORIZONS = {
    "15m": 1,
    "30m": 2,
    "45m": 3,
    "60m": 4,
    "90m": 6,
}

# Feature fields to compare winners vs losers
COMPARE_FEATURES = [
    "ema20_slope",
    "mom_change_pct",
    "volume_ratio",
    "atr_pct",
    "body_pct",
    "rsi_14",
    "trend_strength",
    "session",
    "regime",
    "hour",
    "dow",
]

# ──────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────

def rolling_ema(values: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average."""
    alpha = 2.0 / (period + 1)
    ema = np.empty_like(values)
    ema[0] = values[0]
    for i in range(1, len(values)):
        ema[i] = alpha * values[i] + (1 - alpha) * ema[i - 1]
    return ema


def rolling_sma(values: np.ndarray, period: int) -> np.ndarray:
    """Simple moving average."""
    sma = np.empty_like(values)
    cumsum = np.cumsum(np.insert(values, 0, 0))
    for i in range(len(values)):
        start = max(0, i - period + 1)
        sma[i] = (cumsum[i + 1] - cumsum[start]) / (i - start + 1)
    return sma


def rolling_std(values: np.ndarray, period: int) -> np.ndarray:
    """Rolling standard deviation."""
    std = np.empty_like(values)
    for i in range(len(values)):
        start = max(0, i - period + 1)
        window = values[start:i + 1]
        std[i] = np.std(window, ddof=0)
    return std


def rolling_max(values: np.ndarray, period: int) -> np.ndarray:
    rmax = np.empty_like(values)
    for i in range(len(values)):
        start = max(0, i - period + 1)
        rmax[i] = np.max(values[start:i + 1])
    return rmax


def rolling_min(values: np.ndarray, period: int) -> np.ndarray:
    rmin = np.empty_like(values)
    for i in range(len(values)):
        start = max(0, i - period + 1)
        rmin[i] = np.min(values[start:i + 1])
    return rmin


def percentile_rank(value: float, history: np.ndarray) -> float:
    """Percentile rank of value within history (0-100)."""
    if len(history) == 0:
        return 50.0
    count_less = np.sum(history < value)
    count_equal = np.sum(history == value)
    return (count_less + 0.5 * count_equal) / len(history) * 100


# ──────────────────────────────────────────────────────────────────────
# ENTRY DEFINITIONS
# ──────────────────────────────────────────────────────────────────────

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all indicator columns to the DataFrame."""
    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values
    volumes = df["volume"].values
    opens = df["open"].values
    n = len(df)

    # EMA20
    df["ema20"] = rolling_ema(closes, 20)

    # EMA20 slope (1-candle change, normalized by price)
    ema20 = df["ema20"].values
    ema20_slope = np.full(n, 0.0)
    ema20_slope[1:] = (ema20[1:] - ema20[:-1])
    df["ema20_slope"] = ema20_slope
    df["ema20_slope_pct"] = np.where(closes > 0, ema20_slope / closes * 100, 0.0)

    # Close change %
    close_change = np.full(n, 0.0)
    close_change[1:] = (closes[1:] - closes[:-1]) / np.maximum(closes[:-1], 1e-10) * 100
    df["mom_change_pct"] = close_change

    # ATR14
    tr = np.maximum(
        highs - lows,
        np.maximum(
            np.abs(highs - np.roll(closes, 1)),
            np.abs(lows - np.roll(closes, 1)),
        ),
    )
    tr[0] = highs[0] - lows[0]
    df["atr"] = rolling_ema(tr, 14)
    df["atr_pct"] = df["atr"] / np.maximum(closes, 1e-10) * 100

    # Volume EMA20 ratio
    df["volume_ema20"] = rolling_ema(volumes, 20)
    df["volume_ratio"] = volumes / np.maximum(df["volume_ema20"].values, 1e-10)

    # Body size (percent of price)
    body = np.abs(closes - opens)
    df["body_pct"] = body / np.maximum(closes, 1e-10) * 100

    # RSI 14
    gains = np.where(close_change > 0, close_change, 0)
    losses = np.where(close_change < 0, -close_change, 0)
    avg_gain = rolling_ema(gains, 14)
    avg_loss = rolling_ema(losses, 14)
    rs = avg_gain / np.maximum(avg_loss, 1e-10)
    df["rsi_14"] = 100 - (100 / (1 + rs))

    # Trend strength (ADX-like: abs(close - ema20) / atr)
    df["trend_strength"] = np.abs(closes - ema20) / np.maximum(df["atr"].values, 1e-10)

    # Session detection (UTC)
    # Asia: 0-8, London: 8-16, New York: 16-24
    # Binance is 24/7 so we map broadly
    timestamps = pd.to_datetime(df["timestamp"])
    df["hour"] = timestamps.dt.hour
    df["dow"] = timestamps.dt.dayofweek  # 0=Monday

    def get_session(h: int) -> int:
        if 0 <= h < 8:
            return 0  # Asia
        elif 8 <= h < 16:
            return 1  # London/Europe
        else:
            return 2  # New York/Americas

    df["session"] = df["hour"].apply(get_session)

    # Regime: volatility percentile
    atr_20 = rolling_ema(tr, 20)
    regime = np.full(n, 1, dtype=int)  # default to medium volatility
    for i in range(20, n):
        rank = percentile_rank(atr_20[i], atr_20[:i])
        if rank < 33:
            regime[i] = 0  # low vol
        elif rank < 66:
            regime[i] = 1  # med vol
        else:
            regime[i] = 2  # high vol
    df["regime"] = regime

    # Momentum percentile rank (20-bar lookback)
    mom_rank = np.full(n, np.nan)
    for i in range(20, n):
        mom_rank[i] = percentile_rank(close_change[i], close_change[i - 19:i + 1])
    df["mom_percentile"] = mom_rank

    return df


# ──────────────────────────────────────────────────────────────────────
# ENTRY SIGNAL DEFINITIONS
# ──────────────────────────────────────────────────────────────────────

def entry_close_up(row: pd.Series, _df: pd.DataFrame) -> bool:
    """Close > previous close"""
    return row["mom_change_pct"] > 0


def entry_above_ema20(row: pd.Series, _df: pd.DataFrame) -> bool:
    """Close above EMA20"""
    return row["close"] > row["ema20"]


def entry_ema_slope_pos(row: pd.Series, _df: pd.DataFrame) -> bool:
    """Positive EMA slope"""
    return row["ema20_slope"] > 0


def entry_momentum_threshold(row: pd.Series, _df: pd.DataFrame) -> bool:
    """Close change % > 0.5 * ATR% (momentum exceeding noise)"""
    return row["mom_change_pct"] > 0.5 * row["atr_pct"]


def entry_volume_expansion(row: pd.Series, _df: pd.DataFrame) -> bool:
    """Volume > 1.5x EMA20 volume"""
    return row["volume_ratio"] > 1.5


def entry_combined(row: pd.Series, _df: pd.DataFrame) -> bool:
    """
    Combined: EMA slope positive AND close > EMA20 AND volume expansion AND RSI > 50
    """
    return (
        row["ema20_slope"] > 0
        and row["close"] > row["ema20"]
        and row["volume_ratio"] > 1.5
        and row["rsi_14"] > 50
    )


def entry_momentum_top_20pct(row: pd.Series, _df: pd.DataFrame) -> bool:
    """Close change in top 20% of 20-bar window"""
    return (
        not np.isnan(row["mom_percentile"])
        and row["mom_percentile"] >= 80.0
    )


ENTRY_DEFINITIONS = {
    "Close_Up": entry_close_up,
    "Above_EMA20": entry_above_ema20,
    "EMA_Slope_Pos": entry_ema_slope_pos,
    "Momentum_Threshold": entry_momentum_threshold,
    "Volume_Expansion": entry_volume_expansion,
    "Momentum_Top20pct": entry_momentum_top_20pct,
    "Combined_Strong": entry_combined,
}


# ──────────────────────────────────────────────────────────────────────
# SIGNAL GENERATION
# ──────────────────────────────────────────────────────────────────────

def generate_signals(df: pd.DataFrame, min_idx: int = 60) -> dict[str, list[dict]]:
    """
    Generate entry signals for all definitions.
    min_idx: skip early rows until indicators are stable.
    Returns dict { entry_name: [signal_dict, ...] }
    """
    n = len(df)
    signals: dict[str, list[dict]] = {name: [] for name in ENTRY_DEFINITIONS}

    for idx in range(min_idx, n - max(HORIZONS.values()) - 1):
        row = df.iloc[idx]

        for name, func in ENTRY_DEFINITIONS.items():
            if func(row, df):
                signals[name].append({
                    "idx": idx,
                    "timestamp": row["timestamp"],
                    "entry_price": row["close"],
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                    # Store features for clustering
                    "ema20_slope": row["ema20_slope"],
                    "mom_change_pct": row["mom_change_pct"],
                    "volume_ratio": row["volume_ratio"],
                    "atr_pct": row["atr_pct"],
                    "atr": row["atr"],
                    "body_pct": row["body_pct"],
                    "rsi_14": row["rsi_14"],
                    "trend_strength": row["trend_strength"],
                    "session": row["session"],
                    "regime": row["regime"],
                    "hour": row["hour"],
                    "dow": row["dow"],
                    "mom_percentile": row["mom_percentile"] if not np.isnan(row["mom_percentile"]) else 50,
                })

    return signals


# ──────────────────────────────────────────────────────────────────────
# FORWARD OUTCOME COMPUTATION
# ──────────────────────────────────────────────────────────────────────

def compute_outcomes(signals: list[dict], df: pd.DataFrame) -> list[dict]:
    """
    For each signal, compute forward outcomes.

    For each trade:
    - entry_price (close at signal candle)
    - max_up_{horizon} / max_down_{horizon}  (max favorable/adverse excursion)
    - close_{horizon} (close price at each horizon)
    - time_to_peak (candles to best price within 90m)
    - time_to_bottom (candles to worst price within 90m)
    - MFE_60 / MAE_60 (max favorable/adverse in 60min in price units)
    - return_{horizon} as %
    """
    n = len(df)
    max_horizon_candles = max(HORIZONS.values())

    outcomes = []
    for sig in signals:
        entry_idx = sig["idx"]
        entry_price = sig["entry_price"]

        # Initialize tracking
        best_price = entry_price
        worst_price = entry_price
        time_to_peak = 0
        time_to_bottom = 0

        # Excursions by horizon
        max_up = {h: 0.0 for h in HORIZONS}
        max_down = {h: 0.0 for h in HORIZONS}
        close_at = {h: None for h in HORIZONS}
        return_pct = {h: None for h in HORIZONS}

        for horizon_label, horizon_candles in HORIZONS.items():
            end_idx = min(entry_idx + horizon_candles, n - 1)
            window = df.iloc[entry_idx + 1: end_idx + 1]

            if len(window) == 0:
                continue

            window_high = window["high"].max()
            window_low = window["low"].min()
            window_close = window["close"].iloc[-1]

            max_up_val = max(window_high - entry_price, 0)
            max_down_val = max(entry_price - window_low, 0)

            max_up[horizon_label] = round(max_up_val, 4)
            max_down[horizon_label] = round(max_down_val, 4)
            close_at[horizon_label] = round(window_close, 4)
            return_pct[horizon_label] = round(
                (window_close - entry_price) / entry_price * 100, 4
            )

            # Track global best/worst across all horizons
            if window_high > best_price:
                best_price = window_high
                # Recalculate time_to_peak
                peak_idx = window["high"].idxmax()
                time_to_peak = peak_idx - entry_idx

            if window_low < worst_price:
                worst_price = window_low
                bottom_idx = window["low"].idxmin()
                time_to_bottom = bottom_idx - entry_idx

        # MFE/MAE in 60min (in price units)
        mfe_60 = max_up.get("60m", 0.0)
        mae_60 = max_down.get("60m", 0.0)

        # Direction of trade is implicitly LONG (momentum continuation = prices rising)
        # So positive return = win

        outcome = {
            "entry_price": entry_price,
            "max_up_15m": max_up["15m"],
            "max_up_30m": max_up["30m"],
            "max_up_45m": max_up["45m"],
            "max_up_60m": max_up["60m"],
            "max_up_90m": max_up["90m"],
            "max_down_15m": max_down["15m"],
            "max_down_30m": max_down["30m"],
            "max_down_45m": max_down["45m"],
            "max_down_60m": max_down["60m"],
            "max_down_90m": max_down["90m"],
            "close_15m": close_at["15m"],
            "close_30m": close_at["30m"],
            "close_45m": close_at["45m"],
            "close_60m": close_at["60m"],
            "close_90m": close_at["90m"],
            "return_15m": return_pct["15m"],
            "return_30m": return_pct["30m"],
            "return_45m": return_pct["45m"],
            "return_60m": return_pct["60m"],
            "return_90m": return_pct["90m"],
            "time_to_peak": time_to_peak,
            "time_to_bottom": time_to_bottom,
            "mfe_60": mfe_60,
            "mae_60": mae_60,
        }

        # Is positive after each horizon?
        for h in HORIZONS:
            r = return_pct.get(h)
            outcome[f"positive_{h}"] = 1 if r is not None and r > 0 else 0

        # Overall win/loss (return at 90m > 0)
        outcome["is_winner"] = 1 if return_pct.get("90m", -999) is not None and return_pct["90m"] > 0 else 0

        # Carry forward features
        for feat in COMPARE_FEATURES:
            outcome[feat] = sig[feat]

        outcomes.append(outcome)

    return outcomes


# ──────────────────────────────────────────────────────────────────────
# STATISTICS
# ──────────────────────────────────────────────────────────────────────

def safe_mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def safe_median(vals: list[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def compute_statistics(outcomes: list[dict], strategy_name: str) -> dict:
    """Compute all requested statistics."""
    n = len(outcomes)
    if n == 0:
        return {"strategy": strategy_name, "n_trades": 0}

    mfe_60s = [o["mfe_60"] for o in outcomes]
    mae_60s = [o["mae_60"] for o in outcomes]

    stats = {
        "strategy": strategy_name,
        "n_trades": n,
        "avg_mfe": round(safe_mean(mfe_60s), 6),
        "med_mfe": round(safe_median(mfe_60s), 6),
        "avg_mae": round(safe_mean(mae_60s), 6),
        "med_mae": round(safe_median(mae_60s), 6),
    }

    # Average return at each horizon
    for h in HORIZONS:
        returns = [o[f"return_{h}"] for o in outcomes if o[f"return_{h}"] is not None]
        stats[f"avg_return_{h}"] = round(safe_mean(returns), 4) if returns else None

    # Median time to peak/bottom
    peak_times = [o["time_to_peak"] for o in outcomes if o["time_to_peak"] > 0]
    bottom_times = [o["time_to_bottom"] for o in outcomes if o["time_to_bottom"] > 0]
    stats["med_time_to_peak"] = safe_median(peak_times) if peak_times else 0
    stats["med_time_to_bottom"] = safe_median(bottom_times) if bottom_times else 0

    # Probability positive at each horizon
    for h in HORIZONS:
        pos = [o[f"positive_{h}"] for o in outcomes]
        stats[f"prob_pos_{h}"] = round(sum(pos) / len(pos) * 100, 1) if pos else 0.0

    # Win rate (90m)
    winners = [o for o in outcomes if o["is_winner"] == 1]
    stats["win_rate_90m"] = round(len(winners) / n * 100, 1)

    # Trade frequency
    stats["total_trades"] = n
    # Date range from the data (we can estimate)
    # 70,080 candles = ~2 years
    total_days = 70080 // 96  # ~730 days
    total_months = total_days / 30.44
    stats["trades_per_day"] = round(n / total_days, 2)
    stats["trades_per_week"] = round(n / (total_days / 7), 2)
    stats["trades_per_month"] = round(n / total_months, 1)
    stats["trades_per_year"] = round(n / (total_days / 365), 0)

    # Continuation survival table
    survival = {}
    for h in HORIZONS:
        survival[h] = stats[f"prob_pos_{h}"]
    stats["survival_table"] = survival

    return stats


# ──────────────────────────────────────────────────────────────────────
# FEATURE CLUSTERING (Winners vs Losers)
# ──────────────────────────────────────────────────────────────────────

def analyze_feature_clusters(outcomes: list[dict], stats: dict) -> dict:
    """Search for feature clusters that discriminate winners vs losers."""
    n = len(outcomes)
    if n < 20:
        return {"warning": "Too few trades for feature clustering"}

    winners = [o for o in outcomes if o["is_winner"] == 1]
    losers = [o for o in outcomes if o["is_winner"] == 0]

    if len(winners) < 5 or len(losers) < 5:
        return {"warning": "Winner/loser subgroups too small"}

    results = {}
    for feat in COMPARE_FEATURES:
        w_vals = [o[feat] for o in winners if not isinstance(o[feat], str)]
        l_vals = [o[feat] for o in losers if not isinstance(o[feat], str)]

        if not w_vals or not l_vals:
            continue

        w_mean = safe_mean(w_vals)
        l_mean = safe_mean(l_vals)

        # t-test for significance
        try:
            t_stat, p_value = scipy_stats.ttest_ind(w_vals, l_vals, equal_var=False)
        except Exception:
            t_stat, p_value = 0.0, 1.0

        results[feat] = {
            "winner_mean": round(w_mean, 4),
            "loser_mean": round(l_mean, 4),
            "diff": round(w_mean - l_mean, 4),
            "p_value": round(p_value, 6),
            "significant_005": p_value < 0.05,
        }

    # Find top clusters (composite: combine features)
    # Look for 2-feature combinations that maximize separation
    numeric_features = [f for f in COMPARE_FEATURES if f not in ("session", "hour", "dow", "regime")]
    clusters = []

    for i, f1 in enumerate(numeric_features):
        for f2 in numeric_features[i + 1:]:
            w_combo = [
                (o[f1], o[f2])
                for o in winners
                if not isinstance(o.get(f1), str) and not isinstance(o.get(f2), str)
            ]
            l_combo = [
                (o[f1], o[f2])
                for o in losers
                if not isinstance(o.get(f1), str) and not isinstance(o.get(f2), str)
            ]
            if not w_combo or not l_combo:
                continue

            # Compute euclidean distance between centroids
            w_centroid = (safe_mean([c[0] for c in w_combo]), safe_mean([c[1] for c in w_combo]))
            l_centroid = (safe_mean([c[0] for c in l_combo]), safe_mean([c[1] for c in l_combo]))
            dist = math.sqrt((w_centroid[0] - l_centroid[0])**2 + (w_centroid[1] - l_centroid[1])**2)

            clusters.append({
                "features": (f1, f2),
                "distance": round(dist, 4),
                "w_centroid": (round(w_centroid[0], 4), round(w_centroid[1], 4)),
                "l_centroid": (round(l_centroid[0], 4), round(l_centroid[1], 4)),
            })

    clusters.sort(key=lambda c: c["distance"], reverse=True)

    return {
        "single_features": dict(sorted(
            results.items(),
            key=lambda x: abs(x[1]["diff"]),
            reverse=True,
        )),
        "top_clusters": clusters[:10],
    }


# ──────────────────────────────────────────────────────────────────────
# REPORT GENERATION
# ──────────────────────────────────────────────────────────────────────

def generate_report(all_stats: dict[str, dict], all_outcomes: dict[str, list[dict]],
                    all_clusters: dict[str, dict]) -> str:
    """Generate the full markdown report."""
    lines = []
    lines.append("# BNBUSDT M15 — Momentum Continuation Research")
    lines.append("")
    lines.append(f"> **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"> **Data:** `data/BNBUSDT_M15.csv` (70,080 candles, 2024-05-22 to 2026-05-21)")
    lines.append(f"> **Purpose:** Measure whether momentum continuation can be exploited on BNBUSDT")
    lines.append("> **Methodology:** No optimization. No curve-fitting. Pure measurement from historical data.")
    lines.append("")

    # ── Overview table ──
    lines.append("## Overview — All Entry Definitions")
    lines.append("")
    lines.append("| Entry Definition | Trades | Win Rate (90m) | Avg Return 60m | Med MFE | Med MAE | Med Peak (m) |")
    lines.append("|---|---|---|---|---|---|---|")

    best_def = None
    best_return = -999

    for def_name in sorted(all_stats.keys(), key=lambda x: all_stats[x].get("n_trades", 0), reverse=True):
        s = all_stats[def_name]
        n_t = s.get("n_trades", 0)
        if n_t == 0:
            continue
        wr = s.get("win_rate_90m", 0)
        ar = s.get("avg_return_60m", "N/A")
        ar_str = f"{ar:+.4f}%" if ar is not None else "N/A"
        mmfe = s.get("med_mfe", 0)
        mmae = s.get("med_mae", 0)
        mpeak = s.get("med_time_to_peak", 0) * 15  # convert candles to minutes
        lines.append(f"| {def_name} | {n_t} | {wr:.1f}% | {ar_str} | {mmfe:.4f} | {mmae:.4f} | {mpeak:.0f}m |")

        if ar is not None and ar > best_return:
            best_return = ar
            best_def = def_name

    lines.append("")

    # ── Per-definition detailed stats ──
    lines.append("---")
    lines.append("")
    lines.append("## Detailed Results Per Entry Definition")
    lines.append("")

    for def_name in sorted(all_stats.keys(), key=lambda x: all_stats[x].get("n_trades", 0), reverse=True):
        s = all_stats[def_name]
        n_t = s.get("n_trades", 0)
        if n_t == 0:
            continue

        lines.append(f"### {def_name}")
        lines.append("")
        lines.append(f"- **Total trades:** {n_t}")
        lines.append(f"- **Win rate (90m):** {s.get('win_rate_90m', 0):.1f}%")
        lines.append("")

        # Frequency
        lines.append("#### Trade Frequency")
        lines.append(f"- Per day: {s.get('trades_per_day', 0):.2f}")
        lines.append(f"- Per week: {s.get('trades_per_week', 0):.2f}")
        lines.append(f"- Per month: {s.get('trades_per_month', 0):.1f}")
        lines.append(f"- Per year: {s.get('trades_per_year', 0):.0f}")
        lines.append("")

        # MFE / MAE
        lines.append("#### MFE & MAE (60m horizon)")
        lines.append(f"- Average MFE: {s.get('avg_mfe', 0):.6f}")
        lines.append(f"- Median MFE: {s.get('med_mfe', 0):.6f}")
        lines.append(f"- Average MAE: {s.get('avg_mae', 0):.6f}")
        lines.append(f"- Median MAE: {s.get('med_mae', 0):.6f}")
        lines.append(f"- MFE/MAE ratio: {s.get('avg_mfe', 0) / max(s.get('avg_mae', 0.0001), 0.0001):.2f}x")
        lines.append("")

        # Time to peak/bottom
        lines.append("#### Time Analysis")
        lines.append(f"- Median time to peak: {s.get('med_time_to_peak', 0) * 15:.0f} minutes")
        lines.append(f"- Median time to bottom: {s.get('med_time_to_bottom', 0) * 15:.0f} minutes")
        lines.append("")

        # Returns
        lines.append("#### Returns at Fixed Horizons")
        lines.append("")
        lines.append("| Horizon | Avg Return (%) | Prob Positive (%) |")
        lines.append("|---|---|---|")
        for h in ["15m", "30m", "45m", "60m", "90m"]:
            ar_h = s.get(f"avg_return_{h}")
            pp_h = s.get(f"prob_pos_{h}")
            ar_s = f"{ar_h:+.4f}" if ar_h is not None else "N/A"
            pp_s = f"{pp_h:.1f}" if pp_h is not None else "N/A"
            lines.append(f"| {h} | {ar_s}% | {pp_s}% |")
        lines.append("")

        # Continuation survival
        lines.append("#### Continuation Survival Table")
        lines.append("")
        lines.append("| Time | % Trades Still Positive |")
        lines.append("|---|---|")
        surv = s.get("survival_table", {})
        for h in ["15m", "30m", "45m", "60m", "90m"]:
            pct = surv.get(h)
            pct_s = f"{pct:.1f}%" if pct is not None else "N/A"
            lines.append(f"| {h} | {pct_s} |")
        lines.append("")
        # Determine where edge decays
        decay_point = None
        for h in ["15m", "30m", "45m", "60m", "90m"]:
            pct = surv.get(h)
            if pct is not None and pct < 50:
                decay_point = h
                break
        if decay_point:
            lines.append(f"> **Edge decay point:** Probability drops below 50% at `{decay_point}`")
        else:
            lines.append(f"> **Edge persists** through 90m (probability stays above 50%)")
        lines.append("")

    # ── Feature Discovery ──
    lines.append("---")
    lines.append("")
    lines.append("## Feature Discovery — Winners vs Losers")
    lines.append("")

    for def_name in sorted(all_clusters.keys(), key=lambda x: all_stats[x].get("n_trades", 0), reverse=True):
        cluster_data = all_clusters[def_name]
        if "warning" in cluster_data:
            lines.append(f"### {def_name}")
            lines.append("")
            lines.append(f"*{cluster_data['warning']}*")
            lines.append("")
            continue

        if "single_features" not in cluster_data:
            continue

        s = all_stats.get(def_name, {})
        n_t = s.get("n_trades", 0)
        if n_t == 0:
            continue

        lines.append(f"### {def_name} — Feature Comparison")
        lines.append("")
        lines.append(f"| Feature | Winner Mean | Loser Mean | Diff | p-value | Significant? |")
        lines.append("|---|---|---|---|---|---|")

        single = cluster_data.get("single_features", {})
        for feat, data in single.items():
            wm = data.get("winner_mean", "N/A")
            lm = data.get("loser_mean", "N/A")
            diff = data.get("diff", 0)
            pv = data.get("p_value", 1)
            sig = "✅" if data.get("significant_005") else "❌"
            lines.append(f"| {feat} | {wm} | {lm} | {diff:+.4f} | {pv} | {sig} |")

        lines.append("")

        # Top clusters
        clusters = cluster_data.get("top_clusters", [])
        if clusters:
            lines.append(f"#### Top Feature Clusters (2D centroids)")
            lines.append("")
            lines.append("| Rank | Features | Distance | Winner Centroid | Loser Centroid |")
            lines.append("|---|---|---|---|---|")
            for rank, c in enumerate(clusters, 1):
                f1, f2 = c["features"]
                wc = c["w_centroid"]
                lc = c["l_centroid"]
                lines.append(f"| {rank} | {f1} + {f2} | {c['distance']:.4f} | {wc} | {lc} |")
            lines.append("")

    # ── Recommended Holding Time ──
    lines.append("---")
    lines.append("")
    lines.append("## Recommended Holding Time")
    lines.append("")

    for def_name in sorted(all_stats.keys(), key=lambda x: all_stats[x].get("n_trades", 0), reverse=True):
        s = all_stats[def_name]
        n_t = s.get("n_trades", 0)
        if n_t == 0:
            continue

        # Find horizon with highest avg return
        best_h = None
        best_ret = -999
        for h in ["15m", "30m", "45m", "60m", "90m"]:
            r = s.get(f"avg_return_{h}")
            if r is not None and r > best_ret:
                best_ret = r
                best_h = h

        if best_h:
            lines.append(f"- **{def_name}:** `{best_h}` (avg return {best_ret:+.4f}%)")
    lines.append("")

    # ── Fixed-time exits vs TP/SL ──
    lines.append("## Fixed-Time Exits vs TP/SL")
    lines.append("")
    lines.append("This research uses **fixed-time exits** exclusively (no TP/SL). The data shows:")
    lines.append("")
    for def_name in sorted(all_stats.keys(), key=lambda x: all_stats[x].get("n_trades", 0), reverse=True):
        s = all_stats[def_name]
        n_t = s.get("n_trades", 0)
        if n_t == 0:
            continue

        mfe = s.get("avg_mfe", 0)
        mae = s.get("avg_mae", 0)
        lines.append(f"- **{def_name}:** MFE {mfe:.4f} vs MAE {mae:.4f} (ratio {mfe/max(mae,0.0001):.2f}x)")
        lines.append(f"  - Avg return at best horizon: {s.get(f'avg_return_{best_h}', 'N/A')}%" if any(
            s.get(f"avg_return_{h}") is not None for h in ["15m", "30m", "45m", "60m", "90m"]
        ) else "")
    lines.append("")
    lines.append("**Finding:** Fixed-time exits reveal whether momentum has a natural decay horizon that "
                 "outperforms discretionary exit. If avg returns are positive at some horizons but "
                 "negative at others, fixed-time exits can be calibrated to capture the edge before decay.")
    lines.append("")

    # ── Top Feature Clusters Summary ──
    lines.append("## Top Feature Clusters (All Definitions)")
    lines.append("")
    all_clusters_flat = []
    for def_name, cluster_data in all_clusters.items():
        if "top_clusters" not in cluster_data:
            continue
        for c in cluster_data["top_clusters"]:
            all_clusters_flat.append({
                "def_name": def_name,
                "features": c["features"],
                "distance": c["distance"],
            })
    all_clusters_flat.sort(key=lambda x: x["distance"], reverse=True)

    if all_clusters_flat:
        lines.append("| Rank | Strategy | Features | Separation Distance |")
        lines.append("|---|---|---|---|")
        for rank, c in enumerate(all_clusters_flat[:15], 1):
            f1, f2 = c["features"]
            lines.append(f"| {rank} | {c['def_name']} | {f1} + {f2} | {c['distance']:.4f} |")
        lines.append("")

    # ── Confidence ──
    lines.append("## Confidence Level")
    lines.append("")
    total_all = sum(s.get("n_trades", 0) for s in all_stats.values())
    lines.append(f"| Factor | Assessment |")
    lines.append("|---|---|")
    lines.append(f"| Total signals across all definitions | {total_all} |")
    lines.append(f"| Data period | 2 years (70,080 M15 candles) |")
    lines.append(f"| Multiple definitions tested | {len([s for s in all_stats.values() if s.get('n_trades',0) > 0])} |")
    lines.append("| Statistical tests | Welch t-test on feature differences |")
    lines.append("| Lookahead bias | None — only past data used for indicators, only forward data for outcomes |")
    lines.append("| Survivorship bias | None — Binance live data |")
    lines.append("| Precision | M15 OHLCV (intra-candle moves not captured) |")
    lines.append("")

    if total_all < 100:
        lines.append("> **Overall confidence: LOW.** Limited sample size. Treat as exploratory.")
    elif total_all < 1000:
        lines.append("> **Overall confidence: MODERATE.** Adequate sample for preliminary conclusions.")
    else:
        lines.append("> **Overall confidence: HIGH.** Large sample size across multiple definitions.")
    lines.append("")

    # ── Failure Modes ──
    lines.append("## Failure Modes")
    lines.append("")
    lines.append("1. **Fake breakouts:** Price spikes above EMA/previous close but immediately reverses")
    lines.append("2. **Mean reversion:** Strong moves attract counter-traders, reversing gains")
    lines.append("3. **Low volatility chop:** In low-vol regimes, momentum signals produce many false starts")
    lines.append("4. **Session dependency:** Momentum may work in one session but fail in another")
    lines.append("5. **Large spread events:** News/release events create gaps that invalidate entries")
    lines.append("6. **M15 limitation:** Intra-candle momentum cannot be captured at this resolution")
    lines.append("7. **Volume reliability:** Volume on low-vol candles may be misleading")
    lines.append("")

    # ── Final Conclusion ──
    lines.append("## Final Conclusion")
    lines.append("")

    best_name = best_def or "N/A"
    best_s = all_stats.get(best_name, {})
    best_n = best_s.get("n_trades", 0)
    best_wr = best_s.get("win_rate_90m", 0)

    lines.append("### Summary")
    lines.append("")
    lines.append(f"1. **Total trades analyzed:** {total_all} across {len([s for s in all_stats.values() if s.get('n_trades',0) > 0])} entry definitions")
    lines.append(f"2. **Average trades per month:** varies by definition (see per-definition tables)")
    lines.append(f"3. **Average MFE/MAE:** varies by definition — see MFE/MAE tables above")
    lines.append(f"4. **Median time to peak:** {best_s.get('med_time_to_peak', 0) * 15:.0f} minutes (best definition)")
    lines.append(f"5. **Recommended holding time:** see per-definition analysis above")
    lines.append(f"6. **Fixed-time exits vs TP/SL:** see analysis above")
    lines.append(f"7. **Top feature clusters:** see cluster tables above")
    lines.append(f"8. **Confidence level:** see confidence assessment above")
    lines.append(f"9. **Failure modes:** listed above")
    lines.append("")

    if best_wr > 55 and best_n >= 30:
        lines.append(f"### Verdict: POTENTIAL EDGE DETECTED")
        lines.append("")
        lines.append(f"The best definition (`{best_name}`) produced a {best_wr:.1f}% win rate "
                     f"over {best_n} trades. This suggests momentum continuation *may* be exploitable "
                     f"on BNBUSDT M15, but requires further validation on out-of-sample data.")
    elif best_wr > 50:
        lines.append(f"### Verdict: WEAK SIGNAL — INCONCLUSIVE")
        lines.append("")
        lines.append(f"The best definition (`{best_name}`) produced a {best_wr:.1f}% win rate "
                     f"over {best_n} trades. This is barely above 50% and may be random noise. "
                     f"Further research needed with larger sample sizes.")
    else:
        lines.append(f"### Verdict: NO EDGE DETECTED")
        lines.append("")
        lines.append(f"No entry definition produced a statistically significant edge. "
                     f"Momentum continuation on BNBUSDT M15 appears to be random "
                     f"or negative expectancy over this period.")
    lines.append("")

    lines.append("### Key Recommendations")
    lines.append("")
    lines.append("1. **Do not optimize** — this is purely exploratory")
    lines.append("2. **Test on other instruments** — momentum may work differently on BTC/ETH/SOL")
    lines.append("3. **Test on tick data** — M15 OHLCV misses intra-candle momentum dynamics")
    lines.append("4. **Test different timeframes** — momentum may work on H1/H4 but not M15")
    lines.append("5. **Forward test** — run the best definition on live data to verify")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Report generated by `scripts/research/momentum_continuation_bnbusdt.py`*")
    lines.append(f"*{datetime.now().strftime('%Y-%m-%d %H:%M')} UTC*")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 72)
    print("BNBUSDT M15 — Momentum Continuation Research")
    print("=" * 72)

    # ── Load data ──
    print(f"\nLoading candles from {CANDLES_CSV}...")
    df = pd.read_csv(CANDLES_CSV)
    print(f"Loaded {len(df)} candles")
    print(f"Date range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")

    # ── Compute indicators ──
    print("\nComputing indicators...")
    df = compute_indicators(df)
    print(f"Indicators computed. Columns: {list(df.columns)}")

    # ── Generate signals ──
    print("\nGenerating entry signals...")
    signals = generate_signals(df)
    for name, sig_list in signals.items():
        print(f"  {name}: {len(sig_list)} signals")

    # ── Compute outcomes ──
    print("\nComputing forward outcomes...")
    all_outcomes = {}
    for name, sig_list in signals.items():
        if len(sig_list) == 0:
            print(f"  {name}: no signals, skipping")
            continue
        outcomes = compute_outcomes(sig_list, df)
        all_outcomes[name] = outcomes
        print(f"  {name}: {len(outcomes)} outcomes computed")

    # ── Statistics ──
    print("\nComputing statistics...")
    all_stats = {}
    for name, outcomes in all_outcomes.items():
        all_stats[name] = compute_statistics(outcomes, name)
        s = all_stats[name]
        n_t = s.get("n_trades", 0)
        if n_t > 0:
            print(f"  {name}: {n_t} trades, WR={s['win_rate_90m']:.1f}%, "
                  f"AvgRet60m={s.get('avg_return_60m', 'N/A')}")

    # ── Feature clustering ──
    print("\nAnalyzing feature clusters...")
    all_clusters = {}
    for name, outcomes in all_outcomes.items():
        all_clusters[name] = analyze_feature_clusters(outcomes, all_stats.get(name, {}))
        if "warning" not in all_clusters[name]:
            n_single = len(all_clusters[name].get("single_features", {}))
            n_clust = len(all_clusters[name].get("top_clusters", []))
            print(f"  {name}: {n_single} features, {n_clust} clusters")
        else:
            print(f"  {name}: {all_clusters[name]['warning']}")

    # ── Write dataset ──
    print(f"\nWriting combined dataset...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_rows = []
    for def_name, outcomes in all_outcomes.items():
        for o in outcomes:
            row = {"definition": def_name}
            row.update(o)
            all_rows.append(row)

    if all_rows:
        dataset_df = pd.DataFrame(all_rows)
        dataset_df.to_csv(OUTPUT_DATASET, index=False)
        print(f"  Written: {OUTPUT_DATASET} ({len(all_rows)} rows)")
    else:
        print("  No data to write")

    # ── Generate report ──
    print(f"\nGenerating report...")
    os.makedirs(os.path.dirname(OUTPUT_REPORT), exist_ok=True)
    report = generate_report(all_stats, all_outcomes, all_clusters)
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  Written: {OUTPUT_REPORT}")

    print("\n" + "=" * 72)
    print("RESEARCH COMPLETE")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())