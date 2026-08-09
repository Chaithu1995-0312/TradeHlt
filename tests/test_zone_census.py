"""Unit tests for zone census metrics (synthetic labels — no full corpus)."""
from __future__ import annotations

from research.zone_mapping.zone_census import (
    BarZoneLabel,
    compute_zone_census,
    census_to_markdown,
)


def test_census_occupancy_coverage_dwell_transitions():
    # AAA BBB A — zone_a: 4 bars, zone_b: 3 bars; dwells a:[3,1] b:[3]
    seq = ["zone_a"] * 3 + ["zone_b"] * 3 + ["zone_a"]
    labels = [
        BarZoneLabel(timestamp=str(i), best_zone_id=z, cluster_score=0.5 + 0.1 * (z == "zone_a"), passed=True)
        for i, z in enumerate(seq)
    ]
    c = compute_zone_census(labels, registry_zone_ids=["zone_a", "zone_b", "zone_c"])
    assert c["n_bars"] == 7
    assert c["per_zone"]["zone_a"]["n_bars"] == 4
    assert abs(c["per_zone"]["zone_a"]["coverage_pct"] - 100.0 * 4 / 7) < 1e-9
    assert c["per_zone"]["zone_b"]["n_bars"] == 3
    assert c["per_zone"]["zone_c"]["n_bars"] == 0
    # dwells
    assert c["per_zone"]["zone_a"]["n_dwells"] == 2
    assert abs(c["per_zone"]["zone_a"]["mean_dwell_length"] - 2.0) < 1e-9  # (3+1)/2
    assert c["per_zone"]["zone_b"]["mean_dwell_length"] == 3.0
    # transition a->b once, b->a once among consecutive
    order = c["transition_matrix"]["order"]
    ia, ib = order.index("zone_a"), order.index("zone_b")
    counts = c["transition_matrix"]["counts"]
    assert counts[ia][ib] == 1
    assert counts[ib][ia] == 1
    assert counts[ia][ia] == 2  # a-a within first run of 3
    # mean score for zone_a = 0.6
    assert abs(c["per_zone"]["zone_a"]["mean_cluster_score"] - 0.6) < 1e-9
    md = census_to_markdown(c)
    assert "zone_a" in md and "Transition matrix" in md
