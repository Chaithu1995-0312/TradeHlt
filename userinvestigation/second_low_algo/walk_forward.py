"""Walk-forward of the second-low SELECTION PROCEDURE (not of the frozen rule).

Declared before running (2026-10-06):
  primary cutoff   2025-10-01; secondary cutoffs 2025-07-01, 2026-01-01.
  learn  trades from backtest_{M15,H1,H4}.jsonl whose EXIT is before the cutoff
         (exit = trigger_ts + duration_candles x timeframe; a trade still running at the
         cutoff is unknown to the learner).
  select same rules as second_low_algo.py step 8: timeframe with the highest mean rr_gross
         among those with n >= 20 (tie -> lower TF); then the best of the six conditions
         with n >= 10 that beats that timeframe's mean, else no filter.
  score  trades triggered on/after the cutoff, chosen timeframe + condition:
         n, mean rr_gross, 95% range, plus the same timeframe unfiltered.
Gross R, no costs. economic_claims_allowed = false.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(__file__).resolve().parent
TF_MIN = {"M15": 15, "H1": 60, "H4": 240}
TFS = ("M15", "H1", "H4")
COND = {
    "fvg_active": lambda d: d.fvg_distance != 0,
    "fvg_none": lambda d: d.fvg_distance == 0,
    "below_pdl": lambda d: d.pdl_distance < 0,
    "at_or_above_pdl": lambda d: d.pdl_distance >= 0,
    "sellside_sweep": lambda d: d.liquidity_sweep == -1,
    "no_sellside_sweep": lambda d: d.liquidity_sweep != -1,
}
CUTOFFS = {"primary": "2025-10-01", "secondary_a": "2025-07-01", "secondary_b": "2026-01-01"}

rows = {}
for tf in TFS:
    d = pd.read_json(D / f"backtest_{tf}.jsonl", lines=True)
    d = d[d.status == "CLOSED"].copy()
    d["trigger_ts"] = pd.to_datetime(d.trigger_ts)
    d["exit_ts"] = d.trigger_ts + pd.to_timedelta(d.duration_candles * TF_MIN[tf], unit="min")
    rows[tf] = d


def st(x: pd.Series) -> dict:
    n = len(x)
    if n == 0:
        return {"n": 0}
    se = x.std(ddof=1) / n ** 0.5 if n > 1 else float("nan")
    return dict(n=n, mean=round(float(x.mean()), 4),
                ci95=[round(float(x.mean() - 1.96 * se), 4), round(float(x.mean() + 1.96 * se), 4)],
                total_r=round(float(x.sum()), 2), win_share=round(float((x > 0).mean()), 3))


out = {}
for name, cut in CUTOFFS.items():
    c = pd.Timestamp(cut)
    learn = {tf: d[d.exit_ts < c] for tf, d in rows.items()}
    test = {tf: d[d.trigger_ts >= c] for tf, d in rows.items()}
    learn_tf = {tf: st(learn[tf].rr_gross) for tf in TFS}
    elig = [tf for tf in TFS if learn_tf[tf]["n"] >= 20]
    tf = max(elig, key=lambda t: (learn_tf[t]["mean"], -TFS.index(t))) if elig else None
    cond_learn, cond = {}, None
    if tf:
        base = learn_tf[tf]["mean"]
        for k, fn in COND.items():
            cond_learn[k] = st(learn[tf][fn(learn[tf])].rr_gross)
        ok = [k for k, s in cond_learn.items() if s["n"] >= 10 and s["mean"] > base]
        cond = max(ok, key=lambda k: cond_learn[k]["mean"]) if ok else None
    res = dict(cutoff=cut, learn_by_tf=learn_tf, chosen_tf=tf, learn_conditions=cond_learn,
               chosen_condition=cond)
    if tf:
        t = test[tf]
        picked = t[COND[cond](t)] if cond else t
        res["test_picked"] = st(picked.rr_gross)
        res["test_same_tf_unfiltered"] = st(t.rr_gross)
        res["test_by_tf_unfiltered"] = {x: st(test[x].rr_gross) for x in TFS}
        res["test_frozen_rule_H4_at_or_above_pdl_IN_SAMPLE"] = st(
            test["H4"][COND["at_or_above_pdl"](test["H4"])].rr_gross)
    out[name] = res

out["economic_claims_allowed"] = False
(D / "walk_forward_summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
for name in CUTOFFS:
    r = out[name]
    print(f"== {name} cutoff {r['cutoff']}: learned {r['chosen_tf']} + {r['chosen_condition']}")
    print("  learn by tf:", {k: (v['n'], v.get('mean')) for k, v in r['learn_by_tf'].items()})
    print("  learn conds:", {k: (v['n'], v.get('mean')) for k, v in r['learn_conditions'].items()})
    print("  TEST picked:", r.get("test_picked"))
    print("  test same tf unfiltered:", r.get("test_same_tf_unfiltered"))
    print("  test by tf:", {k: (v['n'], v.get('mean')) for k, v in r.get('test_by_tf_unfiltered', {}).items()})
