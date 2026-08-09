"""
gaussian_rr_scatter.py — Phase 1: Gaussian ↔ RR Coupling Diagnostic
====================================================================
Loads OHLC data, runs both engines per-bar, and reports correlation,
mean comparison, and distribution stats. Does NOT require any audit logs.
"""

import math
import sys
import os
from pathlib import Path
 
# ── Ensure project root is on sys.path ────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np

# ── Engine imports ────────────────────────────────────────────────
from engines.rr_engine import RREngine
from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
from features.feature_schema import CANONICAL_FEATURES

# ── Config ────────────────────────────────────────────────────────
CSV_PATH = PROJECT_ROOT / "data" / "BNBUSDT_M15.csv"
MAX_BARS = 50_000          # last 50k bars (~520 days @ M15)
RR_MEAN_TARGET = 0.7468    # reported mean from Gate-ON ablation
GAUSS_MEAN_TARGET = 0.7468

# ── Helpers ───────────────────────────────────────────────────────

def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def compute_momentum(series: pd.Series, period: int = 14) -> pd.Series:
    """Returns normalised momentum: (close - close[-period]) / close[-period]"""
    shifted = series.shift(period)
    return (series - shifted) / shifted

def make_canonical_features(row: pd.Series, ema_fast: float, ema_slow: float,
                              momentum: float, atr: float) -> dict:
    """Build a dict with all 38 CANONICAL_FEATURES keys, filling defaults
    for unused ones and real values for the features the engines actually use."""
    d = {}
    for k in CANONICAL_FEATURES:
        d[k] = 0.0  # default for all
    # Override with real values
    d["open"] = float(row["open"])
    d["high"] = float(row["high"])
    d["low"] = float(row["low"])
    d["close"] = float(row["close"])
    d["volume"] = float(row.get("volume", 0))
    d["ema_fast"] = ema_fast
    d["ema_slow"] = ema_slow
    d["momentum_score"] = momentum
    d["atr"] = atr
    return d

