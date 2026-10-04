#!/usr/bin/env python3
"""
evaluate_bar_features_outcome.py

Screens 10 OHLCV-only candidate predictors of the next-12-bar outcome:

    "Over the next 3 hours (12 x M15 bars), does price reach +1.5 ATR
     before -1.0 ATR (up-first), -1.5 ATR before +1.0 ATR (down-first),
     or neither?"

Each candidate is computed from the *previous* 12 bars only (the "feature
window"). ATR(12) = mean(high-low) over those 12 bars; ATR(48) = mean(high-low)
over the prior 48 bars. Forward outcome thresholds are anchored to the close
of the most recent bar of the feature window.

Metrics reported per feature:
  * Pearson correlation with the direction code (+1 up / 0 neither / -1 down)
  * Direction AUC  : univariate logistic AUC, up-first vs down-first only
  * Big-move  AUC  : moved (either 1.5 threshold) vs not
  * Top-quintile P(up-first), bottom-quintile P(down-first), and the lift
    over the unconditional rate.

Usage:
    python mt5_analytics/evaluate_bar_features_outcome.py data/mt5/XAUUSD_M15.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import NamedTuple


class Bar(NamedTuple):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    vol: float


# --------------------------------------------------------------------------
# small numeric helpers
# --------------------------------------------------------------------------

def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3:
        return 0.0
    mx, my = sum(x) / n, sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    if vx == 0.0 or vy == 0.0:
        return 0.0
    return cov / math.sqrt(vx * vy)


def linear_slope(values: list[float]) -> float:
    """Least-squares slope of `values` over their index (price per bar)."""
    n = len(values)
    if n < 2:
        return 0.0
    mx = (n - 1) / 2.0
    my = mean(values)
    num = sum((i - mx) * (v - my) for i, v in enumerate(values))
    den = sum((i - mx) ** 2 for i in range(n))
    return num / den if den else 0.0


def rank_auc(x: list[float], y: list[int]) -> float:
    """Univariate logistic AUC via Mann-Whitney U (average tie ranks).

    y == 1 is the 'positive' class. Returns 0.5 for a coin flip.
    """
    pos = [v for v, c in zip(x, y) if c == 1]
    neg = [v for v, c in zip(x, y) if c == 0]
    np_, nn = len(pos), len(neg)
    if np_ == 0 or nn == 0:
        return float("nan")
    allv = sorted(x)
    # rank map with average ranks for ties
    rank_of: dict[float, float] = {}
    i = 0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1] == allv[i]:
            j += 1
        avg = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            rank_of[allv[k]] = avg
        i = j + 1
    rsum = sum(rank_of[v] for v in pos)
    auc = (rsum - np_ * (np_ + 1) / 2.0) / (np_ * nn)
    return auc


def quantile(seq: list[float], q: float) -> float:
    s = sorted(seq)
    if not s:
        return 0.0
    idx = int(round(q * (len(s) - 1)))
    return s[idx]


# --------------------------------------------------------------------------
# data loading
# --------------------------------------------------------------------------

def load_bars(path: Path) -> list[Bar]:
    bars: list[Bar] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = datetime.strptime(row["timestamp"].strip(), "%Y-%m-%d %H:%M:%S")
            bars.append(
                Bar(
                    ts=ts,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    vol=float(row["volume"]),
                )
            )
    return bars


def split_segments(bars: list[Bar], max_gap_minutes: float = 45.0) -> list[list[Bar]]:
    """Split into continuous trading sessions (gap > 45 min breaks a segment)."""
    segs: list[list[Bar]] = []
    cur: list[Bar] = []
    for b in bars:
        if cur:
            gap = (b.ts - cur[-1].ts).total_seconds() / 60.0
            if gap > max_gap_minutes or gap < 0:
                segs.append(cur)
                cur = []
        cur.append(b)
    if cur:
        segs.append(cur)
    return segs


# --------------------------------------------------------------------------
# forward outcome
# --------------------------------------------------------------------------

def forward_outcome(seg: list[Bar], t: int, atr12: float) -> str:
    """Classify the next-12-bar race.

    windows   : bars t+1 .. t+12 (requires len(seg) >= t+13)
    thresholds: close(t) +- 1.5/1.0 * atr12

    Returns 'up', 'down', 'neither', or 'ambiguous' (both 1.5 thresholds hit
    in the same bar, or a smaller opposite threshold preceded the 1.5 hit).
    """
    c0 = seg[t].close
    up15 = c0 + 1.5 * atr12
    dn15 = c0 - 1.5 * atr12
    up10 = c0 + 1.0 * atr12
    dn10 = c0 - 1.0 * atr12

    t_up15 = t_dn15 = t_up10 = t_dn10 = None
    for j in range(t + 1, min(t + 13, len(seg))):
        b = seg[j]
        if t_up15 is None and b.high >= up15 - 1e-9:
            t_up15 = j
        if t_dn15 is None and b.low <= dn15 + 1e-9:
            t_dn15 = j
        if t_up10 is None and b.high >= up10 - 1e-9:
            t_up10 = j
        if t_dn10 is None and b.low <= dn10 + 1e-9:
            t_dn10 = j
        if all(v is not None for v in (t_up15, t_dn15, t_up10, t_dn10)):
            break

    def earlier(a, b):
        return a is not None and (b is None or a < b)

    if t_up15 is not None and earlier(t_up15, t_dn10):
        return "up"
    if t_dn15 is not None and earlier(t_dn15, t_up10):
        return "down"
    if t_up15 is not None or t_dn15 is not None:
        return "ambiguous"
    return "neither"


# --------------------------------------------------------------------------
# features (the 10 candidates)
# --------------------------------------------------------------------------

def compute_features(seg: list[Bar], t: int) -> dict[str, float]:
    ws = seg[t - 11 : t + 1]          # the 12-bar feature window
    os_ = [b.open for b in ws]
    hs = [b.high for b in ws]
    ls = [b.low for b in ws]
    cs = [b.close for b in ws]
    vs = [b.vol for b in ws]

    atr12 = mean([h - l for h, l in zip(hs, ls)])
    atr48 = mean([b.high - b.low for b in seg[t - 47 : t + 1]])
    if atr12 <= 0 or atr48 <= 0:
        return {}

    c1, c12 = cs[0], cs[-1]
    ranges = [h - l for h, l in zip(hs, ls)]
    total_range = max(hs) - min(ls)

    feats: dict[str, float] = {}

    # 1. Coil ratio — recent squeeze vs prior 9 hours
    feats["R_coil_ratio"] = atr12 / atr48

    # 2. Range efficiency — travel vs total churn
    feats["E_range_efficiency"] = total_range / (sum(ranges) + 1e-9)

    # 3. Body share — average decisiveness of the 12 bars
    feats["B_body_share"] = mean(
        [abs(c - o) / (r + 1e-9) for c, o, r in zip(cs, os_, ranges)]
    )

    # 4. Net drift (ATR units)
    feats["D_net_drift"] = (c12 - c1) / atr12

    # 5. Close position inside the 3h band (-0.5 .. +0.5)
    feats["P_close_position"] = (
        (c12 - min(ls)) / (max(hs) - min(ls) + 1e-9) - 0.5
    )

    # 6. Linear slope (ATR units per bar)
    feats["S_linear_slope"] = linear_slope(cs) / atr12

    # 7. Path efficiency — straightness of the close path
    path = sum(abs(cs[k] - cs[k - 1]) for k in range(1, len(cs)))
    feats["F_path_efficiency"] = abs(c12 - c1) / (path + 1e-9)

    # 8. Up/down range imbalance (by bar range on up- vs down-closing bars)
    up_sum = sum(r for k, r in enumerate(ranges) if k > 0 and cs[k] > cs[k - 1])
    dn_sum = sum(r for k, r in enumerate(ranges) if k > 0 and cs[k] < cs[k - 1])
    feats["U_updown_imbalance"] = up_sum / (dn_sum + 1e-9) - 1.0

    # 9. Wick imbalance (positive = long upper tails)
    upper = sum(h - max(o, c) for h, o, c in zip(hs, os_, cs))
    lower = sum(min(o, c) - l for o, c, l in zip(os_, cs, ls))
    feats["W_wick_imbalance"] = (upper - lower) / atr12

    # 10. Volume-weighted direction
    num = sum(
        v * (1.0 if cs[k] > cs[k - 1] else -1.0 if cs[k] < cs[k - 1] else 0.0)
        for k, v in enumerate(vs)
        if k > 0
    )
    den = sum(v for k, v in enumerate(vs) if k > 0)
    feats["Q_vol_direction"] = num / (den + 1e-9)

    return feats


# --------------------------------------------------------------------------
# evaluation
# --------------------------------------------------------------------------

FEATURE_ORDER = [
    "R_coil_ratio",
    "E_range_efficiency",
    "B_body_share",
    "D_net_drift",
    "P_close_position",
    "S_linear_slope",
    "F_path_efficiency",
    "U_updown_imbalance",
    "W_wick_imbalance",
    "Q_vol_direction",
]

LABEL = {
    "R_coil_ratio": "Coil ratio",
    "E_range_efficiency": "Range efficiency",
    "B_body_share": "Body share",
    "D_net_drift": "Net drift",
    "P_close_position": "Close position",
    "S_linear_slope": "Linear slope",
    "F_path_efficiency": "Path efficiency",
    "U_updown_imbalance": "Up/down imbalance",
    "W_wick_imbalance": "Wick imbalance",
    "Q_vol_direction": "Vol-weighted direction",
}


def evaluate(bars: list[Bar]) -> dict:
    segs = split_segments(bars)
    windows: list[tuple[list[Bar], int]] = []
    for seg in segs:
        # need 48 prior bars (for ATR48), the 12-bar feature window, and 12
        # forward bars, all inside one continuous segment
        for t in range(48, len(seg) - 12):
            windows.append((seg, t))

    outcomes = Counter()
    features: dict[str, list[float]] = {k: [] for k in FEATURE_ORDER}
    direction_codes: list[int] = []        # +1 up / 0 neither / -1 down
    up_down_codes: list[int] = []          # 1 = up-first, 0 = down-first
    moved_codes: list[int] = []            # 1 = any 1.5 ATR reached

    dir_values: dict[str, list[float]] = {k: [] for k in FEATURE_ORDER}
    moved_values: dict[str, list[float]] = {k: [] for k in FEATURE_ORDER}

    valid_pairs: list[tuple[list[Bar], int]] = []   # windows with computable features

    for seg, t in windows:
        feats = compute_features(seg, t)
        if not feats:
            continue
        valid_pairs.append((seg, t))

        atr12 = mean([b.high - b.low for b in seg[t - 11 : t + 1]])
        outc = forward_outcome(seg, t, atr12)
        outcomes[outc] += 1

        if outc == "up":
            code = 1
            u_d = 1
            moved = 1
        elif outc == "down":
            code = -1
            u_d = 0
            moved = 1
        elif outc == "ambiguous":
            code = 0
            u_d = None
            moved = 1
        else:  # neither
            code = 0
            u_d = None
            moved = 0

        direction_codes.append(code)
        if u_d is not None:
            up_down_codes.append(u_d)
        moved_codes.append(moved)

        for k in FEATURE_ORDER:
            v = feats[k]
            features[k].append(v)
            if u_d is not None:
                dir_values[k].append(v)
            moved_values[k].append(v)

    # per-feature statistics --------------------------------------------
    result_rows = []
    for k in FEATURE_ORDER:
        vals = features[k]
        if not vals:
            continue
        # top / bottom quintiles (20 %) of the feature distribution
        top_thr = quantile(vals, 0.8)
        bot_thr = quantile(vals, 0.2)
        top = [(seg, o) for (seg, o), v in zip(valid_pairs, vals) if v >= top_thr]
        bot = [(seg, o) for (seg, o), v in zip(valid_pairs, vals) if v <= bot_thr]

        top_up = 0
        for (seg, t), _ in zip(top, top):
            atr12 = mean([b.high - b.low for b in seg[t - 11 : t + 1]])
            if forward_outcome(seg, t, atr12) == "up":
                top_up += 1

        bot_dn = 0
        for (seg, t), _ in zip(bot, bot):
            atr12 = mean([b.high - b.low for b in seg[t - 11 : t + 1]])
            if forward_outcome(seg, t, atr12) == "down":
                bot_dn += 1

        corr = pearson(vals, direction_codes)
        auc_dir = rank_auc(dir_values[k], up_down_codes)
        auc_mv = rank_auc(moved_values[k], moved_codes)

        result_rows.append(
            {
                "key": k,
                "name": LABEL[k],
                "corr": corr,
                "auc_dir": auc_dir,
                "n_dir": len(up_down_codes),
                "auc_mv": auc_mv,
                "top_up_rate": top_up / len(top) if top else float("nan"),
                "bot_dn_rate": bot_dn / len(bot) if bot else float("nan"),
                "top_n": len(top),
                "bot_n": len(bot),
            }
        )

    return {
        "n_bars": len(bars),
        "n_segments": len(segs),
        "outcomes": dict(outcomes),
        "n_windows": len(valid_pairs),
        "n_dir": len(up_down_codes),
        "base_up": sum(up_down_codes) / len(up_down_codes) if up_down_codes else 0.0,
        "rows": result_rows,
    }


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

def render_report(res: dict) -> str:
    L: list[str] = []
    L.append("# 12-Bar Feature Screen — 1.5 ATR vs 1.0 ATR Outcome Race")
    L.append("")
    L.append(f"- Bars loaded: **{res['n_bars']}**")
    L.append(f"- Continuous segments: **{res['n_segments']}**")
    L.append(f"- Feature windows (fully inside a segment, 48-bar warm-up): **{res['n_windows']}**")
    L.append("")
    L.append("## Outcome distribution (next 12 bars)")
    L.append("")
    L.append("| Outcome | Count | Share |")
    L.append("|---------|-------|-------|")
    for k, v in res["outcomes"].items():
        share = v / res["n_windows"] * 100
        L.append(f"| {k} | {v} | {share:.1f}% |")
    L.append("")
    base_up = res["base_up"]
    base_up_uncond = res["outcomes"].get("up", 0) / max(res["n_windows"], 1)
    base_down_uncond = res["outcomes"].get("down", 0) / max(res["n_windows"], 1)

    L.append(f"Base rate up-first among decided (up vs down) windows: "
             f"**{base_up * 100:.1f}%**")
    L.append(f"Unconditional up-first rate (all windows): **{base_up_uncond * 100:.1f}%** "
             f"(down-first {base_down_uncond * 100:.1f}%)")
    L.append("")
    L.append("**Big-move AUC interpretation:** values far below 0.5 mean *low* feature "
             "values predict the move (inverse signal); values far above 0.5 mean *high* "
             "feature values predict it.")
    L.append("")
    L.append("## Per-feature results")
    L.append("")
    L.append("| # | Feature | Corr(dir) | Dir AUC | Big AUC | P(up|top20) | P(down|bot20) | Lift* |")
    L.append("|---|---------|-----------|---------|---------|-------------|----------------|-------|")
    rows = sorted(res["rows"], key=lambda r: -r["auc_dir"])
    for i, r in enumerate(rows, 1):
        lift = (
            max(r["top_up_rate"], r["bot_dn_rate"]) / base_up_uncond
            if base_up_uncond > 0
            else float("nan")
        )
        def fmt(x: float) -> str:
            return "--" if x != x else f"{x:.3f}"
        def pct(x: float) -> str:
            return "--" if x != x else f"{x * 100:.1f}%"
        L.append(
            f"| {i} | {r['name']} | {fmt(r['corr'])} | {fmt(r['auc_dir'])} "
            f"| {fmt(r['auc_mv'])} | {pct(r['top_up_rate'])} | {pct(r['bot_dn_rate'])} "
            f"| {fmt(lift)} |"
        )
    L.append("")
    L.append("*Lift = max(P(up|top20), P(down|bot20)) / unconditional up-first rate. "
             ">1 means the extreme end of the feature beats the unconditional direction rate.")
    L.append("")
    L.append("### Ranked by directional AUC (up-first vs down-first only)")
    L.append("")
    for i, r in enumerate(rows, 1):
        mv_note = ""
        if r["auc_mv"] == r["auc_mv"]:
            if r["auc_mv"] < 0.45:
                mv_note = " ⚠️ **inverse** (low feature values → move)"
            elif r["auc_mv"] > 0.55:
                mv_note = " ✅ high feature values → move"
        L.append(f"{i}. **{r['name']}** — AUC {r['auc_dir']:.3f} "
                 f"(dir n={res['n_dir']}, big-move AUC {r['auc_mv']:.3f}){mv_note}")
    L.append("")
    return "\n".join(L)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=str, help="path to MT5 M15 CSV")
    parser.add_argument(
        "--out",
        type=str,
        default="reports/research/bar_features_outcome_report.md",
        help="output markdown path",
    )
    args = parser.parse_args()

    path = Path(args.csv)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    bars = load_bars(path)
    if not bars:
        print("Error: no bars parsed", file=sys.stderr)
        sys.exit(1)

    res = evaluate(bars)
    report = render_report(res)

    print(report)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"\nReport written to {out_path}")


if __name__ == "__main__":
    main()