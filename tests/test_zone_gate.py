"""
Tests for the ZoneGate scoring kernel and BitNetZoneGate.check() return contract.

SCOPE / HISTORY
---------------
This file previously targeted a ``zone_gate.ZoneGate`` class that no longer exists.
Eight of its nine tests were inert — five behind an ``ImportError`` guard against the
removed class, three behind hard ``@pytest.mark.skip`` for removed APIs
(``runner.bitnet``, the old ``EngineRunner`` ctor, ``zone_gate_engine.compute``). The
only executing test exercised ``unified_replay_harness._derive_symbol_from_data_path``,
which is not ZoneGate code at all; it now lives in
``tests/test_unified_replay_harness.py``. The file could therefore never go red.

Rewritten to cover the surface that actually exists, and deliberately scoped to the
gaps the sibling zone tests leave open:

  · ``compute_gaussian_score`` — the scoring kernel. Had NO direct unit test anywhere
    in the suite despite being the math every zone decision rests on.
  · ``BitNetZoneGate.check()`` early-return branches, asserted on ``top_scores``
    specifically, because that is the ONLY field the live spine consumes
    (``engines.zone_cluster_score.score_zone_cluster``). Its presence or absence
    decides whether a branch passes or blocks downstream.

Already covered elsewhere, NOT duplicated here: top_k slicing + cluster spread
(``test_zone_gate_top_k.py``), underpowered ``allowed`` semantics
(``test_zone_gate_min_samples.py``), force_pass/counters/soft score
(``test_zone_gate_instrumentation.py``), manifest parity
(``test_zone_manifest_runtime_parity.py``), mapper parity
(``test_historical_zone_mapper*.py``).
"""

import math

import pytest

from bitnet.zone_cosine_searcher import compute_gaussian_score
from engines.live_engine import BitNetZoneGate


# ── Fixture helpers ───────────────────────────────────────────────────────────

def _zone(mu, sigma, weights, threshold: float = 0.5, weight: float = 100.0) -> dict:
    """Build a zone dict in the runtime (v2_gaussian) schema."""
    return {
        "mu":        list(mu),
        "sigma":     list(sigma),
        "weights":   list(weights),
        "threshold": threshold,
        "weight":    weight,
    }


def _uniform_zone(n: int = 35, *, weight: float = 100.0, threshold: float = 0.5) -> dict:
    """Unit-variance zone centred at the origin — score reduces to exp(-0.5·Σx²/n)."""
    return _zone([0.0] * n, [1.0] * n, [1.0 / n] * n, threshold=threshold, weight=weight)


# ── The scoring kernel ────────────────────────────────────────────────────────

class TestComputeGaussianScore:
    """score = Σ wₖ·exp(−½·((xₖ−μₖ)/σₖ)²) / Σ wₖ  ∈ [0, 1]"""

    def test_vector_at_centroid_scores_one(self):
        """Every z=0 → every exp term is 1.0 → normalised score is exactly 1.0."""
        zone = _uniform_zone(n=10)
        assert compute_gaussian_score([0.0] * 10, zone) == pytest.approx(1.0)

    def test_matches_hand_computed_identity(self):
        """Two dims, unequal weights — pin the exact formula, not just monotonicity."""
        zone = _zone(mu=[0.0, 10.0], sigma=[1.0, 2.0], weights=[0.25, 0.75])
        # z0 = (1-0)/1 = 1.0        → exp(-0.5)
        # z1 = (11-10)/2 = 0.5      → exp(-0.125)
        expected = (0.25 * math.exp(-0.5) + 0.75 * math.exp(-0.125)) / 1.0
        assert compute_gaussian_score([1.0, 11.0], zone) == pytest.approx(expected)

    def test_weights_need_not_sum_to_one(self):
        """Normalisation is by Σw, so unnormalised weights give the same answer."""
        a = _zone(mu=[0.0, 10.0], sigma=[1.0, 2.0], weights=[0.25, 0.75])
        b = _zone(mu=[0.0, 10.0], sigma=[1.0, 2.0], weights=[25.0, 75.0])
        v = [1.0, 11.0]
        assert compute_gaussian_score(v, a) == pytest.approx(compute_gaussian_score(v, b))

    def test_score_decreases_with_distance(self):
        zone = _uniform_zone(n=5)
        near = compute_gaussian_score([0.1] * 5, zone)
        far = compute_gaussian_score([3.0] * 5, zone)
        assert 1.0 > near > far > 0.0

    def test_zeroed_weight_dim_is_ignored(self):
        """A zero-weighted dim cannot influence the score however far off it is.

        This is the property the live registry depends on: all 8 zones zero the 13
        absolute-price/volume dims, so raw price scale must not enter the score.
        """
        zone = _zone(mu=[0.0, 0.0], sigma=[1.0, 1.0], weights=[1.0, 0.0])
        assert compute_gaussian_score([0.0, 0.0], zone) == pytest.approx(
            compute_gaussian_score([0.0, 9999.0], zone)
        )

    def test_result_is_bounded_to_unit_interval(self):
        zone = _uniform_zone(n=8)
        for vec in ([0.0] * 8, [1e6] * 8, [-1e6] * 8):
            assert 0.0 <= compute_gaussian_score(vec, zone) <= 1.0

    # ── Degenerate / guard paths ──────────────────────────────────────────────

    def test_zero_sigma_is_clamped_not_divide_by_zero(self):
        """sigma is clamped to 1e-9 — an off-centroid vector collapses to ~0, not ZeroDivisionError."""
        zone = _zone(mu=[0.0], sigma=[0.0], weights=[1.0])
        assert compute_gaussian_score([0.0], zone) == pytest.approx(1.0)
        assert compute_gaussian_score([1.0], zone) == pytest.approx(0.0)

    def test_empty_mu_returns_zero(self):
        assert compute_gaussian_score([1.0, 2.0], _zone([], [], [])) == 0.0

    def test_zero_total_weight_returns_zero(self):
        zone = _zone(mu=[0.0, 0.0], sigma=[1.0, 1.0], weights=[0.0, 0.0])
        assert compute_gaussian_score([0.0, 0.0], zone) == 0.0

    def test_under_length_feature_vector_returns_zero(self):
        """Too few features is a contract violation → 0.0, never a partial score."""
        zone = _uniform_zone(n=10)
        assert compute_gaussian_score([0.0] * 9, zone) == 0.0

    def test_over_length_feature_vector_is_truncated(self):
        """Extra trailing dims are ignored (features[:n]), not an error."""
        zone = _uniform_zone(n=4)
        exact = compute_gaussian_score([0.0] * 4, zone)
        padded = compute_gaussian_score([0.0] * 4 + [123.0, 456.0], zone)
        assert padded == pytest.approx(exact) == pytest.approx(1.0)

    def test_legacy_dict_form_mu_sigma_weights(self):
        """Legacy ZoneCandidate.to_dict() form (keyed by feature name) still scores."""
        zone = {
            "mu":        {"a": 0.0, "b": 10.0},
            "sigma":     {"a": 1.0, "b": 2.0},
            "weights":   {"a": 0.25, "b": 0.75},
            "threshold": 0.5,
        }
        expected = 0.25 * math.exp(-0.5) + 0.75 * math.exp(-0.125)
        assert compute_gaussian_score([1.0, 11.0], zone) == pytest.approx(expected)


