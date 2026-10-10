"""
volatility_window_comparison.py  (comparison protocol v1)

Step 2 of the feature-contract sequence: compare bar-based and time-based reference windows for
volatility_regime on IDENTICAL data. Research/diagnostic only: nothing here changes the
production pipeline, trains a model, or looks at trading results.

FROZEN RULES (set before any result was computed; do not edit after seeing output):
  ATR            ATR(14) = rolling mean of true range, exactly as FeaturePipeline.compute_indicators.
  Reference      only observations strictly before the current bar.
  Percentile     mid-rank: (count(ref < v) + 0.5 * count(ref == v)) / count(ref).
  Classes        pct < 0.33 -> 0, pct < 0.66 -> 1, else 2.
  Missing        NaN for insufficient or invalid reference data; never imputed to a neutral class.
  A  bar-based   previous 200 bars; all 200 ATR values must be finite (production candidate).
  B  H1 time     previous 9 elapsed CALENDAR days  [t-9d, t)   (applied to H1 data)
  C  M15 time    previous 2 elapsed CALENDAR days  [t-2d, t)   (applied to M15 data)
  Time rules     (1) bars are selected by timestamp, closures are NOT filled with synthetic bars;
                 (2) the window start must not precede the first bar of the data (full elapsed coverage);
                 (3) at least N_MIN = 100 bars (half of A's window) must fall inside the window;
                 (4) every ATR value inside the window must be finite.
Window lengths, N_MIN and class edges must not be changed after examining results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import time as dtime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from features.feature_pipeline import FeaturePipeline, trailing_atr_percentile  # noqa: E402

ATR_PERIOD = 14
BAR_WINDOW = 200
N_MIN = 100
LOW_PCT, HIGH_PCT = 0.33, 0.66
TIME_WINDOWS = {"H1": pd.Timedelta(days=9), "M15": pd.Timedelta(days=2)}
BARS_PER_DAY = {"H1": 24, "M15": 96}
SESSIONS = {"ASIA": (dtime(0, 0), dtime(3, 0)), "LONDON": (dtime(7, 0), dtime(10, 0)), "NEWYORK": (dtime(13, 0), dtime(16, 0))}
SURGE_RATIO = 1.5
SHOCK_FACTOR = 2.0


# ───────────────────────────── data / ATR ──────────────────────────────
def load_ohlc(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def atr_frame(df: pd.DataFrame) -> pd.DataFrame:
    """ATR(14) and true range computed by the production pipeline's own steps."""
    p = FeaturePipeline(df[["timestamp", "open", "high", "low", "close", "volume"]])
    p.compute_price_features(); p.compute_volume_features(); p.compute_indicators()
    out = p.df[["timestamp", "atr_14", "true_range"]].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"])
    return out.reset_index(drop=True)


# ───────────────────────────── candidates ──────────────────────────────
def _mid_rank(ref: np.ndarray, v: float) -> float:
    return (float((ref < v).sum()) + 0.5 * float((ref == v).sum())) / len(ref)


def bar_window_percentile(values, window: int = BAR_WINDOW, cur=None) -> np.ndarray:
    """Candidate A. cur (optional) overrides the current-bar value (counterfactual tests only)."""
    v = np.asarray(values, dtype=float).copy(); v[~np.isfinite(v)] = np.nan
    c = v if cur is None else np.asarray(cur, dtype=float)
    n = len(v); out = np.full(n, np.nan)
    if n <= window:
        return out
    ref = np.lib.stride_tricks.sliding_window_view(v, window)[:-1]
    cc = c[window:]
    less = (ref < cc[:, None]).sum(axis=1); eq = (ref == cc[:, None]).sum(axis=1)
    ok = ~np.isnan(ref).any(axis=1) & np.isfinite(cc)
    out[window:] = np.where(ok, (less + 0.5 * eq) / window, np.nan)
    return out


