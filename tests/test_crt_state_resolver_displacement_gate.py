"""Regression floor for the shadow resolver's SWEEP→DISPLACEMENT gate 4 (candle_range vs ATR).

Guards the D1 defect: schema v4.0 renamed the canonical column `wick_size` → `candle_range`
(features/feature_schema.py:89), but crt_state_resolver._displacement_entry_allowed read the dead
`raw.get("wick_size")` key, so gate 4 silently no-op'd on every real (v4.0) feature vector — the
shadow DISPLACEMENT was looser than the authoritative engine, which DOES enforce it
(crt_engine_v2.py:1198: candle.wick_size ≡ FM-002 candle_range < atr_multiplier_min * atr_abs).

These tests pin the engine-parity behaviour: with a fresh SWEEP in memory and gates 1-3 passing,
gate 4 must reject a small candle_range and admit a large one, honour the pre-v4 `wick_size`
fallback, and skip (fail-open) only when the value is genuinely absent.

Unit contract (verified against feature_pipeline.py):
    atr in the vector is RELATIVE (atr_14_raw/close) → _atr_abs multiplies by close.
    candle_range is ABSOLUTE (high-low, un-normalised) → same units as atr_abs → direct compare.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from features.crt_state_resolver import CRTStateResolver  # noqa: E402


def _sweep_resolver() -> CRTStateResolver:
    """Resolver with memory forced into a fresh (non-stale) SWEEP so the funnel is open."""
    r = CRTStateResolver()
    r._memory.current_state = "SWEEP"
    r._memory.candle_index = 10
    r._memory.sweep_candle_index = 10  # age 0 ≤ max_sweep_age_candles → not stale
    r._memory.displacement_direction = 1  # LONG — matches bullish _raw fixture
    return r


def _raw(candle_range: float, *, close: float = 2000.0, atr_rel: float = 0.001,
         body_ratio: float = 0.8, move: float = 2.5) -> dict:
    # atr_abs = atr_rel*close = 2.0
    # Active market_crt_states (B1c, prod-aligned): atr_multiplier_min=1.0 → gate4 thr=2.0
    # move_min = 1.2*2.0 = 2.4 ; body_ratio_min = 0.65
    # move=2.5 and body_ratio=0.8 clear gates 1-3, so gate 4 is decisive.
    return {
        "open": close - move,
        "close": close,
        "atr": atr_rel,
        "body_ratio": body_ratio,
        "candle_range": candle_range,
    }


def test_displacement_gate_rejects_small_candle_range_like_engine():
    # candle_range 1.9 < threshold 2.0 → reject. The pre-v4 bug let small ranges through
    # because `wick_size` was absent from the v4.0 vector.
    assert _sweep_resolver()._displacement_entry_allowed(_raw(1.9)) is False


def test_displacement_gate_admits_large_candle_range():
    # candle_range 2.5 ≥ threshold 2.0 → gate 4 passes.
    assert _sweep_resolver()._displacement_entry_allowed(_raw(2.5)) is True


def test_displacement_gate_honours_pre_v4_wick_size_fallback():
    raw = _raw(1.9)
    raw["wick_size"] = raw.pop("candle_range")  # historical / synthetic pre-v4 dict
    assert _sweep_resolver()._displacement_entry_allowed(raw) is False


def test_displacement_gate_skips_only_when_range_genuinely_absent():
    raw = _raw(1.9)
    del raw["candle_range"]  # partial synthetic vector: no range at all → fail-open skip
    assert _sweep_resolver()._displacement_entry_allowed(raw) is True
