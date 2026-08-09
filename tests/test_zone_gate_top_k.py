"""
Focused test for the config-first zone-gate aggregation knobs:
``engine_runner.zone_gate = {top_k, cluster_min_n, cluster_spread_max}``.

Asserts the knobs flow through and that the defaults {3, 2, 0.15} reproduce the
incumbent behaviour (the byte-parity guarantee proven on BNBUSDT + SOLUSDT). See
the config-first migration of the zone-gate top-k cluster aggregation.
"""
from __future__ import annotations

from engines.live_engine import BitNetZoneGate
from engines.zone_gate_engine import compute_weighted_cluster_score


def _zone(zid: str, mu0: float, weight: float = 100.0) -> dict:
    """Minimal list-form zone (compute_gaussian_score positional path)."""
    return {
        "id":        zid,
        "mu":        [mu0, mu0, mu0],
        "sigma":     [0.5, 0.5, 0.5],
        "weights":   [1.0, 1.0, 1.0],
        "threshold": 0.7,
        "weight":    weight,   # keeps the registry above the underpowered floor
    }


def _gate(top_k: int | None, n_zones: int = 5) -> BitNetZoneGate:
    zones = [_zone(f"z{i}", mu0=0.1 * i) for i in range(n_zones)]
    cfg: dict = {"zone_min_samples": 0}
    if top_k is not None:
        cfg["zone_gate_top_k"] = top_k
    return BitNetZoneGate(zones=zones, config=cfg)


# ── top_k flows into check().top_scores ──────────────────────────────────────

def test_top_n_slices_top_scores():
    res = _gate(top_k=2, n_zones=5).check([0.0] * 11)
    assert len(res["top_scores"]) == 2


def test_top_n_capped_by_zone_count():
    res = _gate(top_k=10, n_zones=4).check([0.0] * 11)
    assert len(res["top_scores"]) == 4


def test_top_scores_are_sorted_descending():
    res = _gate(top_k=3, n_zones=5).check([0.0] * 11)
    scores = res["top_scores"]
    assert scores == sorted(scores, reverse=True)


# ── default = historical 3 (byte-parity for standalone callers) ──────────────

def test_default_top_n_is_three():
    gate = _gate(top_k=None, n_zones=5)   # no override → historical default
    res = gate.check([0.0] * 11)
    assert gate._top_n == 3
    assert len(res["top_scores"]) == 3


# ── cluster_spread_max threads through compute_weighted_cluster_score ─────────

def test_cluster_spread_max_param_admits_wider_cluster():
    # spread 0.40 — rejected at the default boundary, admitted when widened.
    assert compute_weighted_cluster_score([0.9, 0.5], spread_max=0.15) == 0.0
    assert compute_weighted_cluster_score([0.9, 0.5], spread_max=0.5) > 0.0


def test_cluster_spread_max_default_preserves_incumbent_boundary():
    # default spread_max=0.15 reproduces the historical reject boundary exactly.
    assert compute_weighted_cluster_score([0.9, 0.5]) == 0.0          # spread 0.40 > 0.15
    assert compute_weighted_cluster_score([0.80, 0.70]) > 0.0         # spread 0.10 < 0.15
