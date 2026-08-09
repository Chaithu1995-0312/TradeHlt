"""f048_decision_probe.py — OBSERVATION-ONLY empirical measurement for the F-048 decision.

HISTORICAL NOTE (F-048 RESOLVED 2026-07-24): this probe was written to measure the earlier
rr-semantic *shim* (DecisionEngine._economic_rr_from_fusion, since DELETED). F-048 was resolved
by REMOVING the RR gate from DecisionEngine entirely — it is now semantic-approval only, and
economic reward:risk is owned by UltronRiskGate. The probe still works as a generic run()
decision/reason distribution counter; the "does the shim let run() execute?" framing below is
superseded (there is no RR gate left to skip).

Question (as originally posed): can EngineRunner.run() actually reach "execute" on a real gate-ON
backtest, or do other gates still structurally block the live path (F-048's original 0/70,002)?

Method: mirrors the backtest_v2 CLI construction verbatim (the F-057 split-brain lives on the
programmatic BacktestRunner(cfg) path — the CLI path loads the production JSON, so we replicate
exactly that), wraps EngineRunner.run with a counting decorator (call-through; zero behavior
change), runs the backtest gate-ON, and prints the decision/reason distribution.

Usage:
    python scripts/analysis/f048_decision_probe.py --csv data/mt5/XAUUSD_M15.csv [--instrument XAUUSD]

READ-ONLY with respect to src/ and configs/. Results are DESCRIPTIVE (architecture evidence).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--instrument", default=None,
                    help="defaults to the CSV stem's leading symbol (e.g. XAUUSD from XAUUSD_M15)")
    ap.add_argument("--out", default=None, help="optional JSON dump of the tally")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    instr = args.instrument or csv_path.stem.split("_")[0].upper()

    # ── mirror the CLI construction (backtest_v2.main, single-instrument arm) ─
    from config_layer.production_config import PROD_VERSION
    from runtime.backtest_v2 import (
        BacktestConfig, BacktestRunner, CandleLoader, MultiInstrumentRunner,
        load_prod_config_from_registry, _preflight_dataset, bt_log,
    )

    crt_cfg = load_prod_config_from_registry(PROD_VERSION, instr)
    cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
    cfg.instrument = instr
    cfg.pip_size = MultiInstrumentRunner.INSTRUMENT_PIP.get(cfg.instrument, 0.0001)
    if not _preflight_dataset(str(csv_path), cfg.instrument, bt_log):
        print("dataset rejected by L3 pre-flight — aborting probe", file=sys.stderr)
        return 1

    # ── counting wrapper around EngineRunner.run (call-through, no mutation) ─
    import core.engine_runner as er_mod

    decisions: Counter = Counter()
    reasons: Counter = Counter()
    stages: Counter = Counter()
    executes: list[dict] = []

    _orig_run = er_mod.EngineRunner.run

    def _counting_run(self, input_data, *a, **kw):
        result = _orig_run(self, input_data, *a, **kw)
        d = (result or {}).get("decision") or (result or {}).get("status", "<none>")
        decisions[str(d)] += 1
        if str(d).upper() in ("REJECT", "REJECTED", "HOLD"):
            reasons[str((result or {}).get("reason", "<none>"))] += 1
            stages[str((result or {}).get("reject_stage", "?"))] += 1
        else:
            executes.append({
                "timestamp": str(input_data.get("timestamp", "")),
                "decision": str(d),
                "score": (result or {}).get("final_score"),
            })
        return result

    er_mod.EngineRunner.run = _counting_run
    try:
        loader = CandleLoader(str(csv_path), cfg.instrument)
        runner = BacktestRunner(cfg, csv_path=str(csv_path))
        metrics = runner.run(loader.stream(), loader.count(), "results")
    finally:
        er_mod.EngineRunner.run = _orig_run  # always restore

    n_calls = sum(decisions.values())
    n_exec = sum(v for k, v in decisions.items() if k.upper() not in ("REJECT", "REJECTED", "HOLD"))
    print("\n" + "=" * 70)
    print(f"F-048 PROBE — {instr} gate-ON — EngineRunner.run() outcome distribution")
    print("=" * 70)
    print(f"run() calls (candidate trades): {n_calls}")
    print(f"decisions: {dict(decisions)}")
    print(f"NON-VETO (allows trade through): {n_exec}")
    if reasons:
        print("reject reasons:")
        for r, c in reasons.most_common():
            print(f"  {r:40s} {c}")
        print(f"reject stages: {dict(stages)}")
    print(f"low_rr rejects: {sum(c for r, c in reasons.items() if 'low_rr' in r)}  "
          f"(F-048 structural block == every call; shim working == 0)")
    if executes:
        print(f"first executes: {executes[:3]}")
    trades = getattr(metrics, "total_trades", None)
    print(f"backtest trades closed: {trades}")

    if args.out:
        Path(args.out).write_text(json.dumps({
            "instrument": instr, "csv": str(csv_path),
            "run_calls": n_calls, "decisions": dict(decisions),
            "reject_reasons": dict(reasons), "reject_stages": dict(stages),
            "non_veto": n_exec, "trades": trades,
        }, indent=2), encoding="utf-8")
        print(f"written -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
