"""
causal_structure.py — FC1-A delayed-confirmed structure publication helpers.

Batch authority: ``FeaturePipeline.compute_structure_liquidity`` (production
columns bind to causal-confirmed swings). Online form used by ``FeatureStore``
so live publishes the same semantics: bar ``t`` uses only information through
``t`` (pivot confirmation latency ``k=SWING_WINDOW``).

No body/range/wick geometry. Liquidity distance/pressure route through resolve_fm
(Phase-3c: FM-025 / FM-026 → derived_math identities).
"""
from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np

from features.fm_resolve import bind_phase3c_causal_structure_callables

# Phase-3c: FM-025 / FM-026 bound once at import (identity == derived_math callables).
_FM_CAUSAL: dict = bind_phase3c_causal_structure_callables()

# PHASE B (2026-07-19): the module-level `from features.feature_pipeline import SWING_WINDOW` was
# REMOVED. That name is now config-derived (PEP 562), so importing it here would force a config
# load at *this module's* import time. `k=None` instead means "resolve from config at call time"
# — same resulting value, no import-time coupling, and an explicit k still wins.
#
# T-7 (2026-07-19): `double_sweep_window` follows the identical `None`-means-config contract. It
# previously defaulted to a literal 5, so the live FeatureStore (which passes no window) silently
# ignored `feature_pipeline.double_sweep_window` while the batch pipeline honored it — a latent
# batch/live split-brain that only surfaced once the config value moved off 5.


def _resolve_k(k: int | None) -> int:
    """Swing half-window: explicit arg wins, else the single config source of truth."""
    if k is not None:
        return int(k)
    from features.feature_pipeline import resolve_swing_window
    return resolve_swing_window()


def _resolve_double_sweep_window(w: int | None) -> int:
    """Double-sweep lookback: explicit arg wins, else the single config source of truth.

    Lives here (not at each call site) so batch and live cannot resolve it differently. Uses the
    same deferred function-local import as `_resolve_k` to avoid a module-level
    ``features -> config_layer`` edge.
    """
    if w is not None:
        return int(w)
    from features.feature_pipeline import resolve_double_sweep_window
    return resolve_double_sweep_window()