# ── check() return contract ───────────────────────────────────────────────────

class TestCheckReturnContract:
    """``top_scores`` is the only field the live spine reads — pin it per branch.

    Downstream (``zone_cluster_score._model_fn``): a present, long-enough
    ``top_scores`` is cluster-aggregated; otherwise the branch falls through to
    ``result.get("score", 0.5)``. So the *score* of a ``top_scores``-less branch is
    what actually decides pass/block, and the branches disagree deliberately.
    """

    def test_scoring_branch_emits_top_scores_capped_at_top_n(self):
        gate = BitNetZoneGate(
            zones=[_uniform_zone() for _ in range(5)],
            config={"zone_min_samples": 50, "zone_gate_top_k": 3},
        )
        result = gate.check([0.0] * 35)
        assert len(result["top_scores"]) == 3
        assert result["top_scores"] == sorted(result["top_scores"], reverse=True)

    def test_disabled_gate_omits_top_scores_and_scores_one(self):
        """No top_scores → falls through to score=1.0 → passes downstream."""
        result = BitNetZoneGate(enabled=False).check([0.0] * 35)
        assert result["reason"] == "gate_disabled"
        assert "top_scores" not in result
        assert result["score"] == 1.0

    def test_underpowered_emits_empty_top_scores_and_scores_one(self):
        """Empty list is falsy → falls through to score=1.0 → passes downstream."""
        gate = BitNetZoneGate(
            zones=[_uniform_zone(weight=10.0)],
            config={"zone_min_samples": 50},
        )
        result = gate.check([0.0] * 35)
        assert result["reason"] == "underpowered_zone_registry"
        assert result["top_scores"] == []
        assert result["score"] == 1.0

    def test_no_zones_omits_top_scores_and_scores_zero(self):
        """The asymmetric branch: score 0.0, so it BLOCKS downstream.

        Regression pin. The other two bypass branches score 1.0 and pass; this one
        scores 0.0, which fails ``zone_cluster_threshold`` (0.25 on the active
        config) and blocks every candle. See the reason-string test below.
        """
        result = BitNetZoneGate(zones=[], config={"zone_min_samples": 50}).check([0.0] * 35)
        assert "top_scores" not in result
        assert result["score"] == 0.0

    def test_empty_registry_reason_string_matches_its_behaviour(self):
        """The reason string must not claim the opposite of what the branch does.

        Guards the mislabel class directly: this branch blocks, so its reason may
        not advertise fail-open. Paired with the score assertion above so the two
        can never drift apart again.
        """
        result = BitNetZoneGate(zones=[], config={"zone_min_samples": 50}).check([0.0] * 35)
        assert result["score"] == 0.0, "precondition: this branch blocks"
        assert "fail_open" not in result["reason"], (
            f"reason {result['reason']!r} advertises fail-open but score "
            f"{result['score']} blocks at any positive threshold"
        )
