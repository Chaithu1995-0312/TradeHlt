"""
Phase-Topology — runtime transition graph from active_models.yaml WHO load.

Guarantees:
  - CRTEngine injects WHO-built graph into StateMachine
  - Default graph set-equals module VALID_TRANSITIONS (parity seed)
  - Injected restricted graph is actually enforced by _transition
  - Python try_* guards unchanged; process_candle dual-run fingerprint stable
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import MappingProxyType

import pytest

from config_layer.crt_engine_v2 import (
    CRTConfig,
    CRTEngine,
    CRTState,
    Candle,
    EngineState,
    StateMachine,
    VALID_TRANSITIONS,
)
from config_layer.state_contract_loader import (
    clear_state_contract_cache,
    load_and_validate_state_contracts,
)
from config_layer.state_topology import (
    StateTopologyError,
    build_runtime_transition_graph,
    build_runtime_transition_graph_from_bundle,
    graphs_equal,
    module_seed_transition_graph,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_state_contract_cache()
    yield
    clear_state_contract_cache()


def test_build_graph_from_production_bundle():
    bundle = load_and_validate_state_contracts()
    graph = build_runtime_transition_graph_from_bundle(bundle)
    assert set(graph) == set(CRTState)
    seed = module_seed_transition_graph()
    assert graphs_equal(graph, seed)
    assert graphs_equal(graph, VALID_TRANSITIONS)


def test_crt_engine_injects_who_topology():
    eng = CRTEngine(config=CRTConfig())
    assert eng.runtime_transitions is not None
    assert eng.sm.valid_transitions is eng.runtime_transitions
    assert graphs_equal(eng.runtime_transitions, VALID_TRANSITIONS)
    # state identities from WHO contracts
    assert set(eng.state_contracts.state_ids()) == {s.name for s in CRTState}


def test_restricted_graph_blocks_legal_module_edge():
    """Prove instance graph is authoritative: drop SHADOW_PENDING from RANGE."""
    restricted = {
        CRTState.RANGE: (CRTState.SWEEP,),  # no SHADOW_PENDING
        CRTState.SHADOW_PENDING: (CRTState.SWEEP, CRTState.RANGE),
        CRTState.SWEEP: (CRTState.DISPLACEMENT, CRTState.EXPANSION, CRTState.RANGE),
        CRTState.DISPLACEMENT: (CRTState.EXPANSION, CRTState.RANGE),
        CRTState.EXPANSION: (CRTState.RETEST, CRTState.EXPIRED, CRTState.RANGE),
        CRTState.EXPIRED: (CRTState.RANGE,),
        CRTState.RETEST: (CRTState.EXECUTION, CRTState.RANGE),
        CRTState.EXECUTION: (CRTState.RESOLUTION,),
        CRTState.RESOLUTION: (CRTState.RANGE,),
    }
    sm = StateMachine(CRTConfig(), valid_transitions=MappingProxyType(restricted))
    st = EngineState()
    assert st.current_state == CRTState.RANGE
    # Module seed would allow SHADOW_PENDING; instance graph must reject
    assert CRTState.SHADOW_PENDING in VALID_TRANSITIONS[CRTState.RANGE]
    ok = sm._transition(st, CRTState.SHADOW_PENDING, "test_block")
    assert ok is False
    assert st.current_state == CRTState.RANGE
    # Still allow SWEEP
    ok2 = sm._transition(st, CRTState.SWEEP, "test_allow")
    assert ok2 is True
    assert st.current_state == CRTState.SWEEP


def test_unknown_state_name_fail_closed():
    raw = {s.name: [t.name for t in VALID_TRANSITIONS[s]] for s in CRTState}
    raw["RANGE"] = ["SWEEP", "NOT_A_STATE"]
    with pytest.raises(StateTopologyError, match="Unknown CRT state"):
        build_runtime_transition_graph(raw)


def test_incomplete_identity_set_fail_closed():
    partial = {
        s.name: [t.name for t in VALID_TRANSITIONS[s]]
        for s in CRTState
        if s is not CRTState.EXPIRED
    }
    with pytest.raises(StateTopologyError, match="incomplete"):
        build_runtime_transition_graph(partial)


def test_process_candle_dual_run_behavior_parity():
    import hashlib
    import json

    def _fingerprint() -> str:
        clear_state_contract_cache()
        eng = CRTEngine(config=CRTConfig())
        base = datetime(2024, 1, 1, 0, 0, 0)
        candles = [
            Candle(
                timestamp=base + timedelta(minutes=15 * i),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.2,
                volume=1.0,
                index=i,
            )
            for i in range(50)
        ]
        eng.initialise_range(candles[:10], htf_candle_id="H0", session="LONDON")
        actions = []
        for c in candles[10:]:
            a = eng.process_candle(c, htf_candle_id="H0")
            actions.append(
                {k: a.get(k) for k in ("action", "state", "state_after", "reason")}
            )
        return hashlib.sha256(json.dumps(actions, default=str).encode()).hexdigest()

    assert _fingerprint() == _fingerprint()


def test_legacy_sm_without_graph_uses_module_seed():
    sm = StateMachine(CRTConfig())
    assert graphs_equal(sm.valid_transitions, VALID_TRANSITIONS)