def time_window_percentile(values, timestamps, delta: pd.Timedelta, n_min: int = N_MIN, cur=None):
    """
    Candidates B / C. Reference = bars with t - delta <= ts_j < ts_t (strictly before the current bar).
    NaN unless: window start >= first bar, >= n_min bars, every ATR in the window finite, current finite.
    Returns (percentile array, reference-count array).
    """
    v = np.asarray(values, dtype=float).copy(); v[~np.isfinite(v)] = np.nan
    c = v if cur is None else np.asarray(cur, dtype=float)
    ts = pd.to_datetime(pd.Series(timestamps)).to_numpy("datetime64[ns]")
    if not (np.diff(ts.astype("int64")) > 0).all():
        raise ValueError("timestamps must be strictly increasing")
    n = len(v)
    lo = np.searchsorted(ts, ts - delta.to_timedelta64(), side="left")
    cbad = np.concatenate([[0], np.cumsum(np.isnan(v))])
    out = np.full(n, np.nan); nref = np.zeros(n, dtype=int)
    covered = (ts - delta.to_timedelta64()) >= ts[0]
    for i in range(n):
        nref[i] = i - lo[i]
        if not covered[i] or nref[i] < n_min or (cbad[i] - cbad[lo[i]]) > 0 or not np.isfinite(c[i]):
            continue
        out[i] = _mid_rank(v[lo[i]:i], c[i])
    return out, nref


def to_class(pct: np.ndarray) -> np.ndarray:
    return np.where(np.isnan(pct), np.nan, np.where(pct < LOW_PCT, 0.0, np.where(pct < HIGH_PCT, 1.0, 2.0)))


def candidates_for(tf: str, atr: np.ndarray, ts, cur=None) -> dict:
    out = {"A": bar_window_percentile(atr, BAR_WINDOW, cur)}
    key = "B" if tf == "H1" else "C"
    out[key], _ = time_window_percentile(atr, ts, TIME_WINDOWS[tf], N_MIN, cur)
    return out


# ───────────────────────────── metrics ─────────────────────────────────
def runs(cls: np.ndarray, ts: pd.Series) -> dict:
    lens, hours = [], []
    i, n = 0, len(cls)
    while i < n:
        if np.isnan(cls[i]):
            i += 1; continue
        j = i
        while j + 1 < n and cls[j + 1] == cls[i]:
            j += 1
        lens.append(j - i + 1)
        hours.append((ts.iloc[j] - ts.iloc[i]).total_seconds() / 3600.0)
        i = j + 1
    a, h = np.array(lens), np.array(hours)
    return {"n_runs": int(len(a)), "mean_bars": float(a.mean()), "median_bars": float(np.median(a)), "p90_bars": float(np.percentile(a, 90)),
            "median_hours": float(np.median(h))}


def flip_rate(cls: np.ndarray) -> float:
    a, b = cls[:-1], cls[1:]
    m = ~np.isnan(a) & ~np.isnan(b)
    return float((a[m] != b[m]).mean())


def session_of(t: pd.Timestamp) -> str:
    tt = t.time()
    for k, (s, e) in SESSIONS.items():
        if s <= tt <= e:
            return k
    return "OTHER"


def kappa(a: np.ndarray, b: np.ndarray) -> float:
    cm = pd.crosstab(a, b).reindex(index=[0, 1, 2], columns=[0, 1, 2], fill_value=0).to_numpy(float)
    n = cm.sum(); po = np.trace(cm) / n
    pe = (cm.sum(0) * cm.sum(1)).sum() / n ** 2
    return float((po - pe) / (1 - pe))


def spearman(a, b) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    return float(pd.Series(a[m]).rank().corr(pd.Series(b[m]).rank()))


def event_response(atr: np.ndarray, cls: np.ndarray, L: int, horizons: list[int], up: bool) -> dict:
    ratio = np.full(len(atr), np.nan); ratio[L:] = atr[L:] / atr[:-L]
    hit = (ratio >= SURGE_RATIO) if up else (ratio <= 1 / SURGE_RATIO)
    ev, last = [], -10 ** 9
    for i in np.where(np.nan_to_num(hit, nan=False).astype(bool))[0]:
        if i - last >= L:
            ev.append(i); last = i
    want = 2.0 if up else 0.0
    res = {"events": len(ev)}
    for h in horizons:
        vals = [cls[i + h] for i in ev if i + h < len(cls) and not np.isnan(cls[i + h])]
        res[f"h{h}"] = {"n": len(vals), "share": float(np.mean([v == want for v in vals])) if vals else float("nan")}
    return res


