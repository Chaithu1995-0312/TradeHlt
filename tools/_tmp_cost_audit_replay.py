"""Side-by-side G1+G2 (ledger) vs SEM-015 ComponentCostModel on run fills."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import sys
sys.path.insert(0, "src")
from research.costs import xau_measured_cost_model, DEFAULT_COST_MODEL

df = pd.read_csv("results/run_20260916_101942_XAUUSD/XAUUSD_trades.csv")
sem = xau_measured_cost_model()
flat = DEFAULT_COST_MODEL

cfg_path = Path("configs/production/v2_htfcrt_2026_08.json")
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

def find(d, key, path=""):
    if isinstance(d, dict):
        if key in d:
            yield (path + "." + key if path else key), d[key]
        for k, v in d.items():
            yield from find(v, key, path + "." + k if path else k)

print("=== CONFIG KNOBS ===")
for k in ["slippage_atr_fraction", "simulated_spread_pct", "slippage_seed", "slippage_enabled",
          "spread_pips", "slippage_pips", "pip_size", "cost_model", "cost_model_id"]:
    hits = list(find(cfg, k))
    if hits:
        print(k, "->", hits[:6])

rows = []
for _, t in df.iterrows():
    entry_raw = float(t.entry_raw)
    entry_fill = float(t.entry_fill)
    sl = float(t.sl)
    direction = str(t.direction).upper()
    exit_reason = str(t.exit_reason).upper()
    if exit_reason in ("STOPPED", "SL", "SL_HIT"):
        exit_kind = "SL_HIT"
    elif exit_reason in ("TP1", "TP2", "TP", "TP_HIT"):
        exit_kind = "TP_HIT"
    else:
        exit_kind = exit_reason

    risk_fill = abs(entry_fill - sl)
    risk_raw = abs(entry_raw - sl)
    drag_g1g2 = float(t.pnl_rr_raw) - float(t.pnl_rr_net)
    cost_price_g1g2_implied = drag_g1g2 * risk_fill

    cost_px_sem = sem.cost_price(exit_kind=exit_kind, direction=direction.lower(), nights_held=0)
    cost_r_sem_raw = sem.cost_r(entry_raw, risk_raw, exit_kind=exit_kind, direction=direction.lower())
    cost_r_sem_fill = sem.cost_r(entry_fill, risk_fill, exit_kind=exit_kind, direction=direction.lower())

    pip = 0.01
    pnl_price_raw = float(t.pnl_pips_raw) * pip
    gross_r_raw = pnl_price_raw / risk_raw if risk_raw > 0 else float("nan")
    net_sem_from_geom = gross_r_raw - cost_r_sem_raw
    cost_r_flat = flat.cost_r(entry_raw, risk_raw)
    net_flat = gross_r_raw - cost_r_flat
    bps_g1g2 = (cost_price_g1g2_implied / entry_raw) * 10000 if entry_raw else None
    bps_sem = sem.effective_bps(entry_raw, exit_kind=exit_kind, direction=direction.lower())

    row = dict(
        trade_id=t.trade_id,
        opened=str(t.opened_at),
        direction=direction,
        exit_reason=exit_reason,
        exit_kind_sem=exit_kind,
        entry_raw=round(entry_raw, 4),
        entry_fill=round(entry_fill, 4),
        risk_raw=round(risk_raw, 4),
        risk_fill=round(risk_fill, 4),
        pnl_rr_raw=round(float(t.pnl_rr_raw), 4),
        pnl_rr_net_g1g2=round(float(t.pnl_rr_net), 4),
        drag_g1g2_R=round(drag_g1g2, 4),
        cost_px_g1g2_implied=round(cost_price_g1g2_implied, 4),
        bps_g1g2_eff=round(bps_g1g2, 2) if bps_g1g2 is not None else None,
        slip_pips=float(t.slippage_pips),
        spread_pips=float(t.spread_pips),
        cost_px_sem=round(cost_px_sem, 4),
        cost_r_sem_raw=round(cost_r_sem_raw, 4),
        cost_r_sem_fill=round(cost_r_sem_fill, 4),
        gross_r_geom=round(gross_r_raw, 4),
        net_sem_geom=round(net_sem_from_geom, 4),
        cost_r_flat12=round(cost_r_flat, 4),
        net_flat12=round(net_flat, 4),
        bps_sem=round(bps_sem, 2),
        delta_net_sem_minus_g1g2=round(net_sem_from_geom - float(t.pnl_rr_net), 4),
    )
    rows.append(row)
    print("\n===", t.trade_id, direction, exit_reason, t.opened_at, "===")
    for k, v in row.items():
        print(f"  {k}: {v}")

out_dir = Path("results/run_20260916_101942_XAUUSD/cost_audit")
out_dir.mkdir(parents=True, exist_ok=True)
pd.DataFrame(rows).to_csv(out_dir / "g1g2_vs_sem015_fills.csv", index=False)
print("\nWrote", out_dir / "g1g2_vs_sem015_fills.csv")
print("SEM components:", {k: getattr(sem, k) for k in [
    "half_spread", "commission", "entry_slippage", "stop_slippage",
    "instrument", "source", "status", "entry_slippage_basis"]})
print("SEM SL RT cost_px=", sem.cost_price(exit_kind="SL_HIT"),
      "TP RT=", sem.cost_price(exit_kind="TP_HIT"))
print("SUM ledger pnl_rr_net=", float(df.pnl_rr_net.sum()), "raw=", float(df.pnl_rr_raw.sum()))
print("SUM SEM net geom=", sum(r["net_sem_geom"] for r in rows))
print("SUM flat net=", sum(r["net_flat12"] for r in rows))

