"""
test_auto_tuner_multi.py
═══════════════════════════════════════════════════════════════════════════════
Test suite for auto_tuner_multi.py — covers the four mandatory invariants
plus edge-case and regression scenarios.

Run with:
    pytest test_auto_tuner_multi.py -v
═══════════════════════════════════════════════════════════════════════════════
"""

import dataclasses
import math
import random
import sys
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

# ── Bootstrap: add parent dir to path so imports resolve ────────────────────
sys.path.insert(0, str(Path(__file__).parent))

# We import the functions we want to test directly; the heavy engine modules
# are mocked so tests run without backtest_v2 / crt_engine_v2 installed.

# ── Minimal stubs for modules not present in test environment ───────────────
import types

# Stub crt_engine_v2
crt_module = types.ModuleType("crt_engine_v2")

@dataclasses.dataclass
class _StubCRTConfig:
    retest_depth_max:           float = 0.30
    retest_atr_depth_fraction:  float = 0.50
    body_ratio_min:             float = 0.65
    atr_multiplier_min:         float = 1.50
    expansion_atr_min_distance: float = 0.20
    instrument:                 str   = "UNKNOWN"

crt_module.CRTConfig = _StubCRTConfig
sys.modules["crt_engine_v2"] = crt_module

# Stub config_builder
cb_module = types.ModuleType("config_builder")
class _StubConfigBuilder:
    @staticmethod
    def build(instrument: str, overrides: Optional[dict] = None) -> _StubCRTConfig:
        cfg = _StubCRTConfig(instrument=instrument)
        if overrides:
            for k, v in overrides.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
        return cfg
cb_module.ConfigBuilder = _StubConfigBuilder
sys.modules["config_builder"] = cb_module

# Stub backtest_v2
bt_module = types.ModuleType("backtest_v2")

@dataclasses.dataclass
class _StubBacktestConfig:
    instrument: str = "UNKNOWN"
    pip_size:   float = 0.0001
    crt_config: object = None
    debug_mode: bool = False

class _StubMetrics:
    approved_trades    = 20
    win_rate           = 0.55
    expectancy_rr      = 0.30
    total_pnl_rr_net   = 6.0
    max_drawdown_pct   = 0.05
    avg_rr_net         = 0.30
    funnel_counts      = {"expansion_success": 10, "retest_success": 3, "sweeps_detected": 5}

class _StubCandleLoader:
    def __init__(self, csv_path, instrument): pass
    def count(self): return 1000
    def stream(self): return iter(range(1000))

class _StubBacktestRunner:
    def __init__(self, cfg): pass
    def run(self, stream, count, output_dir=""): return _StubMetrics()

bt_module.BacktestConfig = _StubBacktestConfig
bt_module.CandleLoader   = _StubCandleLoader
bt_module.BacktestRunner = _StubBacktestRunner
sys.modules["backtest_v2"] = bt_module

# Stub llama_gate
llm_module = types.ModuleType("llama_gate")
llm_module.llm_score = lambda metrics: 0.9
sys.modules["llama_gate"] = llm_module

# Stub market_router (old import — should NOT be used, but must not crash import)
mr_module = types.ModuleType("market_router")
def _forbidden_get_crt_config(*a, **kw):
    raise AssertionError("get_crt_config() called — FORBIDDEN in v3")
mr_module.get_crt_config = _forbidden_get_crt_config
sys.modules["market_router"] = mr_module

# ── Now import the module under test ────────────────────────────────────────
from auto_tuner_multi import (
    PARAM_SPACE,
    fitness_multi,
    fitness_single,
    params_to_key,
    sample_random,
    evaluate_params_multi,
    _run_single_instrument,
)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 1 — Determinism: same params + seed → identical score
# ═══════════════════════════════════════════════════════════════════════════

def _make_csv_paths(tmp_path, instruments=("EURUSD", "GBPUSD")):
    paths = {}
    for inst in instruments:
        p = tmp_path / f"{inst}_M15.csv"
        p.write_text("dummy")
        paths[inst] = str(p)
    return paths


