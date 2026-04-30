"""
test_regime_classifier.py
==========================
Phase B: Regime Switching Layer tests.

Covers:
  RegimeClassifier:
    - HIGH_VOLATILITY when ATR > threshold
    - TRENDING when trend_score > threshold (and ATR normal)
    - RANGING as default
    - Cooldown prevents rapid switching
    - Reset cooldown works
    - Exception in features returns RANGING (safe)
    - Custom thresholds honoured

  ConfigRouter:
    - Default map: TRENDING → BALANCED, RANGING → SAFE, HIGH_VOLATILITY → AGGRESSIVE
    - Unknown regime → DEFAULT → SAFE
    - Custom map injected
    - select_profile returns correct profile
    - select_config returns dict when file exists
    - select_config returns None when file missing (no crash)
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.regime.regime_classifier import (
    RegimeClassifier,
    REGIME_TRENDING,
    REGIME_RANGING,
    REGIME_HIGH_VOLATILITY,
)
from src.regime.config_router import ConfigRouter


# ── RegimeClassifier tests ────────────────────────────────────────────────────

def test_classify_high_volatility():
    clf = RegimeClassifier(atr_high_threshold=0.8, trend_threshold=0.7)
    regime = clf.classify({"atr": 0.9, "trend_score": 0.3})
    assert regime == REGIME_HIGH_VOLATILITY


def test_classify_high_volatility_overrides_trending():
    """ATR > threshold → HIGH_VOLATILITY even if trend_score is high."""
    clf = RegimeClassifier(atr_high_threshold=0.8, trend_threshold=0.7)
    regime = clf.classify({"atr": 0.85, "trend_score": 0.9})
    assert regime == REGIME_HIGH_VOLATILITY


def test_classify_trending():
    clf = RegimeClassifier(atr_high_threshold=0.8, trend_threshold=0.7)
    regime = clf.classify({"atr": 0.4, "trend_score": 0.8})
    assert regime == REGIME_TRENDING


def test_classify_ranging_default():
    clf = RegimeClassifier(atr_high_threshold=0.8, trend_threshold=0.7)
    regime = clf.classify({"atr": 0.3, "trend_score": 0.4})
    assert regime == REGIME_RANGING


def test_classify_boundary_atr_exact():
    """ATR exactly at threshold → NOT HIGH_VOLATILITY (strictly greater)."""
    clf = RegimeClassifier(atr_high_threshold=0.8, trend_threshold=0.7)
    regime = clf.classify({"atr": 0.8, "trend_score": 0.4})
    assert regime == REGIME_RANGING


def test_classify_boundary_trend_exact():
    """trend_score exactly at threshold → NOT TRENDING (strictly greater)."""
    clf = RegimeClassifier(atr_high_threshold=0.8, trend_threshold=0.7)
    regime = clf.classify({"atr": 0.4, "trend_score": 0.7})
    assert regime == REGIME_RANGING


def test_cooldown_prevents_rapid_switch():
    """After switching, cooldown blocks regime change for N candles."""
    clf = RegimeClassifier(
        atr_high_threshold=0.8, trend_threshold=0.7, cooldown_candles=3
    )
    # First call: RANGING
    r1 = clf.classify({"atr": 0.3, "trend_score": 0.4})
    assert r1 == REGIME_RANGING

    # Next call would be TRENDING but cooldown prevents switch
    r2 = clf.classify({"atr": 0.3, "trend_score": 0.85})
    # cooldown_candles=3, only 1 candle elapsed → still RANGING
    assert r2 == REGIME_RANGING


def test_cooldown_allows_switch_after_n_candles():
    """After N candles, cooldown expires and switch is allowed."""
    clf = RegimeClassifier(
        atr_high_threshold=0.8, trend_threshold=0.7, cooldown_candles=3
    )
    # Establish RANGING
    clf.classify({"atr": 0.3, "trend_score": 0.4})

    # Call 3 times with TRENDING signal → should switch on candle 3
    for _ in range(3):
        result = clf.classify({"atr": 0.3, "trend_score": 0.85})
    assert result == REGIME_TRENDING


def test_reset_cooldown():
    clf = RegimeClassifier(cooldown_candles=5)
    clf.classify({"atr": 0.3, "trend_score": 0.4})  # RANGING
    clf.classify({"atr": 0.3, "trend_score": 0.9})  # should be blocked
    clf.reset_cooldown()
    result = clf.classify({"atr": 0.3, "trend_score": 0.9})
    assert result == REGIME_TRENDING


def test_exception_returns_ranging():
    """If features cause an exception, RANGING is returned (safe fallback)."""
    clf = RegimeClassifier()
    # Pass None as features — should not raise, should return RANGING
    result = clf.classify(None)  # type: ignore
    assert result == REGIME_RANGING


def test_missing_features_defaults_gracefully():
    """Empty features dict → defaults to 0.5 for all → RANGING."""
    clf = RegimeClassifier(atr_high_threshold=0.8, trend_threshold=0.7)
    result = clf.classify({})
    assert result == REGIME_RANGING


def test_current_regime_property():
    clf = RegimeClassifier()
    assert clf.current_regime is None
    clf.classify({"atr": 0.3, "trend_score": 0.4})
    assert clf.current_regime == REGIME_RANGING


def test_custom_thresholds_respected():
    """Lower thresholds should trigger regime switches sooner."""
    clf = RegimeClassifier(atr_high_threshold=0.5, trend_threshold=0.4)
    # With low threshold, ATR=0.6 > 0.5 → HIGH_VOLATILITY
    assert clf.classify({"atr": 0.6, "trend_score": 0.3}) == REGIME_HIGH_VOLATILITY
    clf.reset_cooldown()
    # trend_score=0.5 > 0.4 → TRENDING
    assert clf.classify({"atr": 0.3, "trend_score": 0.5}) == REGIME_TRENDING


# ── ConfigRouter tests ─────────────────────────────────────────────────────────

def test_router_default_map_trending():
    router = ConfigRouter()
    assert router.select_profile(REGIME_TRENDING) == "BALANCED"


def test_router_default_map_ranging():
    router = ConfigRouter()
    assert router.select_profile(REGIME_RANGING) == "SAFE"


def test_router_default_map_high_volatility():
    router = ConfigRouter()
    assert router.select_profile(REGIME_HIGH_VOLATILITY) == "AGGRESSIVE"


def test_router_unknown_regime_returns_safe():
    router = ConfigRouter()
    profile = router.select_profile("UNKNOWN_REGIME")
    assert profile == "SAFE"


def test_router_custom_map_injected():
    custom_map = {
        "TRENDING": "AGGRESSIVE",
        "RANGING": "BALANCED",
        "DEFAULT": "SAFE",
    }
    router = ConfigRouter(regime_map=custom_map)
    assert router.select_profile("TRENDING") == "AGGRESSIVE"
    assert router.select_profile("RANGING") == "BALANCED"
    assert router.select_profile("UNKNOWN") == "SAFE"


def test_router_get_map_returns_copy():
    router = ConfigRouter()
    m1 = router.get_map()
    m1["TRENDING"] = "MODIFIED"
    m2 = router.get_map()
    assert m2["TRENDING"] != "MODIFIED"


def test_router_select_config_returns_dict(tmp_path):
    """select_config loads JSON file matching profile name."""
    cfg_data = {"version": "test_safe", "fusion_min_score": 0.65}
    cfg_file = tmp_path / "v1_safe.json"
    cfg_file.write_text(json.dumps(cfg_data))

    router = ConfigRouter()
    result = router.select_config(REGIME_RANGING, str(tmp_path))
    assert result is not None
    assert result["version"] == "test_safe"


def test_router_select_config_missing_returns_none(tmp_path):
    """select_config returns None without raising when no matching file."""
    router = ConfigRouter()
    result = router.select_config(REGIME_RANGING, str(tmp_path))
    assert result is None


def test_router_select_config_missing_dir_returns_none():
    """select_config returns None when config_dir doesn't exist."""
    router = ConfigRouter()
    result = router.select_config(REGIME_TRENDING, "/nonexistent/path/xyz")
    assert result is None


def test_router_loads_from_json_file(tmp_path):
    """ConfigRouter loads regime map from JSON file when provided."""
    map_data = {
        "TRENDING": "AGGRESSIVE",
        "RANGING": "SAFE",
        "HIGH_VOLATILITY": "BALANCED",
    }
    map_file = tmp_path / "regime_map.json"
    map_file.write_text(json.dumps(map_data))

    router = ConfigRouter(map_path=str(map_file))
    assert router.select_profile("TRENDING") == "AGGRESSIVE"
    assert router.select_profile("HIGH_VOLATILITY") == "BALANCED"