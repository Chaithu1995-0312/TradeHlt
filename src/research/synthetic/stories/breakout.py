"""breakout — compression resolves; a range boundary breaks, expands, retests, then continues.

CRT skeleton uses the SWEEP->EXPANSION edge (the break IS a sweep of the boundary). One story is a
designed TIMEOUT (pullback that neither hits TP nor SL within the horizon) for outcome coverage.
"""
from __future__ import annotations

from research.synthetic.story_spec import EntryContract, EntrySignal, PhaseBar, StorySpec

_BREAK_CRT = ("RANGE", "SWEEP", "EXPANSION", "RETEST", "EXECUTION", "RESOLUTION")

_breakout_long = StorySpec(
    id="breakout_continuation_long",
    family="breakout",
    instrument="SYNTHUSDT",
    story="range -> break of high (sweep) -> expansion -> retest -> long 101.30 -> continuation TP>=103.30 (R=2)",
    phases=(
        PhaseBar("range", "range hold", 100.00, 100.30, 99.75, 100.10, 1000),
        PhaseBar("range", "range hold", 100.10, 100.35, 99.80, 100.05, 1000),
        PhaseBar("sweep", "break of range high", 100.05, 100.95, 100.00, 100.85, 4200),
        PhaseBar("expansion", "expansion up 1", 100.85, 101.80, 100.80, 101.60, 3800),
        PhaseBar("expansion", "expansion hold", 101.60, 101.90, 101.30, 101.70, 3000),
        PhaseBar("retest", "retest of breakout level", 101.70, 101.75, 100.90, 101.10, 3200),
        PhaseBar("execution", "continuation LONG entry bar", 101.10, 101.60, 101.05, 101.45, 3100),
        PhaseBar("execution", "adverse dip short of SL", 101.45, 101.60, 100.50, 101.20, 2500),
        PhaseBar("execution", "resume up", 101.20, 102.20, 101.10, 102.00, 2300),
        PhaseBar("execution", "grind higher", 102.00, 102.90, 101.90, 102.70, 2100),
        PhaseBar("resolution", "designed TP touch high>=103.30", 102.70, 103.40, 102.60, 103.30, 3800),
        PhaseBar("resolution", "post-outcome residual", 103.30, 103.60, 103.10, 103.40, 1700),
    ),
    signal=EntrySignal(direction="long", entry_rel_index=6, entry_price=101.30,
                       atr=1.0, sl_atr_mult=1.0, tp_atr_mult=2.0),
    contract=EntryContract(
        disp_strength=2.50, atr=1.0, retest_depth=0.5, candles_since_retest=1,
        sweep_detected=True, double_sweep=False, ema_fast=101.5, ema_slow=100.5,
        momentum_score=0.7, zone_distance=0.10, zone_freshness=0.90, zone_strength=0.80),
    expected_market_states=(
        "range", "sweep", "expansion", "retest", "execution", "resolution",
        "break_of_structure", "volatility_spike", "uptrend", "target_hit"),
    expected_crt_states=_BREAK_CRT,
    expected_feature_signature=(
        "break_of_structure", "disp_strength", "body_ratio", "atr", "volume_spike"),
    expected_engine_signature={"crt": "high", "gaussian": "high", "zone": "high", "rr": "strong"},
    expected_outcome="TP_HIT",
    expected_rr_min=2.0,
)

