"""process_characterization.py — statistical fingerprint of a raw OHLCV series.

MEASURE-ONLY research module, fully decoupled from the live spine (no config, no
governance, no decision path). Tests the thesis "volatility has memory; direction
mostly does not" by characterising the *process* itself rather than any entry/exit
edge — which is why it does not implement the research-layer `Hypothesis` protocol.

Three measurements, all whole-series statistics computed offline (no lookahead leaks
into any live feature because nothing here feeds the spine):

  A. Autocorrelation (ACF) of log-returns, |log-returns| and the ATR series.
  B. Rescaled-Range (R/S) Hurst exponent + Lo-MacKinlay variance ratio, per series.
  C. 6-state Markov transition matrix over {Compression/Normal/Expansion}x{Up/Down},
     volatility axis split at data-driven terciles of ATR.

Pure & deterministic: numpy + stdlib only (no scipy), sorted/rounded outputs, no
wall-clock — mirroring the determinism discipline of `research.runner` /
`research.provenance`. The thin CLI in `scripts/analysis/process_characterizer.py`
owns all I/O; this module owns only the math.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from research.indicators import atr  # reuse the research-layer ATR (identical TR def)

# Canonical state order: volatility {C,N,E} x direction {U,D}. Fixed so the
# transition matrix is diff-stable regardless of which states the data exercises.
STATE_LABELS: list[str] = ["CU", "CD", "NU", "ND", "EU", "ED"]

_LOW_PCT = 100.0 / 3.0   # 33.33rd percentile -> Compression / Normal cut
_HIGH_PCT = 200.0 / 3.0  # 66.67th percentile -> Normal / Expansion cut


# ─────────────────────────────────────────────────────────────────
# A. SERIES BUILDERS
# ─────────────────────────────────────────────────────────────────

def log_returns(closes: Sequence[float]) -> np.ndarray:
    """r_t = ln(close_t / close_{t-1}); length len(closes)-1. Empty if <2 closes."""
    c = np.asarray(closes, dtype=float)
    if c.size < 2:
        return np.empty(0, dtype=float)
    return np.log(c[1:] / c[:-1])


def atr_series(candles: Sequence, period: int = 14) -> np.ndarray:
    """Trailing ATR at each bar i (i>=1), aligned 1:1 with `log_returns`.

    Reuses `research.indicators.atr` on a capped trailing window so the true-range
    definition is byte-identical to what hypotheses/controls already use.
    """
    bars = list(candles)
    n = len(bars)
    if n < 2:
        return np.empty(0, dtype=float)
    return np.asarray(
        [atr(bars[max(0, i - period): i + 1], period) for i in range(1, n)],
        dtype=float,
    )


# ─────────────────────────────────────────────────────────────────
# B. AUTOCORRELATION / HURST / VARIANCE RATIO
# ─────────────────────────────────────────────────────────────────

def autocorrelation(series: Sequence[float], max_lag: int) -> list[float]:
    """Biased sample ACF rho_k for k in [1, max_lag] (clamped to len-1)."""
    x = np.asarray(series, dtype=float)
    n = x.size
    if n < 2 or max_lag < 1:
        return []
    max_lag = min(max_lag, n - 1)
    x = x - x.mean()
    denom = float(np.dot(x, x))
    if denom == 0.0:
        return [0.0] * max_lag
    return [float(np.dot(x[:-k], x[k:]) / denom) for k in range(1, max_lag + 1)]


def hurst_rs(series: Sequence[float], min_window: int = 8) -> float:
    """Rescaled-Range (R/S) Hurst exponent. ~0.5 random walk, >0.5 persistent,
    <0.5 anti-persistent. NaN if the series is too short to fit a slope."""
    x = np.asarray(series, dtype=float)
    n = x.size
    if n < min_window * 2:
        return float("nan")
    max_window = n // 2
    # log-spaced integer window sizes (deterministic, unique, ascending)
    raw = np.logspace(math.log10(min_window), math.log10(max_window), num=12)
    windows = sorted({int(round(w)) for w in raw if min_window <= w <= max_window})
    logs_n: list[float] = []
    logs_rs: list[float] = []
    for w in windows:
        chunks = n // w
        if chunks < 1:
            continue
        rs_vals: list[float] = []
        for j in range(chunks):
            chunk = x[j * w:(j + 1) * w]
            dev = chunk - chunk.mean()
            cum = np.cumsum(dev)
            rng = float(cum.max() - cum.min())
            std = float(chunk.std())  # population std
            if std > 0.0 and rng > 0.0:
                rs_vals.append(rng / std)
        if rs_vals:
            logs_n.append(math.log(w))
            logs_rs.append(math.log(float(np.mean(rs_vals))))
    if len(logs_n) < 2:
        return float("nan")
    slope = float(np.polyfit(logs_n, logs_rs, 1)[0])
    return slope


def variance_ratio(returns: Sequence[float], q: int) -> float:
    """Lo-MacKinlay variance ratio VR(q) on a returns series (overlapping q-sums).
    VR == 1 under a random walk; >1 trending, <1 mean-reverting. NaN if too short."""
    r = np.asarray(returns, dtype=float)
    T = r.size
    if q < 2 or T < q + 1:
        return float("nan")
    mu = r.mean()
    var1 = float(np.sum((r - mu) ** 2) / (T - 1))
    if var1 == 0.0:
        return float("nan")
    cs = np.cumsum(r)
    q_sums = cs[q - 1:] - np.concatenate(([0.0], cs[:-q]))  # overlapping, len T-q+1
    m = q_sums.size
    varq = float(np.sum((q_sums - q * mu) ** 2) / (m - 1))
    return (varq / q) / var1


# ─────────────────────────────────────────────────────────────────
# C. STATE DIGITISATION + MARKOV TRANSITION MATRIX
# ─────────────────────────────────────────────────────────────────

def digitize_states(
    returns: Sequence[float], atr_vals: Sequence[float]
) -> tuple[list[str], float, float]:
    """Map each aligned (return, atr) pair to a 6-state label. Volatility axis is
    split at the data's own 33.3rd/66.7th ATR percentiles (reported). Returns
    (states, vol_cut_low, vol_cut_high)."""
    r = np.asarray(returns, dtype=float)
    a = np.asarray(atr_vals, dtype=float)
    if r.size == 0 or r.size != a.size:
        return [], float("nan"), float("nan")
    lo = float(np.percentile(a, _LOW_PCT))
    hi = float(np.percentile(a, _HIGH_PCT))
    states: list[str] = []
    for ret, av in zip(r, a):
        vol = "C" if av <= lo else ("N" if av <= hi else "E")
        direction = "U" if ret >= 0.0 else "D"
        states.append(vol + direction)
    return states, lo, hi


def transition_matrix(
    states: Sequence[str], labels: Sequence[str] = STATE_LABELS
) -> tuple[list[list[float]], list[list[int]], list[str]]:
    """Row-normalised P_ij and raw counts N_ij over consecutive states. Rows with no
    occurrences are all-zero. Returns (matrix, counts, labels)."""
    labels = list(labels)
    idx = {lab: i for i, lab in enumerate(labels)}
    k = len(labels)
    counts = [[0] * k for _ in range(k)]
    for a, b in zip(states[:-1], states[1:]):
        if a in idx and b in idx:
            counts[idx[a]][idx[b]] += 1
    matrix: list[list[float]] = []
    for row in counts:
        total = sum(row)
        matrix.append([c / total for c in row] if total else [0.0] * k)
    return matrix, counts, labels


def _row_entropy(row: Sequence[float], k: int) -> float:
    """Normalised Shannon entropy of a probability row in [0,1]. 1.0 == uniform
    ('coin-flip' exit); 0.0 == deterministic. Empty/zero rows -> NaN."""
    probs = [p for p in row if p > 0.0]
    if not probs or k < 2:
        return float("nan")
    h = -sum(p * math.log(p) for p in probs)
    return h / math.log(k)


# ─────────────────────────────────────────────────────────────────
# MANIFEST + ORCHESTRATION
# ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProcessManifest:
    """Deterministic process fingerprint. No wall-clock / run-id fields (those live
    in the CLI's separate run-manifest, per the research-layer split)."""
    instrument: str
    n_candles: int
    n_returns: int
    atr_period: int
    max_lag: int
    vr_qs: list[int]
    rounding: int
    # A. autocorrelation
    acf_lags: list[int]
    acf_returns: list[float]
    acf_abs_returns: list[float]
    acf_atr: list[float]
    # B. hurst + variance ratio
    hurst_returns: float
    hurst_abs_returns: float
    hurst_atr: float
    variance_ratio_returns: dict[str, float]
    # C. markov
    state_labels: list[str]
    vol_cut_low: float
    vol_cut_high: float
    state_counts: dict[str, int]
    transition_counts: list[list[int]]
    transition_matrix: list[list[float]]
    row_entropy: dict[str, float]
    mean_exit_entropy: float
    # derived advisory summary (raw numbers above remain authoritative)
    thesis_flags: dict[str, bool]

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _round(x: float, nd: int) -> float:
    return round(x, nd) if isinstance(x, float) and not math.isnan(x) else x


def characterize(
    candles: Sequence,
    *,
    instrument: str = "UNKNOWN",
    atr_period: int = 14,
    max_lag: int = 50,
    vr_qs: Sequence[int] = (2, 4, 8, 16),
    round_to: int = 6,
) -> ProcessManifest:
    """Run measurements A/B/C over an ordered candle sequence and assemble a
    deterministic ProcessManifest."""
    bars = list(candles)
    n = len(bars)
    closes = [b.close for b in bars]
    rets = log_returns(closes)
    abs_rets = np.abs(rets)
    atrs = atr_series(bars, atr_period)

    acf_lags = list(range(1, min(max_lag, max(rets.size - 1, 0)) + 1))
    acf_r = autocorrelation(rets, max_lag)
    acf_ar = autocorrelation(abs_rets, max_lag)
    acf_at = autocorrelation(atrs, max_lag)

    h_r = hurst_rs(rets)
    h_ar = hurst_rs(abs_rets)
    h_at = hurst_rs(atrs)

    vr = {str(q): _round(variance_ratio(rets, q), round_to) for q in vr_qs}

    states, lo, hi = digitize_states(rets, atrs)
    matrix, counts, labels = transition_matrix(states)
    state_counts = {lab: states.count(lab) for lab in labels}
    k = len(labels)
    entropy = {labels[i]: _round(_row_entropy(matrix[i], k), round_to) for i in range(k)}
    valid_ent = [v for v in entropy.values() if isinstance(v, float) and not math.isnan(v)]
    mean_ent = float(np.mean(valid_ent)) if valid_ent else float("nan")

    # Advisory thesis flags — conservative, derived from the raw stats above.
    flags = {
        "returns_near_random_walk": bool(not math.isnan(h_r) and abs(h_r - 0.5) < 0.05),
        "volatility_persistent": bool(not math.isnan(h_at) and h_at > 0.55),
        "volatility_memory_exceeds_direction": bool(
            not math.isnan(h_at) and not math.isnan(h_r) and (h_at - h_r) > 0.10
        ),
        "direction_near_coinflip": bool(not math.isnan(mean_ent) and mean_ent > 0.95),
    }

    return ProcessManifest(
        instrument=instrument,
        n_candles=n,
        n_returns=int(rets.size),
        atr_period=atr_period,
        max_lag=max_lag,
        vr_qs=list(vr_qs),
        rounding=round_to,
        acf_lags=acf_lags,
        acf_returns=[_round(v, round_to) for v in acf_r],
        acf_abs_returns=[_round(v, round_to) for v in acf_ar],
        acf_atr=[_round(v, round_to) for v in acf_at],
        hurst_returns=_round(h_r, round_to),
        hurst_abs_returns=_round(h_ar, round_to),
        hurst_atr=_round(h_at, round_to),
        variance_ratio_returns=vr,
        state_labels=labels,
        vol_cut_low=_round(lo, round_to),
        vol_cut_high=_round(hi, round_to),
        state_counts=state_counts,
        transition_counts=counts,
        transition_matrix=[[_round(p, round_to) for p in row] for row in matrix],
        row_entropy=entropy,
        mean_exit_entropy=_round(mean_ent, round_to),
        thesis_flags=flags,
    )
