#!/usr/bin/env python
"""
Conditional meta-analysis of the 20-day-purge event corpus (read-only post-processing).

Consumes the `*_setups_reversion.csv` files produced by purge_delay_scan.py and asks the
CONDITIONAL question ("under what conditions does the purge behave differently?") rather than the
unconditional one. Methodology (per user spec):

  * Per-instrument FIRST (economics preserved), then a META-ANALYSIS of the instrument-level
    effects -- NOT pooled trades (crypto would dominate a raw pool).
  * Unit = ATR-normalized R-multiple (`ret_R_*`), so FX / crypto / gold are comparable while
    keeping economic meaning.
  * Anti-dredging filter = CROSS-INSTRUMENT CONSISTENCY (k/N same sign), not the largest cell.

FROZEN conditioning set (4 marginal axes only -- do NOT add weekday/month/EMA/RSI/CRT this pass):
  signal (BUY/SELL = lows/highs) | session | atr_tercile (volatility regime) | pen_tercile (purge
  magnitude). Marginal (one axis at a time) is the low-multiple-comparison first look; a combo pass
  is a GATED follow-up only if an axis shows cross-instrument consistency here.

Ranking (three-tier, Tier-1 dominates): (1) consistency k/N -> (2) magnitude |mean R| ->
(3) evidence = median instrument n. Ties broken by temporal sign-stability.

THIS IS HYPOTHESIS-GENERATING, NOT A FINDING. A surviving slice is a pre-registration CANDIDATE
for a separate significance/OOS test -- nothing acts on this table.

Usage:
    python scripts/analysis/purge_slice.py
    python scripts/analysis/purge_slice.py --glob "data/*_setups_reversion.csv" --min-n 30 --top 10
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd

HORIZONS = ["1h", "2h", "4h", "1d"]
DIMENSIONS = ["signal", "session", "atr_tercile", "pen_tercile"]


def _instrument(path: str) -> str:
    return os.path.basename(path).split("_")[0]


def load_corpus(pattern: str) -> pd.DataFrame:
    frames = []
    for p in sorted(glob.glob(pattern)):
        d = pd.read_csv(p)
        d["instrument"] = _instrument(p)
        frames.append(d)
    if not frames:
        raise SystemExit(f"No files matched {pattern!r}. Run purge_delay_scan.py first.")
    return pd.concat(frames, ignore_index=True)


def add_terciles(df: pd.DataFrame) -> pd.DataFrame:
    """atr_tercile from the global volatility rank; pen_tercile per-instrument."""
    def atr_t(v):
        if pd.isna(v):
            return np.nan
        return "low" if v < 1 / 3 else ("high" if v > 2 / 3 else "mid")
    df["atr_tercile"] = df["atr_pctile"].map(atr_t)

    df["pen_tercile"] = pd.Series(pd.NA, index=df.index, dtype="object")
    for inst, g in df.groupby("instrument"):
        vals = g["pen_atr"]
        try:
            labels = pd.qcut(vals, 3, labels=["low", "mid", "high"]).astype("object")
            df.loc[g.index, "pen_tercile"] = labels
        except (ValueError, IndexError):
            pass  # too few distinct values for this instrument -> leave NA
    return df


def _meta(sub: pd.DataFrame, col: str, min_n: int) -> dict | None:
    """Meta-analysis of instrument-level mean R for one slice at one horizon."""
    means, ns = [], []
    for _inst, g in sub.groupby("instrument"):
        vals = g[col].dropna()
        if len(vals) < min_n:
            continue
        means.append(float(vals.mean()))
        ns.append(len(vals))
    if not means:
        return None
    means = np.array(means)
    ns = np.array(ns)
    N = len(means)
    return {
        "k": int((means > 0).sum()),
        "N": N,
        "mean_R": float(means.mean()),          # equal-weight across instruments
        "median_R": float(np.median(means)),
        "between_SD": float(means.std(ddof=1)) if N > 1 else 0.0,
        "median_n": int(np.median(ns)),
    }


def _recommend(kN: float, N: int, stability: int, median_n: int, min_n: int) -> str:
    if N >= 6 and kN >= 7 / 8 and stability >= 3 and median_n >= min_n:
        return "Candidate"
    if N >= 5 and kN >= 6 / 8 and stability >= 2:
        return "Watch"
    return "Ignore"


def slice_report(df: pd.DataFrame, min_n: int, top_n: int) -> None:
    rcols = {h: f"ret_R_{h}" for h in HORIZONS if f"ret_R_{h}" in df.columns}
    horizons = [h for h in HORIZONS if h in rcols]

    # ---- Unsliced sanity: meta over ALL events (reproduces unconditional per-inst means) ----
    print("=" * 92)
    print("UNCONDITIONAL (all events) meta -- equal-weight instrument mean R:")
    base = {h: _meta(df, rcols[h], min_n) for h in horizons}
    print("  " + " | ".join(
        f"{h}: mean_R={base[h]['mean_R']:+.3f} k/N={base[h]['k']}/{base[h]['N']}"
        for h in horizons if base[h]))
    print()

    rows = []  # for Top-N (one per dimension/bucket/horizon)
    for dim in DIMENSIONS:
        buckets = [b for b in df[dim].dropna().unique()]
        # keep a stable, meaningful order
        order = {"low": 0, "mid": 1, "high": 2, "BUY": 0, "SELL": 1,
                 "Asia": 0, "London": 1, "Overlap": 2, "NY": 3, "Late": 4}
        buckets = sorted(buckets, key=lambda b: order.get(b, 99))

        print("-" * 92)
        print(f"DIMENSION: {dim}")
        header = f"{'bucket':<10}" + "".join(f"{h:>18}" for h in horizons)
        print(header)
        print(f"{'':<10}" + "".join(f"{'meanR  k/N':>18}" for _ in horizons))

        for b in buckets:
            sub = df[df[dim] == b]
            metas = {h: _meta(sub, rcols[h], min_n) for h in horizons}
            # temporal sign-stability across horizons (dominant sign count)
            signs = [np.sign(metas[h]["mean_R"]) for h in horizons if metas[h]]
            if signs:
                dom = 1 if sum(s > 0 for s in signs) >= sum(s < 0 for s in signs) else -1
                stability = sum(1 for s in signs if s == dom)
            else:
                stability = 0
            cells = []
            for h in horizons:
                m = metas[h]
                if m is None:
                    cells.append(f"{'--':>18}")
                    continue
                cells.append(f"{m['mean_R']:+.3f} {m['k']}/{m['N']:>2}".rjust(18))
                rows.append({
                    "condition": f"{dim}={b} @{h}",
                    "k": m["k"], "N": m["N"], "kN": m["k"] / m["N"],
                    "mean_R": m["mean_R"], "median_R": m["median_R"],
                    "between_SD": m["between_SD"], "median_n": m["median_n"],
                    "stability": stability,
                })
            print(f"{str(b):<10}" + "".join(cells) + f"   [sign-stability {stability}/{len(horizons)}]")
        print()

    # ---- Top-N: three-tier ranking (consistency -> magnitude -> evidence), stability tiebreak ----
    ranked = sorted(
        rows,
        key=lambda r: (r["kN"], abs(r["mean_R"]), r["median_n"], r["stability"]),
        reverse=True,
    )[:top_n]

    print("=" * 92)
    print(f"TOP {top_n} CONDITIONAL SLICES  (ranked: consistency k/N -> |mean R| -> median n)")
    print(f"{'#':>2}  {'condition':<24}{'k/N':>6}{'mean_R':>9}{'med_R':>8}"
          f"{'btwSD':>8}{'stab':>6}{'med_n':>7}  recommendation")
    for i, r in enumerate(ranked, 1):
        rec = _recommend(r["kN"], r["N"], r["stability"], r["median_n"], min_n)
        print(f"{i:>2}  {r['condition']:<24}{r['k']}/{r['N']:<3}{r['mean_R']:>+9.3f}"
              f"{r['median_R']:>+8.3f}{r['between_SD']:>8.3f}"
              f"{r['stability']:>4}/{len(horizons)}{r['median_n']:>7}  {rec}")
    print()
    print("NOTE: descriptive / hypothesis-generating ONLY. Unit = ATR-normalized R-multiple.")
    print("      Cross-instrument consistency (k/N) is the anti-dredge filter, not magnitude.")
    print("      Recommendation is capped at 'Candidate' (for pre-registration + OOS). Nothing acts")
    print("      on this table. continuation mode = exact per-event sign-flip of these slices.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Conditional meta-analysis of the purge event corpus.")
    ap.add_argument("--glob", default="data/*_setups_reversion.csv", help="Setups CSV glob.")
    ap.add_argument("--min-n", type=int, default=30, help="Min events per instrument-cell to count (default 30).")
    ap.add_argument("--top", type=int, default=10, help="Top-N slices to rank (default 10).")
    args = ap.parse_args(argv)

    df = load_corpus(args.glob)
    df = add_terciles(df)
    instruments = sorted(df["instrument"].unique())
    print(f"Corpus: {len(df):,} events across {len(instruments)} instruments: {', '.join(instruments)}")
    slice_report(df, args.min_n, args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
