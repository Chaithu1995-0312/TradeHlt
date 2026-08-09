"""trend_continuation — an established trend pulls back to a retest, then continues.

Modeled on the CRT golden skeleton (the trend leg = displacement, the pullback = retest); the
semantic bundle (uptrend/downtrend + flag/pullback + momentum) is what distinguishes it.
"""
from __future__ import annotations

from research.synthetic.story_spec import EntryContract, EntrySignal, PhaseBar, StorySpec

_GOLDEN_CRT = ("RANGE", "SWEEP", "DISPLACEMENT", "EXPANSION", "RETEST", "EXECUTION", "RESOLUTION")

_bull_flag = StorySpec(
    id="bull_flag_continuation_long",
    family="trend_continuation",
    instrument="SYNTHUSDT",
    story="uptrend -> flagpole up -> bull-flag pullback (retest) -> long 101.80 -> continuation TP>=103.80 (R=2)",
    phases=(
        PhaseBar("range", "prior balance", 100.00, 100.30, 99.75, 100.05, 1000),
        PhaseBar("range", "prior balance", 100.05, 100.30, 99.80, 100.00, 1000),
        PhaseBar("sweep", "minor sweep of session low", 100.00, 100.20, 99.20, 99.90, 4800),
        PhaseBar("displacement", "flagpole impulse up", 99.90, 102.30, 99.85, 102.20, 4500),
        PhaseBar("displacement", "flagpole extension", 102.20, 102.60, 101.90, 102.30, 3600),
        PhaseBar("expansion", "expansion hold", 102.30, 102.80, 102.00, 102.50, 3000),
        PhaseBar("retest", "bull-flag pullback", 102.50, 102.55, 101.30, 101.60, 3200),
        PhaseBar("execution", "continuation LONG entry bar", 101.60, 102.20, 101.50, 101.95, 3100),
        PhaseBar("execution", "adverse dip short of SL", 101.95, 102.10, 101.00, 101.70, 2500),
        PhaseBar("execution", "resume up", 101.70, 102.60, 101.60, 102.40, 2300),
        PhaseBar("execution", "grind higher", 102.40, 103.20, 102.30, 103.00, 2100),
        PhaseBar("resolution", "designed TP touch high>=103.80", 103.00, 103.90, 102.90, 103.70, 3800),
        PhaseBar("resolution", "post-outcome residual", 103.70, 104.00, 103.50, 103.80, 1700),
    ),
    signal=EntrySignal(direction="long", entry_rel_index=7, entry_price=101.80,
                       atr=1.0, sl_atr_mult=1.0, tp_atr_mult=2.0),
    contract=EntryContract(
        disp_strength=3.1, atr=1.0, retest_depth=0.5, candles_since_retest=1,
        sweep_detected=True, double_sweep=False, ema_fast=102.2, ema_slow=101.0,
        momentum_score=0.7, zone_distance=0.10, zone_freshness=0.90, zone_strength=0.80),
    expected_market_states=(
        "range", "sweep", "displacement", "expansion", "retest", "execution", "resolution",
        "uptrend", "bull_flag", "trend_pullback", "momentum_increasing", "target_hit"),
    expected_crt_states=_GOLDEN_CRT,
    expected_feature_signature=(
        "ema_fast", "ema_slow", "disp_strength", "retest_depth", "body_ratio", "trend_strength",
        "momentum_score"),
    expected_engine_signature={"crt": "high", "gaussian": "high", "zone": "high", "rr": "moderate"},
    expected_outcome="TP_HIT",
    expected_rr_min=2.0,
)

