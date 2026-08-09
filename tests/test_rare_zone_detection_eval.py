"""Unit tests for rare-zone → DISPLACEMENT event detection metrics."""
from __future__ import annotations

from research.zone_mapping.crt_zone_crosstab import BarJointLabel
from research.zone_mapping.rare_zone_detection_eval import (
    evaluate_all_detectors,
    evaluate_detector,
    find_zone_entries,
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


def test_precision_recall_synthetic():
    # bars 0-4: RANGE zone_2
    # bar 5: entry zone_6 (rare signal)
    # bars 6-7: still RANGE zone_6
    # bar 8: DISPLACEMENT starts zone_6
    labels = [_lab(i, "RANGE", "zone_2") for i in range(5)]
    labels += [_lab(i, "RANGE", "zone_6") for i in range(5, 8)]
    labels += [_lab(i, "DISPLACEMENT", "zone_6") for i in range(8, 12)]
    # false alarm: rare entry far from any DISPLACEMENT
    labels += [_lab(i, "RANGE", "zone_2") for i in range(12, 20)]
    labels += [_lab(20, "RANGE", "zone_1")]  # rare entry, no DISPLACEMENT after
    labels += [_lab(i, "RANGE", "zone_1") for i in range(21, 30)]

    rare_sig = find_zone_entries(labels, target_zones=("zone_1", "zone_4", "zone_5", "zone_6"))
    # entries at 5 (zone_6) and 20 (zone_1)
    assert len(rare_sig) == 2
    m = evaluate_detector(labels, rare_sig, K=5, detector_name="rare_zone_entry")
    # signal@5 → DISPLACEMENT@8 within K=5 → TP; signal@20 → no disp → FP
    assert m["tp"] == 1 and m["fp"] == 1
    assert abs(m["precision"] - 0.5) < 1e-9
    assert m["n_displacement_starts"] == 1
    assert m["recalled_displacements"] == 1  # signal at 5 is in [8-5, 8]
    assert abs(m["recall"] - 1.0) < 1e-9
    assert m["lead_time_bars"]["mean"] == 3.0  # 8-5


def test_evaluate_all_includes_baselines():
    labels = [_lab(i, "RANGE", "zone_2") for i in range(10)]
    labels += [_lab(10, "RANGE", "zone_6")]
    labels += [_lab(i, "DISPLACEMENT", "zone_6") for i in range(11, 15)]
    labels += [_lab(i, "RANGE", "zone_7") for i in range(15, 25)]
    ev = evaluate_all_detectors(labels, K_values=(3, 5), n_random_trials=5, random_seed=0)
    assert "3" in ev["by_K"] and "5" in ev["by_K"]
    assert "rare_zone_entry" in ev["by_K"]["3"]
    assert "random_timing" in ev["by_K"]["3"]
    assert "persistent_zone_entry" in ev["by_K"]["3"]
