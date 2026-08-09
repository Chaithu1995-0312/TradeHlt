"""
IC-007 PLAN-001 — retest_min_depth_atr_fraction HOW migration.

Guarantees:
  1. Default 0.10 preserves legacy `0.1 * atr` floor (default-parity).
  2. Changing only the HOW value changes the computed floor (dynamism).
  3. Fail-closed validation: finite and >= 0.
  4. Production load surfaces the key through CRTConfig.
  5. No PLAN-002/003 side effects.

Does not claim mass externalization of other HOW candidates.
"""
from __future__ import annotations

import math
from datetime import datetime

import pytest

from config_layer.config_builder import ConfigBuilder
from config_layer.crt_engine_v2 import (
    CRTConfig,
    Candle,
    Direction,
    EngineState,
    Range,
    StateMachine,
)
from config_layer.production_config import PROD_VERSION, load_prod_config_from_registry


def _min_depth_floor(cfg: CRTConfig, atr: float) -> float:
    """Mirror try_expansion_to_retest floor formula (single authority)."""
    return cfg.retest_min_depth_atr_fraction * atr if atr > 0 else 0.0


def test_dataclass_default_is_legacy_tenth():
    cfg = CRTConfig()
    assert cfg.retest_min_depth_atr_fraction == pytest.approx(0.10)


def test_default_parity_matches_legacy_literal():
    """Omitted/default HOW value must equal the pre-migration 0.1 * atr floor."""
    atr = 2.5
    legacy = 0.1 * atr
    cfg = CRTConfig()  # missing production override → dataclass default
    assert _min_depth_floor(cfg, atr) == pytest.approx(legacy)
    cfg_explicit = CRTConfig(retest_min_depth_atr_fraction=0.10)
    assert _min_depth_floor(cfg_explicit, atr) == pytest.approx(legacy)


def test_dynamism_how_value_changes_floor():
    """Changing only retest_min_depth_atr_fraction must change min_depth."""
    atr = 2.0
    floor_default = _min_depth_floor(CRTConfig(), atr)
    floor_tight = _min_depth_floor(CRTConfig(retest_min_depth_atr_fraction=0.5), atr)
    floor_off = _min_depth_floor(CRTConfig(retest_min_depth_atr_fraction=0.0), atr)
    assert floor_default == pytest.approx(0.2)
    assert floor_tight == pytest.approx(1.0)
    assert floor_off == pytest.approx(0.0)
    assert floor_tight != floor_default
    assert floor_off != floor_default


def test_fail_closed_rejects_negative_and_non_finite():
    with pytest.raises(ValueError, match="retest_min_depth_atr_fraction"):
        CRTConfig(retest_min_depth_atr_fraction=-0.01)
    with pytest.raises(ValueError, match="retest_min_depth_atr_fraction"):
        CRTConfig(retest_min_depth_atr_fraction=float("nan"))
    with pytest.raises(ValueError, match="retest_min_depth_atr_fraction"):
        CRTConfig(retest_min_depth_atr_fraction=float("inf"))


def test_config_builder_override_and_default():
    base = ConfigBuilder.build("BNBUSDT")
    assert base.retest_min_depth_atr_fraction == pytest.approx(0.10)
    tight = ConfigBuilder.build(
        "BNBUSDT", overrides={"retest_min_depth_atr_fraction": 0.25}
    )
    assert tight.retest_min_depth_atr_fraction == pytest.approx(0.25)


def test_production_load_exposes_how_key():
    cfg = load_prod_config_from_registry(PROD_VERSION, "BNBUSDT")
    assert cfg.retest_min_depth_atr_fraction == pytest.approx(0.10)


def test_try_expansion_to_retest_default_parity_vs_dynamism():
    """
    Controlled fixture: shallow retrace passes floor at 0.10*ATR but fails at 0.50*ATR.
    Default path admits; tight HOW rejects — dynamism on the live guard.
    """
    atr = 10.0
    # depth_abs = close - l_ref = 101 - 100 = 1.0 → 0.10*ATR=1.0 borderline;
    # use 1.05 so default floor 1.0 admits, tight floor 5.0 rejects.
    # Actually depth_abs must also clear adaptive ceiling — set ceiling loose.
    def _sm(frac: float) -> tuple[StateMachine, EngineState, Candle]:
        cfg = CRTConfig(
            retest_min_depth_atr_fraction=frac,
            retest_depth_max=1.0,
            retest_atr_depth_fraction=1.0,
            max_displacement_strength=10.0,
        )
        sm = StateMachine(cfg)
        st = EngineState()
        st.current_state = __import__(
            "config_layer.crt_engine_v2", fromlist=["CRTState"]
        ).CRTState.EXPANSION
        st.atr = atr
        st.direction = Direction.LONG
        st.active_range = Range(
            h_ref=120.0,
            l_ref=100.0,
            equilibrium=110.0,
            formed_at=datetime(2024, 1, 1),
            htf_candle_id="T",
            session="LONDON",
        )
        st.displacement_candle = Candle(
            timestamp=datetime(2024, 1, 1, 12, 0),
            open=100,
            high=112,
            low=99,
            close=110,
            volume=1,
            index=5,
        )
        st.current_candle_index = 10
        # depth_abs = 101.5 - 100 = 1.5; default floor=1.0 pass; tight 0.5*10=5.0 reject
        retest = Candle(
            timestamp=datetime(2024, 1, 1, 13, 0),
            open=102,
            high=103,
            low=100.5,
            close=101.5,
            volume=1,
            index=10,
        )
        return sm, st, retest

    sm_def, st_def, c_def = _sm(0.10)
    # floor check only — may still fail other gates; we only assert relative dynamism
    # by comparing min_depth computation path via public API result differences when
    # depth is between floors.
    admitted_default = sm_def.try_expansion_to_retest(st_def, c_def, atr)
    sm_tight, st_tight, c_tight = _sm(0.50)
    admitted_tight = sm_tight.try_expansion_to_retest(st_tight, c_tight, atr)
    assert admitted_default is True
    assert admitted_tight is False


def test_zero_atr_floor_is_zero():
    assert _min_depth_floor(CRTConfig(), 0.0) == 0.0
