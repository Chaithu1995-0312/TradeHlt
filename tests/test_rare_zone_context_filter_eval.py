"""Unit tests for rare-zone × CRT context evaluation."""
from __future__ import annotations

from research.zone_mapping.crt_zone_crosstab import BarJointLabel
from research.zone_mapping.rare_zone_context_filter_eval import (
    build_contextual_rare_signals,
    evaluate_context_filter,
)


def _lab(i: int, state: str, zone: str, score: float = 0.7) -> BarJointLabel:
    return BarJointLabel(
        timestamp=str(i),
        candle_index=i,
        crt_state=state,
        zone_id=zone,
        cluster_score=score,
        passed=True,
        crt_action="NONE",
    )


def test_context_precision_sweep_beats_range():
    labels = []
    # RANGE rare entry → no DISPLACEMENT
    labels += [_lab(i, "RANGE", "zone_2") for i in range(5)]
    labels += [_lab(5, "RANGE", "zone_6")]
    labels += [_lab(i, "RANGE", "zone_6") for i in range(6, 15)]
    # SWEEP rare entry → DISPLACEMENT soon
    labels += [_lab(i, "SWEEP", "zone_2") for i in range(15, 20)]
    labels += [_lab(20, "SWEEP", "zone_4")]
    labels += [_lab(21, "SWEEP", "zone_4")]
    labels += [_lab(i, "DISPLACEMENT", "zone_4") for i in range(22, 28)]

    sigs = build_contextual_rare_signals(labels)
    assert any(s.crt_context == "RANGE" for s in sigs)
    assert any(s.crt_context == "SWEEP" for s in sigs)

    ev = evaluate_context_filter(labels, K_values=(5,))
    by = ev["by_K"]["5"]["by_context"]
    assert by["SWEEP"]["precision"] > by["RANGE"]["precision"]
    inter = ev["by_K"]["5"]["interaction_RANGE_vs_SWEEP"]
    assert inter["precision_SWEEP_minus_RANGE"] > 0
