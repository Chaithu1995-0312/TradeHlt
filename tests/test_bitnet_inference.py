"""
test_bitnet_inference.py
========================
Unit tests for BitNetModel.predict() and signal threshold logic.

Coverage
--------
1. Shape validation   — wrong-shape input raises ValueError
2. NaN validation     — NaN input raises ValueError
3. Score range        — score is in (-1, 1)
4. Signal thresholds  — correct signal for score > 0.5, < -0.5, neutral
5. Determinism        — same input always produces same score
6. Missing model file — FileNotFoundError on load
7. Scale mismatch     — ValueError on malformed model
"""

import json
import os
import tempfile

import numpy as np
import pytest

from bitnet.bitnet_inference import BitNetModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_export_model(in_dim: int = 24, hidden: int = 16, out_dim: int = 1) -> dict:
    """Build a minimal valid export-schema model dict."""
    rng = np.random.default_rng(0)
    return {
        "layers": [
            {
                "name":    "fc1",
                "weights": rng.integers(0, 2, size=(hidden, in_dim)).tolist(),
                "scale":   rng.uniform(0.5, 1.5, size=hidden).tolist(),
            },
            {
                "name":    "fc2",
                "weights": rng.integers(0, 2, size=(hidden, hidden)).tolist(),
                "scale":   rng.uniform(0.5, 1.5, size=hidden).tolist(),
            },
            {
                "name":    "fc3",
                "weights": rng.integers(0, 2, size=(out_dim, hidden)).tolist(),
                "scale":   rng.uniform(0.5, 1.5, size=out_dim).tolist(),
            },
        ]
    }


def _write_model_file(model_dict: dict) -> str:
    """Write model dict to a temp file, return path."""
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(model_dict, f)
    return path


