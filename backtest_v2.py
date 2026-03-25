"""
╔═══════════════════════════════════════════════════════════════════════╗
║         CRT ENGINE — BACKTESTING HARNESS v2.0                        ║
║         Candle-by-candle replay | Zero lookahead | Multi-instrument   ║
║                                                                       ║
║  v2 Patches — Jarvis Audit Gaps:                                      ║
║    [G1] Slippage model  — random(0, 0.1×ATR) on entry/exit           ║
║    [G2] Spread in PnL   — spread cost deducted from every trade      ║
║    [G3] Capital curve   — equity curve + compounded drawdown         ║
║    [G4] Session gap reset — time-gap detector force-resets engine    ║
║    [G5] Trade distribution — clustering, regime, streak analysis     ║
╚═══════════════════════════════════════════════════════════════════════╝

Usage:
    python backtest_v2.py --csv data/EURCAD_M15.csv --instrument EURCAD
    python backtest_v2.py --csv data/ --instrument ALL --output results/
    python backtest_v2.py --csv data/EURCAD_M15.csv --capital 100000 --risk-pct 0.01
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import os
import random
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional
from config_builder import ConfigBuilder
from scoring_engine import ScoringEngine
from train_pipeline import load_active_neural_fn

# ── Fusion + logging (guarded: system runs without them if files missing) ──
try:
    from fusion_engine import FusionEngine, FusionConfig, FusionResult, GaussianAdapter
    from trade_logger  import TradeLogger
    _FUSION_AVAILABLE = True
except ImportError:
    _FUSION_AVAILABLE = False

# ── Passive fusion observation (backtest replay mode) ────────────
# _fusion_engine in BacktestRunner is initialised with neural_fn=None,
# llm_fn=None, enable_llm=False so it NEVER affects execution.
# Scores are logged to TradeRecord for calibration dataset only.

sys.path.insert(0, os.path.dirname(__file__))
from crt_engine_v2 import (
    Candle, CRTConfig, CRTEngine, CRTState, Direction,
    EngineState, ExecutionEngine, Range, Trade,
)

# ─────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────

for _noisy in [
    "CRT.RangeDetector", "CRT.StateMachine", "CRT.UltronRisk",
    "CRT.Execution", "CRT.Reset", "CRT.EventLog", "CRT.Orchestrator",
]:
    logging.getLogger(_noisy).setLevel(logging.WARNING)

bt_log = logging.getLogger("CRT.Backtest")
bt_log.setLevel(logging.INFO)
if not bt_log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s [BT] %(message)s", "%H:%M:%S"))
    bt_log.addHandler(_h)

# ─────────────────────────────────────────────────────────────────
# DEBUG COUNTER — pipeline choke-point visibility
# ─────────────────────────────────────────────────────────────────

class DebugCounter:
    def __init__(self):
        self.counts = {
            "candles":                            0,
            "sweeps_detected":                    0,
            "sweep_to_displacement_attempt":      0,
            "displacement_success":               0,
            "displacement_to_expansion_attempt":  0,
            "expansion_success":                  0,
            "expansion_to_retest_attempt":        0,
            "retest_success":                     0,
            "confirmation_phase_entered":         0,
            "confirmation_passed":                0,
            "confirmation_failed_timeout":        0,
            "filter_rejected_zone":               0,
            "execution_attempt":                  0,
            "execution_success":                  0,
            "risk_rejected_low_score":            0,
            "risk_rejected_no_double_sweep":      0,
            "risk_rejected_outside_session":      0,
            "risk_rejected_news":                 0,
            "risk_rejected_spread":               0,
            "gap_resets":                         0,
            "htf_range_refreshes":                0,
            "sweep_expired":                      0,
        }

    def inc(self, key: str) -> None:
        if key in self.counts:
            self.counts[key] += 1
        # silently ignore unknown keys — no crash in hot path

    def report(self) -> None:
        total = self.counts["candles"]
        print()
        print("=" * 62)
        print("  DEBUG PIPELINE COUNTS")
        print("=" * 62)
        groups = [
            ("INTAKE",        ["candles", "gap_resets", "htf_range_refreshes"]),
            ("SWEEP",         ["sweeps_detected", "sweep_expired"]),
            ("DISPLACEMENT",  ["sweep_to_displacement_attempt", "displacement_success"]),
            ("EXPANSION",     ["displacement_to_expansion_attempt", "expansion_success"]),
            ("RETEST",        ["expansion_to_retest_attempt", "retest_success"]),
            ("CONFIRMATION",  ["confirmation_phase_entered", "confirmation_passed",
                               "confirmation_failed_timeout", "filter_rejected_zone"]),
            ("EXECUTION",     ["execution_attempt", "execution_success"]),
            ("RISK REJECTIONS", ["risk_rejected_no_double_sweep", "risk_rejected_outside_session",
                                 "risk_rejected_low_score", "risk_rejected_news",
                                 "risk_rejected_spread"]),
        ]
        for group_name, keys in groups:
            print(f"  -- {group_name} --")
            for k in keys:
                v = self.counts[k]
                pct = f"  ({v/total*100:.2f}% of candles)" if total > 0 and v > 0 else ""
                print(f"    {k:<42} {v:>8,}{pct}")
        print()
        # Funnel analysis
        s  = self.counts["sweeps_detected"]
        d  = self.counts["displacement_success"]
        e  = self.counts["expansion_success"]
        r  = self.counts["retest_success"]
        c  = self.counts["confirmation_passed"]
        ex = self.counts["execution_success"]
        print("  ── FUNNEL RATIOS ──")
        print(f"    sweep  → displacement   {d:>6} / {s:<6}  = {d/s*100:.1f}%" if s else "    sweep  → displacement   N/A")
        print(f"    disp   → expansion      {e:>6} / {d:<6}  = {e/d*100:.1f}%" if d else "    disp   → expansion      N/A")
        print(f"    exp    → retest         {r:>6} / {e:<6}  = {r/e*100:.1f}%" if e else "    exp    → retest         N/A")
        print(f"    retest → confirmation   {c:>6} / {r:<6}  = {c/r*100:.1f}%" if r else "    retest → confirmation   N/A")
        print(f"    conf   → execution      {ex:>6} / {c:<6}  = {ex/c*100:.1f}%" if c else "    conf   → execution      N/A")
        print("=" * 62)




# ─────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────

@dataclass
class BacktestConfig:
    # ── HTF ──────────────────────────────────────────────────────
    htf_candles_per_range:   int   = 4
    warmup_candles:          int   = 30

    # ── [G1] Slippage model ───────────────────────────────────────
    slippage_enabled:        bool  = True
    slippage_atr_fraction:   float = 0.10   # slip ~ uniform(0, 0.10×ATR)
    slippage_seed:           int   = 42     # reproducible (set 0 for random)

    # ── [G2] Spread ───────────────────────────────────────────────
    simulated_spread_pct:    float = 0.0002  # 0.02% = ~2 pip on EURCAD

    # ── [G3] Capital curve ────────────────────────────────────────
    initial_capital:         float = 100_000.0
    risk_pct_per_trade:      float = 0.01    # 1% of current equity per trade
    use_compounding:         bool  = True    # size off current equity, not starting

    # ── [G4] Session gap reset ────────────────────────────────────
    gap_reset_enabled:       bool  = True
    gap_reset_minutes:       int   = 120     # gap > 2h triggers force-reset

    # ── Event log flush ───────────────────────────────────────────
    event_flush_every:       int   = 100

    # ── Instrument metadata ───────────────────────────────────────
    instrument:              str   = "UNKNOWN"
    pip_size:                float = 0.0001

    # ── Engine config override ────────────────────────────────────
    crt_config: Optional[CRTConfig] = None

    # ── Production version tag (Fix 3) ───────────────────────────
    # Set from production_config.PROD_VERSION in execution code.
    # Stamped on every TradeRecord so you can always answer:
    # "Which config version produced this trade / loss?"
    config_version: str = ""

    # ── [P1] Execution delay ──────────────────────────────────────
    execution_delay_candles:     int   = 1      # 0=same-candle (legacy), 1=realistic next-candle fill
    max_trade_duration_candles:  int   = 96     # 24 h on M15 — time-based exit

    # ── [P4] Sweep slippage amplifier ────────────────────────────
    sweep_slippage_multiplier:   float = 2.5    # thin liquidity at sweep levels
    apply_sweep_slippage:        bool  = True

    # ── [P5] Fill probability (seeded) ───────────────────────────
    fill_probability:            float = 0.90   # 10% non-fill rate
    fill_seed:                   int   = 99     # determinism

    # ── [P6] News simulation (seeded) ────────────────────────────
    news_probability_per_candle: float = 0.02   # 2% chance/candle
    news_seed:                   int   = 77     # determinism

    # ── [P7] Adaptive execution delay (Phase-4: vol + displacement gated) ─
    adaptive_delay_enabled:  bool  = True    # True = selective delay; False = fixed
    vol_low_threshold:       float = 0.0008  # ATR/price below this = low-vol regime
    vol_high_threshold:      float = 0.0015  # kept for reporting only
    displacement_threshold:  float = 1.2     # disp_body/ATR min for delay=0 (price truth gate)
    default_delay_candles:   int   = 1       # fallback when adaptive disabled or inputs invalid

    # ── Debug / tuner mode ────────────────────────────────────────────────
    # False = suppress per-trade verbose logs (forced by auto_tuner).
    # True  = full logs for interactive / manual backtests (default).
    debug_mode: bool = True


# ─────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────

@dataclass
class TradeRecord:
    trade_id:          str
    instrument:        str
    direction:         str
    # Raw engine prices (no costs)
    entry_price_raw:   float
    sl_price:          float
    tp1_price:         float
    tp2_price:         float
    # [G1+G2] Realistic fill prices
    entry_price_fill:  float = 0.0   # entry + slippage + spread
    exit_price_fill:   float = 0.0   # exit - spread
    exit_reason:       str   = "OPEN"
    opened_at:         Optional[datetime] = None
    closed_at:         Optional[datetime] = None
    candle_open:       int   = 0
    candle_close:      int   = 0
    # PnL variants
    pnl_pips_raw:      float = 0.0   # without costs (v1 figure)
    pnl_pips_net:      float = 0.0   # after slippage + spread
    pnl_rr_raw:        float = 0.0   # R-multiple on raw prices
    pnl_rr_net:        float = 0.0   # R-multiple on net prices (use this)
    slippage_pips:     float = 0.0   # total slippage cost in pips
    spread_pips:       float = 0.0   # spread cost in pips
    # [G3] Capital curve fields
    capital_before:    float = 0.0
    capital_after:     float = 0.0
    position_size:     float = 0.0   # in base currency units
    # Metadata
    risk_score:        float = 0.0
    risk_pct:          float = 0.0
    state_path:        list  = field(default_factory=list)
    htf_id:            str   = ""
    session:           str   = ""
    # [G5] Distribution fields
    week_of_year:      int   = 0
    day_of_week:       int   = 0     # 0=Mon … 6=Sun
    hour_of_day:       int   = 0
    # [Gaussian scorer] per-trade score decomposition
    gaussian_score:    float = 0.0
    gaussian_p_win:    float = 0.0
    score_retest:      float = 0.0
    score_body:        float = 0.0
    score_disp:        float = 0.0
    score_time:        float = 0.0
    retest_depth:      float = 0.0   # raw feature for calibration
    body_ratio_feat:   float = 0.0
    disp_str_feat:     float = 0.0
    # [Regime + threshold]
    regime:            str   = ""
    dynamic_threshold: float = 0.0
    risk_multiplier:   float = 1.0
    # [P2] Partial close accounting
    tp1_partial_pnl_rr: float = 0.0   # RR locked at TP1 (50% close)
    # [P3] Time-stop tracking — filled by runner
    candle_duration_actual: int = 0   # raw candles held, set at close
    # [ML Dataset] Context features for Gaussian/ML pipeline (no leakage)
    volatility:           float = 0.0   # ATR / price at fill — regime intensity
    range_size:           float = 0.0   # (htf_high - htf_low) / price — normalised
    candles_since_retest: int   = 0     # candles from retest confirmation to fill

    # [Fusion] Per-trade fusion engine breakdown
    # -1.0 sentinel = layer not active (neural stubbed, LLM disabled, or fusion not run)
    fusion_score:     float = -1.0   # FusionResult.final_score
    fusion_gaussian:  float = -1.0   # FusionResult.gaussian
    fusion_neural:    float = -1.0   # -1 = neural not active
    fusion_llm:       float = -1.0   # -1 = LLM not fired
    fusion_llm_fired: bool  = False
    fusion_risk_mult: float = -1.0   # observed only — not applied in passive mode

    @property
    def is_winner(self) -> bool:
        return self.pnl_rr_net > 0

    @property
    def duration_candles(self) -> int:
        return self.candle_close - self.candle_open if self.candle_close > 0 else 0


@dataclass
class RejectionRecord:
    candle_index: int
    timestamp:    datetime
    reason:       str
    state_path:   list
    risk_score:   float = 0.0


# ─────────────────────────────────────────────────────────────────
# [G3] CAPITAL CURVE TRACKER
# ─────────────────────────────────────────────────────────────────

class CapitalCurve:
    """
    Tracks equity curve tick-by-tick.
    Computes: peak equity, drawdown in both R and % terms.
    """

    def __init__(self, initial_capital: float, risk_pct: float, compounding: bool):
        self.initial_capital  = initial_capital
        self.current_capital  = initial_capital
        self.risk_pct         = risk_pct
        self.use_compounding  = compounding
        self.peak_capital     = initial_capital
        self.equity_curve:    list[float] = [initial_capital]
        self._log = logging.getLogger("CRT.CapitalCurve")

    @property
    def current_risk_amount(self) -> float:
        """Dollar amount at risk per trade (respects compounding)."""
        base = self.current_capital if self.use_compounding else self.initial_capital
        return base * self.risk_pct

    def position_size(self, entry: float, sl: float, pip_size: float) -> float:
        """
        Lot size (units) to risk exactly `current_risk_amount` on this trade.
        risk_amount = position_size × |entry - sl|
        """
        risk_distance = abs(entry - sl)
        if risk_distance == 0:
            return 0.0
        return self.current_risk_amount / risk_distance

    def apply_trade(self, pnl_per_unit: float, position_size: float) -> float:
        """
        Record a closed trade. Returns new capital.
        pnl_per_unit: (exit_fill - entry_fill) × direction_sign, per unit held.
        """
        dollar_pnl = pnl_per_unit * position_size
        self.current_capital += dollar_pnl
        self.peak_capital = max(self.peak_capital, self.current_capital)
        self.equity_curve.append(self.current_capital)
        return self.current_capital

    @property
    def drawdown_pct(self) -> float:
        return (self.peak_capital - self.current_capital) / self.peak_capital \
               if self.peak_capital > 0 else 0.0

    @property
    def max_drawdown_pct(self) -> float:
        if not self.equity_curve:
            return 0.0
        peak = self.equity_curve[0]
        max_dd = 0.0
        for eq in self.equity_curve:
            peak = max(peak, eq)
            dd = (peak - eq) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        return max_dd

    @property
    def total_return_pct(self) -> float:
        return (self.current_capital - self.initial_capital) / self.initial_capital

    def to_dict(self) -> dict:
        return {
            "initial_capital":    self.initial_capital,
            "final_capital":      round(self.current_capital, 2),
            "total_return_pct":   round(self.total_return_pct, 4),
            "max_drawdown_pct":   round(self.max_drawdown_pct, 4),
            "current_drawdown_pct": round(self.drawdown_pct, 4),
            "peak_capital":       round(self.peak_capital, 2),
            "equity_curve_len":   len(self.equity_curve),
        }


# ─────────────────────────────────────────────────────────────────
# [G1] SLIPPAGE MODEL
# ─────────────────────────────────────────────────────────────────

class SlippageModel:
    """
    Simulates realistic fill price offset.
    slip ~ uniform(0, slippage_atr_fraction × ATR)
    Always adverse: adds to long entry, subtracts from long exit.
    """

    def __init__(self, atr_fraction: float, seed: int = 42):
        self.atr_fraction = atr_fraction
        self._rng = random.Random(seed if seed != 0 else None)

    def entry_slip(self, atr: float, direction: Direction) -> float:
        slip = self._rng.uniform(0, self.atr_fraction * atr)
        return slip if direction == Direction.LONG else -slip

    def exit_slip(self, atr: float, direction: Direction) -> float:
        slip = self._rng.uniform(0, self.atr_fraction * atr)
        # On exit: long fills lower (adverse), short fills higher
        return -slip if direction == Direction.LONG else slip

    def compute_fill_prices(
        self, entry_raw: float, exit_raw: float,
        direction: Direction, atr: float,
        spread_half: float,
    ) -> tuple[float, float, float, float]:
        """
        Returns (entry_fill, exit_fill, total_slippage, spread_cost).
        spread_half = half_spread in price units.
        """
        e_slip = self.entry_slip(atr, direction)
        x_slip = self.exit_slip(atr, direction)
        # [G2] Spread: buyer pays ask (entry), seller receives bid (exit)
        entry_fill = entry_raw + e_slip + spread_half
        exit_fill  = exit_raw  + x_slip - spread_half
        total_slip = abs(e_slip) + abs(x_slip)
        spread_cost = 2 * spread_half   # round-trip spread cost in price units
        return entry_fill, exit_fill, total_slip, spread_cost


# ─────────────────────────────────────────────────────────────────
# [G4] SESSION GAP DETECTOR
# ─────────────────────────────────────────────────────────────────

class GapDetector:
    """
    Detects time gaps between consecutive candles (weekends, holidays).
    Issues a force-reset signal when gap exceeds threshold.
    Prevents stale states from leaking across sessions.
    """

    def __init__(self, gap_minutes: int, enabled: bool = True):
        self.gap_minutes = gap_minutes
        self.enabled     = enabled
        self._last_ts:   Optional[datetime] = None
        self.log = logging.getLogger("CRT.GapDetector")

    def check(self, candle: Candle) -> tuple[bool, str]:
        """Returns (gap_detected, reason_string)."""
        if not self.enabled:
            return False, ""

        if self._last_ts is None:
            self._last_ts = candle.timestamp
            return False, ""

        gap = candle.timestamp - self._last_ts
        gap_mins = gap.total_seconds() / 60

        self._last_ts = candle.timestamp

        if gap_mins > self.gap_minutes:
            reason = (
                f"Session gap detected: {gap_mins:.0f}min > {self.gap_minutes}min "
                f"({self._last_ts.strftime('%Y-%m-%d %H:%M')} → "
                f"{candle.timestamp.strftime('%Y-%m-%d %H:%M')})"
            )
            self.log.info(f"GAP RESET | {reason}")
            return True, reason

        return False, ""


# ─────────────────────────────────────────────────────────────────
# [G5] TRADE DISTRIBUTION ANALYSER
# ─────────────────────────────────────────────────────────────────

class DistributionAnalyser:
    """
    Computes trade clustering, regime stats, and session/day-of-week breakdown.
    All computation is post-run — never in the hot path.
    """

    DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def analyse(self, trades: list[TradeRecord]) -> dict:
        if not trades:
            return {}

        # Session breakdown
        session_stats = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl_rr": 0.0})
        for t in trades:
            s = t.session or "UNKNOWN"
            session_stats[s]["trades"] += 1
            session_stats[s]["wins"]   += int(t.is_winner)
            session_stats[s]["pnl_rr"] += t.pnl_rr_net

        # Day-of-week breakdown
        dow_stats = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl_rr": 0.0})
        for t in trades:
            if t.opened_at:
                dow = self.DOW[t.opened_at.weekday()]
                dow_stats[dow]["trades"] += 1
                dow_stats[dow]["wins"]   += int(t.is_winner)
                dow_stats[dow]["pnl_rr"] += t.pnl_rr_net

        # Hour-of-day breakdown
        hour_stats = defaultdict(lambda: {"trades": 0, "pnl_rr": 0.0})
        for t in trades:
            if t.opened_at:
                h = t.opened_at.hour
                hour_stats[h]["trades"] += 1
                hour_stats[h]["pnl_rr"] += t.pnl_rr_net

        # Regime: rolling 10-trade win rate
        regime = self._rolling_win_rate(trades, window=10)

        # Clustering: check if losses cluster in time
        loss_indices = [i for i, t in enumerate(trades) if not t.is_winner]
        clustering_score = self._clustering_score(loss_indices, len(trades))

        # Score vs outcome correlation
        score_corr = self._score_outcome_correlation(trades)

        # Build session win rates
        session_wr = {}
        for sess, stats in session_stats.items():
            n = stats["trades"]
            session_wr[sess] = {
                "trades":  n,
                "win_rate": round(stats["wins"] / n, 4) if n > 0 else 0.0,
                "pnl_rr":  round(stats["pnl_rr"], 4),
                "avg_rr":  round(stats["pnl_rr"] / n, 4) if n > 0 else 0.0,
            }

        dow_wr = {}
        for dow, stats in dow_stats.items():
            n = stats["trades"]
            dow_wr[dow] = {
                "trades":  n,
                "win_rate": round(stats["wins"] / n, 4) if n > 0 else 0.0,
                "pnl_rr":  round(stats["pnl_rr"], 4),
            }

        best_hour = max(hour_stats, key=lambda h: hour_stats[h]["pnl_rr"]) \
                    if hour_stats else None
        worst_hour = min(hour_stats, key=lambda h: hour_stats[h]["pnl_rr"]) \
                     if hour_stats else None

        # Best and worst trades
        best  = max(trades, key=lambda t: t.pnl_rr_net)
        worst = min(trades, key=lambda t: t.pnl_rr_net)

        # ── Gaussian score bucket analysis ─────────────────────────
        bucket_labels = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
        bucket_thresholds = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        score_distribution = {}
        for i, label in enumerate(bucket_labels):
            lo, hi = bucket_thresholds[i], bucket_thresholds[i+1]
            bucket = [t for t in trades if lo <= t.gaussian_score < hi]
            if bucket:
                wins = sum(1 for t in bucket if t.is_winner)
                score_distribution[label] = {
                    "trades":   len(bucket),
                    "win_rate": round(wins / len(bucket), 4),
                    "avg_rr":   round(sum(t.pnl_rr_net for t in bucket) / len(bucket), 4),
                    "avg_p_win": round(sum(t.gaussian_p_win for t in bucket) / len(bucket), 4),
                }

        # ── P(win) calibration: predicted vs actual ───────────────
        # Bucket by p_win decile, check predicted vs realised win rate
        calibration = {}
        for lo_pct in range(0, 100, 10):
            lo, hi = lo_pct / 100, (lo_pct + 10) / 100
            bucket = [t for t in trades if lo <= t.gaussian_p_win < hi]
            if len(bucket) >= 3:
                actual_wr = sum(1 for t in bucket if t.is_winner) / len(bucket)
                pred_wr   = sum(t.gaussian_p_win for t in bucket) / len(bucket)
                calibration[f"{lo_pct}-{lo_pct+10}%"] = {
                    "n": len(bucket),
                    "predicted_wr": round(pred_wr, 4),
                    "actual_wr":    round(actual_wr, 4),
                    "calibration_error": round(actual_wr - pred_wr, 4),
                }

        # ── Score→outcome correlation on Gaussian score ───────────
        gauss_corr = 0.0
        if len(trades) >= 3:
            gs = [t.gaussian_score for t in trades]
            oc = [t.pnl_rr_net    for t in trades]
            n = len(gs)
            mg, mo = sum(gs)/n, sum(oc)/n
            cov = sum((g-mg)*(o-mo) for g,o in zip(gs,oc)) / n
            sg  = math.sqrt(sum((g-mg)**2 for g in gs) / n)
            so  = math.sqrt(sum((o-mo)**2 for o in oc) / n)
            gauss_corr = cov / (sg * so) if sg > 0 and so > 0 else 0.0

        # ── Regime breakdown ──────────────────────────────────────
        regime_stats = {}
        for t in trades:
            r = t.regime or "UNKNOWN"
            regime_stats.setdefault(r, []).append(t)
        regime_distribution = {}
        for regime_name, regime_trades in regime_stats.items():
            wins = sum(1 for t in regime_trades if t.is_winner)
            n    = len(regime_trades)
            regime_distribution[regime_name] = {
                "trades":   n,
                "win_rate": round(wins / n, 4) if n > 0 else 0.0,
                "avg_rr":   round(sum(t.pnl_rr_net for t in regime_trades) / n, 4) if n > 0 else 0.0,
                "avg_risk": round(sum(t.risk_multiplier for t in regime_trades) / n, 4) if n > 0 else 0.0,
            }

        return {
            "regime_distribution":      regime_distribution,
            "session_breakdown":        session_wr,
            "day_of_week_breakdown":    dow_wr,
            "best_hour_utc":            best_hour,
            "worst_hour_utc":           worst_hour,
            "rolling_win_rate":         regime,
            "loss_clustering_score":    round(clustering_score, 4),
            "score_outcome_corr":       round(score_corr, 4),
            "gaussian_score_outcome_corr": round(gauss_corr, 4),
            "score_distribution":       score_distribution,
            "p_win_calibration":        calibration,
            "best_trade": {
                "id": best.trade_id, "rr": best.pnl_rr_net,
                "session": best.session, "opened_at": best.opened_at.isoformat() if best.opened_at else "",
            },
            "worst_trade": {
                "id": worst.trade_id, "rr": worst.pnl_rr_net,
                "session": worst.session, "opened_at": worst.opened_at.isoformat() if worst.opened_at else "",
            },
            "cost_analysis": {
                "total_slippage_pips": round(sum(t.slippage_pips for t in trades), 2),
                "total_spread_pips":   round(sum(t.spread_pips   for t in trades), 2),
                "avg_cost_per_trade":  round(
                    (sum(t.slippage_pips + t.spread_pips for t in trades)) / len(trades), 2
                ),
                "raw_vs_net_pnl_rr_delta": round(
                    sum(t.pnl_rr_raw for t in trades) - sum(t.pnl_rr_net for t in trades), 4
                ),
            },
        }

    def _rolling_win_rate(self, trades: list[TradeRecord], window: int) -> list[float]:
        if len(trades) < window:
            return []
        rates = []
        for i in range(window, len(trades) + 1):
            window_trades = trades[i - window:i]
            wr = sum(1 for t in window_trades if t.is_winner) / window
            rates.append(round(wr, 3))
        return rates

    def _clustering_score(self, loss_indices: list[int], total: int) -> float:
        """
        0.0 = losses perfectly spread. 1.0 = all losses clustered together.
        Uses average gap between consecutive losses vs expected gap.
        """
        if len(loss_indices) < 2 or total == 0:
            return 0.0
        gaps = [loss_indices[i+1] - loss_indices[i] for i in range(len(loss_indices)-1)]
        expected_gap = total / max(len(loss_indices), 1)
        avg_gap = sum(gaps) / len(gaps)
        # Score 0 when avg_gap == expected_gap, approaches 1 when avg_gap << expected_gap
        score = max(0.0, 1.0 - avg_gap / expected_gap) if expected_gap > 0 else 0.0
        return min(score, 1.0)

    def _score_outcome_correlation(self, trades: list[TradeRecord]) -> float:
        """Pearson correlation between risk_score and pnl_rr_net."""
        if len(trades) < 3:
            return 0.0
        scores   = [t.gaussian_score if t.gaussian_score > 0 else t.risk_score for t in trades]
        outcomes = [t.pnl_rr_net for t in trades]
        n = len(scores)
        mean_s = sum(scores) / n
        mean_o = sum(outcomes) / n
        cov  = sum((s - mean_s) * (o - mean_o) for s, o in zip(scores, outcomes)) / n
        std_s = math.sqrt(sum((s - mean_s)**2 for s in scores) / n)
        std_o = math.sqrt(sum((o - mean_o)**2 for o in outcomes) / n)
        if std_s == 0 or std_o == 0:
            return 0.0
        return cov / (std_s * std_o)


# ─────────────────────────────────────────────────────────────────
# CANDLE LOADER (unchanged from v1, with minor fix)
# ─────────────────────────────────────────────────────────────────

class CandleLoader:
    DATE_FORMATS = [
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
        "%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M",
        "%Y/%m/%d %H:%M:%S", "%d/%m/%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d",
    ]
    COLUMN_ALIASES = {
        "timestamp": ["timestamp", "datetime", "date time", "open time"],
        "date":      ["date"],
        "time_col":  ["time"],
        "open":      ["open", "o"],
        "high":      ["high", "h"],
        "low":       ["low", "l"],
        "close":     ["close", "c", "adj close"],
        "volume":    ["volume", "vol", "tickvol", "tick volume"],
    }

    def __init__(self, filepath: str, instrument: str = "UNKNOWN"):
        self.filepath   = filepath
        self.instrument = instrument
        self.log        = logging.getLogger("CRT.CandleLoader")

    def _detect_column(self, headers: list[str], field: str) -> Optional[int]:
        for alias in self.COLUMN_ALIASES.get(field, [field]):
            for i, h in enumerate(headers):
                if h.strip().lower() == alias.lower():
                    return i
        return None

    def _parse_timestamp(self, raw: str) -> datetime:
        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(raw.strip(), fmt)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse timestamp: '{raw}'")

    def stream(self) -> Iterator[Candle]:
        with open(self.filepath, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            headers = [h.strip() for h in next(reader)]
            ts_col   = self._detect_column(headers, "timestamp")
            date_col = self._detect_column(headers, "date")
            time_col = self._detect_column(headers, "time_col")
            o_col = self._detect_column(headers, "open")
            h_col = self._detect_column(headers, "high")
            l_col = self._detect_column(headers, "low")
            c_col = self._detect_column(headers, "close")
            v_col = self._detect_column(headers, "volume")

            use_split = (ts_col is None and date_col is not None and time_col is not None)
            if o_col is None or h_col is None or l_col is None or c_col is None:
                raise ValueError(f"Cannot map OHLC columns. Headers: {headers}")

            for line_num, row in enumerate(reader, start=2):
                try:
                    raw_ts = (row[date_col].strip() + " " + row[time_col].strip()
                              if use_split else row[ts_col].strip())
                    ts  = self._parse_timestamp(raw_ts)
                    o   = float(row[o_col]); h = float(row[h_col])
                    l   = float(row[l_col]); c = float(row[c_col])
                    vol = float(row[v_col]) if v_col is not None else 0.0
                    if h < max(o, c) or l > min(o, c) or h == l:
                        continue
                    yield Candle(timestamp=ts, open=o, high=h, low=l, close=c, volume=vol)
                except (ValueError, IndexError):
                    continue

    def count(self) -> int:
        with open(self.filepath, "r", encoding="utf-8-sig") as f:
            return sum(1 for _ in f) - 1


# ─────────────────────────────────────────────────────────────────
# HTF BUILDER (unchanged)
# ─────────────────────────────────────────────────────────────────

class HTFBuilder:
    def __init__(self, candles_per_htf: int, instrument: str = "UNKNOWN"):
        self.candles_per_htf = candles_per_htf
        self.instrument      = instrument
        self._buffer:      list[Candle] = []
        self._htf_idx:     int  = 0
        self._complete:    list[Candle] = []
        self._complete_id: str  = "HTF-INIT"

    @property
    def current_htf_id(self) -> str:
        return self._complete_id

    @property
    def completed_window(self) -> list[Candle]:
        return self._complete[:]

    def push(self, candle: Candle) -> bool:
        self._buffer.append(candle)
        if len(self._buffer) >= self.candles_per_htf:
            self._htf_idx    += 1
            self._complete    = self._buffer[:]
            self._complete_id = f"{self.instrument}-HTF-{self._htf_idx:06d}"
            self._buffer      = []
            return True
        return False

    def seed_candles(self) -> list[Candle]:
        return self._complete[:]


# ─────────────────────────────────────────────────────────────────
# TRADE JOURNAL v2 — with cost tracking
# ─────────────────────────────────────────────────────────────────

class TradeJournal:
    def __init__(
        self, instrument: str, pip_size: float,
        slippage: SlippageModel, capital_curve: CapitalCurve,
    ):
        self.instrument    = instrument
        self.pip_size      = pip_size
        self.slip          = slippage
        self.cap           = capital_curve
        self.open_trade:   Optional[TradeRecord] = None
        self.closed:       list[TradeRecord] = []
        self.rejections:   list[RejectionRecord] = []
        self.log = logging.getLogger("CRT.Journal")

    def on_trade_opened(
        self, trade: Trade, candle: Candle, candle_index: int,
        risk_score: float, state_path: list, htf_id: str,
        session: str, atr: float, spread_half: float,
        score_data: Optional[dict] = None,
        regime: str = "",
        dynamic_threshold: float = 0.65,
        risk_multiplier: float = 1.0,
    ) -> None:
        # [G1+G2] Compute realistic fill prices
        _, _, _, _ = self.slip.compute_fill_prices(
            trade.entry_price, trade.entry_price,
            trade.direction, atr, spread_half,
        )
        e_slip = self.slip.entry_slip(atr, trade.direction)
        entry_fill = trade.entry_price + e_slip + spread_half

        # [G3] Position size — use trade.risk_pct (set by Phase5ExecutionGate)
        # so p_win-tiered sizing is actually applied, not just logged.
        # cap.risk_pct is the base 1% from config; trade.risk_pct is the
        # gate-adjusted value (0.5×–1.5× depending on p_win and regime).
        risk_distance = abs(entry_fill - trade.sl_price)
        if risk_distance > 0 and trade.risk_pct > 0:
            risk_capital = (
                self.cap.current_capital if self.cap.use_compounding
                else self.cap.initial_capital
            ) * trade.risk_pct
            size = risk_capital / risk_distance
        else:
            size = self.cap.position_size(entry_fill, trade.sl_price, self.pip_size)

        # Content-addressed trade ID — unique across instruments and reruns.
        # Generated AFTER entry_fill is computed so the hash is stable.
        stable_trade_id = ExecutionEngine.generate_trade_id(
            instrument = self.instrument,
            opened_at  = candle.timestamp.isoformat(),
            direction  = trade.direction.value,
            entry      = entry_fill,
        )

        self.open_trade = TradeRecord(
            trade_id         = stable_trade_id,
            instrument       = self.instrument,
            direction        = trade.direction.value,
            entry_price_raw  = trade.entry_price,
            sl_price         = trade.sl_price,
            tp1_price        = trade.tp1_price,
            tp2_price        = trade.tp2_price,
            entry_price_fill = entry_fill,
            opened_at        = candle.timestamp,
            candle_open      = candle_index,
            risk_score       = risk_score,
            risk_pct         = trade.risk_pct,
            state_path       = state_path[:],
            htf_id           = htf_id,
            session          = session,
            capital_before   = self.cap.current_capital,
            position_size    = size,
            week_of_year     = candle.timestamp.isocalendar()[1],
            day_of_week      = candle.timestamp.weekday(),
            hour_of_day      = candle.timestamp.hour,
        )
        # ── ADD THIS IMMEDIATELY AFTER TradeRecord creation ──

        if score_data:
            self.open_trade.fusion_score = score_data.get("final_score", 0.0)
            self.open_trade.fusion_gaussian = score_data.get("gaussian", 0.0)
            self.open_trade.fusion_neural = score_data.get("neural", 0.0)
            self.open_trade.fusion_llm = score_data.get("llm", 0.0)
        # Attach Gaussian score components if provided
        if score_data and self.open_trade:
            self.open_trade.gaussian_score  = score_data.get("score", 0.0)
            self.open_trade.gaussian_p_win  = score_data.get("p_win", 0.0)
            comp = score_data.get("components", {})
            self.open_trade.score_retest    = comp.get("retest", 0.0)
            self.open_trade.score_body      = comp.get("body",   0.0)
            self.open_trade.score_disp      = comp.get("disp",   0.0)
            self.open_trade.score_time      = comp.get("time",   0.0)
            feats = score_data.get("features") or {}
            self.open_trade.retest_depth    = feats.get("retest_depth",   0.0)
            self.open_trade.body_ratio_feat = feats.get("body_ratio",     0.0)
            self.open_trade.disp_str_feat   = feats.get("disp_str",       0.0)
        if self.open_trade:
            self.open_trade.regime            = regime
            self.open_trade.dynamic_threshold = dynamic_threshold
            self.open_trade.risk_multiplier   = risk_multiplier

    def on_trade_closed(
        self, trade: Trade, exit_price_raw: float,
        exit_reason: str, candle: Candle, candle_index: int,
        atr: float, spread_half: float,
    ) -> Optional[TradeRecord]:
        if self.open_trade is None:
            return None

        rec = self.open_trade
        direction = Direction.LONG if rec.direction == "LONG" else Direction.SHORT

        # [G1+G2] Realistic exit fill
        x_slip = self.slip.exit_slip(atr, direction)
        exit_fill = exit_price_raw + x_slip - spread_half

        rec.exit_price_fill = exit_fill
        rec.exit_reason     = exit_reason
        rec.closed_at       = candle.timestamp
        rec.candle_close    = candle_index

        # Pip calculations — raw numbers for cost analysis
        price_move_raw = (exit_price_raw - rec.entry_price_raw) if direction == Direction.LONG \
                         else (rec.entry_price_raw - exit_price_raw)
        price_move_net = (exit_fill - rec.entry_price_fill) if direction == Direction.LONG \
                         else (rec.entry_price_fill - exit_fill)

        rec.pnl_pips_raw  = price_move_raw / self.pip_size
        rec.pnl_pips_net  = price_move_net / self.pip_size

        # ── [Phase-2] Partial-aware R-multiple calculation ────────────────
        # risk_pips is anchored to the ORIGINAL SL distance at open (before BE shift).
        # For partial-close paths (TP1 → TP2 or TP1 → BE), trade.pnl was set by
        # update_trade() as the weighted sum of the two legs:
        #   TP1+TP2: partial_pnl (50%@TP1) + runner_pnl (50%@TP2)
        #   TP1+BE:  partial_pnl (50%@TP1) only — runner exits flat
        #   SL only: full loss at sl_price
        # Dividing trade.pnl by risk_dist gives correct R directly.
        #
        # For non-partial paths (TIME_STOP, RESET_CLOSE, BACKTEST_END),
        # fall back to the single price-move calculation.

        # Original risk distance (before any BE shift)
        orig_sl      = rec.sl_price   # stored at open; BE shift is internal to Trade, not TradeRecord
        risk_pips_orig = abs(rec.entry_price_fill - orig_sl) / self.pip_size

        if trade.partial_pnl != 0.0 and risk_pips_orig > 0:
            # Partial-close path: use the weighted PnL computed by update_trade
            risk_dist_price = abs(rec.entry_price_fill - orig_sl)
            # trade.pnl is in price units; convert to R via risk_dist
            rec.pnl_rr_raw  = trade.pnl / risk_dist_price if risk_dist_price > 0 else 0.0
            # Net: apply cost drag proportionally (cost drag ratio from raw move)
            cost_drag_ratio = (price_move_net / price_move_raw) if price_move_raw != 0.0 else 1.0
            rec.pnl_rr_net  = rec.pnl_rr_raw * cost_drag_ratio
            # Log the TP1 partial component
            rec.tp1_partial_pnl_rr = round(
                (trade.partial_pnl / risk_dist_price), 4
            ) if risk_dist_price > 0 else 0.0
        else:
            # No partial close — single-leg exit (SL, time-stop, reset, end)
            risk_pips = risk_pips_orig if risk_pips_orig > 0 else 1.0
            rec.pnl_rr_raw  = (price_move_raw / self.pip_size) / risk_pips
            rec.pnl_rr_net  = (price_move_net / self.pip_size) / risk_pips
            rec.tp1_partial_pnl_rr = 0.0

        # [P3] Candle duration
        rec.candle_duration_actual = candle_index - rec.candle_open

        # Cost breakdown
        rec.slippage_pips = abs(rec.entry_price_fill - rec.entry_price_raw - spread_half) / self.pip_size \
                            + abs(x_slip) / self.pip_size
        rec.spread_pips   = (spread_half * 2) / self.pip_size

        # [G3] Apply to capital curve
        # For partial-close paths, capital impact = trade.pnl (price units) × position_size.
        # trade.pnl was set by update_trade as the blended weighted result of both legs.
        # For non-partial paths, use the standard single-leg price move.
        if trade.partial_pnl != 0.0:
            # trade.pnl is in price units already (partial_pnl + runner_pnl or partial_pnl only)
            self.cap.apply_trade(trade.pnl, rec.position_size)
        else:
            pnl_per_unit = (exit_fill - rec.entry_price_fill) if direction == Direction.LONG \
                           else (rec.entry_price_fill - exit_fill)
            self.cap.apply_trade(pnl_per_unit, rec.position_size)
        rec.capital_after = self.cap.current_capital

        self.closed.append(rec)
        self.open_trade = None

        self.log.debug(
            f"CLOSE | {rec.trade_id} | {exit_reason} | "
            f"raw={rec.pnl_rr_raw:.2f}R net={rec.pnl_rr_net:.2f}R | "
            f"slip={rec.slippage_pips:.1f}p spread={rec.spread_pips:.1f}p | "
            f"capital={rec.capital_after:,.0f}"
        )
        return rec

    def on_rejected(self, reason: str, candle_index: int, ts: datetime,
                    state_path: list, risk_score: float = 0.0) -> None:
        self.rejections.append(RejectionRecord(
            candle_index=candle_index, timestamp=ts,
            reason=reason, state_path=state_path[:], risk_score=risk_score,
        ))

    def to_csv_rows(self) -> list[dict]:
        return [{
            "trade_id":          r.trade_id,
            "instrument":        r.instrument,
            "direction":         r.direction,
            "entry_raw":         r.entry_price_raw,
            "entry_fill":        r.entry_price_fill,
            "sl":                r.sl_price,
            "tp1":               r.tp1_price,
            "tp2":               r.tp2_price,
            "exit_fill":         r.exit_price_fill,
            "exit_reason":       r.exit_reason,
            "opened_at":         r.opened_at.isoformat() if r.opened_at else "",
            "closed_at":         r.closed_at.isoformat() if r.closed_at else "",
            "duration_candles":  r.duration_candles,
            "pnl_pips_raw":      round(r.pnl_pips_raw, 1),
            "pnl_pips_net":      round(r.pnl_pips_net, 1),
            "pnl_rr_raw":        round(r.pnl_rr_raw, 4),
            "pnl_rr_net":        round(r.pnl_rr_net, 4),
            "slippage_pips":     round(r.slippage_pips, 2),
            "spread_pips":       round(r.spread_pips, 2),
            "capital_before":    round(r.capital_before, 2),
            "capital_after":     round(r.capital_after, 2),
            "position_size":     round(r.position_size, 2),
            "risk_pct":          round(r.risk_pct, 6),
            "risk_score":        round(r.risk_score, 4),
            "gaussian_score":    round(r.gaussian_score, 4),
            "gaussian_p_win":    round(r.gaussian_p_win, 4),
            "score_retest":      round(r.score_retest, 4),
            "score_body":        round(r.score_body,   4),
            "score_disp":        round(r.score_disp,   4),
            "score_time":        round(r.score_time,   4),
            "feat_retest_depth": round(r.retest_depth,    4),
            "feat_body_ratio":   round(r.body_ratio_feat, 4),
            "feat_disp_str":     round(r.disp_str_feat,   4),
            "session":           r.session,
            "regime":            r.regime,
            "dynamic_threshold": round(r.dynamic_threshold, 4),
            "risk_multiplier":   round(r.risk_multiplier,   4),
            "tp1_partial_pnl_rr": round(r.tp1_partial_pnl_rr, 4),
            "candle_duration_actual": r.candle_duration_actual,
            "day_of_week":       r.day_of_week,
            "hour_of_day":       r.hour_of_day,
            "htf_id":            r.htf_id,
            # [Fusion] per-trade scoring breakdown
            "fusion_score":      round(r.fusion_score,    4),
            "fusion_gaussian":   round(r.fusion_gaussian, 4),
            "fusion_neural":     round(r.fusion_neural,   4),
            "fusion_llm":        round(r.fusion_llm,      4),
            "fusion_llm_fired":  int(r.fusion_llm_fired),
            "fusion_risk_mult":  round(r.fusion_risk_mult, 4),
        } for r in self.closed]


# ─────────────────────────────────────────────────────────────────
# METRICS ENGINE v2
# ─────────────────────────────────────────────────────────────────

@dataclass
class BacktestMetrics:
    instrument:            str   = "UNKNOWN"
    total_candles:         int   = 0
    gap_resets:            int   = 0    # [G4]
    total_setups:          int   = 0
    approved_trades:       int   = 0
    rejected_trades:       int   = 0
    wins:                  int   = 0
    losses:                int   = 0
    tp1_hits:              int   = 0
    tp2_hits:              int   = 0
    total_pnl_rr_raw:      float = 0.0
    total_pnl_rr_net:      float = 0.0   # [G1+G2] after costs
    max_drawdown_rr:       float = 0.0
    max_drawdown_pct:      float = 0.0   # [G3]
    max_win_streak:        int   = 0
    max_loss_streak:       int   = 0
    avg_trade_duration:    float = 0.0
    rejection_reasons:     dict  = field(default_factory=lambda: defaultdict(int))
    state_distribution:    dict  = field(default_factory=lambda: defaultdict(int))
    monthly_pnl:           dict  = field(default_factory=lambda: defaultdict(float))
    capital_curve:         dict  = field(default_factory=dict)   # [G3]
    distribution:          dict  = field(default_factory=dict)   # [G5]
    sharpe_ratio:          float = 0.0
    profit_factor:         float = 0.0
    expectancy_rr:         float = 0.0
    # [Phase-1] Realism config snapshot — written by BacktestRunner after run
    p1_exec_delay:         int   = 1
    p1_max_duration:       int   = 96
    p1_sweep_slip_mult:    float = 2.5
    p1_fill_prob:          float = 0.90
    p1_news_prob:          float = 0.02
    # [P7] Adaptive delay counters
    p7_delay_zero:         int   = 0
    p7_delay_one:          int   = 0
    p7_adaptive_on:        bool  = True
    p7_vol_low_thresh:     float = 0.0008
    p7_disp_thresh:        float = 1.2    # Phase-4 displacement gate
    # [Ultron Phase-6] Pipeline funnel counts — stamped from DebugCounter after run
    funnel_counts:         dict  = field(default_factory=dict)
    fusion_avg:            float = 0.0
    gaussian_avg:          float = 0.0

    @property
    def win_rate(self) -> float:
        t = self.wins + self.losses
        return self.wins / t if t > 0 else 0.0

    @property
    def avg_rr_net(self) -> float:
        t = self.wins + self.losses
        return self.total_pnl_rr_net / t if t > 0 else 0.0

    @property
    def approval_rate(self) -> float:
        t = self.approved_trades + self.rejected_trades
        return self.approved_trades / t if t > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "instrument":          self.instrument,
            "total_candles":       self.total_candles,
            "gap_resets":          self.gap_resets,
            "total_setups":        self.total_setups,
            "approved_trades":     self.approved_trades,
            "rejected_trades":     self.rejected_trades,
            "approval_rate":       round(self.approval_rate, 4),
            "win_rate":            round(self.win_rate, 4),
            "avg_rr_net":          round(self.avg_rr_net, 4),
            "total_pnl_rr_raw":    round(self.total_pnl_rr_raw, 4),
            "total_pnl_rr_net":    round(self.total_pnl_rr_net, 4),
            "max_drawdown_rr":     round(self.max_drawdown_rr, 4),
            "max_drawdown_pct":    round(self.max_drawdown_pct, 4),
            "max_win_streak":      self.max_win_streak,
            "max_loss_streak":     self.max_loss_streak,
            "tp1_hits":            self.tp1_hits,
            "tp2_hits":            self.tp2_hits,
            "avg_trade_duration":  round(self.avg_trade_duration, 1),
            "rejection_reasons":   dict(self.rejection_reasons),
            "state_distribution":  dict(self.state_distribution),
            "monthly_pnl":         {k: round(v, 4) for k, v in self.monthly_pnl.items()},
            "capital_curve":       self.capital_curve,
            "distribution":        self.distribution,
            "sharpe_ratio":        round(self.sharpe_ratio, 4),
            "profit_factor":       round(self.profit_factor if self.profit_factor != float("inf") else 999.0, 4),
            "expectancy_rr":       round(self.expectancy_rr, 4),
        }


class MetricsEngine:
    def __init__(self, instrument: str):
        self.instrument = instrument
        self.dist = DistributionAnalyser()

    def compute(
        self, journal: TradeJournal, capital: CapitalCurve,
        total_candles: int, state_counts: dict, gap_resets: int,
    ) -> BacktestMetrics:
        trades = journal.closed
        m = BacktestMetrics(instrument=self.instrument)
        m.total_candles    = total_candles
        m.gap_resets       = gap_resets
        m.approved_trades  = len(trades)
        m.rejected_trades  = len(journal.rejections)
        m.total_setups     = m.approved_trades + m.rejected_trades
        m.state_distribution = dict(state_counts)
        for r in journal.rejections:
            m.rejection_reasons[r.reason] += 1
        m.capital_curve = capital.to_dict()

        if not trades:
            return m

        m.wins           = sum(1 for t in trades if t.pnl_rr_net > 0)
        m.losses         = sum(1 for t in trades if t.pnl_rr_net <= 0)
        m.tp1_hits       = sum(1 for t in trades if t.exit_reason in ("TP1", "TP2"))
        m.tp2_hits       = sum(1 for t in trades if t.exit_reason == "TP2")
        # [P3] Surface time-stop count in rejection_reasons for reporting
        m.rejection_reasons["time_stop"] = sum(
            1 for t in trades if t.exit_reason == "TIME_STOP"
        )
        m.total_pnl_rr_raw = sum(t.pnl_rr_raw for t in trades)
        m.total_pnl_rr_net = sum(t.pnl_rr_net for t in trades)
        m.avg_trade_duration = sum(t.duration_candles for t in trades) / len(trades)
        m.max_drawdown_rr = self._max_dd_rr([t.pnl_rr_net for t in trades])
        m.max_drawdown_pct = capital.max_drawdown_pct
        m.max_win_streak, m.max_loss_streak = self._streaks([t.pnl_rr_net > 0 for t in trades])

        for t in trades:
            if t.opened_at:
                m.monthly_pnl[t.opened_at.strftime("%Y-%m")] += t.pnl_rr_net

        m.distribution = self.dist.analyse(trades)  # [G5]

        import math as _math
        rr_series = [t.pnl_rr_net for t in trades]
        if len(rr_series) >= 2:
            mean_rr = sum(rr_series) / len(rr_series)
            std_rr  = _math.sqrt(sum((r - mean_rr)**2 for r in rr_series) / len(rr_series))
            m.sharpe_ratio = mean_rr / std_rr if std_rr > 0 else 0.0

        gross_win  = sum(t.pnl_rr_net for t in trades if t.pnl_rr_net > 0)
        gross_loss = abs(sum(t.pnl_rr_net for t in trades if t.pnl_rr_net < 0))
        m.profit_factor = gross_win / gross_loss if gross_loss > 0 else float("inf")

        if trades:
            wins   = [t.pnl_rr_net for t in trades if t.pnl_rr_net > 0]
            losses = [t.pnl_rr_net for t in trades if t.pnl_rr_net <= 0]
            avg_win  = sum(wins)   / len(wins)   if wins   else 0.0
            avg_loss = sum(losses) / len(losses) if losses else 0.0
            wr = m.wins / len(trades)
            m.expectancy_rr = avg_win * wr + avg_loss * (1 - wr)

        return m

    def _max_dd_rr(self, pnl: list[float]) -> float:
        eq = peak = dd = 0.0
        for p in pnl:
            eq += p
            peak = max(peak, eq)
            dd = max(dd, peak - eq)
        return dd

    def _streaks(self, wins: list[bool]) -> tuple[int, int]:
        mw = ml = cw = cl = 0
        for w in wins:
            if w: cw += 1; cl = 0
            else: cl += 1; cw = 0
            mw = max(mw, cw); ml = max(ml, cl)
        return mw, ml


# ─────────────────────────────────────────────────────────────────
# REPORT WRITER v2
# ─────────────────────────────────────────────────────────────────

class ReportWriter:
    def __init__(self, output_dir: str, instrument: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.instrument = instrument

    def write_all(self, metrics: BacktestMetrics, journal: TradeJournal,
                  events: list[dict]) -> dict[str, str]:
        paths = {}
        paths["summary"]    = self._write_summary(metrics)
        paths["trades_csv"] = self._write_trades(journal)
        paths["events"]     = self._write_events(events)
        paths["report"]     = self._write_report(metrics)
        return paths

    def _write_summary(self, m: BacktestMetrics) -> str:
        p = self.output_dir / f"{self.instrument}_summary.json"
        out = m.to_dict()

        

# --- Fusion Stats ---
        if hasattr(self, "fusion_avg"):
            out["fusion_avg"] = round(self.fusion_avg, 4)

        if hasattr(self, "gaussian_avg"):
            out["gaussian_avg"] = round(self.gaussian_avg, 4)


        with open(p, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        return str(p)

    def _write_trades(self, journal: TradeJournal) -> str:
        rows = journal.to_csv_rows()
        if not rows:
            return ""
        p = self.output_dir / f"{self.instrument}_trades.csv"
        with open(p, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader(); w.writerows(rows)
        return str(p)

    def _write_events(self, events: list[dict]) -> str:
        if not events:
            return ""
        p = self.output_dir / f"{self.instrument}_events.jsonl"
        with open(p, "w", encoding="utf-8") as f:
            for ev in events:
                f.write(json.dumps(ev) + "\n")
        return str(p)

    def _write_report(self, m: BacktestMetrics) -> str:
        d = m.distribution
        cost = d.get("cost_analysis", {})
        cap  = m.capital_curve

        lines = [
            "═" * 65,
            f"  CRT ENGINE BACKTEST v2 — {m.instrument}",
            "═" * 65,
            "",
            "── COVERAGE ──────────────────────────────────────────────────",
            f"  Total candles:               {m.total_candles:>10,}",
            f"  Session gap resets:          {m.gap_resets:>10,}",
            f"  Total setups:                {m.total_setups:>10,}",
            f"  Approved / Rejected:         {m.approved_trades:>5,} / {m.rejected_trades:<5,}",
            f"  Approval rate:               {m.approval_rate:>10.1%}",
            "",
            "── PERFORMANCE (NET of costs) ────────────────────────────────",
            f"  Win rate:                    {m.win_rate:>10.1%}",
            f"  Avg RR (net):                {m.avg_rr_net:>10.2f}R",
            f"  Expectancy (per trade):      {m.expectancy_rr:>+10.3f}R",
            f"  Profit factor:               {m.profit_factor:>10.2f}  (>1.5 = viable)",
            f"  Sharpe ratio (per-trade):    {m.sharpe_ratio:>10.3f}  (>0.5 = good)",
            f"  Total PnL raw/net:           {m.total_pnl_rr_raw:>+6.2f}R / {m.total_pnl_rr_net:>+6.2f}R",
            f"  Cost drag:                   {m.total_pnl_rr_raw - m.total_pnl_rr_net:>+10.2f}R",
            f"  TP1 / TP2 hit rate:          {m.tp1_hits/max(m.approved_trades,1):.1%} / {m.tp2_hits/max(m.approved_trades,1):.1%}",
            "",
            "── RISK ──────────────────────────────────────────────────────",
            f"  Max drawdown (R):            {m.max_drawdown_rr:>10.2f}R",
            f"  Max drawdown (% equity):     {m.max_drawdown_pct:>10.1%}",
            f"  Max win / loss streak:       {m.max_win_streak:>4} / {m.max_loss_streak:<4}",
            f"  Avg trade duration:          {m.avg_trade_duration:>10.1f} candles",
            "",
            "── PHASE-1 REALISM STATS ─────────────────────────────────────",
            f"  Exec delay (candles):        {m.p1_exec_delay:>10}  [P1]",
            f"  TP1 partial closes:          {m.tp1_hits:>10}  [P2]  50% booked + SL→BE",
            f"  TP2 runner hits:             {m.tp2_hits:>10}  [P2]  remaining 50%",
            f"  Time-stop exits:             {m.rejection_reasons.get('time_stop', 0):>10}  [P3]  ({m.p1_max_duration}c max)",
            f"  Sweep slip multiplier:       {m.p1_sweep_slip_mult:>9.1f}×  [P4]",
            f"  Fill probability:            {m.p1_fill_prob:>10.0%}  [P5]",
            f"  News prob/candle:            {m.p1_news_prob:>10.1%}  [P6]",
            f"  Adaptive delay ON:           {'YES' if m.p7_adaptive_on else 'NO':>10}  [P7]",
            f"  Delay=0 fills (vol+disp):    {m.p7_delay_zero:>10}  [P7]  vol<{m.p7_vol_low_thresh} & disp≥{m.p7_disp_thresh}",
            f"  Delay=1 fills (default):     {m.p7_delay_one:>10}  [P7]",
            "",
            "── CAPITAL CURVE ─────────────────────────────────────────────",
            f"  Starting capital:            {cap.get('initial_capital', 0):>10,.0f}",
            f"  Final capital:               {cap.get('final_capital', 0):>10,.0f}",
            f"  Total return:                {cap.get('total_return_pct', 0):>10.1%}",
            "",
            "── TRADE COSTS ───────────────────────────────────────────────",
            f"  Total slippage:              {cost.get('total_slippage_pips', 0):>10.1f} pips",
            f"  Total spread:                {cost.get('total_spread_pips', 0):>10.1f} pips",
            f"  Avg cost per trade:          {cost.get('avg_cost_per_trade', 0):>10.1f} pips",
            f"  Raw vs Net PnL delta:        {cost.get('raw_vs_net_pnl_rr_delta', 0):>+10.2f}R",
            "",
            "── SESSION BREAKDOWN ─────────────────────────────────────────",
        ]
        for sess, stats in sorted(d.get("session_breakdown", {}).items()):
            lines.append(
                f"  {sess:<12} {stats['trades']:>4} trades  "
                f"WR={stats['win_rate']:.0%}  PnL={stats['pnl_rr']:>+6.2f}R"
            )

        lines += ["", "── DAY OF WEEK ───────────────────────────────────────────────"]
        for day, stats in d.get("day_of_week_breakdown", {}).items():
            lines.append(
                f"  {day:<12} {stats['trades']:>4} trades  "
                f"WR={stats['win_rate']:.0%}  PnL={stats['pnl_rr']:>+6.2f}R"
            )

        corr = d.get("score_outcome_corr", 0)
        cluster = d.get("loss_clustering_score", 0)
        lines += [
            "",
            "── SIGNAL QUALITY ────────────────────────────────────────────",
            f"  Score→outcome correlation:   {corr:>10.3f}  (>0.2 = score predictive)",
            f"  Loss clustering score:       {cluster:>10.3f}  (<0.3 = well dispersed)",
        ]

        lines += ["", "── REJECTION BREAKDOWN ───────────────────────────────────────"]
        for reason, count in sorted(m.rejection_reasons.items(), key=lambda x: -x[1]):
            pct = count / m.rejected_trades if m.rejected_trades > 0 else 0
            lines.append(f"  {reason:<38} {count:>5} ({pct:.1%})")

        # ── Score distribution ────────────────────────────────────
        lines += ["", "── GAUSSIAN SCORE DISTRIBUTION ──────────────────────────────"]
        score_dist = d.get("score_distribution", {})
        if score_dist:
            lines.append(f"  {'Bucket':<12} {'Trades':>6}  {'WinRate':>8}  {'AvgRR':>8}  {'AvgP(win)':>10}")
            lines.append(f"  {'-'*12}  {'-'*5}  {'-'*7}  {'-'*7}  {'-'*9}")
            for bucket, stats in sorted(score_dist.items()):
                lines.append(
                    f"  {bucket:<12} {stats['trades']:>6}  "
                    f"{stats['win_rate']:>8.1%}  "
                    f"{stats['avg_rr']:>+8.3f}R  "
                    f"{stats['avg_p_win']:>9.3f}"
                )
        else:
            lines.append("  No trades with Gaussian scores yet.")

        # ── P(win) calibration ────────────────────────────────────
        calib = d.get("p_win_calibration", {})
        if calib:
            lines += ["", "── P(WIN) CALIBRATION (predicted vs actual) ──────────────────"]
            lines.append(f"  {'P(win) range':<16} {'N':>4}  {'Pred WR':>8}  {'Actual WR':>10}  {'Error':>8}")
            lines.append(f"  {'-'*16}  {'-'*3}  {'-'*7}  {'-'*9}  {'-'*7}")
            for prange, stats in sorted(calib.items()):
                err = stats["calibration_error"]
                flag = " ← overfit" if abs(err) > 0.15 else ""
                lines.append(
                    f"  {prange:<16} {stats['n']:>4}  "
                    f"{stats['predicted_wr']:>8.1%}  "
                    f"{stats['actual_wr']:>10.1%}  "
                    f"{err:>+8.3f}{flag}"
                )

        gc = d.get("gaussian_score_outcome_corr", 0)
        lines.append("")
        lines.append(f"  Gaussian score→outcome corr: {gc:.4f}  (>0.2 = signal has edge)")

        lines += ["", "── REGIME PERFORMANCE ────────────────────────────────────────"]
        for regime_name, rs in d.get("regime_distribution", {}).items():
            lines.append(
                f"  {regime_name:<12} {rs['trades']:>4} trades  "
                f"WR={rs['win_rate']:.0%}  AvgRR={rs['avg_rr']:>+.3f}R  "
                f"AvgRisk={rs['avg_risk']:.2f}x"
            )

        lines += ["", "── MONTHLY PnL ───────────────────────────────────────────────"]
        for month in sorted(m.monthly_pnl.keys()):
            pnl = m.monthly_pnl[month]
            bar = "█" * max(0, int(abs(pnl)))
            lines.append(f"  {month}  {'+'if pnl>=0 else '-'}{abs(pnl):.2f}R  {bar}")

        lines += ["", "═" * 65]

        text = "\n".join(lines)
        p = self.output_dir / f"{self.instrument}_report.txt"
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return str(p)


# ─────────────────────────────────────────────────────────────────
# BACKTEST RUNNER v2
# ─────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────
# GAUSSIAN SCORING ENGINE
# Data-driven non-linear CRT scorer.
# Replaces the linear Ultron score at the confirmation gate.
# Based on statistical analysis showing Goldilocks zones, not linear rewards.
# ─────────────────────────────────────────────────────────────────

class CRTGaussianScorer:
    """
    Scores a CRT setup using Gaussian (bell-curve) proximity scoring.

    Key insight from statistical analysis:
      - retest_depth: optimal 37-65%, NOT "more/less is better"
      - body_ratio:   optimal 65-85%, full bodies (100%) underperform
      - disp_str:     optimal 1.0-1.2× ATR, massive moves exhaust momentum

    Formula: final = (s_retest^0.35) * (s_body^0.30) * (s_disp^0.20) * (s_time^0.15)
    P(win) mapped via calibrated sigmoid: 1 / (1 + exp(-4.5*(score - 0.5)))
    """

    # ── REAL EURCAD M15 CALIBRATION (200 retest observations 2024-2025) ──
    # Replaces theoretical priors. All parameters computed from empirical distribution.
    RETEST_MU   = 0.237; RETEST_S2  = 0.040   # real mean/variance of retest_depth
    BODY_MU     = 0.847; BODY_S2    = 0.021   # real mean/variance of body_ratio
    DISP_MU     = 2.177; DISP_S2    = 1.196   # real mean/variance of disp_str ATR mult

    # Hard filters — 5th/95th percentile of real observed feature range
    RETEST_MIN  = 0.025; RETEST_MAX = 0.469
    DISP_MAX    = 3.670                         # 95th pct; 1.80 rejected 100% of real trades

    # Sigmoid calibration
    SIGMOID_K   = 4.5
    SIGMOID_X0  = 0.50

    # Execution threshold (dynamic threshold overrides this per-trade)
    EXECUTE_P   = 0.50

    def __init__(self, decay_lambda: float = 0.05):
        self.decay_lambda = decay_lambda
        self._log = logging.getLogger("CRT.GaussianScorer")

    # ── Primitives ────────────────────────────────────────────────

    @staticmethod
    def _gaussian(x: float, mu: float, sigma2: float) -> float:
        return math.exp(-((x - mu) ** 2) / sigma2)

    def _p_win(self, score: float) -> float:
        """Sigmoid probability mapping: calibrated against historical outcomes."""
        return 1.0 / (1.0 + math.exp(-self.SIGMOID_K * (score - self.SIGMOID_X0)))

    # ── Main scorer ───────────────────────────────────────────────

    def compute(self, features: dict, current_index: int = 0) -> dict:
        """
        features = {
            retest_depth:  float  — fraction of displacement retraced (0-1)
            body_ratio:    float  — body / wick of displacement candle (0-1)
            disp_str:      float  — displacement size in ATR multiples
            retest_index:  int    — candle index when retest was confirmed (cached)
        }
        current_index: current candle index for time-decay computation.
        Returns dict with score, p_win, components, decision, reject_reason.
        """
        r = features.get("retest_depth", 0.0)
        b = features.get("body_ratio", 0.0)
        d = features.get("disp_str", 0.0)
        # Use retest_index from cached features; fall back to candles_since_retest
        retest_idx = features.get("retest_index", 0)
        t = max(0, current_index - retest_idx) if current_index > 0 else features.get("candles_since_retest", 0)

        # ── Hard filters — capital protection ─────────────────────
        if r < self.RETEST_MIN or r > self.RETEST_MAX:
            return self._reject("filter_retest_depth_invalid",
                                f"retest={r:.3f} outside [{self.RETEST_MIN},{self.RETEST_MAX}]")
        if d > self.DISP_MAX:
            return self._reject("filter_displacement_exhaustion",
                                f"disp_str={d:.2f} > {self.DISP_MAX}")

        # ── Gaussian component scores (all 0–1) ────────────────────
        s_retest = self._gaussian(r, self.RETEST_MU,  self.RETEST_S2)
        s_body   = self._gaussian(b, self.BODY_MU,    self.BODY_S2)
        s_disp   = self._gaussian(d, self.DISP_MU,    self.DISP_S2)
        s_time   = math.exp(-self.decay_lambda * t)

        # ── Multiplicative aggregation (weighted exponents) ────────
        # Using weighted geometric mean — penalises weak links harder than linear addition.
        final_score = (
            (s_retest ** 0.35) *
            (s_body   ** 0.30) *
            (s_disp   ** 0.20) *
            (s_time   ** 0.15)
        )

        components = {
            "retest": round(s_retest, 4),
            "body":   round(s_body,   4),
            "disp":   round(s_disp,   4),
            "time":   round(s_time,   4),
        }

        score = self.scoring_engine.score(features, final_score)

        # HARD BLOCK (ML override)
        if score["decision"] == "BLOCK":
            return self._reject("ML_BLOCK", score["reason"])

        # WARN (log only)
        if score["decision"] == "WARN":
            self._log.warning(f"[WARN] {score}")

        # Use hybrid score instead of raw Gaussian
        p_win = self._p_win(score["final_score"])

        decision = "execute" if p_win >= self.EXECUTE_P else "reject_low_p_win"
        self._log.debug(
            f"Gaussian | r={r:.3f} b={b:.3f} d={d:.2f} t={t} "
            f"→ score={final_score:.4f} p_win={p_win:.3f} → {decision}"
        )

        return {
            "score":        round(final_score, 6),
            "p_win":        round(p_win, 4),
            "components":   components,
            "decision":     decision,
            "reject_reason": None,
        }

    @staticmethod
    def _reject(reason: str, detail: str = "") -> dict:
        return {
            "score":         0.0,
            "p_win":         0.0,
            "components":    {"retest": 0.0, "body": 0.0, "disp": 0.0, "time": 0.0},
            "decision":      "reject",
            "reject_reason": reason,
        }

    # ── Feature extractor ─────────────────────────────────────────

    @staticmethod
    def extract_features(state, candle_idx: int) -> Optional[dict]:
        """
        Returns cached_features if available (set at RETEST_CONFIRMED).
        Falls back to live extraction if cache is missing.
        Returns None on failure — safe no-op.
        """
        # Primary: use features cached at RETEST_CONFIRMED time
        if state.cached_features is not None:
            return state.cached_features

        # Fallback: live extraction (less reliable through confirmation window)
        if state.displacement_candle is None or state.retest_candle is None:
            return None
        if state.active_range is None or state.active_range.size == 0:
            return None

        disp   = state.displacement_candle
        retest = state.retest_candle
        disp_move = abs(disp.close - disp.open)
        if disp_move == 0 or state.atr == 0:
            return None
        retest_retrace = abs(retest.close - disp.close) / disp_move
        return {
            "retest_depth": min(max(retest_retrace, 0.0), 1.0),
            "body_ratio":   disp.body_ratio,
            "disp_str":     disp.wick_size / state.atr,
            "retest_index": state.retest_candle_index,
        }


# ─────────────────────────────────────────────────────────────────
# REGIME DETECTOR
# Classifies current market condition per candle.
# EXPANSION = trending + volatile. DEAD = flat + compressed. NEUTRAL = normal.
# ─────────────────────────────────────────────────────────────────

class RegimeDetector:
    """
    Classifies market regime from ATR and short-term price momentum.
    Used to scale position risk and modulate threshold.
    """
    def __init__(self, vol_low: float = 0.0004, vol_high: float = 0.0015):
        self.vol_low  = vol_low    # ATR/price threshold for DEAD
        self.vol_high = vol_high   # ATR/price threshold for EXPANSION
        self._log = logging.getLogger("CRT.Regime")

    def detect(self, atr: float, price: float, prev_close: float, close: float) -> str:
        if price == 0 or atr == 0:
            return "NEUTRAL"
        volatility      = atr / price
        trend_strength  = abs(close - prev_close) / atr
        if volatility > self.vol_high and trend_strength > 1.2:
            return "EXPANSION"
        if volatility < self.vol_low:
            return "DEAD"
        return "NEUTRAL"


# ─────────────────────────────────────────────────────────────────
# DYNAMIC THRESHOLD CONTROLLER
# Adapts execution threshold based on rolling win-rate feedback.
# Tightens after losing runs. Relaxes during winning runs.
# ─────────────────────────────────────────────────────────────────

class DynamicThreshold:
    """
    Rolling 20-trade win-rate feedback loop.
    Warmup period uses a fixed default threshold.
    """
    WARMUP          = 10    # trades before adaptation kicks in
    THRESHOLD_TIGHT = 0.70  # WR < 45% → tighten
    THRESHOLD_MID   = 0.65  # WR 45-60% → normal
    THRESHOLD_LOOSE = 0.58  # WR > 60%  → relax (edge confirmed)

    def __init__(self):
        self.history: list[int] = []
        self._log = logging.getLogger("CRT.DynThreshold")

    def update(self, is_win: bool) -> None:
        self.history.append(1 if is_win else 0)
        if len(self.history) > 20:
            self.history.pop(0)

    def get_threshold(self) -> float:
        if len(self.history) < self.WARMUP:
            return self.THRESHOLD_MID   # warmup default
        wr = sum(self.history) / len(self.history)
        if wr < 0.45:
            t = self.THRESHOLD_TIGHT
        elif wr > 0.60:
            t = self.THRESHOLD_LOOSE
        else:
            t = self.THRESHOLD_MID
        self._log.debug(f"DynThreshold | rolling_wr={wr:.2f} → threshold={t:.2f}")
        return t




# ─────────────────────────────────────────────────────────────────
# [Ultron Phase-6] DRAWDOWN GOVERNOR
# ─────────────────────────────────────────────────────────────────

class DrawdownGovernor:
    """
    Hard R-based drawdown governor.

    Thresholds:
        >= 20R drawdown  ->  risk x 0.50
        >= 40R drawdown  ->  risk x 0.25
        >= 60R drawdown  ->  HALT (no new trades)

    Call update(r_result) after every closed trade.
    Read .multiplier before sizing the next trade.
    Read .halted to skip new fills entirely.
    """

    def __init__(self, r_half: float = 20.0, r_quarter: float = 40.0, r_halt: float = 60.0):
        self.r_half    = r_half
        self.r_quarter = r_quarter
        self.r_halt    = r_halt
        self._cumulative_r: float = 0.0
        self._peak_r:       float = 0.0
        self._current_dd_r: float = 0.0
        self.halted:        bool  = False
        self._log = logging.getLogger("CRT.DrawdownGovernor")

    def update(self, r_result: float) -> float:
        """Feed closed trade R result. Returns risk multiplier for next trade."""
        if self.halted:
            return 0.0
        self._cumulative_r += r_result
        self._peak_r        = max(self._peak_r, self._cumulative_r)
        self._current_dd_r  = self._peak_r - self._cumulative_r
        mult = self._multiplier()
        if mult == 0.0:
            self.halted = True
            self._log.warning(
                f"DrawdownGovernor HALT | "
                f"cumR={self._cumulative_r:.1f} peak={self._peak_r:.1f} "
                f"dd={self._current_dd_r:.1f}R >= {self.r_halt}"
            )
        elif mult < 1.0:
            self._log.info(f"DrawdownGovernor SCALE | mult={mult:.2f} dd={self._current_dd_r:.1f}R")
        return mult

    def _multiplier(self) -> float:
        if self._current_dd_r >= self.r_halt:    return 0.0
        if self._current_dd_r >= self.r_quarter: return 0.25
        if self._current_dd_r >= self.r_half:    return 0.50
        return 1.0

    @property
    def multiplier(self) -> float:
        return self._multiplier()

    @property
    def current_dd_r(self) -> float:
        return self._current_dd_r

    def status(self) -> str:
        return (
            f"DrawdownGovernor | cumR={self._cumulative_r:+.1f} "
            f"peak={self._peak_r:.1f} dd={self._current_dd_r:.1f}R "
            f"mult={self.multiplier:.2f} halted={self.halted}"
        )

# ─────────────────────────────────────────────────────────────────
# [Phase-5] EXECUTION GATE
# Single source of truth for: score → threshold → risk_pct decision.
#
# Design rationale (from Phase-5 audit, 159 trades):
#   • p_win from CRTGaussianScorer has corr +0.069 vs RR — low but
#     positive and better than the GaussianNB LOO-CV (-0.058).
#   • Regime-aware thresholds reduce false executions in dead markets.
#   • Risk scaling is p_win-driven, not binary — captures the
#     monotonic relationship between scorer confidence and sizing.
#   • When ML correlation crosses 0.15 (needs ~600+ trades), swap in
#     CRTCalibratedScorer without touching anything else here.
# ─────────────────────────────────────────────────────────────────

@dataclass
class ExecutionDecision:
    approved:       bool
    reject_reason:  Optional[str]
    p_win:          float
    score:          float
    regime:         str
    threshold_used: float
    risk_pct:       float
    risk_multiplier: float
    score_data:     Optional[dict]

class Phase5ExecutionGate:
    """
    [Ultron Phase-6] Regime-based risk sizing. Gaussian REMOVED.

    Risk = f(session + double_sweep + ATR regime). No probability prediction.
    Aligns risk with market energy, not a static model.

    Session tiers (from cached_features stamped at RETEST_CONFIRMED):
        LONDON / NEWYORK + double_sweep  ->  1.25%
        LONDON / NEWYORK                 ->  1.00%
        ASIA                             ->  0.75%
        outside all sessions             ->  0.50%

    Regime modifier (ATR-based, on top of session tier):
        EXPANSION  ->  x1.25
        DEAD       ->  x0.75
        NEUTRAL    ->  x1.00

    Clamped to [base x 0.5, base x 1.5].
    CRTGaussianScorer kept as dead code. Swap to LightGBM at 2000+ trades.
    ExecutionDecision interface unchanged.
    """

    SESSION_RISK = {
        "LONDON_DS":  0.0125,
        "NEWYORK_DS": 0.0125,
        "LONDON":     0.0100,
        "NEWYORK":    0.0100,
        "ASIA":       0.0075,
        "DEFAULT":    0.0050,
    }
    REGIME_MULT = {
        "EXPANSION": 1.25,
        "NEUTRAL":   1.00,
        "DEAD":      0.75,
    }

    def __init__(
        self,
        scorer: "CRTGaussianScorer",
        regime_det: "RegimeDetector",
        threshold_ctrl: "DynamicThreshold",
        base_risk_pct: float = 0.01,
    ):
        self.scorer         = scorer          # preserved -- not called
        self.regime_det     = regime_det
        self.threshold_ctrl = threshold_ctrl
        self.base_risk_pct  = base_risk_pct
        self._log           = logging.getLogger("CRT.ExecGate")
        self.n_approved:         int = 0
        self.n_rejected_p_win:   int = 0
        self.n_rejected_no_feat: int = 0

    def reset(self) -> None:
        self.n_approved = self.n_rejected_p_win = self.n_rejected_no_feat = 0

    def evaluate(
        self,
        features: Optional[dict],
        candle_idx: int,
        atr: float,
        price: float,
        prev_close: float,
    ) -> ExecutionDecision:
        """
        [Phase-6] Regime-based sizing. Gaussian NOT called.
        features must contain 'session' and 'double_confirmed'
        (stamped by crt_engine_v2 at RETEST_CONFIRMED time).
        """
        # Regime (always computed)
        regime = self.regime_det.detect(
            atr=atr, price=price,
            prev_close=prev_close, close=price,
        )
        regime_mult = self.REGIME_MULT.get(regime, 1.0)

        # No features: minimum size, still approved
        if not features:
            self.n_approved += 1
            risk_pct = max(self.base_risk_pct * 0.5,
                           self.SESSION_RISK["DEFAULT"] * regime_mult)
            return ExecutionDecision(
                approved=True, reject_reason=None,
                p_win=0.0, score=0.0, regime=regime,
                threshold_used=0.0,
                risk_pct=risk_pct,
                risk_multiplier=risk_pct / self.base_risk_pct,
                score_data=None,
            )

        # Session tier
        session      = features.get("session", "UNKNOWN")
        double_sweep = bool(features.get("double_confirmed", False))

        if session in ("LONDON", "NEWYORK") and double_sweep:
            tier_key = session + "_DS"
        elif session in ("LONDON", "NEWYORK", "ASIA"):
            tier_key = session
        else:
            tier_key = "DEFAULT"

        session_risk    = self.SESSION_RISK[tier_key]
        raw_risk        = session_risk * regime_mult
        final_risk_pct  = max(self.base_risk_pct * 0.5,
                               min(self.base_risk_pct * 1.5, raw_risk))
        final_risk_mult = final_risk_pct / self.base_risk_pct

        self.n_approved += 1
        self._log.debug(
            f"ExecGate [P6] | session={session} ds={double_sweep} "
            f"tier={tier_key} regime={regime} "
            f"session_risk={session_risk:.4f} regime_mult={regime_mult:.2f} "
            f"final={final_risk_pct:.4f} ({final_risk_mult:.2f}x base)"
        )

        return ExecutionDecision(
            approved=True, reject_reason=None,
            p_win=0.0, score=0.0, regime=regime,
            threshold_used=0.0,
            risk_pct=final_risk_pct,
            risk_multiplier=final_risk_mult,
            score_data=None,
        )

    def report(self) -> str:
        total = self.n_approved + self.n_rejected_p_win + self.n_rejected_no_feat
        return (
            f"Phase6Gate [regime-based] | total={total} "
            f"approved={self.n_approved}"
        )


class BacktestRunner:
    def __init__(self, bt_config: BacktestConfig):
        self.cfg     = bt_config
        self.log     = bt_log
        self.crt_cfg = bt_config.crt_config or ConfigBuilder.build(bt_config.instrument)
        self.debug          = DebugCounter()
        self.scorer         = CRTGaussianScorer(decay_lambda=self.crt_cfg.score_decay_lambda)
        self.regime_det     = RegimeDetector()
        self.threshold_ctrl = DynamicThreshold()
        # [Phase-6] Drawdown governor -- scales/halts at 20R/40R/60R
        self.dd_governor    = DrawdownGovernor(r_half=20.0, r_quarter=40.0, r_halt=60.0)
        # [Phase-5] Centralised execution gate
        self.exec_gate      = Phase5ExecutionGate(
            scorer         = self.scorer,
            regime_det     = self.regime_det,
            threshold_ctrl = self.threshold_ctrl,
            base_risk_pct  = bt_config.risk_pct_per_trade,
        )
        # [P5] Seeded fill-probability RNG — deterministic across runs
        self._fill_rng  = random.Random(self.cfg.fill_seed)
        # [P6] Seeded news-simulation RNG — deterministic across runs
        self._news_rng  = random.Random(self.cfg.news_seed)
        # [P1] Pending trade buffer — holds a queued trade between candles
        self._pending_trade:      Optional[Trade] = None
        self._pending_trade_cidx: int             = 0
        self._trade_open_cidx:    int             = 0
        # [P7] Adaptive delay counters — for reporting
        self._delay_zero_count: int = 0
        self._delay_one_count:  int = 0
        # [Fusion] Engine + logger — initialised if fusion_engine.py is present
        self.fusion_engine: Optional["FusionEngine"] = None
        self.trade_logger:  Optional["TradeLogger"]  = None
        from train_pipeline import load_active_neural_fn
        self.scoring_engine = ScoringEngine(
            mode="PASSIVE",
            neural_fn=load_active_neural_fn(),
            llm_enabled=True,
            threshold=self.crt_cfg.score_threshold
        )
        # Backtest passive mode: fusion scores are logged but NEVER applied to risk/execution.
        # neural_fn=None, llm_fn=None, enable_llm=False ensures full determinism.
        # To activate neural or LLM layers, set them after construction in live mode.
        if _FUSION_AVAILABLE:
            try:
                _g_adapter = GaussianAdapter(self.scorer)
                # Auto-load TradeNet if train_pipeline has run (None = stub until trained)
                _neural_fn = None
                try:
                    from train_pipeline import load_active_neural_fn
                    _neural_fn = load_active_neural_fn()
                except ImportError:
                    pass
                self.fusion_engine = FusionEngine(
                    gaussian_adapter = _g_adapter,
                    neural_fn  = _neural_fn,   # None until first training run
                    llm_fn     = None,         # plug llm_gate_live.llm_gate here for live
                    config     = FusionConfig(enable_llm=False),
                )
                self.trade_logger = TradeLogger(
                    path = Path("logs") / f"{bt_config.instrument}_fusion.jsonl"
                )
                bt_log.info(f"FusionEngine initialised | neural={'active' if _neural_fn else 'stub'} | llm=disabled")
            except Exception as _fe:
                bt_log.warning(f"FusionEngine init failed (skipping): {_fe}")
                self.fusion_engine = None
                self.trade_logger  = None

    # ── [P7] Adaptive execution delay resolver (Phase-4) ─────────
    def _resolve_execution_delay(
        self, atr: float, price: float, displacement: float = 0.0
    ) -> int:
        """
        Phase-4: delay=0 ONLY when BOTH conditions hold:
          1. Low volatility   (ATR/price < vol_low_threshold)
          2. Strong displacement  (disp_body/ATR >= displacement_threshold)

        Displacement = actual market aggression at signal time.
        Large body / ATR ratio → continuation probable → safe for immediate fill.
        Weak displacement → mean-reversion risk → wait for next candle open.

        Returns 0 or 1. Never >1. Always deterministic.
        """
        if not self.cfg.adaptive_delay_enabled or price <= 0 or atr <= 0:
            return self.cfg.default_delay_candles

        vol = atr / price

        if vol < self.cfg.vol_low_threshold and displacement >= self.cfg.displacement_threshold:
            return 0   # low-vol + strong displacement: fill same candle

        return 1   # all other cases: next-candle fill

    def run(self, candle_source: Iterator[Candle], total_candles: int,
            output_dir: str = "results") -> BacktestMetrics:
        accepted = 0
        rejected = 0

        fusion_scores = []
        gaussian_scores = []
        model_divergences = []

        engine  = CRTEngine(self.crt_cfg)
        self.exec_gate.reset()
        self.dd_governor = DrawdownGovernor(r_half=20.0, r_quarter=40.0, r_halt=60.0)  # [P6] fresh each run
        htf     = HTFBuilder(self.cfg.htf_candles_per_range, self.cfg.instrument)
        slip    = SlippageModel(
            self.cfg.slippage_atr_fraction if self.cfg.slippage_enabled else 0.0,
            self.cfg.slippage_seed,
        )
        cap     = CapitalCurve(
            self.cfg.initial_capital,
            self.cfg.risk_pct_per_trade,
            self.cfg.use_compounding,
        )
        journal = TradeJournal(self.cfg.instrument, self.cfg.pip_size, slip, cap)
        gap_det = GapDetector(self.cfg.gap_reset_minutes, self.cfg.gap_reset_enabled)
        met_eng = MetricsEngine(self.cfg.instrument)
        writer  = ReportWriter(output_dir, self.cfg.instrument)

        state_counts:   dict[str, int] = defaultdict(int)
        candle_idx      = 0
        warmup_done     = False
        initialised     = False
        gap_resets      = 0
        flushed_events: list[dict] = []
        state_path:     list[str] = []
        last_risk_score = 0.0
        last_session    = ""

        self.log.info(
            f"Backtest v2 | {self.cfg.instrument} | {total_candles:,} candles | "
            f"capital={self.cfg.initial_capital:,.0f} | "
            f"slip={'ON' if self.cfg.slippage_enabled else 'OFF'} | "
            f"gap_reset={'ON' if self.cfg.gap_reset_enabled else 'OFF'}"
        )

        # ── CONFIG GOVERNANCE: assertion + snapshot + hash ──────────────────
        import json as _json, hashlib as _hashlib, dataclasses as _dc, os as _os
        assert isinstance(self.crt_cfg, CRTConfig), (
            f"BacktestRunner: crt_cfg is {type(self.crt_cfg)}, expected CRTConfig. "
            "Use ConfigBuilder.build() to create configs."
        )
        _os.makedirs(output_dir, exist_ok=True)
        def _serialize(obj):
            if isinstance(obj, (datetime,)):
                return obj.isoformat()
            if hasattr(obj, "isoformat"):  # catches time objects
                return obj.isoformat()
            return str(obj)

        _cfg_dict = _dc.asdict(self.crt_cfg)
        _snapshot_path = _os.path.join(output_dir, "config_snapshot.json")
        def _json_safe(obj):
            import datetime

            if isinstance(obj, dict):
                return {k: _json_safe(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_json_safe(v) for v in obj]
            elif isinstance(obj, tuple):
                return tuple(_json_safe(v) for v in obj)
            elif isinstance(obj, datetime.time):
                return obj.strftime("%H:%M:%S")
            elif isinstance(obj, datetime.datetime):
                return obj.isoformat()
            else:
                return obj

        with open(_snapshot_path, "w") as _snap_f:
            _json.dump(_json_safe(_cfg_dict), _snap_f, indent=2, default=_serialize)
        _cfg_str  = _json.dumps(_json_safe(_cfg_dict), sort_keys=True)
        _cfg_hash = _hashlib.md5(_cfg_str.encode()).hexdigest()
        self.log.info(f"[CONFIG HASH] {_cfg_hash} | snapshot -> {_snapshot_path}")
        # ────────────────────────────────────────────────────────────────────

        prev_candle: Optional[Candle] = None

        for candle in candle_source:
            candle_idx += 1

            self.debug.inc("candles")
            if candle_idx % 5000 == 0:
                pct = candle_idx / total_candles * 100 if total_candles > 0 else 0
                self.log.info(
                    f"  {candle_idx:,}/{total_candles:,} ({pct:.0f}%) | "
                    f"trades={len(journal.closed)} cap={cap.current_capital:,.0f} "
                    f"dd={cap.drawdown_pct:.1%}"
                )

            htf_completed = htf.push(candle)

            # ── Warmup ─────────────────────────────────────────────
            if not warmup_done:
                if candle_idx < self.cfg.warmup_candles:
                    prev_candle = candle
                    continue
                warmup_done = True

            # ── Initialise ─────────────────────────────────────────
            if not initialised:
                if htf.seed_candles():
                    session = self._session(candle.timestamp)
                    engine.initialise_range(htf.seed_candles(), htf.current_htf_id, session)
                    initialised = True
                    self.log.info(f"  Engine init @ candle {candle_idx} | HTF={htf.current_htf_id}")
                prev_candle = candle
                continue

            # ── [G4] Gap detection ─────────────────────────────────
            gap_fired, gap_reason = gap_det.check(candle)
            if gap_fired:
                gap_resets += 1
                self.debug.inc("gap_resets")
                if journal.open_trade and engine.state.active_trade:
                    spread_half = candle.close * self.cfg.simulated_spread_pct / 2
                    rec = journal.on_trade_closed(
                        engine.state.active_trade, candle.open,
                        "GAP_RESET_CLOSE", candle, candle_idx,
                        engine.state.atr, spread_half,
                    )
                    if rec is not None:
                        self.threshold_ctrl.update(rec.pnl_rr_net > 0)
                        self.dd_governor.update(rec.pnl_rr_net)
                        if rec is not None and self.trade_logger is not None:
                            self.trade_logger.log_exit(
                                trade_id         = rec.trade_id,
                                pnl_rr_net       = rec.pnl_rr_net,
                                exit_reason      = rec.exit_reason,
                                duration_candles = rec.candle_duration_actual,
                                closed_at        = rec.closed_at,
                            )
                engine.sm.reset_to_range(engine.state, gap_reason, candle, engine.ev_log)
                state_path = []

            # ── [P6] News simulation (seeded, 2% per candle) ──────
            if self._news_rng.random() < self.cfg.news_probability_per_candle:
                engine.set_news(True)
            else:
                engine.set_news(False)

            # ── [P1] Pending trade — delayed fill at next candle open
            # Trade was queued last candle; fill it on current candle's open.
            if self._pending_trade is not None:
                waited = candle_idx - self._pending_trade_cidx
                # [P7] _pending_trade.open_candle_index holds the resolved delay (0 or 1)
                _resolved_delay = self._pending_trade.open_candle_index
                if waited >= _resolved_delay:
                    pt = self._pending_trade
                    self._pending_trade = None

                    # [P5] Seeded fill-probability check
                    if self._fill_rng.random() > self.cfg.fill_probability:
                        if self.cfg.debug_mode:
                            bt_log.info(
                                f"[P5] NON-FILL | {pt.id} | "
                                f"fill_prob={self.cfg.fill_probability:.0%} — skipped"
                            )
                        # Abandon the queued setup cleanly
                        engine.sm.reset_to_range(
                            engine.state, "non_fill", candle, engine.ev_log
                        )
                    elif self.dd_governor.halted:
                        # [Phase-6] DrawdownGovernor HALT — skip fill
                        bt_log.warning(
                            f"[P6-Gov] HALT active — skipping fill {pt.id} "
                            f"dd={self.dd_governor.current_dd_r:.1f}R"
                        )
                        engine.sm.reset_to_range(
                            engine.state, "dd_halt", candle, engine.ev_log
                        )
                    else:
                        # [P7] delay=0 → fill at current candle close (same candle signal)
                        #       delay=1 → fill at current candle open (next candle)
                        _fill_price = candle.close if _resolved_delay == 0 else candle.open
                        pt.entry_price = _fill_price
                        pt.open_candle_index = candle_idx   # actual open candle (overwrite stored delay)
                        engine.executor.open_trade(pt, candle.timestamp)
                        engine.state.active_trade = pt
                        self._trade_open_cidx = candle_idx

                        # [Phase-5] Single execution gate call — score, regime, risk_pct
                        _prev_c = prev_candle.close if prev_candle else candle.close
                        _decision = self.exec_gate.evaluate(
                            features  = pt.cached_features,
                            candle_idx= candle_idx,
                            atr       = engine.state.atr,
                            price     = candle.close,
                            prev_close= _prev_c,
                        )
                        _gdata      = _decision.score_data
                        if _gdata and pt.cached_features:
                            _gdata["features"] = pt.cached_features
                        _regime     = _decision.regime
                        _thresh     = _decision.threshold_used
                        _final_r    = _decision.risk_multiplier
                        _gov_mult   = self.dd_governor.multiplier
                        pt.risk_pct = _decision.risk_pct * _gov_mult
                        if self.cfg.debug_mode:
                            bt_log.debug(f"[P6-Gov] {pt.id} | risk={pt.risk_pct:.4f} gov_mult={_gov_mult:.2f} dd_R={self.dd_governor.current_dd_r:.1f}")

                        if self.cfg.debug_mode:
                            bt_log.info(
                                f"[P5-Gate] {pt.id} | "
                                f"p_win={_decision.p_win:.3f} score={_decision.score:.3f} "
                                f"regime={_regime} thresh={_thresh:.2f} "
                                f"risk={pt.risk_pct:.4f} ({_final_r:.2f}×base)"
                            )

                        _spread_h = candle.close * self.cfg.simulated_spread_pct / 2

                        # ── [Fusion] Score + risk-mult + log entry ──────────
                        if self.fusion_engine is not None:
                            # Enrich cached_features with live ATR ratio so the
                            # feature_builder.build_feature_vector() call inside
                            # the model has a non-zero atr_vol value.
                            # cached_features is a dict; we extend a copy to
                            # avoid mutating the engine's internal state.
                            _raw_feats  = dict(pt.cached_features) if pt.cached_features else {}
                            _atr_now    = engine.state.atr
                            _price_now  = candle.close if candle.close > 0 else 1.0
                            _raw_feats["atr_vol"] = (_atr_now / _price_now) if _atr_now > 0 else 0.0

                            _signal_ctx = {
                                "symbol":    self.cfg.instrument,
                                "direction": str(pt.direction),
                                "session":   self._session(candle.timestamp),
                            }
                            _fres = self.fusion_engine.evaluate(
                                features   = _raw_feats,
                                signal     = _signal_ctx,
                                candle_idx = candle_idx,
                            )
                            # --- Fusion Tracking ---
                            fusion_scores.append(getattr(_fres, "final_score", 0.0))
                            gaussian_scores.append(getattr(_fres, "gaussian_score", 0.0))

                            if hasattr(_fres, "model_divergence"):
                                model_divergences.append(_fres.model_divergence)
                            
                            # Apply fusion risk multiplier on top of Phase-6 risk
                            pt.risk_pct = pt.risk_pct * _fres.risk_mult if _fres.risk_mult > 0 else pt.risk_pct
                            # Stamp fusion breakdown onto TradeRecord
                            pt_rec_fusion = _fres   # saved for journal stamping below

                            if self.trade_logger is not None:
                                self.trade_logger.log_entry(
                                    trade_id    = pt.id,
                                    instrument  = self.cfg.instrument,
                                    direction   = str(pt.direction),
                                    session     = self._session(candle.timestamp),
                                    regime      = _regime,
                                    features    = _raw_feats,
                                    fusion_result = _fres,
                                    risk_pct    = pt.risk_pct,
                                    entry_price = pt.entry_price,
                                    sl_price    = pt.sl_price,
                                    tp1_price   = pt.tp1_price,
                                    tp2_price   = pt.tp2_price,
                                    opened_at   = candle.timestamp,
                                )
                        else:
                            pt_rec_fusion = None

                        # [P4] Amplify slippage if a sweep event is still live
                        _orig_frac = journal.slip.atr_fraction
                        if self.cfg.apply_sweep_slippage and engine.state.sweep_event:
                            journal.slip.atr_fraction *= self.cfg.sweep_slippage_multiplier
                            if self.cfg.debug_mode:
                                bt_log.debug(
                                    f"[P4] SWEEP SLIP | {pt.id} | "
                                    f"slip×{self.cfg.sweep_slippage_multiplier}"
                                )
                        journal.on_trade_opened(
                            trade=pt, candle=candle, candle_index=candle_idx,
                            risk_score=0.0, state_path=state_path,
                            htf_id=htf.current_htf_id, session=self._session(candle.timestamp),
                            atr=engine.state.atr, spread_half=_spread_h,
                            score_data=_gdata,  # dict or None — never a raw float
                            regime=_regime,
                            dynamic_threshold=_thresh, risk_multiplier=_final_r,
                        )
                        # Stamp fusion breakdown onto the TradeRecord just created
                        if pt_rec_fusion is not None and journal.open_trade is not None:
                            journal.open_trade.fusion_score     = pt_rec_fusion.final_score
                            journal.open_trade.fusion_gaussian  = pt_rec_fusion.gaussian
                            journal.open_trade.fusion_neural    = pt_rec_fusion.neural    if pt_rec_fusion.neural is not None else -1.0
                            journal.open_trade.fusion_llm       = pt_rec_fusion.llm       if pt_rec_fusion.llm    is not None else -1.0
                            journal.open_trade.fusion_llm_fired = pt_rec_fusion.llm_fired
                            journal.open_trade.fusion_risk_mult = pt_rec_fusion.risk_mult
                        elif journal.open_trade is not None:
                            # Fusion not available — stamp -1.0 sentinels explicitly
                            journal.open_trade.fusion_score     = -1.0
                            journal.open_trade.fusion_gaussian  = -1.0
                            journal.open_trade.fusion_neural    = -1.0
                            journal.open_trade.fusion_llm       = -1.0
                            journal.open_trade.fusion_llm_fired = False
                            journal.open_trade.fusion_risk_mult = -1.0
                        # ── [ML Dataset] Stamp context features onto TradeRecord ──
                        if journal.open_trade is not None:
                            _atr_fill   = engine.state.atr
                            _price_fill = candle.close if candle.close > 0 else 1.0
                            journal.open_trade.volatility = _atr_fill / _price_fill if _price_fill > 0 else 0.0
                            # range_size = normalised HTF range (htf_high - htf_low) / price
                            _rng = engine.state.active_range
                            if _rng is not None and _price_fill > 0:
                                journal.open_trade.range_size = (_rng.h_ref - _rng.l_ref) / _price_fill
                            else:
                                journal.open_trade.range_size = 0.0
                            # candles_since_retest from cached features retest_index
                            _cf = pt.cached_features or {}
                            _retest_idx = _cf.get("retest_index", candle_idx)
                            journal.open_trade.candles_since_retest = max(0, candle_idx - _retest_idx)
                        journal.slip.atr_fraction = _orig_frac   # restore
                        state_path = []
                        if self.cfg.debug_mode:
                            bt_log.info(
                                f"[P{'7' if _resolved_delay == 0 else '1'}] "
                                f"{'SAME-CANDLE' if _resolved_delay == 0 else 'DELAYED'} FILL | "
                                f"{pt.id} | entry={_fill_price:.5f} "
                                f"delay={_resolved_delay}c waited={waited}c"
                            )

            # ── [P3] Time-based exit ──────────────────────────────
            if journal.open_trade and engine.state.active_trade:
                _dur = candle_idx - self._trade_open_cidx
                if _dur >= self.cfg.max_trade_duration_candles:
                    _at  = engine.state.active_trade
                    _sh  = candle.close * self.cfg.simulated_spread_pct / 2
                    if self.cfg.debug_mode:
                        bt_log.info(
                            f"[P3] TIME STOP | {_at.id} | "
                            f"held {_dur}c ≥ max {self.cfg.max_trade_duration_candles}c"
                        )
                    rec = journal.on_trade_closed(
                        _at, candle.close, "TIME_STOP",
                        candle, candle_idx, engine.state.atr, _sh,
                    )
                    if rec is not None:
                        rec.candle_duration_actual = _dur
                        self.threshold_ctrl.update(rec.pnl_rr_net > 0)
                        self.dd_governor.update(rec.pnl_rr_net)
                        if rec is not None and self.trade_logger is not None:
                            self.trade_logger.log_exit(
                                trade_id         = rec.trade_id,
                                pnl_rr_net       = rec.pnl_rr_net,
                                exit_reason      = rec.exit_reason,
                                duration_candles = rec.candle_duration_actual,
                                closed_at        = rec.closed_at,
                            )
                    engine.sm.reset_to_range(
                        engine.state, "time_stop", candle, engine.ev_log
                    )
                    state_path = []

            # ── Spread ─────────────────────────────────────────────
            if self.cfg.simulated_spread_pct > 0:
                engine.set_spread(
                    candle.close * (1 - self.cfg.simulated_spread_pct / 2),
                    candle.close * (1 + self.cfg.simulated_spread_pct / 2),
                )
            spread_half = candle.close * self.cfg.simulated_spread_pct / 2

            # ── Process candle ─────────────────────────────────────
            prev_state = engine.state.current_state.name
            result     = engine.process_candle(candle, htf.current_htf_id)
            # cached_features is read from trade.cached_features (set in build_trade, survives reset)
            curr_state = engine.state.current_state.name
            state_counts[prev_state] += 1
            if prev_state != curr_state:
                state_path.append(f"{prev_state}→{curr_state}")

            action = result.get("action", "NONE")

            # ── DEBUG HOOKS on engine action results ──────────────
            if action == "SWEEP_DETECTED":
                self.debug.inc("sweeps_detected")
            elif action == "DISPLACEMENT_CONFIRMED":
                self.debug.inc("sweep_to_displacement_attempt")
                self.debug.inc("displacement_success")
            elif action == "EXPANSION_CONFIRMED":
                self.debug.inc("displacement_to_expansion_attempt")
                self.debug.inc("expansion_success")
            elif action == "RETEST_CONFIRMED":
                self.debug.inc("expansion_to_retest_attempt")
                self.debug.inc("retest_success")
            elif action == "EVALUATING_SOFT_CONF":
                pass  # mid-window, counted via RETEST_CONFIRMED entry
            elif action == "CONFIRMATION_FAILED":
                self.debug.inc("confirmation_phase_entered")
                self.debug.inc("confirmation_failed_timeout")
            elif action in ("FILTER_REJECTED", "WAITING_CONFIRMATION"):
                self.debug.inc("filter_rejected_zone")
            elif action == "SWEEP_EXPIRED":
                self.debug.inc("sweep_expired")
            elif "TRADE_OPENED" in action:
                self.debug.inc("confirmation_phase_entered")   # soft conf window entered
                self.debug.inc("confirmation_passed")           # and approved
                self.debug.inc("execution_attempt")
                self.debug.inc("execution_success")
            elif action.startswith("RISK_REJECTED"):
                self.debug.inc("execution_attempt")
                reason_str = action.split(":", 1)[1] if ":" in action else ""
                if "no_double_sweep"    in reason_str: self.debug.inc("risk_rejected_no_double_sweep")
                elif "outside_session" in reason_str: self.debug.inc("risk_rejected_outside_session")
                elif "score_below"     in reason_str: self.debug.inc("risk_rejected_low_score")
                elif "news_filter"     in reason_str: self.debug.inc("risk_rejected_news")
                elif "spread_too_high" in reason_str: self.debug.inc("risk_rejected_spread")

            # ── HTF refresh counter ────────────────────────────────
            if htf_completed:
                self.debug.inc("htf_range_refreshes")
                # Non-destructive range refresh in RANGE state
                if engine.state.current_state == CRTState.RANGE and htf.seed_candles():
                    new_rng = engine.detector.detect_htf_range(
                        htf.seed_candles(), htf.current_htf_id,
                        self._session(candle.timestamp),
                    )
                    engine.state.active_range = new_rng

            if "TRADE_OPENED" in action and engine.state.active_trade:
                # [P1] Queue into pending buffer — fill executes next candle at open.
                # Gaussian log fires here so the score is visible immediately in the log.
                _pt = engine.state.active_trade
                _gf = _pt.cached_features
                _gd = self.scorer.compute(_gf, candle_idx) if _gf else None
                if _gd:
                    _gd["features"] = _gf
                    _prev_c2 = prev_candle.close if prev_candle else candle.close
                    _reg2    = self.regime_det.detect(
                        atr=engine.state.atr, price=candle.close,
                        prev_close=_prev_c2, close=candle.close,
                    )
                    _thr2 = self.threshold_ctrl.get_threshold()
                    bt_log.info(
                        f"Gaussian | {_pt.id} | "
                        f"score={_gd['score']:.4f} p_win={_gd['p_win']:.3f} "
                        f"regime={_reg2} threshold={_thr2:.2f} | "
                        f"r={_gf['retest_depth']:.3f} "
                        f"b={_gf['body_ratio']:.3f} "
                        f"d={_gf['disp_str']:.2f}x"
                    )

                # Detach from engine — pending buffer owns it now
                engine.state.active_trade = None
                # [P7] Phase-4: resolve delay using vol AND displacement (price-truth gate)
                # disp_str = displacement_candle body / ATR — already in cached_features
                _disp = _gf["disp_str"] if _gf else 0.0
                _delay = self._resolve_execution_delay(
                    engine.state.atr, candle.close, _disp
                )
                if _delay == 0:
                    self._delay_zero_count += 1
                else:
                    self._delay_one_count += 1
                _pt.open_candle_index = _delay    # actual open idx set on fill
                self._pending_trade      = _pt
                self._pending_trade_cidx = candle_idx
                bt_log.info(
                    f"[P7] QUEUED | {_pt.id} | "
                    f"delay={_delay}c vol={engine.state.atr/candle.close:.5f} "
                    f"disp={_disp:.2f}x "
                    f"(vol<{self.cfg.vol_low_threshold}={engine.state.atr/candle.close < self.cfg.vol_low_threshold} "
                    f"disp>={self.cfg.displacement_threshold}={_disp >= self.cfg.displacement_threshold})"
                )

            elif "TRADE_STOPPED" in action or "TRADE_TP2" in action:
                if journal.open_trade and engine.state.active_trade:
                    t = engine.state.active_trade
                    exit_raw = t.sl_price if "STOPPED" in action else t.tp2_price
                    rec = journal.on_trade_closed(
                        t, exit_raw, "STOPPED" if "STOPPED" in action else "TP2",
                        candle, candle_idx, engine.state.atr, spread_half,
                    )
                    # ── Threshold feedback loop ──────────────────────
                    if rec is not None:
                        self.threshold_ctrl.update(rec.pnl_rr_net > 0)
                        self.dd_governor.update(rec.pnl_rr_net)
                        if rec is not None and self.trade_logger is not None:
                            self.trade_logger.log_exit(
                                trade_id         = rec.trade_id,
                                pnl_rr_net       = rec.pnl_rr_net,
                                exit_reason      = rec.exit_reason,
                                duration_candles = rec.candle_duration_actual,
                                closed_at        = rec.closed_at,
                            )

            elif action.startswith("RISK_REJECTED"):
                reason = action.split(":", 1)[1] if ":" in action else "unknown"
                score  = engine.state.risk_score.final if engine.state.risk_score else 0.0
                journal.on_rejected(reason, candle_idx, candle.timestamp, state_path, score)
                fusion_scores.append(getattr(_rej_fres, "final_score", 0.0))
                gaussian_scores.append(getattr(_rej_fres, "gaussian_score", 0.0))

                if hasattr(_rej_fres, "model_divergence"):
                    model_divergences.append(_rej_fres.model_divergence)

                # [Fusion] Log every rejection with features + fusion scores.
                # Rejections that later would have been profitable expose gate weakness
                # and become the most valuable training signal in the learning loop.
                if self.fusion_engine is not None and self.trade_logger is not None:
                    _rej_feats = dict(engine.state.cached_features) if engine.state.cached_features else {}
                    _atr_rej   = engine.state.atr
                    _px_rej    = candle.close if candle.close > 0 else 1.0
                    _rej_feats["atr_vol"] = (_atr_rej / _px_rej) if _atr_rej > 0 else 0.0
                    _rej_signal = {
                        "symbol":    self.cfg.instrument,
                        "direction": "",
                        "session":   self._session(candle.timestamp),
                    }
                    _rej_fres = self.fusion_engine.evaluate(
                        features   = _rej_feats,
                        signal     = _rej_signal,
                        candle_idx = candle_idx,
                    )
                    self.trade_logger.log_rejection(
                        instrument    = self.cfg.instrument,
                        features      = _rej_feats,
                        fusion_result = _rej_fres,
                        reason        = reason,
                        candle_idx    = candle_idx,
                    )
                state_path = []

            elif action == "RESET" and journal.open_trade and engine.state.active_trade:
                _at = engine.state.active_trade
                _price = candle.close

                # ── SL breach check: cap exit at SL if price gapped past it ──
                # Price can gap through SL between candles before update_trade
                # checks it. Cap the exit price at SL so RR can't exceed -1R.
                _is_long = (_at.direction == Direction.LONG)
                _sl_breached = (
                    (_is_long  and _price < _at.sl_price) or
                    (not _is_long and _price > _at.sl_price)
                )
                if _sl_breached:
                    _price = _at.sl_price   # honour the stop, don't carry gap loss
                    if self.cfg.debug_mode:
                        bt_log.debug(f"SL CAP | {_at.id} gapped past SL — capping exit at {_price:.5f}")

                # ── Exit protection: let profitable trades ride ──
                _in_profit = (
                    (_is_long  and _price > _at.entry_price) or
                    (not _is_long and _price < _at.entry_price)
                )
                if _in_profit and not _sl_breached:
                    if self.cfg.debug_mode:
                        bt_log.debug(f"EXIT PROTECTION | {_at.id} in profit — skipping reset close")
                else:
                    rec = journal.on_trade_closed(
                        _at, _price, "RESET_CLOSE", candle, candle_idx,
                        engine.state.atr, spread_half,
                    )
                    if rec is not None:
                        self.threshold_ctrl.update(rec.pnl_rr_net > 0)
                        self.dd_governor.update(rec.pnl_rr_net)
                        if rec is not None and self.trade_logger is not None:
                            self.trade_logger.log_exit(
                                trade_id         = rec.trade_id,
                                pnl_rr_net       = rec.pnl_rr_net,
                                exit_reason      = rec.exit_reason,
                                duration_candles = rec.candle_duration_actual,
                                closed_at        = rec.closed_at,
                            )

            # ── Event flush ────────────────────────────────────────
            if len(engine.state.event_log) >= self.cfg.event_flush_every:
                flushed_events.extend(engine.dump_event_log())
                engine.state.event_log.clear()

            prev_candle = candle

        flushed_events.extend(engine.dump_event_log())

        # Force-close at end
        if journal.open_trade and engine.state.active_trade and engine.candle_buffer:
            last = engine.candle_buffer[-1]
            spread_half = last.close * self.cfg.simulated_spread_pct / 2
            journal.on_trade_closed(
                engine.state.active_trade, last.close,
                "BACKTEST_END", last, candle_idx,
                engine.state.atr, spread_half,
            )

        self.debug.report()
        self.log.info(self.exec_gate.report())
        self.log.info(self.dd_governor.status())  # [Phase-6] governor final state
        m = met_eng.compute(journal, cap, candle_idx, state_counts, gap_resets)
        # [Ultron Phase-6] Stamp full funnel counts onto metrics for tuner access
        m.funnel_counts = dict(self.debug.counts)
        # [P-wire] Stamp Phase-1 config onto metrics so report is self-contained
        m.p1_exec_delay      = self.cfg.execution_delay_candles
        m.p1_max_duration    = self.cfg.max_trade_duration_candles
        m.p1_sweep_slip_mult = self.cfg.sweep_slippage_multiplier
        m.p1_fill_prob       = self.cfg.fill_probability
        m.p1_news_prob       = self.cfg.news_probability_per_candle
        # [P7] Stamp adaptive delay counters
        m.p7_delay_zero      = self._delay_zero_count
        m.p7_delay_one       = self._delay_one_count
        m.p7_adaptive_on     = self.cfg.adaptive_delay_enabled
        m.p7_vol_low_thresh  = self.cfg.vol_low_threshold
        m.p7_disp_thresh     = self.cfg.displacement_threshold
        m.fusion_avg = sum(fusion_scores)/len(fusion_scores) if fusion_scores else 0.0
        m.gaussian_avg = sum(gaussian_scores)/len(gaussian_scores) if gaussian_scores else 0.0
        
        
        paths = writer.write_all(m, journal, flushed_events)

        self._print_summary(m)
        self.log.info("Output:")
        for k, p in paths.items():
            if p:
                self.log.info(f"  {k:<15} → {p}")
        return m
    
    def _session(self, ts: datetime) -> str:
        t = ts.time()
        for name, (start, end) in self.crt_cfg.session_windows.items():
            if start <= t <= end:
                return name
        return "LONDON"

    def _print_summary(self, m: BacktestMetrics) -> None:
        time_stops  = m.rejection_reasons.get("time_stop", 0)
        non_fills   = m.rejection_reasons.get("non_fill",  0)
        self.log.info("─" * 55)
        self.log.info(f"  {m.instrument} | {m.approved_trades} trades | "
                      f"WR={m.win_rate:.1%} | AvgRR={m.avg_rr_net:.2f}R | "
                      f"PnL(net)={m.total_pnl_rr_net:+.2f}R | "
                      f"MaxDD={m.max_drawdown_pct:.1%}")
        self.log.info("─" * 55)
        self.log.info(
            f"  Phase-1 realism | "
            f"delay={self.cfg.execution_delay_candles}c [P1] | "
            f"TP1-partial={m.tp1_hits} [P2] | "
            f"TP2-runner={m.tp2_hits} [P2] | "
            f"time_stops={time_stops} [P3] | "
            f"non_fills={non_fills} [P5]"
        )


# ─────────────────────────────────────────────────────────────────
# MULTI-INSTRUMENT RUNNER
# ─────────────────────────────────────────────────────────────────

class MultiInstrumentRunner:
    INSTRUMENT_PIP = {
        "EURCAD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01,
        "AUDUSD": 0.0001, "NZDUSD": 0.0001, "USDCHF": 0.0001,
        "BTCUSDT": 1.0,   "ETHUSDT": 0.01,  "XAUUSD": 0.01,
        "US30": 1.0,      "NAS100": 0.25,   "SP500": 0.25,
    }

    def __init__(self, data_dir: str, output_dir: str,
                 bt_config: Optional[BacktestConfig] = None):
        self.data_dir   = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.bt_config  = bt_config

    def run_all(self) -> list[BacktestMetrics]:
        csv_files = sorted(self.data_dir.glob("*.csv"))
        if not csv_files:
            bt_log.warning(f"No CSVs in {self.data_dir}")
            return []

        results = []
        for csv_path in csv_files:
            instrument = self._infer(csv_path.stem)
            cfg = BacktestConfig(**(vars(self.bt_config) if self.bt_config else {}))
            cfg.instrument = instrument
            cfg.pip_size   = self.INSTRUMENT_PIP.get(instrument, 0.0001)

            try:
                loader = CandleLoader(str(csv_path), instrument)
                runner = BacktestRunner(cfg)
                m = runner.run(
                    loader.stream(), loader.count(),
                    str(self.output_dir / instrument),
                )
                results.append(m)
            except Exception as e:
                bt_log.error(f"{instrument} failed: {e}")
                import traceback; traceback.print_exc()

        self._write_aggregate(results)
        return results

    def _infer(self, stem: str) -> str:
        u = stem.upper()
        for k in self.INSTRUMENT_PIP:
            if k in u:
                return k
        import re
        m = re.search(r"([A-Z]{6})", u)
        return m.group(1) if m else u.split("_")[0]

    def _write_aggregate(self, results: list[BacktestMetrics]) -> None:
        p = self.output_dir / "aggregate_summary.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        agg = {
            "instruments":   len(results),
            "total_trades":  sum(r.approved_trades for r in results),
            "total_pnl_net": round(sum(r.total_pnl_rr_net for r in results), 4),
            "avg_win_rate":  round(sum(r.win_rate for r in results) / max(len(results), 1), 4),
            "per_instrument": [r.to_dict() for r in results],
        }
        with open(p, "w") as f:
            json.dump(agg, f, indent=2)
        bt_log.info(f"Aggregate → {p}")
def log_v2_run(stats: dict, meta: dict):
    from pathlib import Path
    import csv
    from datetime import datetime

    log_dir = Path("results/tracking")
    log_dir.mkdir(parents=True, exist_ok=True)

    file_path = log_dir / "v2_runs.csv"

    row = {
        "timestamp": datetime.utcnow().isoformat(),
        "instrument": meta.get("instrument"),

        # core
        "trades": stats.get("total_trades"),
        "win_rate": stats.get("win_rate"),
        "avg_rr": stats.get("avg_rr"),
        "total_pnl_r": stats.get("total_pnl_r"),
        "max_dd_r": stats.get("max_drawdown_r"),
        "profit_factor": stats.get("profit_factor"),

        # intelligence
        "fusion_avg": stats.get("fusion_avg"),
        "gaussian_avg": stats.get("gaussian_avg"),
        "model_divergence_avg": stats.get("model_divergence_avg"),

        # decision
        "accepted_trades": stats.get("accepted"),
        "rejected_trades": stats.get("rejected"),
        "rejection_rate": stats.get("rejection_rate"),

        # learning
        "neural_active": meta.get("neural_active"),
        "model_version": meta.get("model_version"),
    }

    write_header = not file_path.exists()

    with open(file_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="CRT Backtest Harness v2")
    ap.add_argument("--csv",         required=True)
    ap.add_argument("--instrument",  default="AUTO")
    ap.add_argument("--output",      default="results")
    ap.add_argument("--htf",         type=int,   default=4)
    ap.add_argument("--warmup",      type=int,   default=30)
    ap.add_argument("--capital",     type=float, default=100_000.0)
    ap.add_argument("--risk-pct",    type=float, default=0.01)
    ap.add_argument("--spread",      type=float, default=0.0002)
    ap.add_argument("--no-slip",     action="store_true")
    ap.add_argument("--no-gap-reset",action="store_true")
    ap.add_argument("--sweep-age",   type=int,   default=20)
    ap.add_argument("--decay",       type=float, default=0.10)
    ap.add_argument("--threshold",   type=float, default=0.75)
    args = ap.parse_args()

    # Resolve instrument first so ConfigBuilder can pick the correct market profile.
    resolved_instrument = (
        args.instrument if args.instrument not in ("AUTO", "ALL")
        else Path(args.csv).stem.upper()
    )

    # CLI overrides layer on top of the router base (Forex or Crypto).
    cli_overrides = {
        "max_sweep_age_candles": args.sweep_age,
        "score_decay_lambda":    args.decay,
        "score_threshold":       args.threshold,
    }
    crt_cfg = ConfigBuilder.build(resolved_instrument, overrides=cli_overrides)

    cfg = BacktestConfig(
        htf_candles_per_range=args.htf,
        warmup_candles=args.warmup,
        initial_capital=args.capital,
        risk_pct_per_trade=args.risk_pct,
        simulated_spread_pct=args.spread,
        slippage_enabled=not args.no_slip,
        gap_reset_enabled=not args.no_gap_reset,
        crt_config=crt_cfg,
    )

    csv_path = Path(args.csv)
    if csv_path.is_dir() or args.instrument.upper() == "ALL":
        MultiInstrumentRunner(str(csv_path), args.output, cfg).run_all()
    else:
        cfg.instrument = args.instrument if args.instrument != "AUTO" \
                         else csv_path.stem.upper()
        cfg.pip_size   = MultiInstrumentRunner.INSTRUMENT_PIP.get(cfg.instrument, 0.0001)
        loader = CandleLoader(str(csv_path), cfg.instrument)
        BacktestRunner(cfg).run(loader.stream(), loader.count(), args.output)


if __name__ == "__main__":
    main()
