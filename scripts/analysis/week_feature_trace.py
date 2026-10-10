"""
week_feature_trace.py
Trace the 35 CANONICAL_FEATURES for every hour bar of one week, day by day, and check
whether the signed features are negative in SELL ranges and positive in LONG ranges.

Ranges are a hindsight label: LONG = week open -> the bar with the week's highest high,
SELL = the bar after it -> week end. Range-conditioned numbers are therefore DESCRIPTIVE.
The causal check is feature sign at bar t (known at its close) vs the NEXT bar's direction.

Usage:
    python scripts/analysis/week_feature_trace.py --csv data/XAUUSD_H1.csv \
        --start 2025-07-21 --end 2025-07-25 --out results/week_feature_trace_2025_07_21
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402

# name -> (column or derived, centre). Sign = value - centre.
SIGNED = {
    "trend_bias": 0.0, "ema_spread": 0.0, "trend_strength": 0.0, "momentum_score": 0.0,
    "macd_line": 0.0, "macd_hist": 0.0, "rsi_14": 50.0, "break_of_structure": 0.0,
    "liquidity_sweep": 0.0, "structure_hh_ll": 0.0,   # higher_high - lower_low
}


def load_features(csv_path: str) -> pd.DataFrame:
    raw = pd.read_csv(csv_path)
    raw.columns = [c.strip().lower() for c in raw.columns]
    enriched, _ = FeaturePipeline(raw).run()
    df = enriched.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["structure_hh_ll"] = df["higher_high"] - df["lower_low"]
    return df


def week_slice(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    m = (df["timestamp"] >= pd.Timestamp(start)) & (df["timestamp"] < pd.Timestamp(end) + pd.Timedelta(days=1))
    w = df[m].reset_index(drop=True)
    peak = int(w["high"].idxmax())
    w["range"] = np.where(w.index <= peak, "LONG", "SELL")
    w["bar_dir"] = np.sign(w["close"] - w["open"]).astype(int)
    nxt = np.sign(w["close"].shift(-1) - w["open"].shift(-1))
    w["next_dir"] = nxt
    return w


def sym(v: float, centre: float) -> str:
    d = v - centre
    return "+" if d > 1e-9 else "-" if d < -1e-9 else "0"


def binom_p(k: int, n: int) -> float:
    """Two-sided exact binomial p-value vs 0.5."""
    if n == 0:
        return float("nan")
    pk = [math.comb(n, i) / 2 ** n for i in range(n + 1)]
    return min(1.0, sum(p for p in pk if p <= pk[k] + 1e-12))


def sign_stats(w: pd.DataFrame, feat: str, centre: float) -> dict:
    s = np.sign(w[feat] - centre)
    out = {}
    for rng, want in (("LONG", 1), ("SELL", -1)):
        sub = w[w["range"] == rng]
        ss = s[sub.index]
        nz = ss != 0
        out[rng] = {
            "n": int(len(sub)), "mean": float(sub[feat].mean()), "pct_pos": float((ss > 0).mean()),
            "agree": float(((ss == want) & nz).sum() / max(1, nz.sum())),   # sign matches range direction
        }
    # causal: sign at t vs next bar direction (all bars with a next bar and non-zero sign)
    m = w["next_dir"].notna() & (s != 0) & (w["next_dir"] != 0)
    k = int(((s[m] == w.loc[m, "next_dir"])).sum())
    n = int(m.sum())
    out["next"] = {"hit": k, "n": n, "rate": k / n if n else float("nan"), "p": binom_p(k, n)}
    return out


def causality_check(csv_path: str, full: pd.DataFrame, cuts: list, tail: int = 3) -> dict:
    """
    Truncate the file at each cut bar (inclusive), rebuild the features, and compare the last
    `tail` rows with the full-file values for the same timestamps. A causal feature never differs.
    Returns {feature: number of (cut, row) comparisons that differ}.
    """
    raw = pd.read_csv(csv_path)
    raw.columns = [c.strip().lower() for c in raw.columns]
    raw["_ts"] = pd.to_datetime(raw["timestamp"])
    full_idx = full.set_index("timestamp")
    diffs = {f: 0 for f in CANONICAL_FEATURES}
    total = 0
    for cut in cuts:
        part = raw[raw["_ts"] <= pd.Timestamp(cut)].drop(columns=["_ts"])
        enriched, _ = FeaturePipeline(part).run()
        enriched = enriched.copy()
        enriched["timestamp"] = pd.to_datetime(enriched["timestamp"])
        tail_rows = enriched.tail(tail)
        for _, r in tail_rows.iterrows():
            ref = full_idx.loc[r["timestamp"]]
            total += 1
            for f in CANONICAL_FEATURES:
                if f == "session":
                    continue
                a, b = float(r[f]), float(ref[f])
                if not math.isclose(a, b, rel_tol=1e-4, abs_tol=1e-5):
                    diffs[f] += 1
    diffs["_total"] = total
    return diffs


def flips(w: pd.DataFrame, feat: str, centre: float) -> list[tuple[str, str]]:
    s = np.sign(w[feat] - centre)
    res, prev = [], None
    for i, v in enumerate(s):
        if v == 0:
            continue
        if prev is not None and v != prev:
            res.append((w.loc[i, "timestamp"].strftime("%a %H:%M"), "-→+" if v > 0 else "+→-"))
        prev = v
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    df = load_features(a.csv)
    w = week_slice(df, a.start, a.end)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    cols = ["timestamp", "range", "bar_dir", "next_dir"] + list(CANONICAL_FEATURES)
    w[cols].to_csv(out / "trace.csv", index=False)
    peak_ts = w.loc[w["high"].idxmax(), "timestamp"]
    md = [f"peak (highest high) bar: {peak_ts}  | LONG bars {int((w['range']=='LONG').sum())}, SELL bars {int((w['range']=='SELL').sum())}\n"]

    md.append("### Daily hourly sign grids (+ above centre, - below, 0 flat; columns = hour 01..23)\n")
    for day, g in w.groupby(w["timestamp"].dt.date):
        md.append(f"**{day} {pd.Timestamp(day).strftime('%a')}**  (range labels: {''.join('L' if r=='LONG' else 'S' for r in g['range'])})\n```")
        hours = " ".join(f"{h:02d}" for h in g["timestamp"].dt.hour)
        md.append(f"{'hour':<18}{hours}")
        md.append(f"{'bar (close-open)':<18}" + " ".join(f" {'+' if d>0 else '-' if d<0 else '0'}" for d in g["bar_dir"]))
        for f, c in SIGNED.items():
            md.append(f"{f:<18}" + " ".join(f" {sym(v, c)}" for v in g[f]))
        md.append("```\n")

    md.append("### Daily summary: % of hour bars with positive sign, and mean\n")
    rows = ["| Day | Bars | Day move | " + " | ".join(SIGNED) + " |", "|---|---|---|" + "---|" * len(SIGNED)]
    for day, g in w.groupby(w["timestamp"].dt.date):
        mv = g["close"].iloc[-1] - g["open"].iloc[0]
        rows.append(f"| {day} {pd.Timestamp(day).strftime('%a')} | {len(g)} | {mv:+.1f} | " +
                    " | ".join(f"{(np.sign(g[f]-c)>0).mean():.0%}" for f, c in SIGNED.items()) + " |")
    md.append("\n".join(rows) + "\n")

    md.append("### LONG vs SELL range: does the feature sign match the range? (descriptive, hindsight ranges)\n")
    tab = ["| Feature | LONG: % positive | LONG: sign matches (+) | SELL: % positive | SELL: sign matches (−) | Next-bar hit (causal) | p |", "|---|---|---|---|---|---|---|"]
    stats = {}
    for f, c in SIGNED.items():
        s = sign_stats(w, f, c); stats[f] = s
        tab.append(f"| {f} | {s['LONG']['pct_pos']:.0%} | {s['LONG']['agree']:.0%} | {s['SELL']['pct_pos']:.0%} | {s['SELL']['agree']:.0%} | "
                   f"{s['next']['hit']}/{s['next']['n']} = {s['next']['rate']:.0%} | {s['next']['p']:.2f} |")
    md.append("\n".join(tab) + "\n")

    md.append("### Mean values by range\n")
    mt = ["| Feature | LONG mean | SELL mean |", "|---|---|---|"]
    for f in SIGNED:
        mt.append(f"| {f} | {stats[f]['LONG']['mean']:+.3f} | {stats[f]['SELL']['mean']:+.3f} |")
    md.append("\n".join(mt) + "\n")

    md.append("### Sign flips through the week (time of each flip) vs the peak\n")
    for f, c in SIGNED.items():
        fl = flips(w, f, c)
        md.append(f"- `{f}`: {len(fl)} flips — " + ", ".join(f"{t} {d}" for t, d in fl[:14]) + (" …" if len(fl) > 14 else ""))
    md.append(f"\nPeak bar: {peak_ts.strftime('%a %H:%M')}.\n")
    cuts = list(w["timestamp"].iloc[[10, 25, 40, 55, 70, 85, 100]])
    cz = causality_check(a.csv, df, cuts)
    tot = cz.pop("_total")
    md.append(f"### Causality check: rebuild the features on data truncated at {len(cuts)} cut bars and compare the last 3 rows with the full-file values ({tot} row comparisons)\n")
    bad = {f: n for f, n in cz.items() if n}
    md.append("| Feature | Rows that differ |\n|---|---|")
    for f, n in sorted(bad.items(), key=lambda x: -x[1]):
        md.append(f"| {f} | {n} / {tot} |")
    md.append(f"\nCausal (identical in every comparison): {', '.join(f for f in CANONICAL_FEATURES if f not in bad and f != 'session')}\n")
    (out / "tables.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
