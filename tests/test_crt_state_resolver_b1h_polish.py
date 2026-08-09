"""B1h residual polish: continuous DISP→EXP OFF + SHADOW inject + SWEEP>EXP from SHADOW.

Research-shadow only (CRTStateResolver). Production crt_engine_v2 untouched.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from features.crt_state_resolver import CRTStateResolver  # noqa: E402


def test_continuous_disp_to_expansion_default_off():
    """Default continuous_disp_to_expansion=false → DISPLACEMENT dwell stays DISP."""
    r = CRTStateResolver()
    assert r._config["thresholds"].get("continuous_disp_to_expansion", False) is False
    r._memory.current_state = "DISPLACEMENT"
    r._memory.candle_index = 10
    r._memory.displacement_candle_index = 9
    r._memory.displacement_candle_close = 2000.0
    r._memory.displacement_direction = 1
    # Extension that would pass continuous ATR gate if enabled
    raw = {
        "open": 2000.0,
        "close": 2010.0,  # extends past disp_close by 10
        "atr": 0.001,  # atr_abs = 2.01
        "body_ratio": 0.8,
        "candle_range": 12.0,
        "high": 2011.0,
        "low": 1999.0,
    }
    # Via public resolve without inject — must NOT promote to EXPANSION
    # Build a minimal feature dict with required keys for encoder
    # Use _resolve_from_features path directly for isolation
    out = r._resolve_from_features({}, raw_features=raw)
    assert out == "DISPLACEMENT", out


def test_continuous_disp_to_expansion_opt_in():
    r = CRTStateResolver()
    r._config["thresholds"]["continuous_disp_to_expansion"] = True
    r._memory.current_state = "DISPLACEMENT"
    r._memory.candle_index = 10
    r._memory.displacement_candle_index = 9
    r._memory.displacement_candle_close = 2000.0
    r._memory.displacement_direction = 1
    raw = {
        "open": 2000.0,
        "close": 2010.0,
        "atr": 0.001,
        "body_ratio": 0.8,
        "candle_range": 12.0,
        "high": 2011.0,
        "low": 1999.0,
    }
    assert r._expansion_entry_allowed(raw) is True
    out = r._resolve_from_features({}, raw_features=raw)
    assert out == "EXPANSION", out


def test_engine_inject_shadow_pending_overrides_sweep():
    """RANGE + engine RANGE>SHADOW_PENDING → SHADOW_PENDING (not plain SWEEP)."""
    r = CRTStateResolver()
    r._memory.current_state = "RANGE"
    r._memory.candle_index = 5
    # Minimal resolve path: force features via a no-op encoder classify by
    # calling resolve with a dict and engine_state_to.
    # Provide enough keys that encoder won't KeyError on required features.
    from features.feature_schema import CANONICAL_FEATURES

    feats = {name: 0.0 for name in CANONICAL_FEATURES}
    feats.update(
        {
            "open": 2000.0,
            "close": 2001.0,
            "high": 2005.0,
            "low": 1995.0,
            "atr": 0.001,
            "body_ratio": 0.5,
        }
    )
    # Without range_ready, htf_range sweep may not fire; inject still forces SHADOW
    state = r.resolve(feats, engine_state_to="RANGE>SHADOW_PENDING")
    assert state == "SHADOW_PENDING", state
    assert r._memory.pending_displacement_active is True


def test_engine_inject_sweep_to_exp_from_shadow():
    """Engine logs SWEEP>EXPANSION while resolver is in SHADOW_PENDING → EXP."""
    r = CRTStateResolver()
    r._memory.current_state = "SHADOW_PENDING"
    r._memory.pending_displacement_active = True
    r._memory.candle_index = 6
    from features.feature_schema import CANONICAL_FEATURES

    feats = {name: 0.0 for name in CANONICAL_FEATURES}
    feats.update(
        {
            "open": 2000.0,
            "close": 2010.0,
            "high": 2011.0,
            "low": 1999.0,
            "atr": 0.001,
            "body_ratio": 0.8,
        }
    )
    # Continuous SHADOW collapse also returns EXP when pending; inject path must
    # also accept SWEEP>EXPANSION (engine event label for shadow collapse).
    state = r.resolve(feats, engine_state_to="SWEEP>EXPANSION")
    assert state == "EXPANSION", state


def test_engine_inject_disp_to_exp_still_works():
    r = CRTStateResolver()
    r._memory.current_state = "DISPLACEMENT"
    r._memory.displacement_candle_close = 2000.0
    r._memory.displacement_direction = 1
    r._memory.candle_index = 8
    from features.feature_schema import CANONICAL_FEATURES

    feats = {name: 0.0 for name in CANONICAL_FEATURES}
    feats.update(
        {
            "open": 2000.0,
            "close": 2001.0,
            "high": 2002.0,
            "low": 1999.0,
            "atr": 0.001,
            "body_ratio": 0.5,
        }
    )
    state = r.resolve(feats, engine_state_to="DISPLACEMENT>EXPANSION")
    assert state == "EXPANSION", state
