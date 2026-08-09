"""
Tests for BitNetZoneGate underpowered-registry auto-bypass.

When the total training sample count (sum of zone ``weight`` fields) is below
``zone_min_samples``, the gate must auto-bypass with reason
"underpowered_zone_registry" rather than producing spurious rejections from a
cross-instrument or bootstrap registry.
"""

import pytest
from engines.live_engine import BitNetZoneGate


# ── Minimal zone fixture helpers ──────────────────────────────────────────────

def _make_zone(weight: float, threshold: float = 0.5) -> dict:
    """Return a minimal valid zone dict with the given training-sample weight."""
    n = 35
    return {
        "mu":        [0.0] * n,
        "sigma":     [1.0] * n,   # unit variance → Gaussian score ≈ exp(-0.5 * x²)
        "weights":   [1.0 / n] * n,
        "threshold": threshold,
        "weight":    weight,
    }


def _make_tight_zone(weight: float, threshold: float = 0.5) -> dict:
    """Zone centred at origin with tight sigma — scores near-zero for distant vectors."""
    n = 35
    return {
        "mu":        [0.0] * n,
        "sigma":     [0.01] * n,  # very tight: any non-zero feature → low score
        "weights":   [1.0 / n] * n,
        "threshold": threshold,
        "weight":    weight,
    }


# ── Underpowered bypass tests ─────────────────────────────────────────────────

class TestUnderpoweredBypass:
    """Gate with total samples < zone_min_samples must always allow."""

    def test_single_zone_weight_below_threshold_bypasses(self):
        """weight=19 < zone_min_samples=50 → auto-bypass on any feature vector."""
        gate = BitNetZoneGate(
            zones=[_make_tight_zone(weight=19.0)],
            config={"zone_min_samples": 50},
        )
        assert gate._underpowered is True
        result = gate.check([0.0] * 35)
        assert result["allowed"] is True
        assert result["reason"] == "underpowered_zone_registry"
        assert result["score"] == 1.0

    def test_bypass_also_fires_for_distant_vector(self):
        """Even a vector far from the zone centroid passes when underpowered."""
        gate = BitNetZoneGate(
            zones=[_make_tight_zone(weight=5.0, threshold=0.5)],
            config={"zone_min_samples": 50},
        )
        result = gate.check([999.0] * 35)
        assert result["allowed"] is True
        assert result["reason"] == "underpowered_zone_registry"

    def test_multi_zone_total_below_threshold_bypasses(self):
        """Three zones each with weight=10 → total=30 < 50 → bypass."""
        zones = [_make_tight_zone(weight=10.0) for _ in range(3)]
        gate = BitNetZoneGate(
            zones=zones,
            config={"zone_min_samples": 50},
        )
        assert gate._underpowered is True
        result = gate.check([0.0] * 35)
        assert result["allowed"] is True
        assert result["reason"] == "underpowered_zone_registry"

    def test_default_min_samples_is_50(self):
        """Default zone_min_samples=50 used when config omitted."""
        gate = BitNetZoneGate(zones=[_make_tight_zone(weight=19.0)])
        # weight=19 < default 50 → underpowered
        assert gate._underpowered is True

    def test_weight_exactly_at_threshold_not_underpowered(self):
        """weight == zone_min_samples → NOT underpowered (strict less-than)."""
        gate = BitNetZoneGate(
            zones=[_make_tight_zone(weight=50.0)],
            config={"zone_min_samples": 50},
        )
        assert gate._underpowered is False


# ── Powered registry enforces threshold ──────────────────────────────────────

class TestPoweredRegistryEnforces:
    """Gate with total samples >= zone_min_samples must evaluate normally."""

    def test_powered_registry_allows_close_vector(self):
        """Vector at zone centroid [0,0,...] → high Gaussian score → allowed."""
        gate = BitNetZoneGate(
            zones=[_make_zone(weight=60.0, threshold=0.5)],
            config={"zone_min_samples": 50},
        )
        assert gate._underpowered is False
        result = gate.check([0.0] * 35)
        # score = exp(-0.5 * 0²) = 1.0 (all features at centroid)
        assert result["allowed"] is True
        assert result["score"] > 0.5

    def test_powered_registry_rejects_distant_vector(self):
        """Vector far from tight centroid → low Gaussian score → rejected."""
        gate = BitNetZoneGate(
            zones=[_make_tight_zone(weight=60.0, threshold=0.5)],
            config={"zone_min_samples": 50},
        )
        assert gate._underpowered is False
        result = gate.check([999.0] * 35)
        assert result["allowed"] is False
        assert result["score"] < 0.5


# ── No zones / disabled edge cases ───────────────────────────────────────────

class TestEdgeCases:
    def test_no_zones_underpowered_is_false_but_fails_closed(self):
        """Empty zone list → _underpowered=False (no zones to weigh), fails CLOSED.

        Renamed from ``..._fails_open``. The branch returns score 0.0 and omits
        ``top_scores``, so downstream (``zone_cluster_score._model_fn``) it fails any
        positive ``zone_cluster_threshold`` — it has always blocked. The old name and
        assertion asserted the opposite of the behaviour.
        """
        gate = BitNetZoneGate(zones=[], config={"zone_min_samples": 50})
        assert gate._underpowered is False
        result = gate.check([0.0] * 35)
        # fail-closed path: no zones → block
        assert result["allowed"] is False
        assert result["score"] == 0.0
        assert result["reason"] == "no_zones_fail_closed"

    def test_disabled_gate_always_allows(self):
        """Disabled gate ignores _underpowered and always allows."""
        gate = BitNetZoneGate(enabled=False)
        assert gate._underpowered is False
        result = gate.check([0.0] * 35)
        assert result["allowed"] is True
        assert result["reason"] == "gate_disabled"
