"""
detection_sweep.py
==================
F-003 Phase B — CRT detection-supply sweep (MEASURE-ONLY, attributed).

Mirrors the session_sweep.py doctrine: V0 = current prod config (must be recorded
as the reference), then SINGLE-KNOB variants via dataclasses.replace on the
binding-stage CRTConfig fields proven by Phase A (DISPLACEMENT->EXPANSION ~5%):

  expansion_atr_min_distance : 0.20 -> 0.15 -> 0.10   (the DISP->EXPANSION guard)
  atr_min_displacement       : 1.2  -> 1.1  -> 1.0    (displacement size gate)
  confirmation_body_min      : 0.60 -> 0.55 -> 0.50   (displacement body gate)

For each variant: trade N, PF, expectancy (avg_rr_net), maxDD, win-rate, AND the
funnel counts (DISPLACEMENT/EXPANSION/RETEST/EXECUTION) so we watch the choke
directly and detect a DOWNSTREAM bottleneck migration (more expansions but not
more executions = a major finding, NOT progress).

FROZEN pass/fail (set BEFORE results, user 2026-06-06): a variant PASSES iff
  trade_count >= +50% vs V0  AND  PF >= 90% V0  AND  expectancy >= 90% V0
  AND  maxDD <= 125% V0.

MEASURE-ONLY: writes results/detection_sweep/ only. No config edit / re-hash /
promotion. A passing per-instrument candidate goes through a SEPARATE governed
ConfigValidator -> promotion decision. Deterministic (prod slippage_seed).

Usage:
  python scripts/analysis/detection_sweep.py --instrument BNBUSDT --family expansion
  python scripts/analysis/detection_sweep.py --instrument BNBUSDT --family all
"""
from __future__ import annotations

import argparse
import dataclasses
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

from runtime.backtest_v2 import (  # noqa: E402
    BacktestConfig, BacktestRunner, CandleLoader,
    load_prod_config_from_registry, PROD_VERSION, MultiInstrumentRunner,
)

# Single-knob variant families. All three knobs are "lower = looser = more supply",
# so relaxation = base x factor (factor<1). RELATIVE to each instrument's tuned base
# (per-instrument prod configs are already calibrated; absolute values would tighten
# an already-loose config like BNB's). V0 baseline = current prod, run first.
FAMILIES = {
    "expansion":     ("expansion_atr_min_distance", [0.66, 0.33]),
    "displacement":  ("atr_min_displacement",       [0.75, 0.50]),
    "body":          ("confirmation_body_min",      [0.75, 0.50]),
}

# Frozen pass/fail guardrails (vs V0). Set before results.
_MIN_TRADE_GAIN = 0.50     # trade count must be >= +50% vs V0
_PF_RETENTION   = 0.90     # PF >= 90% of V0
_EXP_RETENTION  = 0.90     # expectancy >= 90% of V0
_MAXDD_CEIL     = 1.25     # maxDD <= 125% of V0


def _run_one(crt_cfg, instrument: str, csv_path: str, output_dir: str, label: str) -> dict:
    cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
    cfg.instrument = instrument
    cfg.pip_size = MultiInstrumentRunner.INSTRUMENT_PIP.get(instrument, 0.0001)
    loader = CandleLoader(csv_path, instrument)
    runner = BacktestRunner(cfg, csv_path=csv_path,
                            overrides={"diagnostic": label, "instrument": instrument})
    t0 = time.time()
    m = runner.run(loader.stream(), loader.count(), output_dir)
    fc = m.funnel_counts or {}
    return {
        "label": label,
        "approved_trades": int(m.approved_trades),
        "win_rate": round(float(m.win_rate), 4),
        "expectancy_rr": round(float(m.avg_rr_net), 4),
        "profit_factor": round(float(m.profit_factor), 4),
        "total_return_pct": round(float(m.total_return_pct), 6),
        "max_drawdown_pct": round(float(m.max_drawdown_pct), 6),
        "return_to_max_dd": round(float(m.return_to_max_dd), 4),
        "funnel": {k: int(fc.get(k, 0)) for k in
                   ("DISPLACEMENT", "EXPANSION", "RETEST", "EXECUTION")},
        "disp_to_exp_pct": round(fc.get("EXPANSION", 0) / fc.get("DISPLACEMENT", 1) * 100, 2)
        if fc.get("DISPLACEMENT") else None,
        "elapsed_s": round(time.time() - t0, 1),
    }


