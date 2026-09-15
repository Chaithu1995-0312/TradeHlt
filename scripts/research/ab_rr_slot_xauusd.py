#!/usr/bin/env python3
"""A/B the fused `rr` slot: live candle-polarity vs rr_trained (OBSERVATION_ONLY).

Compares the sealed frozen-corpus fusion_compute baseline (run 20260914T072116Z,
which puts LIVE candle-polarity in the `rr` slot) against the same fusion recomputed
with the non-quarantined 39-dim XAUUSD rr_trained artifact (run 20260914T093317Z)
in the `rr` slot. Same static weights (from the baseline manifest), same frozen
corpus (data/mt5/XAUUSD_M15.csv sha256 4d73f5ce...).

No train. No promote. No production-config mutation. Research authority only.

Usage:
    python scripts/research/ab_rr_slot_xauusd.py [--out results/research]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

BASELINE_SCORES = (
    ROOT / "results" / "model_runners" / "fusion_compute" / "XAUUSD"
    / "20260914T072116Z" / "scores.jsonl"
)
RR_TRAINED_SCORES = (
    ROOT / "results" / "model_runners" / "rr_trained" / "XAUUSD"
    / "20260914T093317Z" / "scores.jsonl"
)
CSV = ROOT / "data" / "mt5" / "XAUUSD_M15.csv"

# Forward-return horizons (bars) for ground-truth direction labels.
HORIZONS = (1, 4)


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _moments(x: np.ndarray) -> dict:
    return {
        "n": int(len(x)),
        "mean": float(np.mean(x)),
        "p50": float(np.median(x)),
        "std": float(np.std(x)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
    }


def _spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    if a.size < 2 or np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(spearmanr(a, b).statistic)


def _pearson(a: np.ndarray, b: np.ndarray) -> float | None:
    if a.size < 2 or np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(pearsonr(a, b)[0])


def _auroc(score: np.ndarray, y: np.ndarray) -> float | None:
    mask = y != 0  # drop exact ties for a clean binary split
    s, t = score[mask], (y[mask] > 0).astype(int)
    if len(np.unique(t)) < 2:
        return None
    return float(roc_auc_score(t, s))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "results" / "research"))
    args = ap.parse_args()

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    base = _load_jsonl(BASELINE_SCORES)
    rrt = _load_jsonl(RR_TRAINED_SCORES)
    base_by_ts = {r["timestamp"]: r for r in base}
    rrt_by_ts = {r["timestamp"]: r for r in rrt}

    # Weights from the baseline (crt 0.4, others 0.2).
    w = dict(base[0]["native"]["weights_used"])
    wc, wg, wz, wr = w["crt"], w["gaussian"], w["zone_gate"], w["rr"]

    # Raw closes -> forward returns (raw row order; warmup is the first 78 rows).
    raw = pd.read_csv(CSV)
    close = raw["close"].to_numpy(dtype=float)
    ts_to_idx = {
        pd.to_datetime(t).isoformat(): i for i, t in enumerate(raw["timestamp"])
    }
    # Canonicalise the timestamp key the same way scores.jsonl does.
    base_ts_key = next(iter(base_by_ts))
    try:
        pd.Timestamp(base_ts_key)
    except Exception:
        pass

    comps = []
    for ts, rec in base_by_ts.items():
        rr = rrt_by_ts.get(ts)
        if rr is None:
            continue
        scores = rec["native"]["scores"]
        s_crt, s_gauss, s_zone, s_rr = (
            scores["crt"], scores["gaussian"], scores["zone_gate"], scores["rr"],
        )
        s_rrt = rr["native"]["score"]
        fused_base = wc * s_crt + wg * s_gauss + wz * s_zone + wr * s_rr
        fused_rrt = wc * s_crt + wg * s_gauss + wz * s_zone + wr * s_rrt
        row = {
            "timestamp": ts,
            "bar_index": rec["bar_index"],
            "base_final_score": rec["native"]["final_score"],
            "fused_base_live_rr": float(fused_base),
            "fused_rr_trained": float(fused_rrt),
            "crt": float(s_crt),
            "gaussian": float(s_gauss),
            "zone_gate": float(s_zone),
            "rr_live_polarity": float(s_rr),
            "rr_trained": float(s_rrt),
        }
        idx = ts_to_idx.get(ts)
        if idx is not None:
            for h in HORIZONS:
                j = idx + h
                row[f"fwd_ret_h{h}"] = (
                    float(close[j] / close[idx] - 1.0) if j < len(close) else np.nan
                )
        comps.append(row)

    df = pd.DataFrame(comps)
    repro = max(abs(df["fused_base_live_rr"] - df["base_final_score"]))
    print(f"aligned bars: {len(df)}")
    print(f"reproduce base final_score: max|fused_base_live_rr - base_final_score| = {repro:.2e}")

    result = {
        "baseline_run": "20260914T072116Z",
        "rr_trained_run": "20260914T093317Z",
        "weights_used": w,
        "n_aligned": int(len(df)),
        "distribution": {
            "live_rr_fused": _moments(df["fused_base_live_rr"].to_numpy()),
            "rr_trained_fused": _moments(df["fused_rr_trained"].to_numpy()),
            "rr_live_polarity": _moments(df["rr_live_polarity"].to_numpy()),
            "rr_trained": _moments(df["rr_trained"].to_numpy()),
        },
        "rr_pair": {
            "pearson": _pearson(df["rr_live_polarity"].to_numpy(),
                                df["rr_trained"].to_numpy()),
            "spearman": _spearman(df["rr_live_polarity"].to_numpy(),
                                  df["rr_trained"].to_numpy()),
        },
        "fused_pair": {
            "pearson": _pearson(df["fused_base_live_rr"].to_numpy(),
                                df["fused_rr_trained"].to_numpy()),
            "spearman": _spearman(df["fused_base_live_rr"].to_numpy(),
                                  df["fused_rr_trained"].to_numpy()),
        },
    }


    # Discrimination vs forward-return direction labels.
    disc = {}
    for h in HORIZONS:
        col = f"fwd_ret_h{h}"
        sub = df.dropna(subset=[col])
        y = sub[col].to_numpy()
        f_live = sub["fused_base_live_rr"].to_numpy()
        f_rrt = sub["fused_rr_trained"].to_numpy()
        disc[f"h{h}"] = {
            "n": int(len(sub)),
            "up_frac": float((y > 0).mean()),
            "live_rr_fused": {
                "auroc": _auroc(f_live, y),
                "spearman": _spearman(f_live, y),
            },
            "rr_trained_fused": {
                "auroc": _auroc(f_rrt, y),
                "spearman": _spearman(f_rrt, y),
            },
        }
    result["discrimination"] = disc

    ts_s = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_out = out_dir / f"ab_rr_slot_XAUUSD_{ts_s}.json"
    json_out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    aligned_out = out_dir / f"ab_rr_slot_aligned_XAUUSD_{ts_s}.jsonl"
    with aligned_out.open("w", encoding="utf-8") as fh:
        for _, r in df.iterrows():
            d = r.to_dict()
            clean = {
                k: (None if isinstance(v, float) and np.isnan(v) else v)
                for k, v in d.items()
            }
            fh.write(json.dumps(clean, default=float) + "\n")

    print("\n=== rr-slot A/B ===")
    for k, m in result["distribution"].items():
        print(f"{k:22s} mean={m['mean']:.4f} p50={m['p50']:.4f} "
              f"std={m['std']:.4f} range=[{m['min']:.4f},{m['max']:.4f}]")
    print(f"\nrr_pair    pearson={result['rr_pair']['pearson']:.4f} "
          f"spearman={result['rr_pair']['spearman']:.4f}")
    print(f"fused_pair pearson={result['fused_pair']['pearson']:.4f} "
          f"spearman={result['fused_pair']['spearman']:.4f}")
    for h, d in disc.items():
        a_live = d["live_rr_fused"]["auroc"]
        a_rrt = d["rr_trained_fused"]["auroc"]
        s_live = d["live_rr_fused"]["spearman"]
        s_rrt = d["rr_trained_fused"]["spearman"]
        print(f"\nh{h} (n={d['n']}, up_frac={d['up_frac']:.3f})")
        print(f"    live_rr fused:     auroc={a_live if a_live is None else round(a_live,4)} "
              f"spearman={s_live if s_live is None else round(s_live,4)}")
        print(f"    rr_trained fused:  auroc={a_rrt if a_rrt is None else round(a_rrt,4)} "
              f"spearman={s_rrt if s_rrt is None else round(s_rrt,4)}")

    print(f"\nwrote {json_out}")
    print(f"wrote {aligned_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

