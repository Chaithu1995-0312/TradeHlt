#!/usr/bin/env python3
"""CRT-local math parity audit (OBSERVATION_ONLY measurement).

Compares CRT Candle/EngineState quantities vs FeaturePipeline / candle_math.
Does NOT change CRT production behavior or authorize migration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle  # noqa: E402
from features import candle_math as cm  # noqa: E402
from features.feature_pipeline import FeaturePipeline  # noqa: E402


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_ohlcv(path: Path, limit: int) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    rename = {}
    for want in ("timestamp", "open", "high", "low", "close", "volume"):
        for k, orig in cols.items():
            if k == want:
                rename[orig] = want
                break
    df = df.rename(columns=rename)
    if "timestamp" not in df.columns:
        df = df.rename(columns={df.columns[0]: "timestamp"})
    return df.iloc[:limit].copy()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=_ROOT / "data" / "mt5" / "XAUUSD_M15.csv")
    ap.add_argument("--limit", type=int, default=2000)
    ap.add_argument(
        "--out",
        type=Path,
        default=_ROOT
        / "docs"
        / "governance"
        / "msip_shadow_design_v1"
        / "CRT_LOCAL_MATH_PARITY_AUDIT_RESULT_V1.json",
    )
    args = ap.parse_args(argv)

    csv_path = args.csv.resolve()
    corpus_sha = _sha256_file(csv_path)
    df = _load_ohlcv(csv_path, args.limit)

    # --- body_ratio / wick_size: CRT Candle vs candle_math / pipeline ---
    body_errs = []
    wick_errs = []
    for _, row in df.iterrows():
        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
        candle = Candle(
            timestamp=str(row["timestamp"]),
            open=o,
            high=h,
            low=l,
            close=c,
            volume=float(row.get("volume", 0) or 0),
        )
        body_errs.append(abs(candle.body_ratio - cm.body_ratio(o, h, l, c)))
        wick_errs.append(abs(candle.wick_size - cm.candle_range(h, l)))

    pipeline = FeaturePipeline(df)
    enriched, _ = pipeline.run()

    # Align pipeline body_ratio / wick_size with candle_math on same rows
    pipe_body_errs = []
    pipe_wick_errs = []
    if "body_ratio" in enriched.columns and "wick_size" in enriched.columns:
        for _, row in enriched.iterrows():
            o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
            if pd.isna(row["body_ratio"]):
                continue
            pipe_body_errs.append(abs(float(row["body_ratio"]) - cm.body_ratio(o, h, l, c)))
            pipe_wick_errs.append(abs(float(row["wick_size"]) - cm.candle_range(h, l)))

    # --- ATR: CRT absolute SMA-TR vs pipeline atr (likely relative) ---
    # Replicate CRT compute_atr on a rolling window of last 14 TRs
    trs = []
    closes = df["close"].astype(float).values
    highs = df["high"].astype(float).values
    lows = df["low"].astype(float).values
    for i in range(1, len(df)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    period = 14
    crt_atr_abs = []
    for i in range(len(trs)):
        window = trs[max(0, i + 1 - period) : i + 1]
        crt_atr_abs.append(float(np.mean(window)) if window else 0.0)

    # Compare on enriched rows that have atr
    atr_ratios = []
    atr_rel_vs_abs = []
    if "atr" in enriched.columns:
        # enriched may drop warmup — join by position after finalize
        # Use raw df indices 1.. matched approximately via close
        for i, (_, row) in enumerate(enriched.iterrows()):
            # find matching bar in original by timestamp
            pass
        # Simpler: recompute on full df pipeline without finalize drop via columns before finalize
        # Use compute_indicators path: atr column after run
        # Map by integer position: enriched is subset; use close match
        close_to_crt = {}
        for i in range(1, len(df)):
            close_to_crt[float(closes[i])] = crt_atr_abs[i - 1]
        for _, row in enriched.iterrows():
            if pd.isna(row.get("atr")):
                continue
            pipe_atr = float(row["atr"])
            cl = float(row["close"])
            # approximate: crt atr abs / close ≈ relative if transform is close-relative
            crt_abs = close_to_crt.get(cl)
            if crt_abs is None:
                continue
            if cl != 0:
                atr_rel_vs_abs.append(abs(pipe_atr - (crt_abs / cl)))
            atr_ratios.append(
                {
                    "pipe_atr": pipe_atr,
                    "crt_atr_abs": crt_abs,
                    "crt_abs_over_close": (crt_abs / cl) if cl else None,
                }
            )

    # --- EMA: CRT (2,5) vs pipeline ema_fast/ema_slow ---
    ema_fast_crt = 0.0
    ema_slow_crt = 0.0
    crt_ef, crt_es = [], []
    for i, cl in enumerate(closes):
        if i == 0 or ema_fast_crt == 0.0:
            ema_fast_crt = ema_slow_crt = float(cl)
        else:
            af, as_ = 2.0 / (2 + 1), 2.0 / (5 + 1)
            ema_fast_crt = float(cl) * af + ema_fast_crt * (1 - af)
            ema_slow_crt = float(cl) * as_ + ema_slow_crt * (1 - as_)
        crt_ef.append(ema_fast_crt)
        crt_es.append(ema_slow_crt)

    ema_fast_diffs = []
    ema_slow_diffs = []
    if "ema_fast" in enriched.columns:
        # zip by timestamp
        ts_to_i = {str(t): i for i, t in enumerate(df["timestamp"].astype(str))}
        for _, row in enriched.iterrows():
            key = str(row["timestamp"])
            if key not in ts_to_i or pd.isna(row["ema_fast"]):
                continue
            i = ts_to_i[key]
            ema_fast_diffs.append(abs(float(row["ema_fast"]) - crt_ef[i]))
            ema_slow_diffs.append(abs(float(row["ema_slow"]) - crt_es[i]))

    def _max(xs):
        return float(max(xs)) if xs else None

    def _pass_exact(max_err, tol=1e-9):
        if max_err is None:
            return "INSUFFICIENT"
        return "PASS" if max_err <= tol else "FAIL"

    body_max = _max(body_errs)
    wick_max = _max(wick_errs)
    pipe_body_max = _max(pipe_body_errs)
    pipe_wick_max = _max(pipe_wick_errs)

    # ATR relationship
    atr_transform_max = _max(atr_rel_vs_abs)
    if atr_transform_max is not None and atr_transform_max <= 1e-4:
        atr_verdict = "TRANSFORM"
        atr_note = "pipeline atr ≈ CRT absolute ATR / close on sample"
    elif atr_ratios:
        atr_verdict = "TRANSFORM_CANDIDATE_OR_FAIL"
        atr_note = (
            f"max|pipe_atr - crt_abs/close|={atr_transform_max}; "
            "not assumed equal without registry"
        )
    else:
        atr_verdict = "INSUFFICIENT"
        atr_note = "no overlapping atr samples"

    ema_f_max = _max(ema_fast_diffs)
    ema_s_max = _max(ema_slow_diffs)
    if ema_f_max is not None and ema_f_max <= 1e-6 and ema_s_max is not None and ema_s_max <= 1e-6:
        ema_verdict = "PASS"
        ema_note = "pipeline ema matches CRT(2,5) on sample"
    else:
        ema_verdict = "TRANSFORM_OR_MISMATCH"
        ema_note = (
            f"CRT uses span (2,5) seed-from-first-close; "
            f"max|Δema_fast|={ema_f_max}, max|Δema_slow|={ema_s_max}; "
            "do not bind as identical without span proof"
        )

    results = {
        "schema_id": "CRT_LOCAL_MATH_PARITY_AUDIT_RESULT_V1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "task_class": "OBSERVATION_ONLY",
        "authorization": "measurement only; does NOT authorize CRT consumer migration",
        "corpus_path": str(csv_path.relative_to(_ROOT)) if csv_path.is_relative_to(_ROOT) else str(csv_path),
        "corpus_sha256": corpus_sha,
        "sample_bars": int(args.limit),
        "enriched_bars": int(len(enriched)),
        "quantities": {
            "body_ratio": {
                "crt_vs_candle_math_max_abs_err": body_max,
                "pipeline_vs_candle_math_max_abs_err": pipe_body_max,
                "verdict": _pass_exact(body_max),
                "blocks_migration": True,
                "pass_criterion": "max abs err <= 1e-9",
            },
            "wick_size": {
                "crt_vs_candle_math_max_abs_err": wick_max,
                "pipeline_vs_candle_math_max_abs_err": pipe_wick_max,
                "verdict": _pass_exact(wick_max, tol=0.0) if wick_max == 0.0 else _pass_exact(wick_max),
                "blocks_migration": True,
                "pass_criterion": "exact high-low identity",
            },
            "atr": {
                "verdict": atr_verdict,
                "max_abs_err_pipe_vs_crt_abs_over_close": atr_transform_max,
                "n_compare": len(atr_rel_vs_abs),
                "note": atr_note,
                "blocks_migration": True,
                "pass_criterion": "document scale relationship; FAIL if assumed equal without transform proof",
            },
            "ema_fast_ema_slow": {
                "verdict": ema_verdict,
                "max_abs_err_ema_fast": ema_f_max,
                "max_abs_err_ema_slow": ema_s_max,
                "note": ema_note,
                "blocks_migration": True,
                "crt_params": {"fast": 2, "slow": 5, "alpha": "2/(N+1)"},
            },
        },
        "migration_authorized": False,
        "G-PARITY-01_suggested": None,
        "G-MIG-01": "CLOSED",
    }

    # Gate suggestion: PASS only if all migration-blocking quantities are PASS or registered TRANSFORM
    q = results["quantities"]
    ok_body = q["body_ratio"]["verdict"] == "PASS"
    ok_wick = q["wick_size"]["verdict"] == "PASS"
    ok_atr = q["atr"]["verdict"] in ("TRANSFORM", "PASS")
    ok_ema = q["ema_fast_ema_slow"]["verdict"] in ("PASS", "TRANSFORM")
    # EMA TRANSFORM_OR_MISMATCH is not a registered transform — G-PARITY not full PASS
    if ok_body and ok_wick and ok_atr and ok_ema:
        results["G-PARITY-01_suggested"] = "PASS"
    elif ok_body and ok_wick:
        results["G-PARITY-01_suggested"] = "PARTIAL_TRANSFORM_REGISTRY_INCOMPLETE"
    else:
        results["G-PARITY-01_suggested"] = "NOT_PASSED"

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "G-PARITY-01_suggested": results["G-PARITY-01_suggested"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
