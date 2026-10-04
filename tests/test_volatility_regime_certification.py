"""Floor: M14B volatility_regime absolute-ATR14 rolling tercile certification."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PROBE = _ROOT / "scripts" / "analysis" / "volatility_regime_certification.py"
_EVIDENCE = _ROOT / "docs" / "governance" / "volatility_regime_certification-2026-07-14.json"


def _load():
    spec = importlib.util.spec_from_file_location("vr_probe", _PROBE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def probe():
    return _load()


def test_dag_deps_ohlc_roots():
    from importlib.util import spec_from_file_location, module_from_spec

    spec = spec_from_file_location(
        "fdl", _ROOT / "scripts" / "analysis" / "feature_dag_layers.py"
    )
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    nd = next(n for n in mod.build_dag()["nodes"] if n["name"] == "volatility_regime")
    # CORRECTED (M14B, 2026-07-19, feature_dag_layers.py's own "volatility_regime" node comment):
    # the edge was deliberately tightened from the structural roots [close, high, low] to the
    # direct registered producer true_range (FM-040), matching ontology FM-050 exactly and
    # keeping the ontology<->DAG crosscheck divergence-free. M14B's conclusion is unchanged --
    # true_range IS the absolute chain; only the recorded edge's granularity changed.
    assert nd["deps"] == ["true_range"]
    # index 30 under schema v4.0 (was 29 pre-MACD-split; shifted +1, see feature_schema.py:47-68).
    assert nd["canonical_index"] == 30


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
    iq = smod._intended_quantities(fmod.build_dag())["volatility_regime"]
    assert "UNADJUDICATED" not in iq
    assert "ATR14" in iq or "atr_14" in iq or "absolute" in iq
    assert "200" in iq
    assert "0.33" in iq and "0.66" in iq


def test_tr0_nan_and_atr_first_14(probe):
    h = np.array([10.0, 12.0, 11.0])
    l = np.array([9.0, 10.0, 10.0])
    c = np.array([9.5, 11.0, 10.5])
    tr = probe.oracle_true_range(h, l, c)
    assert np.isnan(tr[0])
    close = 100 + np.arange(40, dtype=np.float64) * 0.1
    high, low = close + 0.3, close - 0.3
    atr = probe.independent_sma(probe.oracle_true_range(high, low, close), 14)
    fin = np.where(np.isfinite(atr))[0]
    assert int(fin[0]) == 14


def test_bin_boundaries(probe):
    assert int(probe.oracle_tercile(np.array([0.32]))[0]) == 0
    assert int(probe.oracle_tercile(np.array([0.33]))[0]) == 1
    assert int(probe.oracle_tercile(np.array([0.66]))[0]) == 2
    assert int(probe.oracle_tercile(np.array([np.nan]))[0]) == 2


def test_rank_ties_vs_pandas(probe):
    x = np.array([1.0, 2.0, 2.0, 3.0, 2.0, 1.0, 4.0])
    o = probe.independent_rolling_rank_pct(x, 200)
    p = probe.pandas_reference_rank_pct(x, 200)
    assert np.allclose(o, p, rtol=0, atol=1e-12, equal_nan=True)


def test_pipeline_parity(probe):
    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.normal(0, 0.3, 300))
    high = close + 0.5
    low = close - 0.5
    o = probe.oracle_volatility_regime(high, low, close)
    p = probe.pipeline_volatility_regime(high, low, close)
    assert np.array_equal(o, p)
    assert o.dtype == np.int8
    assert set(int(x) for x in o).issubset({0, 1, 2})
    assert np.all(o[:14] == 2)


def test_prefix_and_future(probe):
    rng = np.random.default_rng(2)
    close = 50 + np.cumsum(rng.normal(0, 0.2, 250))
    high, low = close + 0.4, close - 0.4
    full = probe.oracle_volatility_regime(high, low, close)
    for cut in (80, 150, 200):
        assert np.array_equal(
            probe.oracle_volatility_regime(high[:cut], low[:cut], close[:cut]),
            full[:cut],
        )
    mut_c = close.copy()
    mut_c[200:] = 0.0
    assert np.array_equal(
        probe.oracle_volatility_regime(high[:200], low[:200], mut_c[:200]),
        full[:200],
    )


def test_oracle_independence(probe):
    assert probe.oracle_independence()["ok"] is True


def test_full_battery(probe):
    assert probe.run_battery()["overall_verdict"] == "CERTIFIED"


def test_evidence_when_present():
    if not _EVIDENCE.exists():
        pytest.skip("evidence not yet written")
    raw = _EVIDENCE.read_bytes()
    assert len(hashlib.sha256(raw).hexdigest()) == 64
    art = json.loads(raw.decode("utf-8"))
    assert art["feature"] == "volatility_regime"
    assert sorted(art["corrected_dependency_contract"]) == ["close", "high", "low"]
    assert art["PER_NODE_VERDICT"] == "CERTIFIED"
    assert art["PRODUCTION_BEHAVIOR_CHANGED"] == "NO"
    assert art["FEATURE_PROGRAM_CLOSED"] == "NO"
