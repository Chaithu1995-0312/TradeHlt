"""
tests/regime/test_market_state_cluster_engine.py
=================================================
Tests for MarketStateClusterEngine (Part 6).

Covers:
    1. TREND_EXPANSION from high mean_rr + high win_rate
    2. RANGE_TRAP from high trap_freq + high sweep
    3. Cooldown prevents chattering on alternating inputs
    4. None cluster_stats → TRANSITIONAL_CHAOS with low confidence
    5. All 8 MarketStateOutput fields are present
    6. VOLATILE_REVERSAL from high std_rr + double_sweep
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_SRC = str(Path(__file__).parents[2] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from regime.market_state_cluster_engine import (
    MarketStateClusterEngine,
    MarketStateOutput,
    TREND_EXPANSION,
    RANGE_TRAP,
    TRANSITIONAL_CHAOS,
    VOLATILE_REVERSAL,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_cluster_stats(
    cluster_id: int = 0,
    n_samples: int = 50,
    win_rate: float = 0.5,
    mean_rr: float = 0.0,
    std_rr: float = 0.5,
    trap_frequency: float = 0.2,
    staleness_days: float = 5.0,
    centroid: list = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        cluster_id     = cluster_id,
        n_samples      = n_samples,
        win_rate       = win_rate,
        mean_rr        = mean_rr,
        std_rr         = std_rr,
        trap_frequency = trap_frequency,
        staleness_days = staleness_days,
        centroid       = centroid or [],
    )


def _base_features(**overrides) -> dict:
    base = {
        "volatility_ratio":          1.0,
        "sweep_detected":            0.0,
        "double_sweep":              0.0,
        "break_of_structure":        0.0,
        "disp_strength":             0.0,
        "liquidity_distance":        5.0,
        "liquidity_pressure_score":  0.2,
        "volume_spike":              0.0,
        "atr":                       0.001,
        "retest_depth":              0.3,
        "candles_since_retest":      5.0,
    }
    base.update(overrides)
    return base


# ── Test 1: TREND_EXPANSION ───────────────────────────────────────────────────

def test_trend_expansion_from_stats():
    """TREND_EXPANSION wins when:
      - mean_rr is high (≥2.0 saturates the 0.35*(rr/2) term to 0.35)
      - disp_strength is 0 (BREAKOUT_CONTINUATION gains more from disp: 0.20 vs 0.10)
      - candles_since_retest=0 (suppresses the +0.10 recency bonus in BREAKOUT)
    Scores with these inputs: TREND=0.7325, BREAKOUT=0.7125  (margin +0.02)
    """
    engine = MarketStateClusterEngine(min_cluster_samples=5, cooldown_bars=0)
    cs = _make_cluster_stats(
        win_rate=0.75, mean_rr=2.0, std_rr=0.3, trap_frequency=0.05
    )
    features = _base_features(
        break_of_structure=1.0,
        # disp_strength=0.0 (default) — avoids BREAKOUT's 0.20*disp advantage
        # candles_since_retest=0 — suppresses BREAKOUT's +0.10 recency bonus
        candles_since_retest=0,
    )
    result = engine.classify(features, cluster_stats=cs)
    assert result.market_state == TREND_EXPANSION, (
        f"Expected TREND_EXPANSION, got {result.market_state}"
    )


# ── Test 2: RANGE_TRAP ────────────────────────────────────────────────────────

def test_range_trap_from_stats():
    engine = MarketStateClusterEngine(min_cluster_samples=5, cooldown_bars=0)
    cs = _make_cluster_stats(
        win_rate=0.30, mean_rr=-0.1, std_rr=0.4, trap_frequency=0.75
    )
    features = _base_features(
        sweep_detected=1.0,
        double_sweep=1.0,
    )
    result = engine.classify(features, cluster_stats=cs)
    assert result.market_state == RANGE_TRAP, (
        f"Expected RANGE_TRAP, got {result.market_state}"
    )


# ── Test 3: Cooldown prevents chattering ─────────────────────────────────────

def test_cooldown_prevents_chattering():
    cooldown = 5
    engine = MarketStateClusterEngine(min_cluster_samples=1, cooldown_bars=cooldown)

    # Setup alternating cluster stats
    cs_trend = _make_cluster_stats(
        win_rate=0.80, mean_rr=1.5, trap_frequency=0.05
    )
    cs_trap = _make_cluster_stats(
        win_rate=0.25, mean_rr=-0.1, trap_frequency=0.80
    )

    feat_trend = _base_features(break_of_structure=1.0, disp_strength=1.5)
    feat_trap  = _base_features(sweep_detected=1.0, double_sweep=1.0)

    # First call sets initial state
    r0 = engine.classify(feat_trend, cluster_stats=cs_trend)
    initial_state = r0.market_state

    # Alternate inputs rapidly — state should NOT change within cooldown window
    states = [initial_state]
    for i in range(cooldown - 1):
        if i % 2 == 0:
            r = engine.classify(feat_trap,  cluster_stats=cs_trap)
        else:
            r = engine.classify(feat_trend, cluster_stats=cs_trend)
        states.append(r.market_state)

    # All within-cooldown states should match initial (cooldown suppresses transitions)
    transitions = sum(1 for i in range(1, len(states)) if states[i] != states[i - 1])
    assert transitions == 0, (
        f"Cooldown failed: {transitions} transition(s) within {cooldown}-bar window"
    )


# ── Test 4: None cluster_stats → TRANSITIONAL_CHAOS, low confidence ──────────

def test_no_cluster_stats_transitional_chaos():
    engine = MarketStateClusterEngine(cooldown_bars=0)
    result = engine.classify(_base_features(), cluster_stats=None)
    assert result.market_state == TRANSITIONAL_CHAOS, (
        f"Expected TRANSITIONAL_CHAOS without stats, got {result.market_state}"
    )
    assert result.cluster_confidence == 0.0, (
        f"Expected confidence=0.0 without stats, got {result.cluster_confidence}"
    )


# ── Test 5: All 8 output fields present ──────────────────────────────────────

def test_output_fields():
    engine = MarketStateClusterEngine(cooldown_bars=0)
    result = engine.classify(_base_features())
    assert isinstance(result, MarketStateOutput)
    required = {
        "market_state", "cluster_id", "cluster_confidence",
        "state_persistence", "volatility_profile", "liquidity_profile",
        "trap_probability", "compression_score",
    }
    missing = required - set(vars(result).keys())
    assert not missing, f"Missing MarketStateOutput fields: {missing}"


# ── Test 6: VOLATILE_REVERSAL ─────────────────────────────────────────────────

def test_volatile_reversal():
    engine = MarketStateClusterEngine(min_cluster_samples=5, cooldown_bars=0)
    cs = _make_cluster_stats(
        win_rate=0.45, mean_rr=0.2, std_rr=1.8, trap_frequency=0.30
    )
    features = _base_features(
        sweep_detected=1.0,
        double_sweep=1.0,
        volume_spike=1.0,
        volatility_ratio=2.5,
    )
    result = engine.classify(features, cluster_stats=cs)
    assert result.market_state == VOLATILE_REVERSAL, (
        f"Expected VOLATILE_REVERSAL, got {result.market_state}"
    )
