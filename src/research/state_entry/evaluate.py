"""Split, family correction, controls and verdicts (MC-STATEENTRY splits + metrics).

Verdict ladder for one PRIMARY-arm cell (entry_kind x direction x geometry x horizon),
evaluated in order and short-circuiting at the first failure — the controls are only
drawn for cells that already cleared (1)-(3), which is equivalent to the contract's
"POSITIVE only if ALL hold" and keeps 100 random draws off cells that cannot pass:

    INSUFFICIENT     train n < 30 (outside the BH family) or holdout n < 30
    NEGATIVE         train mean_net <= 0
    NOT_SIGNIFICANT  does not survive BH-FDR (q=0.10) on train
    HOLDOUT_FAIL     holdout mean_net <= 0
    FAILS_CONTROL    (short cells) holdout mean_net does not beat long_only, or beats
                     random_entry in fewer than 95 of 100 seeded draws
    POSITIVE         every clause holds. Information only (Authority Ladder rung 1).
"""
from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Sequence

from research.evidence.context_attribution import benjamini_hochberg
from research.state_entry.walk import (
    ARM_CLOSE_ONLY,
    PRIMARY_ARM,
    Geometry,
    Levels,
    atr_at,
    close_only_bars,
    walk_unit,
)
from research.state_entry.extract import Bar, EntryUnit

TRAIN_FRACTION = 0.70
EMBARGO_BARS = 96
N_MIN = 30
BH_Q = 0.10
N_RANDOM_SEEDS = 100
RANDOM_BEAT_MIN = 95
SEED = 20261005

INSUFFICIENT = "INSUFFICIENT"
NEGATIVE = "NEGATIVE"
NOT_SIGNIFICANT = "NOT_SIGNIFICANT"
HOLDOUT_FAIL = "HOLDOUT_FAIL"
FAILS_CONTROL = "FAILS_CONTROL"
POSITIVE = "POSITIVE"


def split_rows(rows: Sequence[dict], n_bars: int) -> tuple[list, list, dict]:
    """Chronological cut at 70% of corpus rows with a 96-bar embargo and per-horizon purge."""
    cut = int(math.floor(TRAIN_FRACTION * n_bars))
    hold_start = cut + EMBARGO_BARS
    train = [r for r in rows if r["entry_row"] + r["horizon"] < cut]
    hold = [r for r in rows if r["entry_row"] >= hold_start]
    manifest = {"n_bars": n_bars, "cut_row": cut, "holdout_start_row": hold_start,
                "embargo_bars": EMBARGO_BARS, "train_fraction": TRAIN_FRACTION}
    return train, hold, manifest


def summarize(ys: Sequence[float]) -> dict:
    n = len(ys)
    if n == 0:
        return {"n": 0, "mean": None, "sd": None, "ci95": None, "p_one_sided": None, "pf": None}
    mean = sum(ys) / n
    sd = math.sqrt(sum((y - mean) ** 2 for y in ys) / (n - 1)) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 else float("inf")
    if se == 0.0:
        p = 0.0 if mean > 0 else 1.0
    elif math.isinf(se):
        p = None
    else:
        p = 0.5 * math.erfc((mean / se) / math.sqrt(2.0))   # P(Z > t), one-sided mean > 0
    pos = sum(y for y in ys if y > 0)
    neg = -sum(y for y in ys if y < 0)
    return {"n": n, "mean": mean, "sd": sd,
            "ci95": None if math.isinf(se) else [mean - 1.96 * se, mean + 1.96 * se],
            "p_one_sided": p, "pf": (pos / neg) if neg > 0 else None}


def overlap_count(rows: Sequence[dict]) -> int:
    """Units entered while an earlier unit of the same cell was still open."""
    busy_until = -1
    n = 0
    for r in sorted(rows, key=lambda r: r["entry_row"]):
        if r["entry_row"] <= busy_until:
            n += 1
        busy_until = max(busy_until, r["entry_row"] + r["duration"])
    return n


def _cell_key(r: dict) -> tuple:
    return (r["entry_kind"], r["direction"], r["geometry"], r["horizon"])


def _walk_synthetic(bars_view: Sequence[Bar], row: int, direction: str, risk: float,
                    g: Geometry, horizon: int, cost_model):
    """A control trade: same stop distance and R multiples, any bar, any direction."""
    entry = bars_view[row].close
    sign = 1.0 if direction == "long" else -1.0
    lv = Levels(entry, entry - sign * risk, entry + sign * g.tp1_mult * risk,
                entry + sign * g.tp2_mult * risk, 0.0)
    unit = EntryUnit(entry_kind="CONTROL", direction=direction, entry_row=row, entry_price=entry,
                     setup_sweep_row=row, sweep_row=row, displacement_row=None, engine_atr=None)
    o = walk_unit(unit, lv, bars_view, arm=ARM_CLOSE_ONLY, horizon=horizon,
                  partial_fraction=g.partial_fraction)
    if o is None:
        return None
    return o.rr_gross - cost_model.cost_r(entry, risk, exit_kind=o.exit_kind, direction=direction)