def _centered_flags(high: np.ndarray, low: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Centered pivot flags (may use future relative to each index — batch definition)."""
    n = len(high)
    w = 2 * k + 1
    sh = np.zeros(n, dtype=np.int8)
    sl = np.zeros(n, dtype=np.int8)
    for j in range(k, n - k):
        window_h = high[j - k : j + k + 1]
        window_l = low[j - k : j + k + 1]
        if len(window_h) < w:
            continue
        if high[j] == window_h.max():
            sh[j] = 1
        if low[j] == window_l.min():
            sl[j] = 1
    return sh, sl


def causal_structure_series(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray,
    *,
    k: int | None = None,
    double_sweep_window: int | None = None,
) -> Dict[str, np.ndarray]:
    """
    Full-series causal structure matching FeaturePipeline production binding.

    Used for parity tests and online FeatureStore (call with history, take last row).

    `k=None` / `double_sweep_window=None` resolve from config (single source of truth); pass an
    explicit value to override.
    """
    k = _resolve_k(k)
    double_sweep_window = _resolve_double_sweep_window(double_sweep_window)
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    atr = np.asarray(atr, dtype=float)
    n = len(high)
    if not (len(low) == len(close) == len(atr) == n):
        raise ValueError("causal_structure_series: length mismatch")

    sh_c, sl_c = _centered_flags(high, low, k)

    # causal flags = centered shifted by k
    sh = np.zeros(n, dtype=np.int8)
    sl = np.zeros(n, dtype=np.int8)
    if n > k:
        sh[k:] = sh_c[: n - k]
        sl[k:] = sl_c[: n - k]

    # last prices: ffill high/low at centered pivots, then shift k
    last_h_c = np.full(n, np.nan)
    last_l_c = np.full(n, np.nan)
    cur_h = np.nan
    cur_l = np.nan
    for j in range(n):
        if sh_c[j]:
            cur_h = high[j]
        if sl_c[j]:
            cur_l = low[j]
        last_h_c[j] = cur_h
        last_l_c[j] = cur_l

    last_h = np.full(n, np.nan)
    last_l = np.full(n, np.nan)
    if n > k:
        last_h[k:] = last_h_c[: n - k]
        last_l[k:] = last_l_c[: n - k]

    ref_h = np.roll(last_h, 1)
    ref_l = np.roll(last_l, 1)
    ref_h[0] = np.nan
    ref_l[0] = np.nan

    # Match feature_pipeline: comparisons with NaN refs are False
    higher_high = np.where(~np.isnan(ref_h) & (high > ref_h), 1, 0).astype(np.int8)
    lower_low = np.where(~np.isnan(ref_l) & (low < ref_l), 1, 0).astype(np.int8)

    # break_of_structure: np.where(close > ref_high, 1, np.where(close < ref_low, -1, 0))
    bos = np.zeros(n, dtype=np.int8)
    for i in range(n):
        if not np.isnan(ref_h[i]) and close[i] > ref_h[i]:
            bos[i] = 1
        elif not np.isnan(ref_l[i]) and close[i] < ref_l[i]:
            bos[i] = -1

    sweep = np.zeros(n, dtype=np.int8)
    for i in range(n):
        if not np.isnan(ref_h[i]) and high[i] > ref_h[i] and close[i] <= ref_h[i]:
            sweep[i] = 1
        elif not np.isnan(ref_l[i]) and low[i] < ref_l[i] and close[i] >= ref_l[i]:
            sweep[i] = -1

    sweep_detected = (sweep != 0).astype(np.int8)

    double_sweep = np.zeros(n, dtype=np.int8)
    for i in range(n):
        lo = max(0, i - double_sweep_window + 1)
        window = sweep[lo : i + 1]
        if (window > 0).any() and (window < 0).any():
            double_sweep[i] = 1

    # BOS level ffill
    bos_level = np.full(n, np.nan)
    for i in range(n):
        if bos[i] == 1 and not np.isnan(ref_h[i]):
            bos_level[i] = ref_h[i]
        elif bos[i] == -1 and not np.isnan(ref_l[i]):
            bos_level[i] = ref_l[i]
        elif i > 0:
            bos_level[i] = bos_level[i - 1]

    liq_dist = np.full(n, 10.0, dtype=np.float64)
    liq_press = np.full(n, 0.0, dtype=np.float64)
    for i in range(n):
        levels = []
        for v in (ref_h[i], ref_l[i], bos_level[i]):
            if v == v:
                levels.append(float(v))
        d = float(_FM_CAUSAL["FM-025"](float(close[i]), float(atr[i]), *levels))
        if d != d:
            d = 10.0
        liq_dist[i] = d
        liq_press[i] = float(_FM_CAUSAL["FM-026"](d))

    return {
        "swing_high": sh.astype(np.float64),
        "swing_low": sl.astype(np.float64),
        "higher_high": higher_high.astype(np.float64),
        "lower_low": lower_low.astype(np.float64),
        "break_of_structure": bos.astype(np.float64),
        "liquidity_sweep": sweep.astype(np.float64),
        "sweep_detected": sweep_detected.astype(np.float64),
        "double_sweep": double_sweep.astype(np.float64),
        "liquidity_distance": liq_dist,
        "liquidity_pressure_score": liq_press,
        # Internal refs (not CANONICAL_FEATURES — FeatureStore must not inject these)
        "_last_swing_high_price": np.where(np.isnan(last_h), 0.0, last_h),
        "_last_swing_low_price": np.where(np.isnan(last_l), 0.0, last_l),
    }


def causal_structure_at_bar(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    atrs: Sequence[float],
    *,
    k: int | None = None,
    liquidity_sweep_history: Sequence[int] | None = None,
    double_sweep_window: int | None = None,
) -> Dict[str, float]:
    """Structure features for the last bar of the provided history.

    `k=None` / `double_sweep_window=None` resolve from config; pass an explicit value to override.
    """
    # Resolve once so the series computation and the history-window slice below cannot disagree.
    double_sweep_window = _resolve_double_sweep_window(double_sweep_window)
    series = causal_structure_series(
        np.asarray(highs, dtype=float),
        np.asarray(lows, dtype=float),
        np.asarray(closes, dtype=float),
        np.asarray(atrs, dtype=float),
        k=k,
        double_sweep_window=double_sweep_window,
    )
    # Prefer store's double_sweep history window if provided (matches FeatureStore maxlen)
    if liquidity_sweep_history is not None:
        hist = list(liquidity_sweep_history) + [int(series["liquidity_sweep"][-1])]
        hist = hist[-double_sweep_window:]
        has_pos = any(v > 0 for v in hist)
        has_neg = any(v < 0 for v in hist)
        series["double_sweep"][-1] = 1.0 if (has_pos and has_neg) else 0.0

    return {name: float(arr[-1]) for name, arr in series.items()}
