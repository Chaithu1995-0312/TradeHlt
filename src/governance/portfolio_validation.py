"""
╔══════════════════════════════════════════════════════════════════════╗
║  CRT ENGINE — PORTFOLIO VALIDATION v1.0                              ║
║  Multi-market edge universality test                                 ║
║                                                                      ║
║  Question: Is CRT + Gaussian a pattern or a law of markets?          ║
╚══════════════════════════════════════════════════════════════════════╝

Usage:
    python portfolio_validation.py
    python portfolio_validation.py --output results/portfolio
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))
from runtime.backtest_v2 import (
    BacktestConfig, BacktestMetrics, BacktestRunner,
    CandleLoader, TradeRecord,
)
from config_layer.config_builder import ConfigBuilder

# ── Load portfolio section from production config; fall back to defaults ───────
try:
    from config_layer.production_config import get_prod_section as _get_section
    _PV_CFG = _get_section("portfolio")
except Exception:
    _PV_CFG = {}

_DEFAULT_INITIAL_CAPITAL:    float = _PV_CFG.get("initial_capital",       100_000.0)
_DEFAULT_OUTPUT_DIR:         str   = _PV_CFG.get("output_dir",            "results/portfolio")
_DEFAULT_RISK_PCT:           float = _PV_CFG.get("risk_pct",              0.01)
_DEFAULT_SLIPPAGE_FRACTION:  float = _PV_CFG.get("slippage_atr_fraction", 0.08)
_DEFAULT_WARMUP_CANDLES:     int   = _PV_CFG.get("warmup_candles",        100)

# ─────────────────────────────────────────────────────────────────
# INSTRUMENT REGISTRY
# ─────────────────────────────────────────────────────────────────

@dataclass
class InstrumentConfig:
    name:           str
    csv_path:       str
    pip_size:       float
    spread_pct:     float   # simulated spread as % of price
    htf_candles:    int = 16
    warmup:         int = _DEFAULT_WARMUP_CANDLES

INSTRUMENTS = [
    InstrumentConfig("EURUSD",  "data/EURUSD_M15.csv",  pip_size=0.0001, spread_pct=0.0002),
    InstrumentConfig("GBPUSD",  "data/GBPUSD_M15.csv",  pip_size=0.0001, spread_pct=0.0003),
    InstrumentConfig("USDJPY",  "data/USDJPY_M15.csv",  pip_size=0.01,   spread_pct=0.0002),
    InstrumentConfig("AUDUSD",  "data/AUDUSD_M15.csv",  pip_size=0.0001, spread_pct=0.0003),
    InstrumentConfig("EURCAD",  "data/EURCAD_M15.csv",  pip_size=0.0001, spread_pct=0.0003),
    InstrumentConfig("XAUUSD",  "data/XAUUSD_M15.csv",  pip_size=0.0001, spread_pct=0.0003),
    InstrumentConfig("BTCUSDT", "data/BTCUSDT_M15.csv", pip_size=1.0,    spread_pct=0.0008),
    InstrumentConfig("ETHUSDT", "data/ETHUSDT_M15.csv", pip_size=1.0,    spread_pct=0.0008),
]

# ─────────────────────────────────────────────────────────────────
# SHARED ENGINE CONFIG — identical across all instruments
# (No instrument-specific tuning — that would be curve-fitting)
# ─────────────────────────────────────────────────────────────────

def make_crt_config(instrument: str) -> "CRTConfig":
    """
    Instrument-aware config factory.
    Delegates entirely to ConfigBuilder so Forex and Crypto profiles diverge correctly.
    Shared overrides (non-market-specific tuning) are applied on top of the router base.
    """
    return ConfigBuilder.build(
        instrument,
        overrides={
            "score_threshold":        0.70,
            "max_sweep_age_candles":  30,
            "score_decay_lambda":     0.05,
            "atr_multiplier_min":     1.2,
            "confirmation_body_min":  0.5,
        },
    )

# ─────────────────────────────────────────────────────────────────
# PORTFOLIO ANALYTICS ENGINE
# ─────────────────────────────────────────────────────────────────

class PortfolioAnalytics:
    """Aggregates trade records across instruments and computes portfolio stats."""

    def __init__(self, all_trades: list[TradeRecord]):
        self.trades = all_trades

    # ── Core metrics ──────────────────────────────────────────────

    def aggregate(self) -> dict:
        t = self.trades
        if not t:
            return {"total_trades": 0}

        wins   = [x for x in t if x.is_winner]
        losses = [x for x in t if not x.is_winner]
        rr_series = [x.pnl_rr_net for x in t]

        total_r    = sum(rr_series)
        avg_rr     = total_r / len(t)
        gross_win  = sum(x.pnl_rr_net for x in wins)
        gross_loss = abs(sum(x.pnl_rr_net for x in losses))
        pf         = gross_win / gross_loss if gross_loss > 0 else float("inf")

        avg_win  = gross_win  / len(wins)   if wins   else 0.0
        avg_loss = -gross_loss / len(losses) if losses else 0.0
        wr       = len(wins) / len(t)
        expectancy = avg_win * wr - avg_loss * (1 - wr)

        # Per-trade Sharpe
        if len(rr_series) >= 2:
            mean = sum(rr_series) / len(rr_series)
            var  = sum((r - mean)**2 for r in rr_series) / len(rr_series)
            sharpe = mean / math.sqrt(var) if var > 0 else 0.0
        else:
            sharpe = 0.0

        # Max drawdown (R-curve)
        eq = peak = dd = 0.0
        for r in rr_series:
            eq += r
            peak = max(peak, eq)
            dd = max(dd, peak - eq)

        return {
            "total_trades":   len(t),
            "wins":           len(wins),
            "losses":         len(losses),
            "win_rate":       round(wr, 4),
            "avg_rr_net":     round(avg_rr, 4),
            "expectancy_rr":  round(expectancy, 4),
            "total_pnl_rr":   round(total_r, 4),
            "profit_factor":  round(pf if pf != float("inf") else 999.0, 3),
            "sharpe_per_trade": round(sharpe, 4),
            "max_drawdown_rr":  round(dd, 4),
            "avg_trade_duration": round(sum(x.duration_candles for x in t) / len(t), 1),
        }

    def instrument_breakdown(self) -> dict:
        groups = defaultdict(list)
        for t in self.trades:
            groups[t.instrument].append(t)

        result = {}
        for instr, trades in sorted(groups.items()):
            wins   = sum(1 for t in trades if t.is_winner)
            total  = len(trades)
            rr     = sum(t.pnl_rr_net for t in trades)
            scored = [t for t in trades if t.gaussian_score > 0]
            result[instr] = {
                "trades":        total,
                "win_rate":      round(wins / total, 4) if total else 0.0,
                "total_pnl_rr":  round(rr, 4),
                "avg_rr":        round(rr / total, 4) if total else 0.0,
                "scored_trades": len(scored),
                "avg_score":     round(sum(t.gaussian_score for t in scored) / len(scored), 4) if scored else 0.0,
            }
        return result

    def score_distribution(self) -> dict:
        """Win rate by Gaussian score bucket — the key edge validation metric."""
        buckets = {
            "0.0-0.2": [], "0.2-0.4": [],
            "0.4-0.6": [], "0.6-0.8": [], "0.8-1.0": [],
        }
        thresholds = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]

        for t in self.trades:
            s = t.gaussian_score
            for label, (lo, hi) in zip(buckets.keys(), thresholds):
                if lo <= s < hi:
                    buckets[label].append(t)
                    break

        result = {}
        for label, trades in buckets.items():
            if not trades:
                continue
            wins = sum(1 for t in trades if t.is_winner)
            result[label] = {
                "trades":   len(trades),
                "win_rate": round(wins / len(trades), 4),
                "avg_rr":   round(sum(t.pnl_rr_net for t in trades) / len(trades), 4),
            }
        return result

    def gaussian_correlation(self) -> float:
        """Pearson correlation: gaussian_score vs binary win/loss outcome."""
        scored = [(t.gaussian_score, 1.0 if t.is_winner else 0.0)
                  for t in self.trades if t.gaussian_score > 0]
        if len(scored) < 5:
            return float("nan")

        scores   = [s for s, _ in scored]
        outcomes = [o for _, o in scored]
        n        = len(scores)
        ms, mo   = sum(scores) / n, sum(outcomes) / n
        cov      = sum((s - ms) * (o - mo) for s, o in zip(scores, outcomes)) / n
        ss       = math.sqrt(sum((s - ms)**2 for s in scores) / n)
        so       = math.sqrt(sum((o - mo)**2 for o in outcomes) / n)
        return round(cov / (ss * so), 4) if ss > 0 and so > 0 else 0.0

    def score_outcome_rr_correlation(self) -> float:
        """Pearson correlation: gaussian_score vs actual RR (continuous, not binary)."""
        scored = [(t.gaussian_score, t.pnl_rr_net)
                  for t in self.trades if t.gaussian_score > 0]
        if len(scored) < 5:
            return float("nan")

        scores   = [s for s, _ in scored]
        outcomes = [o for _, o in scored]
        n        = len(scores)
        ms, mo   = sum(scores) / n, sum(outcomes) / n
        cov      = sum((s - ms) * (o - mo) for s, o in zip(scores, outcomes)) / n
        ss       = math.sqrt(sum((s - ms)**2 for s in scores) / n)
        so       = math.sqrt(sum((o - mo)**2 for o in outcomes) / n)
        return round(cov / (ss * so), 4) if ss > 0 and so > 0 else 0.0

    def rejection_breakdown(self, all_metrics: list[BacktestMetrics]) -> dict:
        """Aggregate rejection reasons across all instruments."""
        combined = defaultdict(int)
        for m in all_metrics:
            for reason, count in m.rejection_reasons.items():
                combined[reason] += count
        return dict(sorted(combined.items(), key=lambda x: -x[1]))

    def session_breakdown(self) -> dict:
        groups = defaultdict(list)
        for t in self.trades:
            groups[t.session or "UNKNOWN"].append(t)
        result = {}
        for sess, trades in sorted(groups.items()):
            wins = sum(1 for t in trades if t.is_winner)
            n    = len(trades)
            result[sess] = {
                "trades":   n,
                "win_rate": round(wins / n, 4) if n else 0.0,
                "pnl_rr":  round(sum(t.pnl_rr_net for t in trades), 4),
            }
        return result

    def universality_verdict(self) -> str:
        """
        Applies Jarvis's interpretation framework:
        - Positive EV across ≥2 instruments → Universal candidate
        - Gaussian correlation > +0.15      → Score is predictive
        - Single-instrument dominance        → Curve-fit warning
        """
        instr = self.instrument_breakdown()
        profitable = sum(1 for v in instr.values() if v["total_pnl_rr"] > 0)
        corr       = self.gaussian_correlation()
        agg        = self.aggregate()
        ev         = agg.get("expectancy_rr", 0)

        reasons = []

        if profitable >= 2 and ev > 0.10:
            reasons.append("✅ Positive EV across ≥2 instruments")
        elif profitable == 1:
            reasons.append("⚠️  Only 1 profitable instrument — possible curve-fit")
        else:
            reasons.append("❌ No profitable instruments")

        if isinstance(corr, float) and not math.isnan(corr):
            if corr > 0.15:
                reasons.append(f"✅ Gaussian correlation = {corr:.3f} — score is predictive")
            elif corr > 0:
                reasons.append(f"⚠️  Weak correlation = {corr:.3f} — score marginally predictive")
            else:
                reasons.append(f"❌ Negative correlation = {corr:.3f} — model needs recalibration")
        else:
            reasons.append("⚠️  Insufficient scored trades for correlation (<5)")

        if agg.get("total_trades", 0) < 15:
            reasons.append(f"⚠️  Sample too small ({agg['total_trades']} trades) — add more instruments/data")
        else:
            reasons.append(f"✅ Sample size = {agg['total_trades']} trades")

        return "\n  ".join(reasons)


# ─────────────────────────────────────────────────────────────────
# PORTFOLIO RUNNER
# ─────────────────────────────────────────────────────────────────

def run_portfolio(
    instruments: list[InstrumentConfig],
    output_dir: str = _DEFAULT_OUTPUT_DIR,
    initial_capital: float = _DEFAULT_INITIAL_CAPITAL,
) -> tuple[list[TradeRecord], list[BacktestMetrics]]:
    """
    Run backtest on each instrument. Returns all trades and metrics.
    No instrument-specific parameter tuning — identical config everywhere.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    all_trades:   list[TradeRecord]   = []
    all_metrics:  list[BacktestMetrics] = []
    for instr in instruments:
        if not Path(instr.csv_path).exists():
            print(f"  ⚠️  {instr.name}: data not found at {instr.csv_path} — skipping")
            continue

        print(f"\n  ▶ {instr.name} ({instr.csv_path})")

        # Per-instrument config — router selects FOREX or CRYPTO profile automatically
        crt_cfg = make_crt_config(instr.name)

        cfg = BacktestConfig(
            instrument            = instr.name,
            pip_size              = instr.pip_size,
            htf_candles_per_range = instr.htf_candles,
            warmup_candles        = instr.warmup,
            initial_capital       = initial_capital,
            risk_pct_per_trade    = _DEFAULT_RISK_PCT,
            use_compounding       = True,
            simulated_spread_pct  = instr.spread_pct,
            slippage_enabled      = True,
            slippage_atr_fraction = _DEFAULT_SLIPPAGE_FRACTION,
            slippage_seed         = 42,
            gap_reset_enabled     = True,
            gap_reset_minutes     = 120,
            event_flush_every     = 100,
            crt_config            = crt_cfg,
        )

        loader = CandleLoader(instr.csv_path, instr.name)
        runner = BacktestRunner(cfg, csv_path=instr.csv_path)

        try:
            m = runner.run(
                loader.stream(),
                loader.count(),
                f"{output_dir}/{instr.name}",
            )
            all_trades.extend(runner._last_journal_trades)
            all_metrics.append(m)
            print(f"    trades={m.approved_trades}  WR={m.win_rate:.0%}  "
                  f"PnL={m.total_pnl_rr_net:+.2f}R  cap=${m.capital_curve['final_capital']:,.0f}")
        except Exception as e:
            print(f"    ERROR: {e}")
            import traceback; traceback.print_exc()

    return all_trades, all_metrics


