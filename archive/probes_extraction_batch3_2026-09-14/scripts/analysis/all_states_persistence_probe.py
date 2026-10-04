#!/usr/bin/env python
"""all_states_persistence_probe.py — generalizes still_dwelling to every state-entry decision.

READ-ONLY. DESCRIPTIVE ONLY. No p-values, no verdicts, no economic claim.

WHY THIS EXISTS
---------------
`sweep_state_persistence_probe.py` defined "progressed" as reaching a HARDCODED target
(DISPLACEMENT, then EXPANSION) from a SWEEP entry. That definition does not generalize: a
DISPLACEMENT entry's natural progression target is EXPANSION, and an EXPANSION entry's is
RETEST. This module replaces the hardcoded target with the CRT construction's own ORDINAL rank
(`_RANK`), so "did this decision progress" means the same thing -- reached a state further along
the construction than where it started, before reverting to RANGE -- regardless of which state
the decision entered. Verified against the SWEEP-specific probe below (must reproduce it exactly
when restricted to SWEEP entries) before being trusted for DISPLACEMENT/EXPANSION.

STILL-DWELLING x STRUCTURE, GENERALIZED
-----------------------------------------
Reuses the same episode-chain walk discipline as `sweep_state_persistence_probe.py` (stop at the
first RANGE episode; walk the CONTIGUOUS episode chain, never a raw bar-window scan) and the same
SEM-015 realized-economics object as `sweep_structure_economic_probe.py`. For each state with a
well-powered TT-vs-FT cell (checked, not assumed -- population sizes vary sharply by state), splits
into progressed / reverted / still_dwelling buckets and reports net_R per bucket per cell.
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

# CRT construction order. RANGE is the universal "reset" boundary -- reaching it always ends
# a walk, regardless of where it started (matches the SWEEP-specific probe's own rule).
_RANK = {"RANGE": 0, "SWEEP": 1, "DISPLACEMENT": 2, "EXPANSION": 3, "RETEST": 4,
         "EXECUTION": 5, "RESOLUTION": 6, "SHADOW_PENDING": 1, "EXPIRED": 3}

HORIZONS = (20, 40, 80)
MIN_N = 30


def walk_generalized(episodes: list[dict], start_k: int, horizon: int) -> dict:
    """Generalized version of sweep_state_persistence_probe.walk_episode_chain: 'progressed'
    means reaching any state with a HIGHER _RANK than the starting episode's own state, not a
    hardcoded target. Stops at the first RANGE episode encountered, exactly as before."""
    start_rank = _RANK.get(episodes[start_k]["state"], 0)
    cum = 0
    lag_progress = lag_range = None
    k = start_k + 1
    n = len(episodes)
    while k < n and cum < horizon:
        ep = episodes[k]
        cum += ep["bars"]
        if lag_progress is None and _RANK.get(ep["state"], 0) > start_rank and ep["state"] != "RANGE":
            lag_progress = cum
        if ep["state"] == "RANGE":
            lag_range = cum
            break
        if ep.get("right_censored"):
            break
        k += 1
    reached_progress = lag_progress is not None and lag_progress <= horizon
    reverted_never_progressed = (lag_range is not None and lag_range <= horizon
                                  and not reached_progress)
    return {
        "reached_progress": reached_progress,
        "reverted_never_progressed": reverted_never_progressed,
    }


def verify_matches_sweep_specific(atlas: Path) -> None:
    """Sanity gate: for SWEEP entries, this generalized walk must reproduce the SWEEP-specific
    probe's reached_displacement rate exactly (both mean 'reached a state further along the
    construction'). If it does not, the generalization is wrong -- abort before trusting it on
    DISPLACEMENT/EXPANSION."""
    _SPP = ROOT / "scripts" / "analysis" / "sweep_state_persistence_probe.py"
    spec2 = importlib.util.spec_from_file_location("sweep_state_persistence_probe", _SPP)
    spp = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(spp)

    import pyarrow.parquet as pq
    lf = pq.read_table(atlas / "sweep_liquidity_fact.parquet").to_pylist()
    dec = {d["decision_id"]: d for d in pq.read_table(atlas / "transition_decision.parquet").to_pylist()}
    episodes = pq.read_table(atlas / "episode.parquet").to_pylist()
    episodes.sort(key=lambda e: e["episode_id"])
    ep_index = {e["episode_id"]: k for k, e in enumerate(episodes)}

    old_rate, new_rate, n = 0, 0, 0
    for r in lf:
        d = dec[r["decision_id"]]
        k = ep_index.get(d["episode_id"])
        if k is None or episodes[k]["state"] != "SWEEP":
            continue
        old = spp.walk_episode_chain(episodes, k, 20)
        new = walk_generalized(episodes, k, 20)
        old_rate += old["reached_displacement"]
        new_rate += new["reached_progress"]
        n += 1
    if old_rate != new_rate:
        raise AssertionError(
            f"Generalization MISMATCH on SWEEP: sweep-specific reached_displacement={old_rate}/{n} "
            f"vs generalized reached_progress={new_rate}/{n}. Not trusting the generalized walk."
        )
    print(f"verified: generalized walk reproduces SWEEP-specific probe exactly ({old_rate}/{n} both)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--atlas", default="results/decision_atlas_full")
    ap.add_argument("--csv", default="data/mt5/XAUUSD_M15.csv")
    ap.add_argument("--out", default="results/decision_atlas_full/all_states_persistence_probe.json")
    args = ap.parse_args()

    atlas = Path(ROOT / args.atlas)
    verify_matches_sweep_specific(atlas)

    cost_model = sep.load_cost_model()
    import pyarrow.parquet as pq
    dec = {d["decision_id"]: d for d in pq.read_table(atlas / "transition_decision.parquet").to_pylist()}
    episodes = pq.read_table(atlas / "episode.parquet").to_pylist()
    episodes.sort(key=lambda e: e["episode_id"])
    ep_index = {e["episode_id"]: k for k, e in enumerate(episodes)}
    atr_by_bar = {b["bar_index"]: b["live_atr"] for b in pq.read_table(atlas / "envelope_bar.parquet").to_pylist()}
    corpus = sep.p001.load_corpus(ROOT / args.csv)

    STATE_TABLES = {"SWEEP": "sweep_liquidity_fact.parquet",
                    "DISPLACEMENT": "displacement_liquidity_fact.parquet",
                    "EXPANSION": "expansion_liquidity_fact.parquet"}

    results: dict[str, dict] = {}
    for state, fname in STATE_TABLES.items():
        lf = pq.read_table(atlas / fname).to_pylist()
        for r in lf:
            r["cell"] = ("T" if r["breaker_present"] else "F") + ("T" if r["ob_present"] else "F")
        cell_n = {}
        for r in lf:
            cell_n[r["cell"]] = cell_n.get(r["cell"], 0) + 1
        powered_cells = [c for c, n in cell_n.items() if n >= MIN_N]
        state_result = {"cell_population": cell_n, "powered_cells": powered_cells, "H20": {}}
        H = 20
        for cname in powered_cells:
            buckets: dict[str, list[float]] = {"progressed": [], "reverted": [], "still_dwelling": []}
            for r in lf:
                if r["cell"] != cname:
                    continue
                d = dec[r["decision_id"]]
                k = ep_index.get(d["episode_id"])
                if k is None or episodes[k]["state"] != state:
                    continue
                w = walk_generalized(episodes, k, H)
                atr = atr_by_bar.get(r["bar_index"])
                if not atr:
                    continue
                gross = sep.close_at_horizon(corpus, r["bar_index"], d["direction"], atr, H)
                if gross is None:
                    continue
                direction = "long" if d["direction"] == "LONG" else "short"
                cost_r = cost_model.cost_price(exit_kind="TIMEOUT", direction=direction, nights_held=0) / atr
                net = gross - cost_r
                bucket = ("progressed" if w["reached_progress"]
                          else "reverted" if w["reverted_never_progressed"] else "still_dwelling")
                buckets[bucket].append(net)
            cellsum = {}
            for b, vals in buckets.items():
                cellsum[b] = {
                    "n": len(vals),
                    "median": round(st.median(vals), 4) if vals else None,
                    "mean": round(st.mean(vals), 4) if vals else None,
                }
            state_result["H20"][cname] = cellsum
        results[state] = state_result

    artifact = {
        "probe_id": "ALL-STATES-PERSISTENCE-01",
        "claim_class": "DESCRIPTIVE_ONLY",
        "economic_claims_allowed": False,
        "authority": "none",
        "generalization_note": (
            "'progressed' = reached a state with HIGHER CRT ordinal rank than the entry state, "
            "before reverting to RANGE -- verified to reproduce the SWEEP-specific probe exactly "
            "before being trusted on DISPLACEMENT/EXPANSION."
        ),
        "results": results,
    }
    out = ROOT / args.out
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    for state, r in results.items():
        print(f"\n=== {state}: cell population {r['cell_population']}, powered={r['powered_cells']} ===")
        for cname in r["powered_cells"]:
            print(f"  {cname}:")
            for b, s in r["H20"][cname].items():
                if s["n"] == 0:
                    print(f"    {b:14s} n=0")
                else:
                    print(f"    {b:14s} n={s['n']:4d}  median={s['median']:8.4f}  mean={s['mean']:8.4f}")

    print(f"\nartifact: {out}")
    print("DESCRIPTIVE ONLY -- no significance, no economic claim, no finding id.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