# ───────────────────────────── causality ───────────────────────────────
def causality(tf: str, df: pd.DataFrame, cut_seed: int = 42, n_cuts: int = 6) -> dict:
    full_atr = atr_frame(df)
    base = {k: v for k, v in candidates_for(tf, full_atr["atr_14"].to_numpy(), full_atr["timestamp"]).items()}
    rng = np.random.default_rng(cut_seed)
    n = len(df)
    cuts = sorted(int(x) for x in rng.integers(int(0.15 * n), n - 50, size=n_cuts))
    res = {k: {"prefix_fail": 0, "mutation_fail": 0, "rows_checked": 0} for k in base}
    for cut in cuts:
        # prefix invariance / truncation: rebuild ATR and candidates on data[:cut+1], compare ALL rows
        part = df.iloc[: cut + 1].reset_index(drop=True)
        pa = atr_frame(part)
        pc = candidates_for(tf, pa["atr_14"].to_numpy(), pa["timestamp"])
        # future mutation: replace every bar after the cut with different data
        mut = df.copy().reset_index(drop=True)
        r = np.random.default_rng(cut)
        m = n - cut - 1
        close = mut["close"].iloc[cut] + np.cumsum(r.normal(0, mut["close"].diff().abs().median() * 5, m))
        wick = np.abs(r.normal(0, mut["close"].diff().abs().median() * 3, m)); o = close - r.normal(0, 1.0, m)
        mut.loc[cut + 1:, ["open", "high", "low", "close"]] = np.column_stack([o, np.maximum(o, close) + wick, np.minimum(o, close) - wick, close])
        ma = atr_frame(mut)
        mc = candidates_for(tf, ma["atr_14"].to_numpy(), ma["timestamp"])
        for k in base:
            res[k]["rows_checked"] += cut + 1
            if not np.array_equal(pc[k], base[k][: cut + 1], equal_nan=True):
                res[k]["prefix_fail"] += 1
            if not np.array_equal(mc[k][: cut + 1], base[k][: cut + 1], equal_nan=True):
                res[k]["mutation_fail"] += 1
    again = candidates_for(tf, full_atr["atr_14"].to_numpy(), full_atr["timestamp"])
    for k in base:
        ha = hashlib.sha256(np.nan_to_num(base[k], nan=-1).tobytes()).hexdigest()
        hb = hashlib.sha256(np.nan_to_num(again[k], nan=-1).tobytes()).hexdigest()
        res[k]["replay_identical"] = ha == hb
        res[k]["sha256"] = ha
    res["_cuts"] = cuts
    return res


