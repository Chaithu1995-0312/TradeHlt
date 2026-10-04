"""
Candle-pattern observations — the registered authority for FM-103..FM-119 (schema v8.0).

OBSERVATIONS, NOT SIGNALS. Each function says what a bar's geometry IS (a long lower wick at a
fresh 5-bar low, a body that engulfs the previous body, ...). Whether that is bullish, bearish or
noise is decided downstream by context (CRT state, HTF bias, session) and by outcome measurement.
Thresholds are research hypotheses carried in config (`feature_pipeline.candle_patterns`), never
literals here (CLAUDE.md §6.5).

Layering (the linear flow):
    OHLC -> candle_math (body / range / wicks, immutable identities)
         -> wick_ratios (B̂, Û, D̂ — shares of the range, sum to 1)
         -> pattern observations (this module)
         -> FeaturePipeline.compute_candle_patterns (vector slots 54..70, plus morning_star at 71)
         -> consumers (strategy feature dicts, context/state layers, research)

Definitions (corrected spec adopted 2026-10-08, CH-candle-pattern-observations-v8):
  * ATR is the canonical one: FM-074 `atr_absolute` (SMA of true range, PRICE units). No second
    ATR definition. The close-relative FM-041 `atr` must never be compared with a dollar range.
  * Size gate G = range > 0 AND range >= k * ATR_abs. Applied to single-bar patterns and the
    continuous intensities only — not to engulfing / inside bar (their evidence is the sequence).
  * Comparisons are INCLUSIVE where the spec says <= / >=.
  * Zero-range bar: shares are 0, gate false (no epsilon repair; bad OHLC is rejected upstream by
    data_ingestion.ohlcv_schema).
  * Prior swing extremes EXCLUDE the current bar (bars i-k .. i-1); undefined until k prior bars.
  * Two-bar patterns require the previous row to be the immediately preceding bar (`contiguous`);
    across a session/weekend gap they are 0 and compression_ratio is the neutral 1.0.

Scalar functions are the per-bar identities (registered in features.registry); `compute_all` is
the vectorized mirror used by the pipeline, bound to the scalars by tests/test_candle_patterns.py.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from features import candle_math as _cm

_PARAM_KEYS = (
    "size_gate_atr_k",
    "swing_lookback",
    "pin_wick_min",
    "pin_body_max",
    "pin_opposite_wick_max",
    "probe_wick_body_multiple",
    "probe_opposite_wick_max",
    "doji_body_max",
    "doji_wick_asymmetry_max",
    "doji_extreme_body_max",
    "doji_extreme_wick_min",
    "engulfing_strength_cap",
    "compression_ratio_cap",
    "morning_star_body_min",
    "morning_star_mid_max",
)


@dataclass(frozen=True)
class CandlePatternParams:
    size_gate_atr_k: float
    swing_lookback: int
    pin_wick_min: float
    pin_body_max: float
    pin_opposite_wick_max: float
    probe_wick_body_multiple: float
    probe_opposite_wick_max: float
    doji_body_max: float
    doji_wick_asymmetry_max: float
    doji_extreme_body_max: float
    doji_extreme_wick_min: float
    engulfing_strength_cap: float
    compression_ratio_cap: float
    morning_star_body_min: float
    morning_star_mid_max: float

    @classmethod
    def from_cfg(cls, block: dict) -> "CandlePatternParams":
        """Strict: every key of `feature_pipeline.candle_patterns` is required (no silent default)."""
        missing = [k for k in _PARAM_KEYS if k not in block]
        if missing:
            raise KeyError(f"Required config key(s) feature_pipeline.candle_patterns.{missing} missing")
        vals = {k: block[k] for k in _PARAM_KEYS}
        vals["swing_lookback"] = int(vals["swing_lookback"])
        return cls(**vals)


# ── scalar identities ────────────────────────────────────────────────────────────────────────

def wick_ratios(open_: float, high: float, low: float, close: float) -> tuple[float, float, float]:
    """(body, upper wick, lower wick) as shares of the bar range; (0,0,0) on a zero-range bar."""
    rng = _cm.candle_range(high, low)
    if rng <= 0:
        return 0.0, 0.0, 0.0
    return (_cm.body_size(open_, close) / rng,
            _cm.upper_wick(open_, high, close) / rng,
            _cm.lower_wick(open_, low, close) / rng)


def upper_wick_ratio(open_: float, high: float, low: float, close: float) -> float:
    return wick_ratios(open_, high, low, close)[1]


def lower_wick_ratio(open_: float, high: float, low: float, close: float) -> float:
    return wick_ratios(open_, high, low, close)[2]


def size_gate(high: float, low: float, atr_absolute: float, p: CandlePatternParams) -> bool:
    """Material-range gate: range > 0 and range >= k * ATR (price units). False while ATR is undefined."""
    rng = _cm.candle_range(high, low)
    if not (atr_absolute == atr_absolute) or rng <= 0:   # NaN-safe
        return False
    return rng >= p.size_gate_atr_k * atr_absolute


def pin_lower(open_, high, low, close, atr_absolute, p: CandlePatternParams) -> bool:
    b, u, d = wick_ratios(open_, high, low, close)
    return (d >= p.pin_wick_min and b <= p.pin_body_max and u <= p.pin_opposite_wick_max
            and size_gate(high, low, atr_absolute, p))


def pin_upper(open_, high, low, close, atr_absolute, p: CandlePatternParams) -> bool:
    b, u, d = wick_ratios(open_, high, low, close)
    return (u >= p.pin_wick_min and b <= p.pin_body_max and d <= p.pin_opposite_wick_max
            and size_gate(high, low, atr_absolute, p))


def hammer(open_, high, low, close, prior_low_min, atr_absolute, p: CandlePatternParams) -> bool:
    """Lower-wick probe at/below the prior `swing_lookback`-bar low (current bar excluded)."""
    if not (prior_low_min == prior_low_min):
        return False
    _b, u, _d = wick_ratios(open_, high, low, close)
    return (_cm.lower_wick(open_, low, close) >= p.probe_wick_body_multiple * _cm.body_size(open_, close)
            and u <= p.probe_opposite_wick_max and low <= prior_low_min
            and size_gate(high, low, atr_absolute, p))


def shooting_star(open_, high, low, close, prior_high_max, atr_absolute, p: CandlePatternParams) -> bool:
    """Upper-wick probe at/above the prior `swing_lookback`-bar high (current bar excluded)."""
    if not (prior_high_max == prior_high_max):
        return False
    _b, _u, d = wick_ratios(open_, high, low, close)
    return (_cm.upper_wick(open_, high, close) >= p.probe_wick_body_multiple * _cm.body_size(open_, close)
            and d <= p.probe_opposite_wick_max and high >= prior_high_max
            and size_gate(high, low, atr_absolute, p))


def doji_material(open_, high, low, close, atr_absolute, p: CandlePatternParams) -> bool:
    b, u, d = wick_ratios(open_, high, low, close)
    return (b <= p.doji_body_max and abs(u - d) <= p.doji_wick_asymmetry_max
            and size_gate(high, low, atr_absolute, p))


def dragonfly_doji(open_, high, low, close, atr_absolute, p: CandlePatternParams) -> bool:
    b, _u, d = wick_ratios(open_, high, low, close)
    return (b <= p.doji_extreme_body_max and d >= p.doji_extreme_wick_min
            and size_gate(high, low, atr_absolute, p))


def gravestone_doji(open_, high, low, close, atr_absolute, p: CandlePatternParams) -> bool:
    b, u, _d = wick_ratios(open_, high, low, close)
    return (b <= p.doji_extreme_body_max and u >= p.doji_extreme_wick_min
            and size_gate(high, low, atr_absolute, p))


def engulfing_bull(open_, close, prev_open, prev_close, contiguous: bool) -> bool:
    """Bearish previous body fully covered (inclusive) by a larger bullish body."""
    return bool(contiguous and prev_close < prev_open and close > open_
                and open_ <= prev_close and close >= prev_open
                and _cm.body_size(open_, close) > _cm.body_size(prev_open, prev_close))


def engulfing_bear(open_, close, prev_open, prev_close, contiguous: bool) -> bool:
    """Bullish previous body fully covered (inclusive) by a larger bearish body."""
    return bool(contiguous and prev_close > prev_open and close < open_
                and open_ >= prev_close and close <= prev_open
                and _cm.body_size(open_, close) > _cm.body_size(prev_open, prev_close))


def inside_bar(high, low, prev_high, prev_low, contiguous: bool) -> bool:
    """Inclusive containment of the bar's range inside the previous bar's range."""
    return bool(contiguous and high <= prev_high and low >= prev_low)


def compression_ratio(high, low, prev_high, prev_low, contiguous: bool, p: CandlePatternParams) -> float:
    """range / previous range, clipped to [0, cap]; neutral 1.0 when undefined or across a gap."""
    prev_rng = _cm.candle_range(prev_high, prev_low)
    if not contiguous or not (prev_rng > 0):
        return 1.0
    return min(max(_cm.candle_range(high, low) / prev_rng, 0.0), p.compression_ratio_cap)


def rejection_intensity_signed(open_, high, low, close, atr_absolute, p: CandlePatternParams) -> float:
    """Lower-wick share minus upper-wick share in [-1, +1]; 0 on non-material bars.
    Positive = lower-wick rejection geometry, negative = upper-wick (geometry, not direction)."""
    if not size_gate(high, low, atr_absolute, p):
        return 0.0
    _b, u, d = wick_ratios(open_, high, low, close)
    return min(max(d - u, -1.0), 1.0)


def rejection_intensity_lower(open_, high, low, close, atr_absolute, p: CandlePatternParams) -> float:
    """Excess of lower-wick share over body share, in [0, 1]; 0 on non-material bars."""
    if not size_gate(high, low, atr_absolute, p):
        return 0.0
    b, _u, d = wick_ratios(open_, high, low, close)
    return min(max(d - b, 0.0), 1.0)


def rejection_intensity_upper(open_, high, low, close, atr_absolute, p: CandlePatternParams) -> float:
    """Excess of upper-wick share over body share, in [0, 1]; 0 on non-material bars."""
    if not size_gate(high, low, atr_absolute, p):
        return 0.0
    b, u, _d = wick_ratios(open_, high, low, close)
    return min(max(u - b, 0.0), 1.0)


def morning_star(
    open0, high0, low0, close0,
    open1, high1, low1, close1,
    open2, high2, low2, close2,
    contiguous_01: bool, contiguous_12: bool, p: CandlePatternParams,
) -> bool:
    """Three contiguous bars: big bearish, small middle, big bullish. Known on the third bar.

    Shape only. No ATR gate and no trend argument. The middle bar's color is free.
    Thresholds are inclusive. A zero-range middle has body_ratio 0, so it counts as small.
    A zero-range third fails the big-body test. Not an evening star.
    """
    if not (contiguous_01 and contiguous_12):
        return False
    b0 = _cm.body_ratio(open0, high0, low0, close0)
    b1 = _cm.body_ratio(open1, high1, low1, close1)
    b2 = _cm.body_ratio(open2, high2, low2, close2)
    return bool(
        close0 < open0 and b0 >= p.morning_star_body_min
        and b1 <= p.morning_star_mid_max
        and close2 > open2 and b2 >= p.morning_star_body_min
    )


def engulfing_strength(open_, close, prev_open, prev_close, contiguous: bool, p: CandlePatternParams) -> float:
    """Body / previous body on an engulfing bar, capped; 0 otherwise (the previous body is > 0 by
    construction of the pattern, so the ratio is always defined when it fires)."""
    if not (engulfing_bull(open_, close, prev_open, prev_close, contiguous)
            or engulfing_bear(open_, close, prev_open, prev_close, contiguous)):
        return 0.0
    return min(_cm.body_size(open_, close) / _cm.body_size(prev_open, prev_close), p.engulfing_strength_cap)


# ── vectorized mirror (pipeline) ─────────────────────────────────────────────────────────────

#: Output columns in canonical vector order (slots 54..70).
PATTERN_COLUMNS = (
    "upper_wick_ratio", "lower_wick_ratio",
    "pin_lower", "pin_upper", "hammer", "shooting_star",
    "doji_material", "dragonfly_doji", "gravestone_doji",
    "engulfing_bull", "engulfing_bear", "inside_bar", "compression_ratio",
    "rejection_intensity_signed", "rejection_intensity_lower", "engulfing_strength",
    "rejection_intensity_upper",
)


def contiguous_mask(timestamps) -> np.ndarray:
    """True where row i-1 is the immediately preceding bar: timestamp gap == the frame's modal
    positive bar interval. Row 0 (and any frame with < 2 rows) is False."""
    ts = np.asarray(timestamps, dtype="datetime64[ns]").astype(np.int64)
    out = np.zeros(len(ts), dtype=bool)
    if len(ts) < 2:
        return out
    diffs = np.diff(ts)
    pos = diffs[diffs > 0]
    if len(pos) == 0:
        return out
    vals, counts = np.unique(pos, return_counts=True)
    modal = vals[np.argmax(counts)]
    out[1:] = diffs == modal
    return out


def _prev(a: np.ndarray) -> np.ndarray:
    out = np.empty_like(a, dtype=float)
    out[0] = np.nan
    out[1:] = a[:-1]
    return out


def _prior_extreme(a: np.ndarray, k: int, fn) -> np.ndarray:
    """fn (min/max) over bars i-k .. i-1 (current bar excluded); NaN until k prior bars exist."""
    n = len(a)
    out = np.full(n, np.nan)
    if n > k:
        win = np.lib.stride_tricks.sliding_window_view(a, k)   # win[j] = a[j : j+k]
        out[k:] = fn(win[: n - k], axis=1)
    return out


def compute_all(o, h, l, c, atr_absolute, contiguous, p: CandlePatternParams) -> dict:
    """Vectorized mirror of the scalar identities. Inputs are 1-D arrays of equal length;
    returns {column: float32 array} for PATTERN_COLUMNS plus morning_star (flags as 0.0/1.0).
    morning_star is not a member of PATTERN_COLUMNS."""
    o = np.asarray(o, dtype=float)
    h = np.asarray(h, dtype=float)
    l = np.asarray(l, dtype=float)
    c = np.asarray(c, dtype=float)
    atr = np.asarray(atr_absolute, dtype=float)
    contig = np.asarray(contiguous, dtype=bool)

    rng = h - l
    body = np.abs(c - o)
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - l
    pos = rng > 0
    b_hat = np.zeros_like(rng)
    u_hat = np.zeros_like(rng)
    d_hat = np.zeros_like(rng)
    np.divide(body, rng, out=b_hat, where=pos)
    np.divide(upper, rng, out=u_hat, where=pos)
    np.divide(lower, rng, out=d_hat, where=pos)

    with np.errstate(invalid="ignore"):
        gate = pos & ~np.isnan(atr) & (rng >= p.size_gate_atr_k * atr)

    k = p.swing_lookback
    prior_low = _prior_extreme(l, k, np.min)
    prior_high = _prior_extreme(h, k, np.max)

    o1, h1, l1, c1 = _prev(o), _prev(h), _prev(l), _prev(c)
    body1 = np.abs(c1 - o1)
    rng1 = h1 - l1

    with np.errstate(invalid="ignore"):
        pin_lo = (d_hat >= p.pin_wick_min) & (b_hat <= p.pin_body_max) & (u_hat <= p.pin_opposite_wick_max) & gate
        pin_up = (u_hat >= p.pin_wick_min) & (b_hat <= p.pin_body_max) & (d_hat <= p.pin_opposite_wick_max) & gate
        ham = ((lower >= p.probe_wick_body_multiple * body) & (u_hat <= p.probe_opposite_wick_max)
               & ~np.isnan(prior_low) & (l <= prior_low) & gate)
        star = ((upper >= p.probe_wick_body_multiple * body) & (d_hat <= p.probe_opposite_wick_max)
                & ~np.isnan(prior_high) & (h >= prior_high) & gate)
        doji = (b_hat <= p.doji_body_max) & (np.abs(u_hat - d_hat) <= p.doji_wick_asymmetry_max) & gate
        dragon = (b_hat <= p.doji_extreme_body_max) & (d_hat >= p.doji_extreme_wick_min) & gate
        grave = (b_hat <= p.doji_extreme_body_max) & (u_hat >= p.doji_extreme_wick_min) & gate
        eng_bull = contig & (c1 < o1) & (c > o) & (o <= c1) & (c >= o1) & (body > body1)
        eng_bear = contig & (c1 > o1) & (c < o) & (o >= c1) & (c <= o1) & (body > body1)
        inside = contig & (h <= h1) & (l >= l1)

    comp = np.ones_like(rng)
    ok = contig & (rng1 > 0)
    np.divide(rng, rng1, out=comp, where=ok)
    comp = np.where(ok, np.clip(comp, 0.0, p.compression_ratio_cap), 1.0)

    eng = eng_bull | eng_bear
    strength = np.zeros_like(rng)
    np.divide(body, body1, out=strength, where=eng)
    strength = np.where(eng, np.minimum(strength, p.engulfing_strength_cap), 0.0)

    rej_signed = np.where(gate, np.clip(d_hat - u_hat, -1.0, 1.0), 0.0)
    rej_lower = np.where(gate, np.clip(d_hat - b_hat, 0.0, 1.0), 0.0)
    rej_upper = np.where(gate, np.clip(u_hat - b_hat, 0.0, 1.0), 0.0)

    # morning_star: bar i-2 big bearish, bar i-1 small, bar i big bullish, both joins contiguous.
    b_mid = _prev(b_hat)
    b_first = _prev(b_mid)
    o_first = _prev(_prev(o))
    c_first = _prev(_prev(c))
    contig_prev = np.zeros(len(contig), dtype=bool)
    if len(contig) > 1:
        contig_prev[1:] = contig[:-1]
    with np.errstate(invalid="ignore"):
        morning = (
            contig & contig_prev
            & (c_first < o_first) & (b_first >= p.morning_star_body_min)
            & (b_mid <= p.morning_star_mid_max)
            & (c > o) & (b_hat >= p.morning_star_body_min)
        )

    cols = {
        "upper_wick_ratio": u_hat, "lower_wick_ratio": d_hat,
        "pin_lower": pin_lo, "pin_upper": pin_up, "hammer": ham, "shooting_star": star,
        "doji_material": doji, "dragonfly_doji": dragon, "gravestone_doji": grave,
        "engulfing_bull": eng_bull, "engulfing_bear": eng_bear, "inside_bar": inside,
        "compression_ratio": comp,
        "rejection_intensity_signed": rej_signed, "rejection_intensity_lower": rej_lower,
        "engulfing_strength": strength, "rejection_intensity_upper": rej_upper,
        "morning_star": morning,
    }
    return {k2: np.asarray(v, dtype=np.float32) for k2, v in cols.items()}
