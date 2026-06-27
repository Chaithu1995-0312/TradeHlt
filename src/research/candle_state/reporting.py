"""reporting.py — REPORTING-ONLY trade metrics (win-rate, losing streak, rolling-10).

The user wants WR ≥ 70%, max losing streak ≤ 3, and a rolling 10-trade window check surfaced
alongside every result. Per the approved plan these are **reporting only** — they NEVER gate a
promotion. The promote authority remains the expectancy-first `QualificationGate` (intrabar_fixed
+ 12bps). Nothing in this module imports or touches `research.qualification`; these functions
consume a list of per-trade NET R floats and return a dict.

Pure & deterministic: stdlib only.
"""

from __future__ import annotations

from typing import Sequence


def win_rate(net_rrs: Sequence[float]) -> float:
    """Fraction of trades with net R > 0. 0.0 for an empty list."""
    rrs = list(net_rrs)
    if not rrs:
        return 0.0
    return sum(1 for r in rrs if r > 0.0) / len(rrs)


def streak_metrics(net_rrs: Sequence[float]) -> dict:
    """Max consecutive losing / winning run over the (chronological) trade sequence."""
    max_loss = max_win = cur_loss = cur_win = 0
    for r in net_rrs:
        if r > 0.0:
            cur_win += 1
            cur_loss = 0
        elif r < 0.0:
            cur_loss += 1
            cur_win = 0
        else:                       # exactly flat: breaks both runs
            cur_loss = cur_win = 0
        max_loss = max(max_loss, cur_loss)
        max_win = max(max_win, cur_win)
    return {
        "max_losing_streak": max_loss,
        "max_winning_streak": max_win,
        "max_losing_streak_ok": bool(max_loss <= 3),   # reporting flag only
    }


def rolling_window_metrics(net_rrs: Sequence[float], *, window: int = 10, min_wins: int = 7) -> dict:
    """Rolling `window`-trade analysis. Reports the worst window's win count and whether any
    window falls below `min_wins` wins (the user's "no window worse than 7W/3L" check).
    Reporting only — never gates."""
    rrs = list(net_rrs)
    n = len(rrs)
    wins = [1 if r > 0.0 else 0 for r in rrs]
    if n < window:
        return {"n_windows": 0, "worst_window_wins": None,
                "all_windows_ok": None, "window": window, "min_wins": min_wins}
    worst = window
    for i in range(0, n - window + 1):
        w = sum(wins[i:i + window])
        worst = min(worst, w)
    return {
        "n_windows": n - window + 1,
        "worst_window_wins": worst,
        "all_windows_ok": bool(worst >= min_wins),     # reporting flag only
        "window": window,
        "min_wins": min_wins,
    }


def report(net_rrs: Sequence[float]) -> dict:
    """Convenience rollup of all reporting-only metrics for one trade sequence."""
    rrs = list(net_rrs)
    return {
        "n": len(rrs),
        "win_rate": round(win_rate(rrs), 6),
        "win_rate_ge_70pct": bool(win_rate(rrs) >= 0.70),   # reporting flag only
        **streak_metrics(rrs),
        "rolling_10": rolling_window_metrics(rrs),
    }
