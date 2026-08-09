#!/usr/bin/env python3
"""
run_zonegate_xauusd_2m.py
========================
OBSERVATION ONLY — run the production ZoneGate trained registry on XAUUSD
trailing 2 months (same window as run_gaussian_xauusd_2m.py).

Data window:
  trailing 2 calendar months of Phase-1 frozen corpus data/mt5/XAUUSD_M15.csv
  named slice: data/XAUUSD_W2026-03-23-to-2026-05-21.csv

Trained artifact (production active):
  models/zone_registry_v4_2026_07.json
  zone_gate_registry active = v4_gaussian_runtime_2026_07

Scoring path = production EngineRunner path:
  get_zone_gate → score_zone_cluster (cluster knobs from engine_runner)

Outputs (results/ — gitignored):
  results/zonegate_xauusd_2m/zonegate_xauusd_2m_manifest_<ts>.json
  results/zonegate_xauusd_2m/zonegate_xauusd_2m_LATEST.json
  results/zonegate_xauusd_2m/zonegate_scores_xauusd_2m_<ts>.csv

Authority: research/docs only. No promote. No config edit. No economic claim.
F-036 NON_PIVOTAL / F-041B HONEST_NO_EDGE stand; this run does not reverse them.
"""
from __future__ import annotations

import hashlib
import json
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

