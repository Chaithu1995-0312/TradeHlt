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


def disp_strength(
    body_size: float, atr: float, close: float,
    *, clip_low: float = 0.0, clip_high: float = 3.0,
) -> float:
    """
    Displacement strength: clip(body_size / (atr * close), clip_low, clip_high), NaN when
    ATR/close unavailable.

    Canonical: feature_pipeline.py:950-960. `atr` is the close-relative ATR (atr_14_raw/close);
    `atr * close` reconstructs absolute-price ATR. The former naming collision with
    scoring_engine.py's local `disp_strength = move/atr` closed 2026-07-11 as the distinct
    FM-029 `disp_strength_atr_rescale` (GD-004 retirement).

    `clip_low`/`clip_high` default to the pipeline's `feature_pipeline.disp_strength_clip_low`/
    `disp_strength_clip_high` DEFAULT VALUES (0.0/3.0) so every existing caller is unaffected
    (2026-07-31: previously hardcoded; this scalar authority silently diverged from the pipeline
    the moment those config keys were changed off-default). Pass the live config values to
    verify parity under a non-default config.
    """
    if atr > 0 and close > 0:
        val = body_size / (atr * close)
        return min(clip_high, max(clip_low, val))
    return math.nan


def retest_depth(
    close: float, ema_fast: float, atr: float,
    *, clip_low: float = 0.0, clip_high: float = 1.0,
) -> float:
    """
    Retest depth: clip(|close - ema_fast| / (atr * close), clip_low, clip_high), 0.0 when
    ATR/close unavailable.

    Canonical: feature_pipeline.py:969-978. The pipeline additionally gates this on
    `retest_flag == 1` (a stateful condition); this function is the MATH when the retest is active.

    `clip_low`/`clip_high` default to `feature_pipeline.retest_depth_clip_low`/
    `retest_depth_clip_high`'s DEFAULT VALUES (0.0/1.0) — see `disp_strength`'s docstring for why.
    """
    if atr > 0 and close > 0:
        val = abs(close - ema_fast) / (atr * close)
        return min(clip_high, max(clip_low, val))
    return 0.0


def ema_spread(ema_fast: float, ema_slow: float, atr: float) -> float:
    """EMA spread: (ema_fast - ema_slow) / atr, NaN when ATR unavailable. (feature_pipeline.py:869-873)"""
    if atr > 0:
        return (ema_fast - ema_slow) / atr
    return math.nan


def momentum_score(close_delta: float, atr: float) -> float:
    """
    Momentum score: close_delta / atr, NaN when ATR unavailable. (feature_pipeline.py:875-879)

    `close_delta` is the one-bar price change (close.diff()).
    """
    if atr > 0:
        return close_delta / atr
    return math.nan


# ── FM-030 / FM-031 — corrected (scale-invariant) siblings of FM-022 / FM-023 ──────────────
# The legacy pair above divides an ABSOLUTE-price numerator by the close-relative `atr`
# (atr_14_raw/close), so the emitted quantity scales linearly with price level:
#   legacy == corrected * close.
# The pair below reconstructs absolute-price ATR (`atr * close`), matching the discipline
# already used by disp_strength / retest_depth / volatility_ratio in this same module.
#
# ADDITIVE — the legacy functions above are NOT modified. Selection is config-gated by
# `feature_pipeline.normalization_basis` ("atr_relative" = legacy default, "atr_absolute" =
# these). Ontology entries stay `active: false`; this grants no production authority (§6.5).
# Evidence for why the correction matters on the DECISION surface (not merely the
# representation): F-061.


def ema_spread_atr(ema_fast: float, ema_slow: float, atr: float, close: float) -> float:
    """
    FM-030 — scale-invariant correction of FM-022 `ema_spread`.

    (ema_fast - ema_slow) / (atr * close); NaN when ATR/close unavailable (mirrors FM-022's
    NaN discipline exactly, so warm-up rows are dropped identically by finalize()).
    """
    if atr > 0 and close > 0:
        return (ema_fast - ema_slow) / (atr * close)
    return math.nan


def momentum_score_atr(close_delta: float, atr: float, close: float) -> float:
    """
    FM-031 — scale-invariant correction of FM-023 `momentum_score`.

    close_delta / (atr * close); NaN when ATR/close unavailable. `close_delta` is the one-bar
    price change (close.diff()), as in FM-023.
    """
    if atr > 0 and close > 0:
        return close_delta / (atr * close)
    return math.nan


def volatility_ratio(high: float, low: float, atr: float, close: float) -> float:
    """
    Volatility ratio: (high - low) / (atr * close), 1.0 (neutral) when ATR/close unavailable.

    Canonical: feature_pipeline.py:821-825. Fallback is 1.0 (NOT NaN/0.0) — mirror exactly.
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
    feature_pipeline.py:1017-1043. The registry owns this DISTANCE MATH; the pipeline owns which
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


def disp_strength_atr_rescale(disp_strength: float, atr: float) -> float:
    """
    FM-029 (GD-004 closure): the scoring-engine breakout displacement input — the FM-020
    disp_strength feature rescaled by the close-relative ATR; 0.0 when ATR unavailable.

    Canonical: scoring_engine.py:31 (`move/atr`, sole caller crt_engine.py:23 passes the FM-020
    feature as `move`). A THIRD identity, distinct from FM-020 body/(atr·close) and FM-028
    candle_range/atr. The suspected call-site mis-wire (raw move plausibly intended) is tracked
    as FU-CRT-MOVE-MISWIRE; this function freezes the AS-WIRED math, byte-identical.
    """
    if atr > 0:
        return disp_strength / atr
    return 0.0


def liquidity_pressure_score(
    distance: float,
    *, decay_coeff: float = -0.5, nan_sentinel: float = 10.0,
) -> float:
    """
    Liquidity pressure: clip(exp(decay_coeff * distance), 0, 1); a NaN distance is treated as
    nan_sentinel (the pipeline's fillna sentinel -> exp(-0.5*10.0) ~= 0.0067 at the defaults).
    (feature_pipeline.py:1049-1054)

    `decay_coeff`/`nan_sentinel` default to `feature_pipeline.liquidity_decay_coeff`/
    `liquidity_nan_sentinel`'s DEFAULT VALUES (-0.5/10.0) — see `disp_strength`'s docstring for
    why this matters off-default.
    """
    d = nan_sentinel if distance != distance else distance   # != self is True only for NaN
    val = math.exp(decay_coeff * d)
    return min(1.0, max(0.0, val))


def candles_since_retest_state(current_candle_index: float, retest_candle_index: float) -> float:
    """
    FM-070 — CRT engine's live bars-since-the-RETEST-CANDLE count. Registered 2026-07-31 to
    resolve the FM-065 name collision: this is a DISTINCT quantity from FM-065
    `candles_since_retest` (the pipeline's bars-since-SWEEP canonical vector column), despite
    historically sharing the bare name `candles_since_retest` in config_layer/crt_engine_v2.py's
    approve() / approve_with_soft_conf().

    Verbatim transcription of the pre-existing inline expression — no guard, since none existed
    at the call site (current_candle_index >= retest_candle_index always holds by construction:
    the retest index is set from a bar the engine has already processed).
    """
    return float(current_candle_index - retest_candle_index)
