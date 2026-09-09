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
    FeatureAlignmentError,
    OHLCV_DATE_FORMATS,
    OHLCV_HEADER_ALIASES,
    OHLCV_TIMESTAMP_SINGLE_ALIASES,
    OHLCV_TIMESTAMP_SPLIT_ALIASES,
    parse_ohlcv_timestamp,
    require_ohlcv_columns,
    require_reviewed_clock,
    require_unique_ohlcv_headers,
    resolve_ohlcv_column_indices,
    validate_ohlcv_row,
)
from data_ingestion.dataset_registry import (
    DatasetAdmissionError,
    admit_csv_path,
)
from data_ingestion.xauusd_phase1_candidate import Phase1CandidateError
from data_ingestion.corpus_gate import admit_corpus
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
    EngineState, Range, Trade, state_risk_score,
)
from config_layer.production_config import PROD_VERSION, load_prod_config_from_registry
from config_layer.config_builder import ConfigBuilder
from runtime.parent_crt_feed import ParentCRTFeed

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

def _require_bt_cfg(cfg: dict, key: str, section: str) -> object:
    """Strict CONFIG accessor — raises if absent (T-22, CLAUDE.md Section 6.5: no silent
    config defaults). Sibling of core.engine_runner._cfg_require and the other per-module
    `_require` helpers; kept local to match the repo's established per-module convention."""
    if not isinstance(cfg, dict) or key not in cfg:
        raise KeyError(
            f"Required config key '{key}' missing from section '{section}'. "
            "Add it to the active production config (no silent config defaults)."
        )
    return cfg[key]


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

    # P2 F-057: allow ROUTER_BASE crt_config on product path (default refuse).
    # Use only for intentional router-profile experiments — not production claims.
    allow_router_crt_config: bool = False

    # ── Scorer mode ───────────────────────────────────────────────
    scorer_mode: str = "calibrated"   # "calibrated" | "static"

    # ── Strategy Registry pin (instance-specific; §13.5/§8) ────────
    # Names WHICH StrategyPackage this run claims to execute (strategies.
    # strategy_registry). "" = unresolved — TradeProvenanceV1 falls back to
    # a live from_active_config() projection rather than leaving it blank.
    strategy_id: str = ""

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

def _resolved_session_ts_basis() -> Optional[str]:
    """Active `feature_pipeline.session_timestamp_basis`, or None if it cannot be resolved.

    Feeds the Phase-3 double-conversion guard only. Returning None means "skip that optional
    check" — it never substitutes a default basis, so this is not a silent-default (CLAUDE.md
    6.5): the review gate itself still applies unconditionally, and the basis remains strictly
    required by `feature_pipeline` where it actually drives behaviour.
    """
    try:
        from config_layer.production_config import get_prod_section
        return get_prod_section("feature_pipeline")["session_timestamp_basis"]
    except Exception:
        return None


class CandleLoader:
    # Single source of truth lives in ohlcv_schema.OHLCV_DATE_FORMATS; kept as a
    # class attribute for backward compatibility with callers/tests.
    DATE_FORMATS = list(OHLCV_DATE_FORMATS)
    # B1 (2026-07-24): header resolution is delegated to
    # ohlcv_schema.resolve_ohlcv_column_indices (the SSOT). This local table used to be a THIRD,
    # independently-maintained alias map that had already drifted (missing `tick_volume`), gating
    # every load against a table the schema layer didn't know about. It is now DERIVED from the
    # schema tables purely so any external caller/test that still reads `CandleLoader.COLUMN_ALIASES`
    # sees the canonical aliases — it is no longer consulted by `stream()`.
    COLUMN_ALIASES = {
        "timestamp": list(OHLCV_TIMESTAMP_SINGLE_ALIASES),
        "date":      list(OHLCV_TIMESTAMP_SPLIT_ALIASES["date"]),
        "time_col":  list(OHLCV_TIMESTAMP_SPLIT_ALIASES["time"]),
        "open":      list(OHLCV_HEADER_ALIASES["open"]),
        "high":      list(OHLCV_HEADER_ALIASES["high"]),
        "low":       list(OHLCV_HEADER_ALIASES["low"]),
        "close":     list(OHLCV_HEADER_ALIASES["close"]),
        "volume":    list(OHLCV_HEADER_ALIASES["volume"]),
    }

    def __init__(self, filepath: str, instrument: str = "UNKNOWN"):
        # R3 Dataset Identity admission (CH-dataset-identity-r3-v1).
        # Bound XAUUSD M15: rewrite to Phase-1 candidate + hash/range (not APPROVED).
        # FORENSIC native HTF CSVs: reject. Unbound instruments: path passthrough.
        try:
            admission = admit_csv_path(filepath, instrument)
        except (DatasetAdmissionError, Phase1CandidateError) as exc:
            raise DatasetIntegrityError(
                f"corpus admission failed (R3 fail-closed): {exc}"
            ) from exc
        guarded = admission.filepath
        self.filepath   = guarded
        self.instrument = instrument
        self.log        = logging.getLogger("CRT.CandleLoader")
        # ── Phase 3: clock provenance (ohlcv_schema) ──────────────────────────
        # Phases 1-2 validate WHAT the numbers are; this validates what the TIMESTAMPS MEAN.
        # Gated in __init__, not stream(), so an undeclared corpus fails at construction rather
        # than lazily on first iteration. Eager beats surprising.
        require_reviewed_clock(self.filepath, basis=_resolved_session_ts_basis())
        if admission.rewritten or guarded != str(filepath):
            self.log.info(
                "R3 admitted %s -> %s (dataset_id=%s; NOT AUTHORITATIVE / NOT APPROVED)",
                filepath, guarded, admission.dataset_id,
            )

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
            # B1 (2026-07-24): delegate ALL header resolution to the schema SSOT. This one call
            # replaces the former local `_detect_column` ×8 + `use_split` logic AND folds in the
            # L1 uniqueness + mandatory-presence checks. It raises on a duplicate header or a
            # missing mandatory column, so nothing here becomes a silent skip.
            cols = resolve_ohlcv_column_indices(
                headers, source=f"Historical dataset {self.filepath}"
            )
            use_split = "date" in cols and "time" in cols
            date_col = cols.get("date")
            time_col = cols.get("time")
            ts_col   = cols.get("timestamp")
            o_col, h_col = cols["open"], cols["high"]
            l_col, c_col = cols["low"], cols["close"]
            v_col = cols["volume"]

            prev_ts: Optional[datetime] = None
            # B2 (2026-07-24): stamp a 0-based global candle position. The loader is now the
            # single INGESTION-stamp authority — `initialise_range` no longer re-stamps seed
            # candles off a `== 0` sentinel (which depended on this field being left at 0).
            # The CRT engine remains the SPINE authority: `process_candle` overwrites this with
            # its own `state.current_candle_index` on every bar, so spine reads are unchanged.
            # This stamp is what OFF-spine consumers (research scripts, telemetry on raw candles)
            # and the one-time seed window see. Counts YIELDED candles, not CSV lines, so a
            # skipped blank row does not create an index gap.
            _candle_pos = 0
            # B5 (2026-07-24): a trailing blank line at EOF is benign, but a blank line BETWEEN
            # data rows is corruption and must not be silently swallowed (the loader otherwise
            # never silent-skips). A streaming loop can't look ahead, so detect it RETROACTIVELY:
            # remember a skipped blank; if a real data row appears after it, that blank was
            # mid-file → raise.
            _pending_blank_line: Optional[int] = None
            for line_num, row in enumerate(reader, start=2):
                if not row or all(not cell.strip() for cell in row):
                    _pending_blank_line = line_num   # tolerate iff nothing follows (trailing)
                    continue
                if _pending_blank_line is not None:
                    raise DatasetIntegrityError(
                        f"Blank line {_pending_blank_line} inside data (a data row follows at "
                        f"line {line_num}) in {self.filepath} — a mid-file blank is corruption, "
                        "not a tolerable trailing newline."
                    )
                # B4 (2026-07-24): coerce OHLCV with source/line context. `float()` used to run
                # bare below, so a non-numeric cell (or a short row) raised a contextless
                # ValueError/IndexError; validate_ohlcv_row's informative message never fired
                # because coercion failed first. Coerce here, attributing the failure.
                try:
                    if use_split:
                        raw_ts = row[date_col].strip() + " " + row[time_col].strip()
                    else:
                        raw_ts = row[ts_col].strip()
                    o   = float(row[o_col]); h = float(row[h_col])
                    l   = float(row[l_col]); c = float(row[c_col])
                    vol = float(row[v_col])
                except (ValueError, IndexError) as exc:
                    raise ValueError(
                        f"Historical dataset {self.filepath} (line {line_num}): "
                        f"non-numeric or missing OHLCV cell: {exc}"
                    ) from exc
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
                # o/h/l/c/vol already coerced above (B4) with source/line context.
                # Phase 2 — value integrity: non-negative volume, candle
                # consistency. Malformed rows now RAISE (no silent skip) so a
                # corrupt dataset fails fast instead of yielding a truncated
                # candle stream.
                validate_ohlcv_row(
                    o, h, l, c, vol,
                    source=f"Historical dataset {self.filepath}",
                    line=line_num,
                )
                yield Candle(timestamp=ts, open=o, high=h, low=l, close=c,
                             volume=vol, index=_candle_pos)
                _candle_pos += 1

    def count(self) -> int:
        with open(self.filepath, "r", encoding="utf-8-sig") as f:
            return sum(1 for _ in f) - 1


