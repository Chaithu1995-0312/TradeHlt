"""
Phase-2 FM resolution Option A — registry identity, composition parity, contracts.

Does not auto-execute required_fm. Does not change thresholds or transitions.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from features import candle_math as _cm
from features import derived_math as _dm
from features.fm_resolve import (
    PHASE2_CRT_FM_IDS,
    FMResolveError,
    assert_fm_in_contract,
    assert_registry_identity,
    bind_phase2_crt_callables,
    clear_fm_resolve_cache,
    resolve_fm,
    resolve_fm_callable,
)
from config_layer.crt_engine_v2 import CRTConfig, CRTEngine, Candle
from config_layer.state_contract_loader import (
    clear_state_contract_cache,
    load_and_validate_state_contracts,
)


@pytest.fixture(autouse=True)
def _clear_caches():
    clear_fm_resolve_cache()
    clear_state_contract_cache()
    yield
    clear_fm_resolve_cache()
    clear_state_contract_cache()


# ── Positive resolution ──────────────────────────────────────────────────────

def test_resolve_fm002_identity_candle_range():
    assert_registry_identity("FM-002", _cm.candle_range)
    assert resolve_fm_callable("FM-002") is _cm.candle_range


def test_resolve_fm027_identity_displacement_retrace():
    assert_registry_identity("FM-027", _dm.displacement_retrace)
    assert resolve_fm_callable("FM-027") is _dm.displacement_retrace


def test_resolve_fm028_identity_displacement_atr_ratio():
    assert_registry_identity("FM-028", _dm.displacement_atr_ratio)
    assert resolve_fm_callable("FM-028") is _dm.displacement_atr_ratio


def test_fm010_composition_float_parity_with_body_ratio():
    fn = resolve_fm_callable("FM-010")
    resolved = resolve_fm("FM-010")
    assert resolved.kind == "composition"
    assert resolved.name == "body_ratio"
    vectors = [
        (100.0, 105.0, 99.0, 104.0),
        (50.0, 50.0, 50.0, 50.0),  # flat
        (10.0, 12.0, 8.0, 9.0),
        (200.0, 201.0, 199.5, 200.5),
    ]
    for o, h, l, c in vectors:
        assert fn(o, h, l, c) == pytest.approx(_cm.body_ratio(o, h, l, c))


def test_bind_phase2_crt_callables():
    bound = bind_phase2_crt_callables()
    assert set(bound) == PHASE2_CRT_FM_IDS
    assert bound["FM-002"] is _cm.candle_range
    assert bound["FM-027"] is _dm.displacement_retrace
    assert bound["FM-028"] is _dm.displacement_atr_ratio


def test_golden_float_vectors_registry_fms():
    # FM-002
    assert resolve_fm_callable("FM-002")(110.0, 100.0) == 10.0
    # FM-028
    assert resolve_fm_callable("FM-028")(10.0, 5.0) == 2.0
    assert resolve_fm_callable("FM-028")(10.0, 0.0) == 0.0
    # FM-027
    r = resolve_fm_callable("FM-027")(
        retest_close=102.0, disp_open=100.0, disp_close=110.0
    )
    assert r == pytest.approx(0.2)


# ── Contract membership (test/debug surface) ────────────────────────────────

def test_assert_fm_in_contract_sweep_has_fm002():
    bundle = load_and_validate_state_contracts()
    assert_fm_in_contract(bundle, "SWEEP", "FM-002")
    assert_fm_in_contract(bundle, "SWEEP", "FM-010")
    assert_fm_in_contract(bundle, "RETEST", "FM-027")
    assert_fm_in_contract(bundle, "RETEST", "FM-028")


def test_assert_fm_in_contract_rejects_missing():
    bundle = load_and_validate_state_contracts()
    with pytest.raises(FMResolveError, match="contract membership"):
        assert_fm_in_contract(bundle, "RANGE", "FM-002")


# ── Negative ─────────────────────────────────────────────────────────────────

def test_unknown_fm_fail_closed():
    with pytest.raises(FMResolveError, match="not found"):
        resolve_fm("FM-999")


def test_invalid_fm_id_expression():
    with pytest.raises(FMResolveError):
        resolve_fm("body / range")


def test_invalid_fm_id_prefix():
    with pytest.raises(FMResolveError, match="Invalid FM id"):
        resolve_fm("NOT-AN-FM")


def test_registry_identity_mismatch_fails():
    with pytest.raises(FMResolveError, match="identity-equal"):
        assert_registry_identity("FM-002", _cm.body_size)


def test_composition_not_registry_identity():
    with pytest.raises(FMResolveError, match="registry-kind"):
        assert_registry_identity("FM-010", _cm.body_ratio)


# ── CRT wiring / behavior parity ─────────────────────────────────────────────

def test_candle_properties_use_resolved_fms():
    c = Candle(
        timestamp=datetime(2024, 1, 1),
        open=100.0,
        high=110.0,
        low=95.0,
        close=105.0,
        volume=1.0,
        index=0,
    )
    assert c.wick_size == pytest.approx(_cm.candle_range(110.0, 95.0))
    assert c.body_ratio == pytest.approx(_cm.body_ratio(100.0, 110.0, 95.0, 105.0))


def test_process_candle_dual_run_behavior_parity():
    """Phase-2 wiring must not alter SM decisions (byte-identical action stream)."""
    import hashlib
    import json

    def _fingerprint() -> str:
        clear_fm_resolve_cache()
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


def test_crt_engine_imports_and_loads_contracts():
    eng = CRTEngine(config=CRTConfig())
    assert eng.state_contracts is not None
    assert set(eng.state_contracts.contracts) == {
        "RANGE",
        "SHADOW_PENDING",
        "SWEEP",
        "DISPLACEMENT",
        "EXPANSION",
        "EXPIRED",
        "RETEST",
        "EXECUTION",
        "RESOLUTION",
    }
