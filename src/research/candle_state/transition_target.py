"""transition_target.py — non-directional FORWARD target labelers (Stage-1 only).

Program 4b/4c/4d targets are deliberately NON-DIRECTIONAL — they ask "does *something* happen"
(volatility expands / range expands / the state persists / a regime transition occurs), never
"does price go up or down." That is the whole point: the directional channel is falsified
(F-019…F-027/F-035); these probe a different information channel (F-030's untested TRANSITION
successor).

Each labeler returns `(target, valid)` aligned 1:1 with the input bars:
  * target[t] ∈ {0,1}    — the forward event at bar t (0 where invalid)
  * valid[t]  ∈ {F,T}    — whether bar t has a well-defined forward target

Pure & deterministic: numpy + stdlib. ATR reuses `research.indicators.atr` (identical TR def).
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from research.indicators import atr as _atr


def atr_per_bar(candles: Sequence, period: int = 14) -> np.ndarray:
    """Trailing ATR at each bar (atr over the trailing `period`+1 window). atrs[t]=0 in warmup."""
    bars = list(candles)
    n = len(bars)
    out = np.zeros(n, dtype=float)
    for t in range(1, n):
        out[t] = _atr(bars[max(0, t - period): t + 1], period)
    return out


def _range_per_bar(candles: Sequence) -> np.ndarray:
    return np.asarray([float(b.high) - float(b.low) for b in candles], dtype=float)


# ── 4b — volatility / range expansion ────────────────────────────────────────
def vol_expansion_target(atrs: np.ndarray, *, k: int, theta: float) -> tuple[np.ndarray, np.ndarray]:
    """target[t]=1 iff mean(ATR over t+1..t+k) / ATR[t] > theta (forward vol expansion)."""
    a = np.asarray(atrs, dtype=float)
    n = a.size
    target = np.zeros(n, dtype=np.int64)
    valid = np.zeros(n, dtype=bool)
    for t in range(n - k):
        if a[t] <= 0.0:
            continue
        fwd = a[t + 1: t + 1 + k]
        if fwd.size < k or np.any(fwd <= 0.0):
            continue
        valid[t] = True
        target[t] = 1 if (fwd.mean() / a[t]) > theta else 0
    return target, valid


def range_expansion_target(candles: Sequence, *, k: int, theta: float) -> tuple[np.ndarray, np.ndarray]:
    """target[t]=1 iff mean(range over t+1..t+k) / range[t] > theta (forward range expansion)."""
    r = _range_per_bar(candles)
    n = r.size
    target = np.zeros(n, dtype=np.int64)
    valid = np.zeros(n, dtype=bool)
    for t in range(n - k):
        if r[t] <= 0.0:
            continue
        fwd = r[t + 1: t + 1 + k]
        if fwd.size < k:
            continue
        valid[t] = True
        target[t] = 1 if (fwd.mean() / r[t]) > theta else 0
    return target, valid


# ── 4c — state persistence ───────────────────────────────────────────────────
def persistence_target(cell_labels: Sequence[str], *, k: int) -> tuple[np.ndarray, np.ndarray]:
    """target[t]=1 iff the cell label is unchanged across t+1..t+k (the state persists k bars).

    Non-directional: it asks whether the *conjunction state itself* is sticky, conditioned on
    which state it is (the cell). NA cells are invalid (warmup)."""
    labels = list(cell_labels)
    n = len(labels)
    target = np.zeros(n, dtype=np.int64)
    valid = np.zeros(n, dtype=bool)
    for t in range(n - k):
        cur = labels[t]
        if not cur or cur.endswith("=NA") or "=NA" in cur:
            continue
        valid[t] = True
        target[t] = 1 if all(labels[t + j] == cur for j in range(1, k + 1)) else 0
    return target, valid


# ── 4d — regime transition memory (compression -> expansion) ─────────────────
def regime_transition_target(
    vol_labels: Sequence[str], *, k: int, from_state: str = "COMPRESSION", to_state: str = "EXPANSION",
) -> tuple[np.ndarray, np.ndarray]:
    """Among bars currently in `from_state`, target[t]=1 iff `to_state` occurs within the next k
    bars (a forward regime CHANGE). valid only where current vol == from_state."""
    labels = list(vol_labels)
    n = len(labels)
    target = np.zeros(n, dtype=np.int64)
    valid = np.zeros(n, dtype=bool)
    for t in range(n - k):
        if labels[t] != from_state:
            continue
        valid[t] = True
        target[t] = 1 if any(labels[t + j] == to_state for j in range(1, k + 1)) else 0
    return target, valid
