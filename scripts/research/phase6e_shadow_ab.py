"""
phase6e_shadow_ab.py — Phase 6e governance re-validation (measure-only).

Single-knob A/B on BNBUSDT M15 over the V3 session-expanded config:
  - control : shadow_advisory_only = True   (current production policy)
  - treat   : shadow_advisory_only = False  (recover the 70 shadow-blocked retests)

Faithful to the production backtest path:
  load_prod_config_from_registry(PROD_VERSION, instr)  -> all prod crt_engine values
  ConfigBuilder.from_existing(instr, base, extra_overrides=...)  -> apply V3 sessions + flag
  BacktestConfig.from_prod_config(instr, crt_config=...) -> BacktestRunner.run(...)

Measure-only: writes ONLY under results/phase6e_shadow_ab/. No config edit, no promotion.
Control arm MUST reproduce V3 (35 trades / PF ~2.535) or the harness is untrusted (hard gate).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

from config_layer.production_config import PROD_VERSION, load_prod_config_from_registry  # noqa: E402
from config_layer.config_builder import ConfigBuilder                                    # noqa: E402
from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader             # noqa: E402

INSTR = "BNBUSDT"
CSV = "data/BNBUSDT_M15.csv"
V3_SESSIONS = ("LONDON", "NEWYORK", "OVERLAP", "ASIA", "OFF_SESSION")
OUT = Path("results/phase6e_shadow_ab")
# V3 published reference (results/session_sweep/bnbusdt.json)
V3_REF = {"approved_trades": 35, "profit_factor": 2.5351}


def _run_arm(label: str, extra: dict) -> dict:
    base = load_prod_config_from_registry(PROD_VERSION, INSTR)
    crt = ConfigBuilder.from_existing(INSTR, base, extra_overrides=extra)
    cfg = BacktestConfig.from_prod_config(instrument=INSTR, crt_config=crt)
    loader = CandleLoader(CSV, INSTR)
    runner = BacktestRunner(cfg, csv_path=CSV)
    m = runner.run(loader.stream(), loader.count(), str(OUT / label))
    fc = m.funnel_counts or {}
    return {
        "label": label,
        "shadow_advisory_only": bool(crt.shadow_advisory_only),
        "allowed_sessions": list(crt.allowed_sessions),
        "approved_trades": m.approved_trades,
        "win_rate": round(m.win_rate, 4),
        "profit_factor": round(m.profit_factor, 4),
        "avg_rr_net": round(m.avg_rr_net, 4),
        "total_pnl_rr_net": round(m.total_pnl_rr_net, 4),
        "max_drawdown_pct": round(m.max_drawdown_pct, 4),
        "total_return_pct": round(m.total_return_pct, 4),
        "return_to_max_dd": round(m.return_to_max_dd, 4),
        "funnel_retest": fc.get("RETEST"),
        "funnel_execution": fc.get("EXECUTION"),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    arms = [
        ("control_shadowTrue_V3", {"allowed_sessions": V3_SESSIONS}),
        ("treat_shadowFalse_V3", {"allowed_sessions": V3_SESSIONS, "shadow_advisory_only": False}),
    ]
    results = [_run_arm(label, extra) for label, extra in arms]

    ctrl, treat = results[0], results[1]
    ctrl_ok = (ctrl["approved_trades"] == V3_REF["approved_trades"]
               and abs(ctrl["profit_factor"] - V3_REF["profit_factor"]) < 0.01)
    pf_held = treat["profit_factor"] >= V3_REF["profit_factor"]

    payload = {
        "prod_version": PROD_VERSION,
        "instrument": INSTR,
        "v3_reference": V3_REF,
        "control_reproduces_v3": ctrl_ok,
        "treat_pf_held_vs_v3": pf_held,
        "arms": results,
    }
    (OUT / "phase6e_ab.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("=== Phase 6e shadow_advisory_only A/B (BNBUSDT) ===")
    for r in results:
        print(f"  {r['label']:<24} shadow={r['shadow_advisory_only']!s:<5} "
              f"trades={r['approved_trades']:<4} PF={r['profit_factor']:<7} "
              f"WR={r['win_rate']:<6} avgRR={r['avg_rr_net']:<7} "
              f"DD%={r['max_drawdown_pct']:<7} ret%={r['total_return_pct']:<7} "
              f"retest={r['funnel_retest']} exec={r['funnel_execution']}")
    print(f"\nCONTROL reproduces V3 (35 / PF~2.535)? {ctrl_ok}  "
          f"[got {ctrl['approved_trades']} / {ctrl['profit_factor']}]")
    print(f"TREATMENT PF held >= 2.5351? {pf_held}  [got {treat['profit_factor']}]")
    return 0 if ctrl_ok else 2


if __name__ == "__main__":
    sys.exit(main())
