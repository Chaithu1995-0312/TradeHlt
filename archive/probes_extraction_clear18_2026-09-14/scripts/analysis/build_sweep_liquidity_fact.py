#!/usr/bin/env python
"""build_sweep_liquidity_fact.py — liquidity/SMC context joined onto SWEEP decisions.

READ-ONLY. DESCRIPTIVE ONLY. No p-values, no verdicts, no economic claim.

WHY THIS EXISTS
---------------
The decision atlas's own context columns (parent_crt_state, parent_bias, objective_status,
htf_state, resolver_site, direction, bars_to_prior_decision) came back FLAT against the SWEEP
tail -- six of seven tested, all near base rate. Those are CONSTRUCTOR variables (what the CRT
state machine / resolver were doing). The remaining candidate is MARKET variables: proximity to
liquidity (PDH/PDL/EQH/EQL), imbalance (FVG), and structure (order block / breaker), all of
which `bar_structure_snapshot` already emits per bar (F-076's 9 SMC primitives) but which the
decision atlas never joined in.

THREE SEMANTIC TRAPS VERIFIED AGAINST SOURCE BEFORE BUILDING THIS
------------------------------------------------------------------
1. `*_distance` fields are `tanh(favorable_sign * (close - level) / atr)`
   (`features/smc/_geometry.py::signed_atr_distance`) -- SIGNED and ATR-normalized, saturating
   toward +-1. Magnitude near 0 means NEAR the level in ATR terms; magnitude near 1 means FAR
   (saturated). This is not intuitive from the name; a reader expecting "distance" to grow with
   proximity would read every number backwards.
2. `distance == 0.0` is NOT "at the level". It is the function's OWN documented return value
   when the level does not exist yet (`pdh_pdl_distance`: "(0.0, 0.0) if no D1 parent has closed
   yet") and, separately, when ATR is non-positive. So `distance` is gated on the paired
   `*_present` boolean here, never tested against zero -- a present=True row with a genuinely
   tiny distance (price sitting right on a level) would otherwise be silently indistinguishable
   from "no level exists".
3. `htf_range_ratio` is NOT price-position-within-range. Source
   (`runtime/parent_crt_feed.py::last_range_ratio`) shows it is
   `curr_parent_range / prev_parent_range` -- the volatility-expansion ratio behind the
   ACCUMULATION/DISTRIBUTION/EXPANSION classifier. The field this module actually wants
   (`htf_range_percentile`, "where is price inside the HTF range") does not exist pre-computed
   and is derived here from `parent_range_h_ref`/`parent_range_l_ref` (both populated on every
   sampled bar) instead of misusing the wrongly-named existing field.

USAGE
    venv/Scripts/python.exe scripts/analysis/build_sweep_liquidity_fact.py \\
        --atlas results/decision_atlas_full \\
        --bar-structure logs/dual_construction_full_gapfix/XAUUSD_bar_structure.jsonl
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

# Reuse the atlas builder's own loader rather than re-parsing the JSONL a second way.
_BDA = ROOT / "scripts" / "analysis" / "build_decision_atlas.py"
_spec = importlib.util.spec_from_file_location("build_decision_atlas", _BDA)
bda = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bda)

#: (present_field, distance_field, output_name) -- the four liquidity levels + three SMC zones.
_GATED_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("pdh_present", "pdh_distance", "pdh"),
    ("pdl_present", "pdl_distance", "pdl"),
    ("eqh_present", "eqh_distance", "eqh"),
    ("eql_present", "eql_distance", "eql"),
    ("fvg_present", "fvg_distance", "fvg"),
    ("order_block_present", "order_block_distance", "ob"),
    ("breaker_present", "breaker_distance", "breaker"),
    ("mitigation_present", "mitigation_distance", "mitigation"),
)
_BULLISH_FIELDS = ("fvg_bullish", "order_block_bullish", "breaker_bullish", "mitigation_bullish")


def gated_row(b: dict) -> dict:
    """One bar's liquidity/SMC context, every distance gated on its own `_present` flag.

    `signed_{name}` keeps the raw signed tanh value (favorable/unfavorable side); `abs_{name}`
    is the proximity magnitude actually asked for. Both NULL when the level does not exist --
    never defaulted to 0.0, which is the function's own "absent" sentinel, not a real distance.
    """
    out: dict = {}
    for present_f, dist_f, name in _GATED_FIELDS:
        present = bool(b.get(present_f))
        val = b.get(dist_f) if present else None
        out[f"{name}_present"] = present
        out[f"signed_{name}"] = float(val) if val is not None else None
        out[f"abs_{name}"] = abs(float(val)) if val is not None else None
    for f in _BULLISH_FIELDS:
        out[f] = b.get(f)

    h, l = b.get("parent_range_h_ref"), b.get("parent_range_l_ref")
    close = b.get("close")
    if h is not None and l is not None and close is not None and h > l:
        out["htf_range_percentile"] = (close - l) / (h - l)
    else:
        out["htf_range_percentile"] = None
    out["htf_state"] = b.get("htf_state")
    out["parent_crt_state"] = b.get("parent_crt_state")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--atlas", default="results/decision_atlas_full")
    ap.add_argument("--bar-structure",
                    default="logs/dual_construction_full_gapfix/XAUUSD_bar_structure.jsonl")
    ap.add_argument("--to-state", default="SWEEP")
    args = ap.parse_args()

    import pyarrow.parquet as pq

    atlas = Path(ROOT / args.atlas)
    dec = pq.read_table(atlas / "transition_decision.parquet").to_pylist()
    sweeps = [d for d in dec if d["to_state"] == args.to_state and d["direction"]]
    bar_idx = {d["bar_index"] for d in sweeps}

    bstruct = bda.load_bar_structure(ROOT / args.bar_structure)
    missing = bar_idx - set(bstruct)
    if missing:
        print(f"FATAL: {len(missing)} decision bar_index(es) absent from bar_structure -- "
              f"join integrity broken. Nothing written.")
        return 1

    rows = []
    for d in sweeps:
        b = bstruct[d["bar_index"]]
        row = {"decision_id": d["decision_id"], "bar_index": d["bar_index"],
               "direction": d["direction"], "episode_id": d["episode_id"]}
        row.update(gated_row(b))
        rows.append(row)

    import pyarrow as pa
    tbl = pa.Table.from_pylist(rows)
    out_path = atlas / f"{args.to_state.lower()}_liquidity_fact.parquet"
    pq.write_table(tbl, out_path, compression="zstd")

    print(f"{args.to_state}_liquidity_fact: {len(rows)} rows -> {out_path}")
    n_present = {name: sum(1 for r in rows if r[f"{name}_present"])
                 for _, _, name in _GATED_FIELDS}
    print("presence rate (of", len(rows), "decisions):")
    for name, n in n_present.items():
        print(f"  {name:10s} {n:5d}  ({100.0 * n / len(rows):.1f}%)")
    n_pct = sum(1 for r in rows if r["htf_range_percentile"] is not None)
    print(f"  htf_range_percentile populated: {n_pct} ({100.0*n_pct/len(rows):.1f}%)")
    print("\nDESCRIPTIVE ONLY -- no significance, no economic claim, no finding id.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