OUT_DIR = ROOT / "results" / "zonegate_xauusd_2m"
WINDOW_NOTE = (
    "data/XAUUSD_W2026-03-23-to-2026-05-21.csv  "
    "# trailing ~2m export (export_xauusd_window DEFAULT_MONTHS=2)"
)
# Same window as Gaussian run — keep definition identical.
ACTIVE_ARTIFACT_DEFAULT = "models/zone_registry_v4_2026_07.json"
RETIRED_V3 = "models/zone_registry.json"


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
    from config_layer.production_config import get_prod_section
    from engines.live_engine import BitNetZoneGate, ZoneFeatureOrderError, get_zone_gate
    from engines.zone_cluster_score import score_zone_cluster
    from features.feature_pipeline import FeaturePipeline
    from features.feature_schema import (
        CANONICAL_FEATURE_ORDER,
        FEATURE_ORDER_HASH,
        SCHEMA_HASH,
        SCHEMA_V3_ALIASES,
    )
    from data_ingestion.xauusd_phase1_candidate import (
        PHASE1_SHA256,
        PHASE1_STATUS,
        guard_xauusd_csv_path,
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

    # ── resolve production artifact + knobs ─────────────────────────────
    er = get_prod_section("engine_runner")
    how_path = str(er.get("zone_registry_path") or ACTIVE_ARTIFACT_DEFAULT)
    zcfg = er.get("zone_gate") or {}
    if not isinstance(zcfg, dict):
        zcfg = {}

    thr = float(er.get("zone_cluster_threshold", zcfg.get("threshold", 0.25)) or 0.25)
    top_k = int(zcfg.get("top_k", 3))
    cluster_min_n = int(zcfg.get("cluster_min_n", 2))
    cluster_spread_max = float(zcfg.get("cluster_spread_max", 0.15))
    zone_mode = str(er.get("zone_mode", "hard"))

    artifact_path = how_path.replace("\\", "/")
    # Prefer repo-relative
    try:
        artifact_path = str(Path(artifact_path).resolve().relative_to(ROOT)).replace(
            "\\", "/"
        )
    except Exception:
        pass

    resolver_detail: dict = {"how_path": how_path, "artifact_path": artifact_path}
    try:
        from config_layer.model_resolver import resolve_zone_gate_runtime

        resolved = resolve_zone_gate_runtime(how_path=how_path)
        art = resolved.require_artifact()
        artifact_path = str(art).replace("\\", "/")
        try:
            artifact_path = str(Path(artifact_path).resolve().relative_to(ROOT)).replace(
                "\\", "/"
            )
        except Exception:
            pass
        resolver_detail.update(
            {
                "version": getattr(resolved, "version", None),
                "identity_parity": getattr(resolved, "identity_parity", None),
                "resolved_artifact": artifact_path,
            }
        )
    except Exception as e:
        resolver_detail["resolver_error"] = f"{type(e).__name__}: {e}"
        print(f"resolver soft-fail: {e}; using how_path={how_path}")

    p_art = Path(artifact_path)
    if not p_art.exists():
        p_art = ROOT / artifact_path
    if not p_art.exists():
        raise FileNotFoundError(f"ZoneGate artifact missing: {artifact_path}")

    bundle = json.loads(p_art.read_text(encoding="utf-8"))
    feature_order = list(bundle.get("feature_order") or [])
    n_zones = len(bundle.get("zones") or [])

    # Registry active pointer
    reg_path = ROOT / "models" / "zone_gate_registry.json"
    registry_active = {}
    if reg_path.exists():
        zreg = json.loads(reg_path.read_text(encoding="utf-8"))
        registry_active = {
            k: {"model_file": v.get("model_file"), "version": v.get("version")}
            for k, v in zreg.items()
            if isinstance(v, dict) and v.get("active")
        }

    live = list(CANONICAL_FEATURE_ORDER)
    missing = [n for n in feature_order if n not in live]
    feature_alignment = {
        "trained_feature_order_dim": len(feature_order),
        "live_canonical_dim": len(live),
        "missing_from_live": missing,
        "live_names_not_scored": [n for n in live if n not in set(feature_order)],
        "renames_applied": dict(SCHEMA_V3_ALIASES),
        "name_set_subset_ok": missing == [],
        "has_macd_hist_z": "macd_hist_z" in feature_order,
        "has_candle_range": "candle_range" in feature_order,
        "no_v3_names": not ({"macd_hist", "wick_size"} & set(feature_order)),
    }

    # Retired v3 must FAIL_CLOSED
    v3_status = None
    try:
        BitNetZoneGate(zone_path=RETIRED_V3)
        v3_status = "UNEXPECTED_OK — safety net broken"
    except ZoneFeatureOrderError as e:
        v3_status = f"FAIL_CLOSED_OK: {type(e).__name__}"
    except Exception as e:
        v3_status = f"{type(e).__name__}: {e}"

    print(f"loading ZoneGate artifact={artifact_path} n_zones={n_zones}")
    zg = get_zone_gate(str(p_art))
    print(
        f"loaded feature_order_dim={len(getattr(zg, 'feature_order', []) or [])} "
        f"zones={len(getattr(zg, '_zones', []) or [])}"
    )
    print(
        f"knobs thr={thr} top_k={top_k} cluster_min_n={cluster_min_n} "
        f"cluster_spread_max={cluster_spread_max} zone_mode={zone_mode}"
    )

    scores = np.full(len(records), np.nan)
    best_zone_scores = np.full(len(records), np.nan)
    passed_arr = np.zeros(len(records), dtype=np.int8)
    best_zone_ids: list = []
    top_score_lens = np.zeros(len(records), dtype=np.int16)
    exceptions = 0
    blocked = 0
    first_err = None
    reason_counts: Counter = Counter()
    zone_id_counts: Counter = Counter()

    for i, feat in enumerate(records):
        try:
            out = score_zone_cluster(
                feat,
                zg,
                zone_cluster_threshold=thr,
                cluster_min_n=cluster_min_n,
                cluster_spread_max=cluster_spread_max,
            )
            sc = float(out.get("score", float("nan")))
            scores[i] = sc
            bzs = out.get("best_zone_score")
            best_zone_scores[i] = (
                float(bzs) if bzs is not None else float("nan")
            )
            bz = out.get("best_zone_id")
            best_zone_ids.append(str(bz) if bz is not None else "")
            if bz is not None:
                zone_id_counts[str(bz)] += 1
            tops = out.get("top_scores") or []
            top_score_lens[i] = int(len(tops))
            ok = bool(out.get("passed", False))
            passed_arr[i] = 1 if ok else 0
            if not ok:
                blocked += 1
                reason_counts["blocked"] += 1
            else:
                reason_counts["passed"] += 1
        except Exception as e:
            exceptions += 1
            best_zone_ids.append("")
            reason_counts[type(e).__name__] += 1
            if first_err is None:
                first_err = f"{type(e).__name__}: {e}"

    score_stats = _stats(scores)
    best_stats = _stats(best_zone_scores)
    pass_rate = float(passed_arr.mean()) if len(passed_arr) else 0.0

    print(
        f"EXECUTED n={len(records)} mean={score_stats.get('mean')} "
        f"std={score_stats.get('std')} pass_rate={pass_rate:.4f} "
        f"blocked={blocked} exceptions={exceptions}"
    )
    print(f"best_zone_id top: {zone_id_counts.most_common(8)}")

    score_table = {
        "timestamp": timestamps,
        "zone_score": [
            None if not np.isfinite(x) else round(float(x), 6) for x in scores
        ],
        "best_zone_score": [
            None if not np.isfinite(x) else round(float(x), 6)
            for x in best_zone_scores
        ],
        "passed": [int(x) for x in passed_arr],
        "best_zone_id": best_zone_ids,
        "n_top_scores": [int(x) for x in top_score_lens],
    }
    scores_csv = OUT_DIR / f"zonegate_scores_xauusd_2m_{ts}.csv"
    pd.DataFrame(score_table).to_csv(scores_csv, index=False)

    active_version = None
    av = ROOT / "configs" / "production" / "ACTIVE_VERSION"
    if av.exists():
        active_version = av.read_text(encoding="utf-8").strip()

    manifest = {
        "run_id": f"zonegate_xauusd_2m_{ts}",
        "timestamp_utc": ts,
        "task": (
            "Run ZoneGate trained registry on XAUUSD ~2 months M15 "
            "(same window as Gaussian run); record output"
        ),
        "authority": (
            "OBSERVATION_ONLY — no promote / no config edit / no economic claim"
        ),
        "instrument": "XAUUSD",
        "timeframe": "M15",
        "active_config": active_version,
        "paired_with": "results/gaussian_xauusd_2m/gaussian_xauusd_2m_LATEST.json",
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
        "zonegate_model": {
            "kind": "trained_zone_registry",
            "active_registry_entries": registry_active,
            "artifact_path": artifact_path,
            "artifact_sha256": _sha256_file(p_art),
            "n_zones": n_zones,
            "schema_version": bundle.get("schema_version"),
            "feature_order": feature_order,
            "feature_order_dim": len(feature_order),
            "feature_alignment": feature_alignment,
            "resolver": resolver_detail,
            "retired_v3_load": v3_status,
            "pit_provenance": (
                "PIT_UNCLEAN (centered_swings + global_batch_volatility_regime "
                "training era; F-051) — v4 is alignment remap, not retrain"
            ),
            "score_path": "score_zone_cluster (production EngineRunner path)",
            "knobs": {
                "zone_mode": zone_mode,
                "zone_cluster_threshold": thr,
                "top_k": top_k,
                "cluster_min_n": cluster_min_n,
                "cluster_spread_max": cluster_spread_max,
                "zone_registry_path_config": how_path,
            },
        },
        "runtime": {
            "n_rows": len(records),
            "exceptions": exceptions,
            "first_error": first_err,
            "blocked": blocked,
            "passed": int(passed_arr.sum()),
            "pass_rate": pass_rate,
            "block_rate": blocked / max(len(records), 1),
            "reason_counts": dict(reason_counts),
            "best_zone_id_counts": dict(zone_id_counts.most_common(20)),
            "status": (
                "EXECUTED"
                if exceptions == 0
                else "EXECUTED_WITH_ERRORS"
            ),
        },
        "score_stats": score_stats,
        "best_zone_score_stats": best_stats,
        "artifacts": {
            "scores_csv": str(scores_csv).replace("\\", "/"),
        },
        "interpretation_guardrails": [
            "Descriptive stats only — NOT economic validation, NOT promote "
            "authority (§6.5).",
            "F-036: zone channel NON_PIVOTAL on crypto majors (byte-identical "
            "ledgers across weight/threshold cells).",
            "F-041B: zone labels HONEST_NO_EDGE under forward_walk; geometric "
            "gate only (labels unread at runtime).",
            "PIT_UNCLEAN provenance carried on v4 artifact — no causal "
            "revalidation performed by this run.",
            "Same 2m XAUUSD window as Gaussian run for paired observation.",
        ],
    }

    manifest_path = OUT_DIR / f"zonegate_xauusd_2m_manifest_{ts}.json"
    latest_path = OUT_DIR / "zonegate_xauusd_2m_LATEST.json"
    for path in (manifest_path, latest_path):
        manifest["artifacts"]["manifest_json"] = str(manifest_path).replace("\\", "/")
        manifest["artifacts"]["latest_json"] = str(latest_path).replace("\\", "/")
        path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    print("--- DONE ---")
    print(f"manifest: {manifest_path}")
    print(f"scores:   {scores_csv}")
    print(f"latest:   {latest_path}")
    print(json.dumps({
        "status": manifest["runtime"]["status"],
        "score_stats": score_stats,
        "pass_rate": pass_rate,
        "blocked": blocked,
        "exceptions": exceptions,
        "best_zone_id_counts": dict(zone_id_counts.most_common(8)),
        "feature_alignment_ok": feature_alignment["name_set_subset_ok"]
        and feature_alignment["no_v3_names"],
        "v3_retired": v3_status,
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
