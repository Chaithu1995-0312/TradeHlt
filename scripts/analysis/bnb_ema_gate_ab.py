"""
bnb_ema_gate_ab.py
==================
MEASURE-ONLY A/B: does isolating the EMA directional gate help or hurt BNBUSDT under
the GOVERNING intrabar exit model?

Baseline  = current production CRTConfig (load_prod_config_from_registry).
Candidate = baseline with the EMA momentum component removed via TWO existing CRTConfig
            fields (pure config, no spine edit):
              weak_link_weight = 0.0           (drops the min(f_body,f_mom) penalty)
              conf_weights[w_mom] = 0.0        (momentum weight 0; other three renormalized)
All other thresholds held. This isolates the EMA gate ONLY.

Runs the existing BacktestRunner on data/<INSTRUMENT>_M15.csv for both configs and writes a
deterministic comparison to results/analysis/bnb_ema_gate_ab.json (+ wall-clock run-manifest).
NO config promotion, NO ACTIVE_VERSION change, NO spine edit. The formal ConfigValidator
ValidationReport + promotion is a separate governed follow-up (see plan Phase 3).

Usage:
  python scripts/analysis/bnb_ema_gate_ab.py --instrument BNBUSDT
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.config_builder import ConfigBuilder  # noqa: E402
from config_layer.production_config import (  # noqa: E402
    PROD_VERSION, load_prod_config_from_registry,
)
from runtime.backtest_v2 import (  # noqa: E402
    BacktestConfig, BacktestRunner, CandleLoader, MultiInstrumentRunner,
)
from utils.console_safe import safe_print  # noqa: E402


def _candidate_override(baseline) -> dict:
    """EMA-gate isolation override, derived from the baseline's own conf_weights so it
    works regardless of whether the JSON set them. Removes the momentum weight (index 1)
    and renormalizes the remaining three to sum 1.0; disables the weak-link penalty."""
    w_body, w_mom, w_dist, w_disp = baseline.conf_weights
    rest = w_body + w_dist + w_disp
    cw = (round(w_body / rest, 6), 0.0, round(w_dist / rest, 6), round(w_disp / rest, 6))
    return {"conf_weights": cw, "weak_link_weight": 0.0}


def _run_one(crt_cfg, instrument: str, csv_path: str, output_dir: str, label: str) -> dict:
    cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
    cfg.instrument = instrument
    cfg.pip_size = MultiInstrumentRunner.INSTRUMENT_PIP.get(instrument, 0.0001)
    loader = CandleLoader(csv_path, instrument)
    runner = BacktestRunner(cfg, csv_path=csv_path,
                            overrides={"diagnostic": label, "instrument": instrument})
    m = runner.run(loader.stream(), loader.count(), output_dir)
    fc = m.funnel_counts or {}
    return {  # deterministic only — no timing fields in the comparison body
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
    }


def _verdict(base: dict, cand: dict) -> dict:
    """Candidate-vs-baseline deltas + ABSOLUTE profitability floors. 'Beats random' in the
    World-A sense requires positive net expectancy in absolute terms (retention vs a losing
    baseline is degenerate); the formal random-control permutation is the World-A bar,
    referenced not re-fabricated here."""
    d_exp = round(cand["expectancy_rr"] - base["expectancy_rr"], 4)
    d_pf = round(cand["profit_factor"] - base["profit_factor"], 4)
    d_trades = cand["approved_trades"] - base["approved_trades"]
    d_dd = round(cand["max_drawdown_pct"] - base["max_drawdown_pct"], 6)
    checks = {
        "candidate_expectancy_positive": cand["expectancy_rr"] > 0.0,
        "candidate_pf_ge_1": cand["profit_factor"] >= 1.0,
        "candidate_beats_baseline_expectancy": d_exp > 0.0,
        "candidate_not_worse_dd": cand["max_drawdown_pct"] <= base["max_drawdown_pct"],
    }
    return {
        "delta_expectancy_rr": d_exp,
        "delta_profit_factor": d_pf,
        "delta_trades": d_trades,
        "delta_max_drawdown_pct": d_dd,
        "checks": checks,
        "candidate_supported": all(checks.values()),
        "note": ("'candidate_supported' is a measurement signal, NOT a promotion. "
                 "Promotion requires ConfigValidator.validate() APPROVE on a hashed "
                 "candidate config version (separate governed step). World-A baseline: "
                 "BNBUSDT entries are statistically random, net E≈0 before cost / "
                 "negative after."),
    }


def _git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(_ROOT),
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--output-dir",
                    default=str(_ROOT / "results" / "bnb_ema_gate_ab" / "_runs"))
    args = ap.parse_args(argv)

    instrument = args.instrument
    csv_path = args.csv or str(_ROOT / "data" / f"{instrument}_M15.csv")
    if not Path(csv_path).exists():
        safe_print(f"ERROR: data file not found: {csv_path}", file=sys.stderr)
        return 2
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    baseline_cfg = load_prod_config_from_registry(PROD_VERSION, instrument)
    override = _candidate_override(baseline_cfg)
    candidate_cfg = ConfigBuilder.from_existing(instrument, baseline_cfg,
                                                extra_overrides=override)

    base = _run_one(baseline_cfg, instrument, csv_path, args.output_dir, "baseline")
    cand = _run_one(candidate_cfg, instrument, csv_path, args.output_dir, "ema_gate_off")
    verdict = _verdict(base, cand)

    body = {
        "instrument": instrument,
        "exit_model": baseline_cfg.exit_model,
        "candidate_override": {"conf_weights": list(override["conf_weights"]),
                               "weak_link_weight": override["weak_link_weight"]},
        "baseline_conf_weights": list(baseline_cfg.conf_weights),
        "baseline": base,
        "candidate": cand,
        "verdict": verdict,
        # ready-to-paste governed deployment block for the promotion follow-up
        "promotion_block_crt_engine_instrument_overrides": {
            instrument: {"conf_weights": list(override["conf_weights"]),
                         "weak_link_weight": override["weak_link_weight"]}
        },
    }

    out = args.output or (_ROOT / "results" / "analysis" / "bnb_ema_gate_ab.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
    run_out = out.with_name(out.stem + "_run_manifest.json")
    run_out.write_text(json.dumps({
        "instrument": instrument, "csv": csv_path, "prod_version": PROD_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
    }, indent=2, sort_keys=True), encoding="utf-8")

    safe_print(f"==== BNB EMA-GATE A/B — {instrument} (exit={baseline_cfg.exit_model}) ====")
    safe_print(f"  baseline conf_weights={list(baseline_cfg.conf_weights)} weak_link={baseline_cfg.weak_link_weight}")
    safe_print(f"  candidate conf_weights={list(override['conf_weights'])} weak_link=0.0")
    for tag, r in (("BASELINE", base), ("CANDIDATE", cand)):
        safe_print(f"  {tag:<9} trades={r['approved_trades']:<4} "
                   f"PF={r['profit_factor']:+.3f} exp={r['expectancy_rr']:+.4f} "
                   f"maxDD={r['max_drawdown_pct']*100:.2f}% ret={r['total_return_pct']*100:+.2f}%")
    safe_print(f"  DELTA     exp={verdict['delta_expectancy_rr']:+.4f} "
               f"PF={verdict['delta_profit_factor']:+.4f} trades={verdict['delta_trades']:+d}")
    safe_print(f"  CHECKS: {verdict['checks']}")
    safe_print(f"  CANDIDATE_SUPPORTED (measurement only): {verdict['candidate_supported']}")
    safe_print(f"OUTPUT:bnb_ema_gate_ab:{out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
