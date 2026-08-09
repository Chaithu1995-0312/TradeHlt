"""Rolling-indicator series-certification floor — the durable gate that the first-class windowed
identities FM-040..046 (true_range/atr/ema/rsi) stay SERIES-parity + PIT certified against the
production pipeline. Runs the synthetic arm on every pytest invocation.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_PROBE = _REPO / "scripts" / "analysis" / "feature_dag_rolling_certification.py"


def _load():
    spec = importlib.util.spec_from_file_location("feature_dag_rolling_certification", _PROBE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["feature_dag_rolling_certification"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def probe():
    if not _PROBE.exists():
        pytest.skip("rolling certification probe not present")
    return _load()


@pytest.fixture(scope="module")
def synth(probe):
    return probe._synthetic()


def test_series_parity_all_numeric_indicators(probe, synth):
    arm = probe._series_parity(synth, "floor")
    for col, r in arm["per_indicator"].items():
        assert r["parity"], f"{col}: independent recompute != pipeline column (resid {r['max_resid']})"


def test_prefix_invariance(probe, synth):
    pit = probe._prefix_invariance(synth)
    for col, ok in pit.items():
        assert ok, f"{col}: rolling indicator is prefix-VARIANT (future dependence)"


def test_verdicts_certified(probe, synth):
    # synthetic-only report (corpus-independent)
    rep = probe.build_report(limit=0, include_corpus=False)
    for col, v in rep["verdicts"].items():
        assert v.startswith("CERTIFIED"), f"{col} not certified: {v}"
    assert rep["overall"].startswith("CERTIFIED")
    # every rolling indicator maps to an FM-04x id
    for col, fid in rep["formula_id_map"].items():
        assert fid.startswith("FM-04")
