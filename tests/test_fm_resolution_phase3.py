"""Phase-3a / Phase-3b FM resolution — feature_builder + scoring_engine wiring.

Identity-preserving: resolved callables match candle_math / derived_math; compute_scores
output stays GD-004 byte-identical (covered by test_gd004_gd005_identity_closure.py).
"""
from __future__ import annotations

import pytest

from features import candle_math as _cm
from features import derived_math as _dm
from features.fm_resolve import (
    PHASE3A_FEATURE_BUILDER_FM_IDS,
    PHASE3B_SCORING_FM_IDS,
    PHASE3C_CAUSAL_STRUCTURE_FM_IDS,
    assert_registry_identity,
    bind_phase3a_feature_builder_callables,
    bind_phase3b_scoring_callables,
    bind_phase3c_causal_structure_callables,
    clear_fm_resolve_cache,
    resolve_fm,
    resolve_fm_callable,
)
from engines.scoring_engine import compute_scores, _FM_SCORING
from features.crt_feature_builder import _FM_BUILDER
from features.causal_structure import _FM_CAUSAL


@pytest.fixture(autouse=True)
def _clear_caches():
    clear_fm_resolve_cache()
    yield
    clear_fm_resolve_cache()


# ── Phase-3b: FM-029 scoring ─────────────────────────────────────────────────

def test_phase3b_fm029_identity():
    assert_registry_identity("FM-029", _dm.disp_strength_atr_rescale)
    assert resolve_fm_callable("FM-029") is _dm.disp_strength_atr_rescale


def test_bind_phase3b_scoring_callables():
    bound = bind_phase3b_scoring_callables()
    assert set(bound) == PHASE3B_SCORING_FM_IDS
    assert bound["FM-029"] is _dm.disp_strength_atr_rescale


def test_scoring_engine_module_binds_fm029():
    assert "FM-029" in _FM_SCORING
    assert _FM_SCORING["FM-029"] is _dm.disp_strength_atr_rescale


def test_compute_scores_uses_fm029_math():
    """Sanity: breakout component uses move/atr rescale (FM-029 as-wired)."""
    got = compute_scores(
        body_ratio=0.5,
        move=1.0,
        atr=0.5,
        retest_depth=0.5,
        candles_since_retest=0,
        sweep_detected=False,
        double_sweep=False,
        lambda_decay=0.05,
        score_weights=(0.35, 0.25, 0.20, 0.20),
    )
    # disp = 1.0/0.5 = 2.0; s_breakout = 0.5*0.5 + 0.5*min(2/2,1) = 0.25+0.5 = 0.75
    assert got["breakout"] == 0.75


# ── Phase-3a: FM-001 / FM-002 / FM-010 feature builder ────────────────────────

def test_phase3a_fm001_fm002_identity():
    assert_registry_identity("FM-001", _cm.body_size)
    assert_registry_identity("FM-002", _cm.candle_range)
    assert resolve_fm_callable("FM-001") is _cm.body_size
    assert resolve_fm_callable("FM-002") is _cm.candle_range


def test_bind_phase3a_feature_builder_callables():
    bound = bind_phase3a_feature_builder_callables()
    assert set(bound) == PHASE3A_FEATURE_BUILDER_FM_IDS
    assert bound["FM-001"] is _cm.body_size
    assert bound["FM-002"] is _cm.candle_range
    assert resolve_fm("FM-010").kind == "composition"


def test_feature_builder_module_binds_geometry_fms():
    assert set(_FM_BUILDER) == PHASE3A_FEATURE_BUILDER_FM_IDS
    assert _FM_BUILDER["FM-001"] is _cm.body_size
    assert _FM_BUILDER["FM-002"] is _cm.candle_range


def test_phase3a_fm010_float_parity_with_body_ratio():
    fn = _FM_BUILDER["FM-010"]
    vectors = [
        (100.0, 105.0, 99.0, 104.0),
        (50.0, 50.0, 50.0, 50.0),
        (10.0, 12.0, 8.0, 9.0),
    ]
    for o, h, l, c in vectors:
        assert fn(o, h, l, c) == pytest.approx(_cm.body_ratio(o, h, l, c))


# ── Phase-3c: FM-025 / FM-026 causal_structure liquidity ─────────────────────

def test_phase3c_fm025_fm026_identity():
    assert_registry_identity("FM-025", _dm.liquidity_distance)
    assert_registry_identity("FM-026", _dm.liquidity_pressure_score)
    assert resolve_fm_callable("FM-025") is _dm.liquidity_distance
    assert resolve_fm_callable("FM-026") is _dm.liquidity_pressure_score


def test_bind_phase3c_causal_structure_callables():
    bound = bind_phase3c_causal_structure_callables()
    assert set(bound) == PHASE3C_CAUSAL_STRUCTURE_FM_IDS
    assert bound["FM-025"] is _dm.liquidity_distance
    assert bound["FM-026"] is _dm.liquidity_pressure_score


def test_causal_structure_module_binds_liquidity_fms():
    assert set(_FM_CAUSAL) == PHASE3C_CAUSAL_STRUCTURE_FM_IDS
    assert _FM_CAUSAL["FM-025"] is _dm.liquidity_distance
    assert _FM_CAUSAL["FM-026"] is _dm.liquidity_pressure_score


def test_phase3c_liquidity_float_parity():
    """As-wired NaN→10.0 sentinel lives in causal_structure; scalar FM path is pure."""
    d = _FM_CAUSAL["FM-025"](100.0, 0.01, 101.0, 98.0)
    assert d == pytest.approx(_dm.liquidity_distance(100.0, 0.01, 101.0, 98.0))
    p = _FM_CAUSAL["FM-026"](d)
    assert p == pytest.approx(_dm.liquidity_pressure_score(d))
