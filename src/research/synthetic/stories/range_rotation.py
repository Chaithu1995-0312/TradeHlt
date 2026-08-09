"""range_rotation — balanced range; edges fade to the mean (CRT-quiescent), plus a failed break.

These stories demonstrate a family the 9-state CRT skeleton does NOT deeply model: the pure fades
carry expected_crt_states=['RANGE'] (no execution phase), and the failed break walks RANGE->SWEEP->RANGE.
"""
from __future__ import annotations

from research.synthetic.story_spec import EntryContract, EntrySignal, PhaseBar, StorySpec

_fade_short = StorySpec(
    id="range_fade_short",
    family="range_rotation",
    instrument="SYNTHUSDT",
    story="balanced range -> tag upper edge -> short 100.30 -> fade to mid TP<=99.90",
    phases=(
        PhaseBar("range", "range hold", 100.00, 100.30, 99.75, 100.10, 1000),
        PhaseBar("range", "range hold", 100.10, 100.35, 99.80, 100.05, 1000),
        PhaseBar("range", "push to upper edge", 100.05, 100.40, 99.85, 100.30, 1100),
        PhaseBar("range", "upper-edge fade SHORT entry bar", 100.30, 100.45, 100.10, 100.25, 1050),
        PhaseBar("range", "drift toward mid", 100.25, 100.35, 99.95, 100.05, 1000),
        PhaseBar("range", "designed TP touch low<=99.90", 100.05, 100.15, 99.80, 99.85, 1000),
        PhaseBar("range", "mid-range residual", 99.85, 100.05, 99.70, 99.95, 1000),
        PhaseBar("range", "mid-range residual", 99.95, 100.10, 99.75, 100.00, 1000),
    ),
    signal=EntrySignal(direction="short", entry_rel_index=3, entry_price=100.30,
                       atr=0.20, sl_atr_mult=1.5, tp_atr_mult=2.0),
    contract=EntryContract(
        disp_strength=0.10, atr=0.20, retest_depth=0.0, candles_since_retest=5,
        sweep_detected=False, double_sweep=False, ema_fast=100.02, ema_slow=100.00,
        momentum_score=0.05, zone_distance=0.10, zone_freshness=0.90, zone_strength=0.80),
    expected_market_states=(
        "range", "ranging_trend", "compression", "session_asian", "target_hit"),
    expected_crt_states=("RANGE",),
    expected_feature_signature=("swing_high", "swing_low", "atr", "volatility_regime"),
    expected_engine_signature={"crt": "low", "gaussian": "high", "zone": "high", "rr": "moderate"},
    expected_outcome="TP_HIT",
    expected_rr_min=1.3,  # realized R = tp_mult/sl_mult = 2.0/1.5 (wider stop on a mean-revert fade)
)

_fade_long = StorySpec(
    id="range_fade_long",
    family="range_rotation",
    instrument="SYNTHUSDT",
    story="balanced range -> tag lower edge -> long 99.70 -> fade to mid TP>=100.10",
    phases=(
        PhaseBar("range", "range hold", 100.00, 100.25, 99.70, 99.90, 1000),
        PhaseBar("range", "range hold", 99.90, 100.20, 99.65, 99.95, 1000),
        PhaseBar("range", "push to lower edge", 99.95, 100.10, 99.60, 99.70, 1100),
        PhaseBar("range", "lower-edge fade LONG entry bar", 99.70, 99.90, 99.55, 99.75, 1050),
        PhaseBar("range", "drift toward mid", 99.75, 100.05, 99.65, 99.95, 1000),
        PhaseBar("range", "designed TP touch high>=100.10", 99.95, 100.20, 99.90, 100.15, 1000),
        PhaseBar("range", "mid-range residual", 100.15, 100.30, 99.95, 100.05, 1000),
        PhaseBar("range", "mid-range residual", 100.05, 100.25, 99.90, 100.00, 1000),
    ),
    signal=EntrySignal(direction="long", entry_rel_index=3, entry_price=99.70,
                       atr=0.20, sl_atr_mult=1.5, tp_atr_mult=2.0),
    contract=EntryContract(
        disp_strength=0.10, atr=0.20, retest_depth=0.0, candles_since_retest=5,
        sweep_detected=False, double_sweep=False, ema_fast=99.98, ema_slow=100.00,
        momentum_score=-0.05, zone_distance=0.10, zone_freshness=0.90, zone_strength=0.80),
    expected_market_states=(
        "range", "ranging_trend", "compression", "session_asian", "target_hit"),
    expected_crt_states=("RANGE",),
    expected_feature_signature=("swing_high", "swing_low", "atr", "volatility_regime"),
    expected_engine_signature={"crt": "low", "gaussian": "high", "zone": "high", "rr": "moderate"},
    expected_outcome="TP_HIT",
    expected_rr_min=1.3,  # realized R = tp_mult/sl_mult = 2.0/1.5 (wider stop on a mean-revert fade)
)

_failed_break = StorySpec(
    id="failed_breakout_return_to_range",
    family="range_rotation",
    instrument="SYNTHUSDT",
    story="range -> break above high (sweep) -> long 100.70 -> break fails, returns to range -> SL_HIT",
    phases=(
        PhaseBar("range", "range hold", 100.00, 100.30, 99.75, 100.10, 1000),
        PhaseBar("range", "range hold", 100.10, 100.35, 99.80, 100.05, 1000),
        PhaseBar("sweep", "break above range high (sweep of highs)", 100.05, 100.90, 100.00, 100.75, 3500),
        PhaseBar("sweep", "breakout continuation LONG entry bar", 100.75, 101.00, 100.55, 100.85, 3200),
        PhaseBar("range", "break stalls", 100.85, 100.95, 100.40, 100.55, 1500),
        PhaseBar("range", "return into range -> SL", 100.55, 100.60, 100.10, 100.20, 1400),
        PhaseBar("range", "range residual", 100.20, 100.45, 100.05, 100.30, 1000),
        PhaseBar("range", "range residual", 100.30, 100.50, 100.15, 100.35, 1000),
    ),
    signal=EntrySignal(direction="long", entry_rel_index=3, entry_price=100.70,
                       atr=0.40, sl_atr_mult=1.0, tp_atr_mult=2.0),
    contract=EntryContract(
        disp_strength=0.90, atr=0.40, retest_depth=0.0, candles_since_retest=1,
        sweep_detected=True, double_sweep=False, ema_fast=100.40, ema_slow=100.10,
        momentum_score=0.30, zone_distance=0.10, zone_freshness=0.90, zone_strength=0.80),
    expected_market_states=(
        "range", "sweep", "failed_breakout", "ranging_trend", "session_overlap", "stop_hit"),
    expected_crt_states=("RANGE", "SWEEP", "RANGE"),
    expected_feature_signature=(
        "break_of_structure", "liquidity_sweep", "sweep_detected", "retest_depth"),
    expected_engine_signature={"crt": "neutral", "gaussian": "high", "zone": "high", "rr": "moderate"},
    expected_outcome="SL_HIT",
)

RANGE_ROTATION = [_fade_short, _fade_long, _failed_break]
