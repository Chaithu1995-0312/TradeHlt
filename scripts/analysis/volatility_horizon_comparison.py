"""
volatility_horizon_comparison.py  (comparison protocol v2)

Candidate D - shared observation horizon - against the unchanged reference A.

    A  reference     H1: previous 200 bars     M15: previous 200 bars
    D  shared        H1: previous 200 bars     M15: previous 800 bars
       (200 H1 bars and 800 M15 bars are both 200 hours of bar intervals; that is NOMINAL bar time,
        not necessarily 200 hours of continuous market activity.)
    On H1, D is identical to A by construction (asserted), so D differs from A only on M15.

FROZEN RULES (set before any v2 result was computed; do not edit after seeing output). Everything in
protocol v1 (volatility_window_comparison.py) stays unchanged and is reused: same ATR(14) from the
production pipeline's own steps, strictly-prior observations, mid-rank ties, class edges 0.33 / 0.66,
NaN (never imputed) for insufficient or invalid reference data (all W reference ATRs must be finite).

Additional frozen definitions:
  closure         consecutive-bar gap > 3 x the bar interval (M15 > 45 min, H1 > 3 h); holidays and
                  early closes count when they exceed that.
  missing bar     consecutive-bar gap > 1 and <= 3 x the bar interval.
  cross-timeframe the H1 bar opening at T is paired with the M15 bar opening at T + 45 min: both close
                  at T + 1 h, so both labels are known at the same instant.
  diagnostic-only M15 ATR(56) (14 hours of M15 bars) with the 800-bar window. This is NOT a candidate;
                  it only explains residual cross-timeframe disagreement.
No trading metric is computed. Window lengths are not changed after examining results.

Added after the first run, DESCRIPTIVE ONLY (no candidate, rule or threshold changed; recorded as a
deviation in the report): the closure rule above counts the 75-minute daily break on M15 but not the
2-hour daily gap on H1, so "closures in window" is not comparable across timeframes. Two extra metrics
resolve that: long closures (gap >= 24 h, i.e. weekends and holidays) per window, and agreement of each
candidate with the retired full-file label (percentile rank over the whole file).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

import volatility_window_comparison as v1  # noqa: E402
from volatility_window_comparison import (  # noqa: E402
    ATR_PERIOD, BARS_PER_DAY, SHOCK_FACTOR, atr_frame, bar_window_percentile, event_response, flip_rate,
    kappa, load_ohlc, runs, session_of, spearman, to_class,
)

WINDOW_A = {"H1": 200, "M15": 200}
WINDOW_D = {"H1": 200, "M15": 800}
INTERVAL = {"H1": pd.Timedelta(hours=1), "M15": pd.Timedelta(minutes=15)}


def candidates_v2(tf: str, atr, cur=None) -> dict:
    return {"A": bar_window_percentile(atr, WINDOW_A[tf], cur), "D": bar_window_percentile(atr, WINDOW_D[tf], cur)}


def gap_flags(ts: pd.Series, tf: str):
    dt = ts.diff()
    closure = (dt > 3 * INTERVAL[tf]).to_numpy()
    missing = ((dt > INTERVAL[tf]) & (dt <= 3 * INTERVAL[tf])).to_numpy()
    return closure, missing


def closures_in_window(closure: np.ndarray, w: int) -> np.ndarray:
    cs = np.concatenate([[0], np.cumsum(closure)])
    out = np.full(len(closure), -1)
    for i in range(w, len(closure)):
        out[i] = cs[i] - cs[i - w + 1]       # gaps between bars i-w .. i-1 (flag sits on the later bar)
    return out


def causality_v2(tf: str, df: pd.DataFrame, n_cuts: int = 6, seed: int = 42) -> dict:
    full = atr_frame(df); base = candidates_v2(tf, full["atr_14"].to_numpy())
    rng = np.random.default_rng(seed); n = len(df)
    cuts = sorted(int(x) for x in rng.integers(int(0.15 * n), n - 50, size=n_cuts))
    res = {k: {"prefix_fail": 0, "mutation_fail": 0, "rows_checked": 0} for k in base}
    for cut in cuts:
        pa = atr_frame(df.iloc[: cut + 1].reset_index(drop=True))
        pc = candidates_v2(tf, pa["atr_14"].to_numpy())
        mut = df.copy().reset_index(drop=True)
        r = np.random.default_rng(cut); m = n - cut - 1
        step = mut["close"].diff().abs().median()
        close = mut["close"].iloc[cut] + np.cumsum(r.normal(0, step * 5, m))
        wick = np.abs(r.normal(0, step * 3, m)); o = close - r.normal(0, 1.0, m)
        mut.loc[cut + 1:, ["open", "high", "low", "close"]] = np.column_stack([o, np.maximum(o, close) + wick, np.minimum(o, close) - wick, close])
        ma = atr_frame(mut); mc = candidates_v2(tf, ma["atr_14"].to_numpy())
        for k in base:
            res[k]["rows_checked"] += cut + 1
            res[k]["prefix_fail"] += int(not np.array_equal(pc[k], base[k][: cut + 1], equal_nan=True))
            res[k]["mutation_fail"] += int(not np.array_equal(mc[k][: cut + 1], base[k][: cut + 1], equal_nan=True))
    again = candidates_v2(tf, full["atr_14"].to_numpy())
    for k in base:
        ha = hashlib.sha256(np.nan_to_num(base[k], nan=-1).tobytes()).hexdigest()
        res[k]["replay_identical"] = ha == hashlib.sha256(np.nan_to_num(again[k], nan=-1).tobytes()).hexdigest()
        res[k]["sha256"] = ha
    res["_cuts"] = cuts
    return res


def evaluate_tf(tf: str, path: str) -> dict:
    df = load_ohlc(path); af = atr_frame(df)
    ts, atr, tr = af["timestamp"], af["atr_14"].to_numpy(), af["true_range"].to_numpy()
    n = len(af); pcts = candidates_v2(tf, atr); cls = {k: to_class(p) for k, p in pcts.items()}
    closure, missing = gap_flags(ts, tf)
    out = {"tf": tf, "rows": n, "closures": int(closure.sum()), "missing_bar_gaps": int(missing.sum()),
           "identical_to_A": bool(np.array_equal(pcts["A"], pcts["D"], equal_nan=True)), "candidates": {}}
    L = BARS_PER_DAY[tf]
    sess = ts.map(session_of).to_numpy(); wd = ts.dt.dayofweek.to_numpy()
    for k, c in cls.items():
        w = WINDOW_A[tf] if k == "A" else WINDOW_D[tf]
        valid = ~np.isnan(c); first = int(np.argmax(valid))
        span = (ts - ts.shift(w)).dt.total_seconds().to_numpy() / 86400.0
        cw = closures_in_window(closure, w)
        long_cw = closures_in_window((ts.diff() >= pd.Timedelta(hours=24)).to_numpy(), w)
        retired = np.where(np.isnan(atr), np.nan, to_class(pd.Series(atr).rank(pct=True).to_numpy()))
        both_old = valid & ~np.isnan(retired)
        occ = pd.Series(c[valid]).value_counts(normalize=True).sort_index()
        # behaviour around closures: label before vs first label after each closure; first 4 hours after reopening
        idx = np.where(closure)[0]
        pairs = [(c[i - 1], c[i]) for i in idx if i > 0 and not np.isnan(c[i - 1]) and not np.isnan(c[i])]
        reopen = np.zeros(n, dtype=bool)
        for i in idx:
            reopen[i: i + int(4 * 3600 / INTERVAL[tf].total_seconds())] = True
        both = valid[1:] & valid[:-1]
        flips_all = (c[1:] != c[:-1])[both]
        flips_reopen = (c[1:] != c[:-1])[both & reopen[1:]]
        cur = atr + (SHOCK_FACTOR - 1.0) * tr / ATR_PERIOD
        shocked = candidates_v2(tf, atr, cur)[k]
        d = {
            "window_bars": w, "valid_rows": int(valid.sum()), "valid_share": float(valid.mean()), "warmup_rows": first,
            "first_valid_ts": str(ts.iloc[first]), "interior_nan_rows": int((~valid[first:]).sum()),
            "occupancy": {int(i): float(v) for i, v in occ.items()},
            "transition": {str(int(i)): {str(int(j)): float(v) for j, v in row.items()}
                           for i, row in pd.crosstab(pd.Series(c[:-1]), pd.Series(c[1:]), normalize="index").round(3).iterrows()},
            "flip_rate": flip_rate(c), "runs": runs(c, ts), "autocorr_lag1_pct": float(pd.Series(pcts[k]).autocorr(1)),
            "calendar_days_spanned": {q: float(np.nanpercentile(span[w:], p)) for q, p in (("p5", 5), ("median", 50), ("p95", 95))},
            "closures_in_window": {str(j): float((cw[w:] == j).mean()) for j in (0, 1, 2)} | {"3+": float((cw[w:] >= 3).mean())},
            "median_closures_in_window": float(np.median(cw[w:])),
            "long_closures_in_window": {str(j): float((long_cw[w:] == j).mean()) for j in (0, 1, 2)} | {"3+": float((long_cw[w:] >= 3).mean())},
            "agreement_with_retired_full_file_label": float((c[both_old] == retired[both_old]).mean()),
            "label_change_across_closure": float(np.mean([a != b for a, b in pairs])) if pairs else float("nan"),
            "closures_compared": len(pairs),
            "flip_rate_all": float(flips_all.mean()), "flip_rate_first4h_after_reopen": float(flips_reopen.mean()) if len(flips_reopen) else float("nan"),
            "high_share_by_session": {s: float((c[valid & (sess == s)] == 2).mean()) for s in ("ASIA", "LONDON", "NEWYORK", "OTHER")},
            "shock_flip_share": float((valid & ~np.isnan(shocked) & (to_class(shocked) != c)).sum() / valid.sum()),
            "spearman_vs_candle_range_pct": spearman(pcts[k], bar_window_percentile(tr, w)),
            "surge": event_response(atr, c, L, [0, L // 4, L], True), "decay": event_response(atr, c, L, [0, L // 4, L], False),
        }
        out["candidates"][k] = d
    m = ~np.isnan(cls["A"]) & ~np.isnan(cls["D"])
    out["agreement_A_vs_D"] = {
        "common_valid_rows": int(m.sum()), "only_A_valid": int((~np.isnan(cls["A"]) & np.isnan(cls["D"])).sum()),
        "agree": float((cls["A"][m] == cls["D"][m]).mean()) if m.any() else float("nan"),
        "kappa": kappa(cls["A"][m], cls["D"][m]) if m.any() else float("nan"),
        "mean_abs_pct_diff": float(np.mean(np.abs(pcts["A"][m] - pcts["D"][m]))) if m.any() else float("nan"),
        "agree_by_weekday": {int(w_): float((cls["A"][m][wd[m] == w_] == cls["D"][m][wd[m] == w_]).mean()) for w_ in range(5)},
        "one_step_share_of_disagreements": float((np.abs(cls["A"][m] - cls["D"][m]) == 1)[cls["A"][m] != cls["D"][m]].mean()) if (cls["A"][m] != cls["D"][m]).any() else float("nan"),
    }
    out["causality"] = causality_v2(tf, df)
    out["_arrays"] = (ts, atr, tr, pcts, cls)
    return out


def cross_timeframe(h: dict, m: dict) -> dict:
    ts_h, atr_h, _, ph, ch = h["_arrays"]; ts_m, atr_m, tr_m, pm, cm = m["_arrays"]
    idx_m = pd.Series(np.arange(len(ts_m)), index=ts_m)
    pair = []
    for i, t in enumerate(ts_h):
        j = idx_m.get(t + pd.Timedelta(minutes=45))
        if j is not None:
            pair.append((i, int(j)))
    hi, mj = np.array([p[0] for p in pair]), np.array([p[1] for p in pair])
    # diagnostic only: ATR over 56 M15 bars (= 14 hours) with the 800-bar window
    atr56 = pd.Series(tr_m).rolling(56).mean().to_numpy()
    p56 = bar_window_percentile(atr56, 800); c56 = to_class(p56)

    def stats(ph_, pm_, ch_, cm_):
        ok = ~np.isnan(ch_[hi]) & ~np.isnan(cm_[mj])
        a, b = ch_[hi][ok], cm_[mj][ok]
        return {"pairs": int(ok.sum()), "agree": float((a == b).mean()), "kappa": kappa(a, b),
                "spearman_pct": spearman(ph_[hi][ok], pm_[mj][ok]), "mean_abs_pct_diff": float(np.mean(np.abs(ph_[hi][ok] - pm_[mj][ok]))),
                "one_step_share_of_disagreements": float((np.abs(a - b) == 1)[a != b].mean())}
    res = {"aligned_pairs_total": len(pair),
           "A_H1_vs_A_M15": stats(ph["A"], pm["A"], ch["A"], cm["A"]),
           "A_H1_vs_D_M15": stats(ph["A"], pm["D"], ch["A"], cm["D"]),
           "diagnostic_ATR56_D_M15": stats(ph["A"], p56, ch["A"], c56)}
    # calendar span of the reference windows at the aligned instants
    span_h = (ts_h - ts_h.shift(200)).dt.total_seconds().to_numpy() / 86400.0
    for k, w in (("A", 200), ("D", 800)):
        span_m = (ts_m - ts_m.shift(w)).dt.total_seconds().to_numpy() / 86400.0
        ok = ~np.isnan(span_h[hi]) & ~np.isnan(span_m[mj])
        ratio = span_m[mj][ok] / span_h[hi][ok]
        res[f"span_ratio_M15{k}_over_H1"] = {q: float(np.percentile(ratio, p)) for q, p in (("p5", 5), ("median", 50), ("p95", 95))}
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--h1", required=True); ap.add_argument("--m15", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    H, M = evaluate_tf("H1", a.h1), evaluate_tf("M15", a.m15)
    assert H["identical_to_A"], "D must equal A on H1"
    res = {"protocol": "v2", "frozen": {"WINDOW_A": WINDOW_A, "WINDOW_D": WINDOW_D, "closure_gap_intervals": 3, "cross_tf_offset_minutes": 45,
                                         "ATR_PERIOD": ATR_PERIOD, "SHOCK_FACTOR": SHOCK_FACTOR}}
    res["cross_timeframe"] = cross_timeframe(H, M)
    for k, r in (("H1", H), ("M15", M)):
        r.pop("_arrays"); res[k] = r
    (out / "metrics.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    print(json.dumps({"causality": {k: res[k]["causality"] for k in ("H1", "M15")}, "cross": res["cross_timeframe"]}, indent=1, default=float))


if __name__ == "__main__":
    main()
