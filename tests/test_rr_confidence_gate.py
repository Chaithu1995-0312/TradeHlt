"""
test_rr_confidence_gate.py — Track 3B tests for the F-044 dof-aware RR confidence gate.

Covers: legacy_scalar byte-parity (the shipped default), chi2_tail / dof_scaled math against known
values, mode validation, and a real-model predict() determinism/identity check.
"""

import math

import pytest

import config_layer.rr.rr_pattern_miner as rpm
from config_layer.rr.rr_pattern_miner import (
    _confidence_bypass,
    _chi2_sf,
    _CONF_BYPASS,
    NanoInferenceEngine,
    DEFAULT_MODEL_PATH,
)


# ── 1. legacy_scalar parity: the helper reduces EXACTLY to `confidence < _CONF_BYPASS` ──────────
@pytest.mark.parametrize("conf", [0.0, 0.1, _CONF_BYPASS - 1e-9, _CONF_BYPASS, _CONF_BYPASS + 1e-9, 0.5, 1.0])
@pytest.mark.parametrize("d_sq,dof", [(2.0, 27), (50.0, 27), (500.0, 27), (1.0, 5)])
def test_legacy_scalar_is_exact_threshold_parity(monkeypatch, conf, d_sq, dof):
    monkeypatch.setattr(rpm, "_GATE_MODE", "legacy_scalar")
    # In legacy mode the gate depends ONLY on confidence (d_sq/dof ignored) — byte-identical to old.
    assert _confidence_bypass(d_sq, dof, conf) == (conf < _CONF_BYPASS)


def test_default_shipped_mode_matches_active_config():
    """Active config (post 2026-07-28 v39 retrain) ships percentile gate + calibrated d_sq_cut.

    legacy_scalar remains available (parity tests above monkeypatch it). rr_fusion stays
    enabled=false — this only asserts the imported gate constants match production JSON.
    """
    assert rpm._GATE_MODE == "percentile"
    assert math.isfinite(rpm._GATE_DSQ_CUT)
    assert rpm._GATE_DSQ_CUT > 0.0


# ── 2. chi2 survival function against known critical values ─────────────────────────────────────
@pytest.mark.parametrize(
    "x,dof,expected",
    [
        (3.841459, 1, 0.05),     # χ²(1) 95th pct
        (5.991465, 2, 0.05),     # χ²(2) 95th pct
        (46.962942, 27, 0.01),   # χ²(27) 99th pct — the dof of the active rr_model
        (0.0, 27, 1.0),          # at 0, whole mass is above
    ],
)
def test_chi2_sf_known_values(x, dof, expected):
    assert _chi2_sf(x, dof) == pytest.approx(expected, abs=1e-4)


def test_chi2_sf_monotonic_decreasing():
    prev = 1.0
    for x in range(0, 120, 5):
        cur = _chi2_sf(float(x), 27)
        assert cur <= prev + 1e-12
        prev = cur


# ── 3. chi2_tail gate: in-distribution points PASS, extreme outliers BYPASS ──────────────────────
def test_chi2_tail_passes_in_distribution(monkeypatch):
    monkeypatch.setattr(rpm, "_GATE_MODE", "chi2_tail")
    monkeypatch.setattr(rpm, "_GATE_P_THRESHOLD", 0.01)
    # min in-sample d_sq from the probe = 4.30, dof=27 → deep in-distribution → must NOT bypass.
    assert _confidence_bypass(4.30, 27, confidence=1e-6) is False
    # median in-sample d_sq ≈ 21.5 → still passes.
    assert _confidence_bypass(21.5, 27, confidence=1e-6) is False
    # a genuine far outlier (χ²(27) 99.9th ≈ 55.5) → bypass.
    assert _confidence_bypass(80.0, 27, confidence=1e-30) is True


