"""Read-only training/live parity probe (in memory; no models, configs or datasets are written).

Feeds batch FeaturePipeline rows through the live ingestion boundary
(live_engine_hook._build_ohlcv_and_auxiliary -> FeatureStore) as an *idealised upstream*
(trade_data == the batch row) and reports per-feature differences at identical timestamps.
Also reports warm-up/missing-value behaviour and the rr_dataset_builder warm-up effect.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402


def load_ohlcv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    tcol = next(c for c in ("timestamp", "time", "datetime", "date") if c in df.columns)
    df["timestamp"] = pd.to_datetime(df[tcol])
    return df[["timestamp", "open", "high", "low", "close", "volume"]].reset_index(drop=True)


def live_frame(batch: pd.DataFrame) -> pd.DataFrame:
    from core.feature_store import FeatureStore
    from runtime.live_engine_hook import _build_ohlcv_and_auxiliary

    store = FeatureStore(max_history=1000)
    rows, fails = [], 0
    for i, rec in enumerate(batch.to_dict("records")):
        ohlcv, aux = _build_ohlcv_and_auxiliary(rec)
        try:
            fr = store.process(i, rec.get("timestamp"), ohlcv, aux)
            rows.append({k: fr.features.get(k, np.nan) for k in CANONICAL_FEATURES})
        except Exception:
            fails += 1
            rows.append({k: np.nan for k in CANONICAL_FEATURES})
    out = pd.DataFrame(rows)
    out.attrs["store_failures"] = fails
    return out


def compare(batch: pd.DataFrame, live: pd.DataFrame) -> list[dict]:
    res = []
    for k in CANONICAL_FEATURES:
        b = pd.to_numeric(batch[k], errors="coerce").to_numpy(float)
        l = pd.to_numeric(live[k], errors="coerce").to_numpy(float)
        fin = np.isfinite(b)
        nan_b = int((~fin).sum())
        diff = np.abs(np.where(fin, l - b, 0.0))
        tol = 1e-9 + 1e-6 * np.abs(np.where(fin, b, 0.0))
        mism = (diff > tol) & fin
        res.append({
            "feature": k,
            "batch_nan_rows": nan_b,
            "live_value_on_batch_nan_rows_nonnan": int(np.isfinite(l[~fin]).sum()),
            "mismatch_rows": int(mism.sum()),
            "mismatch_frac": round(float(mism.sum() / max(fin.sum(), 1)), 4),
            "max_abs_diff": float(diff.max()) if fin.any() else 0.0,
        })
    return res


def rr_warmup(sizes=(50, 120, 250, 350, 600)) -> dict:
    """Rows surviving FeaturePipeline(trade-row frame) warm-up, using synthetic OHLC rows."""
    rng = np.random.default_rng(0)
    out = {}
    for n in sizes:
        close = 2000 + np.cumsum(rng.normal(0, 1, n))
        df = pd.DataFrame({
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="15min"),
            "open": close + rng.normal(0, .2, n), "high": close + 1, "low": close - 1,
            "close": close, "volume": rng.integers(100, 200, n).astype(float),
        })
        feats, _ = FeaturePipeline(df).run()
        cols = [c for c in CANONICAL_FEATURES if c in feats.columns]
        ok = feats[cols].replace([np.inf, -np.inf], np.nan).dropna()
        out[n] = int(len(ok))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(ROOT / "data/XAUUSD_M15_2025-07.csv"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    raw = load_ohlcv(a.csv)
    batch, _ = FeaturePipeline(raw.copy()).run()
    batch = batch.reset_index(drop=True)
    inp = batch.copy()
    # Align raw OHLCV to the post-warm-up batch rows by timestamp (pipeline drops warm-up rows).
    if "timestamp" in batch.columns:
        r = raw.set_index("timestamp").reindex(pd.to_datetime(batch["timestamp"]))
        for c in ("open", "high", "low", "close", "volume"):
            inp[c] = r[c].to_numpy()
    else:
        tail = raw.tail(len(batch)).reset_index(drop=True)
        for c in ("open", "high", "low", "close", "volume"):
            inp[c] = tail[c].to_numpy()
        inp["timestamp"] = tail["timestamp"].to_numpy()
    live = live_frame(inp)
    report = {
        "csv": a.csv, "raw_bars": len(raw), "batch_rows_after_warmup": len(batch), "store_failures": live.attrs.get("store_failures", 0),
        "per_feature": compare(batch, live),
        "rr_dataset_builder_rows_surviving_pipeline": rr_warmup(),
    }
    txt = json.dumps(report, indent=2, default=str)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
