"""EPIC-84 L-C (src/engines): crt_engine.compute() no longer silently defaults
candles_since_sweep/sweep_detected to 0/False when absent from BOTH features
and context — it raises (caught by compute()'s own try/except, which already
converts any exception into a safe score=0.0 REJECT with a reason), matching
every other required field in the same call which already used bare indexing.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from engines import crt_engine  # noqa: E402

_WEIGHTS_CTX = {"score_component_weights": [0.35, 0.25, 0.20, 0.20]}

_FEATURES = {
    "body_ratio": 0.62, "disp_strength": 0.5, "atr": 0.004,
    "retest_depth": 0.41, "double_sweep": False,
    "candles_since_sweep": 3, "sweep_detected": True,
}


def test_compute_succeeds_with_both_features_present():
    result = crt_engine.compute("t", dict(_FEATURES), dict(_WEIGHTS_CTX))
    assert "score" in result and "reason" not in result


def test_compute_reads_candles_since_sweep_from_context_when_absent_from_features():
    features = {k: v for k, v in _FEATURES.items() if k != "candles_since_sweep"}
    context = {**_WEIGHTS_CTX, "candles_since_sweep": 7}
    result = crt_engine.compute("t", features, context)
    assert "score" in result and "reason" not in result


def test_compute_rejects_when_candles_since_sweep_absent_from_both():
    features = {k: v for k, v in _FEATURES.items() if k != "candles_since_sweep"}
    result = crt_engine.compute("t", features, dict(_WEIGHTS_CTX))
    assert result["score"] == 0.0
    assert "candles_since_sweep" in result["reason"]


def test_compute_rejects_when_sweep_detected_absent_from_both():
    features = {k: v for k, v in _FEATURES.items() if k != "sweep_detected"}
    result = crt_engine.compute("t", features, dict(_WEIGHTS_CTX))
    assert result["score"] == 0.0
    assert "sweep_detected" in result["reason"]