# ── 4. dof_scaled gate ──────────────────────────────────────────────────────────────────────────
def test_dof_scaled(monkeypatch):
    monkeypatch.setattr(rpm, "_GATE_MODE", "dof_scaled")
    monkeypatch.setattr(rpm, "_GATE_DOF_SCALED_MAX", 3.0)
    assert _confidence_bypass(2.0 * 27, 27, 1e-6) is False   # d_sq/dof = 2.0 ≤ 3 → pass
    assert _confidence_bypass(4.0 * 27, 27, 1e-6) is True    # d_sq/dof = 4.0 > 3 → bypass


def test_unknown_mode_raises(monkeypatch):
    monkeypatch.setattr(rpm, "_GATE_MODE", "bogus")
    with pytest.raises(ValueError):
        _confidence_bypass(1.0, 27, 0.5)


# ── 4b. percentile gate (F-044 refinement): bypass iff d_sq > empirically-calibrated cut ────────
def test_percentile_mode(monkeypatch):
    monkeypatch.setattr(rpm, "_GATE_MODE", "percentile")
    monkeypatch.setattr(rpm, "_GATE_DSQ_CUT", 56.86)   # the empirical-5%-bypass cut for this model
    assert _confidence_bypass(21.5, 27, 1e-6) is False   # in-body → pass (use RR)
    assert _confidence_bypass(56.85, 27, 1e-30) is False  # just under cut → pass
    assert _confidence_bypass(56.87, 27, 1e-30) is True   # just over cut → bypass
    assert _confidence_bypass(101.0, 27, 1e-30) is True   # far tail → bypass


def test_percentile_mode_is_registered():
    assert "percentile" in rpm._GATE_MODES


def test_percentile_ignores_confidence(monkeypatch):
    # percentile depends ONLY on d_sq, never on the (mis-scaled) scalar confidence.
    monkeypatch.setattr(rpm, "_GATE_MODE", "percentile")
    monkeypatch.setattr(rpm, "_GATE_DSQ_CUT", 40.0)
    assert _confidence_bypass(10.0, 27, 0.0) is False   # conf=0 but d_sq in-body → still pass
    assert _confidence_bypass(50.0, 27, 1.0) is True    # conf=1 but d_sq past cut → still bypass


# ── 6. Part A: train() emits the training_distribution provenance block (percentile-gate contract) ──
def test_train_emits_training_distribution():
    np = pytest.importorskip("numpy")
    pytest.importorskip("sklearn")
    from config_layer.rr.rr_pattern_miner import RRPatternTrainer, N_FEATURES
    rng = np.random.default_rng(0)
    m = 60
    X = rng.normal(size=(m, N_FEATURES)).tolist()
    y_rr = rng.normal(size=m).tolist()
    y_win = rng.integers(0, 2, size=m).tolist()
    state = RRPatternTrainer().train(X, y_rr, y_win)
    td = state["training_distribution"]
    assert set(td) == {"n", "effective_dof", "d_sq_p50", "d_sq_p90", "d_sq_p95", "d_sq_p99"}
    assert td["n"] == m
    assert td["d_sq_p50"] <= td["d_sq_p90"] <= td["d_sq_p95"] <= td["d_sq_p99"]


# ── 5. real-model predict() determinism + legacy-default bypass (F-044 in-sample fact) ──────────
def test_real_model_predict_deterministic_and_bypasses_under_legacy():
    engine = NanoInferenceEngine.load(DEFAULT_MODEL_PATH)
    n = len(engine.W)
    feats = [0.0] * n  # any vector; under legacy the model bypasses ~always (F-044)
    a = engine.predict(features=feats, gaussian_score=0.42, gaussian_p_win=0.6, threshold=0.5)
    b = engine.predict(features=feats, gaussian_score=0.42, gaussian_p_win=0.6, threshold=0.5)
    assert a == b                                   # determinism
    assert a["status"] == "bypassed_low_confidence" # legacy default gate fires
    assert a["final_score"] == pytest.approx(0.42)  # passthrough returns the gaussian score exactly
