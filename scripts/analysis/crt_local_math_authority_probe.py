#!/usr/bin/env python3
"""OBSERVATION_ONLY probe supporting CRT_LOCAL_MATH_AUTHORITY_RESOLUTION_V1.

Does not write production code paths or authorize migration.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

from config_layer.crt_engine_v2 import Candle  # noqa: E402
from features import candle_math as cm  # noqa: E402
from features.feature_pipeline import FeaturePipeline  # noqa: E402


def main() -> int:
    csv = _ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
    df = pd.read_csv(csv)
    df.columns = [c.lower() for c in df.columns]
    if "timestamp" not in df.columns:
        df = df.rename(columns={df.columns[0]: "timestamp"})
    df = df.iloc[:2000].copy()

    body_errs = []
    wick_errs = []
    for _, r in df.iterrows():
        o, h, l, c = map(float, (r.open, r.high, r.low, r.close))
        candle = Candle(
            timestamp=str(r.timestamp), open=o, high=h, low=l, close=c, volume=0.0
        )
        body_errs.append(abs(candle.body_ratio - cm.body_ratio(o, h, l, c)))
        wick_errs.append(abs(candle.wick_size - cm.candle_range(h, l)))

    # Pipeline absolute ATR raw + relative atr
    work = df.copy()
    tr1 = work["high"] - work["low"]
    tr2 = (work["high"] - work["close"].shift(1)).abs()
    tr3 = (work["low"] - work["close"].shift(1)).abs()
    work["true_range"] = np.maximum(tr1, np.maximum(tr2, tr3))
    work["atr_14_raw"] = work["true_range"].rolling(14).mean()

    # CRT-style expanding absolute ATR on full series (SMA last 14 TRs)
    closes = work["close"].astype(float).values
    highs = work["high"].astype(float).values
    lows = work["low"].astype(float).values
    trs = []
    for i in range(1, len(work)):
        trs.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )
    crt_abs = [np.nan]
    for i in range(len(trs)):
        w = trs[max(0, i + 1 - 14) : i + 1]
        crt_abs.append(float(np.mean(w)))
    work["crt_atr_abs_fullseries"] = crt_abs

    # Compare atr_14_raw vs crt absolute full-series
    both = work.dropna(subset=["atr_14_raw"]).copy()
    abs_err = (both["atr_14_raw"] - both["crt_atr_abs_fullseries"]).abs()
    rel_from_abs = both["crt_atr_abs_fullseries"] / both["close"]

    pipe = FeaturePipeline(df.copy())
    en, _ = pipe.run()
    en = en.copy()
    en["timestamp"] = en["timestamp"].astype(str)
    work["timestamp"] = work["timestamp"].astype(str)
    # merge relative atr vs abs/close
    m = en.merge(
        work[["timestamp", "atr_14_raw", "crt_atr_abs_fullseries"]],
        on="timestamp",
        how="inner",
    )
    m["crt_abs_over_close"] = m["crt_atr_abs_fullseries"] / m["close"]
    m["pipe_times_close"] = m["atr"] * m["close"]

    # EMA CRT 2/5 vs pipeline 9/21
    ef = es = 0.0
    crt_ef, crt_es = [], []
    for i, cl in enumerate(closes):
        if i == 0 or ef == 0.0:
            ef = es = float(cl)
        else:
            af, as_ = 2.0 / 3.0, 2.0 / 6.0
            ef = float(cl) * af + ef * (1 - af)
            es = float(cl) * as_ + es * (1 - as_)
        crt_ef.append(ef)
        crt_es.append(es)
    work["crt_ema2"] = crt_ef
    work["crt_ema5"] = crt_es
    m2 = en.merge(work[["timestamp", "crt_ema2", "crt_ema5"]], on="timestamp", how="inner")

    # pandas ewm 9/21 check
    e9 = pd.Series(closes).ewm(span=9, adjust=False).mean().values
    e21 = pd.Series(closes).ewm(span=21, adjust=False).mean().values
    ts_i = {str(t): i for i, t in enumerate(work["timestamp"].astype(str))}
    idx = [ts_i[str(t)] for t in en["timestamp"].astype(str)]
    pipe_vs_ewm9 = np.max(np.abs(en["ema_fast"].values - e9[idx]))
    pipe_vs_ewm21 = np.max(np.abs(en["ema_slow"].values - e21[idx]))

    out = {
        "schema_id": "CRT_LOCAL_MATH_AUTHORITY_PROBE_V1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "task_class": "OBSERVATION_ONLY",
        "corpus": "data/mt5/XAUUSD_M15.csv",
        "sample_bars": int(len(df)),
        "body_ratio": {
            "crt_vs_candle_math_max_abs_err": float(max(body_errs)),
            "interpretation": "CRT Candle.body_ratio already FM-010/candle_math bound",
        },
        "wick_size": {
            "crt_vs_candle_math_max_abs_err": float(max(wick_errs)),
            "interpretation": "CRT Candle.wick_size already FM-002/candle_range bound",
        },
        "atr": {
            "pipeline_feature_atr_semantics": "close_relative = atr_14_raw / close",
            "pipeline_atr_14_raw_semantics": "absolute SMA of true_range window 14",
            "crt_atr_semantics": "absolute SMA of TR over last atr_period (default 14) on engine buffer",
            "fullseries_atr_14_raw_vs_crt_abs_max_err": float(abs_err.max()),
            "fullseries_atr_14_raw_vs_crt_abs_mean_err": float(abs_err.mean()),
            "pipe_atr_vs_crt_abs_over_close_max_err": float(
                (m["atr"] - m["crt_abs_over_close"]).abs().max()
            ),
            "pipe_atr_times_close_vs_crt_abs_max_err": float(
                (m["pipe_times_close"] - m["crt_atr_abs_fullseries"]).abs().max()
            ),
            "note": (
                "Full-series absolute SMA-TR14 matches atr_14_raw exactly by construction "
                "when TR definitions align; CRT engine buffer may still diverge from full-series. "
                "Canonical feature name 'atr' is relative — not CRT absolute."
            ),
        },
        "ema": {
            "crt_defaults": {"ema_fast": 2, "ema_slow": 5, "alpha": "2/(N+1)"},
            "pipeline": {"ema_fast_span": 9, "ema_slow_span": 21, "adjust": False},
            "pipe_ema_fast_vs_ewm9_max_err": float(pipe_vs_ewm9),
            "pipe_ema_slow_vs_ewm21_max_err": float(pipe_vs_ewm21),
            "pipe_ema_fast_vs_crt_ema2_max_err": float(
                (m2["ema_fast"] - m2["crt_ema2"]).abs().max()
            ),
            "pipe_ema_slow_vs_crt_ema5_max_err": float(
                (m2["ema_slow"] - m2["crt_ema5"]).abs().max()
            ),
            "note": "Period mismatch is intentional product difference, not a failed equality proof",
        },
    }
    out_path = (
        _ROOT
        / "docs"
        / "governance"
        / "crt_local_math_authority_resolution_v1"
        / "CRT_LOCAL_MATH_AUTHORITY_PROBE_V1.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(out_path), "summary": {
        "body_max_err": out["body_ratio"]["crt_vs_candle_math_max_abs_err"],
        "wick_max_err": out["wick_size"]["crt_vs_candle_math_max_abs_err"],
        "atr_raw_vs_crt_fullseries_max": out["atr"]["fullseries_atr_14_raw_vs_crt_abs_max_err"],
        "ema_pipe9_vs_crt2_max": out["ema"]["pipe_ema_fast_vs_crt_ema2_max_err"],
    }}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