# ─────────────────────────────────────────────────────────────────
# HTF BUILDER — count-based RESET CLOCK only.
# The M15 CRT sweep envelope is config_layer.m15_structural_range.M15StructuralLiquidityRange
# (historical name: Range). Calendar-true parent candles are
# features.parent_candle.ParentCandleBuilder. Three objects; do not conflate.
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

    # ── CH-htfcrt-parent-candle-smc-v1 (2026-08-15): additive, zero-risk ───────────
    # `push()`'s bool, `current_htf_id`'s format, and `seed_candles()`'s contents are all
    # UNCHANGED above this line — every existing consumer (backtest_v2 itself + 3
    # research mirrors in src/research/zone_mapping/) stays bit-identical. These two
    # properties merely expose the OHLC of the count-based window HTFBuilder already
    # holds in `_complete` (previously only H/L were derived from it, by
    # RangeDetector.detect_htf_range, with O/C silently discarded).
    #
    # NOTE (important distinction): this is the count-based, stream-offset-dependent
    # window's own OHLC — cheap telemetry, not a calendar-true parent candle. It carries
    # only ONE completed window (whatever `_complete` holds at the moment of the call),
    # never a multi-period history, because HTFBuilder itself never retained more than
    # one. A genuine ≥3-period retention for the 3-candle CRT construct is a SEPARATE,
    # calendar-based object: `features.parent_candle.ParentCandleBuilder(rule, keep=3)`.
    @property
    def parent_candle(self) -> Candle | None:
        """OHLC aggregate of the current `_complete` window, or None before the first
        close. Real open/high/low/close/volume — unlike `current_htf_id` (an opaque id
        string) or `seed_candles()` (the raw child list), this is an actual candle."""
        if not self._complete:
            return None
        from features.parent_candle import _aggregate
        return _aggregate(self._complete, self._complete[0].timestamp, self._htf_idx - 1)

    @property
    def parent_history(self) -> list[Candle]:
        """The single most recently closed window as a one-item list (oldest-first
        convention, matching `ParentCandleBuilder.parent_history`), or `[]` before the
        first close. Named/shaped identically to `ParentCandleBuilder.parent_history` for
        call-site symmetry — it is NOT a multi-period ring; see the note above."""
        pc = self.parent_candle
        return [pc] if pc is not None else []


# ─────────────────────────────────────────────────────────────────
# TRADE JOURNAL v2 — with cost tracking
# ─────────────────────────────────────────────────────────────────

class TradeJournal:
    def __init__(
        self, instrument: str, pip_size: float,
        slippage: SlippageModel, capital_curve: CapitalCurve,
        sl_atr_buffer: float,
    ):
        self.instrument    = instrument
        self.pip_size      = pip_size
        self.slip          = slippage
        self.cap           = capital_curve
        # REQUIRED (no default): the SL-distance floor used by the [FIX-SL] guard in
        # on_trade_opened. Previously a hardcoded `0.2 * atr` whose comment claimed to
        # match crt_engine.sl_atr_buffer but did not READ it — editing the config key
        # silently desynchronized the two. Now threaded from the resolved CRTConfig.
        self.sl_atr_buffer = float(sl_atr_buffer)
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
        # abs(entry_fill - sl_price) < sl_atr_buffer * ATR, extend the SL outward from
        # entry_fill to restore the minimum distance.  Prevents near-zero SL → runaway
        # position size.  The buffer now READS crt_engine.sl_atr_buffer (threaded via
        # the resolved CRTConfig) instead of duplicating it as a 0.2 literal.
        _min_sl_dist = self.sl_atr_buffer * atr
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
    """Default no-op scorer. Replaced by CRTCalibratedScorer after phase5 --integrate.

    Signature matches CRTCalibratedScorer / HeuristicGaussianEngine duck-type:
    ``compute(features, candle_idx, direction=...)`` so the Phase-5 call site
    (``direction=_p5_dir``) never TypeErrors. direction is intentionally ignored —
    this scorer always returns None (no gate).
    """
    def compute(self, features: dict, candle_idx: int, direction: str = "long"):
        return None


