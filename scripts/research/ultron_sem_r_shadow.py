"""REM-SOFT-01 research: shadow Ultron gate RR if SEM-015 cost_R were applied.

Does NOT modify Ultron config or production knobs. Writes a compare table for the
fresh stamped trades CSV.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from research.costs import xau_measured_cost_model


def main() -> None:
    trades = ROOT / "results/run_20260916_225925_XAUUSD/XAUUSD_trades.csv"
    df = pd.read_csv(trades)
    sem = xau_measured_cost_model()
    min_rr = 1.5  # ultron_risk_gate default / config

    rows = []
    for _, t in df.iterrows():
        entry_raw = float(t.entry_raw)
        entry_fill = float(t.entry_fill)
        sl = float(t.sl)
        direction = str(t.direction).lower()
        exit_reason = str(t.exit_reason).upper()
        exit_kind = "SL_HIT" if exit_reason in ("STOPPED", "SL", "SL_HIT") else "TP_HIT"
        risk_raw = abs(entry_raw - sl)
        risk_fill = abs(entry_fill - sl)
        # Planned RR proxy: use ledger pnl_rr_raw as gross geometry under fill denom
        gross_ledger = float(t.pnl_rr_raw)
        # Admission uses raw CRT RR before fills — approximate with |tp1-entry|/risk_raw sign by direction
        tp1 = float(t.tp1)
        if direction == "long":
            planned_raw = (tp1 - entry_raw) / risk_raw if risk_raw else float("nan")
        else:
            planned_raw = (entry_raw - tp1) / risk_raw if risk_raw else float("nan")

        cost_r_sl = sem.cost_r(entry_raw, risk_raw, exit_kind="SL_HIT", direction=direction)
        cost_r_actual = sem.cost_r(entry_raw, risk_raw, exit_kind=exit_kind, direction=direction)
        # Conservative gate haircut assumes stop exit (worst common case)
        gate_rr_sem_shadow = planned_raw - cost_r_sl
        admit_gross = planned_raw >= min_rr
        admit_sem_shadow = gate_rr_sem_shadow >= min_rr

        rows.append(
            {
                "trade_id": t.trade_id,
                "direction": direction,
                "exit_reason": exit_reason,
                "planned_rr_raw_tp1": round(planned_raw, 4),
                "pnl_rr_raw_ledger": round(gross_ledger, 4),
                "pnl_rr_net_g1g2": round(float(t.pnl_rr_net), 4),
                "sem_cost_r_sl_assumption": round(cost_r_sl, 4),
                "sem_cost_r_actual_exit": round(cost_r_actual, 4),
                "gate_rr_sem_shadow": round(gate_rr_sem_shadow, 4),
                "min_rr": min_rr,
                "admit_gross_none": bool(admit_gross),
                "admit_sem_shadow": bool(admit_sem_shadow),
                "flip_vs_gross": bool(admit_gross) != bool(admit_sem_shadow),
                "cost_model_id": t.get("cost_model_id", ""),
                "risk_denominator_id": t.get("risk_denominator_id", ""),
            }
        )

    out_dir = ROOT / "results/run_20260916_225925_XAUUSD/cost_audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "ultron_sem_r_shadow.csv"
    out_json = out_dir / "ultron_sem_r_shadow.json"
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    payload = {
        "authority": "RESEARCH_ONLY — REM-SOFT-01 shadow; Ultron tax NOT activated",
        "min_rr_ratio": min_rr,
        "sem_components": {
            "half_spread": sem.half_spread,
            "commission": sem.commission,
            "entry_slippage": sem.entry_slippage,
            "stop_slippage": sem.stop_slippage,
            "entry_slippage_basis": sem.entry_slippage_basis,
        },
        "n_trades": len(rows),
        "n_flip_vs_gross": sum(1 for r in rows if r["flip_vs_gross"]),
        "rows": rows,
        "design_note": "docs/research/REM_SOFT_01_ULTRON_GROSS_VS_LEDGER_NET_2026-09-16.md",
    }
    out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_csv": str(out_csv), "n_flip": payload["n_flip_vs_gross"], "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
