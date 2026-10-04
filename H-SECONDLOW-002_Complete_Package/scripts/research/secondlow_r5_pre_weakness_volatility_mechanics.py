#!/usr/bin/env python3
"""R5 pre-weakness leg mechanics + volatility/clustering/autocorr — count-only (006)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from research.secondlow_v1.corpus import CANONICAL_XAUUSD_M15
from research.secondlow_v1.detector import (
    POST_WINDOW_BARS,
    compute_true_range_atr,
    detect_independent_events,
    load_ohlcv,
    sha256_prefix,
)
from research.secondlow_v1.regime_metrics import regime_metrics_at_purge

PRE_THRESHOLD = -1.5
DEPTH_V02 = 1.0
MARGINAL_PRE_HI = -1.5
MARGINAL_PRE_LO = -1.8
STRONG_PRE = -2.5
HIGH_VOL_RATIO = 1.2
N_BOOT = 5000
SEED = 42
LEDGER = _REPO / "data/secondlow_prospective_events.jsonl"
OUTPUT = _REPO / "H-SECONDLOW-002_Complete_Package/results/r5_pre_weakness_mechanics"


def assign_session(ts: pd.Timestamp) -> str:
    h = ts.hour
    if 0 <= h < 7:
        return "ASIA"
    if 7 <= h < 12:
        return "LONDON"
    if 12 <= h < 16:
        return "OVERLAP"
    if 16 <= h < 21:
        return "NY"
    return "LATE"


def classify_group(depth: float, pre_2h: float) -> str:
    depth_ok = depth >= DEPTH_V02
    pre_ok = pre_2h <= PRE_THRESHOLD
    if depth_ok and pre_ok:
        return "both_legs"
    if depth_ok:
        return "depth_only"
    if pre_ok:
        return "pre_only"
    return "reference"


def classify_pre_strength(pre_2h: float) -> str | None:
    if pre_2h > PRE_THRESHOLD:
        return None
    if pre_2h <= STRONG_PRE:
        return "strong"
    if pre_2h <= MARGINAL_PRE_LO:
        return "moderate"
    return "marginal"


def true_range_series(df: pd.DataFrame) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev = close.shift(1)
    return pd.concat([(high - low), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)


def lag1_autocorr(values: np.ndarray) -> float | None:
    if len(values) < 3:
        return None
    x, y = values[:-1], values[1:]
    if np.std(x) == 0 or np.std(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def window_slice(df: pd.DataFrame, pos: int, start: int, end: int) -> pd.DataFrame:
    return df.iloc[pos + start : pos + end + 1]


def event_volatility_row(df: pd.DataFrame, tr: pd.Series, atr: pd.Series, pos: int, e) -> dict:
    if pos < POST_WINDOW_BARS or pos + POST_WINDOW_BARS >= len(df):
        return {}
    pre = window_slice(df, pos, -POST_WINDOW_BARS, -1)
    post = window_slice(df, pos, 1, POST_WINDOW_BARS)
    if len(pre) != POST_WINDOW_BARS or len(post) != POST_WINDOW_BARS:
        return {}

    pre_tr = tr.iloc[pos - POST_WINDOW_BARS : pos].to_numpy(dtype=float)
    post_tr = tr.iloc[pos + 1 : pos + 1 + POST_WINDOW_BARS].to_numpy(dtype=float)
    pre_atr = atr.iloc[pos - POST_WINDOW_BARS : pos].to_numpy(dtype=float)
    post_atr = atr.iloc[pos + 1 : pos + 1 + POST_WINDOW_BARS].to_numpy(dtype=float)
    combined_tr = np.concatenate([pre_tr, post_tr])

    pre_ret = pre["close"].pct_change().dropna().to_numpy(dtype=float)
    post_ret = post["close"].pct_change().dropna().to_numpy(dtype=float)

    pre_range = float((pre["high"] - pre["low"]).mean())
    post_range = float((post["high"] - post["low"]).mean())

    reg = regime_metrics_at_purge(df, pos)
    ratio = float(reg.atr_ratio_14_over_100) if reg else float("nan")

    mean_pre_tr = float(np.mean(pre_tr))
    mean_post_tr = float(np.mean(post_tr))
    mean_pre_atr = float(np.mean(pre_atr))
    mean_post_atr = float(np.mean(post_atr))

    return {
        "purge_time": str(e.purge_time),
        "group": classify_group(e.purge_depth_atr, e.pre_2h_return_atr),
        "purge_depth_atr": round(float(e.purge_depth_atr), 4),
        "pre_2h_return_atr": round(float(e.pre_2h_return_atr), 4),
        "pre_strength": classify_pre_strength(e.pre_2h_return_atr),
        "session": assign_session(e.purge_time),
        "atr_ratio_14_over_100": round(ratio, 4) if np.isfinite(ratio) else None,
        "high_vol_regime": bool(ratio > HIGH_VOL_RATIO) if np.isfinite(ratio) else None,
        "mean_pre_window_tr": round(mean_pre_tr, 4),
        "mean_post_window_tr": round(mean_post_tr, 4),
        "mean_pre_window_atr": round(mean_pre_atr, 4),
        "mean_post_window_atr": round(mean_post_atr, 4),
        "post_pre_tr_ratio": round(mean_post_tr / mean_pre_tr, 4) if mean_pre_tr > 0 else None,
        "post_pre_atr_ratio": round(mean_post_atr / mean_pre_atr, 4) if mean_pre_atr > 0 else None,
        "vol_change_atr": round((mean_post_atr - mean_pre_atr) / mean_pre_atr, 4) if mean_pre_atr > 0 else None,
        "realized_vol_pre": round(float(np.std(pre_ret)), 6) if len(pre_ret) else None,
        "realized_vol_post": round(float(np.std(post_ret)), 6) if len(post_ret) else None,
        "mean_range_pre": round(pre_range, 4),
        "mean_range_post": round(post_range, 4),
        "lag1_autocorr_tr_pre": lag1_autocorr(pre_tr),
        "lag1_autocorr_tr_post": lag1_autocorr(post_tr),
        "lag1_autocorr_tr_combined": lag1_autocorr(combined_tr),
        "lag1_autocorr_atr_pre": lag1_autocorr(pre_atr),
        "lag1_autocorr_atr_post": lag1_autocorr(post_atr),
    }


def bootstrap_mean_ci(values: np.ndarray) -> dict | None:
    if len(values) == 0:
        return None
    rng = np.random.default_rng(SEED)
    samples = np.empty(N_BOOT)
    for i in range(N_BOOT):
        samples[i] = float(np.mean(rng.choice(values, size=len(values), replace=True)))
    return {"mean": round(float(np.mean(values)), 4), "ci_95": [round(float(np.percentile(samples, 2.5)), 4), round(float(np.percentile(samples, 97.5)), 4)]}


def bootstrap_mean_diff_ci(a: np.ndarray, b: np.ndarray) -> dict | None:
    if len(a) == 0 or len(b) == 0:
        return None
    rng = np.random.default_rng(SEED)
    obs = float(np.mean(a) - np.mean(b))
    samples = np.empty(N_BOOT)
    for i in range(N_BOOT):
        sa = rng.choice(a, size=len(a), replace=True)
        sb = rng.choice(b, size=len(b), replace=True)
        samples[i] = float(np.mean(sa) - np.mean(sb))
    return {
        "observed_diff": round(obs, 4),
        "ci_95": [round(float(np.percentile(samples, 2.5)), 4), round(float(np.percentile(samples, 97.5)), 4)],
        "n_a": int(len(a)),
        "n_b": int(len(b)),
    }


def summarize_group(rows: list[dict], group: str) -> dict:
    g = [r for r in rows if r["group"] == group]
    if not g:
        return {"n": 0}
    def col(name: str) -> np.ndarray:
        return np.array([r[name] for r in g if r.get(name) is not None], dtype=float)

    pre_tr = col("mean_pre_window_tr")
    post_tr = col("mean_post_window_tr")
    post_pre = col("post_pre_atr_ratio")
    lag_pre = col("lag1_autocorr_tr_pre")
    lag_post = col("lag1_autocorr_tr_post")
    pre_vals = col("pre_2h_return_atr")
    depth_vals = col("purge_depth_atr")

    clustering = 0
    if len(pre_tr) and len(post_tr):
        med_pre, med_post = float(np.median(pre_tr)), float(np.median(post_tr))
        for r in g:
            if r.get("mean_pre_window_tr") is not None and r.get("mean_post_window_tr") is not None:
                if r["mean_pre_window_tr"] >= med_pre and r["mean_post_window_tr"] >= med_post:
                    clustering += 1

    pre_strength = {"marginal": 0, "moderate": 0, "strong": 0}
    for r in g:
        ps = r.get("pre_strength")
        if ps in pre_strength:
            pre_strength[ps] += 1

    sessions = {}
    for r in g:
        sessions[r["session"]] = sessions.get(r["session"], 0) + 1

    return {
        "n": len(g),
        "pre_2h_distribution": {
            "mean": round(float(np.mean(pre_vals)), 4) if len(pre_vals) else None,
            "median": round(float(np.median(pre_vals)), 4) if len(pre_vals) else None,
            "min": round(float(np.min(pre_vals)), 4) if len(pre_vals) else None,
            "max": round(float(np.max(pre_vals)), 4) if len(pre_vals) else None,
            "percentiles": {
                "p25": round(float(np.percentile(pre_vals, 25)), 4) if len(pre_vals) else None,
                "p75": round(float(np.percentile(pre_vals, 75)), 4) if len(pre_vals) else None,
            },
        },
        "depth_distribution": {
            "mean": round(float(np.mean(depth_vals)), 4) if len(depth_vals) else None,
            "median": round(float(np.median(depth_vals)), 4) if len(depth_vals) else None,
        },
        "pre_strength_counts": pre_strength,
        "session_counts": sessions,
        "mean_post_window_atr": bootstrap_mean_ci(col("mean_post_window_atr")),
        "mean_pre_window_atr": bootstrap_mean_ci(col("mean_pre_window_atr")),
        "post_pre_atr_ratio": bootstrap_mean_ci(post_pre),
        "lag1_autocorr_tr_pre": bootstrap_mean_ci(lag_pre),
        "lag1_autocorr_tr_post": bootstrap_mean_ci(lag_post),
        "volatility_clustering_proxy_n": clustering,
        "volatility_clustering_proxy_pct": round(clustering / len(g), 4) if g else None,
        "events": g,
    }


def overlap_summary(rows: list[dict]) -> dict:
    counts = {g: sum(1 for r in rows if r["group"] == g) for g in ("depth_only", "pre_only", "both_legs", "reference")}
    r5_total = counts["depth_only"] + counts["pre_only"] + counts["both_legs"]
    return {
        "depth_only_v02_style": counts["depth_only"],
        "pre_only_r5_incremental": counts["pre_only"],
        "both_legs": counts["both_legs"],
        "reference": counts["reference"],
        "r5_exposed_total": r5_total,
        "pre_only_share_of_r5": round(counts["pre_only"] / r5_total, 4) if r5_total else None,
    }


def pre_depth_correlation(rows: list[dict]) -> dict:
    pre_only = [r for r in rows if r["group"] == "pre_only"]
    if len(pre_only) < 2:
        return {"n": len(pre_only), "corr_pre2h_depth": None}
    x = np.array([r["pre_2h_return_atr"] for r in pre_only])
    y = np.array([r["purge_depth_atr"] for r in pre_only])
    if np.std(x) == 0 or np.std(y) == 0:
        return {"n": len(pre_only), "corr_pre2h_depth": None}
    return {"n": len(pre_only), "corr_pre2h_depth": round(float(np.corrcoef(x, y)[0, 1]), 4)}


def analyze_cohort(df: pd.DataFrame, events: list, cohort_name: str) -> dict:
    tr = true_range_series(df)
    atr = compute_true_range_atr(df)
    rows = []
    for e in events:
        pos = df.index.get_loc(e.purge_time)
        row = event_volatility_row(df, tr, atr, pos, e)
        if row:
            rows.append(row)

    depth_only_post_atr = np.array(
        [r["mean_post_window_atr"] for r in rows if r["group"] == "depth_only" and r.get("mean_post_window_atr")],
        dtype=float,
    )
    pre_only_post_atr = np.array(
        [r["mean_post_window_atr"] for r in rows if r["group"] == "pre_only" and r.get("mean_post_window_atr")],
        dtype=float,
    )
    depth_only_pre_atr = np.array(
        [r["mean_pre_window_atr"] for r in rows if r["group"] == "depth_only" and r.get("mean_pre_window_atr")],
        dtype=float,
    )
    pre_only_pre_atr = np.array(
        [r["mean_pre_window_atr"] for r in rows if r["group"] == "pre_only" and r.get("mean_pre_window_atr")],
        dtype=float,
    )

    return {
        "cohort": cohort_name,
        "n_events": len(rows),
        "overlap": overlap_summary(rows),
        "pre_depth_correlation_pre_only": pre_depth_correlation(rows),
        "groups": {
            "depth_only": summarize_group(rows, "depth_only"),
            "pre_only": summarize_group(rows, "pre_only"),
            "both_legs": summarize_group(rows, "both_legs"),
            "reference": summarize_group(rows, "reference"),
        },
        "comparisons": {
            "post_window_atr_pre_only_minus_depth_only": bootstrap_mean_diff_ci(pre_only_post_atr, depth_only_post_atr),
            "pre_window_atr_pre_only_minus_depth_only": bootstrap_mean_diff_ci(pre_only_pre_atr, depth_only_pre_atr),
        },
    }


def main() -> None:
    corpus = _REPO / CANONICAL_XAUUSD_M15
    df = load_ohlcv(corpus)
    _, events = detect_independent_events(df, require_post_window=False)

    ledger_times: set[pd.Timestamp] = set()
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            if line.strip():
                ledger_times.add(pd.Timestamp(json.loads(line)["purge_time"]))
    post_events = [e for e in events if e.purge_time in ledger_times]

    report = {
        "governance": "COUNT_ONLY_DESCRIPTIVE_NO_OUTCOMES",
        "hypothesis_framework": "H-SECONDLOW-006 v0.1 APPROVED",
        "focus": "R5 pre-weakness leg mechanics + post/pre volatility + clustering + lag1 autocorr",
        "pre_threshold": PRE_THRESHOLD,
        "depth_v02": DEPTH_V02,
        "pre_strength_bins": {
            "marginal": f"({MARGINAL_PRE_LO}, {MARGINAL_PRE_HI}]",
            "moderate": f"({STRONG_PRE}, {MARGINAL_PRE_LO}]",
            "strong": f"<= {STRONG_PRE}",
        },
        "window_bars": POST_WINDOW_BARS,
        "bootstrap": {"n_boot": N_BOOT, "seed": SEED},
        "corpus_hash_prefix": sha256_prefix(corpus),
        "cohorts": {
            "prospective_ledger": analyze_cohort(df, post_events, "prospective_ledger_14"),
            "all_independent": analyze_cohort(df, events, "all_independent_50"),
        },
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    out = OUTPUT / "r5_pre_weakness_volatility_mechanics.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    p = report["cohorts"]["prospective_ledger"]
    lines = [
        "# R5 pre-weakness mechanics — prospective ledger (14)",
        "",
        "## Overlap",
        f"- depth_only: {p['overlap']['depth_only_v02_style']}",
        f"- pre_only (R5 incremental): {p['overlap']['pre_only_r5_incremental']}",
        f"- both_legs: {p['overlap']['both_legs']}",
        f"- reference: {p['overlap']['reference']}",
        "",
        "## Post-window ATR: pre_only vs depth_only",
        str(p["comparisons"]["post_window_atr_pre_only_minus_depth_only"]),
        "",
        "## Pre-only pre-2h strength counts",
        str(p["groups"]["pre_only"].get("pre_strength_counts", {})),
    ]
    (OUTPUT / "r5_pre_weakness_mechanics_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()