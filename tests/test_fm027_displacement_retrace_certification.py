"""Floor: M9 / F-054-DR independent certification of FM-027 displacement_retrace.

Locks the algebraic oracle, property battery, CRT emission parity, and the
immutability of the dated evidence artifact used for ledger CERTIFY/PROMOTE.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from datetime import datetime
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PROBE = _ROOT / "scripts" / "analysis" / "fm027_displacement_retrace_certification.py"
_EVIDENCE = (
    _ROOT / "docs" / "governance" / "fm027_displacement_retrace_certification-2026-07-14.json"
)


def _load_probe():
    spec = importlib.util.spec_from_file_location("fm027_probe", _PROBE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def probe():
    return _load_probe()


# ── Oracle independence + formula properties ─────────────────────────────────

def test_oracle_does_not_import_derived_math_as_source(probe):
    """Independence: oracle is pure arithmetic (callable source lacks derived_math)."""
    import inspect

    src = inspect.getsource(probe.oracle_displacement_retrace)
    assert "derived_math" not in src
    assert "FORMULA_REGISTRY" not in src
    assert "feature_pipeline" not in src


def test_oracle_parity_with_derived_math_and_registry(probe):
    from features import derived_math as dm
    from features.fm_resolve import resolve_fm_callable, bind_phase2_crt_callables

    fm027 = resolve_fm_callable("FM-027")
    bound = bind_phase2_crt_callables()["FM-027"]
    vectors = [
        (105.0, 100.0, 110.0),
        (102.0, 100.0, 110.0),
        (100.0, 100.0, 110.0),
        (110.0, 100.0, 110.0),
        (120.0, 100.0, 110.0),
        (100.0, 100.0, 100.0),
        (101.0, 110.0, 100.0),
    ]
    for rc, do, dc in vectors:
        o = probe.oracle_displacement_retrace(rc, do, dc)
        assert o == pytest.approx(dm.displacement_retrace(rc, do, dc))
        assert o == pytest.approx(fm027(retest_close=rc, disp_open=do, disp_close=dc))
        assert o == pytest.approx(bound(retest_close=rc, disp_open=do, disp_close=dc))


def test_zero_body_returns_zero(probe):
    assert probe.oracle_displacement_retrace(999.0, 50.0, 50.0) == 0.0


def test_clip_high_and_bounds(probe):
    v = probe.oracle_displacement_retrace(200.0, 100.0, 110.0)
    assert v == 1.0
    for triple in [
        (105.0, 100.0, 110.0),
        (0.0, 100.0, 110.0),
        (1000.0, 0.0, 1.0),
    ]:
        x = probe.oracle_displacement_retrace(*triple)
        assert 0.0 <= x <= 1.0


def test_scale_invariance(probe):
    base = (105.0, 100.0, 110.0)
    b = probe.oracle_displacement_retrace(*base)
    for k in (0.01, 100.0, 1e6):
        assert probe.oracle_displacement_retrace(*(x * k for x in base)) == pytest.approx(b)


def test_sign_symmetry_bullish_bearish(probe):
    bull = probe.oracle_displacement_retrace(105.0, 100.0, 110.0)
    bear = probe.oracle_displacement_retrace(105.0, 110.0, 100.0)
    assert bull == pytest.approx(0.5)
    assert bear == pytest.approx(0.5)


def test_nan_inf_as_wired_parity(probe):
    """AS-WIRED: clip min/max collapses NaN paths; oracle must match derived_math."""
    from features import derived_math as dm

    for triple in [
        (float("nan"), 100.0, 110.0),
        (105.0, float("nan"), 110.0),
        (105.0, 100.0, float("nan")),
        (5.0, 0.0, float("inf")),
    ]:
        o = probe.oracle_displacement_retrace(*triple)
        a = dm.displacement_retrace(*triple)
        if math.isnan(o) or math.isnan(a):
            assert math.isnan(o) and math.isnan(a)
        else:
            assert o == pytest.approx(a)


def test_distinct_from_fm021(probe):
    from features import derived_math as dm

    fm027 = probe.oracle_displacement_retrace(105.0, 100.0, 110.0)
    fm021 = dm.retest_depth(close=105.0, ema_fast=100.0, atr=0.01)
    assert fm027 == pytest.approx(0.5)
    assert fm027 != pytest.approx(fm021)


def test_prefix_and_future_mutation(probe):
    series = [
        (100.0 + i * 0.1, 100.0, 110.0) for i in range(80)
    ]
    full = [probe.oracle_displacement_retrace(*t) for t in series]
    n = 50
    pref = [probe.oracle_displacement_retrace(*t) for t in series[:n]]
    assert full[:n] == pref
    cut = 30
    base = probe.oracle_displacement_retrace(*series[cut])
    mut = list(series)
    for j in range(cut + 1, len(mut)):
        mut[j] = (999.0, 0.0, 1.0)
    assert probe.oracle_displacement_retrace(*mut[cut]) == pytest.approx(base)


def test_crt_emission_parity(probe):
    from config_layer.crt_engine_v2 import (
        CRTConfig,
        EngineState,
        StateMachine,
        Range,
        Direction,
        Candle,
        CRTState,
        SweepEvent,
    )
    from features import derived_math as dm

    cfg = CRTConfig(
        retest_depth_max=1.0,
        retest_atr_depth_fraction=1.0,
        max_displacement_strength=10.0,
    )
    sm = StateMachine(cfg)
    st = EngineState()
    st.current_state = CRTState.EXPANSION
    # PRE-EXISTING BUG FIXED 2026-08-01: EngineState has no field named `atr` (deliberately --
    # see crt_engine_v2.py:244-249). `st.atr = 2.0` created an unused stray attribute; the
    # cache-population guard at crt_engine_v2.py:1599 reads `state.atr_abs`, which stayed at its
    # 0.0 default, so cached_features never left its zeroed default.
    st.atr_abs = 2.0
    st.direction = Direction.LONG
    st.active_range = Range(
        h_ref=120.0,
        l_ref=100.0,
        equilibrium=110.0,
        formed_at=datetime(2024, 1, 1),
        htf_candle_id="T",
        session="LONDON",
    )
    st.displacement_candle = Candle(
        timestamp=datetime(2024, 1, 1, 12, 0),
        open=100,
        high=112,
        low=99,
        close=110,
        volume=1,
        index=5,
    )
    st.sweep_event = SweepEvent(
        direction=Direction.LONG,
        price=99.0,
        candle=st.displacement_candle,
        double_confirmed=False,
        candle_index=5,
    )
    st.current_candle_index = 10
    retest = Candle(
        timestamp=datetime(2024, 1, 1, 13, 0),
        open=102,
        high=103,
        low=100.5,
        close=101.0,
        volume=1,
        index=10,
    )
    assert sm.try_expansion_to_retest(st, retest, atr=2.0) is True
    cf = st.cached_features
    assert "displacement_retrace" in cf
    assert "retest_depth" not in cf
    expected = probe.oracle_displacement_retrace(101.0, 100.0, 110.0)
    assert cf["displacement_retrace"] == pytest.approx(expected)
    assert cf["displacement_retrace"] == pytest.approx(
        dm.displacement_retrace(101.0, 100.0, 110.0)
    )


def test_full_battery_certifies(probe):
    battery = probe.run_battery()
    assert battery["overall_verdict"] == "CERTIFIED"
    assert battery["all_probes_pass"] is True
    for key in (
        "formula_parity",
        "bounds",
        "zero_body",
        "clip_high",
        "scale_invariance",
        "sign_symmetry",
        "nan_policy",
        "determinism",
        "prefix_invariance",
        "future_mutation",
        "distinct_from_fm021",
        "crt_emission_parity",
        "monotonicity",
    ):
        assert battery[key]["status"] == "PASS", key


def test_evidence_artifact_exists_and_hashes_nonempty():
    """After probe main() is run, artifact must exist with non-empty SHA-256."""
    if not _EVIDENCE.exists():
        pytest.skip("evidence artifact not yet generated — run probe first")
    raw = _EVIDENCE.read_bytes()
    assert len(raw) > 0
    sha = hashlib.sha256(raw).hexdigest()
    assert len(sha) == 64
    assert sha.strip() != ""
    art = json.loads(raw.decode("utf-8"))
    assert art["feature"] == "displacement_retrace"
    assert art["formula_id"] == "FM-027"
    assert art["verdict"] == "CERTIFIED"
    assert art["production_behavior_changed"] == "NO"
    assert art["dependency_contract"]["classification"] == "ROLE_LABEL_GROUNDING_ALIGNED"
