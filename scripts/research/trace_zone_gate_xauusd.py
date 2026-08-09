# -*- coding: utf-8 -*-
"""trace_zone_gate_xauusd.py — run trained ZoneGate on XAUUSD_M15 and trace IN/OUT.

Observation-only. Mirrors the live spine scoring path:
  FeaturePipeline → filter_canonical_inputs → BitNetZoneGate.check
  → compute_weighted_cluster_score(top_k) ≥ zone_cluster_threshold

Usage:
  python scripts/research/trace_zone_gate_xauusd.py
  python scripts/research/trace_zone_gate_xauusd.py --csv data/XAUUSD_M15.csv
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bitnet.zone_cosine_searcher import compute_gaussian_score  # noqa: E402
from engines.live_engine import get_zone_gate  # noqa: E402
from engines.zone_gate_engine import (  # noqa: E402
    compute_weighted_cluster_score,
    filter_canonical_inputs,
    _extract_vector,
)
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import CANONICAL_FEATURE_ORDER, CANONICAL_FEATURE_DIM  # noqa: E402
from utils.console_safe import safe_print  # noqa: E402


def _sha16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=_ROOT / "data" / "XAUUSD_M15.csv")
    ap.add_argument("--registry", type=Path, default=_ROOT / "models" / "zone_registry.json")
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=_ROOT / "results" / "analysis" / "zone_gate_xauusd_trace",
    )
    ap.add_argument("--threshold", type=float, default=0.25)
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--cluster-min-n", type=int, default=2)
    ap.add_argument("--spread-max", type=float, default=0.15)
    ap.add_argument("--jsonl-stride", type=int, default=10, help="Write every Nth bar to scores.jsonl")
    args = ap.parse_args(argv)

    csv_path: Path = args.csv if args.csv.is_absolute() else _ROOT / args.csv
    reg_path: Path = args.registry if args.registry.is_absolute() else _ROOT / args.registry
    out_dir: Path = args.out_dir if args.out_dir.is_absolute() else _ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    thresh = float(args.threshold)
    top_k = int(args.top_k)
    cluster_min_n = int(args.cluster_min_n)
    spread_max = float(args.spread_max)

    safe_print("=== IN: data file ===")
    safe_print(f"path: {csv_path}")
    safe_print(f"bytes: {csv_path.stat().st_size}")
    safe_print(f"sha256: {_sha16(csv_path)}")

    raw = pd.read_csv(csv_path)
    raw.columns = [c.strip().lower() for c in raw.columns]
    safe_print(f"raw_rows: {len(raw)}")
    safe_print(f"raw_cols: {list(raw.columns)}")
    safe_print(f"ts_range: {raw['timestamp'].iloc[0]} -> {raw['timestamp'].iloc[-1]}")
    safe_print(
        f"price_range close: {float(raw['close'].min()):.2f} -> {float(raw['close'].max()):.2f}"
    )

    safe_print("\n=== IN: trained model ===")
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    safe_print(f"path: {reg_path}")
    safe_print(f"sha256: {_sha16(reg_path)}")
    safe_print(f"schema: {reg.get('schema_version')}")
    safe_print(f"source: {reg.get('source')}")
    safe_print(f"n_zones: {len(reg['zones'])}")
    safe_print(f"feature_order_len: {len(reg.get('feature_order', []))}")
    safe_print(f"total_weight: {sum(z.get('weight', 0) for z in reg['zones'])}")
    zero_idx = list(reg["zones"][0]["meta"].get("zero_indices", []))
    zero_names = [CANONICAL_FEATURE_ORDER[i] for i in zero_idx]
    active_names = [CANONICAL_FEATURE_ORDER[i] for i in range(CANONICAL_FEATURE_DIM) if i not in set(zero_idx)]
    safe_print(f"zeroed dims ({len(zero_names)}): {zero_names}")
    safe_print(f"active dims ({len(active_names)}): {active_names}")

    safe_print("\n=== PIPELINE: FeaturePipeline.run() ===")
    pipe = FeaturePipeline(raw)
    df, vectors = pipe.run()
    safe_print(f"enriched_rows: {len(df)}")
    safe_print(f"vectors_shape: {getattr(vectors, 'shape', None)}")
    safe_print(f"canonical_dim: {CANONICAL_FEATURE_DIM}")

    gate = get_zone_gate(str(reg_path), min_samples=50, top_n=top_k)
    safe_print("\n=== IN: BitNetZoneGate load ===")
    safe_print(f"zones_loaded: {len(gate._zones)}")
    safe_print(f"enabled: {gate.enabled}")
    safe_print(f"underpowered: {gate._underpowered}")
    safe_print(f"top_n: {gate._top_n}")

    records: list[dict] = []
    pass_n = 0
    block_n = 0
    scores: list[float] = []
    best_zone_counts: Counter = Counter()
    errors = 0
    per_zone_score_accum: dict[str, list[float]] = {
        z.get("id", f"z{i}"): [] for i, z in enumerate(gate._zones)
    }

    for i in range(len(df)):
        row = df.iloc[i]
        feats: dict[str, float] = {}
        ok = True
        for k in CANONICAL_FEATURE_ORDER:
            if k not in row.index:
                ok = False
                break
            try:
                v = float(row[k])
                if not math.isfinite(v):
                    ok = False
                    break
                feats[k] = v
            except (TypeError, ValueError):
                ok = False
                break
        if not ok:
            errors += 1
            continue

        try:
            vector = _extract_vector(filter_canonical_inputs(feats))
        except Exception:
            errors += 1
            continue

        try:
            check = gate.check(vector)
            top_scores = check.get("top_scores") or []
            if top_scores and len(top_scores) >= cluster_min_n:
                cluster = compute_weighted_cluster_score(top_scores, spread_max=spread_max)
            else:
                cluster = float(check.get("score", 0.5))

            zone_scores = []
            for z in gate._zones:
                zs = float(compute_gaussian_score(vector, z))
                zid = z.get("id", "?")
                zone_scores.append(
                    {
                        "id": zid,
                        "score": round(zs, 6),
                        "threshold": float(z.get("threshold", 0.3)),
                    }
                )
                per_zone_score_accum[zid].append(zs)

            passed = cluster >= thresh
            if passed:
                pass_n += 1
            else:
                block_n += 1
            scores.append(cluster)
            best_zone_counts[str(check.get("zone_id", "?"))] += 1

            ts = str(row["timestamp"]) if "timestamp" in row.index else str(i)
            close = float(row["close"]) if "close" in row.index else None
            records.append(
                {
                    "i": i,
                    "ts": ts,
                    "close": close,
                    "cluster_score": round(cluster, 6),
                    "passed": passed,
                    "threshold": thresh,
                    "best_zone_id": check.get("zone_id"),
                    "best_raw_score": check.get("score"),
                    "top_scores": [round(float(s), 6) for s in top_scores],
                    "zone_scores": zone_scores,
                    "input_active": {k: round(feats[k], 6) for k in active_names},
                    "input_zeroed_sample": {k: round(feats[k], 6) for k in zero_names[:5]},
                }
            )
        except Exception as e:
            errors += 1
            if errors <= 3:
                safe_print(f"score error i={i}: {e}")

    safe_print("\n=== OUT: aggregate ===")
    safe_print(f"scored_bars: {len(scores)}")
    safe_print(f"errors_skipped: {errors}")
    if scores:
        safe_print(f"pass: {pass_n} ({100 * pass_n / len(scores):.2f}%)")
        safe_print(f"block: {block_n} ({100 * block_n / len(scores):.2f}%)")
        safe_print(
            "score min/median/mean/max: "
            f"{min(scores):.4f} / {statistics.median(scores):.4f} / "
            f"{statistics.mean(scores):.4f} / {max(scores):.4f}"
        )
        arr = np.array(scores)
        for p in (5, 25, 50, 75, 95):
            safe_print(f"  p{p}: {float(np.percentile(arr, p)):.4f}")
    safe_print(f"best_zone_id histogram: {dict(best_zone_counts.most_common())}")

    safe_print("\n=== OUT: per-zone mean similarity ===")
    for zid, lst in per_zone_score_accum.items():
        if lst:
            safe_print(
                f"  {zid}: mean={statistics.mean(lst):.4f} "
                f"med={statistics.median(lst):.4f} max={max(lst):.4f} n={len(lst)}"
            )

    def pick_detail():
        if not records:
            return []
        by_score = sorted(records, key=lambda r: r["cluster_score"])
        picks = [
            ("first", records[0]),
            ("last", records[-1]),
            ("min_score", by_score[0]),
            ("max_score", by_score[-1]),
            ("medianish", records[len(records) // 2]),
        ]
        for r in reversed(records):
            if r["passed"]:
                picks.append(("recent_pass", r))
                break
        for r in reversed(records):
            if not r["passed"]:
                picks.append(("recent_block", r))
                break
        return picks

    details = pick_detail()
    safe_print("\n=== OUT: detail traces (IN -> OUT) ===")
    for label, r in details:
        safe_print(f"\n--- {label} bar i={r['i']} ts={r['ts']} close={r['close']} ---")
        safe_print(f"IN  active (25): {json.dumps(r['input_active'], separators=(',', ':'))}")
        safe_print(f"IN  zeroed sample: {json.dumps(r['input_zeroed_sample'], separators=(',', ':'))}")
        safe_print(f"MID zone_scores: {r['zone_scores']}")
        safe_print(f"MID top_scores: {r['top_scores']}")
        safe_print(
            f"OUT cluster_score={r['cluster_score']} passed={r['passed']} "
            f"(thr={r['threshold']}) best_zone={r['best_zone_id']} best_raw={r['best_raw_score']}"
        )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "instrument": "XAUUSD",
        "csv": str(csv_path).replace("\\", "/"),
        "csv_sha16": _sha16(csv_path),
        "registry": str(reg_path).replace("\\", "/"),
        "registry_sha16": _sha16(reg_path),
        "schema_version": reg.get("schema_version"),
        "source": reg.get("source"),
        "n_zones": len(reg["zones"]),
        "config": {
            "zone_cluster_threshold": thresh,
            "top_k": top_k,
            "cluster_min_n": cluster_min_n,
            "cluster_spread_max": spread_max,
            "zone_mode": "hard",
        },
        "raw_rows": int(len(raw)),
        "enriched_rows": int(len(df)),
        "scored_bars": len(scores),
        "errors_skipped": errors,
        "pass_n": pass_n,
        "block_n": block_n,
        "pass_rate": pass_n / max(1, len(scores)),
        "score_stats": {
            "min": float(min(scores)) if scores else None,
            "median": float(statistics.median(scores)) if scores else None,
            "mean": float(statistics.mean(scores)) if scores else None,
            "max": float(max(scores)) if scores else None,
            "p5": float(np.percentile(scores, 5)) if scores else None,
            "p25": float(np.percentile(scores, 25)) if scores else None,
            "p75": float(np.percentile(scores, 75)) if scores else None,
            "p95": float(np.percentile(scores, 95)) if scores else None,
        },
        "best_zone_histogram": dict(best_zone_counts),
        "per_zone_mean_score": {
            zid: (statistics.mean(lst) if lst else None)
            for zid, lst in per_zone_score_accum.items()
        },
        "zeroed_dims": zero_names,
        "active_dims": active_names,
        "note": (
            "Zone registry trained on crypto opportunity stream (BNB-scale prices in mu). "
            "XAUUSD gold prices are OOD for zeroed price dims (weight=0) but active dims still score. "
            "Stored zone meta labels unread. Observation only — no promotion authority."
        ),
    }

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    detail_out = [{"label": lab, **rec} for lab, rec in details]
    (out_dir / "detail_traces.json").write_text(json.dumps(detail_out, indent=2), encoding="utf-8")

    jsonl_path = out_dir / "scores.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for j, r in enumerate(records):
            if j % max(1, args.jsonl_stride) == 0:
                slim = {
                    "i": r["i"],
                    "ts": r["ts"],
                    "close": r["close"],
                    "cluster_score": r["cluster_score"],
                    "passed": r["passed"],
                    "best_zone_id": r["best_zone_id"],
                    "top_scores": r["top_scores"],
                }
                fh.write(json.dumps(slim) + "\n")

    safe_print("\n=== ARTIFACTS ===")
    safe_print(str(out_dir / "summary.json"))
    safe_print(str(out_dir / "detail_traces.json"))
    safe_print(str(jsonl_path))
    safe_print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
