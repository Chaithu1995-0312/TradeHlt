#!/usr/bin/env python3
"""
run_rr_xauusd_2m.py
===================
OBSERVATION ONLY — run the trained RR (NanoInference / rr_fusion checkpoint)
on XAUUSD trailing 2 months (same window as Gaussian + ZoneGate runs).

Also records the LIVE base RREngine (candle polarity) for dual-path parity
with the Gaussian ML vs heuristic recording pattern.

Trained artifact:
  models/rr_model.json  (== models/rr_model_202605_bnb_v2.json byte-identical)
  registry active: 202605_bnb_v2_bnbusdt
  n_features=38, schema v3.0, quarantined under v4 (incompatible_with_schema=4.0)

Live spine truth:
  engine_runner.rr_fusion.enabled=false (F-038) → trained path NOT on spine
  fusion 'rr' slot = RREngine polarity only

Dim contract:
  Model is 38-dim schema v3 name order. Live CANONICAL is 39-dim v4.
  RRFusionLayer refuses load (fail-closed). Observation scores via
  name-mapped v3-order 38-vector (macd_hist←macd_hist_z, wick_size←candle_range),
  NOT ambient 39-slice (that would silently misalign post-index-19).

Outputs:
  results/rr_xauusd_2m/rr_xauusd_2m_manifest_<ts>.json
  results/rr_xauusd_2m/rr_xauusd_2m_LATEST.json
  results/rr_xauusd_2m/rr_scores_xauusd_2m_<ts>.csv

Authority: research/docs only. No promote. No re-enable. No economic claim.
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

OUT_DIR = ROOT / "results" / "rr_xauusd_2m"
WINDOW_NOTE = (
    "data/XAUUSD_W2026-03-23-to-2026-05-21.csv  "
    "# trailing ~2m export (export_xauusd_window DEFAULT_MONTHS=2)"
)
TRAINED_PATH = "models/rr_model.json"
REGISTRY_ACTIVE_PATH = "models/rr_model_202605_bnb_v2.json"


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


def build_v3_order(canonical_v4: list[str]) -> list[str]:
    """Reconstruct schema-v3 38-name order from live v4 order.

    v4 changes vs v3:
      macd_hist → (macd_hist_raw, macd_hist_z)  — drop raw, keep hist as macd_hist
      wick_size → candle_range                   — restore name wick_size in order
    """
    v3: list[str] = []
    for n in canonical_v4:
        if n == "macd_hist_raw":
            continue
        if n == "macd_hist_z":
            v3.append("macd_hist")
        elif n == "candle_range":
            v3.append("wick_size")
        else:
            v3.append(n)
    return v3


def extract_v3_vector(feat: dict, v3_order: list[str]) -> list[float]:
    """Name-anchored extract into v3 order using live v4 feature dict."""
    vec: list[float] = []
    for name in v3_order:
        if name == "macd_hist":
            if "macd_hist_z" not in feat:
                raise KeyError("macd_hist_z")
            vec.append(float(feat["macd_hist_z"]))
        elif name == "wick_size":
            if "candle_range" not in feat:
                raise KeyError("candle_range")
            vec.append(float(feat["candle_range"]))
        else:
            if name not in feat:
                raise KeyError(name)
            vec.append(float(feat[name]))
    return vec


def raw_ml_path(engine, features: list[float]) -> dict:
    """Compute ridge expected_rr + GNB p_win + confidence WITHOUT the F-044 gate.

    Mirrors NanoInferenceEngine.predict arithmetic so observation can see the
    model output even when legacy_scalar gate forces 100% bypass.
    """
    n = len(engine.W)
    feats = list(features)
    if engine.zero_indices:
        for idx in engine.zero_indices:
            if idx < n:
                feats[idx] = 0.0
    X = [
        (float(feats[i]) - engine.scale_mu[i]) / engine.scale_sigma[i]
        for i in range(n)
    ]
    delta = [X[i] - engine.conf_mu[i] for i in range(n)]
    d_sq = 0.0
    for i in range(n):
        row_dot = 0.0
        Pi = engine.conf_P[i]
        for j in range(n):
            row_dot += Pi[j] * delta[j]
        d_sq += delta[i] * row_dot
    confidence = math.exp(-0.5 * min(d_sq, 1e6))
    confidence = min(1.0, max(0.0, confidence))
    expected_rr = sum(X[i] * engine.W[i] for i in range(n)) + engine.b
    # clamp like predict
    from config_layer.rr.rr_pattern_miner import RR_SCORE_MAX, RR_SCORE_MIN

    expected_rr = min(RR_SCORE_MAX, max(RR_SCORE_MIN, expected_rr))
    ll_loss = 0.0
    ll_win = 0.0
    for i in range(n):
        ll_loss += engine.gnb_C_loss[i] - 0.5 * engine.gnb_V_loss[i] * (
            X[i] - engine.gnb_mu_loss[i]
        ) ** 2
        ll_win += engine.gnb_C_win[i] - 0.5 * engine.gnb_V_win[i] * (
            X[i] - engine.gnb_mu_win[i]
        ) ** 2
    max_ll = ll_win if ll_win > ll_loss else ll_loss
    exp_loss = math.exp(ll_loss - max_ll)
    exp_win = math.exp(ll_win - max_ll)
    p_win = exp_win / (exp_loss + exp_win)
    ml_score = 1.0 / (1.0 + math.exp(-(expected_rr / 3.0)))
    dof = n - len(engine.zero_indices or [])
    return {
        "expected_rr_raw": float(expected_rr),
        "p_win_raw": float(p_win),
        "ml_score_raw": float(ml_score),
        "confidence_raw": float(confidence),
        "d_sq": float(d_sq),
        "dof": int(dof),
    }


def main() -> int:
    from config_layer.rr.rr_fusion import RRFusionLayer
    from config_layer.rr.rr_pattern_miner import NanoInferenceEngine
    from data_ingestion.xauusd_phase1_candidate import (
        PHASE1_SHA256,
        PHASE1_STATUS,
        guard_xauusd_csv_path,
    )
    from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
    from engines.rr_engine import RREngine
    from features.feature_pipeline import FeaturePipeline
    from features.feature_schema import (
        CANONICAL_FEATURE_DIM,
        CANONICAL_FEATURE_ORDER,
        FEATURE_ORDER_HASH,
        SCHEMA_HASH,
        SCHEMA_V3_FEATURE_DIM,
    )

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

    v3_order = build_v3_order(list(CANONICAL_FEATURE_ORDER))
    if len(v3_order) != SCHEMA_V3_FEATURE_DIM:
        raise RuntimeError(
            f"v3 order len {len(v3_order)} != SCHEMA_V3_FEATURE_DIM={SCHEMA_V3_FEATURE_DIM}"
        )

    # ── load trained model ──────────────────────────────────────────────
    p_trained = Path(TRAINED_PATH)
    p_reg = Path(REGISTRY_ACTIVE_PATH)
    bundle = json.loads(p_trained.read_text(encoding="utf-8"))
    byte_identical = (
        p_reg.exists() and p_trained.read_bytes() == p_reg.read_bytes()
    )

    reg_active = {}
    reg_path = Path("models/rr_registry.json")
    if reg_path.exists():
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
        reg_active = {
            k: {
                "model_file": v.get("model_file"),
                "n_features": v.get("n_features"),
                "active": v.get("active"),
            }
            for k, v in reg.items()
            if isinstance(v, dict) and v.get("active")
        }

    # Production layer refuses load under v4 — record that
    layer = RRFusionLayer(model_path=TRAINED_PATH, threshold=0.5, enabled=True)
    layer_status = {
        "is_loaded": bool(layer.is_loaded),
        "load_error": layer.load_error,
        "note": "RRFusionLayer fail-closed under n_features 38 != CANONICAL 39",
    }
    print(f"RRFusionLayer loaded={layer.is_loaded} err={layer.load_error}")

    engine = NanoInferenceEngine.load(TRAINED_PATH)
    print(f"NanoInferenceEngine n_features={engine.n_features}")

    # Optional: heuristic gaussian for blend path (what fusion would pass in)
    print("scoring heuristic gaussian for fusion-blend context...")
    h_eng = HeuristicGaussianEngine(
        {"instrument": "XAUUSD"}, instrument="XAUUSD", preload_registry=True
    )
    g_scores = np.full(len(records), np.nan)
    for i, feat in enumerate(records):
        try:
            g_scores[i] = float(h_eng.compute(feat, candle_idx=i).get("score", 0.5))
        except Exception:
            g_scores[i] = 0.5

    # ── trained RR predict + raw ML path ────────────────────────────────
    n = len(records)
    final_scores = np.full(n, np.nan)
    expected_rrs = np.full(n, np.nan)
    p_wins = np.full(n, np.nan)
    confidences = np.full(n, np.nan)
    statuses: list[str] = []
    status_counts: Counter = Counter()

    raw_expected = np.full(n, np.nan)
    raw_p_win = np.full(n, np.nan)
    raw_ml_score = np.full(n, np.nan)
    raw_conf = np.full(n, np.nan)
    d_sqs = np.full(n, np.nan)

    exceptions = 0
    extract_fail = 0
    first_err = None

    for i, feat in enumerate(records):
        try:
            vec = extract_v3_vector(feat, v3_order)
        except Exception as e:
            extract_fail += 1
            statuses.append("extract_fail")
            status_counts["extract_fail"] += 1
            if first_err is None:
                first_err = f"extract: {type(e).__name__}: {e}"
            continue

        try:
            raw = raw_ml_path(engine, vec)
            raw_expected[i] = raw["expected_rr_raw"]
            raw_p_win[i] = raw["p_win_raw"]
            raw_ml_score[i] = raw["ml_score_raw"]
            raw_conf[i] = raw["confidence_raw"]
            d_sqs[i] = raw["d_sq"]
        except Exception as e:
            if first_err is None:
                first_err = f"raw: {type(e).__name__}: {e}"

        try:
            g = float(g_scores[i]) if np.isfinite(g_scores[i]) else 0.5
            out = engine.predict(
                vec,
                gaussian_score=g,
                gaussian_p_win=0.5,
                threshold=0.5,
            )
            final_scores[i] = float(out.get("final_score", float("nan")))
            expected_rrs[i] = float(out.get("expected_rr", float("nan")))
            p_wins[i] = float(out.get("probability_of_win", float("nan")))
            confidences[i] = float(out.get("confidence", float("nan")))
            st = str(out.get("status", ""))
            statuses.append(st)
            status_counts[st] += 1
        except Exception as e:
            exceptions += 1
            statuses.append(type(e).__name__)
            status_counts[type(e).__name__] += 1
            if first_err is None:
                first_err = f"predict: {type(e).__name__}: {e}"

    while len(statuses) < n:
        statuses.append("")

    bypass_n = int(status_counts.get("bypassed_low_confidence", 0))
    success_n = int(status_counts.get("success", 0))
    print(
        f"TRAINED RR: n={n} exceptions={exceptions} extract_fail={extract_fail} "
        f"bypass={bypass_n} success={success_n}"
    )
    print(
        f"  gated final_score mean={_stats(final_scores).get('mean')} "
        f"raw expected_rr mean={_stats(raw_expected).get('mean')} "
        f"raw conf mean={_stats(raw_conf).get('mean')}"
    )

    # ── live polarity RREngine ──────────────────────────────────────────
    print("scoring live RREngine polarity...")
    pol_eng = RREngine({"min_rr": 1.5})
    pol_scores = np.full(n, np.nan)
    pol_reasons: Counter = Counter()
    pol_exc = 0
    for i, feat in enumerate(records):
        try:
            out = pol_eng.compute(feat)
            pol_scores[i] = float(out.get("score", float("nan")))
            pol_reasons[str(out.get("reason", ""))[:40]] += 1
        except Exception:
            pol_exc += 1
    print(
        f"POLARITY mean={_stats(pol_scores).get('mean')} "
        f"std={_stats(pol_scores).get('std')} exceptions={pol_exc}"
    )

    # ── persist CSV ─────────────────────────────────────────────────────
    score_table = {
        "timestamp": timestamps,
        # trained gated path (official predict)
        "rr_trained_final_score": [
            None if not np.isfinite(x) else round(float(x), 6) for x in final_scores
        ],
        "rr_trained_expected_rr_gated": [
            None if not np.isfinite(x) else round(float(x), 6) for x in expected_rrs
        ],
        "rr_trained_p_win_gated": [
            None if not np.isfinite(x) else round(float(x), 6) for x in p_wins
        ],
        "rr_trained_confidence": [
            None if not np.isfinite(x) else round(float(x), 6) for x in confidences
        ],
        "rr_trained_status": statuses,
        # raw ML (gate-bypassed observation — F-044 context)
        "rr_trained_expected_rr_raw": [
            None if not np.isfinite(x) else round(float(x), 6) for x in raw_expected
        ],
        "rr_trained_p_win_raw": [
            None if not np.isfinite(x) else round(float(x), 6) for x in raw_p_win
        ],
        "rr_trained_ml_score_raw": [
            None if not np.isfinite(x) else round(float(x), 6) for x in raw_ml_score
        ],
        "rr_trained_confidence_raw": [
            None if not np.isfinite(x) else round(float(x), 6) for x in raw_conf
        ],
        "rr_trained_d_sq": [
            None if not np.isfinite(x) else round(float(x), 6) for x in d_sqs
        ],
        # live polarity
        "rr_polarity_score": [
            None if not np.isfinite(x) else round(float(x), 6) for x in pol_scores
        ],
        # context gaussian used for blend
        "gaussian_heuristic_for_blend": [
            None if not np.isfinite(x) else round(float(x), 6) for x in g_scores
        ],
    }
    scores_csv = OUT_DIR / f"rr_scores_xauusd_2m_{ts}.csv"
    pd.DataFrame(score_table).to_csv(scores_csv, index=False)

    active_version = None
    av = ROOT / "configs" / "production" / "ACTIVE_VERSION"
    if av.exists():
        active_version = av.read_text(encoding="utf-8").strip()

    trained_stats = {
        "gated_final_score": _stats(final_scores),
        "gated_expected_rr": _stats(expected_rrs),
        "gated_p_win": _stats(p_wins),
        "confidence": _stats(confidences),
        "raw_expected_rr": _stats(raw_expected),
        "raw_p_win": _stats(raw_p_win),
        "raw_ml_score": _stats(raw_ml_score),
        "raw_confidence": _stats(raw_conf),
        "d_sq": _stats(d_sqs),
    }

    manifest = {
        "run_id": f"rr_xauusd_2m_{ts}",
        "timestamp_utc": ts,
        "task": (
            "Run RR trained NanoInference model on XAUUSD ~2 months M15 "
            "(same window as Gaussian + ZoneGate); record dual path"
        ),
        "authority": (
            "OBSERVATION_ONLY — no promote / no rr_fusion re-enable / no economic claim"
        ),
        "instrument": "XAUUSD",
        "timeframe": "M15",
        "active_config": active_version,
        "paired_with": [
            "results/gaussian_xauusd_2m/gaussian_xauusd_2m_LATEST.json",
            "results/zonegate_xauusd_2m/zonegate_xauusd_2m_LATEST.json",
        ],
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
            "n_bars_scored": n,
            "ts_first_scored": timestamps[0] if timestamps else None,
            "ts_last_scored": timestamps[-1] if timestamps else None,
        },
        "feature_pipeline": {
            "schema_hash": SCHEMA_HASH,
            "feature_order_hash": FEATURE_ORDER_HASH,
            "canonical_dim_live": CANONICAL_FEATURE_DIM,
            "schema_v3_feature_dim": SCHEMA_V3_FEATURE_DIM,
            "warmup": "features built on FULL frozen corpus, then 2m slice applied",
            "vector_shape_full": list(vectors.shape),
        },
        "rr_trained_model": {
            "kind": "NanoInferenceEngine / rr_fusion checkpoint",
            "path": TRAINED_PATH,
            "registry_active_path": REGISTRY_ACTIVE_PATH,
            "byte_identical_to_registry_active": byte_identical,
            "sha256": _sha256_file(p_trained),
            "n_features": bundle.get("n_features"),
            "feature_schema": bundle.get("feature_schema"),
            "schema_version": bundle.get("schema_version"),
            "n_train": bundle.get("n_train"),
            "ridge_alpha": bundle.get("ridge_alpha"),
            "zero_indices": bundle.get("zero_indices"),
            "incompatible_with_schema": bundle.get("incompatible_with_schema"),
            "quarantine_reason": bundle.get("quarantine_reason"),
            "quarantined_at": bundle.get("quarantined_at"),
            "registry_active": reg_active,
            "rr_fusion_layer": layer_status,
            "spine_enabled": False,
            "spine_note": (
                "engine_runner.rr_fusion.enabled=false (F-038); "
                "selected_not_enabled in active_models.yaml"
            ),
            "extract_path": "name_mapped_v3_order_38",
            "v3_order": v3_order,
            "v3_order_dim": len(v3_order),
            "blend_gaussian": "HeuristicGaussianEngine on same bars (for predict blend)",
        },
        "rr_polarity_live": {
            "kind": "RREngine candle polarity (NOT trained)",
            "spine_enabled": True,
            "note": "Live fusion 'rr' slot; polarity ∈[0.5,1] — F-048 name mismatch vs thr 1.5",
            "score_stats": _stats(pol_scores),
            "exceptions": pol_exc,
            "reason_counts": dict(pol_reasons.most_common(10)),
        },
        "runtime_trained": {
            "n_rows": n,
            "exceptions": exceptions,
            "extract_fail": extract_fail,
            "first_error": first_err,
            "status_counts": dict(status_counts),
            "bypass_count": bypass_n,
            "bypass_rate": bypass_n / max(n, 1),
            "success_count": success_n,
            "status": (
                "EXECUTED"
                if exceptions == 0 and extract_fail == 0
                else "EXECUTED_WITH_ERRORS"
            ),
        },
        "score_stats_trained": trained_stats,
        "artifacts": {
            "scores_csv": str(scores_csv).replace("\\", "/"),
        },
        "interpretation_guardrails": [
            "OBSERVATION ONLY — rr_fusion stays enabled:false; no promote (F-038/F-044).",
            "Model quarantined under schema v4 (positional vectors invalid if ambient-sliced); "
            "this run used name-mapped v3 order, not fail-open truncate.",
            "Gated path expected to high-bypass under legacy_scalar conf gate (F-044); "
            "raw_* columns expose ML expected_rr without that gate for diagnostics.",
            "Labels F-022 contaminated historically (F-045/F-059); no economic authority.",
            "PIT_UNCLEAN provenance (F-051) — no causal retrain performed.",
            "Polarity path is the LIVE consumer; trained path is orphan vs spine.",
        ],
    }

    manifest_path = OUT_DIR / f"rr_xauusd_2m_manifest_{ts}.json"
    latest_path = OUT_DIR / "rr_xauusd_2m_LATEST.json"
    for path in (manifest_path, latest_path):
        manifest["artifacts"]["manifest_json"] = str(manifest_path).replace("\\", "/")
        manifest["artifacts"]["latest_json"] = str(latest_path).replace("\\", "/")
        path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    print("--- DONE ---")
    print(f"manifest: {manifest_path}")
    print(f"scores:   {scores_csv}")
    print(f"latest:   {latest_path}")
    print(
        json.dumps(
            {
                "status": manifest["runtime_trained"]["status"],
                "bypass_rate": manifest["runtime_trained"]["bypass_rate"],
                "status_counts": dict(status_counts),
                "gated_final_score": trained_stats["gated_final_score"],
                "raw_expected_rr": trained_stats["raw_expected_rr"],
                "raw_confidence": trained_stats["raw_confidence"],
                "polarity": _stats(pol_scores),
                "layer_fail_closed": not layer.is_loaded,
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