_ascending_triangle = StorySpec(
    id="ascending_triangle_breakout_long",
    family="breakout",
    instrument="SYNTHUSDT",
    story="ascending triangle (higher lows into resistance) -> break (sweep) -> retest -> long 101.20 -> TP>=103.20 (R=2)",
    phases=(
        PhaseBar("range", "higher-low base", 100.00, 100.20, 99.80, 100.05, 1000),
        PhaseBar("range", "higher-low base", 100.05, 100.25, 99.85, 100.10, 1000),
        PhaseBar("sweep", "break of triangle resistance", 100.10, 100.85, 100.05, 100.75, 4200),
        PhaseBar("expansion", "expansion up", 100.75, 101.60, 100.70, 101.45, 3600),
        PhaseBar("retest", "retest of broken resistance", 101.45, 101.50, 100.85, 101.05, 3200),
        PhaseBar("execution", "continuation LONG entry bar", 101.05, 101.55, 101.00, 101.40, 3100),
        PhaseBar("execution", "adverse dip short of SL", 101.40, 101.55, 100.40, 101.10, 2500),
        PhaseBar("execution", "resume up", 101.10, 102.10, 101.00, 101.90, 2300),
        PhaseBar("execution", "grind higher", 101.90, 102.80, 101.80, 102.60, 2100),
        PhaseBar("resolution", "designed TP touch high>=103.20", 102.60, 103.30, 102.50, 103.20, 3800),
        PhaseBar("resolution", "post-outcome residual", 103.20, 103.50, 103.00, 103.30, 1700),
    ),
    signal=EntrySignal(direction="long", entry_rel_index=5, entry_price=101.20,
                       atr=1.0, sl_atr_mult=1.0, tp_atr_mult=2.0),
    contract=EntryContract(
        disp_strength=2.30, atr=1.0, retest_depth=0.5, candles_since_retest=1,
        sweep_detected=True, double_sweep=False, ema_fast=101.4, ema_slow=100.5,
        momentum_score=0.65, zone_distance=0.10, zone_freshness=0.90, zone_strength=0.80),
    expected_market_states=(
        "range", "sweep", "expansion", "retest", "execution", "resolution",
        "ascending_triangle", "break_of_structure", "uptrend", "target_hit"),
    expected_crt_states=_BREAK_CRT,
    expected_feature_signature=(
        "swing_high", "higher_high", "break_of_structure", "atr", "body_ratio"),
    expected_engine_signature={"crt": "high", "gaussian": "high", "zone": "high", "rr": "strong"},
    expected_outcome="TP_HIT",
    expected_rr_min=2.0,
)

_breakout_timeout = StorySpec(
    id="breakout_pullback_timeout_long",
    family="breakout",
    instrument="SYNTHUSDT",
    story="range -> break (sweep) -> expansion -> retest -> long 101.20 -> stalls, neither TP nor SL -> TIMEOUT",
    phases=(
        PhaseBar("range", "range hold", 100.00, 100.30, 99.75, 100.10, 1000),
        PhaseBar("range", "range hold", 100.10, 100.35, 99.80, 100.05, 1000),
        PhaseBar("sweep", "break of range high", 100.05, 100.90, 100.00, 100.80, 4000),
        PhaseBar("expansion", "expansion up", 100.80, 101.50, 100.75, 101.30, 3400),
        PhaseBar("retest", "retest of breakout level", 101.30, 101.35, 100.85, 101.05, 3000),
        PhaseBar("execution", "continuation LONG entry bar", 101.05, 101.40, 101.00, 101.25, 3000),
        PhaseBar("execution", "stall drift", 101.25, 101.60, 100.90, 101.30, 2200),
        PhaseBar("execution", "stall drift", 101.30, 101.70, 101.00, 101.40, 2100),
        PhaseBar("execution", "stall drift", 101.40, 101.75, 101.10, 101.35, 2000),
        PhaseBar("execution", "stall drift", 101.35, 101.80, 101.05, 101.50, 1900),
        PhaseBar("execution", "stall drift", 101.50, 101.85, 101.20, 101.60, 1800),
    ),
    signal=EntrySignal(direction="long", entry_rel_index=5, entry_price=101.20,
                       atr=1.0, sl_atr_mult=1.0, tp_atr_mult=2.0),
    contract=EntryContract(
        disp_strength=1.50, atr=1.0, retest_depth=0.5, candles_since_retest=1,
        sweep_detected=True, double_sweep=False, ema_fast=101.3, ema_slow=100.6,
        momentum_score=0.5, zone_distance=0.10, zone_freshness=0.90, zone_strength=0.80),
    expected_market_states=(
        "range", "sweep", "expansion", "retest", "execution",
        "uptrend", "compression", "volatility_spike", "timeout_exit"),
    expected_crt_states=("RANGE", "SWEEP", "EXPANSION", "RETEST", "EXECUTION"),
    expected_feature_signature=("disp_strength", "body_ratio", "atr", "volatility_ratio"),
    expected_engine_signature={"crt": "high", "gaussian": "high", "zone": "high", "rr": "moderate"},
    expected_outcome="TIMEOUT",
)

BREAKOUT = [_breakout_long, _ascending_triangle, _breakout_timeout]
