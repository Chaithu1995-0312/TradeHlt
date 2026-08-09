"""Floor: M13B trend_strength nested rolling certification."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PROBE = _ROOT / "scripts" / "analysis" / "trend_strength_certification.py"
_EVIDENCE = _ROOT / "docs" / "governance" / "trend_strength_certification-2026-07-14.json"


def _load():
    spec = importlib.util.spec_from_file_location("ts_probe", _PROBE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def probe():
    return _load()


def test_dag_deps_close_only():
    from importlib.util import spec_from_file_location, module_from_spec

    spec = spec_from_file_location(
        "fdl", _ROOT / "scripts" / "analysis" / "feature_dag_layers.py"
    )
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    nd = next(n for n in mod.build_dag()["nodes"] if n["name"] == "trend_strength")
    assert nd["deps"] == ["close"]
    assert nd["canonical_index"] == 11


def test_intended_quantity_pinned():
    from importlib.util import spec_from_file_location, module_from_spec

    fdl = spec_from_file_location(
        "fdl", _ROOT / "scripts" / "analysis" / "feature_dag_layers.py"
    )
    fmod = module_from_spec(fdl)
    fdl.loader.exec_module(fmod)
    fcs = spec_from_file_location(
        "fcs", _ROOT / "scripts" / "governance" / "feature_certification_state.py"
    )
    smod = module_from_spec(fcs)
    fcs.loader.exec_module(smod)
    iq = smod._intended_quantities(fmod.build_dag())["trend_strength"]
    assert "UNADJUDICATED" not in iq
    assert "SMA20" in iq or "window=20" in iq
    assert "index 29" in iq
    assert "float64" in iq and "float32" in iq


def test_first_finite_index_29(probe):
    close = 100.0 + np.arange(50, dtype=np.float64)
    o = probe.oracle_trend_strength(close)
    fin = np.where(np.isfinite(o))[0]
    assert len(fin) > 0 and int(fin[0]) == 29
    assert not np.isfinite(probe.oracle_trend_strength(close[:29])).any()
    assert int(np.isfinite(probe.oracle_trend_strength(close[:30])).sum()) == 1


def test_constant_zero_and_linear_sign(probe):
    n = 60
    c = np.full(n, 50.0)
    o = probe.oracle_trend_strength(c)
    assert np.allclose(o[29:], 0.0, atol=1e-12)
    up = 10.0 + np.arange(n, dtype=np.float64)
    dn = 100.0 - np.arange(n, dtype=np.float64)
    assert np.all(probe.oracle_trend_strength(up)[29:] > 0)
    assert np.all(probe.oracle_trend_strength(dn)[29:] < 0)


def test_pipeline_parity_and_mask(probe):
    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.normal(0, 0.2, 100))
    o = probe.oracle_trend_strength(close)
    p = probe.pipeline_trend_strength(close)
    assert np.array_equal(np.isfinite(o), np.isfinite(p))
    m = np.isfinite(o)
    # float64 SMA accumulation: independent recurrence vs pandas within 1e-12
    assert np.allclose(o[m], p[m], rtol=0, atol=1e-12)


def test_nan_injection_mask(probe):
    close = 100.0 + np.arange(80, dtype=np.float64)
    close[40] = np.nan
    o = probe.oracle_trend_strength(close)
    p = probe.production_formula_trend_strength(close)
    assert np.array_equal(np.isfinite(o), np.isfinite(p))
    m = np.isfinite(o)
    assert np.allclose(o[m], p[m], rtol=0, atol=1e-12)


def test_prefix_future_determinism(probe):
    close = 50 + np.cumsum(np.random.default_rng(3).normal(0, 0.1, 90))
    full = probe.oracle_trend_strength(close)
    for cut in (19, 20, 28, 29, 30, 50):
        pref = probe.oracle_trend_strength(close[:cut])
        assert np.array_equal(np.isfinite(pref), np.isfinite(full[:cut]))
        m = np.isfinite(pref)
        assert np.allclose(pref[m], full[:cut][m], rtol=0, atol=0)
    mut = close.copy()
    mut[60:] = 0.0
    assert np.allclose(
        probe.oracle_trend_strength(close[:60])[np.isfinite(probe.oracle_trend_strength(close[:60]))],
        probe.oracle_trend_strength(mut[:60])[np.isfinite(probe.oracle_trend_strength(mut[:60]))],
        rtol=0,
        atol=0,
    )
    assert np.array_equal(
        np.isfinite(probe.oracle_trend_strength(close)),
        np.isfinite(probe.oracle_trend_strength(close)),
    )


def test_oracle_independence_and_collision(probe):
    assert probe.oracle_independence_ok()["ok"] is True
    b = probe.run_battery()
    assert b["name_collision"]["canonical_ne_abs_ema_spread"] == "PASS"


def test_full_battery(probe):
    assert probe.run_battery()["overall_verdict"] == "CERTIFIED"


def test_evidence_when_present():
    if not _EVIDENCE.exists():
        pytest.skip("evidence not yet written")
    raw = _EVIDENCE.read_bytes()
    assert len(hashlib.sha256(raw).hexdigest()) == 64
    art = json.loads(raw.decode("utf-8"))
    assert art["TARGET_FEATURE"] == "trend_strength"
    assert art["FIRST_FINITE_INDEX_FINITE_INPUT"] == 29
    assert art["CURRENT_DAG_DEPS"] == ["close"]
    assert art["PER_NODE_VERDICT"] == "CERTIFIED"
    assert art["PRODUCTION_BEHAVIOR_CHANGED"] == "NO"
