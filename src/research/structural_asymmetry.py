"""structural_asymmetry.py — Program 2 / Phase E1 pure core: forward asymmetry of a structural-event
population, measured PURELY (no exits, no RR, no expectancy).

Measures only raw forward price geometry from an anchor t0, in the continuation direction:
  * multi-horizon MFE_r / MAE_r at h ∈ {1,2,4,8,16} bars (running max-favorable / min-adverse ÷ ATR),
  * symmetric first-hit barrier race at L ∈ {0.25,0.5,1.0}R — does price touch +L or −L first (conservative
    SL-before-TP tie-break inside a bar) within the barrier window.

The question is asymmetry, never profitability: E[MFE] vs E[MAE], and P(+L first) vs P(−L first), of the
COMPLETED sweep→displacement→retest population vs four controls (esp. the sweep-only control D).

Pure & deterministic: numpy + stdlib, seeded permutations, no spine import, no I/O.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

HORIZONS_DEFAULT = (1, 2, 4, 8, 16)
LEVELS_DEFAULT = (0.25, 0.5, 1.0)


def seed_for(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()[:8], 16)


def _dir_sign(direction) -> float:
    return 1.0 if direction in ("long", 1, "+1", "1") else -1.0


@dataclass(frozen=True)
class PathMeasure:
    mfe_r: dict          # h -> running max favorable excursion (R), >= 0
    mae_r: dict          # h -> running min adverse excursion (R), <= 0
    first_hit: dict      # L -> +1 (+L first) | -1 (−L first) | 0 (neither) within the barrier window


def measure_path(entry: float, direction, atr: float, future: Sequence,
                 *, horizons: Sequence[int] = HORIZONS_DEFAULT,
                 levels: Sequence[float] = LEVELS_DEFAULT) -> PathMeasure:
    """Exit-agnostic forward geometry from t0 (= entry close), continuation direction. Never closes a
    position — records excursions + the first symmetric barrier touched. Barrier window = max(horizons)."""
    sign = _dir_sign(direction)
    risk = atr if atr > 0 else float("nan")
    hmax = max(horizons)
    mfe = {h: 0.0 for h in horizons}
    mae = {h: 0.0 for h in horizons}
    first_hit = {L: 0 for L in levels}
    done = {L: False for L in levels}
    run_fav = 0.0
    run_adv = 0.0
    bars = list(future)[:hmax]
    for k, bar in enumerate(bars, start=1):
        hi, lo = float(bar.high), float(bar.low)
        fav = ((hi - entry) if sign > 0 else (entry - lo)) / risk   # max favorable this bar (R)
        adv = ((lo - entry) if sign > 0 else (entry - hi)) / risk   # max adverse this bar (R, <=0)
        run_fav = max(run_fav, fav)
        run_adv = min(run_adv, adv)
        for h in horizons:
            if k <= h:
                mfe[h] = max(mfe[h], run_fav)
                mae[h] = min(mae[h], run_adv)
        # symmetric first-hit (conservative: if a bar touches both ±L, count −L first)
        for L in levels:
            if done[L]:
                continue
            if adv <= -L:
                first_hit[L] = -1; done[L] = True
            elif fav >= L:
                first_hit[L] = +1; done[L] = True
    return PathMeasure(mfe_r={h: round(mfe[h], 6) for h in horizons},
                       mae_r={h: round(mae[h], 6) for h in horizons},
                       first_hit=first_hit)


# ── population aggregation ────────────────────────────────────────────────────
def _mean(xs) -> float:
    a = np.asarray(xs, dtype=float)
    return float(a.mean()) if a.size else float("nan")


def aggregate(measures: Sequence[PathMeasure], *, horizons=HORIZONS_DEFAULT, levels=LEVELS_DEFAULT) -> dict:
    """Per-horizon excursion asymmetry + per-level first-hit asymmetry for a population."""
    n = len(measures)
    out = {"n": n, "excursion": {}, "first_hit": {}}
    for h in horizons:
        mfe = [m.mfe_r[h] for m in measures]
        mae = [m.mae_r[h] for m in measures]
        out["excursion"][str(h)] = {
            "mfe_r": round(_mean(mfe), 6), "mae_r": round(_mean(mae), 6),
            "asymmetry": round(_mean(mfe) + _mean(mae), 6),   # E[MFE] − E[|MAE|] = E[MFE]+E[MAE(neg)]
        }
    for L in levels:
        hits = [m.first_hit[L] for m in measures]
        n_plus = sum(1 for x in hits if x > 0)
        n_minus = sum(1 for x in hits if x < 0)
        decided = n_plus + n_minus
        p_plus = (n_plus / n) if n else float("nan")
        p_minus = (n_minus / n) if n else float("nan")
        out["first_hit"][str(L)] = {
            "n": n, "decided": decided, "p_plus": round(p_plus, 6), "p_minus": round(p_minus, 6),
            "delta": round(p_plus - p_minus, 6),
            "ci_halfwidth": round(_wilson_halfwidth(n_plus, decided), 6) if decided else None,
        }
    return out


def _wilson_halfwidth(k: int, n: int, z: float = 1.96) -> float:
    """Wilson-interval half-width for a proportion k/n (power diagnostic). 1.0 (max) if n==0."""
    if n <= 0:
        return 1.0
    p = k / n
    denom = 1.0 + z * z / n
    half = (z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)) / denom
    return half


# ── test vs control (asymmetry difference + permutation) ──────────────────────
def _excursion_asym(measures, h) -> float:
    return _mean([m.mfe_r[h] for m in measures]) + _mean([m.mae_r[h] for m in measures])


def _firsthit_delta(measures, L) -> float:
    n = len(measures)
    if not n:
        return float("nan")
    p_plus = sum(1 for m in measures if m.first_hit[L] > 0) / n
    p_minus = sum(1 for m in measures if m.first_hit[L] < 0) / n
    return p_plus - p_minus


def permutation_vs_control(test: Sequence[PathMeasure], control: Sequence[PathMeasure],
                           *, stat: str, key, n_permutations: int, seed: int) -> tuple[float, float]:
    """One-sided permutation: is the test population's asymmetry > the control's? `stat` ∈
    {'excursion','first_hit'}; `key` = horizon (int) or level (float). Returns (observed_delta, p)."""
    if stat == "excursion":
        f = lambda ms: _excursion_asym(ms, key)
    else:
        f = lambda ms: _firsthit_delta(ms, key)
    nt = len(test)
    if nt == 0 or len(control) == 0:
        return float("nan"), 1.0
    obs = f(list(test)) - f(list(control))
    pool = list(test) + list(control)
    rng = np.random.default_rng(seed)
    idx = np.arange(len(pool))
    ge = 0
    for _ in range(n_permutations):
        rng.shuffle(idx)
        t = [pool[i] for i in idx[:nt]]
        c = [pool[i] for i in idx[nt:]]
        if (f(t) - f(c)) >= obs:
            ge += 1
    return round(obs, 6), (ge + 1) / (n_permutations + 1)
