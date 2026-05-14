"""
Tests for [PATCH 7] max_displacement_strength guard in StateMachine.try_expansion_to_retest().

When the displacement candle's wick_size / ATR exceeds max_displacement_strength,
the engine must reject the retest and never open a trade for that setup.
"""

import pytest
from datetime import datetime
from dataclasses import replace

from config_layer.crt_engine_v2 import CRTConfig, CRTEngine, EngineState, StateMachine


# ── Minimal helpers ──────────────────────────────────────────────────────────

def _make_candle(ts_str: str, o: float, h: float, l: float, c: float):
    """Create a minimal Candle for testing."""
    from config_layer.crt_engine_v2 import Candle
    return Candle(
        timestamp=datetime.fromisoformat(ts_str),
        open=o, high=h, low=l, close=c,
        volume=1.0,
    )


def _default_cfg(**kwargs) -> CRTConfig:
    """Return a CRTConfig with test-friendly defaults."""
    base = {"max_displacement_strength": 2.0}
    base.update(kwargs)
    return replace(CRTConfig(), **base)


# ── StateMachine unit tests ───────────────────────────────────────────────────

class TestDispStrengthFilter:
    """
    Drive StateMachine.try_expansion_to_retest() directly to check the guard.
    """

    def _make_state_with_displacement(
        self,
        wick_size: float,
        atr: float,
        cfg: CRTConfig = None,
    ) -> EngineState:
        """
        Build an EngineState that is in EXPANSION phase with a displacement candle
        whose wick_size/atr = given ratio.
        """
        from config_layer.crt_engine_v2 import (
            EngineState, CRTState, Direction, Range, SweepEvent
        )
        state = EngineState()
        state.current_state = CRTState.EXPANSION
        state.direction = Direction.LONG
        state.atr = atr
        state.current_candle_index = 100

        # Fake range: h_ref=1.10, l_ref=1.09 (size=0.01)
        state.active_range = Range(
            h_ref=1.10, l_ref=1.09,
            equilibrium=1.095,
            formed_at=datetime.fromisoformat("2024-01-01T07:00:00"),
            htf_candle_id="test-htf",
            session="LONDON",
        )

        # Fake displacement candle: wick_size = high - low = wick_size param.
        # Use l=0.0 so that high - low = wick_size - 0.0 is exact in float
        # (avoids (1.08 + x) - 1.08 ≠ x rounding artifact).
        # Division wick_size/atr is also exact when wick_size = N * atr (power-of-2 multiple).
        state.displacement_candle = _make_candle(
            "2024-01-01T08:00:00",
            o=wick_size, h=wick_size, l=0.0, c=wick_size,
        )

        # Fake sweep event (required)
        state.sweep_event = SweepEvent(
            candle=_make_candle("2024-01-01T07:45:00", 1.09, 1.09, 1.088, 1.089),
            price=1.089,
            direction=Direction.LONG,
            candle_index=95,
            double_confirmed=False,
        )
        return state

    def test_high_disp_rejects_retest(self):
        """wick_size/ATR = 3.0 > max=2.0 → retest blocked, trade never opens."""
        cfg = _default_cfg(max_displacement_strength=2.0)
        sm = StateMachine(cfg)
        state = self._make_state_with_displacement(wick_size=0.006, atr=0.002)  # ratio=3.0

        # Candle whose close is inside the range (valid retest depth)
        retest_candle = _make_candle("2024-01-01T09:00:00", 1.091, 1.092, 1.090, 1.0905)
        result = sm.try_expansion_to_retest(state, retest_candle, atr=0.002, ev_logger=None)

        assert result is False, "High disp_strength should block retest"
        assert state.retest_candle is None, "retest_candle must not be set when blocked"
        assert state.retest_candle_index == 0, "retest_candle_index must not change from default (0) when blocked"

    def test_normal_disp_allows_retest(self):
        """wick_size/ATR = 1.5 ≤ max=2.0 → retest allowed."""
        cfg = _default_cfg(max_displacement_strength=2.0)
        sm = StateMachine(cfg)
        state = self._make_state_with_displacement(wick_size=0.003, atr=0.002)  # ratio=1.5

        retest_candle = _make_candle("2024-01-01T09:00:00", 1.091, 1.092, 1.090, 1.0905)
        result = sm.try_expansion_to_retest(state, retest_candle, atr=0.002, ev_logger=None)

        assert result is True, "Normal disp_strength should allow retest"
        assert state.retest_candle is retest_candle

    def test_exact_threshold_allowed(self):
        """wick_size/ATR = 2.0 exactly → allowed (filter uses strict >)."""
        cfg = _default_cfg(max_displacement_strength=2.0)
        sm = StateMachine(cfg)
        state = self._make_state_with_displacement(wick_size=0.004, atr=0.002)  # ratio=2.0

        retest_candle = _make_candle("2024-01-01T09:00:00", 1.091, 1.092, 1.090, 1.0905)
        result = sm.try_expansion_to_retest(state, retest_candle, atr=0.002, ev_logger=None)

        assert result is True, "Exactly at threshold (not strictly greater) should pass"

    def test_custom_threshold(self):
        """Config-driven threshold: max=1.0 blocks ratio=1.5."""
        cfg = _default_cfg(max_displacement_strength=1.0)
        sm = StateMachine(cfg)
        state = self._make_state_with_displacement(wick_size=0.003, atr=0.002)  # ratio=1.5

        retest_candle = _make_candle("2024-01-01T09:00:00", 1.091, 1.092, 1.090, 1.0905)
        result = sm.try_expansion_to_retest(state, retest_candle, atr=0.002, ev_logger=None)

        assert result is False


# ── CRTConfig field tests ─────────────────────────────────────────────────────

class TestCRTConfigDispStrengthField:
    def test_default_value(self):
        """CRTConfig.max_displacement_strength defaults to 2.0."""
        cfg = CRTConfig()
        assert cfg.max_displacement_strength == 2.0

    def test_override_via_replace(self):
        """Field is overridable via dataclasses.replace."""
        cfg = replace(CRTConfig(), max_displacement_strength=1.5)
        assert cfg.max_displacement_strength == 1.5

    def test_prod_config_loads_field(self):
        """Production config JSON populates max_displacement_strength."""
        try:
            from config_layer.production_config import get_prod_config
            cfg = get_prod_config("EURUSD")
            assert cfg.max_displacement_strength == 2.0
        except RuntimeError:
            pytest.skip("Production registry not available in test env")