def test_determinism(tmp_path):
    """Same params evaluated twice must produce byte-identical scores."""
    params = {
        "retest_depth_max":           0.30,
        "retest_atr_depth_fraction":  0.50,
        "body_ratio_min":             0.65,
        "atr_multiplier_min":         1.50,
        "expansion_atr_min_distance": 0.20,
    }
    csv_paths = _make_csv_paths(tmp_path)
    start_idx = {inst: 0 for inst in csv_paths}
    end_idx   = {inst: 0 for inst in csv_paths}

    with patch("auto_tuner_multi.CandleLoader", _StubCandleLoader), \
         patch("auto_tuner_multi.BacktestRunner", _StubBacktestRunner), \
         patch("auto_tuner_multi.BacktestConfig", _StubBacktestConfig):

        r1 = evaluate_params_multi(params, csv_paths, None, "/tmp", start_idx, end_idx, use_llm=False)
        r2 = evaluate_params_multi(params, csv_paths, None, "/tmp", start_idx, end_idx, use_llm=False)

    assert r1["final_score"] == r2["final_score"], (
        f"Non-deterministic: {r1['final_score']} != {r2['final_score']}"
    )
    assert r1["config_snapshot"] == r2["config_snapshot"]


# ═══════════════════════════════════════════════════════════════════════════
# TEST 2 — Forex vs Crypto produce different ConfigBuilder snapshots
# ═══════════════════════════════════════════════════════════════════════════

def test_forex_vs_crypto_config(tmp_path):
    """GBPUSD and BTCUSDT must produce different config snapshots."""
    params = {
        "retest_depth_max":           0.30,
        "retest_atr_depth_fraction":  0.50,
        "body_ratio_min":             0.65,
        "atr_multiplier_min":         1.50,
        "expansion_atr_min_distance": 0.20,
    }

    csv_forex  = tmp_path / "GBPUSD_M15.csv"; csv_forex.write_text("dummy")
    csv_crypto = tmp_path / "BTCUSDT_M15.csv"; csv_crypto.write_text("dummy")

    with patch("auto_tuner_multi.CandleLoader", _StubCandleLoader), \
         patch("auto_tuner_multi.BacktestRunner", _StubBacktestRunner), \
         patch("auto_tuner_multi.BacktestConfig", _StubBacktestConfig):

        _, snap_forex  = _run_single_instrument(params, str(csv_forex),  "GBPUSD",  None, "/tmp")
        _, snap_crypto = _run_single_instrument(params, str(csv_crypto), "BTCUSDT", None, "/tmp")

    # The stub ConfigBuilder stamps the instrument name into the snapshot
    assert snap_forex.get("instrument")  == "GBPUSD",  f"Got: {snap_forex}"
    assert snap_crypto.get("instrument") == "BTCUSDT", f"Got: {snap_crypto}"
    assert snap_forex != snap_crypto, "Forex and Crypto configs must differ"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 3 — Multi-instrument score ≠ single-instrument score
# ═══════════════════════════════════════════════════════════════════════════

def test_multi_score_differs_from_single():
    """
    fitness_multi() with consistency penalty must differ from a raw single score
    when per-instrument scores are heterogeneous.
    """
    # Simulate heterogeneous per-instrument scores
    per_scores = {"EURUSD": 0.50, "BTCUSDT": 0.10}
    final, penalty = fitness_multi(per_scores)

    assert penalty > 0, "Heterogeneous scores must produce a non-zero consistency penalty"
    assert final < 0.50, "Multi score must be below the best single-instrument score"
    assert final > -999, "Multi score must not be -999 when valid instruments exist"


