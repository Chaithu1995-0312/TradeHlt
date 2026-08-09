"""liquidity_reversal — resting liquidity swept, price reverses & reclaims (CRT golden path).

`liq_sweep_reversal_long` is the PARITY ANCHOR: its event geometry reproduces the single existing
synthetic pack (data/synthetic/erp_4h_m15/) so the library is proven consistent with the original.
"""
from __future__ import annotations

from research.synthetic.story_spec import EntryContract, EntrySignal, PhaseBar, StorySpec

_GOLDEN_CRT = ("RANGE", "SWEEP", "DISPLACEMENT", "EXPANSION", "RETEST", "EXECUTION", "RESOLUTION")

# ── Anchor: reproduces scripts/research/erp_synth_4h_trace.py event geometry ─────────────────────
_ANCHOR_PHASES = (
    PhaseBar("range", "range hold pre-sweep", 99.95, 100.35, 99.70, 100.10, 1100),
    PhaseBar("range", "range hold", 100.10, 100.40, 99.75, 100.05, 1050),
    PhaseBar("range", "range hold", 100.05, 100.30, 99.80, 100.00, 1000),
    PhaseBar("sweep", "liquidity sweep below range, close reclaimed", 100.00, 100.20, 98.50, 99.90, 5000),
    PhaseBar("displacement", "impulsive bullish displacement 1", 99.90, 102.60, 99.85, 102.40, 4500),
    PhaseBar("displacement", "impulsive bullish displacement 2", 102.40, 103.50, 102.20, 103.20, 4200),
    PhaseBar("expansion", "expansion toward design TP zone", 103.20, 104.20, 103.00, 103.80, 3000),
    PhaseBar("expansion", "hold near highs", 103.80, 104.10, 103.40, 103.70, 2800),
    PhaseBar("retest", "retest pullback above design SL=101", 103.70, 103.75, 101.40, 101.80, 3500),
    PhaseBar("execution", "reclaim / designed LONG entry bar", 101.80, 102.40, 101.70, 102.15, 3200),
    PhaseBar("execution", "adverse excursion short of SL", 102.15, 102.30, 101.20, 101.90, 2500),
    PhaseBar("execution", "recovery", 101.90, 102.80, 101.85, 102.60, 2200),
    PhaseBar("execution", "grind higher", 102.60, 103.40, 102.50, 103.20, 2100),
    PhaseBar("resolution", "designed TP touch high>=104", 103.20, 104.25, 103.10, 104.05, 4000),
    PhaseBar("resolution", "post-outcome residual", 104.05, 104.40, 103.80, 104.10, 1800),
    PhaseBar("resolution", "post-outcome residual", 104.10, 104.30, 103.90, 104.00, 1700),
)

_anchor = StorySpec(
    id="liq_sweep_reversal_long",
    family="liquidity_reversal",
    instrument="SYNTHUSDT",
    story="range -> sweep low 98.50 -> displacement up -> expansion 104 -> retest 101.40 -> long 102 -> TP>=104 (R=2)",
    phases=_ANCHOR_PHASES,
    signal=EntrySignal(direction="long", entry_rel_index=9, entry_price=102.00,
                       atr=1.0, sl_atr_mult=1.0, tp_atr_mult=2.0),
    contract=EntryContract(
        disp_strength=4.7, atr=1.0, retest_depth=0.5, candles_since_retest=1,
        sweep_detected=True, double_sweep=False, ema_fast=102.5, ema_slow=100.5,
        momentum_score=0.8, zone_distance=0.10, zone_freshness=0.90, zone_strength=0.80),
    expected_market_states=(
        "range", "sweep", "displacement", "expansion", "retest", "execution", "resolution",
        "uptrend", "sweep_low", "momentum_increasing", "session_london", "target_hit"),
    expected_crt_states=_GOLDEN_CRT,
    expected_feature_signature=(
        "liquidity_sweep", "sweep_detected", "disp_strength", "retest_depth", "body_ratio",
        "atr", "momentum_score"),
    expected_engine_signature={"crt": "high", "gaussian": "high", "zone": "high", "rr": "moderate"},
    expected_outcome="TP_HIT",
    expected_rr_min=2.0,
)

