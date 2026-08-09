"""conditional_entropy_grid.py — Phase B (B1): where, if anywhere, does next-direction
become conditionally predictable?

MEASURE-ONLY, fully spine-free (candle-only proxies — no CRT/sweep/telemetry labels; that
is B2). Generalises `process_diagnostics.direction_conditional_entropy` (vol-band only) to a
configurable partition `session x vol-tercile x momentum-regime`, measured at multiple
horizons, across instruments.

The inferential object is the PARTITION, not the cell (the key statistical discipline):
  * per cell we report H(sign r_{t+h} | cell), n, p_up   -> EXPLANATORY (interpretation)
  * per (instrument, horizon) PARTITION we test the information gain
        IG = H(sign r_{t+h}) - H(sign r_{t+h} | partition)
    against a label-permutation null (shuffle the direction labels, preserving cell
    cardinalities), so adding cells cannot trivially "win"           -> INFERENTIAL (p-value)
The caller (driver) BH-corrects the partition p-values within each family (per-instrument vs
pooled) and only then interprets cells inside significant partitions.

Pure & deterministic: numpy + stdlib, seeded permutations, no wall-clock, no spine import.
Reuses the audited entropy primitive `process_diagnostics._conditional_entropy_bits`, the
research ATR, and the same tercile cuts as `process_characterization`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

import numpy as np

from research.indicators import atr as _atr
from research.process_diagnostics import _conditional_entropy_bits  # audited H(Y|X) in bits


# ── partition labelers (candle-derivable only) ───────────────────────────────
def hour_of(ts) -> int:
    """UTC hour from a Candle timestamp (datetime or ISO string)."""
    if isinstance(ts, datetime):
        return ts.hour
    s = str(ts)
    # "YYYY-MM-DD HH:MM:SS" / ISO "…THH:…"
    sep = "T" if "T" in s else " "
    try:
        return int(s.split(sep)[1][:2])
    except (IndexError, ValueError):
        return 0


def hour_to_session(hour: int, windows: dict) -> str:
    """Map an hour to a session label via half-open [start, end) integer-hour windows.
    `windows` = {name: [start, end]} covering 0..23 exactly once; falls back to 'OFF'."""
    for name, (start, end) in windows.items():
        if start <= hour < end:
            return name
    return "OFF"


def vol_terciles(atr_vals: np.ndarray) -> tuple[float, float]:
    """Data-driven 33.3/66.7 ATR percentiles (same cuts as process_characterization)."""
    a = np.asarray(atr_vals, dtype=float)
    a = a[a > 0.0]
    if a.size == 0:
        return float("nan"), float("nan")
    return float(np.percentile(a, 100.0 / 3.0)), float(np.percentile(a, 200.0 / 3.0))


def vol_label(av: float, lo: float, hi: float) -> str:
    return "C" if av <= lo else ("N" if av <= hi else "E")


def momentum_label(m: float, eps: float) -> str:
    return "up" if m > eps else ("down" if m < -eps else "flat")


# ── per-instrument bar features ──────────────────────────────────────────────
@dataclass(frozen=True)
class BarFeatures:
    """Aligned per-bar arrays (length n). Built once per instrument, reused per horizon."""
    closes: np.ndarray          # float (n,)
    atrs: np.ndarray            # float (n,) — trailing ATR; 0.0 in warmup
    cells: list[str]            # cell label "SESSION|VOL|MOM" per bar ("" until valid)
    valid_from: int             # first bar index with a fully-defined cell


def bar_features(
    candles: Sequence,
    *,
    session_windows: dict,
    atr_period: int,
    mom_lookback: int,
    mom_eps: float,
) -> BarFeatures:
    bars = list(candles)
    n = len(bars)
    closes = np.asarray([float(b.close) for b in bars], dtype=float)
    atrs = np.zeros(n, dtype=float)
    for i in range(1, n):
        atrs[i] = _atr(bars[max(0, i - atr_period): i + 1], atr_period)

    lo, hi = vol_terciles(atrs)
    valid_from = max(atr_period, mom_lookback)
    cells: list[str] = [""] * n
    for i in range(n):
        if i < valid_from or atrs[i] <= 0.0:
            continue
        session = hour_to_session(hour_of(bars[i].timestamp), session_windows)
        vol = vol_label(atrs[i], lo, hi)
        mom = momentum_label((closes[i] - closes[i - mom_lookback]) / atrs[i], mom_eps)
        cells[i] = f"{session}|{vol}|{mom}"
    return BarFeatures(closes=closes, atrs=atrs, cells=cells, valid_from=valid_from)


def horizon_pairs(feats: BarFeatures, horizon: int) -> tuple[list[str], np.ndarray, np.ndarray]:
    """For a horizon h, return (cell_labels, up[int8], bar_index) over valid bars where the
    next-h direction is defined: up = 1 iff close_{t+h} >= close_t."""
    n = feats.closes.size
    labels: list[str] = []
    ups: list[int] = []
    idx: list[int] = []
    for t in range(feats.valid_from, n - horizon):
        cell = feats.cells[t]
        if not cell:
            continue
        labels.append(cell)
        ups.append(1 if feats.closes[t + horizon] >= feats.closes[t] else 0)
        idx.append(t)
    return labels, np.asarray(ups, dtype=np.int64), np.asarray(idx, dtype=np.int64)


# ── entropy / information gain over a partition ──────────────────────────────
def _entropy_bits(rows) -> float:
    """H(direction | partition) in bits via the audited primitive; rows = [[up, down], ...]."""
    return _conditional_entropy_bits(np.asarray(rows, dtype=float))


@dataclass(frozen=True)
class CellStat:
    cell: str
    n: int
    p_up: float
    h_cell: float


@dataclass(frozen=True)
class PartitionStat:
    n: int
    p_up: float
    h_unconditional: float
    h_conditional: float
    information_gain: float
    cells: list[CellStat]


def _cell_counts(labels: Sequence[str], ups: np.ndarray) -> dict[str, tuple[int, int]]:
    """{cell: (n_up, n_down)} — deterministic (insertion via sorted unique labels)."""
    counts: dict[str, list[int]] = {}
    for lab, u in zip(labels, ups.tolist()):
        c = counts.setdefault(lab, [0, 0])
        c[0 if u else 1] += 1
    return {k: (v[0], v[1]) for k, v in sorted(counts.items())}


def partition_stat(labels: Sequence[str], ups: np.ndarray) -> PartitionStat:
    counts = _cell_counts(labels, ups)
    total_up = int(ups.sum())
    total = int(ups.size)
    total_down = total - total_up
    h_uncond = _entropy_bits([[total_up, total_down]]) if total else float("nan")
    rows = [[up, dn] for (up, dn) in counts.values()]
    h_cond = _entropy_bits(rows) if rows else float("nan")
    ig = (h_uncond - h_cond) if (total and rows) else float("nan")
    cells = [
        CellStat(cell=k, n=up + dn, p_up=round(up / (up + dn), 6) if (up + dn) else 0.0,
                 h_cell=round(_entropy_bits([[up, dn]]), 6))
        for k, (up, dn) in counts.items()
    ]
    return PartitionStat(
        n=total, p_up=round(total_up / total, 6) if total else 0.0,
        h_unconditional=round(h_uncond, 6), h_conditional=round(h_cond, 6),
        information_gain=round(ig, 6), cells=cells,
    )


def seed_for(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()[:8], 16)


def permutation_pvalue(labels: Sequence[str], ups: np.ndarray, n_permutations: int, seed: int) -> float:
    """Label-permutation test of the PARTITION's information gain. Null = direction is
    independent of the cell (shuffle `ups`, preserving cell cardinalities). Deterministic.
    Returns add-one p = (#(IG_perm >= IG_obs) + 1)/(n_perm + 1); 1.0 if degenerate."""
    total = int(ups.size)
    if total == 0 or n_permutations <= 0:
        return 1.0
    # Map cells -> contiguous ids; precompute fixed per-cell totals.
    uniq = sorted(set(labels))
    cid = {c: i for i, c in enumerate(uniq)}
    ids = np.fromiter((cid[l] for l in labels), dtype=np.int64, count=total)
    k = len(uniq)
    cell_total = np.bincount(ids, minlength=k).astype(float)
    total_up = float(ups.sum())
    h_uncond = _entropy_bits([[int(total_up), total - int(total_up)]])
    ig_obs = h_uncond - _partition_entropy_from_ids(ids, ups.astype(float), cell_total, k)

    rng = np.random.default_rng(seed)
    up_f = ups.astype(float)
    ge = 0
    for _ in range(n_permutations):
        perm = rng.permutation(up_f)
        ig = h_uncond - _partition_entropy_from_ids(ids, perm, cell_total, k)
        if ig >= ig_obs:
            ge += 1
    return (ge + 1) / (n_permutations + 1)


def _partition_entropy_from_ids(ids: np.ndarray, ups: np.ndarray, cell_total: np.ndarray, k: int) -> float:
    """Weighted H(dir | cell) in bits, vectorised, given fixed cell ids + per-cell totals."""
    up = np.bincount(ids, weights=ups, minlength=k)
    total = cell_total.sum()
    if total <= 0:
        return float("nan")
    with np.errstate(divide="ignore", invalid="ignore"):
        p = np.where(cell_total > 0, up / cell_total, 0.0)
        # binary entropy in bits; 0 at p in {0,1}
        term = np.zeros_like(p)
        m = (p > 0.0) & (p < 1.0)
        term[m] = -(p[m] * np.log2(p[m]) + (1 - p[m]) * np.log2(1 - p[m]))
    return float(np.sum((cell_total / total) * term))


def candidate_cells(stat: PartitionStat, *, min_n: int, dir_floor: float) -> list[CellStat]:
    """Cells inside a (significant) partition worth interpreting: powered + directional."""
    return sorted(
        (c for c in stat.cells if c.n >= min_n and abs(c.p_up - 0.5) >= dir_floor),
        key=lambda c: abs(c.p_up - 0.5), reverse=True,
    )