# ─────────────────────────────────────────────────────────────────
# REPORT
# ─────────────────────────────────────────────────────────────────

def print_portfolio_report(
    all_trades: list[TradeRecord],
    all_metrics: list[BacktestMetrics],
    output_dir: str = "results/portfolio",
) -> dict:
    pa = PortfolioAnalytics(all_trades)

    agg    = pa.aggregate()
    instr  = pa.instrument_breakdown()
    sdist  = pa.score_distribution()
    corr   = pa.gaussian_correlation()
    corr_rr= pa.score_outcome_rr_correlation()
    sess   = pa.session_breakdown()
    rejections = pa.rejection_breakdown(all_metrics)
    verdict = pa.universality_verdict()

    W = 65
    print()
    print("═" * W)
    print("  CRT ENGINE — PORTFOLIO VALIDATION REPORT")
    print("═" * W)

    print(f"""
── GLOBAL AGGREGATE ──────────────────────────────────────────
  Total instruments run:      {len(all_metrics):>8}
  Total trades:               {agg.get('total_trades', 0):>8}
  Win rate:                   {agg.get('win_rate', 0):>8.1%}
  Avg RR (net):               {agg.get('avg_rr_net', 0):>+8.3f}R
  Expectancy per trade:       {agg.get('expectancy_rr', 0):>+8.3f}R
  Total PnL:                  {agg.get('total_pnl_rr', 0):>+8.2f}R
  Profit factor:              {agg.get('profit_factor', 0):>8.2f}
  Sharpe (per-trade):         {agg.get('sharpe_per_trade', 0):>8.3f}
  Max drawdown:               {agg.get('max_drawdown_rr', 0):>8.2f}R
  Avg trade duration:         {agg.get('avg_trade_duration', 0):>8.1f} candles""")

    print("\n── INSTRUMENT BREAKDOWN ──────────────────────────────────────")
    print(f"  {'Instrument':<12} {'Trades':>6}  {'WinRate':>8}  {'TotalPnL':>10}  {'AvgRR':>8}  {'Scored':>6}")
    print(f"  {'-'*12}  {'-'*5}  {'-'*7}  {'-'*9}  {'-'*7}  {'-'*5}")
    for name, stats in instr.items():
        print(f"  {name:<12} {stats['trades']:>6}  {stats['win_rate']:>8.1%}  "
              f"{stats['total_pnl_rr']:>+10.2f}R  {stats['avg_rr']:>+8.3f}R  "
              f"{stats['scored_trades']:>6}")

    print("\n── GAUSSIAN SCORE DISTRIBUTION (GLOBAL) ─────────────────────")
    print(f"  {'Bucket':<10} {'Trades':>6}  {'WinRate':>8}  {'AvgRR':>8}")
    print(f"  {'-'*10}  {'-'*5}  {'-'*7}  {'-'*7}")
    for bucket, stats in sorted(sdist.items()):
        wr_flag = " ←" if stats["win_rate"] > 0.55 else ""
        print(f"  {bucket:<10} {stats['trades']:>6}  {stats['win_rate']:>8.1%}  "
              f"{stats['avg_rr']:>+8.3f}R{wr_flag}")

    print(f"""
── GAUSSIAN SCORE PREDICTIVENESS ────────────────────────────
  Score vs win/loss correlation:  {corr:>8.4f}  (>+0.15 = predictive)
  Score vs RR correlation:        {corr_rr:>8.4f}  (continuous outcome)
  Interpretation: {'PREDICTIVE' if isinstance(corr,float) and corr > 0.15 else 'WEAK' if isinstance(corr,float) and corr > 0 else 'INSUFFICIENT DATA'}""")

    print("\n── SESSION BREAKDOWN ────────────────────────────────────────")
    for sess_name, stats in sess.items():
        print(f"  {sess_name:<12} {stats['trades']:>4} trades  "
              f"WR={stats['win_rate']:.0%}  PnL={stats['pnl_rr']:>+.2f}R")

    if rejections:
        print("\n── REJECTION REASONS (all instruments) ──────────────────────")
        total_rej = sum(rejections.values())
        for reason, count in list(rejections.items())[:6]:
            pct = count / total_rej if total_rej > 0 else 0
            print(f"  {reason:<40} {count:>5}  ({pct:.1%})")

    print("\n── UNIVERSALITY VERDICT ──────────────────────────────────────")
    print(f"  {verdict}")
    print()
    print("═" * W)

    # Build full results dict
    results = {
        "aggregate":           agg,
        "instrument_breakdown": instr,
        "score_distribution":  sdist,
        "gaussian_correlation": corr,
        "gaussian_corr_rr":    corr_rr,
        "session_breakdown":   sess,
        "rejection_reasons":   rejections,
        "universality_verdict": verdict,
    }

    # Write JSON
    out = Path(output_dir) / "portfolio_report.json"
    with open(out, "w") as f:
        # corr may be float nan — convert to None for JSON
        safe = json.dumps(results, default=lambda x: None if (isinstance(x, float) and math.isnan(x)) else x, indent=2)
        f.write(safe)
    print(f"  Report → {out}")

    return results


