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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # top-level so tests can monkeypatch backtest_v2.pd

from features.feature_schema import CANONICAL_FEATURES
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
        session: str, atr: float, spread_half: float, feature_vector,
        live_metrics: dict = None,   # Universe-B live state from CRTEngine.get_live_metrics()
    ) -> None:
        # [G1+G2] Compute realistic fill prices
        _, _, _, _ = self.slip.compute_fill_prices(
            trade.entry_price, trade.entry_price,
            trade.direction, atr, spread_half,
        )
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
# BACKTEST RUNNER v2
# ─────────────────────────────────────────────────────────────────

class BacktestRunner:
    def __init__(self, bt_config: BacktestConfig, csv_path: str = None,
                 skip_features: bool = False):
        """
        skip_features=True  — skips FeaturePipeline entirely (csv_path still recorded
        but not processed).  Use for tuner workers where fitness is derived from
        metric scalars only and feature columns in _trades.csv are not needed.
        All other behaviour (candle loop, CRT engine, metrics) is unchanged.
        """
        self.cfg     = bt_config
        self.log     = bt_log
        self.crt_cfg = bt_config.crt_config or CRTConfig()
        self.csv_path = csv_path
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
                import traceback as _tb
                bt_log.warning(
                    "FeaturePipeline init FAILED for %s — "
                    "all feature columns will default to 0.0.\n"
                    "Exception: %s\nTraceback:\n%s",
                    self.csv_path, _fp_err, _tb.format_exc(),
                )
                self.feature_vectors = None
                self.feature_ts_to_idx = {}

        # Phase 2: FeatureMonitor for drift detection in replay loop
        try:
            from features.feature_monitor import FeatureMonitor
            self._monitor = FeatureMonitor(window_size=500)
            self._monitor_available = True
        except Exception:
            self._monitor = None
            self._monitor_available = False
    def run(self, candle_source: Iterator[Candle], total_candles: int,
            output_dir: str = "results") -> BacktestMetrics:
        
    # Ensure vectors is a list of lists (or numpy array)
        engine  = CRTEngine(self.crt_cfg)
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

        prev_candle: Optional[Candle] = None

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
                if journal.open_trade and engine.state.active_trade:
                    spread_half = candle.close * self.cfg.simulated_spread_pct / 2
                    journal.on_trade_closed(
                        engine.state.active_trade, candle.open,
                        "GAP_RESET_CLOSE", candle, candle_idx,
                        engine.state.atr, spread_half,
                    )
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

            action = result.get("action", "NONE")

            if "TRADE_OPENED" in action and engine.state.active_trade:
                last_risk_score = engine.state.risk_score.final \
                                  if engine.state.risk_score else 0.0
                last_session = self._session(candle.timestamp)
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

                # Phase 2: update FeatureMonitor and log drift signals
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
                                "features strongly OOD (Z>3.0).",
                                candle_idx, self.cfg.instrument,
                            )
                        elif _sev == "soft":
                            self.log.debug(
                                "FeatureMonitor: soft drift at candle %d (%s).",
                                candle_idx, self.cfg.instrument,
                            )
                    except Exception:
                        pass

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
                    live_metrics   = result.get("live_metrics", {}),
                )
                state_path = []

            elif "TRADE_STOPPED" in action or "TRADE_TP2" in action or "TRADE_TP1" in action:
                if journal.open_trade and engine.state.active_trade:
                    t = engine.state.active_trade
                    if "STOPPED" in action:
                        exit_raw, reason = t.sl_price, "STOPPED"
                    elif "TP2" in action:
                        exit_raw, reason = t.tp2_price, "TP2"
                    else:
                        exit_raw, reason = t.tp1_price, "TP1"
                    journal.on_trade_closed(
                        t, exit_raw, reason,
                        candle, candle_idx, engine.state.atr, spread_half,
                    )

            elif action.startswith("RISK_REJECTED"):
                reason = action.split(":", 1)[1] if ":" in action else "unknown"
                score  = engine.state.risk_score.final if engine.state.risk_score else 0.0
                journal.on_rejected(reason, candle_idx, candle.timestamp, state_path, score)
                state_path = []

            elif action == "RESET" and journal.open_trade and engine.state.active_trade:
                journal.on_trade_closed(
                    engine.state.active_trade, candle.close,
                    "RESET_CLOSE", candle, candle_idx,
                    engine.state.atr, spread_half,
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
        return "OFF_SESSION"

    def _print_summary(self, m: BacktestMetrics) -> None:
        self.log.info("─" * 55)
        self.log.info(f"  {m.instrument} | {m.approved_trades} trades | "
                      f"WR={m.win_rate:.1%} | AvgRR={m.avg_rr_net:.2f}R | "
                      f"PnL(net)={m.total_pnl_rr_net:+.2f}R | "
                      f"MaxDD={m.max_drawdown_pct:.1%}")
        self.log.info("─" * 55)


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
    ap.add_argument("--sweep-age",    type=int,   default=20)
    ap.add_argument("--decay",        type=float, default=0.10)
    ap.add_argument("--threshold",    type=float, default=0.75)
    ap.add_argument("--config", help="JSON config file (not used by CRT backtest)")
    args = ap.parse_args()

    crt_cfg = CRTConfig(
        max_sweep_age_candles=args.sweep_age,
        score_decay_lambda=args.decay,
        score_threshold=args.threshold,
    )
    # Load base config from JSON; CLI args override only when explicitly passed
    cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
    if args.htf         is not None: cfg.htf_candles_per_range = args.htf
    if args.warmup      is not None: cfg.warmup_candles        = args.warmup
    if args.capital     is not None: cfg.initial_capital       = args.capital
    if args.risk_pct    is not None: cfg.risk_pct_per_trade    = args.risk_pct
    if args.spread      is not None: cfg.simulated_spread_pct  = args.spread
    if args.no_slip:                  cfg.slippage_enabled      = False
    if args.no_gap_reset:             cfg.gap_reset_enabled     = False

    # Optional: additional JSON override file (informational only)
    if args.config:
        with open(args.config) as f:
            overrides = json.load(f)
        safe_print(f"Config overrides loaded from {args.config} (not applied to CRT backtest)")

    csv_path = Path(args.csv)

    if csv_path.is_dir() or args.instrument.upper() == "ALL":
        # Multi-instrument mode
        MultiInstrumentRunner(str(csv_path), args.output, cfg).run_all()
    else:
        # Single instrument
        cfg.instrument = args.instrument if args.instrument != "AUTO" else csv_path.stem.upper()
        cfg.pip_size = MultiInstrumentRunner.INSTRUMENT_PIP.get(cfg.instrument, 0.0001)
        loader = CandleLoader(str(csv_path), cfg.instrument)
        runner = BacktestRunner(cfg, csv_path=str(csv_path))
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
            "volume":     float(row.get("volume", 0.0)),
        }

        result = runner.run(input_data, context)
        results.append(result)

    return results


if __name__ == "__main__":
    main()
