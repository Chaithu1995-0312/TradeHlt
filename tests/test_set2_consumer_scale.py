"""Set-2 consumer-scale program (2026-10-07): the Decision-4 regime arm + activation pins.

1. DEFAULT PARITY   — with `regime_trend_confirmation` absent or "none", detect_regime is
                      byte-identical to the pre-change behaviour (the key is tunability, not authority).
2. z-CONFIRM ARM    — "trend_strength_z" additionally requires |z| > thr AND sign(z) == sign(ema_spread);
                      a missing z fails closed to not-trend.
3. STRICTNESS       — an unrecognised mode raises; no silent fall-through (§6.5).
4. ACTIVATION PINS  — the active config selects the corrected arm on BOTH switches, and the Decision-4
                      arm is NOT armed on it (it is a measured shadow arm only).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from config_layer.production_config import get_prod_section        # noqa: E402
from core.engine_runner import DUAL_ENGINE_DEFAULTS, detect_regime  # noqa: E402

BASE = dict(DUAL_ENGINE_DEFAULTS)
TREND = {"ema_spread": 0.4, "momentum_score": 0.5, "volatility_ratio": 1.0}


def test_default_and_none_are_byte_identical():
    for f in (TREND, {**TREND, "ema_spread": 0.01}, {"ema_spread": 0.0, "momentum_score": 0.0, "volatility_ratio": 0.5}):
        assert detect_regime(f, BASE) == detect_regime(f, {**BASE, "regime_trend_confirmation": "none"})


def test_z_confirmation_requires_magnitude_and_sign_agreement():
    cfg = {**BASE, "regime_trend_confirmation": "trend_strength_z", "regime_trend_strength_z_threshold": 1.5}
    assert detect_regime({**TREND, "trend_strength_z": 2.0}, cfg) == "trend"
    assert detect_regime({**TREND, "trend_strength_z": 1.0}, cfg) != "trend"      # below threshold
    assert detect_regime({**TREND, "trend_strength_z": -2.0}, cfg) != "trend"     # sign disagrees with spread
    assert detect_regime(TREND, cfg) != "trend"                                   # missing z fails closed


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        detect_regime(TREND, {**BASE, "regime_trend_confirmation": "bogus"})


def test_activation_pins_on_active_config():
    assert get_prod_section("feature_pipeline")["normalization_basis"] == "atr_absolute"
    assert get_prod_section("gate_intelligence")["gate_vol_atr_basis"] == "absolute"
    dual = get_prod_section("engine_runner")["dual_engine"]
    assert dual.get("regime_trend_confirmation", "none") == "none", (
        "Decision-4 arm must stay un-armed on the active config until measured and approved"
    )