# ─────────────────────────────────────────────────────────────────
# RUNNER JOURNAL HOOK — attach last journal to runner for aggregation
# ─────────────────────────────────────────────────────────────────

def _patch_runner_for_journal_access():
    """
    Monkey-patches BacktestRunner.run() to store closed trades on the runner
    instance after completion. Zero changes to business logic.
    """
    original_run = BacktestRunner.run

    def patched_run(self, candle_source, total_candles, output_dir="results"):
        # Create a fresh journal capture by wrapping the original
        from backtest_v2 import TradeJournal, SlippageModel, CapitalCurve
        result = original_run(self, candle_source, total_candles, output_dir)
        # Access the journal via the result metrics (trades are in the CSV)
        # We'll read them back from the written CSV for cleanliness
        import csv as _csv
        trades_csv = Path(output_dir) / f"{self.cfg.instrument}_trades.csv"
        self._last_journal_trades = []
        if trades_csv.exists():
            with open(trades_csv, newline="") as f:
                reader = _csv.DictReader(f)
                for row in reader:
                    from datetime import datetime
                    from config_layer.crt_engine_v2 import Direction
                    tr = _build_trade_record(row)
                    self._last_journal_trades.append(tr)
        return result

    BacktestRunner.run = patched_run


def _build_trade_record(row: dict) -> TradeRecord:
    """Reconstruct a TradeRecord from a CSV row dict."""
    from datetime import datetime

    def _dt(s):
        return datetime.fromisoformat(s) if s else None

    def _f(k, default=0.0):
        try: return float(row.get(k, default))
        except: return default

    def _i(k, default=0):
        try: return int(row.get(k, default))
        except: return default

    return TradeRecord(
        trade_id          = row.get("trade_id", ""),
        instrument        = row.get("instrument", ""),
        direction         = row.get("direction", ""),
        entry_price_raw   = _f("entry_raw"),
        sl_price          = _f("sl"),
        tp1_price         = _f("tp1"),
        tp2_price         = _f("tp2"),
        entry_price_fill  = _f("entry_fill"),
        exit_price_fill   = _f("exit_fill"),
        exit_reason       = row.get("exit_reason", ""),
        opened_at         = _dt(row.get("opened_at", "")),
        closed_at         = _dt(row.get("closed_at", "")),
        candle_open       = _i("candle_open") if "candle_open" in row else 0,
        candle_close      = _i("candle_close") if "candle_close" in row else 0,
        pnl_pips_raw      = _f("pnl_pips_raw"),
        pnl_pips_net      = _f("pnl_pips_net"),
        pnl_rr_raw        = _f("pnl_rr_raw"),
        pnl_rr_net        = _f("pnl_rr_net"),
        slippage_pips     = _f("slippage_pips"),
        spread_pips       = _f("spread_pips"),
        capital_before    = _f("capital_before"),
        capital_after     = _f("capital_after"),
        position_size     = _f("position_size"),
        risk_score        = _f("risk_score"),
        risk_pct          = _f("risk_pct") if "risk_pct" in row else 0.01,
        gaussian_score    = _f("gaussian_score"),
        gaussian_p_win    = _f("gaussian_p_win"),
        score_retest      = _f("score_retest"),
        score_body        = _f("score_body"),
        score_disp        = _f("score_disp"),
        score_time        = _f("score_time"),
        retest_depth      = _f("feat_retest_depth"),
        body_ratio_feat   = _f("feat_body_ratio"),
        disp_str_feat     = _f("feat_disp_str"),
        session           = row.get("session", ""),
        regime            = row.get("regime", ""),
        dynamic_threshold = _f("dynamic_threshold"),
        risk_multiplier   = _f("risk_multiplier"),
        week_of_year      = _i("week_of_year") if "week_of_year" in row else 0,
        day_of_week       = _i("day_of_week"),
        hour_of_day       = _i("hour_of_day"),
        htf_id            = row.get("htf_id", ""),
    )


# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="CRT Portfolio Validation")
    ap.add_argument("--output", default=_DEFAULT_OUTPUT_DIR)
    ap.add_argument("--capital", type=float, default=_DEFAULT_INITIAL_CAPITAL)
    args = ap.parse_args()

    print("╔══════════════════════════════════════════════════════════╗")
    print("║  CRT ENGINE — PORTFOLIO VALIDATION                      ║")
    print("║  Testing edge universality across instruments            ║")
    print("╚══════════════════════════════════════════════════════════╝")

    _patch_runner_for_journal_access()

    print(f"\nInstruments: {[i.name for i in INSTRUMENTS]}")
    print(f"Capital: ${args.capital:,.0f}  |  Config: SHARED (no per-instrument tuning)\n")

    all_trades, all_metrics = run_portfolio(
        INSTRUMENTS, args.output, args.capital
    )

    if not all_trades:
        print("\n⚠️  No trades generated across any instrument.")
        print("   Check data files and paths in INSTRUMENTS list.")
        return

    print_portfolio_report(all_trades, all_metrics, args.output)


if __name__ == "__main__":
    main()