# ─────────────────────────────────────────────────────────────────
# LEDGER PROVENANCE (§13 item8 / §9 — closes TradeProvenanceV1's zero-consumer gap)
# ─────────────────────────────────────────────────────────────────

def _model_version_string(pkg) -> str:
    """Compact single-string join of a StrategyPackage's model pins — fits
    TradeProvenanceV1.model_version (Optional[str]) without widening its schema."""
    if pkg is None:
        return ""
    parts = [f"{k}={v}" for k, v in pkg.model.items() if v is not None]
    return ";".join(parts)


def _build_provenance_base(instrument: str, strategy_id: str) -> dict:
    """Resolve the run-level provenance fields once (config version/hash, model
    pins, strategy id). Best-effort — never raises; a resolution failure just
    means those fields stay None on every trade this run opens."""
    from config_layer.production_config import get_prod_metadata

    base = {
        "config_version":    PROD_VERSION,
        "config_hash":       None,
        "promotion_version": PROD_VERSION,
        "model_version":     None,
        "strategy_id":       strategy_id or None,
    }
    try:
        meta = get_prod_metadata()
        base["config_hash"] = meta.get("config_hash")
    except Exception as _meta_exc:  # noqa: BLE001
        bt_log.debug("Provenance: get_prod_metadata failed: %s", _meta_exc)

    try:
        from strategies.strategy_registry import StrategyRegistry
        pkg = StrategyRegistry().resolve_for_instrument(instrument, name=(strategy_id or None))
        base["model_version"] = _model_version_string(pkg)
        if not strategy_id:
            base["strategy_id"] = pkg.name
    except Exception as _pkg_exc:  # noqa: BLE001
        bt_log.debug("Provenance: StrategyPackage resolution failed: %s", _pkg_exc)

    return base


# ─────────────────────────────────────────────────────────────────
# BACKTEST RUNNER v2
# ─────────────────────────────────────────────────────────────────

# ── CH-v3-unified-market-structure-v1 ──────────────────────────────────────────────────
# Canonical vector positions for the two CHoCH inputs, resolved from FEATURE_INDEX_MAP at
# import rather than written as literals, so a schema reorder moves them automatically instead
# of silently reading the wrong column (the failure class behind F-062/F-063).
from features.feature_schema import FEATURE_INDEX_MAP as _FEATURE_INDEX_MAP

