#!/usr/bin/env python
"""all_states_economic_probe.py — generalizes the SWEEP economic probe to every state-entry
decision type with real full-corpus population.

READ-ONLY. DESCRIPTIVE ONLY. No p-values, no verdicts, no economic claim.

WHY THIS EXISTS
---------------
Per [[project_entry_decisions_not_occupancy_rule]] (the strongest, most-replicated finding of
this investigation): state-machine research must start at entry DECISIONS, never OCCUPANCY.
The SWEEP-specific probes (sweep_structure_economic_probe.py etc.) proved this rigor out on one
state. This script asks the next-level question directly: "which state-entry decisions produce
materially different outcome distributions" -- BEFORE attaching structure (breaker/OB/CHoCH) to
any of them, per the curriculum: Observe -> Measure Outcomes -> Kill False Explanations ->
Survivors -> Attach Structure -> Promote. This is the "Measure Outcomes" step, generalized.

SCOPE. Only states with real full-corpus decision population are measured: SWEEP (n=1798),
DISPLACEMENT (n=399), EXPANSION (n=148). RETEST (n=24) and SHADOW_PENDING (n=6) are excluded --
both are below the n=30 floor this investigation has used throughout, and reporting a median on
either would repeat exactly the small-n trap (TF's n=51, FF's n=55) that has already produced two
retracted conclusions this session.

REUSE. Same object as `sweep_structure_economic_probe.py`: hold from next-bar open to fixed
horizon close, no SL/TP, net of SEM-015 measured cost (`research.costs.ComponentCostModel`,
exit_kind=TIMEOUT, nights_held=0 -- see that module for the full cost-model rationale, unchanged
here). Episode-concentration check on both tails at every horizon, exactly as done for SWEEP,
because a distribution that looks different but is 90% one episode is not a different state
behaviour -- it is E4 again.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import statistics as st
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

_SEP = ROOT / "scripts" / "analysis" / "sweep_structure_economic_probe.py"
_spec = importlib.util.spec_from_file_location("sweep_structure_economic_probe", _SEP)
sep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sep)

HORIZONS = (20, 40, 80)
STATES = ("SWEEP", "DISPLACEMENT", "EXPANSION")
MIN_N = 30


def pct(xs: list[float], p: float) -> Optional[float]:
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def tail_episodes(rows: list[dict], key: str, frac: float, top: bool) -> int:
    n = max(1, int(len(rows) * frac))
    ordered = sorted(rows, key=lambda r: r[key], reverse=top)[:n]
    return len(set(r["episode_id"] for r in ordered))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--atlas", default="results/decision_atlas_full")
    ap.add_argument("--csv", default="data/mt5/XAUUSD_M15.csv")
    ap.add_argument("--out", default="results/decision_atlas_full/all_states_economic_probe.json")
    args = ap.parse_args()

    cost_model = sep.load_cost_model()
    print(f"cost model provenance: {json.dumps(cost_model.provenance(), indent=2)}")

    import pyarrow.parquet as pq
    atlas = Path(ROOT / args.atlas)
    dec = pq.read_table(atlas / "transition_decision.parquet").to_pylist()
    atr_by_bar = {b["bar_index"]: b["live_atr"] for b in pq.read_table(atlas / "envelope_bar.parquet").to_pylist()}
    corpus = sep.p001.load_corpus(ROOT / args.csv)

    by_state = {s: [d for d in dec if d["to_state"] == s and d["direction"]
                    and not d["is_self_transition"]] for s in STATES}
    for s, rows in by_state.items():
        print(f"{s}: {len(rows)} directional decisions (pre-truncation)")

    results: dict[str, dict] = {}
    for H in HORIZONS:
        state_summaries = {}
        for s in STATES:
            rows_h = []
            for d in by_state[s]:
                atr = atr_by_bar.get(d["bar_index"])
                if not atr:
                    continue
                gross = sep.close_at_horizon(corpus, d["bar_index"], d["direction"], atr, H)
                if gross is None:
                    continue
                direction = "long" if d["direction"] == "LONG" else "short"
                cost_r = cost_model.cost_price(exit_kind="TIMEOUT", direction=direction, nights_held=0) / atr
                rows_h.append({"net_R": gross - cost_r, "episode_id": d["episode_id"]})
            n = len(rows_h)
            if n == 0:
                continue
            net = [r["net_R"] for r in rows_h]
            summary = {
                "n": n,
                "power": "INSUFFICIENT" if n < MIN_N else "WEAK",
                "net_mean": round(st.mean(net), 4), "net_median": round(st.median(net), 4),
                "net_p25": round(pct(net, 25), 4), "net_p75": round(pct(net, 75), 4),
                "net_p90": round(pct(net, 90), 4),
                "win_rate": round(sum(1 for x in net if x > 0) / n, 4),
                "top10pct_distinct_episodes": tail_episodes(rows_h, "net_R", 0.10, top=True),
                "bottom10pct_distinct_episodes": tail_episodes(rows_h, "net_R", 0.10, top=False),
            }
            state_summaries[s] = summary
        results[f"H{H}"] = state_summaries

    artifact = {
        "probe_id": "ALL-STATES-ECON-01",
        "claim_class": "DESCRIPTIVE_ONLY",
        "economic_claims_allowed": False,
        "authority": "none",
        "scope_note": (
            "Only SWEEP/DISPLACEMENT/EXPANSION measured -- RETEST (n=24) and SHADOW_PENDING "
            "(n=6) excluded, below the n=30 floor used throughout this investigation."
        ),
        "cost_model_provenance": cost_model.provenance(),
        "results": results,
    }
    sep.p001.assert_no_claim_keys(artifact)
    out = ROOT / args.out
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    for H in HORIZONS:
        print(f"\n=== H={H} ===")
        print(f"{'state':13s} {'n':>5s} {'power':>12s} {'net_med':>8s} {'net_p25':>8s} "
              f"{'net_p75':>8s} {'net_p90':>8s} {'win%':>6s} {'top10_eps':>10s} {'bot10_eps':>10s}")
        for s in STATES:
            c = results[f"H{H}"].get(s)
            if not c:
                continue
            print(f"{s:13s} {c['n']:5d} {c['power']:>12s} {c['net_median']:8.4f} "
                  f"{c['net_p25']:8.4f} {c['net_p75']:8.4f} {c['net_p90']:8.4f} "
                  f"{100*c['win_rate']:6.1f} {c['top10pct_distinct_episodes']:10d} "
                  f"{c['bottom10pct_distinct_episodes']:10d}")

    print(f"\nartifact: {out}")
    print("DESCRIPTIVE ONLY -- no significance, no economic claim, no finding id.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
