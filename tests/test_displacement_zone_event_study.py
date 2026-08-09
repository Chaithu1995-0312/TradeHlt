"""Unit tests for DISPLACEMENT lead/lag zone event study (synthetic)."""
from __future__ import annotations

from research.zone_mapping.crt_zone_crosstab import BarJointLabel
from research.zone_mapping.displacement_zone_event_study import (
    compute_displacement_zone_event_study,
    find_displacement_starts,
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


def test_find_displacement_starts_and_rare_entry_before():
    # 5 RANGE zone_2, then enter zone_6 at i=5, DISPLACEMENT starts at i=8
    labels = [_lab(i, "RANGE", "zone_2") for i in range(5)]
    labels += [_lab(i, "RANGE", "zone_6") for i in range(5, 8)]
    labels += [_lab(i, "DISPLACEMENT", "zone_6") for i in range(8, 12)]
    labels += [_lab(i, "EXPANSION", "zone_2") for i in range(12, 15)]
    # pad so window exists
    starts = find_displacement_starts(labels)
    assert len(starts) == 1
    assert starts[0].t0_index == 8
    es = compute_displacement_zone_event_study(labels, half_window=5)
    assert es["n_displacement_starts"] == 1
    # first entry into zone_6 at lag = 5-8 = -3
    z6 = es["rare_entry_timing"]["zone_6"]
    assert z6["n"] == 1
    assert z6["mean_lag"] == -3.0
    # at lag 0 should be in zone_6
    assert es["lag_profiles"]["0"]["p_zone_6"] == 1.0
    assert es["lag_profiles"]["-3"]["p_rare_union"] == 1.0