def long_only_mean(hold_rows: Sequence[dict], bars_view, g: Geometry, cost_model) -> float | None:
    ys = []
    for r in hold_rows:
        y = _walk_synthetic(bars_view, r["entry_row"], "long", abs(r["entry"] - r["sl"]),
                            g, r["horizon"], cost_model)
        if y is not None:
            ys.append(y)
    return sum(ys) / len(ys) if ys else None


def random_entry_beats(hold_rows: Sequence[dict], cell_mean: float, bars, bars_view,
                       hold_start: int, g: Geometry, cost_model) -> tuple[int, list[float]]:
    """Seeds (of 100) whose matched random draw the cell beats. Matched on direction,
    hour-of-day and stop distance in ATR units; ATR taken at the DRAWN bar."""
    horizon = hold_rows[0]["horizon"]
    last = len(bars) - horizon - 1
    by_hour: dict[int, list[int]] = defaultdict(list)
    for i in range(max(hold_start, 1), last + 1):
        by_hour[bars[i].timestamp.hour].append(i)
    beats, means = 0, []
    for s in range(N_RANDOM_SEEDS):
        rng = random.Random(SEED + s)
        ys = []
        for r in hold_rows:
            pool = by_hour.get(r["hour"]) or []
            if not pool:
                continue
            row = rng.choice(pool)
            a = atr_at(bars, row)
            if not a > 0:
                continue
            y = _walk_synthetic(bars_view, row, r["direction"], r["sl_atr"] * a,
                                g, horizon, cost_model)
            if y is not None:
                ys.append(y)
        m = sum(ys) / len(ys) if ys else None
        means.append(m)
        if m is not None and cell_mean > m:
            beats += 1
    return beats, means


def evaluate(rows: Sequence[dict], bars: Sequence[Bar], g: Geometry, cost_model) -> dict:
    """All cells, both arms. Tests and verdicts on the PRIMARY arm only."""
    train, hold, manifest = split_rows(rows, len(bars))
    view = close_only_bars(bars)

    def group(rs):
        out = defaultdict(lambda: defaultdict(list))
        for r in rs:
            out[r["arm"]][_cell_key(r)].append(r)
        return out

    tr, ho = group(train), group(hold)
    keys = sorted(set(tr[PRIMARY_ARM]) | set(ho[PRIMARY_ARM]))

    cells = {}
    for k in keys:
        t_rows, h_rows = tr[PRIMARY_ARM].get(k, []), ho[PRIMARY_ARM].get(k, [])
        cells[k] = {
            "train_net": summarize([r["y_net"] for r in t_rows]),
            "train_gross": summarize([r["y_gross"] for r in t_rows]),
            "hold_net": summarize([r["y_net"] for r in h_rows]),
            "hold_gross": summarize([r["y_gross"] for r in h_rows]),
            "train_overlap": overlap_count(t_rows),
            "hold_overlap": overlap_count(h_rows),
            "reference_sl_first": {
                "train_net_mean": summarize([r["y_net"] for r in tr["sl_first"].get(k, [])])["mean"],
                "hold_net_mean": summarize([r["y_net"] for r in ho["sl_first"].get(k, [])])["mean"],
            },
        }

    family = {k: c["train_net"]["p_one_sided"] for k, c in cells.items()
              if c["train_net"]["n"] >= N_MIN}
    survive = benjamini_hochberg(family, q=BH_Q)

    for k, c in cells.items():
        tn, hn = c["train_net"], c["hold_net"]
        c["in_family"] = k in family
        c["bh_survives"] = bool(survive.get(k, False))
        if tn["n"] < N_MIN:
            c["verdict"] = INSUFFICIENT
        elif tn["mean"] <= 0:
            c["verdict"] = NEGATIVE
        elif not c["bh_survives"]:
            c["verdict"] = NOT_SIGNIFICANT
        elif hn["n"] < N_MIN:
            c["verdict"] = INSUFFICIENT
        elif hn["mean"] <= 0:
            c["verdict"] = HOLDOUT_FAIL
        else:
            h_rows = ho[PRIMARY_ARM][k]
            # Forcing a LONG unit long reproduces it, so long_only judges SHORT cells only;
            # a long cell's passive-drift control is the random LONG draw below (contract (4)).
            lo = long_only_mean(h_rows, view, g, cost_model) if k[1] == "short" else None
            beats, _ = random_entry_beats(h_rows, hn["mean"], bars, view,
                                          manifest["holdout_start_row"], g, cost_model)
            c["control_long_only_hold_mean"] = lo
            c["control_random_beats_of_100"] = beats
            ok = (lo is None or hn["mean"] > lo) and beats >= RANDOM_BEAT_MIN
            c["verdict"] = POSITIVE if ok else FAILS_CONTROL

    tally = defaultdict(int)
    for c in cells.values():
        tally[c["verdict"]] += 1
    return {
        "split_manifest": manifest,
        "family_size": len(family),
        "bh_q": BH_Q,
        "verdict_counts": dict(tally),
        "cells": {"|".join(map(str, k)): v for k, v in cells.items()},
    }
