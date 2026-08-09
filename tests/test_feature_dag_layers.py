"""Feature-DAG layer-spine floor — the durable gate that the bottom-up certification
order stays a valid, grounded, layer-monotone DAG covering all 38 canonical features.

Evidence twin: docs/governance/feature_dag_layers-*.json (+ .LATEST.json). This floor
recomputes the DAG on every pytest invocation (pure structure — no market data).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_PROBE = _REPO / "scripts" / "analysis" / "feature_dag_layers.py"
from features.feature_schema import CANONICAL_FEATURE_DIM  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location("feature_dag_layers", _PROBE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["feature_dag_layers"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def dag():
    if not _PROBE.exists():
        pytest.skip("feature_dag_layers probe not present")
    return _load().build_dag()


def test_is_acyclic_and_grounded(dag):
    assert dag["is_dag"], f"feature DAG has cycles: {dag['cycle_nodes']}"
    assert not dag["ungrounded_nodes"], f"nodes not grounded in raw OHLC: {dag['ungrounded_nodes']}"
    assert not dag["undefined_dependency_nodes"], (
        f"edges reference undefined nodes: {dag['undefined_dependency_nodes']}"
    )


def test_all_canonical_features_covered(dag):
    """Was pinned to the literal 38 (schema v3.0); de-literalized to CANONICAL_FEATURE_DIM so
    this floor tracks the live schema instead of silently drifting stale across a dim migration
    (schema v4.0, 2026-07-22, raised CANONICAL_FEATURE_DIM to 39 — Semantic Layer Certification
    Audit, Tier 1 item 3)."""
    assert dag["n_canonical_covered"] == CANONICAL_FEATURE_DIM, dag["missing_canonical"]
    assert not dag["missing_canonical"]


def test_layers_are_monotone(dag):
    """Every dependency edge must go from a lower-or-equal layer to a higher-or-equal one —
    the bottom-up certification order is only valid if deps never sit above their consumer."""
    assert not dag["layer_monotonicity_violations"], dag["layer_monotonicity_violations"]


def test_known_bugfixes_present(dag):
    """The two fc05-DEPS data bugs must stay fixed."""
    assert dag["bugfixes_applied"]["disp_strength_body_size_close_edge"], (
        "disp_strength must depend on body_size + close (ontology FM-020), not just atr"
    )
    assert dag["bugfixes_applied"]["double_sweep_single_entry"], "double_sweep must be a single edge entry"


def test_ontology_crosscheck_only_known_rollups(dag):
    """The DAG may differ from ontology depends_on ONLY by rolling finer structural leaves up to
    their producing node. Any NEW divergence on a registered feature must trip this floor.

    v4.0 re-sync (Semantic Layer Certification Audit, Tier 1 item 1): renaming the DAG's
    `wick_size` node to `candle_range` surfaced five pre-existing divergences that were previously
    masked by the alias lookup silently matching nothing for these features. All five are the same
    documented pattern as the original four -- ontology `structural_states` entries declare their
    finer raw-price/raw-swing-reference dependencies (`high`/`low`/`close`/
    `last_swing_high_price`/`last_swing_low_price`), which this DAG rolls up to the producing
    `swing_high`/`swing_low` nodes -- not a new kind of drift."""
    allowed = {
        "retest_depth", "momentum_score", "liquidity_distance", "displacement_retrace",
        # newly surfaced by the v4.0 candle_range rename; same rollup pattern as the four above
        "momentum_score_atr", "higher_high", "lower_low", "break_of_structure", "liquidity_sweep",
    }
    unexpected = [x["feature"] for x in dag["ontology_crosscheck"] if x["feature"] not in allowed]
    assert not unexpected, f"new ontology<->DAG edge divergence on registered features: {unexpected}"


def test_l0_l1_ordering_for_bottom_up(dag):
    """Sanity of the certification frontier: candle primitives (L0) below rolling indicators (L1)
    below direct-derived (L2); atr depends on true_range (both certifiable before ema_spread)."""
    layer = {n["name"]: n["layer"] for n in dag["nodes"]}
    assert layer["true_range"] == 0 and layer["atr"] == 1
    assert layer["ema_spread"] == 2 and layer["momentum_score"] == 2
    # the L2 pair sits strictly above their L1 ATR dependency in topo order
    topo = {n["name"]: n["topo_index"] for n in dag["nodes"]}
    assert topo["true_range"] < topo["atr"] < topo["ema_spread"]
    assert topo["atr"] < topo["momentum_score"]