_BOS_IDX = _FEATURE_INDEX_MAP["break_of_structure"]
_TREND_BIAS_IDX = _FEATURE_INDEX_MAP["trend_bias"]


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
        # F-057 fix (2026-07-29, target-strategy-architecture.md sec13 item1): a caller
        # that constructs BacktestConfig without an explicit crt_config used to fall back
        # to the bare router profile (ConfigBuilder.build — 5 hardcoded keys, no params/
        # crt_engine merge), silently diverging from the CLI path's governed
        # load_prod_config_from_registry(). That fallback is now the SAME governed loader,
        # so every programmatic caller (tuner workers, diagnostics, portfolio_validation,
        # research adapters) gets the identical CRTConfig the CLI would build for the same
        # instrument. instrument is required — no silent "EURUSD" default (F-057 sec14.A).
        if bt_config.crt_config is not None:
            self.crt_cfg = bt_config.crt_config
        else:
            if not bt_config.instrument or bt_config.instrument == "UNKNOWN":
                raise ValueError(
                    "BacktestRunner: bt_config.crt_config is None and bt_config.instrument "
                    f"is unset ({bt_config.instrument!r}) — cannot resolve a governed CRTConfig. "
                    "Pass an explicit instrument or crt_config (F-057: no silent EURUSD default)."
                )
            self.crt_cfg = load_prod_config_from_registry(PROD_VERSION, bt_config.instrument)

        # P2 F-057: product path refuses ROUTER_BASE / SCHEMA / UNKNOWN unless escape hatch.
        from config_layer.crt_config_provenance import assert_product_crt_config

        assert_product_crt_config(
            self.crt_cfg,
            context="BacktestRunner",
            allow_router_base=bool(
                getattr(bt_config, "allow_router_crt_config", False)
            ),
        )

        # ── Ledger provenance base (§13 item8 / §9 — TradeProvenanceV1) ────────
        # Resolved once per run (strategy/model pins don't change mid-backtest).
        # Best-effort: a resolution failure degrades to None fields rather than
        # aborting the run — provenance is captured best-effort, never blocking
        # (see journal.trade_provenance_v1_0 module docstring).
        self._provenance_base = _build_provenance_base(bt_config.instrument, bt_config.strategy_id)

        # R3 Dataset Identity admission (fail-closed rewrite + hash/range for bound M15).
        if csv_path:
            try:
                csv_path = admit_csv_path(
                    csv_path, bt_config.instrument or "UNKNOWN"
                ).filepath
            except (DatasetAdmissionError, Phase1CandidateError) as exc:
                raise DatasetIntegrityError(
                    f"corpus admission failed (R3 fail-closed): {exc}"
                ) from exc
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
        # T-16: recorded so the replay loop can tell "no features by construction" from
        # "features expected but absent" — only the latter is a contract failure.
        # TWO legitimate no-feature modes, both of which must keep zero-filling:
        #   * skip_features=True      — tuner workers that never read feature columns
        #   * no csv_path at all      — the programmatic BacktestRunner(cfg) path used by the
        #                               tuner / embedders / tests (F-057), which streams candles
        #                               from a caller-supplied iterator and never builds a frame
        # The __init__ warmup assert below is likewise scoped to the expected case, so the
        # replay-loop predicate must match it exactly or the two disagree.
        self._features_expected = bool(self.csv_path) and not skip_features
        if self.csv_path and not skip_features:
            try:
                from features.feature_pipeline import FeaturePipeline
                require_reviewed_clock(self.csv_path,
                                       basis=_resolved_session_ts_basis())  # Phase 3
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
                # CH-v4-dual-construction-crt-trace-2026-08-30: `CRTStateResolver.resolve()`
                # requires 3 non-canonical, non-vector columns FeaturePipeline already computes
                # and `enriched_df` already carries, but which `CANONICAL_FEATURES`/
                # `self.feature_vectors` never included (they are not part of the 48-dim
                # vector). Retained ADDITIVELY here — this does not touch `feature_vectors` or
                # `feature_ts_to_idx`, the objects every parity-sensitive lookup (trade-open,
                # `_bar_structure_choch_inputs`) already depends on. Absent gracefully: a
                # missing column here degrades `_construction_trace_feature_dict` to None
                # (recorded as NO_FEATURES) rather than fabricating a 0.0 the resolver's own
                # supply-contract check exists specifically to forbid.
                self._resolver_extra_arrays = {
                    c: (enriched_df[c].to_numpy() if c in enriched_df.columns else None)
                    for c in ("displacement_flag", "retest_flag", "rsi_state")
                }
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
                # ── T-16: warmup coupling (closes the two-declarations split-brain) ──
                # finalize() dropped `required_warmup_rows()` leading rows; any candle the
                # replay loop processes before that index has NO feature row behind it. The
                # loop's own skip is `cfg.warmup_candles`, which was an unrelated literal.
                # Resolve the true value and refuse to start if the configured skip is shorter,
                # rather than discovering it as a lookup miss 30 bars later.
                from features.feature_pipeline import required_warmup_rows
                _pipeline_warmup = required_warmup_rows()
                if int(self.cfg.warmup_candles) < _pipeline_warmup:
                    raise FeatureAlignmentError(
                        f"backtest.warmup_candles={self.cfg.warmup_candles} is shorter than the "
                        f"feature pipeline's canonical warmup ({_pipeline_warmup} rows dropped by "
                        f"FeaturePipeline.finalize()). Candles "
                        f"{self.cfg.warmup_candles}..{_pipeline_warmup - 1} would run through the "
                        f"CRT state machine with no feature row behind them. The pipeline warmup is "
                        f"derived from feature_pipeline.ma_periods[0] + "
                        f"(trend_strength_window - 1) + (zscore_window - 1). Raise "
                        f"backtest.warmup_candles to >= {_pipeline_warmup}, or shorten those windows."
                    )
            except FeatureAlignmentError:
                raise   # a governed contract failure — never repackaged as a generic RuntimeError
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
                window_size=int(_require_bt_cfg(_fm_cfg, "window_size", "feature_monitor")),
                soft_threshold=float(_require_bt_cfg(_fm_cfg, "soft_drift_z", "feature_monitor")),
                hard_threshold=float(_require_bt_cfg(_fm_cfg, "hard_drift_z", "feature_monitor")),
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
    # ── CH-v3-unified-market-structure-v1 ────────────────────────────────────────────
    # Two OBSERVATION-ONLY helpers for the BarStructureSnapshot sidecar (SEM-035). Neither is
    # reachable from any decision path: the first is called once at run setup, the second is a
    # pure read of already-computed canonical feature columns. Both fail SOFT — a broken
    # observation surface must never be able to take a backtest down with it, which is exactly
    # the opposite of the fail-fast discipline that governs decision-bearing config (CLAUDE.md
    # 6.5). Observation is not decision, so the correct failure mode is different.

    def _build_bar_structure_emitter(self, run_id: str):
        """Construct the per-bar snapshot emitter, or None when it is not enabled.

        Returns None on ANY problem (section absent, disabled, or construction error) after
        logging. v2_htfcrt_2026_08 has no `bar_structure_snapshot` section at all, so None is
        the normal path for every config that predates v3.
        """
        try:
            from runtime.bar_structure_snapshot import (
                BarStructureEmitter,
                SnapshotConfig,
                corpus_sha256,
            )

            cfg = SnapshotConfig.from_prod_config()
            if cfg is None:
                return None

            from config_layer.production_config import get_prod_section
            from features.feature_schema import SCHEMA_HASH, SCHEMA_VERSION

            fp = get_prod_section("feature_pipeline")
            try:
                parent = get_prod_section("parent_crt")
            except (RuntimeError, KeyError):
                parent = {}
            obj_gate = parent.get("objective_gate", {}) or {}

            emitter = BarStructureEmitter(
                cfg,
                run_id=run_id,
                instrument=self.cfg.instrument,
                timeframe="M15",
                corpus_path=str(self.csv_path or ""),
                # A missing corpus (the programmatic no-CSV path) is recorded as the literal
                # sentinel rather than an empty string, so a record can never LOOK identified
                # while carrying no corpus binding.
                corpus_hash=(corpus_sha256(self.csv_path) if self.csv_path else "NO_CORPUS_FILE"),
                config_version=PROD_VERSION,
                config_hash=self._bar_structure_config_hash(),
                swing_window=int(fp["swing_window"]),
                smc_max_window=int(fp["smc_max_window"]),
                timestamp_basis=str(fp["session_timestamp_basis"]),
                objective_gate_enabled=bool(obj_gate.get("enabled", False)),
                objective_gate_mode=str(obj_gate.get("mode", "")),
                parent_timeframe=parent.get("timeframe"),
                htf_thresholds=parent.get("htf_state"),
                feature_schema_version=SCHEMA_VERSION,
                feature_schema_hash=SCHEMA_HASH,
            )
            self.log.info(
                "BarStructureSnapshot ENABLED (observation only) | schema=%s | -> %s",
                cfg.schema_version, emitter.path,
            )
            return emitter
        except Exception as exc:  # noqa: BLE001
            self.log.warning(
                "BarStructureSnapshot disabled (construction failed, backtest unaffected): %s",
                exc,
            )
            return None

    def _bar_structure_config_hash(self) -> str:
        from config_layer.production_config import get_full_config_dict

        try:
            return str(get_full_config_dict().get("config_hash", ""))
        except Exception:  # noqa: BLE001
            return ""

    def _bar_structure_choch_inputs(self, candle):
        """`(break_of_structure, trend_bias)` for this bar, JOINED from the canonical 48-dim
        vector — never re-derived.

        Both are canonical features (`FEATURE_INDEX_MAP`: break_of_structure=22, trend_bias=10),
        so reading them out of `self.feature_vectors` is a join against the same values the rest
        of the system uses. `(None, None)` when no vector exists for this timestamp, which the
        emitter records as `choch_basis="UNAVAILABLE_NO_PIPELINE_COLUMNS"` rather than silently
        substituting a locally-computed BOS.
        """
        if self.feature_vectors is None or not self.feature_ts_to_idx:
            return None, None
        try:
            idx = self.feature_ts_to_idx.get(
                candle.timestamp.strftime("%Y-%m-%d %H:%M:%S"), -1
            )
            if idx < 0:
                return None, None
            row = self.feature_vectors[idx]
            return float(row[_BOS_IDX]), float(row[_TREND_BIAS_IDX])
        except Exception:  # noqa: BLE001
            return None, None

    # ── CH-v4-dual-construction-crt-trace-2026-08-30 ──────────────────────────────
    def _build_construction_trace_emitter(self, run_id: str):
        """Construct the engine-vs-ontology dual-construction trace emitter, or None.

        Mirrors `_build_bar_structure_emitter`'s discipline exactly: returns None on ANY
        problem (section absent, disabled, construction error) after logging, and never lets
        an observation sidecar take the backtest down with it.
        """
        try:
            from runtime.crt_construction_trace import ConstructionTraceConfig, ConstructionTraceEmitter
            from runtime.bar_structure_snapshot import corpus_sha256

            cfg = ConstructionTraceConfig.from_prod_config()
            if cfg is None:
                return None

            import yaml as _yaml
            with open(cfg.ontology_source, encoding="utf-8") as _fh:
                _ontology_version = _yaml.safe_load(_fh).get("version")

            emitter = ConstructionTraceEmitter(
                cfg,
                run_id=run_id,
                instrument=self.cfg.instrument,
                timeframe="M15",
                corpus_path=str(self.csv_path or ""),
                corpus_hash=(corpus_sha256(self.csv_path) if self.csv_path else "NO_CORPUS_FILE"),
                config_version=PROD_VERSION,
                config_hash=self._bar_structure_config_hash(),
                ontology_version=_ontology_version,
            )
            self.log.info(
                "CRTConstructionTrace ENABLED (observation only) | schema=%s | -> %s",
                cfg.schema_version, emitter.path,
            )
            return emitter
        except Exception as exc:  # noqa: BLE001
            self.log.warning(
                "CRTConstructionTrace disabled (construction failed, backtest unaffected): %s",
                exc,
            )
            return None

    def _construction_trace_feature_dict(self, candle) -> Optional[dict]:
        """Canonical name->value feature dict for THIS bar, or None on a lookup miss.

        Deliberately non-raising (unlike the T-16 fail-closed lookup at trade-open): this is an
        observation sidecar, and a missing feature row is itself information the emitter
        records (`divergence_pair` carries `NO_FEATURES`), not a reason to abort the backtest.
        """
        if self.feature_vectors is None or not self.feature_ts_to_idx:
            return None
        try:
            idx = self.feature_ts_to_idx.get(
                candle.timestamp.strftime("%Y-%m-%d %H:%M:%S"), -1
            )
            if idx < 0:
                return None
            row = self.feature_vectors[idx]
            feat = {name: float(row[i]) for i, name in enumerate(CANONICAL_FEATURES)}
            extra = getattr(self, "_resolver_extra_arrays", None)
            if extra is None:
                # Attribute never populated (e.g. a construction path that bypassed the
                # FeaturePipeline branch in __init__) -- cannot supply the resolver's
                # required non-vector features. Graceful skip, not a partial dict that
                # would raise PredicateValidationError downstream.
                return None
            for col, arr in extra.items():
                if arr is None:
                    # Required-but-absent (RISK: see __init__ comment) -- graceful skip,
                    # never a fabricated 0.0.
                    return None
                feat[col] = float(arr[idx])
            return feat
        except Exception:  # noqa: BLE001
            return None

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
        # F-075 caller: calendar-true parent CRT. None when parent_crt.enabled is
        # false (v2_multi_2026_04 stays parent_state=None). Pushed on every child
        # bar including warmup so C1/C2/C3 exist before the first process_candle.
        parent_feed = ParentCRTFeed.from_prod_config()
        if parent_feed is not None:
            self.log.info(
                "ParentCRT feed wired | timeframe=%s | gate=reject_on_mismatch",
                parent_feed.rule,
            )
        slip    = SlippageModel(
            self.cfg.slippage_atr_fraction if self.cfg.slippage_enabled else 0.0,
            self.cfg.slippage_seed,
        )
        cap     = CapitalCurve(
            self.cfg.initial_capital,
            self.cfg.risk_pct_per_trade,
            self.cfg.use_compounding,
        )
        journal = TradeJournal(
            self.cfg.instrument, self.cfg.pip_size, slip, cap,
            sl_atr_buffer=self.crt_cfg.sl_atr_buffer,
        )
        gap_det = GapDetector(self.cfg.gap_reset_minutes, self.cfg.gap_reset_enabled)
        met_eng = MetricsEngine(self.cfg.instrument)
        writer  = ReportWriter(output_dir, self.cfg.instrument)

        # ── CH-v3-unified-market-structure-v1: BarStructureSnapshot ─────────
        # OBSERVATION ONLY. `_bar_structure` is None unless the ACTIVE config carries
        # `bar_structure_snapshot.enabled: true` (absent on v2 and earlier, false by
        # default on v3), so on every existing config this is a `None` check per bar and
        # nothing else. Construction failure NEVER breaks a backtest: this surface is an
        # observation sidecar and must not be able to take the spine down with it.
        _bar_structure = self._build_bar_structure_emitter(writer.run_id)

        # ── CH-v4-dual-construction-crt-trace-2026-08-30: CRTConstructionTrace ──
        # OBSERVATION ONLY, same discipline as `_bar_structure` immediately above. `None`
        # unless `crt_construction_trace.enabled: true` (absent from every config that
        # predates v4, false by default on v4 itself). `_gate_hooks` is attached to
        # `engine.baseline_trace` ONCE below (not per bar) — the engine's own
        # `process_candle` calls `reset_bar()` on it internally every bar when enabled
        # (crt_engine_v2.py:2856), so the object is reusable across the whole run.
        _construction_trace = self._build_construction_trace_emitter(writer.run_id)
        _gate_hooks = _construction_trace.new_gate_hooks() if _construction_trace is not None else None
        # `engine` already exists (constructed above) — attach ONCE, not per bar. Inherits the
        # pre-existing CRTBaselineTraceHooks contract (crt_baseline_trace.py docstring: "Does
        # NOT recompute features, re-evaluate guards, or mutate CRT control flow") —
        # `engine.baseline_trace` defaults None regardless, so a None `_gate_hooks` here is a
        # complete no-op identical to every config that predates this feature. The engine's own
        # `process_candle` calls `reset_bar()` on it internally every bar when enabled
        # (crt_engine_v2.py:2856), so the object is reusable across the whole run.
        if _gate_hooks is not None:
            engine.baseline_trace = _gate_hooks

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
        # T-16 (2026-07-23): the two ENABLE flags were still soft (`.get(..., False)`) while the
        # magnitudes beside them were made strict by the F-056 remediation — the fractions were
        # fixed and the flags in the same block were missed. Both are declared `true` in config
        # while the code default was `False`, so an absent key silently FLIPPED the feature off
        # while the config claimed it was on: the F-056 "config illusion" class exactly. Strict
        # now; parity-safe because the declared values are what the runtime was already using.
        _partial_tp_enabled  = bool(_require_bt_cfg(_ep_cfg_bt, "partial_tp_breakeven_enabled", "execution_planner"))
        _partial_tp_fraction = float(_require_bt_cfg(_ep_cfg_bt, "partial_tp_fraction", "execution_planner"))
        _drift_pause_enabled = bool(_require_bt_cfg(_fm_cfg_bt, "drift_regime_pause_enabled", "feature_monitor"))
        _drift_cooldown      = int(_require_bt_cfg(_fm_cfg_bt, "drift_cooldown_candles", "feature_monitor"))
        # Phase-5 calibrated-scorer veto floor. Was a bare `0.35` literal at the compare
        # site, declared in NO config section despite phase5_calibration existing — and it
        # gates every trade under the default scorer_mode="calibrated".
        _p5_cfg_bt   = _gps_bt("phase5_calibration")
        _p5_min_pwin = float(_require_bt_cfg(_p5_cfg_bt, "min_p_win", "phase5_calibration"))

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
        # Runs adapter → fusion → dual-engine → decision_engine on each candidate trade.
        #
        # F-058 resolution (T-16, 2026-07-23): CONFIG is the authority. This was read only as
        # os.getenv("BACKTEST_ENGINE_GATE", "1"), declared in no config, so the documented
        # behavior depended on an untracked `.env` — F-037 and active_models.yaml say OFF, the
        # code default is ON, and CI/scrubbed environments silently produced a different ledger.
        # The env var is now an EXPLICIT override that logs at WARNING when it disagrees with
        # config, so the divergence can never again be silent.
        _bt_gate_cfg = _require_bt_cfg(
            _gps_bt("backtest"), "engine_gate_enabled", "backtest"
        )
        _gate_enabled = bool(_bt_gate_cfg)
        _gate_env = os.getenv("BACKTEST_ENGINE_GATE")
        if _gate_env is not None:
            _env_enabled = _gate_env == "1"
            if _env_enabled != _gate_enabled:
                self.log.warning(
                    "BACKTEST_ENGINE_GATE=%r OVERRIDES backtest.engine_gate_enabled=%s — "
                    "this run's ledger is NOT the config-declared epoch (F-058).",
                    _gate_env, _gate_enabled,
                )
            _gate_enabled = _env_enabled

        # F-058-class fix (2026-07-29, target-strategy-architecture.md sec13 item2): the
        # zone_gate_invalid backtest-mode bypass was read only as
        # os.getenv("BACKTEST_BYPASS_ZONE_INVALID", "1"), declared in no config — the same
        # undeclared-env-truth class as engine_gate_enabled above. CONFIG is now the
        # authority; the env var stays an explicit override that logs at WARNING on
        # disagreement, mirroring the engine_gate_enabled pattern exactly.
        _bypass_zone_cfg = bool(_require_bt_cfg(
            _gps_bt("backtest"), "bypass_zone_invalid", "backtest"
        ))
        _bypass_zone_enabled = _bypass_zone_cfg
        _bypass_zone_env = os.getenv("BACKTEST_BYPASS_ZONE_INVALID")
        if _bypass_zone_env is not None:
            _bypass_zone_env_enabled = _bypass_zone_env == "1"
            if _bypass_zone_env_enabled != _bypass_zone_cfg:
                self.log.warning(
                    "BACKTEST_BYPASS_ZONE_INVALID=%r OVERRIDES backtest.bypass_zone_invalid=%s "
                    "— this run's ledger is NOT the config-declared epoch (F-058-class).",
                    _bypass_zone_env, _bypass_zone_cfg,
                )
            _bypass_zone_enabled = _bypass_zone_env_enabled

        _engine_runner = None
        _engine_rejected_count = 0
        if _gate_enabled:
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
            if parent_feed is not None:
                _parent_closed = parent_feed.push(candle)
                # Observation only: the return value was previously discarded. The
                # snapshot needs it to distinguish "the parent state changed on this bar"
                # from "unchanged and carried forward". Nothing reads it back.
                if _bar_structure is not None:
                    _bar_structure.note_parent_closed(_parent_closed)
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
                    # Observation only, emitted BEFORE the `continue` so `bar_index` is a
                    # gapless 0..N-1 occupancy series. That gaplessness is what lets the
                    # stream carry CC-CTX-RUN-SCOPED-OBSERVATION rather than the
                    # unidentified class `logs/crt_transitions.jsonl` sits in.
                    if _bar_structure is not None:
                        _bar_structure.emit_warmup(candle, candle_idx - 1)
                    if _construction_trace is not None:
                        _construction_trace.emit_warmup(candle_idx - 1, candle.timestamp)
                    prev_candle = candle
                    continue
                warmup_done = True

            # ── Initialise ─────────────────────────────────────────
            if not initialised:
                if htf.seed_candles():
                    # Named `session_label` (not `session`) to avoid colliding with the canonical
                    # feature `session` (FM-052, int8 {0,1,2} from hour cutoffs 8/16). THIS is the
                    # CRT-engine session LABEL: a string name resolved from crt_cfg.session_windows,
                    # defaulting to "OFF_SESSION". Distinct quantity, distinct type.
                    session_label = self._session(candle.timestamp)
                    engine.initialise_range(htf.seed_candles(), htf.current_htf_id, session_label)
                    initialised = True
                    self.log.info(f"  Engine init @ candle {candle_idx} | HTF={htf.current_htf_id}")
                # Observation only. This branch `continue`s BEFORE process_candle, so without
                # an emit here the initialisation bar would be the single hole in an otherwise
                # gapless bar_index -- and a stream with a coverage hole cannot support "the
                # state at bar i", which is the whole basis for CC-CTX-RUN-SCOPED-OBSERVATION.
                # Emitted in the WARMUP shape because the engine has no state for this bar yet.
                if _bar_structure is not None:
                    _bar_structure.emit_warmup(candle, candle_idx - 1)
                if _construction_trace is not None:
                    _construction_trace.emit_warmup(candle_idx - 1, candle.timestamp)
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

            # CH-resolver-engine-envelope: mark the transition log HERE, before the G4 gap
            # reset below, not after it. `reset_to_range` appends to `transition_log`, so a
            # mark taken after the gap block silently drops every gap-driven SWEEP->RANGE from
            # `engine.transitions` -- caught by an occupancy-vs-transition invariant (162
            # occupancy changes vs 161 recorded transitions on the XAUUSD window). Same reason
            # `_trace_state_before` is captured here rather than reusing `prev_state`, which is
            # read AFTER the reset and therefore already shows the post-reset state.
            # Observation only; `prev_state` and everything downstream are untouched.
            _tlog_mark = (
                len(engine.state.transition_log)
                if _construction_trace is not None else 0
            )
            _trace_state_before = engine.state.current_state.name

            # ── [G4] Gap detection ─────────────────────────────────
            gap_fired, gap_reason = gap_det.check(candle)
            if gap_fired:
                gap_resets += 1
                if journal.open_trade and engine.state.active_trade:
                    spread_half = candle.close * self.cfg.simulated_spread_pct / 2
                    _gap_closed = journal.on_trade_closed(
                        engine.state.active_trade, candle.open,
                        "GAP_RESET_CLOSE", candle, candle_idx,
                        engine.state.atr_abs, spread_half,
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
            parent_state = parent_feed.bias if parent_feed is not None else None
            parent_objective = (
                parent_feed.objective.status if parent_feed is not None else None
            )
            result     = engine.process_candle(
                candle, htf.current_htf_id,
                parent_state=parent_state,
                parent_objective=parent_objective,
            )
            curr_state = engine.state.current_state.name
            state_counts[prev_state] += 1
            if prev_state != curr_state:
                state_path.append(f"{prev_state}→{curr_state}")
                # M1 — episode summarizer: notify on every state change
                self._episode_summarizer.on_state_transition(
                    prev_state, curr_state, candle.timestamp, candle_idx
                )

            # ── CH-v3: BarStructureSnapshot ────────────────────────
            # Placed AFTER `process_candle` has returned and after `curr_state` is read,
            # so the decision for this bar is already final and unobservable from here.
            # `emit` returns None and nothing below consumes it — the byte-identical
            # ledger test (tests/test_bar_structure_decision_neutrality.py) is the proof.
            if _bar_structure is not None:
                _bos, _tb = self._bar_structure_choch_inputs(candle)
                _bar_structure.emit(
                    candle=candle,
                    bar_index=candle_idx - 1,
                    engine_state=engine.state,
                    result=result,
                    prev_state=prev_state,
                    curr_state=curr_state,
                    htf_candle_id=htf.current_htf_id,
                    parent_feed=parent_feed,
                    break_of_structure=_bos,
                    trend_bias=_tb,
                )

            # ── CH-v4-dual-construction-crt-trace-2026-08-30: CRTConstructionTrace ──
            # Same placement discipline as `_bar_structure` immediately above: AFTER
            # `process_candle` has returned, decision already final. `_gate_hooks.guards`
            # was populated (if enabled) by the engine's OWN `reset_bar()`/`record_guard()`
            # calls made during THIS `process_candle`; read it here, before the next bar's
            # `process_candle` calls `reset_bar()` again and clears it.
            if _construction_trace is not None:
                # v2.0.0 envelope. Both reads are decision-neutral: `transition_log` is a
                # legacy audit list nothing branches on, and `get_live_metrics()` is the
                # engine's documented read-only execution-audit API.
                _transitions = [
                    dict(t) for t in engine.state.transition_log[_tlog_mark:]
                ]
                _engine_live = None
                if _construction_trace.cfg.record_resolver_engine:
                    _engine_live = engine.get_live_metrics()
                    _engine_live["risk_score_final"] = state_risk_score(engine.state)
                _construction_trace.emit(
                    bar_index=candle_idx - 1,
                    timestamp=candle.timestamp,
                    htf_id=htf.current_htf_id,
                    engine_state_before=_trace_state_before,
                    engine_state_after=curr_state,
                    engine_action=result.get("action", "NONE"),
                    engine_reason=result.get("reason"),
                    feature_dict=self._construction_trace_feature_dict(candle),
                    gate_hooks=_gate_hooks,
                    engine_live=_engine_live,
                    transitions=_transitions,
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
                    # ── T-16: FAIL CLOSED on a lookup miss ─────────────────────
                    # This used to substitute [0.0] * len(CANONICAL_FEATURES) and warn at most
                    # three times, so a mid-file NaN drop (finalize() tolerates up to
                    # max(300, 2%)) or a timestamp-format break produced a confidently-scored
                    # ZERO vector that flowed on into fusion, BitNet, the orchestrator and the
                    # trade ledger. The leading-warmup cause is now structurally impossible
                    # (the __init__ assert), so a miss here is real corruption.
                    if _fv_idx < 0:
                        _sample = list(self.feature_ts_to_idx.keys())[:1]
                        raise FeatureAlignmentError(
                            f"Feature-vector lookup MISS at candle_idx={candle_idx}: "
                            f"candle timestamp {_ts_key!r} is absent from the feature frame "
                            f"({len(self.feature_ts_to_idx)} rows, sample key "
                            f"{(_sample[0] if _sample else 'empty')!r}). Refusing to substitute a "
                            "zero vector: a zero-filled feature row is not a neutral input, it is "
                            "a fabricated observation that scores through fusion as if measured. "
                            "Causes: a CSV timestamp format the pipeline and loader parse "
                            "differently, or a row dropped mid-file by FeaturePipeline.finalize() "
                            "(NaN in a canonical column)."
                        )
                    feature_vector = self.feature_vectors[_fv_idx].tolist()
                elif not self._features_expected:
                    # No features BY CONSTRUCTION (skip_features=True, or no csv_path — the
                    # programmatic tuner/embedder/test path). Zero vector is the documented
                    # contract for those modes, unchanged by T-16.
                    if not hasattr(self, "_fv_none_logged"):
                        self._fv_none_logged = True
                        self.log.info(
                            "FEATURE DIAG | no feature frame by construction "
                            "(skip_features or no csv_path): batch feature columns are "
                            "zero-filled by contract for this run."
                        )
                    feature_vector = [0.0] * len(CANONICAL_FEATURES)
                else:
                    # Features WERE expected (csv_path set, skip_features=False) but the frame is
                    # absent. __init__ raises before reaching here, so this is a defensive floor
                    # against a future construction path that bypasses it — never a silent zero-fill.
                    raise FeatureAlignmentError(
                        f"Feature vectors are absent although a feature frame was expected "
                        f"(csv_path={self.csv_path!r}, "
                        f"feature_vectors={self.feature_vectors is not None}, "
                        f"ts_to_idx_len={len(self.feature_ts_to_idx)}). The pipeline must have "
                        "been built in __init__; refusing to score trades on zero-filled features."
                    )

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
                    if _p5 is not None and _p5["p_win"] < _p5_min_pwin:
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
                        _feat_map_er.setdefault("atr",       engine.state.atr_abs)
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
                                _feat_dict["atr"] = engine.state.atr_abs
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
                        # it in backtest. Live behavior unchanged. Config-declared —
                        # see _bypass_zone_enabled above (F-058-class fix).
                        _bypass_zone = (
                            _bypass_zone_enabled
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
                        atr            = engine.state.atr_abs,
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
                        # §13 item8 / §9 — ledger completeness. TradeProvenanceV1 had zero
                        # consumers before this; stamped here so every ENTRY line carries the
                        # config version+hash, model pins, and strategy id it was opened under,
                        # plus a feature-vector fingerprint and the CRTConfig threshold snapshot
                        # ("gates_fired") that let this trade through. Best-effort — a failure
                        # here must never block trade logging.
                        _provenance_dict = {}
                        _fv_sha = ""
                        _gates_fired = {}
                        try:
                            import hashlib as _hashlib
                            import json as _json_prov
                            import dataclasses as _dc_prov
                            from journal.trade_provenance_v1_0 import TradeProvenanceV1
                            _provenance_dict = TradeProvenanceV1(
                                trade_id=_orec.trade_id, **self._provenance_base,
                            ).to_dict()
                            _fv_sha = _hashlib.sha256(
                                repr([round(float(v), 8) for v in feature_vector]).encode("utf-8")
                            ).hexdigest()
                            # CRTConfig carries datetime.time (session_windows) — not natively
                            # JSON-serializable. Round-trip through json.dumps(default=str) so
                            # this is a JSON-safe snapshot, not a live CRTConfig object.
                            _gates_fired = _json_prov.loads(
                                _json_prov.dumps(_dc_prov.asdict(self.crt_cfg), default=str)
                            )
                        except Exception as _prov_exc:  # noqa: BLE001
                            self.log.debug("Provenance stamping failed for %s: %s", _orec.trade_id, _prov_exc)
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
                            provenance         = _provenance_dict,
                            feature_vector_sha = _fv_sha,
                            gates_fired        = _gates_fired,
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
                                # Runner stopped at breakeven; blend exit = f@TP1 + (1-f)@entry.
                                # f is execution_planner.partial_tp_fraction (was a hardcoded 0.5
                                # while the config key was strict-read at :1854 and then discarded —
                                # a config illusion: editing the key had zero effect on output).
                                exit_raw = (
                                    _partial_tp_fraction * t.tp1_price
                                    + (1.0 - _partial_tp_fraction) * t.sl_price
                                )
                                reason = "TP1_BE_STOP"
                            else:
                                exit_raw, reason = t.sl_price, "STOPPED"
                        elif "TP2" in action:
                            if _trade_status == "TP1" and _partial_tp_enabled:
                                # Runner reached TP2; blend exit = f@TP1 + (1-f)@TP2 (same key as above)
                                exit_raw = (
                                    _partial_tp_fraction * t.tp1_price
                                    + (1.0 - _partial_tp_fraction) * t.tp2_price
                                )
                                reason = "TP1_TP2"
                            else:
                                exit_raw, reason = t.tp2_price, "TP2"
                        else:
                            exit_raw, reason = t.tp1_price, "TP1"
                        _closed = journal.on_trade_closed(
                            t, exit_raw, reason,
                            candle, candle_idx, engine.state.atr_abs, spread_half,
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
                    # Runner alive at RESET: blend exit = f@TP1 + (1-f)@SL (already at
                    # trail/BE). Same execution_planner.partial_tp_fraction as the two
                    # blend sites in on_candle — this THIRD site was missed in the first
                    # pass and only surfaced because the floor test greps the source.
                    _exit_raw = (
                        _partial_tp_fraction * t.tp1_price
                        + (1.0 - _partial_tp_fraction) * t.sl_price
                    )
                    _reset_reason = "TP1_BE_RESET"
                else:
                    _exit_raw = candle.close
                    _reset_reason = "RESET_CLOSE"
                _closed = journal.on_trade_closed(
                    t, _exit_raw, _reset_reason, candle, candle_idx,
                    engine.state.atr_abs, spread_half,
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

        if _bar_structure is not None:
            _bs_manifest = _bar_structure.close()
            self.log.info(
                "BarStructureSnapshot | rows=%d | %s",
                _bs_manifest["rows"], _bs_manifest["path"],
            )
            self._bar_structure_manifest = _bs_manifest

        if _construction_trace is not None:
            _ct_manifest = _construction_trace.close()
            self.log.info(
                "CRTConstructionTrace | rows=%d | agreement=%s | %s",
                _ct_manifest["rows"], _ct_manifest["agreement_rate"], _ct_manifest["path"],
            )
            self._construction_trace_manifest = _ct_manifest
        # Detach so a later run in the SAME process (e.g. MultiInstrumentRunner) never
        # inherits a stale hooks object across a different engine instance.
        if _gate_hooks is not None:
            engine.baseline_trace = None

        flushed_events.extend(engine.dump_event_log())

        # Force-close at end
        if journal.open_trade and engine.state.active_trade and engine.candle_buffer:
            last = engine.candle_buffer[-1]
            spread_half = last.close * self.cfg.simulated_spread_pct / 2
            _closed = journal.on_trade_closed(
                engine.state.active_trade, last.close,
                "BACKTEST_END", last, candle_idx,
                engine.state.atr_abs, spread_half,
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
    instrument is logged and skipped. A WARN runs but is logged with its report.

    Delegates to `corpus_gate.admit_corpus` so the admission+integrity
    composition has ONE implementation rather than a backtest copy and a
    research copy that can drift apart (the F-052 discipline).

    `enforce=False` preserves this function's skip-not-abort batch semantics, and
    `check_plausibility=False` keeps the delegation BEHAVIOUR-IDENTICAL: the
    gate's D-1..D-4 checks are a research-path capability, and arming a new HARD
    check (D-1 lattice) across every backtest instrument is a separate authorized
    decision, not a side effect of removing a duplicate."""
    try:
        adm = admit_corpus(
            csv_path,
            instrument,
            enforce=False,
            check_plausibility=False,
            log=log,
        )
    except (DatasetAdmissionError, Phase1CandidateError) as exc:
        log.error(
            "[dataset_integrity] R3 admission REJECT %s (%s): %s — skipping.",
            csv_path, instrument, exc,
        )
        return False
    csv_path = adm.filepath
    rep = adm.report
    decision = adm.decision
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
    # R3 Dataset Identity admission (fail-closed for bound corpora).
    symbol_hint = os.path.basename(csv_path).split("_")[0]
    try:
        csv_path = admit_csv_path(csv_path, symbol_hint).filepath
    except (DatasetAdmissionError, Phase1CandidateError) as exc:
        raise DatasetIntegrityError(
            f"corpus admission failed (R3 fail-closed): {exc}"
        ) from exc
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
