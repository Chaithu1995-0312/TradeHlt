"""
high_acceptance_scan.py — High-Acceptance-Candle Numerical Scan (research / phase 1, ontology-free).

Pure numerical time-series study. Ignores CRT/SMC/ontology vocabulary entirely — no sweep,
retest, manipulation, accumulation, distribution, displacement, or execution concepts. Treats
the candle series as plain OHLCV numbers.

For every candle i and forward horizon N in {5,10,20,50,100,250,500}, asks one question only:

    Did price ever trade back below candle i's HIGH within the next N bars?

    future_min_low(N)  = min(low[i+1 .. i+N])
    acceptance_score    = future_min_low(N) - candidate_high

    acceptance_score > 0  -> price never traded below the candidate high in the window
    acceptance_score = 0  -> exact touch
    acceptance_score < 0  -> candidate high was reclaimed

This script does NOT classify results and does NOT attach trading meaning. It produces
descriptive statistics only (distributions, percentiles, top-decile tables, survival streaks,
time clustering, run-length sequences, ATR/range-normalized scores, per-instrument summary).
A separate second-stage investigation (what structural characteristics are common among the
strongest acceptance candles) is deliberately deferred to a later, explicitly-requested turn.

PURE READ-ONLY over data/mt5/XAUUSD_M15.csv. No production/src/config/spine change. No new
ontology (`FM-*`) feature is registered — the local ATR here is a display-only normalizer, not
a canonical quantity (same "observe-only" pattern as prior diagnostic probes, e.g. F-067).

Outputs:
    results/research/high_acceptance/xauusd_m15.parquet             (raw OHLCV, parquet-ified)
    results/research/high_acceptance/xauusd_m15_candidates.parquet  (+ .csv) per-candidate x per-horizon metrics
    results/research/high_acceptance/xauusd_m15_summary.json        descriptive statistics only
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC_CSV = ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
OUT_DIR = ROOT / "results" / "research" / "high_acceptance"
OUT_PARQUET_RAW = OUT_DIR / "xauusd_m15.parquet"
OUT_PARQUET_CANDIDATES = OUT_DIR / "xauusd_m15_candidates.parquet"
OUT_CSV_CANDIDATES = OUT_DIR / "xauusd_m15_candidates.csv"
OUT_SUMMARY_JSON = OUT_DIR / "xauusd_m15_summary.json"

INSTRUMENT = "XAUUSD"
TIMEFRAME = "M15"
HORIZONS = [5, 10, 20, 50, 100, 250, 500]
ATR_PERIOD = 14  # simple SMA of True Range, display-only, not a registered ontology feature
PERCENTILES = [1, 5, 10, 25, 50, 75, 90, 95, 99]
CLUSTER_FREQ = "W"  # weekly bucket for time-clustering
TOP_DECILE_PCTS = [1, 5, 10]
LONGEST_SURVIVORS_N = 50
LONGEST_SURVIVORS_HORIZON = 500
LONGEST_RUNS_TOP_K = 10


def load_raw() -> pd.DataFrame:
    df = pd.read_csv(SRC_CSV, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET_RAW, engine="pyarrow", index=False)
    return df


def add_local_atr(df: pd.DataFrame) -> pd.DataFrame:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df = df.copy()
    df["true_range"] = tr
    df["atr_local"] = tr.rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean()
    df["candle_range"] = high - low
    return df


def sliding_forward_windows(arr: np.ndarray, n: int) -> np.ndarray:
    """Forward window [i+1 .. i+n] for every i where i+n < len(arr). Shape: (len(arr)-n, n)."""
    shifted = arr[1:]  # aligns index 0 -> original index 1
    return np.lib.stride_tricks.sliding_window_view(shifted, n)[: len(arr) - n]


def compute_horizon(df: pd.DataFrame, n: int) -> pd.DataFrame:
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    ts = df["timestamp"].to_numpy()
    atr = df["atr_local"].to_numpy()
    rng = df["candle_range"].to_numpy()

    n_valid = len(df) - n
    if n_valid <= 0:
        return pd.DataFrame()

    candidate_high = high[:n_valid]
    win_low = sliding_forward_windows(low, n)[:n_valid]
    win_high = sliding_forward_windows(high, n)[:n_valid]

    future_min_low = win_low.min(axis=1)
    acceptance_score = future_min_low - candidate_high
    mfe = win_high.max(axis=1) - candidate_high
    mae = candidate_high - future_min_low

    reclaim_mask = win_low < candidate_high[:, None]
    any_reclaim = reclaim_mask.any(axis=1)
    first_reclaim_offset = np.where(any_reclaim, reclaim_mask.argmax(axis=1) + 1, n)
    survival_bars = np.where(any_reclaim, first_reclaim_offset, n)

    # first_reclaim_ts: timestamp at candidate_index + first_reclaim_offset, only when reclaimed
    reclaim_idx = np.arange(n_valid) + first_reclaim_offset
    first_reclaim_ts = np.where(any_reclaim, ts[reclaim_idx], np.datetime64("NaT"))

    atr_i = atr[:n_valid]
    range_i = rng[:n_valid]
    with np.errstate(divide="ignore", invalid="ignore"):
        acceptance_atr_norm = np.where(atr_i > 0, acceptance_score / atr_i, np.nan)
        acceptance_range_norm = np.where(range_i > 0, acceptance_score / range_i, np.nan)

    return pd.DataFrame(
        {
            "instrument": INSTRUMENT,
            "timeframe": TIMEFRAME,
            "candidate_ts": ts[:n_valid],
            "candidate_index": np.arange(n_valid),
            "candidate_high": candidate_high,
            "N": n,
            "future_min_low": future_min_low,
            "acceptance_score": acceptance_score,
            "survival_bars": survival_bars,
            "first_reclaim_ts": first_reclaim_ts,
            "mfe": mfe,
            "mae": mae,
            "acceptance_score_atr_norm": acceptance_atr_norm,
            "acceptance_score_range_norm": acceptance_range_norm,
        }
    )


def build_candidate_table(df: pd.DataFrame) -> pd.DataFrame:
    parts = [compute_horizon(df, n) for n in HORIZONS]
    parts = [p for p in parts if not p.empty]
    return pd.concat(parts, ignore_index=True)


def _percentiles(series: pd.Series) -> dict:
    vals = series.dropna()
    return {f"p{p}": float(np.percentile(vals, p)) for p in PERCENTILES} if len(vals) else {}


def _top_decile_tables(sub: pd.DataFrame, col: str, top_n: int = 25) -> dict:
    out = {}
    for pct in TOP_DECILE_PCTS:
        k = max(1, int(len(sub) * pct / 100))
        top = sub.nlargest(k, col)
        out[f"top_{pct}pct"] = {
            "n": int(k),
            "threshold": float(top[col].min()) if k else None,
            "sample": top.nlargest(min(top_n, k), col)[
                ["candidate_ts", "candidate_high", col]
            ].assign(candidate_ts=lambda d: d["candidate_ts"].astype(str)).to_dict("records"),
        }
    return out


def _longest_runs(flags: np.ndarray, ts: np.ndarray, top_k: int) -> tuple[int, list[dict]]:
    if len(flags) == 0:
        return 0, []
    runs = []
    start = 0
    cur = flags[0]
    for i in range(1, len(flags) + 1):
        if i == len(flags) or flags[i] != cur:
            if cur:
                runs.append((start, i - 1))
            if i < len(flags):
                start = i
                cur = flags[i]
    runs.sort(key=lambda r: r[1] - r[0], reverse=True)
    max_len = (runs[0][1] - runs[0][0] + 1) if runs else 0
    top = [
        {
            "start_ts": str(ts[s]),
            "end_ts": str(ts[e]),
            "length": int(e - s + 1),
        }
        for s, e in runs[:top_k]
    ]
    return max_len, top


def summarize_horizon(cand: pd.DataFrame, n: int, raw_len: int) -> dict:
    sub = cand[cand["N"] == n].sort_values("candidate_index").reset_index(drop=True)
    if sub.empty:
        return {"n_candidates": 0}

    score = sub["acceptance_score"]
    hist_counts, hist_edges = np.histogram(score.dropna(), bins=20)

    accepted_flag = (score > 0).to_numpy()
    max_run, top_runs = _longest_runs(accepted_flag, sub["candidate_ts"].to_numpy(), LONGEST_RUNS_TOP_K)

    cluster = (
        sub.set_index(pd.DatetimeIndex(sub["candidate_ts"]))
        .resample(CLUSTER_FREQ)
        .agg(n_candidates=("acceptance_score", "size"), n_accepted=("acceptance_score", lambda s: int((s > 0).sum())))
    )
    cluster["fraction_accepted"] = cluster["n_accepted"] / cluster["n_candidates"].replace(0, np.nan)
    cluster_records = [
        {
            "period_start": str(idx),
            "n_candidates": int(row.n_candidates),
            "n_accepted": int(row.n_accepted),
            "fraction_accepted": None if pd.isna(row.fraction_accepted) else float(row.fraction_accepted),
        }
        for idx, row in cluster.iterrows()
        if row.n_candidates > 0
    ]

    longest_survivors = None
    if n == LONGEST_SURVIVORS_HORIZON:
        top_surv = sub.nlargest(LONGEST_SURVIVORS_N, "survival_bars")
        longest_survivors = top_surv.assign(
            candidate_ts=lambda d: d["candidate_ts"].astype(str),
            first_reclaim_ts=lambda d: d["first_reclaim_ts"].astype(str),
        )[["candidate_ts", "candidate_high", "survival_bars", "first_reclaim_ts"]].to_dict("records")

    return {
        "n_candidates": int(len(sub)),
        "coverage_fraction_of_full_series": round(len(sub) / raw_len, 4),
        "distribution": {
            "acceptance_score": {
                "count": int(score.count()),
                "mean": float(score.mean()),
                "std": float(score.std()),
                "min": float(score.min()),
                "max": float(score.max()),
                "histogram_counts": hist_counts.tolist(),
                "histogram_bin_edges": hist_edges.tolist(),
            }
        },
        "percentiles": {
            "acceptance_score": _percentiles(score),
            "acceptance_score_atr_norm": _percentiles(sub["acceptance_score_atr_norm"]),
            "acceptance_score_range_norm": _percentiles(sub["acceptance_score_range_norm"]),
        },
        "top_decile_by_acceptance_score": _top_decile_tables(sub, "acceptance_score"),
        "top_decile_by_acceptance_score_atr_norm": _top_decile_tables(sub, "acceptance_score_atr_norm"),
        "longest_survivors_top50": longest_survivors,
        "consecutive_accepted_sequences": {
            "max_run_length": int(max_run),
            "top_runs": top_runs,
        },
        "clusters_through_time": {
            "bucket_freq": CLUSTER_FREQ,
            "buckets": cluster_records,
        },
        "fraction_accepted_overall": float((score > 0).mean()),
        "fraction_exact_touch": float((score == 0).mean()),
        "fraction_reclaimed": float((score < 0).mean()),
    }


def build_summary(df: pd.DataFrame, cand: pd.DataFrame) -> dict:
    raw_len = len(df)
    per_horizon = {str(n): summarize_horizon(cand, n, raw_len) for n in HORIZONS}
    return {
        "instrument_level_statistics": [
            {
                "instrument": INSTRUMENT,
                "timeframe": TIMEFRAME,
                "n_raw_candles": raw_len,
                "date_range_start": str(df["timestamp"].min()),
                "date_range_end": str(df["timestamp"].max()),
                "atr_period_local": ATR_PERIOD,
            }
        ],
        "horizons": HORIZONS,
        "per_horizon": per_horizon,
        "note": (
            "Purely descriptive numerical output. No classification, no trading meaning, "
            "no ontology vocabulary attached. atr_local is a display-only rolling SMA(TR), "
            "not a registered canonical feature."
        ),
    }


def main() -> None:
    df = load_raw()
    df = add_local_atr(df)
    cand = build_candidate_table(df)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cand.to_parquet(OUT_PARQUET_CANDIDATES, engine="pyarrow", index=False)
    cand.to_csv(OUT_CSV_CANDIDATES, index=False)

    summary = build_summary(df, cand)
    OUT_SUMMARY_JSON.write_text(json.dumps(summary, indent=2, default=str))

    print(f"raw candles: {len(df)}")
    print(f"candidate rows (all horizons): {len(cand)}")
    print(f"wrote: {OUT_PARQUET_RAW}")
    print(f"wrote: {OUT_PARQUET_CANDIDATES}")
    print(f"wrote: {OUT_CSV_CANDIDATES}")
    print(f"wrote: {OUT_SUMMARY_JSON}")


if __name__ == "__main__":
    sys.exit(main())
