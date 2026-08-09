"""selection_effect.py — Phase S1 pure core: the spine's RETEST selection effect.

Measures ΔE = E[net-RR | selected retests] − E[net-RR | rejected retests], decomposed by
reject-reason class and **pooled by EFFECT, not raw entries** (weight w_i = min(n_sel, n_rej))
so per-instrument microstructure never mixes (respects F-009). Significance is a **stratified
permutation** — labels are shuffled WITHIN each instrument (preserving per-instrument counts),
then the effect is pooled — so a result cannot be manufactured by cross-instrument imbalance.

Pure & deterministic: numpy + stdlib, seeded permutations, no spine import, no I/O.
The driver (scripts/research/phase_s_selection_effect.py) supplies net-RR via the governing
forward_walk(intrabar_fixed)+CostModel and owns all backtest/harvest/disk work.
"""

from __future__ import annotations

import hashlib
from typing import Sequence

import numpy as np


def fold_reason(reason, reason_classes: dict) -> str:
    """Fold a RETEST_REPLAY.reject_reason into a selection-skill class. accepted → 'ACCEPTED'."""
    if reason is None:
        return "ACCEPTED"
    for cls, tokens in reason_classes.items():
        if reason in tokens:
            return cls
    return "OTHER"


def _mean(xs) -> float:
    a = np.asarray(xs, dtype=float)
    return float(a.mean()) if a.size else float("nan")


def delta_e(selected: Sequence[float], rejected: Sequence[float]) -> float:
    """E[selected] − E[rejected]; NaN if either side is empty."""
    if len(selected) == 0 or len(rejected) == 0:
        return float("nan")
    return _mean(selected) - _mean(rejected)


def seed_for(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()[:8], 16)


def pooled_delta(groups: Sequence[tuple]) -> tuple[float, float]:
    """Pool ΔE_i across instruments, weight w_i = min(n_sel, n_rej). Instruments with either
    side empty are skipped. `groups` = list of (selected_rr, rejected_rr). Returns (ΔE_pooled, ΣW)."""
    num = 0.0
    den = 0.0
    for sel, rej in groups:
        ns, nr = len(sel), len(rej)
        if ns == 0 or nr == 0:
            continue
        w = float(min(ns, nr))
        num += w * (_mean(sel) - _mean(rej))
        den += w
    return (num / den if den > 0 else float("nan")), den


def stratified_permutation_p(groups: Sequence[tuple], n_permutations: int, seed: int) -> tuple[float, float, int]:
    """One-sided stratified-permutation test of the pooled ΔE (H1: selected > rejected).
    Within each instrument, shuffle the selected/rejected labels (preserve counts), pool, repeat
    (seeded → deterministic). Returns (ΔE_obs, p_value, n_instruments_used)."""
    used = [(np.asarray(sel, float), np.asarray(rej, float))
            for sel, rej in groups if len(sel) > 0 and len(rej) > 0]
    if not used:
        return float("nan"), 1.0, 0
    obs, _ = pooled_delta([(s, r) for s, r in used])
    pools = [np.concatenate([s, r]) for s, r in used]
    nsel = [len(s) for s, _ in used]
    weights = [float(min(len(s), len(r))) for s, r in used]
    W = sum(weights)
    rng = np.random.default_rng(seed)
    ge = 0
    for _ in range(n_permutations):
        num = 0.0
        for pool, ns, w in zip(pools, nsel, weights):
            perm = rng.permutation(pool)
            num += w * (perm[:ns].mean() - perm[ns:].mean())
        if (num / W) >= obs:
            ge += 1
    return obs, (ge + 1) / (n_permutations + 1), len(used)


def sign_consistency(deltas: Sequence[float]) -> tuple[int, int]:
    """(#instruments with ΔE_i > 0, #instruments with a defined ΔE_i). Guards against a pooled
    positive carried by one instrument."""
    vals = [d for d in deltas if not np.isnan(d)]
    return sum(1 for d in vals if d > 0), len(vals)