def test_multi_score_homogeneous():
    """Identical per-instrument scores → zero penalty."""
    per_scores = {"EURUSD": 0.40, "GBPUSD": 0.40, "XAUUSD": 0.40}
    final, penalty = fitness_multi(per_scores)
    assert math.isclose(penalty, 0.0, abs_tol=1e-9)
    assert math.isclose(final, 0.40, abs_tol=1e-6)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 4 — Config snapshot matches ConfigBuilder output
# ═══════════════════════════════════════════════════════════════════════════

def test_config_snapshot_matches_builder(tmp_path):
    """config_snapshot stored in result must match ConfigBuilder.build() output."""
    params = {
        "retest_depth_max":           0.40,
        "retest_atr_depth_fraction":  0.70,
        "body_ratio_min":             0.70,
        "atr_multiplier_min":         1.75,
        "expansion_atr_min_distance": 0.25,
    }

    csv_path = tmp_path / "EURUSD_M15.csv"
    csv_path.write_text("dummy")

    with patch("auto_tuner_multi.CandleLoader", _StubCandleLoader), \
         patch("auto_tuner_multi.BacktestRunner", _StubBacktestRunner), \
         patch("auto_tuner_multi.BacktestConfig", _StubBacktestConfig):

        _, snapshot = _run_single_instrument(params, str(csv_path), "EURUSD", None, "/tmp")

    expected = dataclasses.asdict(_StubConfigBuilder.build("EURUSD", overrides=params))
    assert snapshot == expected, f"\nExpected: {expected}\nGot:      {snapshot}"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 5 — Edge case: missing CSV
# ═══════════════════════════════════════════════════════════════════════════

def test_missing_csv_handled(tmp_path):
    """Missing CSV must not raise; must return error metric and score -999."""
    params = sample_random(random.Random(0))
    csv_paths   = {"EURUSD": "/nonexistent/path.csv"}
    start_idx   = {"EURUSD": 0}
    end_idx     = {"EURUSD": 0}

    result = evaluate_params_multi(params, csv_paths, None, "/tmp", start_idx, end_idx, use_llm=False)
    assert result["final_score"] == -999.0
    assert result["instrument_results"]["EURUSD"]["score"] == -999.0


# ═══════════════════════════════════════════════════════════════════════════
# TEST 6 — Edge case: all instruments return -999
# ═══════════════════════════════════════════════════════════════════════════

def test_all_instruments_invalid():
    per_scores = {"EURUSD": -999.0, "GBPUSD": -999.0}
    final, penalty = fitness_multi(per_scores)
    assert final == -999.0


# ═══════════════════════════════════════════════════════════════════════════
# TEST 7 — Divide-by-zero guard in base score
# ═══════════════════════════════════════════════════════════════════════════

def test_zero_expansion_guard():
    """exp=0 should not trigger the retest-ratio guard (avoids ZeroDivisionError)."""
    from auto_tuner_multi import _compute_base_score
    metrics = {
        "approved_trades": 10, "expansions": 0, "retests": 0,
        "expectancy_rr": 0.3, "win_rate": 0.6,
        "max_drawdown_pct": 0.1,
    }
    score = _compute_base_score(metrics)
    assert score != -999.0, "Zero expansions must not trip the retest-ratio guard"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 8 — params_to_key is deterministic and order-independent
# ═══════════════════════════════════════════════════════════════════════════

def test_params_to_key_deterministic():
    p1 = {"a": 1, "b": 2, "c": 3}
    p2 = {"c": 3, "a": 1, "b": 2}
    assert params_to_key(p1) == params_to_key(p2)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 9 — No get_crt_config / CRTConfig direct instantiation in new code
# ═══════════════════════════════════════════════════════════════════════════

def test_no_forbidden_imports():
    """Source code must not call get_crt_config or CRTConfig(...)."""
    source = Path("auto_tuner_multi.py").read_text()
    assert "get_crt_config" not in source, "get_crt_config found in source — FORBIDDEN"
    # Direct instantiation pattern: CRTConfig(  (with opening paren)
    assert "CRTConfig(" not in source, "Direct CRTConfig(...) instantiation found — FORBIDDEN"
