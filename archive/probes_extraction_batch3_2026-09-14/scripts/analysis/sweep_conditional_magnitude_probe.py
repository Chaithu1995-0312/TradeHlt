#!/usr/bin/env python
"""sweep_conditional_magnitude_probe.py — same state path, different magnitude?

READ-ONLY. DESCRIPTIVE ONLY. No p-values, no verdicts, no economic claim.

WHY THIS EXISTS
---------------
The state-persistence probe found reached_displacement/reached_expansion rates FLAT across
breaker/OB cells -- the CRT construction progresses at the same rate regardless of structure.
But the economic probe found TF/TT diverge sharply in realized outcome. If the PATH frequency
is the same but the ECONOMICS differ, the remaining candidate is MAGNITUDE conditional on path:
two decisions can both walk SWEEP->DISPLACEMENT->EXPANSION and still travel +1 ATR vs +8 ATR.
This probe conditions on path (reached_displacement, reached_expansion) and asks whether the
realized magnitude differs by cell WITHIN that conditioning -- a materially different question
from "does the path happen" (already answered, flat) or "does the pooled outcome differ"
(already answered, yes).

REUSE. Imports `walk_episode_chain` from `sweep_state_persistence_probe.py` verbatim -- the
same contamination-safe episode-chain walk, not a re-implementation. Reads `fav_exc`/`adv_exc`
from the existing `excursion.parquet` (uncapped MFE/MAE, never recomputed) and net_R from the
same cost model + close-at-horizon object as `sweep_structure_economic_probe.py` (SEM-015,
exit_kind=TIMEOUT, nights_held=0 -- see that module's docstring for the full cost rationale).

OBJECT: at H=20 (the horizon with the most decisions surviving truncation), split SWEEP
decisions into reached_displacement==True and reached_expansion==True subsets, then report
fav_exc / adv_exc / net_R (median, p75, p90, n, distinct-episode count) per breaker/OB cell
WITHIN each subset.
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

_SPP = ROOT / "scripts" / "analysis" / "sweep_state_persistence_probe.py"
_spec = importlib.util.spec_from_file_location("sweep_state_persistence_probe", _SPP)
spp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(spp)

_SEP = ROOT / "scripts" / "analysis" / "sweep_structure_economic_probe.py"
_spec2 = importlib.util.spec_from_file_location("sweep_structure_economic_probe", _SEP)
sep = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(sep)

HORIZON = 20


def pct(xs: list[float], p: float) -> Optional[float]:
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def summarize(rows: list[dict], field: str) -> dict:
    vals = [r[field] for r in rows if r.get(field) is not None]
    eps = {r["episode_id"] for r in rows}
    return {
        "n": len(rows), "distinct_episodes": len(eps),
        "median": round(st.median(vals), 4) if vals else None,
        "p75": round(pct(vals, 75), 4) if vals else None,
        "p90": round(pct(vals, 90), 4) if vals else None,
        "mean": round(st.mean(vals), 4) if vals else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--atlas", default="results/decision_atlas_full")
    ap.add_argument("--csv", default="data/mt5/XAUUSD_M15.csv")
    ap.add_argument("--out", default="results/decision_atlas_full/sweep_conditional_magnitude_probe.json")
    args = ap.parse_args()

    import pyarrow.parquet as pq
    atlas = Path(ROOT / args.atlas)
    lf = pq.read_table(atlas / "sweep_liquidity_fact.parquet").to_pylist()
    dec = {d["decision_id"]: d for d in pq.read_table(atlas / "transition_decision.parquet").to_pylist()}
    episodes = pq.read_table(atlas / "episode.parquet").to_pylist()
    episodes.sort(key=lambda e: e["episode_id"])
    ep_index = {e["episode_id"]: k for k, e in enumerate(episodes)}
    atr_by_bar = {b["bar_index"]: b["live_atr"] for b in pq.read_table(atlas / "envelope_bar.parquet").to_pylist()}
    exc_by_dh = {(e["decision_id"], e["horizon"]): e
                 for e in pq.read_table(atlas / "excursion.parquet").to_pylist()}
    corpus = sep.p001.load_corpus(ROOT / args.csv)
    cost_model = sep.load_cost_model()

    def cell(r: dict) -> str:
        return ("T" if r["breaker_present"] else "F") + ("T" if r["ob_present"] else "F")

    rows = []
    for r in lf:
        d = dec[r["decision_id"]]
        eid = d["episode_id"]
        k = ep_index.get(eid)
        if k is None or episodes[k]["state"] != "SWEEP":
            continue
        walk = spp.walk_episode_chain(episodes, k, HORIZON)
        atr = atr_by_bar.get(r["bar_index"])
        exc = exc_by_dh.get((r["decision_id"], HORIZON)) or {}
        if not atr or exc.get("truncated"):
            continue
        gross = sep.close_at_horizon(corpus, r["bar_index"], d["direction"], atr, HORIZON)
        if gross is None:
            continue
        direction = "long" if d["direction"] == "LONG" else "short"
        cost_r = cost_model.cost_price(exit_kind="TIMEOUT", direction=direction, nights_held=0) / atr
        rows.append({
            "cell": cell(r), "episode_id": eid,
            "reached_displacement": walk["reached_displacement"],
            "reached_expansion": walk["reached_expansion"],
            "fav_exc": exc.get("fav_exc"), "adv_exc": exc.get("adv_exc"),
            "net_R": gross - cost_r,
        })

    results: dict[str, dict] = {}
    for cond_name, cond_field in (("reached_displacement", "reached_displacement"),
                                  ("reached_expansion", "reached_expansion")):
        cond_rows = [r for r in rows if r[cond_field]]
        by_cell = {}
        for cname in ("FF", "TF", "FT", "TT"):
            crows = [r for r in cond_rows if r["cell"] == cname]
            by_cell[cname] = {
                "fav_exc": summarize(crows, "fav_exc"),
                "adv_exc": summarize(crows, "adv_exc"),
                "net_R": summarize(crows, "net_R"),
            }
        results[cond_name] = by_cell

    artifact = {
        "probe_id": "SWEEP-CONDITIONAL-MAGNITUDE-01",
        "claim_class": "DESCRIPTIVE_ONLY",
        "economic_claims_allowed": False,
        "authority": "none",
        "horizon": HORIZON,
        "object_note": (
            "Conditions on PATH (reached_displacement / reached_expansion, from the same "
            "contamination-safe episode-chain walk as sweep_state_persistence_probe.py) and "
            "compares MAGNITUDE (fav_exc/adv_exc uncapped excursion; net_R realized cost-net "
            "outcome) by breaker/OB cell WITHIN that conditioning."
        ),
        "results": results,
    }
    out = ROOT / args.out
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    for cond in ("reached_displacement", "reached_expansion"):
        print(f"\n=== conditional on {cond}=True, H={HORIZON} ===")
        print(f"{'cell':6s} {'n':>5s} {'eps':>5s} {'fav_med':>8s} {'adv_med':>8s} "
              f"{'net_med':>8s} {'net_p75':>8s} {'net_p90':>8s}")
        for cname in ("FF", "TF", "FT", "TT"):
            c = results[cond][cname]
            n = c["net_R"]["n"]
            if n == 0:
                print(f"{cname:6s} {'0':>5s}  (no decisions in this cell reached {cond})")
                continue
            print(f"{cname:6s} {n:5d} {c['net_R']['distinct_episodes']:5d} "
                  f"{c['fav_exc']['median'] or 0:8.3f} {c['adv_exc']['median'] or 0:8.3f} "
                  f"{c['net_R']['median'] or 0:8.3f} {c['net_R']['p75'] or 0:8.3f} "
                  f"{c['net_R']['p90'] or 0:8.3f}")

    print(f"\nartifact: {out}")
    print("DESCRIPTIVE ONLY -- no significance, no economic claim, no finding id.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
