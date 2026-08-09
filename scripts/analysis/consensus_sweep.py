"""
consensus_sweep.py
==================
Fusion consensus gate sensitivity sweep (MEASURE-ONLY).

Varies two FusionConfig knobs across a 3x5 grid and records trade count + PF
for each combination BEFORE any production value is changed:

  min_consensus_signals   : 1, 2* (baseline), 3
  min_consensus_agreement : 0.50, 0.55, 0.60* (baseline), 0.65, 0.70

Injection mechanism: monkeypatch config_layer.production_config.get_prod_section
so the "fusion_engine" section returns the sweep values. All call sites in
backtest_v2.py use deferred imports (inside functions) and therefore see the
patch. Strategy modules use top-level imports but are DORMANT
(weight_strategy_consensus=0.0), so they are irrelevant to this gate.
BacktestRunner is rebuilt each run — no config caching risk.

FROZEN pass/fail (set BEFORE results):
  trade_count >= 90% V0  AND  PF >= 90% V0  AND  avg_rr >= 90% V0
  AND  maxDD <= 125% V0

Composite score (for ranking):
  0.35*PF_norm + 0.25*trades_norm + 0.20*avg_rr_norm + 0.20*(1/DD_norm)
  PF capped at 5.0 before normalisation to prevent inf distortion.

MEASURE-ONLY: writes results/consensus_sweep/ only. No config edit / rehash /
promotion. A candidate that scores > baseline goes through a SEPARATE governed
ConfigValidator -> promotion path.

Usage:
  python scripts/analysis/consensus_sweep.py --instrument BNBUSDT
  python scripts/analysis/consensus_sweep.py --instrument BNBUSDT --signals 2 --agreement 0.60
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# ── Monkeypatch must be installed BEFORE backtest_v2 is imported so that
#    any module-level code that calls get_prod_section during import sees the
#    original (sweep overrides are only set per-run, not at import time).
import config_layer.production_config as _pc  # noqa: E402

_sweep_overrides: dict = {}
_orig_get_prod_section = _pc.get_prod_section


def _patched_get_prod_section(section: str, version=None):
    d = _orig_get_prod_section(section, version=version)
    if section == "fusion_engine" and _sweep_overrides:
        d = dict(d)        # shallow copy — never mutate the cached/returned dict
        d.update(_sweep_overrides)
    return d


_pc.get_prod_section = _patched_get_prod_section

from runtime.backtest_v2 import (  # noqa: E402
    BacktestConfig, BacktestRunner, CandleLoader, PROD_VERSION, MultiInstrumentRunner,
)

# ── Grid ──────────────────────────────────────────────────────────────────────
BASELINE = (2, 0.60)

_DEFAULT_SIGNALS    = [1, 2, 3]
_DEFAULT_AGREEMENTS = [0.50, 0.55, 0.60, 0.65, 0.70]

# ── Pass/fail guardrails (frozen before results) ───────────────────────────────
_TRADE_RETENTION = 0.90   # trade count >= 90% V0
_PF_RETENTION    = 0.90   # PF >= 90% V0
_EXP_RETENTION   = 0.90   # avg_rr >= 90% V0
_MAXDD_CEIL      = 1.25   # maxDD <= 125% V0

# ── PF computation ────────────────────────────────────────────────────────────

def _profit_factor(m) -> float:
    """
    Approximate PF from BacktestMetrics using total_pnl_rr_raw + losses count.
    Uses pre-cost raw PnL so spread/slippage don't distort the ratio.
    Assumes fixed 1R loss per losing trade (valid for fixed-SL system; bias is
    consistent across all 15 runs so relative ranking is stable).
    """
    if m.losses == 0:
        return float("inf")
    gross_losses = float(m.losses)                     # 1R per loss
    gross_wins   = float(m.total_pnl_rr_raw) + gross_losses
    if gross_wins <= 0:
        return 0.0
    return round(gross_wins / gross_losses, 4)


def _run_one(instrument: str, csv_path: str, output_dir: str,
             label: str, signals: int, agreement: float) -> dict:
    global _sweep_overrides
    _sweep_overrides = {"min_consensus_signals": signals,
                        "min_consensus_agreement": agreement}
    try:
        cfg = BacktestConfig.from_prod_config(instrument=instrument)
        cfg.pip_size = MultiInstrumentRunner.INSTRUMENT_PIP.get(instrument, 0.0001)
        loader = CandleLoader(csv_path, instrument)
        runner = BacktestRunner(cfg, csv_path=csv_path,
                                overrides={"diagnostic": label, "instrument": instrument})

        # Fail-fast assertion: verify override propagated into FusionConfig before run.
        er = getattr(runner, "_engine_runner", None)
        if er is not None:
            fe = getattr(er, "fusion", None)
            fc = getattr(fe, "cfg", None)
            if fc is not None:
                if fc.min_consensus_signals != signals:
                    raise RuntimeError(
                        f"[consensus_sweep] monkeypatch did not propagate: "
                        f"expected signals={signals}, got {fc.min_consensus_signals}"
                    )
                if abs(fc.min_consensus_agreement - agreement) > 1e-9:
                    raise RuntimeError(
                        f"[consensus_sweep] monkeypatch did not propagate: "
                        f"expected agreement={agreement}, got {fc.min_consensus_agreement}"
                    )

        t0 = time.time()
        m = runner.run(loader.stream(), loader.count(), output_dir)
    finally:
        _sweep_overrides = {}

    return {
        "label":                    label,
        "min_consensus_signals":    signals,
        "min_consensus_agreement":  agreement,
        "approved_trades":          int(m.approved_trades),
        "profit_factor":            _profit_factor(m),
        "win_rate":                 round(float(m.win_rate), 4),
        "avg_rr_net":               round(float(m.avg_rr_net), 4),
        "total_pnl_rr_net":         round(float(m.total_pnl_rr_net), 4),
        "max_drawdown_pct":         round(float(m.max_drawdown_pct), 6),
        "is_baseline":              (signals, agreement) == BASELINE,
        "elapsed_s":                round(time.time() - t0, 1),
    }


def _score(row: dict, v0: dict) -> float:
    pf_cap   = 5.0
    pf       = min(row["profit_factor"], pf_cap)
    v0_pf    = min(v0["profit_factor"], pf_cap)
    trades   = row["approved_trades"]
    avg_rr   = row["avg_rr_net"]
    dd       = row["max_drawdown_pct"]

    v0_trades = max(v0["approved_trades"], 1)
    v0_avg_rr = v0["avg_rr_net"]
    v0_dd     = max(v0["max_drawdown_pct"], 1e-9)
    v0_pf_s   = max(v0_pf, 1e-9)

    s = (
        0.35 * (pf / v0_pf_s)
        + 0.25 * (trades / v0_trades)
        + 0.20 * (avg_rr / v0_avg_rr if v0_avg_rr > 0 else (1.0 if avg_rr >= v0_avg_rr else 0.0))
        + 0.20 * (v0_dd / max(dd, 1e-9))
    )
    return round(min(max(s, 0.0), 2.0), 3)


def _verdict(row: dict, v0: dict) -> dict:
    v0_trades = max(v0["approved_trades"], 1)
    v0_pf     = v0["profit_factor"]
    v0_avg_rr = v0["avg_rr_net"]
    v0_dd     = max(v0["max_drawdown_pct"], 1e-9)

    tr_ret  = row["approved_trades"] / v0_trades
    pf_ret  = row["profit_factor"] / v0_pf if v0_pf > 0 else (1.0 if row["profit_factor"] >= 0 else 0.0)
    exp_ret = (row["avg_rr_net"] / v0_avg_rr
               if v0_avg_rr > 0 else (1.0 if row["avg_rr_net"] >= v0_avg_rr else 0.0))
    dd_ratio = row["max_drawdown_pct"] / v0_dd

    checks = {
        "trades_ge_90pct":     tr_ret  >= _TRADE_RETENTION,
        "pf_ge_90pct":         pf_ret  >= _PF_RETENTION,
        "avg_rr_ge_90pct":     exp_ret >= _EXP_RETENTION,
        "maxdd_le_125pct":     dd_ratio <= _MAXDD_CEIL,
        "pf_abs_ge_1":         row["profit_factor"] >= 1.0,
        "avg_rr_positive":     row["avg_rr_net"] > 0.0,
    }
    return {
        "trade_retention": round(tr_ret, 3),
        "pf_retention":    round(pf_ret, 3),
        "exp_retention":   round(exp_ret, 3),
        "maxdd_ratio":     round(dd_ratio, 3),
        "checks":          checks,
        "PASS":            all(checks.values()),
    }


def _deltas(row: dict, v0: dict) -> dict:
    def _pct(a, b):
        return round((a - b) / abs(b) * 100, 1) if b else 0.0
    return {
        "delta_pf_pct":     _pct(row["profit_factor"], v0["profit_factor"]),
        "delta_trades_pct": _pct(row["approved_trades"], v0["approved_trades"]),
        "delta_avg_rr_pct": _pct(row["avg_rr_net"], v0["avg_rr_net"]),
        "delta_dd_pct":     _pct(row["max_drawdown_pct"], v0["max_drawdown_pct"]),
    }


def _build_grid(signals_list: list[int], agreements_list: list[float]) -> list[tuple]:
    """Baseline always first, then remaining pairs in signals×agreements order."""
    rest = [(s, a) for s in signals_list for a in agreements_list if (s, a) != BASELINE]
    return [BASELINE] + rest if BASELINE in [(s, a) for s in signals_list for a in agreements_list] else rest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--output-dir",
                    default=str(_ROOT / "results" / "consensus_sweep" / "_runs"))
    ap.add_argument("--results-json", default=None)
    ap.add_argument("--signals",   default=None,
                    help="Comma-separated signal counts, e.g. '1,2,3'")
    ap.add_argument("--agreement", default=None,
                    help="Comma-separated agreement values, e.g. '0.50,0.55,0.60'")
    args = ap.parse_args(argv)

    instrument = args.instrument
    csv_path   = args.csv or str(_ROOT / "data" / f"{instrument}_M15.csv")
    if not Path(csv_path).exists():
        sys.exit(f"[ERROR] data file not found: {csv_path}")
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    signals_list    = ([int(x) for x in args.signals.split(",")]
                       if args.signals else _DEFAULT_SIGNALS)
    agreements_list = ([float(x) for x in args.agreement.split(",")]
                       if args.agreement else _DEFAULT_AGREEMENTS)

    grid = _build_grid(signals_list, agreements_list)
    n    = len(grid)

    print(f"[consensus_sweep] instrument={instrument}  prod={PROD_VERSION}")
    print(f"[consensus_sweep] grid: {n} runs  "
          f"signals={signals_list}  agreements={agreements_list}\n")

    rows: list[dict] = []
    v0: dict | None  = None

    for i, (sig, agr) in enumerate(grid, 1):
        label = (f"s{sig}_a{agr:.2f}_baseline" if (sig, agr) == BASELINE
                 else f"s{sig}_a{agr:.2f}")
        print(f"  [{i}/{n}] {label} ...", end=" ", flush=True)
        row = _run_one(instrument, csv_path, args.output_dir, label, sig, agr)

        if row["is_baseline"]:
            row["score"]          = 1.000
            row["pass"]           = True
            row["verdict"]        = {}
            row["delta_pf_pct"]   = 0.0
            row["delta_trades_pct"] = 0.0
            row["delta_avg_rr_pct"] = 0.0
            row["delta_dd_pct"]   = 0.0
            v0 = row
        elif v0 is not None:
            row["score"]   = _score(row, v0)
            verdict        = _verdict(row, v0)
            row["pass"]    = verdict["PASS"]
            row["verdict"] = verdict
            row.update(_deltas(row, v0))
        else:
            # baseline not in grid (override mode), no relative scoring
            row["score"] = None
            row["pass"]  = None
            row["verdict"] = {}
            row.update({"delta_pf_pct": None, "delta_trades_pct": None,
                        "delta_avg_rr_pct": None, "delta_dd_pct": None})

        rows.append(row)
        pf_str = (f"{row['profit_factor']:.3f}" if row['profit_factor'] != float("inf")
                  else "inf")
        verdict_str = ""
        if row["pass"] is True and not row["is_baseline"]:
            verdict_str = "  [PASS]"
        elif row["pass"] is False:
            verdict_str = "  [fail]"
        print(f"trades={row['approved_trades']}  PF={pf_str}  "
              f"avg_rr={row['avg_rr_net']:+.3f}  "
              f"maxDD={row['max_drawdown_pct']*100:.2f}%  "
              f"score={row['score']}  {row['elapsed_s']}s{verdict_str}")

    # ── ASCII summary table (sorted by score desc, then PF, trades) ──────────
    if len(rows) > 1 and v0 is not None:
        ranked = sorted(
            rows,
            key=lambda r: (
                r["score"] if r["score"] is not None else -1,
                r["profit_factor"] if r["profit_factor"] != float("inf") else 999,
                r["approved_trades"],
            ),
            reverse=True,
        )
        print(f"\n{'─'*90}")
        print(f"{'RANK':<5} {'LABEL':<28} {'SIG':>3} {'AGR':>5} "
              f"{'TRADES':>7} {'PF':>7} {'AVG_RR':>7} {'DD%':>7} "
              f"{'SCORE':>6} {'PASS':<5}")
        print(f"{'─'*90}")
        for rank, r in enumerate(ranked, 1):
            pf_s  = f"{r['profit_factor']:.3f}" if r['profit_factor'] != float("inf") else "inf"
            pass_s = "✓" if r["pass"] is True else ("✗" if r["pass"] is False else "–")
            base_s = " *" if r["is_baseline"] else ""
            print(f"{rank:<5} {r['label']+base_s:<28} {r['min_consensus_signals']:>3} "
                  f"{r['min_consensus_agreement']:>5.2f} "
                  f"{r['approved_trades']:>7} {pf_s:>7} "
                  f"{r['avg_rr_net']:>+7.3f} {r['max_drawdown_pct']*100:>7.2f} "
                  f"{str(r['score']):>6} {pass_s:<5}")
        print(f"{'─'*90}")
        print("* = baseline\n")

    # ── Write JSON output ─────────────────────────────────────────────────────
    ts  = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.results_json) if args.results_json else (
        _ROOT / "results" / "consensus_sweep" / f"{instrument.lower()}_{ts}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "schema":          "consensus_sweep_v1",
        "status":          "MEASURE-ONLY (no config change / no promotion)",
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "instrument":      instrument,
        "prod_version":    PROD_VERSION,
        "baseline":        BASELINE,
        "guardrails": {
            "trade_retention": _TRADE_RETENTION,
            "pf_retention":    _PF_RETENTION,
            "exp_retention":   _EXP_RETENTION,
            "maxdd_ceil":      _MAXDD_CEIL,
        },
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print(f"OUTPUT:consensus_sweep:{out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