# ── Main ──────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Phase 1: Gaussian ↔ RR Coupling Diagnostic")
    print("=" * 60)

    # 1. Load data
    print(f"\n[1] Loading data: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, parse_dates=["timestamp"])
    print(f"    Rows available: {len(df):,}")

    # Take last N bars
    if len(df) > MAX_BARS:
        df = df.tail(MAX_BARS)
    print(f"    Rows used:      {len(df):,}")
    print(f"    Date range:     {df['timestamp'].min()} → {df['timestamp'].max()}")

    # ── Compute features needed by HeuristicGaussianEngine ──────────
    # It needs: ema_fast, ema_slow, momentum_score (plus 38-key assertion)
    print("\n[2] Computing EMA/momentum/ATR features ...")
    close = df["close"]
    high = df["high"]
    low = df["low"]
    ema_fast = compute_ema(close, period=12)
    ema_slow = compute_ema(close, period=26)
    momentum_score = compute_momentum(close, period=14)
    # Simple ATR (14-period)
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean()

    # ── Initialise engines ──────────────────────────────────────────
    rr_engine = RREngine(config={"min_rr": 1.5})
    # Gaussian engine with mu=0, sigma=1 (no registry model)
    gauss_engine = HeuristicGaussianEngine(
        {"gaussian_mu": 0.0, "gaussian_sigma": 1.0},
        instrument="BNBUSDT",
        preload_registry=False,
    )

    # ── Per-bar scoring ─────────────────────────────────────────────
    print("\n[3] Running per-bar engines ...")
    rr_scores = []
    gauss_scores = []
    gauss_fails = 0
    rr_fails = 0

    total = len(df)
    for i in range(total):
        row = df.iloc[i]

        # Build full canonical feature dict
        feat = make_canonical_features(
            row,
            ema_fast=float(ema_fast.iloc[i]) if not pd.isna(ema_fast.iloc[i]) else 0.0,
            ema_slow=float(ema_slow.iloc[i]) if not pd.isna(ema_slow.iloc[i]) else 0.0,
            momentum=float(momentum_score.iloc[i]) if not pd.isna(momentum_score.iloc[i]) else 0.0,
            atr=float(atr.iloc[i]) if not pd.isna(atr.iloc[i]) else 0.0,
        )

        # RREngine
        try:
            rr_result = rr_engine.compute({
                "close": float(row["close"]),
                "high":  float(row["high"]),
                "low":   float(row["low"]),
            })
            rr_scores.append(rr_result.get("score", 0.0))
        except Exception as e:
            rr_scores.append(0.0)
            rr_fails += 1

        # HeuristicGaussianEngine
        try:
            gauss_result = gauss_engine.compute(feat)
            gauss_scores.append(gauss_result.get("score", 0.5))
        except Exception as e:
            gauss_scores.append(0.5)
            gauss_fails += 1

        if (i + 1) % 10000 == 0:
            print(f"    Scored {i+1:,}/{total:,} bars ...")

    # ── Clean invalid entries (NaN from momentum warm-up) ───────────
    rr_arr = np.array(rr_scores, dtype=float)
    gauss_arr = np.array(gauss_scores, dtype=float)
    valid = ~(np.isnan(rr_arr) | np.isnan(gauss_arr))
    rr_arr = rr_arr[valid]
    gauss_arr = gauss_arr[valid]

    print(f"\n[4] Results ({len(rr_arr):,} valid bars scored)")
    print(f"    RR  fails: {rr_fails}  |  Gaussian fails: {gauss_fails}")

    # ── Basic statistics ────────────────────────────────────────────
    rr_mean = float(np.mean(rr_arr))
    gauss_mean = float(np.mean(gauss_arr))
    rr_std = float(np.std(rr_arr))
    gauss_std = float(np.std(gauss_arr))
    rr_median = float(np.median(rr_arr))
    gauss_median = float(np.median(gauss_arr))

    print(f"\n{'Metric':<25} {'RR (Candle Polarity)':<25} {'Gaussian':<25}")
    print("-" * 75)
    print(f"{'Count':<25} {len(rr_arr):<25} {len(gauss_arr):<25}")
    print(f"{'Mean':<25} {rr_mean:<25.6f} {gauss_mean:<25.6f}")
    print(f"{'Std':<25} {rr_std:<25.6f} {gauss_std:<25.6f}")
    print(f"{'Median':<25} {rr_median:<25.6f} {gauss_median:<25.6f}")
    print(f"{'Min':<25} {float(np.min(rr_arr)):<25.6f} {float(np.min(gauss_arr)):<25.6f}")
    print(f"{'Max':<25} {float(np.max(rr_arr)):<25.6f} {float(np.max(gauss_arr)):<25.6f}")

    # ── Identical means check ───────────────────────────────────────
    print(f"\n[5] Coupling check:")
    print(f"    RR mean:      {rr_mean:.6f}")
    print(f"    Gaussian mean: {gauss_mean:.6f}")
    print(f"    Mean diff:     {abs(rr_mean - gauss_mean):.6f}")
    print(f"    Target diff (vs reported 0.7468):")
    print(f"      RR  − target: {abs(rr_mean - RR_MEAN_TARGET):.6f}")
    print(f"      Gauss − target: {abs(gauss_mean - GAUSS_MEAN_TARGET):.6f}")

    # ── Correlation ─────────────────────────────────────────────────
    # Guard against constant array (std == 0)
    if gauss_std > 0 and rr_std > 0:
        corr = float(np.corrcoef(rr_arr, gauss_arr)[0, 1])
    else:
        corr = None
    print(f"\n    Pearson correlation: {corr if corr is not None else 'N/A (zero variance)'}")

    # ── Exact identity check ────────────────────────────────────────
    exact_match = int(np.sum(np.isclose(rr_arr, gauss_arr, atol=1e-6)))
    print(f"    Bars with exact identical scores: {exact_match:,} / {len(rr_arr):,} "
          f"({100.0 * exact_match / len(rr_arr):.2f}%)")

    # Bars where score differs by > 0.001
    diff = np.abs(rr_arr - gauss_arr)
    different_bars = int(np.sum(diff > 0.001))
    print(f"    Bars with diff > 0.001: {different_bars:,} / {len(rr_arr):,} "
          f"({100.0 * different_bars / len(rr_arr):.2f}%)")

    # ── Saturation check ────────────────────────────────────────────
    rr_saturated = int(np.sum(rr_arr >= 0.95))
    gauss_saturated = int(np.sum(gauss_arr >= 0.95))
    print(f"\n    RR  scores ≥ 0.95: {rr_saturated:,} ({100.0 * rr_saturated / len(rr_arr):.1f}%)")
    print(f"    Gauss scores ≥ 0.95: {gauss_saturated:,} ({100.0 * gauss_saturated / len(gauss_arr):.1f}%)")

    # ── Scatter plot (if matplotlib available) ──────────────────────
    try:
        import matplotlib.pyplot as plt
        print("\n[6] Generating scatter plot ...")
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # Scatter
        ax = axes[0]
        corr_label = f"r = {corr:.4f}" if corr is not None else "r = N/A"
        ax.scatter(gauss_arr, rr_arr, s=1, alpha=0.3, c="#1f77b4")
        ax.plot([0, 1], [0, 1], "r--", lw=1, alpha=0.7, label="y=x (perfect match)")
        ax.set_xlabel("Gaussian Score")
        ax.set_ylabel("RR (Candle Polarity) Score")
        ax.set_title(f"Gaussian vs RR Score ({corr_label})")
        ax.legend()
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.grid(True, alpha=0.3)

        # Histogram overlay
        ax = axes[1]
        ax.hist(gauss_arr, bins=80, alpha=0.6, label=f"Gaussian (μ={gauss_mean:.3f}, σ={gauss_std:.3f})", color="#ff7f0e")
        ax.hist(rr_arr, bins=80, alpha=0.6, label=f"RR (μ={rr_mean:.3f}, σ={rr_std:.3f})", color="#1f77b4")
        ax.set_xlabel("Score")
        ax.set_ylabel("Frequency")
        ax.set_title("Score Distribution")
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        out_path = PROJECT_ROOT / "reports" / "gaussian_rr_scatter.png"
        plt.savefig(str(out_path), dpi=150)
        print(f"    Plot saved: {out_path}")
        plt.close()
    except ImportError:
        print("\n[6] matplotlib not available — skipping scatter plot.")

    # ── Verdict ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("VERDICT")
    print("=" * 60)
    if corr is not None:
        if corr > 0.95:
            print("STRONG COUPLING: Correlation > 0.95")
        elif corr > 0.80:
            print("MODERATE COUPLING: Correlation > 0.80")
        elif corr > 0.50:
            print("WEAK COUPLING: Correlation between 0.50 and 0.80")
        else:
            print("NO MEANINGFUL COUPLING: Correlation < 0.50")
    else:
        print("COUPLING INDETERMINATE: Zero variance in at least one engine")

    if exact_match > 0.5 * len(rr_arr):
        print("IDENTICAL SCORES: >50% of bars have exactly identical scores")
    elif exact_match > 0.1 * len(rr_arr):
        print(f"FREQUENT IDENTICAL SCORES: {100.0 * exact_match / len(rr_arr):.1f}% of bars are identical")
    else:
        print(f"SCORES DIFFER PER-BAR: only {100.0 * exact_match / len(rr_arr):.1f}% of bars are identical")

    match_target = abs(rr_mean - RR_MEAN_TARGET) < 0.001 and abs(gauss_mean - GAUSS_MEAN_TARGET) < 0.001
    if match_target:
        print("REPORTED 0.7468 MATCH: Both engines matched the reported mean.")
    else:
        print(f"REPORTED 0.7468 MISMATCH (RR: {rr_mean:.4f}, Gauss: {gauss_mean:.4f})")
        print("The reported identical means were likely a fused/combined score, not raw engine means.")

    print("=" * 60)


if __name__ == "__main__":
    main()