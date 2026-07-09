"""
Derived-metric primitives — the immutable scalar source of truth for deterministic
NORMALIZED feature mathematics (ATR/price-relative quantities).

MECHANISM, NOT POLICY. Sibling of candle_math.py (the OHLC-identity layer). These are the
canonical scalar definitions of the derived metrics declared in
configs/formulas/market_ontology.yaml (`derived_metrics` section); execution is via the
registry (src/features/registry/), never `eval`'d.

Each function is transcribed VERBATIM from the vectorized batch pipeline
(src/features/feature_pipeline.py, the training-truth source) — the YAML formula, the pipeline
numpy form, and the scalar function below must all agree. The vectorized pipeline is bound to
these scalars by tests/test_derived_math.py (parity battery), exactly as candle_math is bound by
tests/test_candle_math.py.

Fallback discipline mirrors the pipeline EXACTLY (it is load-bearing — the pipeline uses NaN
fallbacks so finalize() drops ATR-warmup rows, and 1.0 / 0.0 sentinels where a real value is
semantically "none"):
  - disp_strength / ema_spread / momentum_score : NaN when ATR is unavailable
  - retest_depth                                : 0.0 when ATR is unavailable ("no retest")
  - volatility_ratio                            : 1.0 when ATR is unavailable (neutral ratio)

All functions are scalar (float -> float). `math.nan` is the scalar analogue of the pipeline's
`np.nan`.
"""
from __future__ import annotations

import math


def disp_strength(body_size: float, atr: float, close: float) -> float:
    """
    Displacement strength: clip(body_size / (atr * close), 0, 3), NaN when ATR/close unavailable.

    Canonical: feature_pipeline.py:565-570. `atr` is the close-relative ATR (atr_14_raw/close);
    `atr * close` reconstructs absolute-price ATR. Note the naming collision with
    scoring_engine.py's local `disp_strength = move/atr` (a different quantity — Phase B).
    """
    if atr > 0 and close > 0:
        val = body_size / (atr * close)
        return min(3.0, max(0.0, val))
    return math.nan


def retest_depth(close: float, ema_fast: float, atr: float) -> float:
    """
    Retest depth: clip(|close - ema_fast| / (atr * close), 0, 1), 0.0 when ATR/close unavailable.

    Canonical: feature_pipeline.py:579-584. The pipeline additionally gates this on
    `retest_flag == 1` (a stateful condition); this function is the MATH when the retest is active.
    """
    if atr > 0 and close > 0:
        val = abs(close - ema_fast) / (atr * close)
        return min(1.0, max(0.0, val))
    return 0.0


def ema_spread(ema_fast: float, ema_slow: float, atr: float) -> float:
    """EMA spread: (ema_fast - ema_slow) / atr, NaN when ATR unavailable. (feature_pipeline.py:497-501)"""
    if atr > 0:
        return (ema_fast - ema_slow) / atr
    return math.nan


def momentum_score(close_delta: float, atr: float) -> float:
    """
    Momentum score: close_delta / atr, NaN when ATR unavailable. (feature_pipeline.py:503-507)

    `close_delta` is the one-bar price change (close.diff()).
    """
    if atr > 0:
        return close_delta / atr
    return math.nan


def volatility_ratio(high: float, low: float, atr: float, close: float) -> float:
    """
    Volatility ratio: (high - low) / (atr * close), 1.0 (neutral) when ATR/close unavailable.

    Canonical: feature_pipeline.py:482-486. Fallback is 1.0 (NOT NaN/0.0) — mirror exactly.
    (high - low) is candle_range.
    """
    if atr > 0 and close > 0:
        return (high - low) / (atr * close)
    return 1.0


def liquidity_distance(close: float, atr: float, *levels: float) -> float:
    """
    ATR-normalized distance to the nearest liquidity level:
        min over finite `levels` of |close - level| / (atr * close), clipped >= 0.

    Returns NaN when atr*close <= 0 or no finite level is supplied. Canonical:
    feature_pipeline.py:641-651. The registry owns this DISTANCE MATH; the pipeline owns which
    levels (trailing swing highs/lows, ffill'd BOS) — that structural resolution is out of scope.
    """
    atr_abs = atr * close
    if not (atr_abs > 0):
        return math.nan
    dists = [abs(close - lvl) / atr_abs for lvl in levels if lvl == lvl]  # lvl==lvl drops NaN
    if not dists:
        return math.nan
    return max(0.0, min(dists))


def displacement_retrace(retest_close: float, disp_open: float, disp_close: float) -> float:
    """
    FM-027 (F-050 remediation CH-001): CROSS-CANDLE retracement — how far the retest close moved
    back toward the displacement open, normalized by the displacement body; clipped [0, 1].

    Canonical: crt_engine_v2.py:1372 / crt_gaussian_scorer.py:190 (historically EMITTED under the
    colliding name "retest_depth" — a DISTINCT quantity from FM-021). Returns 0.0 when the
    displacement body is zero (the source sites skip/None-guard; scalar mirrors as 0.0-with-note —
    callers that need skip semantics test disp_move themselves).
    """
    disp_move = abs(disp_close - disp_open)
    if disp_move <= 0:
        return 0.0
    val = abs(retest_close - disp_open) / disp_move
    return min(1.0, max(0.0, val))


def displacement_atr_ratio(candle_range: float, atr: float) -> float:
    """
    FM-028 (F-050 sibling): structural displacement magnitude in ATR units — candle_range / atr,
    0.0 when ATR unavailable. Canonical: crt_engine_v2.py:1355 (family :1560, scorer :194) —
    historically emitted as "disp_str"/"disp_strength", colliding with FM-020 body/(atr·close).
    """
    if atr > 0:
        return candle_range / atr
    return 0.0


def liquidity_pressure_score(distance: float) -> float:
    """
    Liquidity pressure: clip(exp(-0.5 * distance), 0, 1); a NaN distance is treated as 10.0
    (the pipeline's fillna sentinel -> exp(-5) ~= 0.0067). (feature_pipeline.py:654-656)
    """
    d = 10.0 if distance != distance else distance   # distance != distance is True only for NaN
    val = math.exp(-0.5 * d)
    return min(1.0, max(0.0, val))
