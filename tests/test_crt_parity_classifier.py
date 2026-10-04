"""
CRT Semantic Parity mismatch classifier — behavioral floor.

Exercises scripts/research/crt_parity_classifier.py (pure, F-069 program) with
synthetic MismatchContext/episode inputs so every category code is reachable
without a live sweep run. Per E-001 (a test that cannot fail is not
enforcement): each test asserts a specific code/category, not just "no
exception raised".
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_MODULE_PATH = _REPO / "scripts" / "research" / "crt_parity_classifier.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("crt_parity_classifier", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["crt_parity_classifier"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cpc():
    if not _MODULE_PATH.exists():
        pytest.skip("crt_parity_classifier.py not present")
    return _load_module()


def _ctx(cpc, **overrides):
    kwargs = dict(
        resolver_thresholds={},
        engine_thresholds={},
        state_marginals={},
        cells_improved_by_sweep=frozenset(),
        known_geometry_divergent_pairs=frozenset(),
        engine_only_threshold_names=frozenset(),
    )
    kwargs.update(overrides)
    return cpc.MismatchContext(**kwargs)


class TestStructuralUnreachability:
    def test_execution_is_unreachable_even_at_low_n(self, cpc):
        # 5 engine bars, well below MIN_CELL_N=15 — must still classify as
        # B-UNREACHABLE-STATE (deductive, not a power-gated statistical claim).
        ctx = _ctx(cpc, state_marginals={"EXECUTION": (5, 0, 0)})
        result = cpc.classify_mismatch("EXECUTION", "RETEST", {}, ctx)
        assert result.category == "B"
        assert result.code == "B-UNREACHABLE-STATE"
        assert "score" in result.rationale

    def test_resolution_is_unreachable(self, cpc):
        ctx = _ctx(cpc, state_marginals={"RESOLUTION": (5, 0, 0)})
        result = cpc.classify_mismatch("RESOLUTION", "RANGE", {}, ctx)
        assert result.code == "B-UNREACHABLE-STATE"

    def test_expired_is_unreachable(self, cpc):
        ctx = _ctx(cpc, state_marginals={"EXPIRED": (0, 0, 0)})
        result = cpc.classify_mismatch("EXPIRED", "RANGE", {}, ctx)
        assert result.code == "B-UNREACHABLE-STATE"


class TestPowerGate:
    def test_low_n_state_is_insufficient_never_reject(self, cpc):
        ctx = _ctx(cpc, state_marginals={"SHADOW_PENDING": (14, 5, 2)})
        result = cpc.classify_mismatch("SHADOW_PENDING", "SWEEP", {}, ctx)
        assert result.category == "INSUFFICIENT"
        assert result.code == "INSUFFICIENT"
        assert result.category != "REJECT"  # the class must not exist at all

    def test_n_exactly_at_floor_is_powered(self, cpc):
        # engine_n == MIN_CELL_N (15) must NOT be flagged insufficient — the
        # gate is strictly "<", matching the pre-registration's "n >= 15" rule.
        ctx = _ctx(cpc, state_marginals={"RETEST": (15, 15, 15)})
        result = cpc.classify_mismatch("RETEST", "RETEST", {}, ctx)
        assert result.code != "INSUFFICIENT"


class TestNoCounterpart:
    def test_engine_only_threshold_in_reason_is_b_no_counterpart(self, cpc):
        ctx = _ctx(
            cpc,
            state_marginals={"RETEST": (20, 10, 3)},
            engine_only_threshold_names=frozenset({"retest_min_depth_atr_fraction"}),
        )
        episode = {"engine_transition_reason": "retest_min_depth_atr_fraction gate failed"}
        result = cpc.classify_mismatch("RETEST", "EXPANSION", episode, ctx)
        assert result.category == "B"
        assert result.code == "B-NO-COUNTERPART"
        assert result.payload["matched_threshold"] == "retest_min_depth_atr_fraction"


class TestThresholdDelta:
    def test_shared_threshold_value_mismatch_is_category_a(self, cpc):
        ctx = _ctx(
            cpc,
            state_marginals={"RETEST": (20, 10, 3)},
            resolver_thresholds={"retest_depth_max": 0.08},
            engine_thresholds={"retest_depth_max": 0.25},
        )
        result = cpc.classify_mismatch("RETEST", "EXPANSION", {}, ctx)
        assert result.category == "A"
        assert result.code == "A-THRESHOLD-DELTA"
        assert "retest_depth_max" in result.payload["delta_names"]

    def test_identical_shared_threshold_does_not_trigger(self, cpc):
        ctx = _ctx(
            cpc,
            state_marginals={"RETEST": (20, 20, 20)},
            resolver_thresholds={"retest_depth_max": 0.25},
            engine_thresholds={"retest_depth_max": 0.25},
        )
        result = cpc.classify_mismatch("RETEST", "RETEST", {}, ctx)
        assert result.code != "A-THRESHOLD-DELTA"


class TestSweepReachable:
    def test_cell_shrunk_by_sweep_is_category_a(self, cpc):
        ctx = _ctx(
            cpc,
            state_marginals={"EXPANSION": (4625, 4000, 3500)},
            cells_improved_by_sweep=frozenset({("EXPANSION", "RANGE")}),
        )
        result = cpc.classify_mismatch("EXPANSION", "RANGE", {}, ctx)
        assert result.category == "A"
        assert result.code == "A-SWEEP-REACHABLE"


class TestPhaseError:
    def test_matching_marginals_low_recall_is_phase_error(self, cpc):
        # EXPANSION-shaped: eng_n=4625, res_n=4876 (5.4% delta, within TAU_MARGINAL),
        # recall=0.27 (well below TAU_RECALL=0.60) — the program's signature case.
        ctx = _ctx(cpc, state_marginals={"EXPANSION": (4625, 4876, 1244)})
        result = cpc.classify_mismatch("EXPANSION", "RANGE", {}, ctx)
        assert result.category == "C"
        assert result.code == "C-PHASE-ERROR"
        assert result.payload["recall"] == pytest.approx(1244 / 4625)

    def test_high_recall_does_not_trigger_phase_error(self, cpc):
        ctx = _ctx(cpc, state_marginals={"EXPANSION": (4625, 4700, 4400)})
        result = cpc.classify_mismatch("EXPANSION", "RANGE", {}, ctx)
        assert result.code != "C-PHASE-ERROR"

    def test_large_marginal_delta_does_not_trigger_phase_error(self, cpc):
        # res_n far from eng_n (e.g. 1,803 vs 4,625 = 61% delta) — a volume
        # defect, not a phase defect, even though recall is also low.
        ctx = _ctx(cpc, state_marginals={"EXPANSION": (4625, 1803, 498)})
        result = cpc.classify_mismatch("EXPANSION", "RANGE", {}, ctx)
        assert result.code != "C-PHASE-ERROR"


class TestGeometry:
    def test_known_geometry_divergent_pair_is_category_c(self, cpc):
        ctx = _ctx(
            cpc,
            state_marginals={"SWEEP": (7004, 3000, 2000)},
            known_geometry_divergent_pairs=frozenset({("SWEEP", "RANGE")}),
        )
        result = cpc.classify_mismatch("SWEEP", "RANGE", {}, ctx)
        assert result.category == "C"
        assert result.code == "C-GEOMETRY"


class TestUnknownFallthrough:
    def test_no_rule_matches_is_d_unknown(self, cpc):
        ctx = _ctx(cpc, state_marginals={"SWEEP": (7004, 7100, 6900)})
        result = cpc.classify_mismatch("SWEEP", "DISPLACEMENT", {}, ctx)
        assert result.category == "D"
        assert result.code == "D-UNKNOWN"


class TestPrecedenceOrder:
    def test_structural_unreachability_beats_threshold_delta(self, cpc):
        # EXECUTION would also match a threshold-delta if we let it fall
        # through — must be caught by rule 1 first.
        ctx = _ctx(
            cpc,
            state_marginals={"EXECUTION": (5, 0, 0)},
            resolver_thresholds={"score_threshold": 0.10},
            engine_thresholds={"score_threshold": 0.45},
        )
        result = cpc.classify_mismatch("EXECUTION", "RETEST", {}, ctx)
        assert result.code == "B-UNREACHABLE-STATE"

    def test_power_gate_beats_threshold_delta(self, cpc):
        ctx = _ctx(
            cpc,
            state_marginals={"SHADOW_PENDING": (10, 5, 0)},
            resolver_thresholds={"pending_displacement_ttl_candles": 2},
            engine_thresholds={"pending_displacement_ttl_candles": 4},
        )
        result = cpc.classify_mismatch("SHADOW_PENDING", "SWEEP", {}, ctx)
        assert result.code == "INSUFFICIENT"


class TestAggregateCategories:
    def test_all_configuration_is_configuration_determination(self, cpc):
        results = [
            cpc.Classification("A", "A-THRESHOLD-DELTA", "", "", ""),
            cpc.Classification("A", "A-SWEEP-REACHABLE", "", "", ""),
        ]
        agg = cpc.aggregate_categories(results)
        assert agg["determination"] == "Configuration"

    def test_all_implementation_is_implementation_determination(self, cpc):
        results = [cpc.Classification("B", "B-UNREACHABLE-STATE", "", "", "")]
        agg = cpc.aggregate_categories(results)
        assert agg["determination"] == "Implementation"

    def test_mixed_a_and_b_is_mixed_determination(self, cpc):
        results = [
            cpc.Classification("A", "A-THRESHOLD-DELTA", "", "", ""),
            cpc.Classification("B", "B-UNREACHABLE-STATE", "", "", ""),
        ]
        agg = cpc.aggregate_categories(results)
        assert agg["determination"] == "Mixed"

    def test_any_unknown_forces_inconclusive(self, cpc):
        # Parent verdict must never exceed the weakest child (E-001E) — a
        # single D-UNKNOWN among many A's must not be smoothed over.
        results = [
            cpc.Classification("A", "A-THRESHOLD-DELTA", "", "", ""),
            cpc.Classification("A", "A-THRESHOLD-DELTA", "", "", ""),
            cpc.Classification("D", "D-UNKNOWN", "", "", ""),
        ]
        agg = cpc.aggregate_categories(results)
        assert agg["determination"] == "Inconclusive"

    def test_only_insufficient_is_inconclusive_not_configuration(self, cpc):
        results = [
            cpc.Classification("INSUFFICIENT", "INSUFFICIENT", "", "", ""),
            cpc.Classification("INSUFFICIENT", "INSUFFICIENT", "", "", ""),
        ]
        agg = cpc.aggregate_categories(results)
        assert agg["determination"] == "Inconclusive"

    def test_empty_is_inconclusive(self, cpc):
        agg = cpc.aggregate_categories([])
        assert agg["determination"] == "Inconclusive"
        assert agg["total"] == 0


def test_category_precedence_matches_module_constant(cpc):
    # Pins the documented precedence order (pre-registration doc) so a future
    # reordering is a deliberate, reviewed change, not a silent drift.
    assert cpc.CATEGORY_PRECEDENCE == (
        "B-UNREACHABLE-STATE",
        "INSUFFICIENT",
        "B-NO-COUNTERPART",
        "A-THRESHOLD-DELTA",
        "A-SWEEP-REACHABLE",
        "C-PHASE-ERROR",
        "C-GEOMETRY",
        "D-UNKNOWN",
    )


def test_min_cell_n_matches_precedent(cpc):
    assert cpc.MIN_CELL_N == 15
