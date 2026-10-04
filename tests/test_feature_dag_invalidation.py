"""Feature-DAG invalidation-engine floor — the durable gate on the bottom-up invariants:
ordering (no dependent certified before dependencies), hash binding (validate-against-promoted),
and contagious transitive STALE-invalidation on upstream promotion/change.

Pure planners are exercised on synthetic state so the real ledger is never mutated.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_CERT = _REPO / "scripts" / "governance" / "feature_dag_certify.py"
_DAG = _REPO / "scripts" / "analysis" / "feature_dag_layers.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mods():
    if not _CERT.exists() or not _DAG.exists():
        pytest.skip("certification engine not present")
    dagmod = _load(_DAG, "feature_dag_layers")
    cert = _load(_CERT, "feature_dag_certify")
    return cert, dagmod.build_dag()


def _witness(cert, dag):
    return cert._formula_witnesses(dag)


def test_formula_hash_deterministic_and_sensitive(mods):
    cert, dag = mods
    w = _witness(cert, dag)
    h1 = cert.compute_formula_hash("atr", dag, w)
    h2 = cert.compute_formula_hash("atr", dag, w)
    assert h1 == h2 and len(h1) == 64
    # changing the witness (the intended-quantity/formula identity) changes the hash
    w2 = dict(w); w2["atr"] = w["atr"] + " (Wilder instead of SMA)"
    assert cert.compute_formula_hash("atr", dag, w2) != h1


def test_dependency_contract_hash_binds_to_promoted_dep_hash(mods):
    cert, dag = mods
    w = _witness(cert, dag)
    fh = cert.compute_formula_hash("ema_spread", dag, w)
    promoted_a = {"ema_fast": "AAA", "ema_slow": "BBB", "atr": "OLD_ATR_HASH"}
    promoted_b = {"ema_fast": "AAA", "ema_slow": "BBB", "atr": "NEW_ATR_HASH"}
    dch_a = cert.compute_dep_contract_hash("ema_spread", dag, fh, promoted_a)
    dch_b = cert.compute_dep_contract_hash("ema_spread", dag, fh, promoted_b)
    assert dch_a != dch_b, "changing a dep's promoted formula_hash must change the dependent's contract hash"


def test_ordering_gate_refuses_certify_with_unpromoted_dep(mods):
    cert, dag = mods
    w = _witness(cert, dag)
    # ema_spread's deps (ema_fast/ema_slow/atr) are NOT promoted → certify must refuse
    state = {"ema_spread": {"feature_name": "ema_spread", "layer": 2,
                            "frontier_state": "UNKNOWN", "blocking_dependencies": ["atr", "ema_fast"]}}
    with pytest.raises(cert.OrderingViolation):
        cert.plan_certify("ema_spread", state, dag, w)


def test_ordering_gate_allows_certify_when_deps_promoted(mods):
    cert, dag = mods
    w = _witness(cert, dag)
    state = {"ema_spread": {"feature_name": "ema_spread", "layer": 2,
                            "frontier_state": "UNKNOWN", "blocking_dependencies": []}}
    ev = cert.plan_certify("ema_spread", state, dag, w)
    assert ev["event"] == "CERTIFIED" and ev["formula_hash"] and ev["dependency_contract_hash"]


def test_transitive_downstream_of_atr(mods):
    cert, dag = mods
    ds = set(cert.transitive_downstream("atr", dag))
    # atr feeds the whole direct-derived + several structural/context features.
    # volatility_regime is deliberately NOT in this list (was, pre-2026-07-19): the M14B
    # correction (feature_dag_layers.py, "edge tightened from the structural roots
    # [close, high, low] to the direct registered producer true_range") made volatility_regime
    # depend on true_range directly, matching ontology FM-050 exactly -- atr and
    # volatility_regime are now SIBLINGS under true_range, not parent/child. Stale assertion
    # fixed 2026-07-31 (Semantic Layer Certification Audit, Tier 1) after widening this
    # session's verification set surfaced it; unrelated to the day's DAG edits (git diff on
    # feature_dag_layers.py touches candle_range/macd_hist_raw/macd_hist_z/
    # displacement_atr_ratio only, never volatility_regime's deps).
    for expected in ("ema_spread", "momentum_score", "disp_strength", "volatility_ratio",
                     "retest_depth", "liquidity_distance", "liquidity_pressure_score"):
        assert expected in ds, f"{expected} missing from atr's transitive downstream"
    assert "atr" not in ds
    assert "volatility_regime" not in ds, (
        "volatility_regime should be a SIBLING of atr under true_range post-M14B, not a "
        "downstream -- if this now fails, the DAG dependency reverted, not the test"
    )


def test_transitive_downstream_of_true_range_includes_atr_and_volatility_regime(mods):
    """true_range is the actual shared ancestor of atr and volatility_regime post-M14B."""
    cert, dag = mods
    ds = set(cert.transitive_downstream("true_range", dag))
    assert "atr" in ds
    assert "volatility_regime" in ds


def test_cascade_stale_marks_certified_downstream(mods):
    cert, dag = mods
    # synthetic: ema_spread + momentum_score already CERTIFIED, then atr changes
    state = {
        "ema_spread": {"feature_name": "ema_spread", "frontier_state": "CERTIFIED"},
        "momentum_score": {"feature_name": "momentum_score", "frontier_state": "PROMOTED_PRODUCTION"},
        "rsi_14": {"feature_name": "rsi_14", "frontier_state": "CERTIFIED"},  # not downstream of atr
    }
    stale = cert.cascade_stale("atr", state, dag, trigger="PROMOTED")
    staled = {s["feature_name"] for s in stale}
    assert "ema_spread" in staled and "momentum_score" in staled
    assert "rsi_14" not in staled, "rsi_14 does not depend on atr — must not be staled"
    for s in stale:
        assert s["event"] == "INVALIDATED_STALE" and s["frontier_state"] == "STALE"
        assert s["upstream_trigger"] == "atr"


def test_promote_requires_certified_state(mods):
    cert, dag = mods
    w = _witness(cert, dag)
    state = {"atr": {"feature_name": "atr", "layer": 1, "frontier_state": "UNKNOWN"}}
    with pytest.raises(cert.OrderingViolation):
        cert.plan_promote("atr", state, dag, w, "src/governance/promotion_manager.py")


def test_promote_rejects_non_code_authority(mods):
    cert, dag = mods
    w = _witness(cert, dag)
    state = {"atr": {"feature_name": "atr", "layer": 1, "frontier_state": "CERTIFIED",
                     "formula_hash": "x", "dependency_contract_hash": "y"}}
    with pytest.raises(cert.OrderingViolation):
        cert.plan_promote("atr", state, dag, w, "docs/governance/feature_certification_ledger.jsonl")
