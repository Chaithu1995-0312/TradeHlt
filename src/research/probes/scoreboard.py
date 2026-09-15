"""Generic probe scoreboard rows (n / coverage / expectancy / PF / win rate)."""
from __future__ import annotations

import statistics as st


def profit_factor(xs: list[float], pf_cap: float = 9999.0) -> float:
    gp = sum(x for x in xs if x > 0)
    gl = -sum(x for x in xs if x < 0)
    if gl <= 0:
        return pf_cap if gp > 0 else 0.0
    return min(gp / gl, pf_cap)


def scoreboard_row(
    name: str,
    net_rs: list[float],
    *,
    n_universe: int,
    n_eligible: int,
    min_n_label: int = 30,
    pf_cap: float = 9999.0,
) -> dict:
    n = len(net_rs)
    coverage = (100.0 * n / n_universe) if n_universe else 0.0
    if n == 0:
        return {
            "arm": name,
            "n": 0,
            "n_universe": n_universe,
            "n_eligible_direction": n_eligible,
            "coverage_pct": round(coverage, 4),
            "expectancy": None,
            "PF": None,
            "win_rate": None,
            "power": "EMPTY",
        }
    wins = sum(1 for x in net_rs if x > 0)
    return {
        "arm": name,
        "n": n,
        "n_universe": n_universe,
        "n_eligible_direction": n_eligible,
        "coverage_pct": round(coverage, 4),
        "expectancy": round(st.mean(net_rs), 6),
        "PF": round(profit_factor(net_rs, pf_cap=pf_cap), 4),
        "win_rate": round(wins / n, 6),
        "power": "INSUFFICIENT" if n < min_n_label else "WEAK",
    }
