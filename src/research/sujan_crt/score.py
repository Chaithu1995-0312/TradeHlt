"""SEM-023 comparison arm. Never admits or rejects a SEM-031 candidate.

Weights are the registered Score B cartoon (15+15+20+15+10+10+10+5 = 100).
An unevaluable component returns None (UNDEFINED), never a silent 0.
"""
from __future__ import annotations

WEIGHTS = {
    "monthly_aligned": 15,
    "weekly_aligned": 15,
    "daily_objective_clear": 20,
    "htf_location": 15,
    "liquidity_sweep": 10,
    "rejection_block": 10,
    "displacement": 10,
    "bos_choch": 5,
}


def alignment_score(
    *,
    monthly_aligned: bool | None,
    weekly_aligned: bool | None,
    daily_objective_clear: bool | None,
    htf_location: bool | None,
    liquidity_sweep: bool | None,
    rejection_block: bool | None,
    displacement: bool | None,
    bos_choch: bool | None,
) -> int | None:
    if sum(WEIGHTS.values()) != 100:
        raise RuntimeError("SEM-023 weights must sum to 100")
    values = {
        "monthly_aligned": monthly_aligned,
        "weekly_aligned": weekly_aligned,
        "daily_objective_clear": daily_objective_clear,
        "htf_location": htf_location,
        "liquidity_sweep": liquidity_sweep,
        "rejection_block": rejection_block,
        "displacement": displacement,
        "bos_choch": bos_choch,
    }
    if any(v is None for v in values.values()):
        return None
    return sum(WEIGHTS[k] * (1 if values[k] else 0) for k in WEIGHTS)
