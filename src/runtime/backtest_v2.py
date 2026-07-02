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
    python backtest_v2.py --csv data/EURUSD_M15.csv --instrument EURUSD
    python backtest_v2.py --csv data/ --instrument ALL --output results/
    python backtest_v2.py --csv data/EURUSD_M15.csv --capital 100000 --risk-pct 0.01
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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # top-level so tests can monkeypatch backtest_v2.pd

from features.feature_schema import CANONICAL_FEATURES
from data_ingestion.ohlcv_schema import (
    DatasetIntegrityError,
    OHLCV_DATE_FORMATS,
    parse_ohlcv_timestamp,
    require_ohlcv_columns,
    require_unique_ohlcv_headers,
    validate_ohlcv_row,
)
from data_ingestion.dataset_integrity import (
    DatasetDecision,
    validate_dataset,
    validate_universe,
)
from utils.console_safe import SafeStreamHandler, safe_print

# Top-level class references so tests can monkeypatch backtest_v2.FeaturePipeline etc.
try:
    from features.feature_pipeline import FeaturePipeline
except Exception:
    FeaturePipeline = None  # type: ignore[assignment,misc]

try:
    from bitnet.bitnet_inference import BitNetModel
except Exception:
    BitNetModel = None  # type: ignore[assignment,misc]

try:
    from core.engine_runner import EngineRunner
except Exception:
    EngineRunner = None  # type: ignore[assignment,misc]


from config_layer.crt_engine_v2 import (
    Candle, CRTConfig, CRTEngine, CRTState, Direction,
    EngineState, Range, Trade,
)
from config_layer.production_config import PROD_VERSION, load_prod_config_from_registry
from config_layer.config_builder import ConfigBuilder

# ─────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────

for _noisy in [
    "CRT.RangeDetector", "CRT.StateMachine", "CRT.UltronRisk",
    "CRT.Execution", "CRT.Reset", "CRT.EventLog", "CRT.Orchestrator",
]:
    logging.getLogger(_noisy).setLevel(logging.WARNING)

bt_log = logging.getLogger("CRT.Backtest")
bt_log.setLevel(logging.DEBUG)
if not bt_log.handlers:
    _h = SafeStreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s [BT] %(message)s", "%H:%M:%S"))
    bt_log.addHandler(_h)
# ── Persistent file handler so diagnostics survive subprocess stdout swallowing ──
try:
    import pathlib as _pl
    _bt_log_dir = _pl.Path(__file__).resolve().parent.parent.parent / "logs"
    _bt_log_dir.mkdir(parents=True, exist_ok=True)
    _bt_fh = logging.FileHandler(_bt_log_dir / "backtest_debug.log", encoding="utf-8", mode="a")
    _bt_fh.setLevel(logging.DEBUG)
    _bt_fh.setFormatter(logging.Formatter(
        "%(asctime)s [BT] [%(levelname)s] %(message)s", "%Y-%m-%dT%H:%M:%S"
    ))
    bt_log.addHandler(_bt_fh)
except Exception:
    pass  # never block startup


# ─────────────────────────────────────────────────────────────────
# ROI / RETURNS TELEMETRY — additive, measure-only (never gated)
# ─────────────────────────────────────────────────────────────────
_ROI_DEFAULTS = {
    "profit_factor_inf_sentinel": 999.0,   # PF when there are no losing trades
}


# ─────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────

@dataclass
class BacktestConfig:
    # ── HTF ──────────────────────────────────────────────────────
    htf_candles_per_range:   int

    # ── [G1] Slippage model ───────────────────────────────────────
    slippage_enabled:        bool
    slippage_atr_fraction:   float   # slip ~ uniform(0, N×ATR)
    slippage_seed:           int     # reproducible (set 0 for random)

    # ── [G2] Spread ───────────────────────────────────────────────
    simulated_spread_pct:    float

    # ── [G3] Capital curve ────────────────────────────────────────
    initial_capital:         float
    risk_pct_per_trade:      float
    use_compounding:         bool

    # ── [G4] Session gap reset ────────────────────────────────────
    gap_reset_enabled:       bool
    gap_reset_minutes:       int

    # ── Event log flush ───────────────────────────────────────────
    event_flush_every:       int

    # ── Warmup ────────────────────────────────────────────────────
    warmup_candles:          int

    # ── Instrument metadata (instance-specific, not from global config) ──────
    instrument:              str            = "UNKNOWN"
    pip_size:                float          = 0.0001

    # ── Engine config override (instance-specific) ────────────────
    crt_config: Optional[CRTConfig] = None

    # ── Scorer mode ───────────────────────────────────────────────
    scorer_mode: str = "calibrated"   # "calibrated" | "static"

    @classmethod
    def from_prod_config(
        cls,
        instrument: str = "UNKNOWN",
        pip_size: float = 0.0001,
        crt_config: Optional[CRTConfig] = None,
    ) -> "BacktestConfig":
        """
        Build a BacktestConfig from the production JSON 'backtest' section.

        All numeric / bool fields are loaded from
        configs/production/v1_multi_2026_03.json under 'backtest'.
        Raises RuntimeError if the file or section is missing.
        Raises KeyError if any required key is absent.
        """
        import sys, os
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from config_layer.production_config import get_prod_section

        cfg = get_prod_section("backtest")

        required_keys = (
            "htf_candles_per_range", "warmup_candles",
            "slippage_enabled", "slippage_atr_fraction", "slippage_seed",
            "simulated_spread_pct",
            "initial_capital", "risk_pct_per_trade", "use_compounding",
            "gap_reset_enabled", "gap_reset_minutes",
            "event_flush_every",
        )
        missing = [k for k in required_keys if k not in cfg]
        if missing:
            raise KeyError(
                f"BacktestConfig: missing required keys in 'backtest' section: {missing}. "
                "Add them to configs/production/v1_multi_2026_03.json."
            )

        return cls(
            htf_candles_per_range = int(cfg["htf_candles_per_range"]),
            warmup_candles        = int(cfg["warmup_candles"]),
            slippage_enabled      = bool(cfg["slippage_enabled"]),
            slippage_atr_fraction = float(cfg["slippage_atr_fraction"]),
            slippage_seed         = int(cfg["slippage_seed"]),
            simulated_spread_pct  = float(cfg["simulated_spread_pct"]),
            initial_capital       = float(cfg["initial_capital"]),
            risk_pct_per_trade    = float(cfg["risk_pct_per_trade"]),
            use_compounding       = bool(cfg["use_compounding"]),
            gap_reset_enabled     = bool(cfg["gap_reset_enabled"]),
            gap_reset_minutes     = int(cfg["gap_reset_minutes"]),
            event_flush_every     = int(cfg["event_flush_every"]),
            instrument            = instrument,
            pip_size              = pip_size,
            crt_config            = crt_config,
        )


# ─────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────