# ── Buy-side sweep -> reversal SHORT (mirror of the anchor) ───────────────────────────────────────
_buyside_short = StorySpec(
    id="buyside_sweep_reversal_short",
    family="liquidity_reversal",
    instrument="SYNTHUSDT",
    story="range -> sweep high 101.50 -> displacement down -> expansion 95.8 -> retest 98.60 -> short 98 -> TP<=96 (R=2)",
    phases=(
        PhaseBar("range", "range hold pre-sweep", 100.05, 100.30, 99.75, 100.00, 1000),
        PhaseBar("range", "range hold", 100.00, 100.25, 99.80, 100.10, 1000),
        PhaseBar("sweep", "liquidity sweep above range, close rejected", 100.10, 101.50, 100.05, 100.20, 5000),
        PhaseBar("displacement", "impulsive bearish displacement 1", 100.20, 100.30, 97.80, 97.90, 4500),
        PhaseBar("displacement", "impulsive bearish displacement 2", 97.90, 98.10, 96.70, 96.80, 4200),
        PhaseBar("expansion", "expansion toward design TP zone", 96.80, 97.00, 95.80, 96.20, 3000),
        PhaseBar("expansion", "hold near lows", 96.20, 96.60, 95.90, 96.10, 2800),
        PhaseBar("retest", "retest pullback below design SL=99", 96.10, 98.60, 96.05, 98.20, 3500),
        PhaseBar("execution", "rejection / designed SHORT entry bar", 98.20, 98.30, 97.60, 97.85, 3200),
        PhaseBar("execution", "adverse excursion short of SL", 97.85, 98.80, 97.70, 97.90, 2500),
        PhaseBar("execution", "roll over", 97.90, 97.95, 96.90, 97.00, 2200),
        PhaseBar("execution", "grind lower", 97.00, 97.10, 96.30, 96.50, 2100),
        PhaseBar("resolution", "designed TP touch low<=96", 96.50, 96.60, 95.90, 96.05, 4000),
        PhaseBar("resolution", "post-outcome residual", 96.05, 96.40, 95.80, 96.00, 1800),
        PhaseBar("resolution", "post-outcome residual", 96.00, 96.30, 95.70, 95.90, 1700),
    ),
    signal=EntrySignal(direction="short", entry_rel_index=8, entry_price=98.00,
                       atr=1.0, sl_atr_mult=1.0, tp_atr_mult=2.0),
    contract=EntryContract(
        disp_strength=4.7, atr=1.0, retest_depth=0.5, candles_since_retest=1,
        sweep_detected=True, double_sweep=False, ema_fast=97.5, ema_slow=99.5,
        momentum_score=-0.8, zone_distance=0.10, zone_freshness=0.90, zone_strength=0.80),
    expected_market_states=(
        "range", "sweep", "displacement", "expansion", "retest", "execution", "resolution",
        "downtrend", "sweep_high", "momentum_decreasing", "session_newyork", "target_hit"),
    expected_crt_states=_GOLDEN_CRT,
    expected_feature_signature=(
        "liquidity_sweep", "sweep_detected", "disp_strength", "retest_depth", "body_ratio",
        "atr", "momentum_score"),
    expected_engine_signature={"crt": "high", "gaussian": "high", "zone": "high", "rr": "moderate"},
    expected_outcome="TP_HIT",
    expected_rr_min=2.0,
)

# ── Stop-hunt both sides -> reversal LONG (double sweep) ──────────────────────────────────────────
_stop_hunt_long = StorySpec(
    id="stop_hunt_both_sides_long",
    family="liquidity_reversal",
    instrument="SYNTHUSDT",
    story="range -> sweep low 98.50 then sweep high 100.90 (both stops) -> displacement up -> retest -> long 102 -> TP (R=2)",
    phases=(
        PhaseBar("range", "range hold", 100.00, 100.30, 99.75, 100.05, 1000),
        PhaseBar("range", "range hold", 100.05, 100.30, 99.80, 100.00, 1000),
        PhaseBar("sweep", "sweep sell-side liquidity (low 98.50)", 100.00, 100.20, 98.50, 99.90, 5200),
        PhaseBar("sweep", "sweep buy-side liquidity (high 100.90)", 99.90, 100.90, 99.85, 100.20, 5000),
        PhaseBar("displacement", "impulsive bullish displacement 1", 100.20, 102.60, 100.10, 102.40, 4500),
        PhaseBar("displacement", "impulsive bullish displacement 2", 102.40, 103.30, 102.20, 103.10, 4200),
        PhaseBar("expansion", "expansion toward TP zone", 103.10, 104.20, 102.90, 103.80, 3000),
        PhaseBar("retest", "retest pullback above design SL=101", 103.80, 103.85, 101.40, 101.85, 3500),
        PhaseBar("execution", "reclaim / designed LONG entry bar", 101.85, 102.45, 101.70, 102.20, 3200),
        PhaseBar("execution", "adverse excursion short of SL", 102.20, 102.35, 101.20, 101.95, 2500),
        PhaseBar("execution", "recovery", 101.95, 102.90, 101.90, 102.70, 2200),
        PhaseBar("execution", "grind higher", 102.70, 103.50, 102.60, 103.30, 2100),
        PhaseBar("resolution", "designed TP touch high>=104", 103.30, 104.30, 103.20, 104.10, 4000),
        PhaseBar("resolution", "post-outcome residual", 104.10, 104.40, 103.90, 104.05, 1800),
    ),
    signal=EntrySignal(direction="long", entry_rel_index=8, entry_price=102.00,
                       atr=1.0, sl_atr_mult=1.0, tp_atr_mult=2.0),
    contract=EntryContract(
        disp_strength=4.6, atr=1.0, retest_depth=0.5, candles_since_retest=1,
        sweep_detected=True, double_sweep=True, ema_fast=102.5, ema_slow=100.5,
        momentum_score=0.8, zone_distance=0.10, zone_freshness=0.90, zone_strength=0.80),
    expected_market_states=(
        "range", "sweep", "displacement", "expansion", "retest", "execution", "resolution",
        "double_sweep", "stop_hunt", "uptrend", "momentum_increasing", "target_hit"),
    expected_crt_states=_GOLDEN_CRT,
    expected_feature_signature=(
        "double_sweep", "liquidity_sweep", "sweep_detected", "disp_strength", "retest_depth",
        "body_ratio", "atr"),
    expected_engine_signature={"crt": "high", "gaussian": "high", "zone": "high", "rr": "moderate"},
    expected_outcome="TP_HIT",
    expected_rr_min=2.0,
)

LIQUIDITY_REVERSAL = [_anchor, _buyside_short, _stop_hunt_long]
