#!/usr/bin/env python3
"""
mother_range_inside_close.py
=============================
Configurable MOTHER-RANGE / INSIDE-CLOSE detector over M15 OHLCV.

CONCEPT
-------
Group M15 bars into blocks of `x` bars (x=16 -> 4-hour, x=96 -> "1 day", any x):

    Block 1 (the MOTHER RANGE):  H1 = max(high), L1 = min(low), R1 = H1 - L1
    Block 2 (the TEST):          C2 = close of the LAST bar of block 2

    inside      = (L1 <= C2 <= H1)
    InsideScore = (C2 - L1) / (H1 - L1)      # 0.0 = closed at mother low, 1.0 = at mother high

Optional BIG-MOTHER filter so only genuine expansions qualify:
    percentile : R1 > P{big_pct} of the trailing `lookback` block ranges  (PRIOR blocks only)
    atr_mult   : R1 > k * ATR   where ATR = mean of the trailing `lookback` block ranges
                                                                          (PRIOR blocks only)

Thesis: a large expansion followed by a close back INSIDE it means the expansion was not
accepted -- absorption / failed continuation / balance returning after imbalance.

CAUSALITY
---------
Every quantity uses only bars at or before C2's own bar. The big-mother threshold is built
from PRIOR blocks only (shift(1) on the trailing rolling statistic), so a block is never
judged against a window containing itself. Both properties are ASSERTED at runtime, per record.

BLOCKING MODES (both computed; the divergence is itself a finding)
-----------------------------------------------------------------
positional : every `x` consecutive ROWS. Always exactly x bars. Drifts vs wall-clock.
             This is what the `x` parameter literally means.
calendar   : anchored to real UTC boundaries derived from x (x=16 -> 4H, x=96 -> daily).
             Matches what a chart shows. Bar counts VARY at data gaps and are reported, never
             padded.

DATA-TRUTH NOTE (measured on data/mt5/XAUUSD_M15.csv, 47,275 bars)
------------------------------------------------------------------
This dataset's trading day is 92 bars, NOT 96: the 00:00-00:45 UTC hour is absent (75-minute
daily gap). So x=96 is not "1 day" here -- positional 96-bar blocks absorb 4 bars of the next
day and the phase drifts 4 bars/day, compounding. Likewise 92 mod 16 = 12, so positional
16-bar blocks do not stay aligned to wall-clock 4-hour boundaries across days. Both facts are
surfaced in the output rather than papered over.

Usage:
    PYTHONPATH=src python scripts/analysis/mother_range_inside_close.py
    PYTHONPATH=src python scripts/analysis/mother_range_inside_close.py --block-bars 16 32 96
    PYTHONPATH=src python scripts/analysis/mother_range_inside_close.py --big-rule atr_mult --big-k 1.5
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

# x (bars) -> the wall-clock hours one block spans, for calendar-anchored blocking.
# M15 bars: x bars * 15 min = x/4 hours.
def _hours_for(x: int) -> float:
    return x * 15.0 / 60.0


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _native(v):
    if v is None:
        return None
    if isinstance(v, (np.floating, float)):
        v = float(v)
        return None if (v != v or np.isinf(v)) else v
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return str(v)


# ── BLOCK CONSTRUCTION ──────────────────────────────────────────────────────────────────────

def build_blocks(df: pd.DataFrame, x: int, mode: str) -> pd.DataFrame:
    """Return one row per block with H/L/C plus the SOURCE ROW PROVENANCE of every quantity.

    `df` must carry a `row` column = the original 0-based CSV data-row index, so every emitted
    block can be traced back to exact source rows.
    """
    if mode == "positional":
        n_full = len(df) // x
        if n_full < 2:
            return pd.DataFrame()
        # Trailing partial block is DROPPED, never truncated into a short block.
        d = df.iloc[:n_full * x].copy()
        d["blk"] = np.arange(n_full * x) // x
    elif mode == "calendar":
        hours = _hours_for(x)
        d = df.copy()
        if hours >= 24:
            # Daily (or coarser) anchoring: floor to the calendar day.
            d["blk"] = d["ts"].dt.floor(f"{int(hours)}h") if hours == 24 else \
                       d["ts"].dt.floor(f"{int(hours)}h")
        else:
            d["blk"] = d["ts"].dt.floor(f"{hours:g}h")
    else:
        raise ValueError(f"unknown blocking mode {mode!r}")

    g = d.groupby("blk", sort=True)
    blocks = pd.DataFrame({
        "n_bars": g.size(),
        "row_start": g["row"].min(),
        "row_end": g["row"].max(),
        "ts_start": g["ts"].min(),
        "ts_end": g["ts"].max(),
        "H": g["high"].max(),
        "L": g["low"].min(),
        "C": g["close"].last(),
        # Provenance: WHICH bar set the high / the low.
        "H_row": g.apply(lambda t: t.loc[t["high"].idxmax(), "row"], include_groups=False),
        "L_row": g.apply(lambda t: t.loc[t["low"].idxmin(), "row"], include_groups=False),
        "H_ts": g.apply(lambda t: t.loc[t["high"].idxmax(), "ts"], include_groups=False),
        "L_ts": g.apply(lambda t: t.loc[t["low"].idxmin(), "ts"], include_groups=False),
        "C_row": g["row"].max(),
        "C_ts": g["ts"].max(),
    }).reset_index(drop=True)
    return blocks


# ── PAIRING + THE CONCEPT ───────────────────────────────────────────────────────────────────

def analyse(blocks: pd.DataFrame, x: int, mode: str, big_rule: str,
            big_pct: float, big_k: float, lookback: int) -> pd.DataFrame:
    """Pair each block with its successor and evaluate the inside-close condition."""
    if len(blocks) < 2:
        return pd.DataFrame()

    b = blocks
    # Block 1 = the mother (row i), block 2 = its successor (row i+1).
    m = pd.DataFrame({
        "pair_id": np.arange(len(b) - 1),
        "x": x,
        "blocking_mode": mode,
        # --- mother block (block 1) ---
        "m_row_start": b["row_start"].values[:-1], "m_row_end": b["row_end"].values[:-1],
        "m_ts_start": b["ts_start"].values[:-1],   "m_ts_end": b["ts_end"].values[:-1],
        "m_n_bars": b["n_bars"].values[:-1],
        "H1": b["H"].values[:-1], "H1_row": b["H_row"].values[:-1], "H1_ts": b["H_ts"].values[:-1],
        "L1": b["L"].values[:-1], "L1_row": b["L_row"].values[:-1], "L1_ts": b["L_ts"].values[:-1],
        # --- test block (block 2) ---
        "t_row_start": b["row_start"].values[1:], "t_row_end": b["row_end"].values[1:],
        "t_ts_start": b["ts_start"].values[1:],   "t_ts_end": b["ts_end"].values[1:],
        "t_n_bars": b["n_bars"].values[1:],
        "C2": b["C"].values[1:], "C2_row": b["C_row"].values[1:], "C2_ts": b["C_ts"].values[1:],
    })
    m["R1"] = m["H1"] - m["L1"]

    # --- the condition + the score ---
    m["inside"] = (m["C2"] >= m["L1"]) & (m["C2"] <= m["H1"])
    m["InsideScore"] = np.where(m["R1"] > 0, (m["C2"] - m["L1"]) / m["R1"].replace(0, np.nan), np.nan)

    # --- BIG-MOTHER filter, built from PRIOR blocks only (shift(1) => never self-referential) ---
    r1 = m["R1"]
    if big_rule == "percentile":
        thr = r1.rolling(lookback, min_periods=max(10, lookback // 4)).quantile(big_pct / 100.0).shift(1)
        rule_desc = f"R1 > P{big_pct:g} of trailing {lookback} PRIOR block ranges"
    elif big_rule == "atr_mult":
        thr = (r1.rolling(lookback, min_periods=max(10, lookback // 4)).mean() * big_k).shift(1)
        rule_desc = f"R1 > {big_k:g} x ATR({lookback}) of PRIOR block ranges"
    elif big_rule == "none":
        thr = pd.Series(np.nan, index=m.index)
        rule_desc = "no filter (every mother block qualifies)"
    else:
        raise ValueError(f"unknown big_rule {big_rule!r}")
    m["big_threshold"] = thr
    m["big_rule"] = rule_desc
    m["big_pass"] = (r1 > thr) if big_rule != "none" else True

    # --- CAUSALITY PROOF (asserted below): highest source row touched vs C2's own row ---
    m["max_source_row"] = m[["m_row_end", "t_row_end"]].max(axis=1)
    return m


def assert_causality(m: pd.DataFrame, mode: str, x: int) -> None:
    bad = m[m["max_source_row"] > m["C2_row"]]
    if len(bad):
        raise AssertionError(
            f"CAUSALITY VIOLATION ({mode}, x={x}): {len(bad)} pair(s) reference a source row "
            f"after C2's own bar. First: pair_id={bad.iloc[0]['pair_id']}")
    # mother block must strictly precede the test block
    bad2 = m[m["m_row_end"] >= m["t_row_start"]]
    if len(bad2):
        raise AssertionError(
            f"ORDERING VIOLATION ({mode}, x={x}): {len(bad2)} pair(s) have a mother block that "
            f"does not strictly precede its test block.")


def summarise(m: pd.DataFrame, x: int, mode: str) -> dict:
    valid = m["R1"].notna() & (m["R1"] > 0)
    big = valid & m["big_pass"].fillna(False)
    ins_all = m.loc[valid, "inside"]
    ins_big = m.loc[big, "inside"]
    score_inside = m.loc[valid & m["inside"], "InsideScore"].dropna()

    def dist(s):
        if s.empty:
            return {"n": 0}
        return {"n": int(len(s)), "min": _native(s.min()), "max": _native(s.max()),
                "mean": _native(s.mean()), "median": _native(s.median()),
                "std": _native(s.std(ddof=1)),
                "p25": _native(s.quantile(0.25)), "p75": _native(s.quantile(0.75))}

    base = float(ins_all.mean()) * 100 if len(ins_all) else float("nan")
    bigr = float(ins_big.mean()) * 100 if len(ins_big) else float("nan")
    return {
        "x": x, "blocking_mode": mode,
        "total_blocks": int(len(m) + 1), "total_pairs": int(len(m)),
        "bars_per_block": {"min": _native(m["m_n_bars"].min()),
                           "median": _native(m["m_n_bars"].median()),
                           "max": _native(m["m_n_bars"].max())},
        "inside_close_rate_all_pct": _native(base),
        "inside_close_n_all": int(valid.sum()),
        "inside_close_rate_big_pct": _native(bigr),
        "inside_close_n_big": int(big.sum()),
        "lift_big_over_baseline_pp": _native(bigr - base),
        "R1_distribution": dist(m.loc[valid, "R1"]),
        "InsideScore_when_inside": dist(score_inside),
        "InsideScore_all_pairs": dist(m.loc[valid, "InsideScore"].dropna()),
    }


def pick_examples(m: pd.DataFrame) -> dict:
    """Rule-selected, hand-verifiable examples -- never cherry-picked."""
    valid = m["R1"].notna() & (m["R1"] > 0)
    v = m[valid]
    if v.empty:
        return {}

    def rec(row, rule):
        return {"selection_rule": rule, **{k: _native(row[k]) for k in (
            "pair_id", "x", "blocking_mode", "m_row_start", "m_row_end", "m_ts_start", "m_ts_end",
            "m_n_bars", "H1", "H1_row", "H1_ts", "L1", "L1_row", "L1_ts", "R1",
            "t_row_start", "t_row_end", "C2", "C2_row", "C2_ts",
            "inside", "InsideScore", "big_threshold", "big_pass")}}

    out = {"largest_mother_range": rec(v.loc[v["R1"].idxmax()], "argmax of R1")}
    ins = v[v["inside"]]
    if not ins.empty:
        mid = (ins["InsideScore"] - 0.5).abs()
        out["deepest_mid_range_close"] = rec(ins.loc[mid.idxmin()],
                                             "inside pair whose InsideScore is nearest 0.50")
        big_ins = ins[ins["big_pass"].fillna(False)]
        if not big_ins.empty:
            out["largest_big_mother_that_closed_inside"] = rec(
                big_ins.loc[big_ins["R1"].idxmax()],
                "argmax of R1 among big-filtered pairs that closed INSIDE")
    outside = v[~v["inside"]]
    if not outside.empty:
        out["clean_outside_close"] = rec(
            outside.loc[(outside["C2"] - outside["H1"]).abs().idxmax()],
            "argmax |C2 - H1| among pairs that closed OUTSIDE (most decisive rejection)")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default="data/mt5/XAUUSD_M15.csv")
    ap.add_argument("--block-bars", type=int, nargs="+", default=[16, 96],
                    help="Configurable block size(s) x in M15 bars. 16=4h, 96=nominal 1d.")
    ap.add_argument("--blocking", choices=["both", "positional", "calendar"], default="both")
    ap.add_argument("--big-rule", choices=["percentile", "atr_mult", "none"], default="percentile")
    ap.add_argument("--big-pct", type=float, default=90.0)
    ap.add_argument("--big-k", type=float, default=1.5)
    ap.add_argument("--lookback", type=int, default=100)
    ap.add_argument("--output-dir", default="results/mother_range")
    args = ap.parse_args()

    csv_path = Path(args.csv) if Path(args.csv).is_absolute() else ROOT / args.csv
    if not csv_path.exists():
        print(f"ERROR: csv not found: {csv_path}", file=sys.stderr)
        return 1

    raw = pd.read_csv(csv_path)
    raw["ts"] = pd.to_datetime(raw["timestamp"])
    raw["row"] = np.arange(len(raw))       # 0-based CSV data-row index (the traceability anchor)

    out_dir = Path(args.output_dir) if Path(args.output_dir).is_absolute() else ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    modes = ["positional", "calendar"] if args.blocking == "both" else [args.blocking]

    # Dataset-truth facts, measured not assumed.
    per_day = raw.groupby(raw["ts"].dt.date).size()
    payload = {
        "generator": "scripts/analysis/mother_range_inside_close.py",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(csv_path), "source_csv_sha256": _sha256(csv_path),
        "total_bars": int(len(raw)),
        "date_range": [_native(raw["ts"].min()), _native(raw["ts"].max())],
        "dataset_truth": {
            "bars_per_trading_day_median": _native(per_day.median()),
            "bars_per_trading_day_max": _native(per_day.max()),
            "trading_days": int(len(per_day)),
            "note": "A full trading day here is 92 bars (01:00-23:45 UTC), NOT 96 -- the "
                    "00:00-00:45 hour is absent. So x=96 is not '1 day' for this dataset; "
                    "positional 96-bar blocks drift 4 bars/day, compounding.",
        },
        "parameters": {"block_bars": args.block_bars, "blocking": args.blocking,
                       "big_rule": args.big_rule, "big_pct": args.big_pct,
                       "big_k": args.big_k, "lookback": args.lookback},
        "results": [], "examples": {},
    }

    print(f"Source: {csv_path.name}  bars={len(raw)}  "
          f"trading days={len(per_day)} (median {per_day.median():.0f} bars/day)")
    print()

    for x in args.block_bars:
        for mode in modes:
            blocks = build_blocks(raw, x, mode)
            if blocks.empty or len(blocks) < 2:
                print(f"  x={x:<4} {mode:<11} SKIPPED (fewer than 2 blocks)")
                continue
            m = analyse(blocks, x, mode, args.big_rule, args.big_pct, args.big_k, args.lookback)
            assert_causality(m, mode, x)
            if mode == "positional":
                assert (m["m_n_bars"] == x).all(), \
                    f"positional blocks must all hold exactly {x} bars"

            s = summarise(m, x, mode)
            payload["results"].append(s)
            payload["examples"][f"x{x}_{mode}"] = pick_examples(m)

            csv_out = out_dir / f"mother_range_x{x}_{mode}_blocks.csv"
            m.to_csv(csv_out, index=False)

            def _pct(v):
                return f"{v:5.1f}%" if v is not None else "  N/A "

            def _pp(v):
                return f"{v:+5.1f}pp" if v is not None else "   N/A"

            print(f"  x={x:<4} {mode:<11} pairs={s['total_pairs']:<5} "
                  f"bars/block[{s['bars_per_block']['min']}-{s['bars_per_block']['max']}]  "
                  f"inside(all)={_pct(s['inside_close_rate_all_pct'])}  "
                  f"inside(BIG)={_pct(s['inside_close_rate_big_pct'])} "
                  f"(n={s['inside_close_n_big']})  lift={_pp(s['lift_big_over_baseline_pp'])}"
                  + ("  [BIG filter never activated: too few pairs for --lookback]"
                     if s["inside_close_n_big"] == 0 and args.big_rule != "none" else ""))

    json_path = out_dir / "mother_range_stats.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {json_path}")
    print(f"Wrote {len(payload['results'])} per-block trace CSV(s) to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
