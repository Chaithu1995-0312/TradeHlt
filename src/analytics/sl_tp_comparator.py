"""
sl_tp_comparator.py — Dual SL/TP method comparator for backtest productivity analysis.

PURPOSE
-------
Runs both CRT SL/TP (current production method) and Legacy SL/TP (old ExecutionPlanner
ATR-based method) against the same trade entry signals from a completed backtest.
Reports which method produces better outcomes — per-trade and in aggregate.

The comparison is FAIR by design:
  - Same entry signals (same TradeRecords from BacktestRunner)
  - Same entry fill price (slippage already baked in)
  - Same forward candles
  - Only SL/TP placement differs

Architecture position:
    BacktestRunner → TradeRecord list
    SLTPComparator.compare(trade_records, candles) → ComparisonReport

Usage (script):
    python sl_tp_comparator.py \\
        --csv data/EURUSD_M15.csv \\
        --instrument EURUSD \\
        --output results/sl_tp_comparison.json

Usage (library):
    from analytics.sl_tp_comparator import SLTPComparator
    report = SLTPComparator.from_prod_config().compare(trade_records, candles)
    report.print_summary()
    report.save_json("results/sl_tp_comparison.json")
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# [trust-layer WS2B, 2026-06-10] R-multiple metric formulas are sourced from the
# independent oracle so this comparator and the backtest path cannot drift. The
# oracle is the shared authority for win-rate / expectancy / drawdown in R.
from analytics import metrics_oracle as mo
from data_ingestion.ohlcv_schema import require_ohlcv_columns, resolve_ohlcv_headers

log = logging.getLogger("SLTPComparator")

# -- Intent derivation constants (mirrors ExecutionPlannerV1_2._derive_intent) --
_INTENT_LIQ_SWEEP = "LIQ_SWEEP"
_INTENT_PULLBACK  = "PULLBACK"
_INTENT_BREAKOUT  = "BREAKOUT"
_INTENT_REVERSAL  = "REVERSAL"
_INTENT_UNKNOWN   = "UNKNOWN"

# -- Legacy TP multiplier map by intent ---------------------------------------
_DEFAULT_LEGACY_TP_MULTS: dict[str, str] = {
    _INTENT_BREAKOUT:  "legacy_tp_atr_mult_breakout",
    _INTENT_PULLBACK:  "legacy_tp_atr_mult_pullback",
    _INTENT_REVERSAL:  "legacy_tp_atr_mult_reversal",
    _INTENT_LIQ_SWEEP: "legacy_tp_atr_mult_sweep",
    _INTENT_UNKNOWN:   "legacy_tp_atr_mult_breakout",  # fallback
}


# -----------------------------------------------------------------------------
# PURE FUNCTIONS
# -----------------------------------------------------------------------------

def derive_intent_from_features(features: dict, direction: int) -> str:
    """
    Re-derive trade intent from a TradeRecord's feature snapshot.
    Mirrors ExecutionPlannerV1_2._derive_intent exactly.
    """
    sweep         = bool(features.get("sweep_detected", False))
    double_sweep  = bool(features.get("double_sweep",   False))
    retest_depth  = float(features.get("retest_depth",  0.0))
    csr           = int(  features.get("candles_since_retest", 99))
    momentum      = float(features.get("momentum_score", 0.0))
    body_ratio    = float(features.get("body_ratio",     0.0))
    disp_strength = float(features.get("disp_strength",  0.0))
    ema_fast      = float(features.get("ema_fast",       0.0))
    ema_slow      = float(features.get("ema_slow",       0.0))

    if sweep or double_sweep:
        return _INTENT_LIQ_SWEEP
    if 0.3 <= retest_depth <= 0.7 and csr <= 5 and momentum > 0:
        return _INTENT_PULLBACK
    if body_ratio > 0.6 and disp_strength > 1.5:
        return _INTENT_BREAKOUT
    if (ema_fast > ema_slow and direction == -1) or (ema_fast < ema_slow and direction == 1):
        return _INTENT_REVERSAL
    return _INTENT_UNKNOWN


def compute_legacy_levels(
    entry: float,
    direction: int,   # 1=LONG, -1=SHORT
    features: dict,
    cfg: dict,
) -> dict[str, float]:
    """
    Old ExecutionPlanner formula:
        sl  = close ± legacy_sl_atr_mult × ATR
        tp1 = entry ± tp_atr_mult × ATR  (intent-specific)
        tp2 = entry ± tp_atr_mult × 2 × ATR

    Returns {"sl", "tp1", "tp2", "risk_dist", "rr"}.
    rr is the PLANNED RR (tp1 distance / sl distance), not always 1.0.
    """
    close        = float(features.get("close", entry))
    atr          = float(features.get("atr", 0.0))
    intent       = derive_intent_from_features(features, direction)
    sl_mult      = float(cfg.get("legacy_sl_atr_mult", 1.0))
    tp_mult_key  = _DEFAULT_LEGACY_TP_MULTS.get(intent, "legacy_tp_atr_mult_breakout")
    tp_mult      = float(cfg.get(tp_mult_key, 2.0))

    sl = close - sl_mult * atr if direction == 1 else close + sl_mult * atr
    tp1 = entry + direction * tp_mult * atr
    tp2 = entry + direction * tp_mult * 2.0 * atr

    risk_dist = abs(entry - sl)
    rr = abs(tp1 - entry) / risk_dist if risk_dist > 0 else 0.0

    return {
        "sl":        sl,
        "tp1":       tp1,
        "tp2":       tp2,
        "risk_dist": risk_dist,
        "rr":        rr,
        "intent":    intent,
    }


def simulate_exit(
    entry_fill: float,
    direction: int,          # 1=LONG, -1=SHORT
    sl: float,
    tp1: float,
    tp2: float,
    forward_candles: list[dict],
    max_candles: int = 100,
) -> dict[str, Any]:
    """
    Simulate trade exit by walking forward candles.
    Each candle dict must have: {"high": float, "low": float, "close": float}.

    Exit priority per candle (matches BacktestRunner): TP2 first, then SL, then TP1.
    This preserves the same optimism characteristic as BacktestRunner for fair comparison.

    Returns:
        exit_reason:   "TP2" | "TP1" | "SL" | "TIMEOUT"
        exit_price:    raw exit price (no slippage/spread)
        realized_rr:   R-multiple vs SL distance
        candles_held:  how many candles the trade was open
    """
    risk_dist = abs(entry_fill - sl)

    for i, c in enumerate(forward_candles[:max_candles]):
        high  = float(c["high"])
        low   = float(c["low"])
        close = float(c["close"])

        if direction == 1:  # LONG
            tp2_hit = high >= tp2
            sl_hit  = low  <= sl
            tp1_hit = high >= tp1
        else:               # SHORT
            tp2_hit = low  <= tp2
            sl_hit  = high >= sl
            tp1_hit = low  <= tp1

        # Priority: TP2 > SL > TP1  (same as BacktestRunner)
        if tp2_hit:
            raw_rr = abs(tp2 - entry_fill) / risk_dist if risk_dist > 0 else 2.0
            return {"exit_reason": "TP2", "exit_price": tp2, "realized_rr": raw_rr, "candles_held": i + 1}
        if sl_hit:
            raw_rr = -abs(entry_fill - sl) / risk_dist if risk_dist > 0 else -1.0
            return {"exit_reason": "SL",  "exit_price": sl,  "realized_rr": raw_rr, "candles_held": i + 1}
        if tp1_hit:
            raw_rr = abs(tp1 - entry_fill) / risk_dist if risk_dist > 0 else 1.0
            return {"exit_reason": "TP1", "exit_price": tp1, "realized_rr": raw_rr, "candles_held": i + 1}

    # Timeout: close at final candle's close
    if forward_candles:
        last_close = float(forward_candles[min(max_candles, len(forward_candles)) - 1]["close"])
        raw_rr_dir = (last_close - entry_fill) if direction == 1 else (entry_fill - last_close)
        raw_rr = raw_rr_dir / risk_dist if risk_dist > 0 else 0.0
        return {"exit_reason": "TIMEOUT", "exit_price": last_close, "realized_rr": raw_rr,
                "candles_held": min(max_candles, len(forward_candles))}
    return {"exit_reason": "TIMEOUT", "exit_price": entry_fill, "realized_rr": 0.0, "candles_held": 0}


# -----------------------------------------------------------------------------
# AGGREGATE METRICS
# -----------------------------------------------------------------------------

def _aggregate_variant_results(results: list[dict]) -> dict[str, Any]:
    """
    Compute aggregate metrics from a list of simulate_exit() results
    (each augmented with "sl_dist_atr" and "entry" keys by the comparator).
    """
    if not results:
        return {
            "total_trades": 0, "win_rate": 0.0, "expectancy_rr": 0.0,
            "avg_realized_rr": 0.0, "avg_candles_held": 0.0,
            "avg_sl_dist_atr": 0.0, "max_drawdown_r": 0.0,
            "tp2_rate": 0.0, "tp1_rate": 0.0, "sl_rate": 0.0, "timeout_rate": 0.0,
        }

    total = len(results)
    # [WS2B] R-metrics via the shared oracle (same win/loss convention: r>0 win).
    # expectancy_mean ≡ the prior classical form win_rate·avg_win + (1−win_rate)·avg_loss
    # (algebraically the signed mean); max_drawdown_rr ≡ the prior R-equity walk.
    rr            = [r["realized_rr"] for r in results]
    win_rate      = mo.win_rate(rr)
    avg_rr        = mo.expectancy_mean(rr)
    expectancy_rr = mo.expectancy_mean(rr)
    max_dd        = mo.max_drawdown_rr(rr)
    avg_candles   = sum(r["candles_held"] for r in results) / total
    avg_sl_atr    = sum(r.get("sl_dist_atr", 0.0) for r in results) / total

    reasons = [r["exit_reason"] for r in results]
    return {
        "total_trades":   total,
        "win_rate":       round(win_rate, 4),
        "expectancy_rr":  round(expectancy_rr, 4),
        "avg_realized_rr":round(avg_rr, 4),
        "avg_candles_held":round(avg_candles, 1),
        "avg_sl_dist_atr": round(avg_sl_atr, 4),
        "max_drawdown_r": round(max_dd, 4),
        "tp2_rate":       round(reasons.count("TP2") / total, 4),
        "tp1_rate":       round(reasons.count("TP1") / total, 4),
        "sl_rate":        round(reasons.count("SL")  / total, 4),
        "timeout_rate":   round(reasons.count("TIMEOUT") / total, 4),
    }


# -----------------------------------------------------------------------------
# RESULT DATACLASSES
# -----------------------------------------------------------------------------

@dataclass
class ComparisonReport:
    """Full comparison report between CRT and Legacy SL/TP methods."""

    trades_compared:  int
    primary_metric:   str                   # e.g. "expectancy_rr"

    crt:     dict[str, Any] = field(default_factory=dict)   # aggregate metrics
    legacy:  dict[str, Any] = field(default_factory=dict)

    winner:              str   = "tie"      # "crt" | "legacy" | "tie"
    winner_delta:        float = 0.0        # winning method - losing method on primary_metric
    recommendation:      str   = ""

    per_trade: list[dict] = field(default_factory=list)

    def print_summary(self) -> None:
        sep = "-" * 60
        print(f"\n{sep}")
        print(f"  SL/TP METHOD COMPARISON  ({self.trades_compared} trades)")
        print(sep)
        cols = ["win_rate", "expectancy_rr", "avg_realized_rr",
                "avg_sl_dist_atr", "tp2_rate", "sl_rate", "max_drawdown_r"]
        header = f"{'Metric':<24} {'CRT':>10} {'Legacy':>10} {'Delta':>10}"
        print(header)
        print("-" * len(header))
        for col in cols:
            a = self.crt.get(col, 0.0)
            b = self.legacy.get(col, 0.0)
            delta = a - b
            arrow = "+" if delta > 0 else ("-" if delta < 0 else "=")
            print(f"  {col:<22} {a:>10.4f} {b:>10.4f} {arrow}{abs(delta):>9.4f}")
        print(sep)
        winner_label = self.winner.upper() if self.winner != "tie" else "TIE"
        print(f"  WINNER: {winner_label}  (delta_{self.primary_metric}={self.winner_delta:+.4f})")
        print(f"  {self.recommendation}")
        print(sep)

    def to_dict(self) -> dict:
        return asdict(self)

    def save_json(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        log.info("ComparisonReport saved → %s", path)


# -----------------------------------------------------------------------------
# COMPARATOR
# -----------------------------------------------------------------------------

class SLTPComparator:
    """
    Compares CRT vs Legacy SL/TP methods on identical trade entries.

    The comparison:
      Method A (CRT):    sl/tp already stored in TradeRecord — no re-computation
      Method B (Legacy): sl/tp re-computed from features at entry, then forward-simulated

    Both methods use the same entry_price_fill (slippage already captured in original
    TradeRecord) so the comparison isolates SL/TP placement quality only.
    """

    def __init__(self, cfg: dict) -> None:
        """
        cfg: contents of the "sl_tp_comparison" config section.
        """
        self._cfg            = cfg
        self._max_candles    = int(cfg.get("max_candles_per_trade", 100))
        self._primary_metric = str(cfg.get("primary_metric", "expectancy_rr"))

    @classmethod
    def from_prod_config(cls) -> "SLTPComparator":
        from config_layer.production_config import get_prod_section
        return cls(get_prod_section("sl_tp_comparison"))

    # -- Main entry point ------------------------------------------------------

    def compare(
        self,
        trade_records: list,
        candles: list[dict],
    ) -> ComparisonReport:
        """
        Parameters
        ----------
        trade_records : list of TradeRecord (from BacktestRunner or a saved JSON list)
        candles       : full ordered candle list as dicts with keys
                        {"high", "low", "close", "open", "timestamp"}.
                        Must be the same series as the original backtest.

        Returns
        -------
        ComparisonReport
        """
        if not trade_records:
            log.warning("SLTPComparator: no trade records provided — empty report")
            return ComparisonReport(trades_compared=0, primary_metric=self._primary_metric)

        crt_results:    list[dict] = []
        legacy_results: list[dict] = []
        per_trade:      list[dict] = []

        for rec in trade_records:
            # Support both dataclass TradeRecord and plain dict (from saved JSON)
            tr = rec if isinstance(rec, dict) else self._record_to_dict(rec)

            entry_fill = float(tr.get("entry_price_fill") or tr.get("entry_price_raw", 0.0))
            direction  = 1 if str(tr.get("direction", "LONG")).upper() == "LONG" else -1
            features   = tr.get("features", {})
            atr        = float(features.get("atr", tr.get("live_atr", 1.0)) or 1.0)

            # -- CRT result: directly from TradeRecord (no re-simulation) ------
            crt_exit_rr  = float(tr.get("pnl_rr_net") or tr.get("pnl_rr_raw", 0.0))
            crt_exit_rsn = str(tr.get("exit_reason", "UNKNOWN"))
            crt_candles  = int(tr.get("candle_close", 0)) - int(tr.get("candle_open", 0))
            sl_crt       = float(tr.get("sl_price", tr.get("sl", 0.0)))
            sl_dist_crt_atr = abs(entry_fill - sl_crt) / atr if atr > 0 else 0.0

            crt_row = {
                "exit_reason":   crt_exit_rsn,
                "realized_rr":   crt_exit_rr,
                "candles_held":  max(0, crt_candles),
                "sl_dist_atr":   round(sl_dist_crt_atr, 4),
                "entry":         entry_fill,
            }

            # -- Legacy result: re-compute levels, then simulate forward -------
            legacy_levels = compute_legacy_levels(entry_fill, direction, features, self._cfg)
            sl_leg   = legacy_levels["sl"]
            tp1_leg  = legacy_levels["tp1"]
            tp2_leg  = legacy_levels["tp2"]
            sl_dist_leg_atr = abs(entry_fill - sl_leg) / atr if atr > 0 else 0.0

            candle_open = int(tr.get("candle_open", 0))
            forward     = candles[candle_open + 1 : candle_open + 1 + self._max_candles]
            leg_exit    = simulate_exit(
                entry_fill, direction, sl_leg, tp1_leg, tp2_leg,
                forward, self._max_candles,
            )
            leg_exit["sl_dist_atr"] = round(sl_dist_leg_atr, 4)
            leg_exit["entry"]       = entry_fill

            crt_results.append(crt_row)
            legacy_results.append(leg_exit)

            per_trade.append({
                "trade_id":      tr.get("trade_id", "?"),
                "direction":     "LONG" if direction == 1 else "SHORT",
                "intent":        legacy_levels["intent"],
                "entry_fill":    round(entry_fill, 6),
                "crt": {
                    "sl":         round(sl_crt, 6),
                    "tp1":        round(float(tr.get("tp1_price") or tr.get("tp1", 0)), 6),
                    "tp2":        round(float(tr.get("tp2_price") or tr.get("tp2", 0)), 6),
                    "sl_dist_atr":round(sl_dist_crt_atr, 4),
                    "exit_reason":crt_exit_rsn,
                    "realized_rr":round(crt_exit_rr, 4),
                },
                "legacy": {
                    "sl":          round(sl_leg, 6),
                    "tp1":         round(tp1_leg, 6),
                    "tp2":         round(tp2_leg, 6),
                    "sl_dist_atr": round(sl_dist_leg_atr, 4),
                    "exit_reason": leg_exit["exit_reason"],
                    "realized_rr": round(leg_exit["realized_rr"], 4),
                    "planned_rr":  round(legacy_levels["rr"], 4),
                },
            })

        agg_crt    = _aggregate_variant_results(crt_results)
        agg_legacy = _aggregate_variant_results(legacy_results)

        winner, delta, recommendation = self._determine_winner(agg_crt, agg_legacy)

        return ComparisonReport(
            trades_compared  = len(trade_records),
            primary_metric   = self._primary_metric,
            crt              = agg_crt,
            legacy           = agg_legacy,
            winner           = winner,
            winner_delta     = delta,
            recommendation   = recommendation,
            per_trade        = per_trade,
        )

    # -- Winner determination --------------------------------------------------

    def _determine_winner(
        self,
        crt: dict,
        legacy: dict,
    ) -> tuple[str, float, str]:
        m   = self._primary_metric
        a   = crt.get(m, 0.0)
        b   = legacy.get(m, 0.0)
        delta = round(a - b, 6)

        if abs(delta) < 1e-4:
            return "tie", delta, (
                f"Both methods statistically equivalent on {m} "
                f"(CRT={a:.4f}, Legacy={b:.4f}, delta_<0.0001). Keep CRT (simpler, single formula)."
            )

        if a > b:
            return "crt", delta, (
                f"CRT wins on {m}: CRT={a:.4f} vs Legacy={b:.4f} (delta_={delta:+.4f}). "
                f"Current production method is optimal. "
                f"Also note: CRT SL is tighter (avg {crt.get('avg_sl_dist_atr', 0):.2f}R vs "
                f"{legacy.get('avg_sl_dist_atr', 0):.2f}R ATR), "
                f"TP2 rate CRT={crt.get('tp2_rate', 0):.1%} vs Legacy={legacy.get('tp2_rate', 0):.1%}."
            )
        else:
            return "legacy", abs(delta), (
                f"Legacy wins on {m}: Legacy={b:.4f} vs CRT={a:.4f} (delta_={abs(delta):+.4f}). "
                f"Consider re-introducing legacy SL/TP params. "
                f"Review per_trade entries where legacy.realized_rr > crt.realized_rr to confirm pattern."
            )

    # -- Dict conversion for dict-typed TradeRecord ----------------------------

    @staticmethod
    def _record_to_dict(tr: Any) -> dict:
        """Convert a dataclass TradeRecord to a plain dict."""
        try:
            from dataclasses import asdict as _asdict
            return _asdict(tr)
        except Exception:
            return vars(tr) if hasattr(tr, "__dict__") else {}

    # -- Candle loading helper -------------------------------------------------

    @staticmethod
    def load_candles_from_csv(csv_path: str) -> list[dict]:
        """
        Load candle data from CSV into list of dicts.
        Expects columns: timestamp (or datetime), open, high, low, close.
        Same loading logic as BacktestRunner._read_csv.
        """
        import csv as _csv
        candles = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = _csv.DictReader(f)
            # Enforce the full six-column dataset contract even though this
            # comparator only consumes timestamp + OHLC.
            resolved = resolve_ohlcv_headers(reader.fieldnames or [])
            require_ohlcv_columns(
                resolved.keys(), source=f"Historical dataset {csv_path}"
            )
            ts_key, o_key, h_key, l_key, c_key = (
                resolved["timestamp"], resolved["open"], resolved["high"],
                resolved["low"], resolved["close"],
            )
            for row in reader:
                candles.append({
                    "timestamp": row[ts_key],
                    "open":  float(row[o_key]),
                    "high":  float(row[h_key]),
                    "low":   float(row[l_key]),
                    "close": float(row[c_key]),
                })
        log.info("Loaded %d candles from %s", len(candles), csv_path)
        return candles


# -----------------------------------------------------------------------------
# INTEGRATION HELPER — run backtest then compare
# -----------------------------------------------------------------------------

def _load_trades_from_csv(path: str) -> list[dict]:
    """
    Read the trades CSV written by BacktestRunner's ReportWriter and reconstruct
    dicts that compare() can consume.

    Remaps CSV column names → TradeRecord field names:
        entry_fill  → entry_price_fill
        entry_raw   → entry_price_raw
        sl          → sl_price
        tp1         → tp1_price
        tp2         → tp2_price
        candle_idx  → candle_open

    Any column whose name appears in CANONICAL_FEATURES is grouped under a nested
    "features" dict (so compare()._vol_score / _intent_score etc. find their keys).
    """
    import csv as _csv
    try:
        from features.feature_schema import CANONICAL_FEATURES
        _feat_set: set[str] = set(CANONICAL_FEATURES)
    except Exception:
        _feat_set = set()

    _col_map = {
        "entry_fill": "entry_price_fill",
        "entry_raw":  "entry_price_raw",
        "sl":         "sl_price",
        "tp1":        "tp1_price",
        "tp2":        "tp2_price",
        "candle_idx": "candle_open",
    }

    result: list[dict] = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                rec: dict      = {}
                features: dict = {}
                for k, v in row.items():
                    if k in _feat_set:
                        try:
                            features[k] = float(v)
                        except (ValueError, TypeError):
                            features[k] = 0.0
                    else:
                        mapped_k = _col_map.get(k, k)
                        # Normalise BacktestRunner exit reasons → comparator names
                        if mapped_k == "exit_reason":
                            v = "SL" if v == "STOPPED" else ("TIMEOUT" if v == "RESET_CLOSE" else v)
                        rec[mapped_k] = v
                rec["features"] = features
                result.append(rec)
    except FileNotFoundError:
        log.warning("Trades CSV not found at %s — no trade records loaded", path)
    return result


def run_comparison_from_backtest(
    csv_path: str,
    instrument: str = "UNKNOWN",
    cfg_override: Optional[dict] = None,
    output_path: Optional[str] = None,
) -> ComparisonReport:
    """
    Convenience wrapper: runs BacktestRunner, feeds results directly to SLTPComparator.

    Parameters
    ----------
    csv_path    : path to OHLCV CSV
    instrument  : instrument label
    cfg_override: optional overrides for sl_tp_comparison config
    output_path : if provided, saves report JSON here

    Returns
    -------
    ComparisonReport
    """
    # Import here to avoid circular deps at module level
    from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader

    bt_cfg     = BacktestConfig.from_prod_config(instrument=instrument)
    tmp_dir    = "results/sl_tp_comparison_tmp"
    loader     = CandleLoader(csv_path, instrument)
    runner     = BacktestRunner(bt_cfg, csv_path=csv_path)

    log.info("Running backtest: %s ...", csv_path)
    runner.run(loader.stream(), loader.count(), output_dir=tmp_dir)

    # ReportWriter writes to {output_dir}/run_{timestamp}_{instrument}/{instrument}_trades.csv
    # Find the most recently modified trades CSV under tmp_dir
    import glob as _glob
    pattern = str(Path(tmp_dir) / "**" / f"{instrument}_trades.csv")
    matches = sorted(_glob.glob(pattern, recursive=True), key=lambda p: Path(p).stat().st_mtime)
    if not matches:
        log.warning("No trades CSV found under %s — comparison will be empty", tmp_dir)
        trade_records: list[dict] = []
    else:
        trades_csv = matches[-1]   # most recently written
        trade_records = _load_trades_from_csv(trades_csv)
        log.info("Loaded %d trade records from %s", len(trade_records), trades_csv)

    if not trade_records:
        log.warning("No trades in backtest — comparison will be empty")

    _COMP_DEFAULTS = {
        "legacy_sl_atr_mult": 1.0, "legacy_tp_atr_mult_breakout": 2.0,
        "legacy_tp_atr_mult_pullback": 1.5, "legacy_tp_atr_mult_reversal": 1.0,
        "legacy_tp_atr_mult_sweep": 1.2, "primary_metric": "expectancy_rr",
        "max_candles_per_trade": 100, "output_path": "results/sl_tp_comparison.json",
    }
    try:
        from config_layer.production_config import get_prod_section
        _prod_comp = get_prod_section("sl_tp_comparison")
    except (RuntimeError, KeyError):
        log.warning("'sl_tp_comparison' section not in prod config — using built-in defaults")
        _prod_comp = {}
    comp_cfg = {**_COMP_DEFAULTS, **_prod_comp, **(cfg_override or {})}
    comp_cfg.pop("_comment", None)

    candles    = SLTPComparator.load_candles_from_csv(csv_path)
    comparator = SLTPComparator(comp_cfg)
    report     = comparator.compare(trade_records, candles)

    if output_path or comp_cfg.get("output_path"):
        report.save_json(output_path or comp_cfg["output_path"])

    return report


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Compare CRT vs Legacy SL/TP methods on the same backtest data"
    )
    parser.add_argument("--csv",        required=True, help="Path to OHLCV CSV file")
    parser.add_argument("--instrument", default="UNKNOWN")
    parser.add_argument("--output",     default=None,  help="Output JSON path (overrides config)")
    parser.add_argument("--metric",     default=None,  help="Primary comparison metric override")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    overrides: dict = {}
    if args.metric:
        overrides["primary_metric"] = args.metric

    report = run_comparison_from_backtest(
        csv_path   = args.csv,
        instrument = args.instrument,
        cfg_override = overrides,
        output_path  = args.output,
    )
    report.print_summary()


if __name__ == "__main__":
    _cli()
