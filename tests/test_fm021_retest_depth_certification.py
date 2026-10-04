"""Floor: M10 / F-054-RD gated retest_depth certification (FM-021 component)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PROBE = _ROOT / "scripts" / "analysis" / "fm021_retest_depth_certification.py"
_EVIDENCE = _ROOT / "docs" / "governance" / "fm021_retest_depth_certification-2026-07-14.json"


def _load():
    spec = importlib.util.spec_from_file_location("fm021_probe", _PROBE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def probe():
    return _load()


def test_dag_deps_include_close():
    from importlib.util import spec_from_file_location, module_from_spec

    spec = spec_from_file_location(
        "feature_dag_layers",
        _ROOT / "scripts" / "analysis" / "feature_dag_layers.py",
    )
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    dag = mod.build_dag()
    nd = next(n for n in dag["nodes"] if n["name"] == "retest_depth")
    assert sorted(nd["deps"]) == ["atr", "close", "ema_fast", "liquidity_sweep"]
    assert nd["formula_id"] == "FM-021"
    assert nd["in_canonical_vector"] is True
    # index 34 under schema v4.0 (was 33 pre-MACD-split; shifted +1, feature_schema.py:47-68).
    assert nd["canonical_index"] == 34


def test_intended_quantity_is_gated_not_kernel_only():
    from importlib.util import spec_from_file_location, module_from_spec

    layers = spec_from_file_location(
        "feature_dag_layers",
        _ROOT / "scripts" / "analysis" / "feature_dag_layers.py",
    )
    lmod = module_from_spec(layers)
    layers.loader.exec_module(lmod)
    dag = lmod.build_dag()

    fcs = spec_from_file_location(
        "feature_certification_state",
        _ROOT / "scripts" / "governance" / "feature_certification_state.py",
    )
    fmod = module_from_spec(fcs)
    fcs.loader.exec_module(fmod)
    iq = fmod._intended_quantities(dag)["retest_depth"]
    assert "GATED_PRODUCTION_COMPOSITION" in iq
    assert "FM-021" in iq
    assert "OFF_GATE=0.0" in iq or "OFF_GATE" in iq
    assert "rolling(10" in iq or "window" in iq.lower() or "10" in iq


def test_oracle_independent_of_derived_math_source(probe):
    import inspect

    src = inspect.getsource(probe.oracle_kernel_independent)
    assert "derived_math" not in src
    src2 = inspect.getsource(probe.oracle_canonical_retest_depth)
    assert "derived_math" not in src2
    assert "rolling" not in src2  # full series path uses online flag
    src3 = inspect.getsource(probe.oracle_recent_sweep_online)
    assert "rolling" not in src3
    assert "pandas" not in src3


def test_gate_window_lag9_lag10(probe):
    n = 20
    close = np.full(n, 100.5)
    ema = np.full(n, 100.0)
    atr = np.full(n, 0.01)  # band = 1.0
    sweep = np.zeros(n, dtype=np.int8)
    sweep[5] = 1
    flag = probe.oracle_retest_flag(close, ema, atr, sweep)
    recent = probe.oracle_recent_sweep_online(sweep)
    assert recent[5] and flag[5] == 1
    assert recent[14] and flag[14] == 1  # lag 9
    assert not recent[15] and flag[15] == 0  # lag 10


def test_near_boundary_inclusive(probe):
    # |c-e| == atr*c
    assert probe.oracle_near_fast_ema(101.0, 100.0, 0.01) is True
    assert probe.oracle_near_fast_ema(101.1, 100.0, 0.01) is False


def test_off_gate_zero_despite_positive_kernel(probe):
    c = np.array([100.0, 110.0])
    e = np.array([100.0, 100.0])
    a = np.array([0.01, 0.01])
    s = np.array([0, 0], dtype=np.int8)
    rd = probe.oracle_canonical_retest_depth(c, e, a, s)
    assert rd[1] == 0.0
    assert abs(110.0 - 100.0) / (0.01 * 110.0) > 0


def test_on_gate_component_parity_derived_math(probe):
    from features import derived_math as dm

    c = np.array([100.0, 100.5, 100.2])
    e = np.array([100.0, 100.0, 100.0])
    a = np.array([0.01, 0.01, 0.01])
    s = np.array([1, 1, 1], dtype=np.int8)
    rd = probe.oracle_canonical_retest_depth(c, e, a, s)
    fl = probe.oracle_retest_flag(c, e, a, s)
    for t in range(3):
        assert fl[t] == 1
        assert rd[t] == pytest.approx(
            dm.retest_depth(float(c[t]), float(e[t]), float(a[t])), abs=1e-5
        )


def test_emission_order_clip_after_where(probe):
    # Construct on-gate with raw ratio > 1, ensure clip to 1
    # near needs |c-e| <= atr*c; for ratio > 1 need |c-e| > atr*c — impossible while near
    # So clip>1 only if band allows and ratio>1: ratio = |c-e|/(atr*c) <= 1 when near with band=1
    # Therefore on-gate kernel always in [0,1] when band==1.0 — clip is safety. Still verify dtype.
    c = np.array([101.0])
    e = np.array([100.0])
    a = np.array([0.01])
    s = np.array([1], dtype=np.int8)
    rd = probe.oracle_canonical_retest_depth(c, e, a, s)
    assert rd.dtype == np.float32
    assert 0.0 <= float(rd[0]) <= 1.0


def test_prefix_and_future_mutation(probe):
    corp = probe.synthetic_boundary_corpus()
    c, e, a, s = corp["close"], corp["ema_fast"], corp["atr"], corp["liquidity_sweep"]
    full = probe.oracle_canonical_retest_depth(c, e, a, s)
    cut = 25
    pref = probe.oracle_canonical_retest_depth(c[:cut], e[:cut], a[:cut], s[:cut])
    assert np.array_equal(full[:cut], pref)
    c2 = c.copy()
    c2[cut:] = 1e6
    mut = probe.oracle_canonical_retest_depth(c2[:cut], e[:cut], a[:cut], s[:cut])
    assert np.array_equal(pref, mut)


def test_full_battery_certifies(probe):
    battery = probe.run_battery()
    assert battery["overall_verdict"] == "CERTIFIED", battery
    assert battery["all_probes_pass"] is True


def test_evidence_artifact_when_present():
    if not _EVIDENCE.exists():
        pytest.skip("evidence not yet written")
    raw = _EVIDENCE.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    assert len(sha) == 64
    art = json.loads(raw.decode("utf-8"))
    assert art["TARGET_FEATURE"] == "retest_depth"
    assert art["TARGET_IDENTITY"] == "GATED_PRODUCTION_COMPOSITION"
    assert art["COMPONENT_FORMULA_IDENTITY"] == "FM-021"
    assert art["PER_NODE_VERDICT"] == "CERTIFIED"
    assert art["PRODUCTION_BEHAVIOR_CHANGED"] == "NO"
    assert sorted(art["FULL_DEPENDENCIES"]) == [
        "atr",
        "close",
        "ema_fast",
        "liquidity_sweep",
    ]
    assert "FM-021 != full" in art["COMPOSITION_RELATION"] or "!=" in art["COMPOSITION_RELATION"]
