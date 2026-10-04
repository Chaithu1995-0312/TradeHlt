"""Unit tests for CRT×Zone cross-tab metrics (synthetic labels)."""
from __future__ import annotations

from research.zone_mapping.crt_zone_crosstab import (
    BarJointLabel,
    compute_crt_zone_crosstab,
    crosstab_to_markdown,
)


def _lab(i: int, state: str, zone: str, action: str = "NONE") -> BarJointLabel:
    return BarJointLabel(
        timestamp=str(i),
        candle_index=i,
        crt_state=state,
        zone_id=zone,
        cluster_score=0.7,
        passed=True,
        crt_action=action,
    )


def test_crosstab_counts_lift_and_entries():
    # RANGE mostly zone_a; SWEEP mostly zone_b
    labels = (
        [_lab(i, "RANGE", "zone_a") for i in range(80)]
        + [_lab(100 + i, "RANGE", "zone_b") for i in range(20)]
        + [_lab(200 + i, "SWEEP", "zone_b") for i in range(50)]
        + [_lab(300 + i, "SWEEP", "zone_a") for i in range(10)]
        + [_lab(400, "EXECUTION", "zone_b", action="TRADE_OPENED")]
    )
    xt = compute_crt_zone_crosstab(
        labels, registry_zone_ids=["zone_a", "zone_b"]
    )
    assert xt["n_bars"] == len(labels)
    assert xt["state_marginal"]["RANGE"] == 100
    assert xt["state_marginal"]["SWEEP"] == 60
    # P(zone_a | RANGE) = 0.8
    assert abs(xt["p_zone_given_state"]["RANGE"]["zone_a"] - 0.8) < 1e-9
    # lift(RANGE, zone_a) = 0.8 / (90/171) > 1
    assert xt["lift_zone_given_state"]["RANGE"]["zone_a"] > 1.0
    assert xt["trade_opened"]["n"] == 1
    assert xt["trade_opened"]["zone_counts"]["zone_b"] == 1
    md = crosstab_to_markdown(xt)
    assert "P(zone | CRT state)" in md
    assert "Lift" in md
