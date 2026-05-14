"""
strategy_backtest.py
================================================================================
StrategyBacktester — per-strategy historical performance measurement.

Loads M15 OHLCV CSV data, runs the FeaturePipeline to derive indicators, then
simulates each of the 10 strategies candle-by-candle. Trades are forward-
simulated: for each BUY/SELL signal the next max_forward_candles bars are
scanned to see if price hits TP (win) or SL (loss) first.

Returns per-strategy metrics compatible with MultiStrategyValidator and the
governance ValidationReport format.

Usage
-----
    from governance.strategy_backtest import StrategyBacktester

    bt = StrategyBacktester(pair="EURUSD", timeframe="M15")
    results = bt.run("data/EURUSD_M15.csv")
    # results: {strategy_id: StrategyMetrics}

Config: reads strategy_engine params from production config automatically.
================================================================================
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

import pandas as pd

from features.feature_pipeline import FeaturePipeline          # type: ignore
from features.feature_schema import CANONICAL_FEATURES          # type: ignore
from strategies.strategy_orchestrator import _STRATEGY_CLASSES  # type: ignore
from utils.logging_config import get_flow_logger                # type: ignore

logger = get_flow_logger("COLLECTOR")

_USD_TO_INR = 84.0
_WARMUP     = 60   # candles to skip before counting signals
_MAX_FWD    = 40   # max candles to look ahead for SL/TP hit


@dataclass
class StrategyMetrics:
    """Per-strategy backtest result."""
    strategy_id:    str
    trade_count:    int       = 0
    win_count:      int       = 0
    loss_count:     int       = 0
    timeout_count:  int       = 0
    total_pnl_inr:  float     = 0.0
    gross_profit:   float     = 0.0
    gross_loss:     float     = 0.0
    max_drawdown:   float     = 0.0   # peak-to-trough in INR
    win_rate:       float     = 0.0   # wins / (wins + losses)
    profit_factor:  float     = 0.0   # gross_profit / |gross_loss|
    expectancy_inr: float     = 0.0   # avg P&L per trade
    score:          float     = 0.0   # composite governance score

    def finalise(self) -> None:
        decided = self.win_count + self.loss_count
        if decided > 0:
            self.win_rate = round(self.win_count / decided, 4)
        if self.gross_loss > 0:
            self.profit_factor = round(self.gross_profit / self.gross_loss, 3)
        if self.trade_count > 0:
            self.expectancy_inr = round(self.total_pnl_inr / self.trade_count, 2)
        self.score = self._compute_score()

    def _compute_score(self) -> float:
        """Composite score in [0, 1] used by MultiStrategyValidator."""
        if self.trade_count < 5:
            return 0.0
        wr_score  = min(1.0, max(0.0, (self.win_rate - 0.30) / 0.40))
        pf_score  = min(1.0, max(0.0, (self.profit_factor - 1.0) / 2.0))
        dd_score  = max(0.0, 1.0 - self.max_drawdown / 50_000.0)
        vol_score = min(1.0, self.trade_count / 30.0)
        return round(0.35 * wr_score + 0.30 * pf_score + 0.20 * dd_score + 0.15 * vol_score, 4)

    def to_dict(self) -> dict:
        return {
            "strategy_id":    self.strategy_id,
            "trades":         self.trade_count,
            "wins":           self.win_count,
            "losses":         self.loss_count,
            "timeouts":       self.timeout_count,
            "win_rate":       self.win_rate,
            "profit_factor":  self.profit_factor,
            "expectancy_inr": self.expectancy_inr,
            "total_pnl_inr":  round(self.total_pnl_inr, 2),
            "max_drawdown":   round(self.max_drawdown, 2),
            "score":          self.score,
        }


class StrategyBacktester:
    """
    Runs all 10 strategies candle-by-candle against a CSV and returns
    per-strategy StrategyMetrics.

    Feature contract: builds CANONICAL_FEATURES dict first (same format as
    BacktestRunner / live_engine_hook), then merges strategy-specific extras.
    If backtest and live diverge on features, live_engine_hook is updated to
    match — backtest is the reference implementation.

    Forward-sim (governance-specific — not a production path):
      This loop exists ONLY to measure per-strategy win/loss rates for the
      governance gate in MultiStrategyValidator.  It does NOT replace
      BacktestRunner.  For system-level metrics use BacktestRunner directly.

      BUY signal:  scan subsequent candles; win if high >= tp, loss if low <= sl.
      SELL signal: scan subsequent candles; win if low <= tp, loss if high >= sl.
      If neither in max_forward_candles → TIMEOUT (excluded from win/loss ratio).
    """

    def __init__(
        self,
        pair: str = "EURUSD",
        timeframe: str = "M15",
        warmup: int = _WARMUP,
        max_forward_candles: int = _MAX_FWD,
    ) -> None:
        self._pair     = pair
        self._tf       = timeframe
        self._warmup   = warmup
        self._max_fwd  = max_forward_candles

    def run(self, csv_path: str) -> Dict[str, StrategyMetrics]:
        """
        Run all 10 strategies against a CSV file.

        Returns {strategy_id: StrategyMetrics} for every strategy class
        registered in _STRATEGY_CLASSES.
        """
        try:
            df = pd.read_csv(csv_path, parse_dates=["timestamp"])
        except (FileNotFoundError, OSError) as exc:
            logger.warning("StrategyBacktester: cannot open %s: %s", csv_path, exc)
            return {}
        if len(df) < self._warmup + self._max_fwd + 10:
            logger.warning(
                "StrategyBacktester: CSV too short (%d rows) for %s — skipping.",
                len(df), csv_path,
            )
            return {}

        logger.info(
            "StrategyBacktester: loaded %d candles from %s", len(df), csv_path
        )

        pipeline = FeaturePipeline(df)
        try:
            features_df, _ = pipeline.run()
        except Exception as exc:
            logger.warning("StrategyBacktester: FeaturePipeline failed: %s", exc)
            return {}

        # Instantiate all strategy objects
        strategies = {}
        for sid, cls in _STRATEGY_CLASSES.items():
            try:
                strategies[sid] = cls(pair=self._pair, timeframe=self._tf)
            except Exception as exc:
                logger.warning("StrategyBacktester: cannot init %s: %s", sid, exc)

        metrics: Dict[str, StrategyMetrics] = {
            sid: StrategyMetrics(strategy_id=sid) for sid in strategies
        }

        highs  = features_df["high"].values
        lows   = features_df["low"].values
        n      = len(features_df)

        for i in range(self._warmup, n - self._max_fwd):
            row = features_df.iloc[i]
            # Build canonical feature dict — identical format to BacktestRunner.
            # This ensures governance validation uses the same feature contract
            # as production.  Strategy-specific extras are merged on top.
            feat = {f: float(row.get(f, 0.0)) for f in CANONICAL_FEATURES}
            feat.update(self._row_to_features(row))
            candle = {
                "open":   float(row.get("open",  0.0)),
                "high":   float(row.get("high",  0.0)),
                "low":    float(row.get("low",   0.0)),
                "close":  float(row.get("close", 0.0)),
                "volume": float(row.get("volume", 1.0)),
            }

            for sid, strategy in strategies.items():
                try:
                    result = strategy.compute(feat, candle)
                except Exception:
                    continue

                if not result.is_actionable():
                    continue
                if result.entry <= 0.0 or result.sl <= 0.0 or result.tp <= 0.0:
                    continue

                # Forward-scan for SL/TP hit
                win, loss = False, False
                for j in range(i + 1, min(i + 1 + self._max_fwd, n)):
                    h, l = highs[j], lows[j]
                    if result.signal == "BUY":
                        if h >= result.tp:
                            win = True; break
                        if l <= result.sl:
                            loss = True; break
                    else:  # SELL
                        if l <= result.tp:
                            win = True; break
                        if h >= result.sl:
                            loss = True; break

                m = metrics[sid]
                m.trade_count += 1
                if win:
                    m.win_count    += 1
                    m.gross_profit += result.tp_inr
                    m.total_pnl_inr += result.tp_inr
                elif loss:
                    m.loss_count   += 1
                    m.gross_loss   += result.sl_inr
                    m.total_pnl_inr -= result.sl_inr
                else:
                    m.timeout_count += 1

                # Running drawdown tracker (simplified: worst contiguous loss run)
                if m.total_pnl_inr < 0 and abs(m.total_pnl_inr) > m.max_drawdown:
                    m.max_drawdown = abs(m.total_pnl_inr)

        for m in metrics.values():
            m.finalise()
            logger.info(
                "StrategyBacktester: %s | trades=%d win_rate=%.1f%% PF=%.2f score=%.3f",
                m.strategy_id, m.trade_count, m.win_rate * 100,
                m.profit_factor, m.score,
            )

        return metrics

    @staticmethod
    def _row_to_features(row: "pd.Series") -> dict:
        """Convert a FeaturePipeline output row to strategy feature dict."""
        def _f(key, default=0.0):
            v = row.get(key, default)
            return float(v) if v is not None and str(v) not in ("nan", "NaN") else default

        def _b(key):
            v = row.get(key, 0.0)
            try:
                return bool(float(v) > 0.5)
            except (TypeError, ValueError):
                return False

        session_val = row.get("session", "london")
        if isinstance(session_val, (int, float)):
            session_map = {0: "asia", 1: "london", 2: "new_york", 3: "overlap"}
            session_val = session_map.get(int(session_val), "london")

        vol_regime = row.get("volatility_regime", "RANGING")
        if isinstance(vol_regime, (int, float)):
            vol_regime = "RANGING"

        return {
            "open":   _f("open"),   "high":  _f("high"),
            "low":    _f("low"),    "close": _f("close"),
            "volume": _f("volume"),
            "atr":    _f("atr"),
            "rsi_14": _f("rsi_14"),
            "trend_bias":   str(
                {-1: "bearish", 0: "neutral", 1: "bullish"}.get(
                    int(_f("trend_bias", 0)), "neutral"
                )
            ),
            "sweep_detected":   _b("sweep_detected"),
            "break_of_structure": abs(float(row.get("break_of_structure", 0.0))) > 0.5,
            "higher_high":      _b("higher_high"),
            "lower_low":        _b("lower_low"),
            "swing_high":       _f("last_swing_high_price"),
            "swing_low":        _f("last_swing_low_price"),
            "disp_strength":    _f("disp_strength"),
            "retest_depth":     _f("retest_depth"),
            "candles_since_retest": int(_f("candles_since_retest")),
            "body_ratio":       _f("body_ratio"),
            "liquidity_sweep":  _b("liquidity_sweep"),
            "double_sweep":     _b("double_sweep"),
            "volume_ratio":     _f("volume_ratio", 1.0),
            "momentum_score":   _f("momentum_score"),
            "bb_upper":         _f("bb_upper"),
            "bb_lower":         _f("bb_lower"),
            "rejection_wick":   _b("upper_wick"),
            "is_inside_bar":    False,
            "ema_fast":         _f("ema_fast"),
            "ema_slow":         _f("ema_slow"),
            "ema_spread":       _f("ema_spread"),
            "body_size":        _f("body_size"),
            "wick_size":        _f("wick_size"),
            "pattern_score":    0.5,
            "session":          session_val,
            "hour_of_day":      _f("hour_of_day"),
            "macd_line":        _f("macd_line"),
            "macd_signal":      _f("macd_signal"),
            "macd_hist":        _f("macd_hist"),
            "zone_strength":    0.5,
            "trend_strength":   _f("trend_strength"),
            "volatility_ratio": _f("volatility_ratio", 1.0),
            "volatility_regime": str(vol_regime),
            "spread_pct":       0.0001,
        }
