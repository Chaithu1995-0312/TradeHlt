#!/usr/bin/env python3
"""
run_gaussian_xauusd_2m.py
========================
OBSERVATION ONLY — run trained Gaussian NB checkpoints on XAUUSD trailing 2 months.

Data window (matches export_xauusd_window DEFAULT_MONTHS=2 / named export):
  trailing 2 calendar months of Phase-1 frozen corpus data/mt5/XAUUSD_M15.csv
  named slice file: data/XAUUSD_W2026-03-23-to-2026-05-21.csv

No XAUUSD-trained Gaussian exists in models/gaussian_registry.json. This scores
the registry-active BNB/ETH (and optional EUR) checkpoints cross-instrument.

Outputs (results/ — gitignored):
  results/gaussian_xauusd_2m/gaussian_xauusd_2m_manifest_<ts>.json
  results/gaussian_xauusd_2m/gaussian_xauusd_2m_LATEST.json
  results/gaussian_xauusd_2m/gaussian_scores_xauusd_2m_<ts>.csv

Authority: research/docs only. No promote. No config edit. No economic claim.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = ROOT / "results" / "gaussian_xauusd_2m"
WINDOW_NOTE = (
    "data/XAUUSD_W2026-03-23-to-2026-05-21.csv  "
    "# trailing ~2m export (export_xauusd_window DEFAULT_MONTHS=2)"
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _stats(arr) -> dict:
    a = np.asarray(arr, dtype=np.float64)
    finite = a[np.isfinite(a)]
    if finite.size == 0:
        return {"n": int(a.size), "n_finite": 0, "n_nan": int(a.size)}
    return {
        "n": int(a.size),
        "n_finite": int(finite.size),
        "n_nan": int(a.size - finite.size),
        "mean": float(finite.mean()),
        "std": float(finite.std()),
        "min": float(finite.min()),
        "max": float(finite.max()),
        "p01": float(np.percentile(finite, 1)),
        "p10": float(np.percentile(finite, 10)),
        "p50": float(np.percentile(finite, 50)),
        "p90": float(np.percentile(finite, 90)),
        "p99": float(np.percentile(finite, 99)),
        "n_unique_6dp": int(np.unique(np.round(finite, 6)).size),
        "is_constant": bool(finite.std() < 1e-12),
        "frac_ge_0_99": (
            float((finite >= 0.99).mean()) if finite.max() <= 1.01 else None
        ),
        "frac_le_0_01": (
            float((finite <= 0.01).mean()) if finite.min() >= -0.01 else None
        ),
    }


def main() -> int:
    from data_ingestion.xauusd_phase1_candidate import (
        PHASE1_SHA256,
        PHASE1_STATUS,
        guard_xauusd_csv_path,
    )
    from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
    from features.feature_pipeline import FeaturePipeline
    from features.feature_schema import (
        CANONICAL_FEATURE_ORDER,
        FEATURE_ORDER_HASH,
        SCHEMA_HASH,
    )
    from features.gaussian_schema_contract import extract_model_feature_vector
    from training.trainer import load_gaussian_model

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    corpus = Path(guard_xauusd_csv_path("data/mt5/XAUUSD_M15.csv", "XAUUSD"))
    df = pd.read_csv(corpus)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    corpus_sha = _sha256_file(corpus)

    print(f"corpus rows={len(df)} range={df.timestamp.iloc[0]} .. {df.timestamp.iloc[-1]}")
    print(f"corpus sha256={corpus_sha[:16]}... phase1_status={PHASE1_STATUS}")

    end = df["timestamp"].max()
    start = end - pd.DateOffset(months=2)
    mask = (df["timestamp"] >= start) & (df["timestamp"] <= end)
    print(f"2m window: {start} .. {end}  n={int(mask.sum())}")

    print("building features on full corpus (warmup)...")
    pipe = FeaturePipeline(df)
    enriched, vectors = pipe.run()
    print(f"enriched={len(enriched)} vectors={vectors.shape}")

    if "timestamp" not in enriched.columns:
        raise RuntimeError("FeaturePipeline output missing timestamp column")
    enr_ts = pd.to_datetime(enriched["timestamp"])
    enr_mask = (enr_ts >= start) & (enr_ts <= end)
    window_df = enriched.loc[enr_mask].reset_index(drop=True)
    print(
        f"window enriched rows={len(window_df)} "
        f"ts={window_df.timestamp.iloc[0]} .. {window_df.timestamp.iloc[-1]}"
    )

    cols = [c for c in CANONICAL_FEATURE_ORDER if c in window_df.columns]
    records = window_df[cols].to_dict(orient="records")
    timestamps = [str(t) for t in window_df["timestamp"].tolist()]

    candidates = [
        {
            "version": "p5_20260524T120449",
            "instrument_trained": "BNBUSDT",
            "registry_active": True,
            "path": "models/BNBUSDT/bnbusdt_balanced_20260524/gaussian_p5_20260524T120449.json",
            "primary": True,
        },
        {
            "version": "v5_auto_2026_06_eth",
            "instrument_trained": "ETHUSDT",
            "registry_active": True,
            "path": "models/ETHUSDT/20260519_113806/gaussian_v5_auto_2026_06_eth.json",
            "primary": False,
        },
        {
            "version": "v6_2026_05_eur",
            "instrument_trained": "EURUSD",
            "registry_active": False,
            "path": "models/EURUSD/20260519_002117/gaussian_v6_2026_05_eur.json",
            "primary": False,
        },
    ]

    model_reports = []
    score_table: dict = {"timestamp": timestamps}

    for cand in candidates:
        p = Path(cand["path"])
        rep = {
            "version": cand["version"],
            "instrument_trained": cand["instrument_trained"],
            "registry_active": cand["registry_active"],
            "path": cand["path"],
            "path_exists": p.exists(),
            "primary_report": cand["primary"],
            "target_instrument": "XAUUSD",
            "cross_instrument_note": (
                "No XAUUSD Gaussian checkpoint in registry; "
                "scoring is cross-instrument application of trained NB"
            ),
        }
        if not p.exists():
            rep["status"] = "MISSING_CHECKPOINT"
            model_reports.append(rep)
            print(f"MISSING {cand['version']}")
            continue

        rep["sha256"] = _sha256_file(p)
        mf = cand["path"].replace("\\", "/")
        if mf.startswith("models/"):
            mf = mf[len("models/") :]
        try:
            model, scaler, meta = load_gaussian_model(mf)
        except Exception as e:
            rep["status"] = "LOAD_FAIL"
            rep["error"] = f"{type(e).__name__}: {e}"
            model_reports.append(rep)
            print(f"LOAD_FAIL {cand['version']}: {e}")
            continue

        schema_resolved = list((meta or {}).get("feature_schema_resolved") or [])
        schema_alignment = (meta or {}).get("schema_alignment")
        name_anchored = bool((meta or {}).get("name_anchored"))
        bundle = json.loads(p.read_text(encoding="utf-8"))
        schema_saved = list(bundle.get("feature_schema") or [])
        order = schema_resolved or schema_saved

        rep.update(
            {
                "status": "LOADED",
                "model_n_features": getattr(model, "n_features", None),
                "schema_alignment": schema_alignment,
                "name_anchored": name_anchored,
                "feature_schema_resolved_dim": len(schema_resolved),
                "feature_schema_saved_dim": len(schema_saved),
                "feature_order_hash_bundle": bundle.get("feature_order_hash"),
                "feature_order_hash_runtime": FEATURE_ORDER_HASH,
                "hash_match_runtime": bundle.get("feature_order_hash")
                == FEATURE_ORDER_HASH,
            }
        )

        scores = np.full(len(records), np.nan)
        expected_rrs = np.full(len(records), np.nan)
        confs = np.full(len(records), np.nan)
        exceptions = 0
        fallback = 0
        reasons: Counter = Counter()
        first_err = None

        for i, feat in enumerate(records):
            try:
                vec = extract_model_feature_vector(feat, order)
                if len(vec) != model.n_features:
                    fallback += 1
                    scores[i] = 0.5
                    reasons["dim_mismatch"] += 1
                    continue
                scaled = scaler.transform_one(vec)
                expected_rr, confidence, _probs = model.predict_expected_rr(scaled)
                sc = 1.0 / (1.0 + math.exp(-float(expected_rr)))
                scores[i] = max(0.0, min(1.0, sc))
                expected_rrs[i] = float(expected_rr)
                confs[i] = float(confidence)
                reasons["ml_gaussian"] += 1
            except Exception as e:
                exceptions += 1
                reasons[type(e).__name__] += 1
                if first_err is None:
                    first_err = f"{type(e).__name__}: {e}"

        rep["runtime"] = {
            "n_rows": len(records),
            "exceptions": exceptions,
            "fallback_dim_mismatch": fallback,
            "reason_counts": dict(reasons),
            "first_error": first_err,
            "extract_path": "name_anchored_extract",
        }
        rep["score_stats"] = _stats(scores)
        rep["expected_rr_stats"] = _stats(expected_rrs)
        rep["confidence_stats"] = _stats(confs)
        rep["status"] = "EXECUTED" if exceptions == 0 else "EXECUTED_WITH_ERRORS"
        if rep["score_stats"].get("is_constant"):
            rep["note_constant"] = "scores constant — zero discrimination on this window"
        if (
            rep["score_stats"].get("frac_ge_0_99") is not None
            and rep["score_stats"]["frac_ge_0_99"] > 0.9
        ):
            rep["note_saturated"] = "scores saturated near 1.0 on majority of bars"

        score_table[f"score_{cand['version']}"] = [
            None if not np.isfinite(x) else round(float(x), 6) for x in scores
        ]
        score_table[f"expected_rr_{cand['version']}"] = [
            None if not np.isfinite(x) else round(float(x), 6) for x in expected_rrs
        ]
        model_reports.append(rep)
        print(
            f"EXECUTED {cand['version']} n={len(records)} "
            f"mean={rep['score_stats'].get('mean')} "
            f"std={rep['score_stats'].get('std')} "
            f"exceptions={exceptions} fallback={fallback}"
        )

    print("running live heuristic gaussian (reference, not trained)...")
    h_eng = HeuristicGaussianEngine(
        {"instrument": "XAUUSD"}, instrument="XAUUSD", preload_registry=True
    )
    h_scores = np.full(len(records), np.nan)
    h_reasons: Counter = Counter()
    h_exc = 0
    for i, feat in enumerate(records):
        try:
            out = h_eng.compute(feat, candle_idx=i)
            h_scores[i] = float(out.get("score", float("nan")))
            h_reasons[str(out.get("reason", ""))] += 1
        except Exception:
            h_exc += 1
    heuristic_rep = {
        "model": "HeuristicGaussianEngine_live",
        "note": (
            "LIVE fusion path when gaussian_impl=heuristic; "
            "NOT the trained NB (F-060)"
        ),
        "mu": h_eng.mu,
        "sigma": h_eng.sigma,
        "loaded_version": h_eng._loaded_version,
        "exceptions": h_exc,
        "reason_counts": dict(h_reasons),
        "score_stats": _stats(h_scores),
    }
    score_table["score_heuristic_live"] = [
        None if not np.isfinite(x) else round(float(x), 6) for x in h_scores
    ]
    print(
        f"HEURISTIC mean={heuristic_rep['score_stats'].get('mean')} "
        f"std={heuristic_rep['score_stats'].get('std')}"
    )

    scores_csv = OUT_DIR / f"gaussian_scores_xauusd_2m_{ts}.csv"
    pd.DataFrame(score_table).to_csv(scores_csv, index=False)

    active_version = None
    av = ROOT / "configs" / "production" / "ACTIVE_VERSION"
    if av.exists():
        active_version = av.read_text(encoding="utf-8").strip()

    manifest = {
        "run_id": f"gaussian_xauusd_2m_{ts}",
        "timestamp_utc": ts,
        "task": "Run trained Gaussian NB on XAUUSD ~2 months M15; record output",
        "authority": (
            "OBSERVATION_ONLY — no promote / no config edit / no economic claim"
        ),
        "instrument": "XAUUSD",
        "timeframe": "M15",
        "active_config": active_version,
        "corpus": {
            "path": str(corpus).replace("\\", "/"),
            "sha256": corpus_sha,
            "phase1_pin": PHASE1_SHA256,
            "phase1_status": PHASE1_STATUS,
            "full_rows": int(len(df)),
            "full_range": [str(df.timestamp.iloc[0]), str(df.timestamp.iloc[-1])],
        },
        "window": {
            "definition": (
                "trailing 2 calendar months from corpus end "
                "(export_xauusd_window DEFAULT_MONTHS=2)"
            ),
            "named_export_file": WINDOW_NOTE,
            "start": str(start),
            "end": str(end),
            "n_bars_raw_mask": int(mask.sum()),
            "n_bars_scored": len(records),
            "ts_first_scored": timestamps[0] if timestamps else None,
            "ts_last_scored": timestamps[-1] if timestamps else None,
        },
        "feature_pipeline": {
            "schema_hash": SCHEMA_HASH,
            "feature_order_hash": FEATURE_ORDER_HASH,
            "canonical_dim": len(CANONICAL_FEATURE_ORDER),
            "warmup": "features built on FULL frozen corpus, then 2m slice applied",
            "vector_shape_full": list(vectors.shape),
        },
        "registry_note": {
            "xauusd_active_gaussian": None,
            "active_map": {
                "ETHUSDT": "v5_auto_2026_06_eth",
                "BNBUSDT": "p5_20260524T120449",
            },
            "live_gaussian_impl": "heuristic (trained NB not on spine; F-060)",
        },
        "trained_models": model_reports,
        "live_heuristic_reference": heuristic_rep,
        "artifacts": {
            "scores_csv": str(scores_csv).replace("\\", "/"),
        },
        "interpretation_guardrails": [
            "No XAUUSD-trained Gaussian exists; scores are cross-instrument "
            "application of BNB/ETH/EUR checkpoints.",
            "Descriptive stats only — NOT economic validation, NOT promote "
            "authority (§6.5).",
            "Live spine uses HeuristicGaussianEngine, not these trained "
            "checkpoints (gaussian_impl=heuristic).",
            "Labels/training of NB artifacts are F-022 contaminated (F-060) — "
            "research/docs only.",
        ],
    }

    manifest_path = OUT_DIR / f"gaussian_xauusd_2m_manifest_{ts}.json"
    latest_path = OUT_DIR / "gaussian_xauusd_2m_LATEST.json"
    for path in (manifest_path, latest_path):
        manifest["artifacts"]["manifest_json"] = str(manifest_path).replace("\\", "/")
        manifest["artifacts"]["latest_json"] = str(latest_path).replace("\\", "/")
        path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    print("--- DONE ---")
    print(f"manifest: {manifest_path}")
    print(f"scores:   {scores_csv}")
    print(f"latest:   {latest_path}")
    for m in model_reports:
        summary = {
            k: m[k]
            for k in ("version", "status", "score_stats", "runtime")
            if k in m
        }
        print(json.dumps(summary, indent=2, default=str))
    print("heuristic", json.dumps(heuristic_rep["score_stats"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
