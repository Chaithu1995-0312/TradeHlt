"""Unit tests for rare-zone FA CRT-evolution labeling."""
from __future__ import annotations

from research.zone_mapping.crt_zone_crosstab import BarJointLabel
from research.zone_mapping.rare_zone_fa_characterization import (
    characterize_false_alarms,
    classify_crt_evolution,
    extract_crt_path,
)


def _lab(i: int, state: str, zone: str) -> BarJointLabel:
    return BarJointLabel(
        timestamp=str(i),
        candle_index=i,
        crt_state=state,
        zone_id=zone,
        cluster_score=0.7,
        passed=True,
        crt_action="NONE",
    )


def test_classify_range_to_sweep_and_tp_disp():
    path = ["RANGE"] * 5 + ["SWEEP"] * 10
    tax = classify_crt_evolution(
        path, is_tp=False, K=5, disp_starts_set=set(), signal_index=0
    )
    assert "RANGE_TO_SWEEP_ONLY" in tax.tags or tax.primary == "RANGE_TO_SWEEP_ONLY"

    path2 = ["RANGE", "SWEEP", "DISPLACEMENT", "EXPANSION"]
    tax2 = classify_crt_evolution(
        path2, is_tp=True, K=5, disp_starts_set={2}, signal_index=0
    )
    assert tax2.primary in ("REACHED_DISPLACEMENT", "REACHED_EXECUTION", "EXPANSION_AFTER_DISP") or "TP_DISPLACEMENT_IN_K" in tax2.tags


def test_characterize_partitions_fa_by_zone():
    # rare entry zone_6 at 5, then only RANGE → FA for K=3
    labels = [_lab(i, "RANGE", "zone_2") for i in range(5)]
    labels += [_lab(5, "RANGE", "zone_6")]
    labels += [_lab(i, "RANGE", "zone_6") for i in range(6, 30)]
    # TP: rare entry zone_1 at 40, DISPLACEMENT at 42
    labels += [_lab(i, "RANGE", "zone_2") for i in range(30, 40)]
    labels += [_lab(40, "SWEEP", "zone_1")]
    labels += [_lab(41, "SWEEP", "zone_1")]
    labels += [_lab(i, "DISPLACEMENT", "zone_1") for i in range(42, 50)]

    rep = characterize_false_alarms(labels, K=5, follow=20)
    assert rep["n_fa"] >= 1
    assert rep["n_tp"] >= 1
    assert "zone_6" in rep["by_zone"]
    assert rep["by_zone"]["zone_6"]["n_fa"] >= 1
