"""stats.py — per-cell statistics shared by sealed-contract drivers.

`trade_stats` replaces the byte-identical body (module-level in `research.sujan_crt.driver`,
nested inside `run()` in `research.mother_range.driver` — a real AST fingerprint census only
walks module-level defs, so the mother_range copy was invisible to it; found by reading both
files in full) computing {n, gross_mean, net_mean, win_rate, pf} from `y_R_gross`/`y_R_net` rows.

`arm_cells` replaces the COMPUTATIONALLY-identical (not AST-identical — see module docstring in
`research.mc_kit`) agree/disagree cell body in `research.evidence.mother_range_prior` and
`research.evidence.magnitude_prior`: same four statistics per side, same null/zero handling,
different local-variable staging. Proven equal by the parity floor, not by AST comparison.

`sign` replaces the identical 4-line `>`/`<`/`0`/`None` classifier duplicated across
`asymmetry_contract`, `magnitude_prior`, and `mother_range_prior` (a real duplicate despite the
`verdict` functions that call it differing per contract).
"""
from __future__ import annotations

import statistics
from typing import Any, Optional


def trade_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """{n, gross_mean, net_mean, win_rate, pf} from `y_R_gross`/`y_R_net` on each row.

    `pf` (gross profit / gross |loss|) is `inf` when there are wins and no losses, `0.0` when
    there are neither — matches both replaced copies exactly. `{"n": 0, ...: None}` on empty
    input (never a ZeroDivisionError).
    """
    n = len(rows)
    if n == 0:
        return {"n": 0, "gross_mean": None, "net_mean": None, "win_rate": None, "pf": None}
    gross = [float(r["y_R_gross"]) for r in rows]
    net = [float(r["y_R_net"]) for r in rows]
    wins = [g for g in gross if g > 0]
    losses = [g for g in gross if g < 0]
    gp = sum(wins)
    gl = abs(sum(losses))
    pf = (gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0)
    return {
        "n": n,
        "gross_mean": sum(gross) / n,
        "net_mean": sum(net) / n,
        "win_rate": sum(1 for g in gross if g > 0) / n,
        "pf": pf,
    }


def _mean(xs: list[float]) -> Optional[float]:
    """`statistics.mean` (exact fraction-based summation), matching
    `research.evidence.queries._mean` exactly — NOT naive `sum(xs)/len(xs)`, which can differ in
    the last bit on real data (caught by the Phase-3 end-to-end byte-identity gate on
    `mother_range_prior`, not by a small synthetic unit test — see test_mc_kit.py)."""
    return statistics.mean(xs) if xs else None


def arm_cells(rows: list[dict[str, Any]], y_key: str) -> dict[str, Any]:
    """Split `rows` by their `"agree"` field into agree/disagree cells over `row[y_key]`.

    Per cell: n, mean, P(y>0), E[y | y>0]. Rows whose `y_key` is `None` count toward
    `n_null_y` and are dropped from both cells; rows whose `"agree"` is `None` count toward
    `n_trend_zero_or_unknown` and are likewise dropped. `contrast` = agree.mean - disagree.mean,
    `None` if either is undefined.
    """
    agree_xs: list[float] = []
    disag_xs: list[float] = []
    n_zero = 0
    n_null_y = 0
    for r in rows:
        y = r.get(y_key)
        if y is None:
            n_null_y += 1
            continue
        if r.get("agree") is None:
            n_zero += 1
            continue
        (agree_xs if r["agree"] else disag_xs).append(float(y))
    ea, ed = _mean(agree_xs), _mean(disag_xs)
    return {
        "agree": {
            "n": len(agree_xs),
            "mean": ea,
            "p_gt_0": (sum(1 for x in agree_xs if x > 0) / len(agree_xs)) if agree_xs else None,
            "e_given_gt_0": _mean([x for x in agree_xs if x > 0]),
        },
        "disagree": {
            "n": len(disag_xs),
            "mean": ed,
            "p_gt_0": (sum(1 for x in disag_xs if x > 0) / len(disag_xs)) if disag_xs else None,
            "e_given_gt_0": _mean([x for x in disag_xs if x > 0]),
        },
        "contrast": None if ea is None or ed is None else ea - ed,
        "n_trend_zero_or_unknown": n_zero,
        "n_null_y": n_null_y,
    }


def sign(x: Optional[float]) -> Optional[int]:
    """`+1` / `-1` / `0` / `None` (`None` in, `None` out) — never raises."""
    if x is None:
        return None
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0