# ───────────────────────────── evaluation ──────────────────────────────
def evaluate(tf: str, path: str) -> dict:
    df = load_ohlc(path)
    af = atr_frame(df)
    ts, atr, tr = af["timestamp"], af["atr_14"].to_numpy(), af["true_range"].to_numpy()
    n = len(af)
    pcts = candidates_for(tf, atr, ts)
    nref = time_window_percentile(atr, ts, TIME_WINDOWS[tf], N_MIN)[1]
    cls = {k: to_class(p) for k, p in pcts.items()}
    L = BARS_PER_DAY[tf]
    sess = ts.map(session_of); wd = ts.dt.dayofweek
    out = {"tf": tf, "rows": n, "first_ts": str(ts.iloc[0]), "last_ts": str(ts.iloc[-1]), "candidates": {}}

    # strawman (NOT a candidate): class of the current candle's own true range vs the prior 200 true ranges
    straw_pct = bar_window_percentile(tr, BAR_WINDOW)
    straw_cls = to_class(straw_pct)

    for k, c in cls.items():
        valid = ~np.isnan(c)
        first = int(np.argmax(valid)) if valid.any() else None
        interior_nan = int((~valid[first:]).sum()) if first is not None else n
        occ = pd.Series(c[valid]).value_counts(normalize=True).sort_index()
        d = {
            "valid_rows": int(valid.sum()), "valid_share": float(valid.mean()),
            "first_valid_ts": str(ts.iloc[first]) if first is not None else None, "warmup_rows": first,
            "interior_nan_rows": interior_nan, "interior_nan_share": interior_nan / max(1, n - (first or 0)),
            "occupancy": {int(i): float(v) for i, v in occ.items()},
            "flip_rate": flip_rate(c), "runs": runs(c, ts),
            "autocorr_lag1_pct": float(pd.Series(pcts[k]).autocorr(1)),
            "by_session": {s: {int(i): float(v) for i, v in pd.Series(c[valid & (sess.to_numpy() == s)]).value_counts(normalize=True).sort_index().items()}
                           for s in ["ASIA", "LONDON", "NEWYORK", "OTHER"]},
            "nan_share_by_weekday": {int(w): float(np.isnan(c[wd.to_numpy() == w]).mean()) for w in range(5)},
        }
        trans = pd.crosstab(pd.Series(c[:-1]), pd.Series(c[1:]), normalize="index").round(3)
        d["transition"] = {str(int(i)): {str(int(j)): float(trans.loc[i, j]) for j in trans.columns} for i in trans.index}
        # semantic: shock the current candle (double its true range), see how many labels flip
        cur = atr + (SHOCK_FACTOR - 1.0) * tr / ATR_PERIOD
        shocked = candidates_for(tf, atr, ts, cur)[k]
        flips = valid & ~np.isnan(shocked) & (to_class(shocked) != c)
        d["shock_flip_share"] = float(flips.sum() / valid.sum())
        d["shock_mean_abs_pct_change"] = float(np.nanmean(np.abs(shocked - pcts[k])))
        d["spearman_vs_candle_range_pct"] = spearman(pcts[k], straw_pct)
        d["surge"] = event_response(atr, c, L, [0, L // 4, L], True)
        d["decay"] = event_response(atr, c, L, [0, L // 4, L], False)
        out["candidates"][k] = d
    sv = ~np.isnan(straw_cls)
    shocked_straw = bar_window_percentile(tr, BAR_WINDOW, SHOCK_FACTOR * tr)
    out["strawman_candle_range"] = {
        "flip_rate": flip_rate(straw_cls), "autocorr_lag1_pct": float(pd.Series(straw_pct).autocorr(1)),
        "shock_flip_share": float(((to_class(shocked_straw) != straw_cls) & sv & ~np.isnan(shocked_straw)).sum() / sv.sum()),
        "shock_mean_abs_pct_change": float(np.nanmean(np.abs(shocked_straw - straw_pct))),
    }
    # effective history behind each window
    span_a = (ts - ts.shift(BAR_WINDOW)).dt.total_seconds() / 86400.0
    out["effective_history"] = {
        "A_calendar_days_of_200_bars": {q: float(np.nanpercentile(span_a, p)) for q, p in (("p5", 5), ("median", 50), ("p95", 95))},
        "time_window_bars": {q: float(np.percentile(nref[nref > 0], p)) for q, p in (("p5", 5), ("median", 50), ("p95", 95))},
        "time_window_bars_min": int(nref[nref > 0].min()), "time_window_bars_max": int(nref.max()),
        "time_window_below_n_min_share": float((nref[np.arange(n) >= 0] < N_MIN).mean()),
    }
    # pairwise agreement on identical rows
    other = [k for k in cls if k != "A"][0]
    m = ~np.isnan(cls["A"]) & ~np.isnan(cls[other])
    wd_m = wd.to_numpy()[m]
    out["agreement_A_vs_" + other] = {
        "common_valid_rows": int(m.sum()), "agree": float((cls["A"][m] == cls[other][m]).mean()),
        "kappa": kappa(cls["A"][m], cls[other][m]), "mean_abs_pct_diff": float(np.mean(np.abs(pcts["A"][m] - pcts[other][m]))),
        "agree_mon_tue": float((cls["A"][m][np.isin(wd_m, [0, 1])] == cls[other][m][np.isin(wd_m, [0, 1])]).mean()),
        "agree_wed_fri": float((cls["A"][m][np.isin(wd_m, [2, 3, 4])] == cls[other][m][np.isin(wd_m, [2, 3, 4])]).mean()),
        "only_A_valid": int((~np.isnan(cls["A"]) & np.isnan(cls[other])).sum()),
        "only_other_valid": int((np.isnan(cls["A"]) & ~np.isnan(cls[other])).sum()),
    }
    out["causality"] = causality(tf, df)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--h1", required=True); ap.add_argument("--m15", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    res = {"protocol": "v1", "frozen": {"ATR_PERIOD": ATR_PERIOD, "BAR_WINDOW": BAR_WINDOW, "N_MIN": N_MIN, "LOW_PCT": LOW_PCT, "HIGH_PCT": HIGH_PCT,
                                        "TIME_WINDOWS_DAYS": {k: v.days for k, v in TIME_WINDOWS.items()}, "SURGE_RATIO": SURGE_RATIO, "SHOCK_FACTOR": SHOCK_FACTOR}}
    res["H1"] = evaluate("H1", a.h1)
    res["M15"] = evaluate("M15", a.m15)
    (out / "metrics.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: res[k]["causality"] for k in ("H1", "M15")}, indent=1, default=float))


if __name__ == "__main__":
    main()