def _make_vector(seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.uniform(-1.0, 1.0, size=24).astype(np.float32)


@pytest.fixture
def model_path():
    path = _write_model_file(_make_export_model())
    yield path
    os.unlink(path)


@pytest.fixture
def model(model_path):
    return BitNetModel(model_path)


# ---------------------------------------------------------------------------
# Test 1 — Shape validation
# ---------------------------------------------------------------------------

def test_predict_rejects_wrong_shape(model):
    """Input with wrong shape must raise ValueError."""
    bad_vector = np.zeros(20, dtype=np.float32)
    with pytest.raises(ValueError, match="expected shape"):
        model.predict(bad_vector)


def test_predict_rejects_2d_array(model):
    """2D array input must raise ValueError."""
    bad_vector = np.zeros((1, 24), dtype=np.float32)
    with pytest.raises(ValueError, match="expected shape"):
        model.predict(bad_vector)


# ---------------------------------------------------------------------------
# Test 2 — NaN validation
# ---------------------------------------------------------------------------

def test_predict_rejects_nan(model):
    """Vector with NaN must raise ValueError."""
    v = _make_vector()
    v[5] = float("nan")
    with pytest.raises(ValueError, match="NaN"):
        model.predict(v)


def test_predict_rejects_all_nan(model):
    """All-NaN vector must raise ValueError."""
    v = np.full(24, float("nan"), dtype=np.float32)
    with pytest.raises(ValueError, match="NaN"):
        model.predict(v)


# ---------------------------------------------------------------------------
# Test 3 — Score range
# ---------------------------------------------------------------------------

def test_score_in_range(model):
    """score must be strictly in (-1, 1)."""
    v = _make_vector()
    score = model.predict(v)
    assert isinstance(score, float), f"score must be float, got {type(score)}"
    assert -1.0 < score < 1.0, f"score out of (-1, 1) range: {score}"


def test_score_range_multiple_vectors(model):
    """Score must be in (-1, 1) for 50 random vectors."""
    rng = np.random.default_rng(7)
    for _ in range(50):
        v = rng.uniform(-2.0, 2.0, size=24).astype(np.float32)
        score = model.predict(v)
        assert -1.0 < score < 1.0, f"score out of range: {score}"


# ---------------------------------------------------------------------------
# Test 4 — Signal threshold logic
# ---------------------------------------------------------------------------

def _apply_threshold(score: float) -> tuple:
    """Mirror the signal logic from backtest_v2.py."""
    if score > 0.5:
        signal = 1
    elif score < -0.5:
        signal = -1
    else:
        signal = 0
    confidence = abs(score)
    return signal, confidence


def test_signal_high_score():
    """score = 0.8 → signal = 1."""
    signal, confidence = _apply_threshold(0.8)
    assert signal == 1
    assert abs(confidence - 0.8) < 1e-9


def test_signal_low_score():
    """score = -0.8 → signal = -1."""
    signal, confidence = _apply_threshold(-0.8)
    assert signal == -1
    assert abs(confidence - 0.8) < 1e-9


def test_signal_neutral_positive():
    """score = 0.3 (below threshold) → signal = 0."""
    signal, _ = _apply_threshold(0.3)
    assert signal == 0


def test_signal_neutral_negative():
    """score = -0.2 (above -0.5 threshold) → signal = 0."""
    signal, _ = _apply_threshold(-0.2)
    assert signal == 0


def test_signal_exactly_at_threshold_positive():
    """score = 0.5 is NOT above threshold → signal = 0."""
    signal, _ = _apply_threshold(0.5)
    assert signal == 0  # requires strictly > 0.5


def test_signal_exactly_at_threshold_negative():
    """score = -0.5 is NOT below threshold → signal = 0."""
    signal, _ = _apply_threshold(-0.5)
    assert signal == 0  # requires strictly < -0.5


def test_confidence_is_abs_score():
    """confidence == abs(score) for both positive and negative scores."""
    for s in [0.7, -0.7, 0.0, 0.99, -0.99]:
        _, conf = _apply_threshold(s)
        assert abs(conf - abs(s)) < 1e-9, f"confidence mismatch for score={s}"


# ---------------------------------------------------------------------------
# Test 5 — Determinism
# ---------------------------------------------------------------------------

def test_deterministic_same_input(model):
    """Same input must always produce the same score."""
    v = _make_vector(seed=123)
    score1 = model.predict(v)
    score2 = model.predict(v)
    assert score1 == score2, f"Non-deterministic: {score1} != {score2}"


def test_deterministic_two_model_instances():
    """Two models loaded from the same file must produce the same score."""
    path = _write_model_file(_make_export_model(seed=0) if False else _make_export_model())
    try:
        model_a = BitNetModel(path)
        model_b = BitNetModel(path)
        v = _make_vector(seed=77)
        assert model_a.predict(v) == model_b.predict(v)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Test 6 — Missing model file
# ---------------------------------------------------------------------------

def test_missing_model_file_raises():
    """Loading a non-existent model path must raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="not found"):
        BitNetModel("/nonexistent/path/model.json")


# ---------------------------------------------------------------------------
# Test 7 — Malformed model (scale shape mismatch)
# ---------------------------------------------------------------------------

def test_scale_shape_mismatch_raises():
    """scale length != weight output_dim must raise ValueError on predict()."""
    bad_model = {
        "layers": [
            {
                "name":    "fc1",
                "weights": [[1, 0, 1] * 8],  # 1 output, 24 inputs
                "scale":   [0.5, 0.6],        # length 2 — WRONG (should be 1)
            }
        ]
    }
    path = _write_model_file(bad_model)
    try:
        m = BitNetModel(path)
        v = _make_vector()
        with pytest.raises(ValueError, match="scale length"):
            m.predict(v)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Test 8 — Zero vector edge case
# ---------------------------------------------------------------------------

def test_zero_vector_does_not_raise(model):
    """All-zero input must not raise and must return a score in (-1, 1)."""
    v = np.zeros(24, dtype=np.float32)
    score = model.predict(v)
    assert -1.0 < score < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])