@dataclass
class TradePathStats:
    """[Metrics V2 — Layer A] Raw per-trade PATH observations (within-trade).

    MFE/MAE are entry-relative price excursions tracked over bars strictly AFTER
    entry (including the exit bar), updated from each streaming bar's high/low —
    deliberately identical to `research.measurement.forward_walk` so that the
    frozen forward_walk is the verifying ORACLE for this hot-loop tracking.

    OBSERVATION-ONLY: nothing here feeds the exit/SL/TP decision. Derived fields
    (capture / giveback / efficiency) are filled once at close from the realized
    RAW move (same entry_raw basis as MFE). Kept on its own dataclass (decision 5)
    so TradeRecord — the hot-loop object — does not become a field dump.
    """
    # ── observed during the trade (raw, entry-relative; price units) ──
    mfe_price:      float = 0.0   # max favorable excursion vs entry_raw (>= 0)
    mae_price:      float = 0.0   # max adverse excursion  vs entry_raw (<= 0)
    bars_to_peak:   int   = 0     # 1-based post-entry bar at which MFE was set
    bars_to_trough: int   = 0     # 1-based post-entry bar at which MAE was set
    bars_observed:  int   = 0     # post-entry bars seen (duration sanity check)
    # ── derived at close (raw basis: same entry_raw the MFE uses) ──
    mfe_rr:             float = 0.0
    mae_rr:             float = 0.0   # <= 0
    capture_ratio:      Optional[float] = None  # realized_raw / mfe  (None if mfe<=0)
    giveback:           Optional[float] = None  # (mfe - realized_raw)/mfe (None if mfe<=0)
    time_efficiency:    Optional[float] = None  # bars_to_peak / duration  (None if dur<=0)
    adverse_efficiency: Optional[float] = None  # |mae_rr| / mfe_rr (None if mfe_rr<=0)

    def to_dict(self) -> dict:
        return {
            "mfe_price":      round(self.mfe_price, 8),
            "mae_price":      round(self.mae_price, 8),
            "bars_to_peak":   self.bars_to_peak,
            "bars_to_trough": self.bars_to_trough,
            "bars_observed":  self.bars_observed,
            "mfe_rr":         round(self.mfe_rr, 6),
            "mae_rr":         round(self.mae_rr, 6),
            "capture_ratio":      None if self.capture_ratio is None else round(self.capture_ratio, 6),
            "giveback":           None if self.giveback is None else round(self.giveback, 6),
            "time_efficiency":    None if self.time_efficiency is None else round(self.time_efficiency, 6),
            "adverse_efficiency": None if self.adverse_efficiency is None else round(self.adverse_efficiency, 6),
        }


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
    features: dict = field(default_factory=dict)
    # ── [Live Audit] Universe-B execution metrics from CRTEngine.get_live_metrics() ──
    # These are the exact indicator values present at the moment of entry — not
    # post-hoc batch features.  live_atr cross-checks SL/TP sizing; cached_*
    # fields are the decision inputs that passed UltronRiskEngine.approve().
    live_atr:               float = 0.0   # raw price-unit ATR used for SL/TP
    live_ema_fast:          float = 0.0   # EMA-2 (soft-confirmation momentum)
    live_ema_slow:          float = 0.0   # EMA-5 (soft-confirmation momentum)
    cached_retest_depth:    float = 0.0   # retrace depth at RETEST confirmation
    cached_body_ratio:      float = 0.0   # displacement candle body_ratio
    cached_disp_strength:   float = 0.0   # displacement / ATR ratio
    cached_session:         str   = ""    # session label recorded at RETEST
    cached_double_sweep:    bool  = False # double-sweep confirmed at RETEST
    # ── [BitNet adaptive threshold] score that led to this trade's approval ──
    # Populated from CRTEngine.state.bitnet_main_score at on_trade_opened time.
    # Used by BitNetThresholdAdapter to fit per-instrument per-regime thresholds
    # against (score, exit_reason) outcomes. Defaults preserve old-record loads.
    bitnet_score_at_entry:    float = 0.0
    bitnet_decision_at_entry: str   = ""   # "ACCEPT" | "REJECT" | "" (not evaluated)
    config_version:         str   = field(default_factory=lambda: PROD_VERSION)
    # ── [Phase D] Strategy memory fields ─────────────────────────────────────
    # Populated at trade close by BacktestRunner._on_trade_close().
    # winning_strategy_id: strategy that produced the top signal (from OrchestratorResult).
    # crt_path: compact CRT transition codes at decision time (["S","D","T","X"]).
    # pattern_hash: 16-char SHA-256 fingerprint for cluster-level expectancy lookup.
    winning_strategy_id: str       = ""
    crt_path:            list      = field(default_factory=list)
    pattern_hash:        str       = ""
    # [Phase 2b] Shadow displacement flag — True if trade entered via SHADOW_PENDING path
    shadow_used:         bool      = False
    # [Metrics V2 — Layer A] within-trade path observations (MFE/MAE/efficiency).
    # Default factory keeps old-record loads valid; populated by TradeJournal.
    path:                TradePathStats = field(default_factory=TradePathStats)

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

        return {
            "session_breakdown":     session_wr,
            "day_of_week_breakdown": dow_wr,
            "best_hour_utc":         best_hour,
            "worst_hour_utc":        worst_hour,
            "rolling_win_rate":      regime,
            "loss_clustering_score": round(clustering_score, 4),
            "score_outcome_corr":    round(score_corr, 4),
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
        scores   = [t.risk_score for t in trades]
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
    # Single source of truth lives in ohlcv_schema.OHLCV_DATE_FORMATS; kept as a
    # class attribute for backward compatibility with callers/tests.
    DATE_FORMATS = list(OHLCV_DATE_FORMATS)
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
        # Delegate to the shared parser (single source of truth).
        return parse_ohlcv_timestamp(raw)

    def stream(self) -> Iterator[Candle]:
        with open(self.filepath, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            headers = [h.strip() for h in next(reader)]
            # L1 — reject duplicate column headers (e.g. "... volume volume"),
            # which would silently shadow the real column under set-based checks.
            require_unique_ohlcv_headers(
                headers, source=f"Historical dataset {self.filepath}"
            )
            ts_col   = self._detect_column(headers, "timestamp")
            date_col = self._detect_column(headers, "date")
            time_col = self._detect_column(headers, "time_col")
            o_col = self._detect_column(headers, "open")
            h_col = self._detect_column(headers, "high")
            l_col = self._detect_column(headers, "low")
            c_col = self._detect_column(headers, "close")
            v_col = self._detect_column(headers, "volume")

            use_split = (ts_col is None and date_col is not None and time_col is not None)
            # Phase 1 — all six mandatory columns must resolve to a header (a
            # split date+time pair satisfies "timestamp"). volume is mandatory.
            resolved = set()
            if ts_col is not None or use_split:
                resolved.add("timestamp")
            for field_name, col in (("open", o_col), ("high", h_col),
                                    ("low", l_col), ("close", c_col), ("volume", v_col)):
                if col is not None:
                    resolved.add(field_name)
            require_ohlcv_columns(resolved, source=f"Historical dataset {self.filepath}")

            prev_ts: Optional[datetime] = None
            for line_num, row in enumerate(reader, start=2):
                if not row or all(not cell.strip() for cell in row):
                    continue  # skip blank/EOF lines (not a data fallback)
                raw_ts = (row[date_col].strip() + " " + row[time_col].strip()
                          if use_split else row[ts_col].strip())
                ts  = self._parse_timestamp(raw_ts)
                # L2 inline backstop — sequence integrity. The full pre-flight
                # gate (dataset_integrity.validate_dataset) does the complete
                # analysis; this always-on guard catches duplicate/out-of-order
                # timestamps even if a caller streams a file without pre-flight.
                if prev_ts is not None:
                    if ts == prev_ts:
                        raise DatasetIntegrityError(
                            f"Duplicate timestamp {ts.isoformat()} (line {line_num}) "
                            f"in {self.filepath}"
                        )
                    if ts < prev_ts:
                        raise ValueError(
                            f"Out-of-order timestamp {ts.isoformat()} < "
                            f"{prev_ts.isoformat()} (line {line_num}) in {self.filepath}"
                        )
                prev_ts = ts
                o   = float(row[o_col]); h = float(row[h_col])
                l   = float(row[l_col]); c = float(row[c_col])
                vol = float(row[v_col])
                # Phase 2 — value integrity: non-negative volume, candle
                # consistency. Malformed rows now RAISE (no silent skip) so a
                # corrupt dataset fails fast instead of yielding a truncated
                # candle stream.
                validate_ohlcv_row(
                    o, h, l, c, vol,
                    source=f"Historical dataset {self.filepath}",
                    line=line_num,
                )
                yield Candle(timestamp=ts, open=o, high=h, low=l, close=c, volume=vol)

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

    def observe_open_bar(self, candle: "Candle") -> None:
        """[Metrics V2 — Layer A] Update the open trade's path stats from ONE bar.

        OBSERVATION-ONLY — must never read or alter exit/SL/TP state (the engine
        owns the governing intrabar_fixed exit). No-lookahead: uses only this bar's
        high/low. The caller invokes it once per candle for bars strictly after
        entry (the entry bar opens later in its own iteration) and including the
        exit bar (which closes later in its iteration) — so MFE/MAE span the exact
        same bar range as research.measurement.forward_walk (the oracle).
        """
        rec = self.open_trade
        if rec is None:
            return
        p = rec.path
        p.bars_observed += 1
        entry = rec.entry_price_raw
        if rec.direction == "LONG":
            fav = candle.high - entry
            adv = candle.low - entry
        else:
            fav = entry - candle.low
            adv = entry - candle.high
        if fav > p.mfe_price:               # floored at 0 (mfe_price starts 0.0)
            p.mfe_price = fav
            p.bars_to_peak = p.bars_observed
        if adv < p.mae_price:               # capped at 0 (mae_price starts 0.0)
            p.mae_price = adv
            p.bars_to_trough = p.bars_observed

    def on_trade_opened(
        self, trade: Trade, candle: Candle, candle_index: int,
        risk_score: float, state_path: list, htf_id: str,
        session: str, atr: float, spread_half: float, feature_vector,
        live_metrics: dict = None,   # Universe-B live state from CRTEngine.get_live_metrics()
        bitnet_score: float = 0.0,
        bitnet_decision: str = "",
        shadow_used: bool = False,   # [Phase 2b] True if trade came via SHADOW_PENDING path
    ) -> None:
        # [G1+G2] Realistic entry fill from a single slippage draw.
        # NOTE (trust-layer F3, 2026-06-10): the prior code called
        # compute_fill_prices() here and discarded all four results, then re-drew
        # entry_slip — burning an extra entry+exit draw per trade-open and leaving
        # the used entry/exit slips unpaired. Exit slippage is drawn independently
        # at close time in on_trade_closed(), so entry-open consumes exactly one
        # entry_slip draw. Deterministic given slippage_seed; this changes the RNG
        # draw sequence (and thus the ledger) — see backtest-trust-audit-2026-06-10.
        feature_map = {name: feature_vector[i] for i, name in enumerate(CANONICAL_FEATURES)}
        e_slip = self.slip.entry_slip(atr, trade.direction)
        entry_fill = trade.entry_price + e_slip + spread_half

        # [FIX-SL] Dynamic SL: if slippage eats into the SL distance so that
        # abs(entry_fill - sl_price) < 20% ATR (matching sl_atr_buffer in CRT
        # engine config), extend the SL outward from entry_fill to restore the
        # minimum distance.  This prevents near-zero SL → runaway position size.
        _min_sl_dist = 0.2 * atr
        _raw_sl_dist = abs(entry_fill - trade.sl_price)
        if atr > 0 and _raw_sl_dist < _min_sl_dist:
            effective_sl = (
                entry_fill - _min_sl_dist
                if trade.direction == Direction.LONG
                else entry_fill + _min_sl_dist
            )
            self.log.warning(
                "SL adjusted %.6f→%.6f (fill=%.6f, sl_dist=%.8f < min=%.8f)",
                trade.sl_price, effective_sl, entry_fill, _raw_sl_dist, _min_sl_dist,
            )
        else:
            effective_sl = trade.sl_price

        # [G3] Position size from capital curve using effective (fill-adjusted) SL
        size = self.cap.position_size(entry_fill, effective_sl, self.pip_size)

        lm = live_metrics or {}
        self.open_trade = TradeRecord(
            trade_id              = trade.id,
            instrument            = self.instrument,
            direction             = trade.direction.value,
            entry_price_raw       = trade.entry_price,
            sl_price              = effective_sl,  # fill-adjusted; used for RR calc
            tp1_price             = trade.tp1_price,
            tp2_price             = trade.tp2_price,
            entry_price_fill      = entry_fill,
            opened_at             = candle.timestamp,
            candle_open           = candle_index,
            risk_score            = risk_score,
            risk_pct              = trade.risk_pct,
            state_path            = state_path[:],
            htf_id                = htf_id,
            session               = session,
            capital_before        = self.cap.current_capital,
            position_size         = size,
            week_of_year          = candle.timestamp.isocalendar()[1],
            day_of_week           = candle.timestamp.weekday(),
            hour_of_day           = candle.timestamp.hour,
            features              = feature_map,
            # ── Universe-B live audit fields ─────────────────────────────────
            live_atr              = float(lm.get("live_atr",             0.0)),
            live_ema_fast         = float(lm.get("live_ema_fast",        0.0)),
            live_ema_slow         = float(lm.get("live_ema_slow",        0.0)),
            cached_retest_depth   = float(lm.get("cached_retest_depth",  0.0)),
            cached_body_ratio     = float(lm.get("cached_body_ratio",    0.0)),
            cached_disp_strength  = float(lm.get("cached_disp_strength", 0.0)),
            cached_session        = str(lm.get("cached_session",         "")),
            cached_double_sweep   = bool(lm.get("cached_double_sweep",   False)),
            bitnet_score_at_entry    = float(bitnet_score),
            bitnet_decision_at_entry = str(bitnet_decision),
            shadow_used              = shadow_used,
        )

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

        # Pip calculations
        price_move_raw = (exit_price_raw - rec.entry_price_raw) if direction == Direction.LONG \
                         else (rec.entry_price_raw - exit_price_raw)
        price_move_net = (exit_fill - rec.entry_price_fill) if direction == Direction.LONG \
                         else (rec.entry_price_fill - exit_fill)

        rec.pnl_pips_raw  = price_move_raw / self.pip_size
        rec.pnl_pips_net  = price_move_net / self.pip_size

        risk_pips = abs(rec.entry_price_fill - rec.sl_price) / self.pip_size
        rec.pnl_rr_raw = (price_move_raw / self.pip_size) / risk_pips if risk_pips > 0 else 0.0
        rec.pnl_rr_net = (price_move_net / self.pip_size) / risk_pips if risk_pips > 0 else 0.0

        # Cost breakdown
        rec.slippage_pips = abs(rec.entry_price_fill - rec.entry_price_raw - spread_half) / self.pip_size \
                            + abs(x_slip) / self.pip_size
        rec.spread_pips   = (spread_half * 2) / self.pip_size

        # [Metrics V2 — Layer A→close] derive path efficiency from observed MFE/MAE.
        # Everything stays on the RAW (entry_price_raw) basis the MFE was tracked on,
        # so capture/giveback are consistent with the observed excursion and the
        # forward_walk oracle. realized_raw = price_move_raw (entry_raw-relative).
        p = rec.path
        risk_price_raw = abs(rec.entry_price_raw - rec.sl_price)
        if risk_price_raw > 0:
            p.mfe_rr = p.mfe_price / risk_price_raw
            p.mae_rr = p.mae_price / risk_price_raw
        if p.mfe_price > 0:
            p.capture_ratio = price_move_raw / p.mfe_price
            p.giveback      = (p.mfe_price - price_move_raw) / p.mfe_price
        _dur = rec.duration_candles
        if _dur > 0:
            p.time_efficiency = p.bars_to_peak / _dur
        if p.mfe_rr > 0:
            p.adverse_efficiency = abs(p.mae_rr) / p.mfe_rr

        # [G3] Apply to capital curve
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
        rows = []
        for r in self.closed:
            row = {
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
                "risk_score":        round(r.risk_score, 4),
                "session":           r.session,
                "day_of_week":       r.day_of_week,
                "hour_of_day":       r.hour_of_day,
                "htf_id":            r.htf_id,
                "candle_idx":        r.candle_open,
            }
            # ── Universe-A canonical features (35-dim, timestamp-keyed batch) ──
            row.update(r.features)

            # ── [Zero-Feature WARNING] ────────────────────────────────────────
            # If the timestamp-keyed batch lookup missed (wrong ts format or
            # CSV column mismatch), every canonical feature will be 0.0.
            # Detecting this here surfaces the problem in the log rather than
            # silently writing a useless all-zero row.
            _zero_count = sum(1 for v in r.features.values() if v == 0.0)
            if _zero_count > len(r.features) // 2:
                self.log.warning(
                    "ZERO FEATURES | trade=%s candle_open=%d "
                    "zero_count=%d/%d — batch timestamp lookup likely missed. "
                    "live_atr=%.6g (should be non-zero if engine is healthy).",
                    r.trade_id, r.candle_open,
                    _zero_count, len(r.features),
                    r.live_atr,
                )

            # ── Universe-B live audit columns (always from engine state) ─────
            # These are guaranteed non-zero whenever a trade fires because they
            # come directly from CRTEngine.get_live_metrics(), not a batch array.
            # live_atr lets you cross-check: sl_distance ≈ sl_atr_buffer × live_atr.
            row["live_atr"]             = round(r.live_atr,             8)
            row["live_ema_fast"]        = round(r.live_ema_fast,        8)
            row["live_ema_slow"]        = round(r.live_ema_slow,        8)
            row["cached_retest_depth"]  = round(r.cached_retest_depth,  6)
            row["cached_body_ratio"]    = round(r.cached_body_ratio,    6)
            row["cached_disp_strength"] = round(r.cached_disp_strength, 6)
            row["cached_session"]       = r.cached_session
            row["cached_double_sweep"]  = int(r.cached_double_sweep)
            # ── BitNet adaptive-threshold audit ──────────────────────────────
            row["bitnet_score_at_entry"]    = round(r.bitnet_score_at_entry, 6)
            row["bitnet_decision_at_entry"] = r.bitnet_decision_at_entry
            row["config_version"]       = r.config_version
            row["shadow_used"]          = int(r.shadow_used)
            rows.append(row)
        return rows


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
    hard_drift_pauses:     int   = 0

    # ── ROI / returns telemetry (additive, measure-only) ──────────────────────
    gross_win_rr:          float = 0.0
    gross_loss_rr:         float = 0.0   # negative (sum of losing pnl_rr_net)
    profit_factor:         float = 0.0
    total_return_pct:      float = 0.0
    annualized_return_pct: float = 0.0
    return_to_max_dd:      float = 0.0
    trades_per_month:      float = 0.0   # span-derived frequency (Goal Layer)
    funnel_counts:         dict  = field(default_factory=dict)   # CRT-state funnel

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
            # ── ROI / returns telemetry (additive, measure-only) ──────────────
            "total_return_pct":      round(self.total_return_pct, 6),
            "annualized_return_pct": round(self.annualized_return_pct, 6),
            "profit_factor":         round(self.profit_factor, 4),
            "return_to_max_dd":      round(self.return_to_max_dd, 4),
            "trades_per_month":      round(self.trades_per_month, 4),
            "gross_win_rr":          round(self.gross_win_rr, 4),
            "gross_loss_rr":         round(self.gross_loss_rr, 4),
            "funnel_counts":         dict(self.funnel_counts),
            "config_version":      PROD_VERSION,
        }


# ── [Metrics V2 — Layer B] pure aggregation helpers (mirrored by metrics_oracle) ──
# These define the EXACT math the independent oracle must reproduce for parity, so
# keep them simple and dependency-free. _v2_percentile uses numpy-style linear
# interpolation on the sorted sample (rank = p/100*(n-1)).
def _v2_mean(xs: list[float]) -> Optional[float]:
    return sum(xs) / len(xs) if xs else None


def _v2_percentile(xs: list[float], p: float) -> Optional[float]:
    if not xs:
        return None
    s = sorted(xs)
    if len(s) == 1:
        return float(s[0])
    rank = (p / 100.0) * (len(s) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(s) - 1)
    frac = rank - lo
    return float(s[lo] + (s[hi] - s[lo]) * frac)


def _planned_rr(t) -> Optional[float]:
    """Planned reward:risk from the entry/SL/TP1 geometry (direction-agnostic via
    abs). None when the risk leg is degenerate."""
    risk = abs(t.entry_price_raw - t.sl_price)
    if risk <= 0:
        return None
    return abs(t.tp1_price - t.entry_price_raw) / risk


def _top_n_contribution_pct(rrs: list[float], n: int = 5) -> Optional[float]:
    """Share of GROSS winning R contributed by the top-n winners (concentration)."""
    wins = sorted((r for r in rrs if r > 0), reverse=True)
    gross = sum(wins)
    if gross <= 0:
        return None
    return sum(wins[:n]) / gross


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
        m.funnel_counts = dict(state_counts)   # CRT-state funnel for sweep attribution

        if not trades:
            self._roi_block(m, trades, capital, total_candles)   # ROI on zero-trade run
            return m

        m.wins           = sum(1 for t in trades if t.pnl_rr_net > 0)
        m.losses         = sum(1 for t in trades if t.pnl_rr_net <= 0)
        m.tp1_hits       = sum(1 for t in trades if t.exit_reason in ("TP1", "TP2"))
        m.tp2_hits       = sum(1 for t in trades if t.exit_reason == "TP2")
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
        self._roi_block(m, trades, capital, total_candles)   # ROI / returns telemetry
        self._metrics_v2_block(m, trades)                    # [Metrics V2 — Layer B]
        return m

    def _roi_block(self, m: BacktestMetrics, trades: list,
                   cap: "CapitalCurve", total_candles: int) -> None:
        """Post-hoc ROI / returns telemetry. Additive, measure-only — never gated.

        Reads only t.pnl_rr_net per trade. PF uses gross win / |gross loss| in R;
        when there are no losses the inf-sentinel is used. annualized_return_pct is
        span-aware (M15 candles → years), so IS/OOS rates are comparable.
        """
        m.gross_win_rr  = sum(t.pnl_rr_net for t in trades if t.pnl_rr_net > 0)
        m.gross_loss_rr = sum(t.pnl_rr_net for t in trades if t.pnl_rr_net <= 0)  # ≤0
        if m.gross_loss_rr < 0:
            m.profit_factor = round(m.gross_win_rr / abs(m.gross_loss_rr), 4)
        else:
            m.profit_factor = _ROI_DEFAULTS["profit_factor_inf_sentinel"]

        m.total_return_pct = cap.total_return_pct
        max_dd = cap.max_drawdown_pct
        m.return_to_max_dd = round(m.total_return_pct / max_dd, 6) if max_dd > 0 else 0.0

        # span-aware CAGR: years = total_candles × 15 min / minutes-in-a-year
        years = (total_candles * 15) / (365 * 24 * 60) if total_candles > 0 else 0.0
        if years > 0 and (1.0 + m.total_return_pct) > 0:
            m.annualized_return_pct = (1.0 + m.total_return_pct) ** (1.0 / years) - 1.0
        else:
            m.annualized_return_pct = 0.0

        # span-derived trade frequency (Goal Layer): trades / calendar-month & week
        months = years * 12.0
        weeks  = (total_candles * 15) / (7 * 24 * 60) if total_candles > 0 else 0.0
        m.trades_per_month = round(m.approved_trades / months, 6) if months > 0 else 0.0
        m.trades_per_week  = round(m.approved_trades / weeks, 6) if weeks > 0 else 0.0

        # ── Goal Layer telemetry (additive, measure-only — never gates here) ──────
        self._attach_goal_report(m)

    def _metrics_v2_block(self, m: BacktestMetrics, trades: list) -> None:
        """[Metrics V2 — Layer B] Aggregate RR / concentration / distribution /
        survival / efficiency telemetry from the closed-trade ledger. Additive,
        measure-only (mirrors _roi_block). Stored at m.distribution['metrics_v2']
        so the hot-loop dataclass stays lean (decision 5). Reproduced independently
        by metrics_oracle.metrics_v2_block for the parity gate."""
        if not trades:
            return
        rrs       = [t.pnl_rr_net for t in trades]
        planned   = [v for v in (_planned_rr(t) for t in trades) if v is not None]
        durations = [t.duration_candles for t in trades]
        # per-session counts (group by the trade's recorded session label)
        sessions: dict = defaultdict(int)
        for t in trades:
            sessions[t.session or "UNKNOWN"] += 1
        # survival / efficiency from the Layer-A path stats
        captures  = [t.path.capture_ratio for t in trades if t.path.capture_ratio is not None]
        givebacks = [t.path.giveback for t in trades if t.path.giveback is not None]
        time_eff  = [t.path.time_efficiency for t in trades if t.path.time_efficiency is not None]
        adv_eff   = [t.path.adverse_efficiency for t in trades if t.path.adverse_efficiency is not None]
        btp       = [t.path.bars_to_peak for t in trades]
        mfe_rrs   = [t.path.mfe_rr for t in trades]
        mae_rrs   = [t.path.mae_rr for t in trades]

        def _r(x):
            return None if x is None else round(x, 6)

        m.distribution["metrics_v2"] = {
            "rr": {
                "avg_realized_rr": _r(_v2_mean(rrs)),
                "avg_planned_rr":  _r(_v2_mean(planned)),
                "median_rr":       _r(_v2_percentile(rrs, 50)),
                "rr_p10":          _r(_v2_percentile(rrs, 10)),
                "rr_p50":          _r(_v2_percentile(rrs, 50)),
                "rr_p90":          _r(_v2_percentile(rrs, 90)),
            },
            "concentration": {
                "largest_winner_rr": _r(max((r for r in rrs if r > 0), default=0.0)),
                "largest_loser_rr":  _r(min((r for r in rrs if r <= 0), default=0.0)),
                "top5_win_contribution_pct": _r(_top_n_contribution_pct(rrs, 5)),
            },
            "distribution": {
                "trades_per_week":    m.trades_per_week,
                "trades_per_month":   m.trades_per_month,
                "trades_per_session": dict(sessions),
                "median_duration":    _r(_v2_percentile(durations, 50)),
            },
            "survival": {
                "median_capture_ratio": _r(_v2_percentile(captures, 50)),
                "median_giveback":      _r(_v2_percentile(givebacks, 50)),
                "median_bars_to_peak":  _r(_v2_percentile(btp, 50)),
                "mfe_rr_p50": _r(_v2_percentile(mfe_rrs, 50)),
                "mfe_rr_p90": _r(_v2_percentile(mfe_rrs, 90)),
                "mae_rr_p50": _r(_v2_percentile(mae_rrs, 50)),
                "mae_rr_p90": _r(_v2_percentile(mae_rrs, 90)),
            },
            "efficiency": {
                "median_time_efficiency":    _r(_v2_percentile(time_eff, 50)),
                "time_efficiency_p90":       _r(_v2_percentile(time_eff, 90)),
                "median_adverse_efficiency": _r(_v2_percentile(adv_eff, 50)),
            },
        }

    def _attach_goal_report(self, m: BacktestMetrics) -> None:
        """Compare measured metrics against the active GoalSpec and attach the
        report to `m.distribution["goal_report"]`. Measure-only: enforcement (if
        ever) lives in the promotion authority, never in this hot path. Failure to
        load/evaluate is non-blocking — telemetry must never break a backtest."""
        try:
            from config_layer.goal_validator import GoalValidator
            report = GoalValidator.evaluate({
                "trades_per_month": m.trades_per_month,
                "win_rate":         m.win_rate,
                "max_drawdown_pct": m.max_drawdown_pct,
                "expectancy_r":     m.avg_rr_net,   # realized E[R] in R units
                # [Metrics V2 — Phase 5] avg_rr bound = REALIZED avg RR (avg_rr_net),
                # the meaningful outcome. avg_planned_rr is emitted as advisory
                # telemetry in distribution['metrics_v2'].rr, NOT a goal bound.
                "avg_rr":           m.avg_rr_net,
            })
            m.distribution["goal_report"] = report.to_dict()
        except Exception as exc:   # pragma: no cover - telemetry must never block
            bt_log.warning("Goal report attach failed (non-blocking): %s", exc)

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
    def __init__(self, output_dir: str, instrument: str, run_id: str = None):
        self.instrument = instrument
        if run_id is None:
            from datetime import datetime
            run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
        self.run_id = run_id
        self.output_dir = Path(output_dir) / f"{run_id}_{instrument}"
        self.output_dir.mkdir(parents=True, exist_ok=True)

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
        with open(p, "w", encoding="utf-8") as f:
            json.dump(m.to_dict(), f, indent=2)
        return str(p)

    def _write_trades(self, journal: TradeJournal) -> str:
        rows = journal.to_csv_rows()
        if not rows:
            return ""
        p = self.output_dir / f"{self.instrument}_trades.csv"
        with open(p, "w", newline="", encoding="utf-8") as f:
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
# PHASE-5 SCORER STUB — injection anchor for phase5_calibration.py
# ─────────────────────────────────────────────────────────────────


# -----------------------------------------------------------------
# # [Phase-5] CALIBRATED GAUSSIAN SCORER — DYNAMIC LOADER
# Model params now live in models/gaussian_{version}.json and are loaded
# at runtime via core.model_registry.load_active_gaussian_scorer().
# The _P5_PARAMS literal and the injected scorer body are deprecated;
# phase5_calibration.py no longer writes to this file.
# -----------------------------------------------------------------

# DEPRECATED — kept empty for backwards compat with any external imports.
# Models load dynamically; see core.model_registry.GaussianScorer.
_P5_PARAMS: dict = {}


class CRTCalibratedScorer:
    """Backwards-compat shim. Delegates to core.model_registry's dynamic loader.

    Returns the active gaussian model (or NoOpScorer fallback) at construction
    time. .compute() is forwarded to the underlying scorer so callers that
    instantiate CRTCalibratedScorer() directly keep working.
    """

    def __init__(self):
        from core.model_registry import load_active_gaussian_scorer
        self._delegate = load_active_gaussian_scorer()
        self.version = getattr(self._delegate, "version", None)

    def compute(self, features, candle_idx, direction: str = "long"):
        return self._delegate.compute(features, candle_idx, direction=direction)


class CRTGaussianScorer:
    """Default no-op scorer. Replaced by CRTCalibratedScorer after phase5 --integrate."""
    def compute(self, features: dict, candle_idx: int):
        return None


# ─────────────────────────────────────────────────────────────────
# BACKTEST RUNNER v2
# ─────────────────────────────────────────────────────────────────

class BacktestRunner:
    def __init__(self, bt_config: BacktestConfig, csv_path: str = None,
                 skip_features: bool = False, overrides: dict | None = None):
        """
        skip_features=True  — skips FeaturePipeline entirely (csv_path still recorded
        but not processed).  Use for tuner workers where fitness is derived from
        metric scalars only and feature columns in _trades.csv are not needed.
        All other behaviour (candle loop, CRT engine, metrics) is unchanged.

        overrides — dict of CLI flags that were explicitly set (e.g. {"--threshold": "0.75"}).
                    Recorded in the per-run config dump for full auditability.
        """
        self.cfg      = bt_config
        self.log      = bt_log
        self.crt_cfg  = bt_config.crt_config or ConfigBuilder.build(
            bt_config.instrument or "EURUSD"
        )
        self.csv_path = csv_path
        self._overrides: dict = overrides or {}

        # Coin-level log init — creates logs/run_{RUN_ID}/{instrument}/ and
        # attaches FileHandlers to all flow loggers and engine loggers.
        # MUST run before FeaturePipeline so the very first log messages land
        # in the coin-scoped directory rather than being lost to console-only.
        from utils.logging_config import init_coin_logging, RUN_ID as _RUN_ID
        init_coin_logging(bt_config.instrument)
        from utils.sweep_trace_logger import SweepTraceLogger
        self._sweep_tracer = SweepTraceLogger(run_id=_RUN_ID, instrument=bt_config.instrument)

        self.feature_vectors = None
        self.feature_ts_to_idx: dict = {}  # timestamp → row-index in feature_vectors
        if self.csv_path and not skip_features:
            try:
                from features.feature_pipeline import FeaturePipeline
                raw_df = pd.read_csv(self.csv_path)
                # Normalise headers so FeaturePipeline always sees lowercase names
                raw_df.columns = [c.strip().lower() for c in raw_df.columns]
                # Merge split date+time columns into a single "timestamp" column
                if "timestamp" not in raw_df.columns:
                    if "date" in raw_df.columns and "time" in raw_df.columns:
                        raw_df["timestamp"] = (
                            raw_df["date"].astype(str) + " " + raw_df["time"].astype(str)
                        )
                    elif "date" in raw_df.columns:
                        raw_df["timestamp"] = raw_df["date"]
                # Fail fast on a malformed source before any feature work.
                # (FeaturePipeline re-runs full value validation internally.)
                require_ohlcv_columns(raw_df.columns, source=f"Historical dataset {self.csv_path}")
                pipeline = FeaturePipeline(raw_df)
                enriched_df, self.feature_vectors = pipeline.run()
                # Build O(1) timestamp → row-index lookup.
                # This replaces the broken candle_idx integer lookup which suffered from:
                #   (a) 1-based vs 0-based offset, and
                #   (b) NaN-warmup rows dropped by finalize() shifting every index by ~50.
                _ts_series = pd.to_datetime(enriched_df["timestamp"])
                self.feature_ts_to_idx = {
                    ts.strftime("%Y-%m-%d %H:%M:%S"): i
                    for i, ts in enumerate(_ts_series)
                }
                _sample_keys = list(self.feature_ts_to_idx.keys())[:3]
                bt_log.info(
                    "FeaturePipeline built: %d rows | first 3 ts keys: %s",
                    len(self.feature_ts_to_idx), _sample_keys,
                )
            except Exception as _fp_err:
                raise RuntimeError(
                    f"FeaturePipeline init FAILED for {self.csv_path} — "
                    f"cannot run backtest with broken feature pipeline. "
                    f"Use skip_features=True only for tuner workers that do not need feature columns. "
                    f"Root cause: {_fp_err}"
                ) from _fp_err

        # Phase 2: FeatureMonitor for drift detection in replay loop
        try:
            from features.feature_monitor import FeatureMonitor
            from config_layer.production_config import get_prod_section
            try:
                _fm_cfg = get_prod_section("feature_monitor")
            except Exception:
                _fm_cfg = {}
            # Governed drift thresholds (config: feature_monitor.soft_drift_z /
            # hard_drift_z); defaults equal the historical hardcoded literals.
            self._monitor = FeatureMonitor(
                window_size=int(_fm_cfg.get("window_size", 500)),
                soft_threshold=float(_fm_cfg.get("soft_drift_z", 2.5)),
                hard_threshold=float(_fm_cfg.get("hard_drift_z", 3.0)),
            )
            self._monitor_available = True
        except Exception as _fm_err:
            bt_log.error(
                "FeatureMonitor init FAILED — drift detection is DISABLED for this run. "
                "Root cause: %s", _fm_err
            )
            self._monitor = None
            self._monitor_available = False

        # Phase-5 scorer gate — choose based on scorer_mode
        if bt_config.scorer_mode == "static":
            self._scorer = CRTGaussianScorer()
        else:
            self._scorer = CRTCalibratedScorer()

        # Fusion JSONL — one file per run, scoped under the coin log dir
        # _RUN_ID imported above alongside init_coin_logging
        from utils.trade_logger import TradeLogger as _TradeLogger
        _run_log_dir = Path("logs") / f"run_{_RUN_ID}" / bt_config.instrument
        _run_log_dir.mkdir(parents=True, exist_ok=True)
        self._trade_logger = _TradeLogger(_run_log_dir / f"{bt_config.instrument}_fusion.jsonl")

        # M1 Part 2 — per-episode LLM log (deterministic, read-only projection)
        from utils.episode_summarizer import EpisodeSummarizer as _EpisodeSummarizer
        self._episode_summarizer = _EpisodeSummarizer(
            instrument=bt_config.instrument, run_id=_RUN_ID
        )

        # Phase C — SignalBeliefTracker lifecycle container.
        # RuntimeContext owns the BeliefRegistry; EngineRunner only reads it.
        # Isolated per BacktestRunner instance — no module-global state.
        try:
            from core.signal_belief_tracker import RuntimeContext as _RuntimeContext, BeliefRegistry as _BeliefRegistry
            from config_layer.production_config import get_prod_section as _gps
            _belief_cfg = (_gps("engine_runner") or {}).get("signal_belief", {})
            self._runtime_ctx = _RuntimeContext(
                belief_registry=_BeliefRegistry(_belief_cfg)
            )
        except Exception as _bel_err:
            bt_log.warning(
                "BeliefRegistry init FAILED — belief gate DISABLED for this run. "
                "Root cause: %s", _bel_err
            )
            self._runtime_ctx = None

        # ── StrategyOrchestrator (parallel entry families: S1-S10) ─────────────
        # Runs all 10 strategies per candle and produces consensus signal.
        # Consensus score is injected into EngineRunner context as
        # strategy_consensus_score, consumed by FusionEngine when
        # weight_strategy_consensus > 0 in production config.
        try:
            from strategies.strategy_orchestrator import StrategyOrchestrator
            self._orch = StrategyOrchestrator(
                pair=bt_config.instrument or "BNBUSDT",
                timeframe="M15",
            )
            self._orch_available = True
            bt_log.info("StrategyOrchestrator initialised for %s", bt_config.instrument)
        except Exception as _orch_err:
            bt_log.warning(
                "StrategyOrchestrator init FAILED — strategy consensus DISABLED "
                "for this run. Root cause: %s", _orch_err
            )
            self._orch = None
            self._orch_available = False
    def run(self, candle_source: Iterator[Candle], total_candles: int,
            output_dir: str = "results") -> BacktestMetrics:
        self.log.info("Production config version: %s", PROD_VERSION)

        # ── Per-run config dump ───────────────────────────────────────────────
        try:
            import dataclasses as _dc
            from utils.config_dumper import dump_config as _dump_config, _asdict_serializable
            from config_layer.production_config import get_full_config_dict, PRODUCTION_REGISTRY_DIR
            _run_id = datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")
            _source_path = (
                f"{PRODUCTION_REGISTRY_DIR}/{PROD_VERSION}.json"
            )
            _bt_params = {
                k: v for k, v in _dc.asdict(self.cfg).items()
                if k != "crt_config"  # serialised separately below
            }
            _crt_dict = _asdict_serializable(self.crt_cfg)
            _full_reg = get_full_config_dict()
            _dump_payload = {
                "mode":               "backtest",
                "config_version":     PROD_VERSION,
                "source_config_path": _source_path,
                "overrides":          self._overrides,
                "backtest_params":    _bt_params,
                "crt_engine":         _crt_dict,
                "engine_runner":      _full_reg["engine_runner"],
                "fusion_engine":      _full_reg["fusion_engine"],
                "execution_planner":  _full_reg["execution_planner"],
                "decision_engine":    _full_reg["decision_engine"],
            }
            _dump_path = _dump_config(
                _dump_payload,
                instrument=self.cfg.instrument,
                run_id=_run_id,
            )
            self.log.info("Full config dumped to: %s", _dump_path)
        except Exception as _dump_err:
            self.log.warning("Config dump skipped: %s", _dump_err)

    # Ensure vectors is a list of lists (or numpy array)
        engine  = CRTEngine(self.crt_cfg, sweep_tracer=self._sweep_tracer)
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
        last_risk_score  = 0.0
        last_session     = ""
        _is_shadow_trade = False   # [Phase 2b] reset each trade open

        # ── Phase 3 / Phase 4 config (loaded once per run) ────────────────────
        from config_layer.production_config import get_prod_section as _gps_bt
        _ep_cfg_bt = _gps_bt("execution_planner")
        _fm_cfg_bt = _gps_bt("feature_monitor")
        _partial_tp_enabled  = bool(_ep_cfg_bt.get("partial_tp_breakeven_enabled", False))
        _partial_tp_fraction = float(_ep_cfg_bt.get("partial_tp_fraction", 0.5))
        _drift_pause_enabled = bool(_fm_cfg_bt.get("drift_regime_pause_enabled", False))
        _drift_cooldown      = int(_fm_cfg_bt.get("drift_cooldown_candles", 10))

        _drift_pause_remaining = 0
        _hard_drift_pauses     = 0

        # ── Phase D — strategy memory tracking ───────────────────────────────
        # Helper defined in run() scope to capture engine/state via closure.
        # Called after every journal.on_trade_closed() that returns a record.
        # _last_strategy_id: strategy that produced the top signal for the
        #   open trade (blank in standard backtest; set by EngineRunner when
        #   strategy_id is surfaced in the result dict).
        # _last_sweep_type:  sweep_type from CRT sweep event at entry time.
        #   Used by compute_pattern_hash to avoid state-name collisions.
        _last_strategy_id: str = ""
        _last_sweep_type:  str = ""
        try:
            from utils.pattern_hasher import encode_crt_path as _enc_path, compute_pattern_hash as _comp_hash
            from config_layer.crt_engine_v2 import recent_transition_path as _recent_path
            _phase_d_available = True
        except Exception as _pd_err:
            bt_log.warning("Phase D pattern_hasher unavailable — strategy memory disabled. %s", _pd_err)
            _phase_d_available = False

        # ── EngineRunner gate (live-mode pipeline wired into backtest) ────────
        # Runs adapter → fusion → dual-engine → decision_engine on each candidate
        # trade. Enabled by default; set BACKTEST_ENGINE_GATE=0 to disable.
        _engine_runner = None
        _engine_rejected_count = 0
        if os.getenv("BACKTEST_ENGINE_GATE", "1") == "1":
            from config_layer.production_config import get_prod_section as _gps_er
            from core.engine_runner import EngineRunner as _ER
            _er_cfg = dict(_gps_er("engine_runner"))
            _er_cfg.setdefault("fusion_engine", dict(_gps_er("fusion_engine")))
            for _k, _v in dict(_gps_er("decision_engine")).items():
                _er_cfg.setdefault(_k, _v)
            _er_cfg["instrument"] = self.cfg.instrument  # instrument-aware Gaussian lookup
            _engine_runner = _ER(_er_cfg)
            self.log.info("EngineRunner gate wired into backtest path (BACKTEST_ENGINE_GATE=1)")

        self.log.info(
            f"Backtest v2 | {self.cfg.instrument} | {total_candles:,} candles | "
            f"capital={self.cfg.initial_capital:,.0f} | "
            f"slip={'ON' if self.cfg.slippage_enabled else 'OFF'} | "
            f"gap_reset={'ON' if self.cfg.gap_reset_enabled else 'OFF'}"
        )

        prev_candle: Optional[Candle] = None
        # [Phase 0b] HTF window position tracking (1-based within candles_per_range window)
        _htf_pos:       int = 0
        _prev_htf_id:   str = ""
        _htf_remaining: int = self.cfg.htf_candles_per_range
        # [Phase 1] Shadow displacement counters for counterfactual comparison
        _shadow_sweep_count:     int = 0   # SHADOW_PENDING entries (resume attempts)
        _shadow_expansion_count: int = 0   # successful SHADOW_EXPANSION_CONFIRMED
        _shadow_leak_count:      int = 0   # SHADOW_LEAK integrity events

        for candle in candle_source:
            candle_idx += 1

            if candle_idx % 5000 == 0:
                pct = candle_idx / total_candles * 100 if total_candles > 0 else 0
                self.log.info(
                    f"  {candle_idx:,}/{total_candles:,} ({pct:.0f}%) | "
                    f"trades={len(journal.closed)} cap={cap.current_capital:,.0f} "
                    f"dd={cap.drawdown_pct:.1%}"
                )

            htf.push(candle)
            # [Phase 0b] Update HTF window position counter
            if htf.current_htf_id != _prev_htf_id:
                _htf_pos       = 1
                _prev_htf_id   = htf.current_htf_id
                _htf_remaining = self.cfg.htf_candles_per_range - 1
            else:
                _htf_pos      += 1
                _htf_remaining = max(0, _htf_remaining - 1)
            engine.state.htf_remaining_candles = _htf_remaining

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

            # ── [Metrics V2 — Layer A] within-trade path observation ──
            # Observation-only: update MFE/MAE/bars-to-peak for the open trade from
            # THIS streaming bar. Placed at the top of the iteration so it runs for
            # bars strictly after entry (the entry bar opens later, below) and
            # includes the exit bar (which closes later this iteration) — matching
            # forward_walk's bar range. Never touches exit/SL/TP.
            if journal.open_trade is not None:
                journal.observe_open_bar(candle)

            # ── [G4] Gap detection ─────────────────────────────────
            gap_fired, gap_reason = gap_det.check(candle)
            if gap_fired:
                gap_resets += 1
                if journal.open_trade and engine.state.active_trade:
                    spread_half = candle.close * self.cfg.simulated_spread_pct / 2
                    _gap_closed = journal.on_trade_closed(
                        engine.state.active_trade, candle.open,
                        "GAP_RESET_CLOSE", candle, candle_idx,
                        engine.state.atr, spread_half,
                    )
                    # Phase D: attach strategy memory fields
                    if _gap_closed is not None and _phase_d_available:
                        try:
                            _gap_closed.winning_strategy_id = _last_strategy_id
                            _gap_closed.crt_path            = _enc_path(_recent_path(engine.state))
                            _gap_closed.pattern_hash        = _comp_hash(
                                _gap_closed.features, sweep_type=_last_sweep_type or None,
                            )
                        except Exception:
                            pass
                engine.sm.reset_to_range(engine.state, gap_reason, candle, engine.ev_log)
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
            curr_state = engine.state.current_state.name
            state_counts[prev_state] += 1
            if prev_state != curr_state:
                state_path.append(f"{prev_state}→{curr_state}")
                # M1 — episode summarizer: notify on every state change
                self._episode_summarizer.on_state_transition(
                    prev_state, curr_state, candle.timestamp, candle_idx
                )

            action = result.get("action", "NONE")
            # [Phase 0b] Stamp HTF position on displacement events
            if action == "DISPLACEMENT_CONFIRMED":
                engine.telemetry.on_displacement_htf_position(_htf_pos, _htf_remaining)
            # [Phase 1] Shadow displacement counters
            if action == "SHADOW_SWEEP_DETECTED":
                _shadow_sweep_count += 1
            elif action == "SHADOW_EXPANSION_CONFIRMED":
                _shadow_expansion_count += 1
            elif action == "SHADOW_LEAK":
                _shadow_leak_count += 1

            if "TRADE_OPENED" in action and engine.state.active_trade:
                last_risk_score = engine.state.risk_score.final \
                                  if engine.state.risk_score else 0.0
                last_session = self._session(candle.timestamp)
                # [Phase 2b] Capture shadow flag here; passed to journal.on_trade_opened below.
                _is_shadow_trade = engine.state._came_from_shadow
                # Timestamp-keyed lookup: immune to off-by-one and warmup-offset bugs.
                # Old code used candle_idx (1-based, counts all raw rows) to index
                # feature_vectors (0-based, NaN warmup rows already dropped+reset),
                # so the two indices were misaligned by ~50 bars AND ran OOB near EOF.
                if self.feature_vectors is not None and self.feature_ts_to_idx:
                    _ts_key = candle.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    _fv_idx = self.feature_ts_to_idx.get(_ts_key, -1)
                    # ── ONE-TIME state dump (first trade only) ─────────────────
                    if not hasattr(self, "_fv_diag_done"):
                        self._fv_diag_done = True
                        _sample_dict_keys = list(self.feature_ts_to_idx.keys())[:3]
                        _fv_shape = getattr(self.feature_vectors, "shape", len(self.feature_vectors))
                        self.log.warning(
                            "FEATURE DIAG | dict_size=%d dict_sample=%s "
                            "candle_ts_key=%r fv_idx=%d fv_shape=%s",
                            len(self.feature_ts_to_idx), _sample_dict_keys,
                            _ts_key, _fv_idx, _fv_shape,
                        )
                    if _fv_idx < 0:
                        if not hasattr(self, "_ts_miss_count"):
                            self._ts_miss_count = 0
                        self._ts_miss_count += 1
                        if self._ts_miss_count <= 3:
                            _sample = list(self.feature_ts_to_idx.keys())[:1]
                            self.log.warning(
                                "Feature lookup MISS #%d: candle_ts=%r not in dict "
                                "(dict sample key=%r) — check CSV timestamp format.",
                                self._ts_miss_count, _ts_key,
                                _sample[0] if _sample else "empty",
                            )
                    feature_vector = (
                        self.feature_vectors[_fv_idx].tolist()
                        if _fv_idx >= 0
                        else [0.0] * len(CANONICAL_FEATURES)
                    )
                else:
                    # No pipeline data — log once so we know which branch we're in
                    if not hasattr(self, "_fv_none_logged"):
                        self._fv_none_logged = True
                        self.log.warning(
                            "FEATURE DIAG | feature_vectors=%s ts_to_idx_len=%d — "
                            "batch features will be all 0.0 for all trades.",
                            self.feature_vectors is not None,
                            len(self.feature_ts_to_idx),
                        )
                    feature_vector = [0.0] * len(CANONICAL_FEATURES)

                # ── Phase-5 scorer gate ────────────────────────────────────
                # Rejects trades whose predicted win-probability is below 0.35.
                # No-op while self._scorer is CRTGaussianScorer (returns None).
                # Active once swapped to CRTCalibratedScorer after --integrate.
                _p5_rejected = False
                _p5 = None
                # ── Drift cooldown gate: veto trades during post-HARD-drift pause ──
                if _drift_pause_remaining > 0:
                    _drift_pause_remaining -= 1
                    journal.on_rejected(
                        "drift_cooldown", candle_idx, candle.timestamp, state_path, 0.0
                    )
                    self._episode_summarizer.on_rejected("drift_cooldown", candle.timestamp)
                    state_path = []
                    _p5_rejected = True
                if not _p5_rejected and self._scorer is not None:
                    _feat_map_p5 = {
                        name: feature_vector[i]
                        for i, name in enumerate(CANONICAL_FEATURES)
                    }
                    _p5_dir = getattr(engine.state.direction, "value", "LONG").lower()
                    _p5 = self._scorer.compute(_feat_map_p5, candle_idx, direction=_p5_dir)
                    if _p5 is not None and _p5["p_win"] < 0.35:
                        journal.on_rejected(
                            f"P5_SCORE_LOW:{_p5['p_win']:.3f}",
                            candle_idx, candle.timestamp,
                            state_path, _p5["score"],
                        )
                        self._episode_summarizer.on_rejected(
                            f"P5_SCORE_LOW:{_p5['p_win']:.3f}", candle.timestamp
                        )
                        state_path = []
                        _p5_rejected = True

                # ── FeatureMonitor drift update ─────────────────────────────────
                _drift_vetoed = False
                if not _p5_rejected:
                    if self._monitor_available and self._monitor is not None:
                        try:
                            _feat_names = CANONICAL_FEATURES
                            _fv = feature_vector
                            _drift_dict = {}
                            for _fn in ("retest_depth", "body_ratio", "disp_strength"):
                                _idx = _feat_names.index(_fn) if _fn in _feat_names else -1
                                _drift_dict[_fn] = float(_fv[_idx]) if 0 <= _idx < len(_fv) else 0.0
                            self._monitor.update(_drift_dict)
                            _sev = self._monitor.detect_drift_severity(_drift_dict)
                            if _sev == "hard":
                                self.log.warning(
                                    "FeatureMonitor: HARD drift at candle %d (%s) — "
                                    "features strongly OOD (Z>3.0). Pausing %d candles.",
                                    candle_idx, self.cfg.instrument, _drift_cooldown,
                                )
                                if _drift_pause_enabled:
                                    _drift_pause_remaining = _drift_cooldown
                                    _hard_drift_pauses += 1
                                    _drift_vetoed = True
                                    journal.on_rejected(
                                        "hard_drift_veto",
                                        candle_idx, candle.timestamp, state_path, 0.0,
                                    )
                                    self._episode_summarizer.on_rejected(
                                        "hard_drift_veto", candle.timestamp
                                    )
                                    self._episode_summarizer.on_drift(
                                        "hard_drift", candle.timestamp
                                    )
                                    state_path = []
                            elif _sev == "soft":
                                self.log.debug(
                                    "FeatureMonitor: soft drift at candle %d (%s).",
                                    candle_idx, self.cfg.instrument,
                                )
                        except Exception:
                            pass

                # ── EngineRunner gate (adapter / fusion / dual / decision) ──
                _engine_vetoed = False
                _er_result = None   # default; set inside gate when BACKTEST_ENGINE_GATE=1
                if not _p5_rejected and not _drift_vetoed and _engine_runner is not None:
                    try:
                        _feat_map_er = {
                            name: feature_vector[i]
                            for i, name in enumerate(CANONICAL_FEATURES)
                        }
                        _feat_map_er.setdefault("close",     candle.close)
                        _feat_map_er.setdefault("high",      candle.high)
                        _feat_map_er.setdefault("low",       candle.low)
                        _feat_map_er.setdefault("open",      candle.open)
                        _feat_map_er.setdefault("volume",    candle.volume)
                        _feat_map_er.setdefault("atr",       engine.state.atr)
                        _feat_map_er.setdefault("timestamp", str(candle.timestamp))
                        # Map feature_vector's numeric session (0/1/2) → adapter's expected
                        # string ("asia"/"london"/"new_york"). FeaturePipeline encodes it
                        # int8; adapter session_map handles ints natively, so leave it.
                        # No override — the int will be correctly resolved by adapter_engine.
                        # Adapter requires this sentinel; FeatureStore adds it in live path.
                        if self.feature_vectors is not None and _fv_idx >= 0:
                            _feat_map_er["_data_integrity"] = "real"
                        # Pass CRT-determined direction so ultron_gate doesn't reject
                        # with "<regime>_no_direction" when breakout/trap are tied.
                        _crt_dir = engine.state.direction
                        if _crt_dir is not None:
                            _dir_int = getattr(_crt_dir, "value", _crt_dir)
                            try:
                                _feat_map_er["direction"]    = int(_dir_int)
                                _feat_map_er["signal_dir"]   = int(_dir_int)
                                _feat_map_er["trade_direction"] = int(_dir_int)
                            except Exception:
                                pass
                        # ── StrategyOrchestrator consensus (runs once per candle) ──
                        _strat_consensus_score = -1.0
                        _strat_consensus_dir = 0
                        if self._orch_available and self.feature_vectors is not None:
                            try:
                                _feat_dict = {
                                    name: feature_vector[i]
                                    for i, name in enumerate(CANONICAL_FEATURES)
                                    if i < len(feature_vector)
                                }
                                _feat_dict["close"] = candle.close
                                _feat_dict["atr"] = engine.state.atr
                                # Phase A/B: inject CRT transition path so StrategyIntentBuilder
                                # can use CRT-enriched evidence for S01/S10 (capabilities={"transition_path"}).
                                # Guarded by _phase_d_available — same import block as _recent_path (line ~1473).
                                if _phase_d_available:
                                    _feat_dict["_transition_path"] = _recent_path(engine.state)
                                _candle_dict = {"close": candle.close, "high": candle.high, "low": candle.low, "open": candle.open, "volume": candle.volume}
                                _orch_result = self._orch.compute(_feat_dict, _candle_dict)
                                if _orch_result.is_actionable():
                                    _strat_consensus_score = _orch_result.score
                                    _strat_consensus_dir = 1 if _orch_result.signal == "BUY" else -1
                            except Exception:
                                pass  # fail-open

                        _er_context = {
                            "instrument":                    self.cfg.instrument,
                            "timeframe":                     getattr(self.cfg, "timeframe", "M15"),
                            "strategy_consensus_direction":  int(_feat_map_er.get("direction", 0)),
                        }
                        if _strat_consensus_score >= 0.0:
                            _er_context["strategy_consensus_score"] = _strat_consensus_score
                        if self._runtime_ctx is not None:
                            _er_context["belief_registry"] = self._runtime_ctx.belief_registry
                        _er_result = _engine_runner.run(
                            _feat_map_er,
                            context=_er_context,
                        )
                        _decision = (_er_result or {}).get("decision") or (_er_result or {}).get("status", "")
                        _reason = (_er_result or {}).get("reason", "engine_runner_reject")
                        _stage  = (_er_result or {}).get("reject_stage", "?")
                        # Backtest-mode bypass: zone_gate_invalid is a production-only
                        # rule that requires a populated zone_registry.json. With ≤5
                        # zones loaded (treated as "no zones") we can't fairly enforce
                        # it in backtest. Live behavior unchanged.
                        _bypass_zone = (
                            os.getenv("BACKTEST_BYPASS_ZONE_INVALID", "1") == "1"
                            and "zone_gate_invalid" in str(_reason)
                        )
                        if str(_decision).upper() in ("REJECT", "REJECTED", "HOLD") and not _bypass_zone:
                            _engine_vetoed = True
                            _engine_rejected_count += 1
                            if _engine_rejected_count <= 5:
                                self.log.info(
                                    f"EngineRunner REJECT #{_engine_rejected_count} "
                                    f"stage={_stage} reason={_reason}"
                                )
                            journal.on_rejected(
                                f"engine_runner:{_stage}:{_reason}",
                                candle_idx, candle.timestamp, state_path, last_risk_score,
                            )
                            self._episode_summarizer.on_rejected(
                                f"engine_runner:{_stage}:{_reason}", candle.timestamp
                            )
                            state_path = []
                    except Exception as _er_exc:
                        # Fail-soft: log but allow trade through
                        self.log.debug(f"EngineRunner gate exception (allow): {_er_exc}")

                if not _p5_rejected and not _drift_vetoed and not _engine_vetoed:
                    # BitNet score recorded at approval time. crt_engine_v2 sets
                    # state.bitnet_main_score during compute_score()/approve() when
                    # use_bitnet is on and required features present; absent attr
                    # → BitNet was not evaluated → "" decision (adapter ignores).
                    _bn_score = getattr(engine.state, "bitnet_main_score", None)
                    if _bn_score is None:
                        _bn_score_val = 0.0
                        _bn_decision  = ""
                    else:
                        _bn_score_val = float(_bn_score)
                        # Trade reached this point ⇒ score cleared the engine's
                        # internal BitNet gate ⇒ implicit ACCEPT.
                        _bn_decision  = "ACCEPT"
                    journal.on_trade_opened(
                        trade          = engine.state.active_trade,
                        candle         = candle,
                        candle_index   = candle_idx,
                        risk_score     = last_risk_score,
                        state_path     = state_path,
                        htf_id         = htf.current_htf_id,
                        session        = last_session,
                        atr            = engine.state.atr,
                        spread_half    = spread_half,
                        feature_vector = feature_vector,
                        # Universe-B live metrics injected from the result dict —
                        # CRTEngine.get_live_metrics() was called immediately after
                        # TRADE_OPENED so these reflect the entry-candle state exactly.
                        # NOTE: must read from `result` (the full dict), not `action`
                        # (which is just the string value of result["action"]).
                        live_metrics    = result.get("live_metrics", {}),
                        bitnet_score    = _bn_score_val,
                        bitnet_decision = _bn_decision,
                        shadow_used     = _is_shadow_trade,
                    )
                    # Phase D: capture per-trade context for strategy memory
                    _sw_ev = getattr(engine.state, "sweep_event", None)
                    _last_sweep_type = str(getattr(_sw_ev, "sweep_type", "") or "")
                    # strategy_id surfaces via EngineRunner result (BACKTEST_ENGINE_GATE=1 only)
                    _last_strategy_id = str((_er_result or {}).get("top_strategy_id", ""))
                    # Log ENTRY to fusion JSONL for downstream Gaussian/TradeNet training
                    # Guard: skip when feature lookup missed (all-zero vector corrupts training data)
                    _orec = journal.open_trade
                    _fv_valid = any(v != 0.0 for v in feature_vector)
                    if _orec is not None and not _fv_valid:
                        self.log.warning(
                            "Skipping ENTRY log for %s — feature timestamp lookup missed "
                            "(candle_ts=%s not in feature index). Trade not written to fusion log.",
                            _orec.trade_id,
                            candle.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        )
                    if _orec is not None and _fv_valid:
                        self._trade_logger.log_entry(
                            trade_id      = _orec.trade_id,
                            instrument    = _orec.instrument,
                            direction     = _orec.direction,
                            session       = _orec.session,
                            regime        = "",
                            features      = _orec.features,
                            fusion_result = _p5 or {},
                            risk_pct      = _orec.risk_pct,
                            entry_price   = _orec.entry_price_raw,
                            sl_price      = _orec.sl_price,
                            tp1_price     = _orec.tp1_price,
                            tp2_price     = _orec.tp2_price,
                            opened_at     = _orec.opened_at,
                        )
                        # M1 — episode summarizer: trade opened
                        self._episode_summarizer.on_trade_opened(
                            trade_id    = _orec.trade_id,
                            entry_price = _orec.entry_price_raw,
                            sl_price    = _orec.sl_price,
                            tp2_price   = _orec.tp2_price,
                            direction   = str(getattr(_orec.direction, "value", _orec.direction)),
                            candle_ts   = candle.timestamp,
                            features    = _orec.features or {},
                        )
                    state_path = []

            elif "TRADE_STOPPED" in action or "TRADE_TP2" in action or "TRADE_TP1" in action:
                if journal.open_trade and engine.state.active_trade:
                    t = engine.state.active_trade
                    _closed = None
                    _trade_status = getattr(t, "status", "OPEN")
                    if "TP1" in action and "TP2" not in action and _partial_tp_enabled:
                        # Phase 3: partial TP — engine already moved SL→entry and set
                        # status="TP1". Don't close yet; runner continues to TP2 or BE.
                        self.log.info(
                            "TP1_PARTIAL: runner live for %s | partial_pnl=%.5f SL→%.5f",
                            t.id, t.partial_pnl, t.sl_price,
                        )
                    else:
                        if "STOPPED" in action:
                            if _trade_status == "TP1" and _partial_tp_enabled:
                                # Runner stopped at breakeven; blend exit = 50%@TP1 + 50%@entry
                                exit_raw = 0.5 * t.tp1_price + 0.5 * t.sl_price
                                reason = "TP1_BE_STOP"
                            else:
                                exit_raw, reason = t.sl_price, "STOPPED"
                        elif "TP2" in action:
                            if _trade_status == "TP1" and _partial_tp_enabled:
                                # Runner reached TP2; blend exit = 50%@TP1 + 50%@TP2
                                exit_raw = 0.5 * t.tp1_price + 0.5 * t.tp2_price
                                reason = "TP1_TP2"
                            else:
                                exit_raw, reason = t.tp2_price, "TP2"
                        else:
                            exit_raw, reason = t.tp1_price, "TP1"
                        _closed = journal.on_trade_closed(
                            t, exit_raw, reason,
                            candle, candle_idx, engine.state.atr, spread_half,
                        )
                    if _closed is not None:
                        # Phase D: attach strategy memory fields before any downstream read
                        if _phase_d_available:
                            try:
                                _closed.winning_strategy_id = _last_strategy_id
                                _closed.crt_path            = _enc_path(_recent_path(engine.state))
                                _closed.pattern_hash        = _comp_hash(
                                    _closed.features, sweep_type=_last_sweep_type or None,
                                )
                            except Exception:
                                pass
                        self._trade_logger.log_exit(
                            trade_id         = _closed.trade_id,
                            pnl_rr_net       = _closed.pnl_rr_net,
                            exit_reason      = _closed.exit_reason,
                            duration_candles = _closed.candle_close - _closed.candle_open,
                            closed_at        = _closed.closed_at,
                        )
                        # M1 — episode summarizer: trade closed
                        self._episode_summarizer.on_trade_closed(
                            trade_id    = _closed.trade_id,
                            pnl_rr_net  = _closed.pnl_rr_net,
                            exit_reason = _closed.exit_reason,
                            candle_ts   = candle.timestamp,
                        )

            elif action.startswith("RISK_REJECTED"):
                reason = action.split(":", 1)[1] if ":" in action else "unknown"
                score  = engine.state.risk_score.final if engine.state.risk_score else 0.0
                journal.on_rejected(reason, candle_idx, candle.timestamp, state_path, score)
                self._episode_summarizer.on_rejected(reason, candle.timestamp)
                state_path = []

            elif action == "RESET" and journal.open_trade and engine.state.active_trade:
                t = engine.state.active_trade
                _t_status = getattr(t, "status", "OPEN")
                if _t_status == "TP1" and _partial_tp_enabled:
                    # Runner alive at RESET: blend exit = 50%@TP1 + 50%@SL (already at trail/BE)
                    _exit_raw = 0.5 * t.tp1_price + 0.5 * t.sl_price
                    _reset_reason = "TP1_BE_RESET"
                else:
                    _exit_raw = candle.close
                    _reset_reason = "RESET_CLOSE"
                _closed = journal.on_trade_closed(
                    t, _exit_raw, _reset_reason, candle, candle_idx,
                    engine.state.atr, spread_half,
                )
                if _closed is not None:
                    # Phase D: attach strategy memory fields
                    if _phase_d_available:
                        try:
                            _closed.winning_strategy_id = _last_strategy_id
                            _closed.crt_path            = _enc_path(_recent_path(engine.state))
                            _closed.pattern_hash        = _comp_hash(
                                _closed.features, sweep_type=_last_sweep_type or None,
                            )
                        except Exception:
                            pass
                    self._trade_logger.log_exit(
                        trade_id         = _closed.trade_id,
                        pnl_rr_net       = _closed.pnl_rr_net,
                        exit_reason      = _closed.exit_reason,
                        duration_candles = _closed.candle_close - _closed.candle_open,
                        closed_at        = _closed.closed_at,
                    )
                    # M1 — episode summarizer: trade closed (RESET path)
                    self._episode_summarizer.on_trade_closed(
                        trade_id    = _closed.trade_id,
                        pnl_rr_net  = _closed.pnl_rr_net,
                        exit_reason = _closed.exit_reason,
                        candle_ts   = candle.timestamp,
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
            _closed = journal.on_trade_closed(
                engine.state.active_trade, last.close,
                "BACKTEST_END", last, candle_idx,
                engine.state.atr, spread_half,
            )
            if _closed is not None:
                self._trade_logger.log_exit(
                    trade_id         = _closed.trade_id,
                    pnl_rr_net       = _closed.pnl_rr_net,
                    exit_reason      = _closed.exit_reason,
                    duration_candles = _closed.candle_close - _closed.candle_open,
                    closed_at        = _closed.closed_at,
                )
                # M1 — episode summarizer: trade closed (BACKTEST_END)
                self._episode_summarizer.on_trade_closed(
                    trade_id    = _closed.trade_id,
                    pnl_rr_net  = _closed.pnl_rr_net,
                    exit_reason = _closed.exit_reason,
                    candle_ts   = last.timestamp,
                )

        # M1 — episode summarizer: flush any open episode at run end
        self._episode_summarizer.flush()

        m = met_eng.compute(journal, cap, candle_idx, state_counts, gap_resets)

        # Phase 2: attach drift monitor stats to distribution summary
        if self._monitor_available and self._monitor is not None:
            try:
                drift_stats = self._monitor.stats()
                if m.distribution:
                    m.distribution["feature_drift"] = drift_stats
                else:
                    m.distribution = {"feature_drift": drift_stats}
            except Exception:
                pass

        # Phase 4: attach hard drift pause count
        m.hard_drift_pauses = _hard_drift_pauses

        paths = writer.write_all(m, journal, flushed_events)

        # [TELEMETRY] Write Phase-0 CRT funnel telemetry sidecar
        try:
            _tel_records = engine.dump_telemetry()
            if _tel_records:
                _tel_path = writer.output_dir / f"{self.cfg.instrument}_crt_telemetry.jsonl"
                with open(_tel_path, "w", encoding="utf-8") as _tf:
                    for _rec in _tel_records:
                        _tf.write(json.dumps(_rec, default=str) + "\n")
                self.log.info("Telemetry: %s (%d records)", _tel_path, len(_tel_records))
        except Exception as _tel_exc:
            self.log.warning("Telemetry write failed (non-fatal): %s", _tel_exc)

        self._print_summary(
            m,
            shadow_sweep_count=_shadow_sweep_count,
            shadow_expansion_count=_shadow_expansion_count,
            shadow_leak_count=_shadow_leak_count,
        )
        self.log.info("Output:")
        for k, p in paths.items():
            if p:
                self.log.info(f"  {k:<15} → {p}")

        # Post-run training-trigger check: if cooldown/samples/drift gates open,
        # emit TRAINING_RECOMMENDED so the operator sees it in the audit log.
        # Backtest path → log only (no Telegram spam per batch). Wrapped so a
        # missing prod-config section or any disk error can never fail the run.
        try:
            from training.training_trigger import TrainingTrigger
            from utils.integrity_events import emit_integrity_event
            _trig = TrainingTrigger.from_prod_config()
            if _trig.should_trigger():
                _instr = getattr(self.cfg, "instrument", "")
                emit_integrity_event(
                    "TRAINING_RECOMMENDED", "INFO", "backtest_runner",
                    {"instrument":     _instr,
                     "results_dir":    str(output_dir),
                     "trigger_source": "backtest_completion"},
                )
                self.log.info(
                    "TrainingTrigger fired post-backtest for %s. "
                    "Run: python scripts/auto_train_from_opportunities.py "
                    "--instruments %s --refresh-zones --promote-if-approved",
                    _instr, _instr,
                )
                _trig.mark_fired()
        except Exception as _exc:
            self.log.debug("TrainingTrigger check failed (non-fatal): %s", _exc)

        # Release coin-scoped file handlers so multi-coin sequential runs don't
        # accumulate open handles or double-write to a previous coin's log dir.
        from utils.logging_config import close_coin_logging
        close_coin_logging(self.cfg.instrument)

        self._sweep_tracer.close()

        return m

    def _session(self, ts: datetime) -> str:
        t = ts.time()
        for name, (start, end) in self.crt_cfg.session_windows.items():
            if start <= t <= end:
                return name
        return "OFF_SESSION"

    def _print_summary(
        self,
        m: BacktestMetrics,
        shadow_sweep_count: int = 0,
        shadow_expansion_count: int = 0,
        shadow_leak_count: int = 0,
    ) -> None:
        self.log.info("─" * 55)
        self.log.info(f"  {m.instrument} | {m.approved_trades} trades | "
                      f"WR={m.win_rate:.1%} | AvgRR={m.avg_rr_net:.2f}R | "
                      f"PnL(net)={m.total_pnl_rr_net:+.2f}R | "
                      f"MaxDD={m.max_drawdown_pct:.1%}")
        if shadow_sweep_count > 0 or shadow_expansion_count > 0 or shadow_leak_count > 0:
            _leak_tag = "OK" if shadow_leak_count == 0 else f"FAIL ({shadow_leak_count})"
            self.log.info("─" * 55)
            self.log.info("  COUNTERFACTUAL COMPARISON (shadow displacement path)")
            self.log.info(f"    Shadow resume attempts : {shadow_sweep_count}")
            self.log.info(f"    Shadow expansions      : {shadow_expansion_count}")
            self.log.info(f"    SHADOW_LEAK            : {shadow_leak_count} [{_leak_tag}]")
            if shadow_leak_count > 0:
                self.log.warning(
                    "  SHADOW_LEAK > 0 — replay is invalid; investigate before promotion."
                )
        self.log.info("─" * 55)


# ─────────────────────────────────────────────────────────────────
# DATASET INTEGRITY PRE-FLIGHT (L2 gate)
# ─────────────────────────────────────────────────────────────────

def _preflight_dataset(csv_path: str, instrument: str, log: logging.Logger) -> bool:
    """L2 pre-flight gate. Runs the whole-sequence integrity validator before a
    file is streamed. Returns True if the file may proceed (APPROVE/WARN),
    False if it must be skipped (REJECT). Never aborts a batch — a rejected
    instrument is logged and skipped. A WARN runs but is logged with its report."""
    rep = validate_dataset(csv_path, instrument=instrument, raise_on_fail=False)
    decision = rep.get("decision")
    if decision == DatasetDecision.REJECT.value:
        log.error(
            "[dataset_integrity] REJECT %s (%s): %s — skipping instrument.",
            csv_path, instrument, "; ".join(rep.get("hard_failures", [])),
        )
        return False
    if decision == DatasetDecision.WARN.value:
        log.warning(
            "[dataset_integrity] WARN %s (%s): %s",
            csv_path, instrument, "; ".join(rep.get("warnings", [])),
        )
    return True


# ─────────────────────────────────────────────────────────────────
# MULTI-INSTRUMENT RUNNER
# ─────────────────────────────────────────────────────────────────

class MultiInstrumentRunner:
    INSTRUMENT_PIP = {
        "EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01,
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

        # L2+L3 pre-flight over the whole universe (single pass): per-file integrity
        # plus cross-file checks (exact-duplicate REJECT, overlap WARN). The returned
        # decision map is the per-file gate — REJECT files are skipped, never aborting
        # the batch.
        decisions = validate_universe(str(self.data_dir))["decisions"]

        results = []
        for csv_path in csv_files:
            instrument = self._infer(csv_path.stem)
            cfg = (
            BacktestConfig(**vars(self.bt_config))
            if self.bt_config is not None
            else BacktestConfig.from_prod_config()
        )
            cfg.instrument = instrument
            cfg.pip_size   = self.INSTRUMENT_PIP.get(instrument, 0.0001)

            decision = decisions.get(str(csv_path), DatasetDecision.APPROVE.value)
            if decision == DatasetDecision.REJECT.value:
                bt_log.error("[dataset_integrity] REJECT %s (%s) — skipping instrument.",
                             csv_path, instrument)
                continue
            if decision == DatasetDecision.WARN.value:
                bt_log.warning("[dataset_integrity] WARN %s (%s) — running with report.",
                               csv_path, instrument)

            try:
                loader = CandleLoader(str(csv_path), instrument)
                runner = BacktestRunner(cfg, csv_path=str(csv_path))
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
        # [Metrics V2 — Phase 3] per-symbol attribution. Each result is ONE symbol,
        # so attribution is a direct projection. Surfaces hidden concentration —
        # "30 trades" can be 29 on one symbol and 0 on the rest. trades_per_symbol
        # makes that visible; symbols are the proto-interpreters judged on this.
        total_trades = sum(r.approved_trades for r in results)
        symbol_attribution = {
            r.instrument: {
                "trades":           r.approved_trades,
                "trades_pct":       round(r.approved_trades / total_trades, 4) if total_trades else 0.0,
                "expectancy_rr":    round(r.avg_rr_net, 6),     # realized E[R]
                "avg_rr":           round(r.avg_rr_net, 6),
                "profit_factor":    round(r.profit_factor, 4),
                "win_rate":         round(r.win_rate, 4),
                "max_drawdown_pct": round(r.max_drawdown_pct, 4),
                "total_pnl_rr_net": round(r.total_pnl_rr_net, 4),
            }
            for r in results
        }
        agg = {
            "instruments":   len(results),
            "total_trades":  total_trades,
            "total_pnl_net": round(sum(r.total_pnl_rr_net for r in results), 4),
            "avg_win_rate":  round(sum(r.win_rate for r in results) / max(len(results), 1), 4),
            "trades_per_symbol":   {r.instrument: r.approved_trades for r in results},
            "symbol_attribution":  symbol_attribution,
            "per_instrument": [r.to_dict() for r in results],
        }
        with open(p, "w") as f:
            json.dump(agg, f, indent=2)
        bt_log.info(f"Aggregate → {p}")


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="CRT Backtest Harness v2")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--instrument", default="AUTO")
    ap.add_argument("--output", default="results")
    # CLI args below OVERRIDE the JSON production config; pass None to use JSON value
    ap.add_argument("--htf",          type=int,   default=None)
    ap.add_argument("--warmup",       type=int,   default=None)
    ap.add_argument("--capital",      type=float, default=None)
    ap.add_argument("--risk-pct",     type=float, default=None)
    ap.add_argument("--spread",       type=float, default=None)
    ap.add_argument("--no-slip",      action="store_true", default=False)
    ap.add_argument("--no-gap-reset", action="store_true", default=False)
    ap.add_argument("--sweep-age",    type=int,   default=None)
    ap.add_argument("--decay",        type=float, default=None)
    ap.add_argument("--threshold",    type=float, default=None)
    ap.add_argument("--config", help="JSON config file (not used by CRT backtest)")
    ap.add_argument("--scorer", choices=["static", "calibrated"], default="calibrated",
                    help="static = no-op scorer (CRT-only); calibrated = phase-5 GaussianNB gate")
    args = ap.parse_args()

    # Collect which CLI flags were explicitly set (for config dump audit trail).
    _cli_overrides: dict = {}

    # Determine instrument for market routing. Multi-instrument runs use EURUSD as the
    # Forex baseline; crt_engine JSON values override the base, so numeric params are
    # correct regardless of which instrument is routed later.
    _instr_hint = (
        args.instrument if args.instrument not in ("AUTO", "ALL")
        else Path(args.csv).stem.upper() if not Path(args.csv).is_dir()
        else "EURUSD"
    )

    # Load ALL CRTConfig fields from the production JSON (params + crt_engine merged).
    crt_cfg = load_prod_config_from_registry(PROD_VERSION, _instr_hint)

    # Apply explicit CLI overrides only for flags that were actually passed.
    _crt_cli: dict = {}
    if args.sweep_age is not None:
        _crt_cli["max_sweep_age_candles"] = args.sweep_age
        _cli_overrides["--sweep-age"] = str(args.sweep_age)
    if args.decay is not None:
        _crt_cli["score_decay_lambda"] = args.decay
        _cli_overrides["--decay"] = str(args.decay)
    if args.threshold is not None:
        _crt_cli["score_threshold"] = args.threshold
        _cli_overrides["--threshold"] = str(args.threshold)

    if _crt_cli:
        crt_cfg = ConfigBuilder.from_existing(_instr_hint, crt_cfg, extra_overrides=_crt_cli)

    _cli_overrides["--scorer"] = args.scorer

    # Load base config from JSON; CLI args override only when explicitly passed
    cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
    if args.htf         is not None:
        cfg.htf_candles_per_range = args.htf
        _cli_overrides["--htf"] = str(args.htf)
    if args.warmup      is not None:
        cfg.warmup_candles = args.warmup
        _cli_overrides["--warmup"] = str(args.warmup)
    if args.capital     is not None:
        cfg.initial_capital = args.capital
        _cli_overrides["--capital"] = str(args.capital)
    if args.risk_pct    is not None:
        cfg.risk_pct_per_trade = args.risk_pct
        _cli_overrides["--risk-pct"] = str(args.risk_pct)
    if args.spread      is not None:
        cfg.simulated_spread_pct = args.spread
        _cli_overrides["--spread"] = str(args.spread)
    if args.no_slip:
        cfg.slippage_enabled = False
        _cli_overrides["--no-slip"] = "true"
    if args.no_gap_reset:
        cfg.gap_reset_enabled = False
        _cli_overrides["--no-gap-reset"] = "true"
    cfg.scorer_mode = args.scorer

    # Optional: additional JSON override file (informational only)
    if args.config:
        bt_log.warning(
            "Using overridden config: %s (production version %s ignored)",
            args.config, PROD_VERSION,
        )
        _cli_overrides["--config"] = args.config
        import config_layer.production_config as _pc
        _pc.PROD_VERSION = f"CUSTOM:{Path(args.config).name}"

    csv_path = Path(args.csv)

    if csv_path.is_dir() or args.instrument.upper() == "ALL":
        # Multi-instrument mode
        MultiInstrumentRunner(str(csv_path), args.output, cfg).run_all()
    else:
        # Single instrument
        cfg.instrument = args.instrument if args.instrument != "AUTO" else csv_path.stem.upper()
        cfg.pip_size = MultiInstrumentRunner.INSTRUMENT_PIP.get(cfg.instrument, 0.0001)
        # L2 pre-flight gate — refuse to backtest a structurally corrupt dataset.
        if not _preflight_dataset(str(csv_path), cfg.instrument, bt_log):
            bt_log.error("Aborting single-instrument backtest: dataset rejected.")
            sys.exit(1)
        loader = CandleLoader(str(csv_path), cfg.instrument)
        runner = BacktestRunner(cfg, csv_path=str(csv_path), overrides=_cli_overrides)
        runner.run(loader.stream(), loader.count(), args.output)
        
# ─────────────────────────────────────────────────────────────────────────────
# Simplified backtest entry-point for signal-routing tests.
#
# Payload separation contract (tested by test_backtest_payload_integrity.py):
#   input_data → canonical features only  (no runtime metadata)
#   context    → runtime info (symbol, signal, confidence, score, volume)
# ─────────────────────────────────────────────────────────────────────────────

def run_backtest(config: dict, csv_path: str) -> list:
    """
    Run one-pass backtest using FeaturePipeline → BitNetModel → EngineRunner.

    Parameters
    ----------
    config : dict
        Must contain ``"model_path"`` key pointing to the BitNet model JSON.
    csv_path : str
        Path to the OHLCV CSV file.  Symbol is derived from the filename
        (``AUDUSD_M15.csv`` → ``"AUDUSD"``).

    Returns
    -------
    list[dict]
        One decision dict per row returned by ``EngineRunner.run()``.
    """
    raw_df  = pd.read_csv(csv_path)
    pipeline = FeaturePipeline(raw_df)
    enriched_df, vectors = pipeline.run()

    model  = BitNetModel(config["model_path"])
    runner = EngineRunner(config)

    # Symbol from filename: "data/AUDUSD_M15.csv" → "AUDUSD"
    symbol = os.path.basename(csv_path).split("_")[0]

    results = []
    for i, (_, row) in enumerate(enriched_df.iterrows()):
        # Canonical features only — no runtime metadata in input_data
        input_data = {feat: float(row.get(feat, 0.0)) for feat in CANONICAL_FEATURES}

        # Score via BitNet model
        vector     = vectors[i]
        score      = float(model.predict(vector))
        signal     = 1 if score > 0.5 else (-1 if score < -0.5 else 0)
        confidence = abs(score)

        # Runtime context (NOT canonical — goes to EngineRunner context arg)
        context = {
            "symbol":     symbol,
            "signal":     signal,
            "confidence": confidence,
            "score":      score,
            "volume":     float(row["volume"]),  # guaranteed by FeaturePipeline schema gate
        }

        result = runner.run(input_data, context)
        results.append(result)

    return results


if __name__ == "__main__":
    main()
