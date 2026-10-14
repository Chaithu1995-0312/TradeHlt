"""Arm B (reclaim-bar entry) of the second-low research. Declared in reclaim_arm_freeze.json BEFORE running.

Research only, no order is ever sent, economic_claims_allowed = false. Imports the frozen
second_low_algo.py without editing it. Run ONCE:
  python userinvestigation/second_low_algo/reclaim_arm.py
"""
from __future__ import annotations

import importlib.util
import io
import contextlib
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
logging.disable(logging.CRITICAL)
spec = importlib.util.spec_from_file_location("sla", HERE / "second_low_algo.py")
sla = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sla)
from research.costs import xau_measured_cost_model  # noqa: E402

FREEZE = json.loads((HERE / "reclaim_arm_freeze.json").read_text(encoding="utf-8"))
CSVS = [str(ROOT / c) for c in FREEZE["corpus"]]
COST = xau_measured_cost_model()


def stats(x: pd.Series) -> dict:
    n = len(x)
    if n == 0:
        return {"n": 0}
    if n == 1:
        return {"n": 1, "mean": round(float(x.iloc[0]), 4)}
    se = x.std(ddof=1) / n ** 0.5
    m = float(x.mean())
    return dict(n=n, mean=round(m, 4), ci95=[round(m - 1.96 * se, 4), round(m + 1.96 * se, 4)],
                win_share=round(float((x > 0).mean()), 4), sd=round(float(x.std(ddof=1)), 4))


def main() -> None:
    m15 = sla.load_csvs(CSVS)
    print("corpus", FREEZE["corpus"], "rows", len(m15), m15.timestamp.iloc[0], "->", m15.timestamp.iloc[-1])
    raw = sla.tf_frame(m15, "H4")
    with contextlib.redirect_stdout(io.StringIO()):
        feat, _ = sla.FeaturePipeline(raw.copy(), cfg=sla.get_prod_section("feature_pipeline")).run()
    feat = feat.set_index("timestamp")
    work = raw.set_index("timestamp")
    work["second_low_20d"] = sla.compute_trading_day_second_low(work)
    lv = work["second_low_20d"].to_numpy()
    lows, closes, highs = work["low"].to_numpy(), work["close"].to_numpy(), work["high"].to_numpy()
    bars = sla.to_candles(raw)
    events = sla._independent_indices(work.index, sla._detect_raw_purge_mask(work))

    arm_a = {r["trigger_ts"]: r for r in sla.build_rows(m15, "H4")}
    rows = []
    for i in events:
        j = next((k for k in range(i, len(work)) if closes[k] >= lv[k]), None)
        if j is None:
            continue   # approach never reclaimed before corpus end (none expected)
        ts_i, ts_j = work.index[i], work.index[j]
        if ts_j not in feat.index:
            continue
        f = feat.loc[ts_j]
        atr_abs = float(f["atr"]) * float(f["close"])
        if not np.isfinite(atr_abs) or atr_abs <= 0:
            continue
        extreme = float(lows[i:j + 1].min())
        b = bars[j]
        lvl = sla.compute_crt_levels(b.close, 1, extreme, float(highs[j]), atr_abs,
                                     sla.SL_BUFFER, sla.TP1_MULT, sla.TP2_MULT)
        future = bars[j + 1:]
        row = dict(trigger_ts=str(ts_i), reclaim_ts=str(ts_j), bars_to_reclaim=int(j - i),
                   same_as_arm_A=bool(j == i), level=float(lv[j]), approach_extreme=extreme,
                   entry=b.close, sl=lvl["sl"], tp1=lvl["tp1"], tp2=lvl["tp2"], risk=lvl["risk_dist"],
                   atr_abs=atr_abs)
        if not future:
            row.update(status="OPEN")
            rows.append(row)
            continue
        out = sla.multi_tp_walk(b.close, "long", lvl["sl"], lvl["tp1"], lvl["tp2"], future,
                                max_forward=len(future), entry_index=b.index)
        if out.outcome == "TIMEOUT":
            row.update(status="OPEN")
        else:
            cost_r = COST.cost_r(b.close, lvl["risk_dist"], exit_kind=out.exit_kind, direction="long")
            row.update(status="CLOSED", exit_kind=out.exit_kind, rr_gross=out.rr_gross,
                       cost_r=cost_r, rr_net=out.rr_gross - cost_r, duration_candles=out.duration_candles)
        a = arm_a.get(str(ts_i))
        row["arm_A_rr_gross"] = a.get("rr_gross") if a else None
        rows.append(row)

    (HERE / "reclaim_arm_rows.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    d = pd.DataFrame([r for r in rows if r.get("status") == "CLOSED"])
    new = d[~d.same_as_arm_A]
    same = d[d.same_as_arm_A]
    summary = dict(
        freeze=FREEZE["id"], rows=len(rows), closed=len(d), open=len(rows) - len(d),
        all_gross=stats(d.rr_gross), all_net=stats(d.rr_net),
        identical_to_arm_A=stats(same.rr_gross), reclaim_later_gross=stats(new.rr_gross),
        reclaim_later_net=stats(new.rr_net),
        arm_A_on_reclaim_later=stats(new.arm_A_rr_gross.astype(float)),
        paired_B_minus_A_on_reclaim_later=stats(new.rr_gross - new.arm_A_rr_gross.astype(float)),
        median_risk_pct_of_price=round(float((d.risk / d.entry * 100).median()), 3),
        mean_bars_to_reclaim_when_later=round(float(new.bars_to_reclaim.mean()), 2) if len(new) else None,
        economic_claims_allowed=False,
    )
    ci = summary["all_gross"].get("ci95")
    summary["verdict"] = ("POSITIVE_DIAGNOSTIC" if ci and ci[0] > 0 else
                          "NEGATIVE_DIAGNOSTIC" if ci and ci[1] < 0 else "NULL_INSUFFICIENT")
    (HERE / "reclaim_arm_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