def _verdict(v0: dict, r: dict) -> dict:
    tr_gain = (r["approved_trades"] - v0["approved_trades"]) / max(v0["approved_trades"], 1)
    pf_ret = r["profit_factor"] / v0["profit_factor"] if v0["profit_factor"] else 0.0
    exp_ret = (r["expectancy_rr"] / v0["expectancy_rr"]
               if v0["expectancy_rr"] > 0 else (1.0 if r["expectancy_rr"] >= v0["expectancy_rr"] else 0.0))
    dd_ratio = r["max_drawdown_pct"] / v0["max_drawdown_pct"] if v0["max_drawdown_pct"] else 1.0
    checks = {
        "trade_gain_ge_50pct": tr_gain >= _MIN_TRADE_GAIN,
        "pf_ge_90pct": pf_ret >= _PF_RETENTION,
        "expectancy_ge_90pct": exp_ret >= _EXP_RETENTION,
        "maxdd_le_125pct": dd_ratio <= _MAXDD_CEIL,
        # ABSOLUTE profitability floor — retention vs an unprofitable baseline is
        # degenerate (more trades = more loss). A pass must be profitable in
        # absolute terms, not merely "not much worse than a losing baseline".
        "pf_abs_ge_1": r["profit_factor"] >= 1.0,
        "expectancy_positive": r["expectancy_rr"] > 0.0,
    }
    return {"trade_gain": round(tr_gain, 3), "pf_retention": round(pf_ret, 3),
            "exp_retention": round(exp_ret, 3), "maxdd_ratio": round(dd_ratio, 3),
            "checks": checks, "PASS": all(checks.values())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--family", default="expansion",
                    help="expansion | displacement | body | all")
    ap.add_argument("--output-dir", default=str(_ROOT / "results" / "detection_sweep" / "_runs"))
    ap.add_argument("--results-json", default=None)
    args = ap.parse_args()

    instrument = args.instrument
    csv_path = args.csv or str(_ROOT / "data" / f"{instrument}_M15.csv")
    if not Path(csv_path).exists():
        sys.exit(f"[ERROR] data file not found: {csv_path}")
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    fams = list(FAMILIES) if args.family == "all" else [args.family]
    for f in fams:
        if f not in FAMILIES:
            sys.exit(f"[ERROR] unknown family '{f}'. Valid: {list(FAMILIES)} or 'all'")

    base_cfg = load_prod_config_from_registry(PROD_VERSION, instrument)
    print(f"[detection_sweep] instrument={instrument} prod={PROD_VERSION}")
    print(f"[detection_sweep] V0 base: exp_atr_min={base_cfg.expansion_atr_min_distance} "
          f"atr_min_disp={base_cfg.atr_min_displacement} conf_body_min={base_cfg.confirmation_body_min}\n")

    v0 = _run_one(base_cfg, instrument, csv_path, args.output_dir, "V0_baseline")
    v0["variant"] = "V0_baseline"
    print(f"  V0: trades={v0['approved_trades']} PF={v0['profit_factor']:.3f} "
          f"exp={v0['expectancy_rr']:+.3f} maxDD={v0['max_drawdown_pct']*100:.2f}% "
          f"funnel={v0['funnel']} disp->exp={v0['disp_to_exp_pct']}%\n")

    rows = [v0]
    for fam in fams:
        knob, factors = FAMILIES[fam]
        base_val = getattr(base_cfg, knob)
        for factor in factors:
            val = round(base_val * factor, 4)
            label = f"{fam}:{knob}={val}(x{factor})"
            crt_cfg = dataclasses.replace(base_cfg, **{knob: val})
            r = _run_one(crt_cfg, instrument, csv_path, args.output_dir, label)
            r["variant"] = label; r["knob"] = knob; r["value"] = val
            r["verdict"] = _verdict(v0, r)
            rows.append(r)
            v = r["verdict"]
            print(f"  {label}: trades={r['approved_trades']} (dN{v['trade_gain']*100:+.0f}%) "
                  f"PF={r['profit_factor']:.3f} exp={r['expectancy_rr']:+.3f} "
                  f"maxDD={r['max_drawdown_pct']*100:.2f}% disp->exp={r['disp_to_exp_pct']}% "
                  f"EXEC={r['funnel']['EXECUTION']}  [{'PASS' if v['PASS'] else 'fail'}]")

    out = Path(args.results_json) if args.results_json else (
        _ROOT / "results" / "detection_sweep" / f"{instrument.lower()}_{args.family}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "schema": "detection_sweep_v1",
        "status": "MEASURE-ONLY (no config change / no promotion)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "instrument": instrument, "prod_version": PROD_VERSION,
        "guardrails": {"min_trade_gain": _MIN_TRADE_GAIN, "pf_retention": _PF_RETENTION,
                       "exp_retention": _EXP_RETENTION, "maxdd_ceil": _MAXDD_CEIL},
        "v0": v0, "rows": rows,
    }, indent=2), encoding="utf-8")
    print(f"\nOUTPUT:detection_sweep:{out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
