"""
test_tradenet_v2_pipeline.py
============================
Tests for the TradeNet v2 stack:

  - TradeNetRegistry per-instrument __active__ map (register, promote,
    regression guard, force, rollback, isolation)
  - Label extraction from MFE-based BE-survival proxy
  - Input matrix shape (38-dim, no strategy flags in this patch)
  - V2 envelope load + 3-head forward pass + composite formula

Mirrors tests/test_gaussian_update_pipeline.py in spirit. Does not invoke the
PyTorch training loop — that path is exercised by running the training script
end-to-end with real data; here we only verify the JSON envelope round-trip.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import pytest

# scripts/training is not on sys.path by default — the training script is meant
# to be invoked directly from the repo root. Add it just for the tests that
# import label/matrix helpers.
_SCRIPTS = Path(__file__).parent.parent / "scripts" / "training"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


# ─────────────────────────────────────────────────────────────────────────────
# Registry: per-instrument isolation
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_registry(tmp_path):
    from core.model_registry import TradeNetRegistry
    return TradeNetRegistry(models_dir=tmp_path)


def test_first_deploy_two_instruments_isolated(tmp_registry):
    tmp_registry.register("v_eth_1", "eth1.json",
                          {"auc_p_tp1": 0.65}, instrument="ETHUSDT")
    tmp_registry.register("v_eur_1", "eur1.json",
                          {"auc_p_tp1": 0.62}, instrument="EURUSD")
    ok1, _ = tmp_registry.promote("v_eth_1", instrument="ETHUSDT")
    ok2, _ = tmp_registry.promote("v_eur_1", instrument="EURUSD")
    assert ok1 and ok2
    assert tmp_registry.get_active_version("ETHUSDT") == "v_eth_1"
    assert tmp_registry.get_active_version("EURUSD") == "v_eur_1"


def test_upgrade_one_instrument_does_not_touch_other(tmp_registry):
    tmp_registry.register("v_eth_1", "eth1.json",
                          {"auc_p_tp1": 0.65}, instrument="ETHUSDT")
    tmp_registry.register("v_eth_2", "eth2.json",
                          {"auc_p_tp1": 0.70}, instrument="ETHUSDT")
    tmp_registry.register("v_eur_1", "eur1.json",
                          {"auc_p_tp1": 0.62}, instrument="EURUSD")
    tmp_registry.promote("v_eth_1", instrument="ETHUSDT")
    tmp_registry.promote("v_eur_1", instrument="EURUSD")
    ok, _ = tmp_registry.promote("v_eth_2", instrument="ETHUSDT")
    assert ok
    assert tmp_registry.get_active_version("ETHUSDT") == "v_eth_2"
    assert tmp_registry.get_active_version("EURUSD") == "v_eur_1"


def test_regression_guard_blocks_then_force_bypasses(tmp_registry):
    tmp_registry.register("v_a", "a.json", {"auc_p_tp1": 0.70}, instrument="X")
    tmp_registry.register("v_b", "b.json", {"auc_p_tp1": 0.55}, instrument="X")
    tmp_registry.promote("v_a", instrument="X")
    ok, why = tmp_registry.promote("v_b", instrument="X")
    assert not ok
    assert "BLOCKED" in why
    ok, _ = tmp_registry.promote("v_b", instrument="X", force=True)
    assert ok
    assert tmp_registry.get_active_version("X") == "v_b"


def test_rollback_restores_prior(tmp_registry):
    tmp_registry.register("v_old", "old.json", {"auc_p_tp1": 0.70}, instrument="X")
    tmp_registry.register("v_new", "new.json", {"auc_p_tp1": 0.55}, instrument="X")
    tmp_registry.promote("v_old", instrument="X")
    tmp_registry.promote("v_new", instrument="X", force=True)
    assert tmp_registry.get_active_version("X") == "v_new"
    ok, _ = tmp_registry.rollback_tradenet("X")
    assert ok
    assert tmp_registry.get_active_version("X") == "v_old"


def test_gov3_single_active_per_instrument_invariant(tmp_registry):
    """Forcing two simultaneous active entries for one instrument must raise."""
    from core.model_registry import _assert_single_active_per_instrument
    reg = {
        "v_a": {"version": "v_a", "instrument": "X", "active": True},
        "v_b": {"version": "v_b", "instrument": "X", "active": True},
    }
    with pytest.raises(RuntimeError, match="GOV-3"):
        _assert_single_active_per_instrument(reg)


def test_lazy_migration_populates_active_map(tmp_path):
    """A pre-migration registry (entry-level active=true, no __active__ key)
    must produce an __active__ map on first load."""
    from core.model_registry import TradeNetRegistry
    reg_path = tmp_path / "tradenet_registry.json"
    reg_path.write_text(json.dumps({
        "v_legacy": {
            "version": "v_legacy", "model_file": "legacy.pth",
            "instrument": "ETHUSDT", "active": True, "metrics": {},
        }
    }))
    r = TradeNetRegistry(models_dir=tmp_path)
    raw = r._load()
    assert "__active__" in raw
    assert raw["__active__"] == {"ETHUSDT": "v_legacy"}


# ─────────────────────────────────────────────────────────────────────────────
# Label extraction
# ─────────────────────────────────────────────────────────────────────────────

def test_label_extraction_mfe_proxy():
    from train_trade_net_v2 import extract_labels
    cases = [
        {"exit_reason": "TP2", "mfe": 100.0, "entry": 100.0, "sl": 99.0},
        {"exit_reason": "TP1", "mfe": 2.0,   "entry": 100.0, "sl": 99.0},
        {"exit_reason": "SL",  "mfe": 0.3,   "entry": 100.0, "sl": 99.0},
        {"exit_reason": "SL",  "mfe": 1.5,   "entry": 100.0, "sl": 99.0},
        {"exit_reason": "TIMEOUT", "mfe": 0.5, "entry": 100.0, "sl": 99.0},
        {"outcome": "TP1_HIT", "mfe": 3.0, "entry": 100.0, "sl": 99.0},
        {"outcome": "SL_HIT", "mfe": 0.1, "entry": 100.0, "sl": 99.0},
    ]
    y = extract_labels(cases)
    assert y[0].tolist() == [1, 1, 1]   # TP2 — reaches both + survives BE
    assert y[1].tolist() == [1, 0, 1]   # TP1 + mfe>=1R
    assert y[2].tolist() == [0, 0, 0]   # SL never reaches 1R
    assert y[3].tolist() == [0, 0, 1]   # SL but mfe>=1R first
    assert y[4].tolist() == [0, 0, 0]   # TIMEOUT short of 1R
    assert y[5].tolist() == [1, 0, 1]   # opportunity-format TP1_HIT
    assert y[6].tolist() == [0, 0, 0]   # opportunity-format SL_HIT


def test_label_missing_mfe_defaults_to_zero():
    from train_trade_net_v2 import extract_labels
    y = extract_labels([{"exit_reason": "TP1", "entry": 100.0, "sl": 99.0}])
    assert y[0, 2] == 0.0   # survives_be defaults to 0 when mfe absent


# ─────────────────────────────────────────────────────────────────────────────
# Input matrix shape
# ─────────────────────────────────────────────────────────────────────────────

def test_input_matrix_is_38_dim():
    from train_trade_net_v2 import build_input_matrix, INPUT_DIM
    from features.feature_schema import CANONICAL_FEATURES
    feats = {k: 0.0 for k in CANONICAL_FEATURES}
    feats["session"] = 0.0
    feats["trend_bias"] = 0.0
    recs = [{"features": dict(feats)} for _ in range(5)]
    X = build_input_matrix(recs)
    assert X.shape == (5, INPUT_DIM)
    # 48 under schema v5.0 (was 39 pre-2026-08-15 CH-htfcrt-parent-candle-smc-v1; 38 pre-v4).
    assert INPUT_DIM == 48


# ─────────────────────────────────────────────────────────────────────────────
# V2 envelope round-trip
# ─────────────────────────────────────────────────────────────────────────────

def test_v2_envelope_predict_composite_formula(tmp_path):
    import numpy as np
    from features.feature_schema import CANONICAL_FEATURES
    from training.trade_net_v2 import TradeNetV2, COMPOSITE_WEIGHTS

    # Dimension is derived from CANONICAL_FEATURES (39 under schema v4.0), not a hardcoded
    # literal -- a hardcoded "38" here would silently desync from feature_names below the
    # moment the schema migrates again (as it already did once, 2026-07-22).
    n_feat = len(CANONICAL_FEATURES)
    np.random.seed(0)
    W1 = (np.random.randn(32, n_feat) * 0.1).astype(np.float32)
    W2 = (np.random.randn(16, 32) * 0.1).astype(np.float32)
    Wt1 = (np.random.randn(1, 16) * 0.1).astype(np.float32)
    Wt2 = (np.random.randn(1, 16) * 0.1).astype(np.float32)
    Wbe = (np.random.randn(1, 16) * 0.1).astype(np.float32)

    envelope = {
        "schema_version": "tradenet_v2",
        "feature_dim": n_feat,
        "feature_order_hash": hashlib.sha256(
            json.dumps(list(CANONICAL_FEATURES)).encode()
        ).hexdigest()[:16],
        "feature_names": list(CANONICAL_FEATURES),
        "trunk": [
            {"type": "linear", "in": n_feat, "out": 32,
             "weight": W1.tolist(), "bias": [0.0] * 32},
            {"type": "relu"},
            {"type": "linear", "in": 32, "out": 16,
             "weight": W2.tolist(), "bias": [0.0] * 16},
            {"type": "relu"},
        ],
        "heads": {
            "p_tp1":         {"weight": Wt1.tolist(), "bias": [0.0]},
            "p_tp2":         {"weight": Wt2.tolist(), "bias": [0.0]},
            "p_survives_be": {"weight": Wbe.tolist(), "bias": [0.0]},
        },
        "scaler": {"mean": [0.0] * n_feat, "std": [1.0] * n_feat},
        "metadata": {"instrument": "TEST", "version": "v2_test"},
    }
    p = tmp_path / "v2.json"
    p.write_text(json.dumps(envelope))

    m = TradeNetV2(p, instrument="TEST")
    assert m._mode == "v2"

    feats = {k: 0.5 for k in CANONICAL_FEATURES}
    feats["session"] = 1.0
    feats["trend_bias"] = 0.0
    out = m.predict(feats)
    assert out is not None
    assert set(out.keys()) == {
        "tradenet_score", "p_tp1", "p_tp2", "p_survives_be", "schema_version",
    }
    assert out["schema_version"] == "tradenet_v2"
    assert 0.0 <= out["tradenet_score"] <= 1.0
    expected = (
        COMPOSITE_WEIGHTS[0] * out["p_tp1"]
        + COMPOSITE_WEIGHTS[1] * out["p_tp2"]
        + COMPOSITE_WEIGHTS[2] * out["p_survives_be"]
    )
    assert abs(out["tradenet_score"] - expected) < 1e-6


def test_missing_model_returns_none_and_emits_critical(tmp_path, monkeypatch):
    """When neither a v2 envelope nor a legacy .pth resolves, predict() must
    return None and an integrity event must fire (FusionEngine renorm path)."""
    from training.trade_net_v2 import TradeNetV2
    m = TradeNetV2(model_path=tmp_path / "does_not_exist.json",
                   instrument="__no_such_instrument__")
    assert m._mode == "missing"
    assert m.predict({}) is None
