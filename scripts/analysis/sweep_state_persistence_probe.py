#!/usr/bin/env python
"""sweep_state_persistence_probe.py — did the move PERSIST, split by breaker/OB structure.

READ-ONLY. DESCRIPTIVE ONLY. No p-values, no verdicts, no economic claim.

WHY THIS EXISTS
---------------
The economic probe found TF (breaker present, OB absent) has favorable excursion comparable to
FT/TT but a WORSE realized outcome at longer horizons -- the move happens but is not held. That
distinguishes "did price move" from "did price keep the move", which is a STATE question (did
the engine's own construction progress: SWEEP -> DISPLACEMENT -> EXPANSION) rather than a payoff
question.

THE METHODOLOGICAL TRAP THIS PROBE WAS BUILT TO AVOID
------------------------------------------------------
A first draft scanned `engine_state` over a raw N-bar window looking for "does DISPLACEMENT
ever appear". That is WRONG: if a SWEEP reverts to RANGE quickly, a completely unrelated new
RANGE->SWEEP->DISPLACEMENT cycle can start later in the SAME N-bar window, and a raw bar-scan
would credit THIS sweep with progressing when it did not -- exactly the kind of cross-episode
contamination this investigation's discipline exists to catch (the same class of error as
counting resolver dwell bars as independent decisions, or reading a pooled statistic across
unrelated episodes).

THE CORRECT OBJECT: THE EPISODE CHAIN
--------------------------------------
`episode.parquet` is already a chronologically-ordered, gapless partition of every bar into
maximal same-state runs (built once in `build_decision_atlas.py`). Episode index k+1 is BY
CONSTRUCTION the run that immediately follows episode k -- there is no gap and no way for an
unrelated later cycle to be mistaken for this one. So "what did this SWEEP become" is answered
by walking episode[k+1], episode[k+2], ... and STOPPING the instant occupancy returns to RANGE
(that boundary marks a genuinely new, unrelated cycle beginning) or the horizon's bar-budget is
exhausted -- never by re-scanning raw bar labels.

THE OBJECT
----------
Per SWEEP decision (which OPENS a SWEEP-state episode), walk the episode chain forward,
accumulating `bars` per hop, up to a bar-budget of N in {20,40,80}:
  - reached_displacement / lag_to_displacement (cumulative bars to the DISPLACEMENT episode's
    start)
  - reached_expansion / lag_to_expansion (only meaningful after DISPLACEMENT; requires the
    chain to continue DISPLACEMENT -> EXPANSION within budget)
  - reverted_never_progressed / lag_to_reversion: the chain hits RANGE before ever reaching
    DISPLACEMENT -- BOUNDARY, stop walking (a RANGE episode is where a new, unrelated cycle
    could start; walking past it would reintroduce the exact contamination this probe exists
    to avoid)
  - still_dwelling: the budget exhausted before DISPLACEMENT/EXPANSION/RANGE was reached (the
    chain was still inside a non-RANGE episode, e.g. still dwelling in SWEEP or DISPLACEMENT)

Precedence: reaching DISPLACEMENT/EXPANSION beats a LATER reversion within the same walk --
"progressed, then later reverted" and "reverted having never progressed" are kept distinct,
because they describe different market behaviour even though both eventually return to RANGE.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

HORIZONS = (20, 40, 80)


def walk_episode_chain(episodes: list[dict], start_k: int, horizon: int) -> dict:
    """episodes[start_k] is the SWEEP episode itself. Walk forward summing `bars`."""
    cum = 0
    lag_disp = lag_exp = lag_range = None
    k = start_k + 1
    n = len(episodes)
    while k < n and cum < horizon:
        ep = episodes[k]
        cum += ep["bars"]
        if lag_disp is None and ep["state"] == "DISPLACEMENT":
            lag_disp = cum
        elif lag_disp is not None and lag_exp is None and ep["state"] == "EXPANSION":
            lag_exp = cum
        if ep["state"] == "RANGE":
            lag_range = cum
            break  # BOUNDARY: stop here, never walk past a RANGE episode.
        if ep.get("right_censored"):
            break
        k += 1
    reached_progress = lag_disp is not None
    return {
        "reached_displacement": lag_disp is not None and lag_disp <= horizon,
        "lag_to_displacement": lag_disp if (lag_disp is not None and lag_disp <= horizon) else None,
        "reached_expansion": lag_exp is not None and lag_exp <= horizon,
        "lag_to_expansion": lag_exp if (lag_exp is not None and lag_exp <= horizon) else None,
        "reverted_never_progressed": (lag_range is not None and lag_range <= horizon
                                       and not reached_progress),
        "lag_to_reversion": (lag_range if (lag_range is not None and lag_range <= horizon
                                            and not reached_progress) else None),
        "right_censored_in_window": k < n and bool(episodes[k].get("right_censored")) and cum <= horizon,
    }


def cell(r: dict) -> str:
    return ("T" if r["breaker_present"] else "F") + ("T" if r["ob_present"] else "F")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--atlas", default="results/decision_atlas_full")
    ap.add_argument("--out", default="results/decision_atlas_full/sweep_state_persistence_probe.json")
    args = ap.parse_args()

    import pyarrow.parquet as pq
    atlas = Path(ROOT / args.atlas)
    lf = pq.read_table(atlas / "sweep_liquidity_fact.parquet").to_pylist()
    dec = {d["decision_id"]: d for d in pq.read_table(atlas / "transition_decision.parquet").to_pylist()}
    episodes = pq.read_table(atlas / "episode.parquet").to_pylist()
    episodes.sort(key=lambda e: e["episode_id"])
    # Structural invariant: episode_id order must equal chronological order (by construction in
    # build_decision_atlas.py), or "index+1 = next episode" is unsafe. Verify before trusting it.
    ts_order = [e["entry_ts"] for e in episodes]
    if ts_order != sorted(ts_order):
        print("FATAL: episode.parquet is not chronologically ordered by episode_id -- "
              "the chain-walk assumption is unsafe. Nothing measured.")
        return 1
    ep_index = {e["episode_id"]: k for k, e in enumerate(episodes)}

    for r in lf:
        r["cell"] = cell(r)

    results: dict[str, dict] = {}
    for H in HORIZONS:
        by_cell: dict[str, list[dict]] = {}
        skipped_no_episode = 0
        for r in lf:
            d = dec[r["decision_id"]]
            eid = d["episode_id"]
            k = ep_index.get(eid)
            if k is None or episodes[k]["state"] != "SWEEP":
                skipped_no_episode += 1
                continue
            sc = walk_episode_chain(episodes, k, H)
            by_cell.setdefault(r["cell"], []).append(sc)
        if skipped_no_episode:
            print(f"H{H}: {skipped_no_episode} decisions had no matching SWEEP episode (unexpected)")

        cellsum = {}
        for cname, rows in by_cell.items():
            n = len(rows)
            disp_lags = [x["lag_to_displacement"] for x in rows if x["lag_to_displacement"]]
            exp_lags = [x["lag_to_expansion"] for x in rows if x["lag_to_expansion"]]
            rev_lags = [x["lag_to_reversion"] for x in rows if x["lag_to_reversion"]]
            still_dwelling = sum(
                1 for x in rows
                if not x["reached_displacement"] and not x["reverted_never_progressed"]
            )
            cellsum[cname] = {
                "n": n,
                "reached_displacement_rate": round(sum(x["reached_displacement"] for x in rows) / n, 4),
                "reached_expansion_rate": round(sum(x["reached_expansion"] for x in rows) / n, 4),
                "reverted_never_progressed_rate": round(sum(x["reverted_never_progressed"] for x in rows) / n, 4),
                "still_dwelling_rate": round(still_dwelling / n, 4),
                "median_lag_to_displacement": round(st.median(disp_lags), 2) if disp_lags else None,
                "median_lag_to_expansion": round(st.median(exp_lags), 2) if exp_lags else None,
                "median_lag_to_reversion": round(st.median(rev_lags), 2) if rev_lags else None,
            }
        results[f"H{H}"] = cellsum

    artifact = {
        "probe_id": "SWEEP-STATE-PERSISTENCE-01",
        "claim_class": "DESCRIPTIVE_ONLY",
        "economic_claims_allowed": False,
        "authority": "none",
        "object_note": (
            "Walks the EPISODE CHAIN (not a raw bar-window scan) to avoid crediting a SWEEP "
            "with progress made by a later, unrelated cycle. Stops at the first RANGE episode "
            "encountered -- that boundary is where a new cycle could begin."
        ),
        "results": results,
    }
    out = ROOT / args.out
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    for H in HORIZONS:
        print(f"\n=== H={H} (bar-budget walked along the episode chain) ===")
        print(f"{'cell':6s} {'n':>5s} {'->DISP%':>8s} {'->EXP%':>7s} {'reverted%':>10s} "
              f"{'dwelling%':>10s} {'med_lag_disp':>13s} {'med_lag_rev':>12s}")
        for cname in ("FF", "TF", "FT", "TT"):
            c = results[f"H{H}"].get(cname)
            if not c:
                continue
            print(f"{cname:6s} {c['n']:5d} {100*c['reached_displacement_rate']:8.1f} "
                  f"{100*c['reached_expansion_rate']:7.1f} "
                  f"{100*c['reverted_never_progressed_rate']:10.1f} "
                  f"{100*c['still_dwelling_rate']:10.1f} "
                  f"{c['median_lag_to_displacement'] or 0:13.1f} "
                  f"{c['median_lag_to_reversion'] or 0:12.1f}")

    print(f"\nartifact: {out}")
    print("DESCRIPTIVE ONLY -- no significance, no economic claim, no finding id.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
