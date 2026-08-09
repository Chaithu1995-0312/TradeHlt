"""Unit tests for boundary margin enrichment."""
from __future__ import annotations

from research.zone_mapping.boundary_hypothesis_eval import evaluate_boundary_hypothesis
from research.zone_mapping.crt_zone_crosstab import BarJointLabel


def _lab(i: int, state: str, margin: float, score: float) -> BarJointLabel:
    return BarJointLabel(
        timestamp=str(i),
        candle_index=i,
        crt_state=state,
        zone_id="zone_2",
        cluster_score=score,
        passed=True,
        crt_action="NONE",
        best_zone_score=0.8,
        second_best_score=0.8 - margin,
        margin_best_second=margin,
    )


def test_boundary_enrichment_when_disp_has_low_margin():
    # 80 RANGE high margin, then 20 DISPLACEMENT low margin
    labels = [_lab(i, "RANGE", margin=0.2, score=0.75) for i in range(80)]
    labels += [_lab(80 + i, "DISPLACEMENT", margin=0.01, score=0.55) for i in range(20)]
    # SWEEP bars with low margin followed by DISPLACEMENT starts (forward hyp)
    labels += [_lab(100 + i, "SWEEP", margin=0.02, score=0.5) for i in range(40)]
    labels += [_lab(140 + i, "DISPLACEMENT", margin=0.01, score=0.55) for i in range(10)]
    labels += [_lab(150 + i, "SWEEP", margin=0.2, score=0.8) for i in range(40)]

    ev = evaluate_boundary_hypothesis(
        labels, contexts=("ALL", "RANGE", "SWEEP"), forward_K=5
    )
    allp = ev["by_context"]["ALL"]
    assert allp["delta_margin_disp_minus_other"] < 0
    assert allp["hypothesis_support"]["margin_lower_on_positive"] is True
    low_m = allp["top20pct"]["lowest_margin_state"]
    high_m = allp["top20pct"]["highest_margin_state"]
    assert low_m["hit_rate"] >= high_m["hit_rate"]
    # SWEEP forward positives exist
    sw = ev["by_context"]["SWEEP"]
    assert sw["n_positive"] >= 1