_bear_flag = StorySpec(
    id="bear_flag_continuation_short",
    family="trend_continuation",
    instrument="SYNTHUSDT",
    story="downtrend -> flagpole down -> bear-flag pullback (retest) -> short 98.20 -> continuation TP<=96.20 (R=2)",
    phases=(
        PhaseBar("range", "prior balance", 100.00, 100.25, 99.75, 100.00, 1000),
        PhaseBar("range", "prior balance", 100.00, 100.20, 99.80, 100.05, 1000),
        PhaseBar("sweep", "minor sweep of session high", 100.05, 100.80, 99.95, 100.10, 4800),
        PhaseBar("displacement", "flagpole impulse down", 100.10, 100.20, 97.70, 97.80, 4500),
        PhaseBar("displacement", "flagpole extension", 97.80, 98.10, 97.40, 97.80, 3600),
        PhaseBar("expansion", "expansion hold", 97.80, 98.00, 97.20, 97.50, 3000),
        PhaseBar("retest", "bear-flag pullback", 97.50, 98.70, 97.45, 98.40, 3200),
        PhaseBar("execution", "continuation SHORT entry bar", 98.40, 98.50, 97.90, 98.10, 3100),
        PhaseBar("execution", "adverse pop short of SL", 98.10, 99.00, 98.00, 98.30, 2500),
        PhaseBar("execution", "resume down", 98.30, 98.40, 97.40, 97.60, 2300),
        PhaseBar("execution", "grind lower", 97.60, 97.70, 96.80, 97.00, 2100),
        PhaseBar("resolution", "designed TP touch low<=96.20", 97.00, 97.10, 96.10, 96.20, 3800),
        PhaseBar("resolution", "post-outcome residual", 96.20, 96.50, 96.00, 96.30, 1700),
    ),
    signal=EntrySignal(direction="short", entry_rel_index=7, entry_price=98.20,
                       atr=1.0, sl_atr_mult=1.0, tp_atr_mult=2.0),
    contract=EntryContract(
        disp_strength=3.3, atr=1.0, retest_depth=0.5, candles_since_retest=1,
        sweep_detected=True, double_sweep=False, ema_fast=97.8, ema_slow=99.0,
        momentum_score=-0.7, zone_distance=0.10, zone_freshness=0.90, zone_strength=0.80),
    expected_market_states=(
        "range", "sweep", "displacement", "expansion", "retest", "execution", "resolution",
        "downtrend", "bear_flag", "trend_pullback", "momentum_decreasing", "target_hit"),
    expected_crt_states=_GOLDEN_CRT,
    expected_feature_signature=(
        "ema_fast", "ema_slow", "disp_strength", "retest_depth", "body_ratio", "trend_strength",
        "momentum_score"),
    expected_engine_signature={"crt": "high", "gaussian": "high", "zone": "high", "rr": "moderate"},
    expected_outcome="TP_HIT",
    expected_rr_min=2.0,
)

_ema_pullback = StorySpec(
    id="ema_pullback_continuation_long",
    family="trend_continuation",
    instrument="SYNTHUSDT",
    story="uptrend -> impulse -> pullback to fast EMA (retest) -> long 101.60 -> continuation TP>=103.60 (R=2)",
    phases=(
        PhaseBar("range", "prior balance", 100.00, 100.30, 99.75, 100.05, 1000),
        PhaseBar("range", "prior balance", 100.05, 100.30, 99.80, 100.00, 1000),
        PhaseBar("sweep", "minor sweep of session low", 100.00, 100.15, 99.40, 100.00, 4600),
        PhaseBar("displacement", "impulse up 1", 100.00, 101.90, 99.95, 101.80, 4400),
        PhaseBar("displacement", "impulse up 2", 101.80, 102.10, 101.50, 101.95, 3600),
        PhaseBar("expansion", "expansion hold", 101.95, 102.50, 101.80, 102.30, 3000),
        PhaseBar("retest", "pullback to fast EMA", 102.30, 102.35, 101.10, 101.40, 3200),
        PhaseBar("execution", "continuation LONG entry bar", 101.40, 102.00, 101.30, 101.75, 3100),
        PhaseBar("execution", "adverse dip short of SL", 101.75, 101.90, 100.80, 101.50, 2500),
        PhaseBar("execution", "resume up", 101.50, 102.40, 101.40, 102.20, 2300),
        PhaseBar("execution", "grind higher", 102.20, 103.00, 102.10, 102.80, 2100),
        PhaseBar("resolution", "designed TP touch high>=103.60", 102.80, 103.70, 102.70, 103.60, 3800),
        PhaseBar("resolution", "post-outcome residual", 103.60, 103.90, 103.40, 103.70, 1700),
    ),
    signal=EntrySignal(direction="long", entry_rel_index=7, entry_price=101.60,
                       atr=1.0, sl_atr_mult=1.0, tp_atr_mult=2.0),
    contract=EntryContract(
        disp_strength=2.55, atr=1.0, retest_depth=0.5, candles_since_retest=1,
        sweep_detected=True, double_sweep=False, ema_fast=101.8, ema_slow=101.0,
        momentum_score=0.6, zone_distance=0.10, zone_freshness=0.90, zone_strength=0.80),
    expected_market_states=(
        "range", "sweep", "displacement", "expansion", "retest", "execution", "resolution",
        "uptrend", "trend_pullback", "momentum_increasing", "target_hit"),
    expected_crt_states=_GOLDEN_CRT,
    expected_feature_signature=(
        "ema_fast", "ema_slow", "disp_strength", "retest_depth", "body_ratio", "momentum_score"),
    expected_engine_signature={"crt": "high", "gaussian": "high", "zone": "high", "rr": "moderate"},
    expected_outcome="TP_HIT",
    expected_rr_min=2.0,
)

TREND_CONTINUATION = [_bull_flag, _bear_flag, _ema_pullback]
