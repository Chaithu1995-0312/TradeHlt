#!/usr/bin/env python3
"""
xauusd_gaussian_econ_units.py — Phase E0
========================================
Build journal-aligned **scored economic units** for the XAUUSD Gaussian NB.

Design: docs/implementation_plan/xauusd-gaussian-toward-economics-2026-07-23.md §E0

What this is
------------
One JSONL row per unit derived from bar_semantic.v1 journal events:
  * LABEL_ACCEPTED → split=train (was used in NB training label set)
  * HOLDOUT        → split=oos   (sweep in holdout window; excluded from train)

Each row is scored with the promoted (or CLI-selected) XAUUSD Gaussian via
name-anchored 39-dim extract. **No forward_walk economics, no M4, no config edit.**

Authority: RESEARCH_ONLY. REGISTRY_ACTIVE ≠ ECONOMIC_AUTHORITY.

Usage
-----
  python scripts/research/xauusd_gaussian_econ_units.py
  python scripts/research/xauusd_gaussian_econ_units.py \\
      --journal results/gaussian_xauusd_train/gaussian_xauusd_train_20260722T194904Z/bar_semantic_journal.jsonl \\
      --model-version xauusd_nb_20260722T194904Z
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INSTRUMENT = "XAUUSD"
DEFAULT_JOURNAL = (
    "results/gaussian_xauusd_train/"
    "gaussian_xauusd_train_20260722T194904Z/bar_semantic_journal.jsonl"
)
DEFAULT_MODEL_VERSION = "xauusd_nb_20260722T194904Z"
PHASE = "E0_SCORED_UNITS"
AUTHORITY = (
    "RESEARCH_ONLY — no M4, no ΔG001, no gaussian_impl flip; "
    "REGISTRY_ACTIVE ≠ ECONOMIC_AUTHORITY"
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def resolve_model_rel(version: str, registry_path: Path) -> tuple[str, dict]:
    """Return (path relative to models/, registry entry)."""
    reg = json.loads(registry_path.read_text(encoding="utf-8"))
    entry = reg.get(version)
    if not isinstance(entry, dict):
        # allow path-like version
        candidate = Path(version)
        if candidate.suffix == ".json":
            rel = str(candidate).replace("\\", "/")
            if rel.startswith("models/"):
                rel = rel[len("models/") :]
            return rel, {"version": version, "model_file": f"models/{rel}"}
        raise KeyError(f"Gaussian version not in registry: {version}")
    mf = str(entry.get("model_file") or "").replace("\\", "/")
    if mf.startswith("models/"):
        mf = mf[len("models/") :]
    return mf, entry


def parse_journal_units(
    journal_path: Path,
) -> tuple[list[dict], dict]:
    """Extract train (LABEL_ACCEPTED) + oos (HOLDOUT) units from bar_semantic.v1.

    Returns (units, stats). Does not score.
    """
    units: list[dict] = []
    kind_counts: Counter = Counter()
    holdout_start: Optional[str] = None
    schema_versions: Counter = Counter()

    with journal_path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            schema_versions[str(o.get("schema_version") or "?")] += 1
            kind = o.get("kind")
            if kind not in ("LABEL_ACCEPTED", "HOLDOUT"):
                continue
            kind_counts[kind] += 1

            ts = o.get("timestamp")
            direction = o.get("direction")
            if direction not in ("long", "short"):
                # HOLDOUT/SWEEP should carry direction; skip if not
                continue
            if not ts:
                continue

            payload = o.get("payload") or {}
            if kind == "HOLDOUT" and payload.get("holdout_start") and holdout_start is None:
                holdout_start = str(payload["holdout_start"])

            split = "train" if kind == "LABEL_ACCEPTED" else "oos"
            units.append(
                {
                    "journal_line": line_no,
                    "journal_kind": kind,
                    "reason_code_origin": o.get("reason_code"),
                    "narrative_seed": o.get("narrative"),
                    "bar_index_journal": o.get("bar_index"),
                    "timestamp": str(ts),
                    "direction": direction,
                    "crt_state": o.get("crt_state"),
                    "split": split,
                    # train-label payload (research only; not E1 economics yet)
                    "train_y_rr": payload.get("y_rr") if kind == "LABEL_ACCEPTED" else None,
                    "train_rr_gross": payload.get("rr_gross") if kind == "LABEL_ACCEPTED" else None,
                    "train_exit_reason": payload.get("exit_reason")
                    if kind == "LABEL_ACCEPTED"
                    else None,
                    "train_entry": payload.get("entry") if kind == "LABEL_ACCEPTED" else None,
                    "train_atr_abs": payload.get("atr_abs") if kind == "LABEL_ACCEPTED" else None,
                    "train_sl_atr_mult": payload.get("sl_atr_mult")
                    if kind == "LABEL_ACCEPTED"
                    else None,
                    "train_tp_atr_mult": payload.get("tp_atr_mult")
                    if kind == "LABEL_ACCEPTED"
                    else None,
                    "holdout_start": payload.get("holdout_start"),
                }
            )

    stats = {
        "journal_path": str(journal_path).replace("\\", "/"),
        "journal_sha256": _sha256_file(journal_path),
        "kind_counts_extracted": dict(kind_counts),
        "n_units_parsed": len(units),
        "n_train_parsed": sum(1 for u in units if u["split"] == "train"),
        "n_oos_parsed": sum(1 for u in units if u["split"] == "oos"),
        "holdout_start": holdout_start,
        "schema_versions": dict(schema_versions),
    }
    return units, stats


def build_feature_lookup(
    corpus_path: Path,
) -> tuple[pd.DataFrame, dict, dict]:
    """FeaturePipeline on corpus → timestamp→row index + meta."""
    from data_ingestion.xauusd_phase1_candidate import (
        PHASE1_SHA256,
        PHASE1_STATUS,
        guard_xauusd_csv_path,
    )
    from features.feature_pipeline import FeaturePipeline
    from features.feature_schema import (
        CANONICAL_FEATURE_DIM,
        CANONICAL_FEATURE_ORDER,
        FEATURE_ORDER_HASH,
        SCHEMA_HASH,
    )

    guarded = Path(guard_xauusd_csv_path(str(corpus_path), INSTRUMENT))
    df = pd.read_csv(guarded)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    pipe = FeaturePipeline(df)
    enriched, vectors = pipe.run()
    enr = enriched.copy()
    enr["timestamp"] = pd.to_datetime(enr["timestamp"])
    # exact timestamp map
    ts_to_i = {pd.Timestamp(t): int(i) for i, t in enumerate(enr["timestamp"])}
    # also raw bar index map for LABEL_ACCEPTED bar_index when reliable (>0)
    meta = {
        "corpus_path": str(guarded).replace("\\", "/"),
        "corpus_sha256": _sha256_file(guarded),
        "phase1_pin": PHASE1_SHA256,
        "phase1_status": PHASE1_STATUS,
        "n_raw": int(len(df)),
        "n_enriched": int(len(enr)),
        "vector_shape": list(vectors.shape),
        "canonical_dim": CANONICAL_FEATURE_DIM,
        "feature_order_hash": FEATURE_ORDER_HASH,
        "schema_hash": SCHEMA_HASH,
        "canonical_feature_order": list(CANONICAL_FEATURE_ORDER),
    }
    return enr, ts_to_i, meta


def score_units(
    units: list[dict],
    enr: pd.DataFrame,
    ts_to_i: dict,
    model_rel: str,
    feature_order: list[str],
) -> tuple[list[dict], dict]:
    """Attach NB score / expected_rr / confidence; resolve bar_index from ts."""
    from features.gaussian_schema_contract import extract_model_feature_vector
    from training.trainer import load_gaussian_model

    model, scaler, meta = load_gaussian_model(model_rel)
    resolved = list(meta.get("feature_schema_resolved") or feature_order)
    n_features = int(model.n_features)

    scored: list[dict] = []
    fails: Counter = Counter()
    scores: list[float] = []

    for u in units:
        ts = pd.Timestamp(u["timestamp"])
        enr_i = ts_to_i.get(ts)
        if enr_i is None:
            # nearest string match
            enr_i = ts_to_i.get(pd.Timestamp(str(ts)))
        if enr_i is None:
            fails["ts_not_in_features"] += 1
            continue

        row = enr.iloc[enr_i]
        try:
            feat = {k: float(row[k]) for k in feature_order if k in row.index}
            vec = extract_model_feature_vector(feat, resolved)
        except Exception as e:
            fails[f"extract:{type(e).__name__}"] += 1
            continue

        if len(vec) != n_features:
            fails["dim_mismatch"] += 1
            continue

        try:
            scaled = scaler.transform_one(vec)
            expected_rr, confidence, _probs = model.predict_expected_rr(scaled)
            sc = 1.0 / (1.0 + math.exp(-float(expected_rr)))
            sc = max(0.0, min(1.0, sc))
        except Exception as e:
            fails[f"predict:{type(e).__name__}"] += 1
            continue

        # Prefer journal bar_index when it looks real; else use enriched alignment
        bidx = u.get("bar_index_journal")
        try:
            bidx_i = int(bidx) if bidx is not None else -1
        except (TypeError, ValueError):
            bidx_i = -1
        if bidx_i <= 0:
            # resolve from raw-ish index via timestamp order in enriched
            bidx_i = int(enr_i)

        out = {
            **u,
            "bar_index": bidx_i,
            "feature_row_index": int(enr_i),
            "score": round(float(sc), 6),
            "expected_rr": round(float(expected_rr), 6),
            "confidence": round(float(confidence), 6),
            "model_n_features": n_features,
            "schema_alignment": meta.get("schema_alignment"),
            "phase": PHASE,
            "authority": AUTHORITY,
        }
        scored.append(out)
        scores.append(float(sc))

    score_stats = {}
    if scores:
        a = np.asarray(scores, dtype=float)
        score_stats = {
            "n": int(a.size),
            "mean": float(a.mean()),
            "std": float(a.std()),
            "min": float(a.min()),
            "max": float(a.max()),
            "p10": float(np.percentile(a, 10)),
            "p50": float(np.percentile(a, 50)),
            "p90": float(np.percentile(a, 90)),
        }

    runtime = {
        "n_scored": len(scored),
        "n_train_scored": sum(1 for u in scored if u["split"] == "train"),
        "n_oos_scored": sum(1 for u in scored if u["split"] == "oos"),
        "fail_counts": dict(fails),
        "model_n_features": n_features,
        "schema_alignment": meta.get("schema_alignment"),
        "feature_schema_resolved_dim": len(resolved),
        "score_stats_all": score_stats,
        "score_stats_train": _split_score_stats(scored, "train"),
        "score_stats_oos": _split_score_stats(scored, "oos"),
    }
    return scored, runtime


def _split_score_stats(scored: list[dict], split: str) -> dict:
    xs = [float(u["score"]) for u in scored if u.get("split") == split]
    if not xs:
        return {"n": 0}
    a = np.asarray(xs, dtype=float)
    return {
        "n": int(a.size),
        "mean": float(a.mean()),
        "std": float(a.std()),
        "min": float(a.min()),
        "max": float(a.max()),
        "p10": float(np.percentile(a, 10)),
        "p50": float(np.percentile(a, 50)),
        "p90": float(np.percentile(a, 90)),
    }


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="E0: XAUUSD Gaussian scored econ units")
    ap.add_argument("--journal", default=DEFAULT_JOURNAL)
    ap.add_argument("--model-version", default=DEFAULT_MODEL_VERSION)
    ap.add_argument(
        "--corpus",
        default="data/mt5/XAUUSD_M15.csv",
        help="OHLCV path (guarded to Phase-1 frozen candidate for XAUUSD)",
    )
    ap.add_argument(
        "--registry",
        default="models/gaussian_registry.json",
    )
    ap.add_argument(
        "--out-dir",
        default="results/gaussian_xauusd_econ",
    )
    ap.add_argument(
        "--expected-holdout-count",
        type=int,
        default=267,
        help="Journal HOLDOUT count pin (design E0 parity). 0 disables check.",
    )
    ap.add_argument(
        "--expected-label-accepted-count",
        type=int,
        default=2980,
        help="Journal LABEL_ACCEPTED count pin. 0 disables check.",
    )
    args = ap.parse_args(argv)

    journal_path = ROOT / args.journal
    if not journal_path.exists():
        print(f"ERROR: journal not found: {journal_path}", file=sys.stderr)
        return 2

    reg_path = ROOT / args.registry
    model_rel, reg_entry = resolve_model_rel(args.model_version, reg_path)
    model_abs = ROOT / "models" / model_rel
    if not model_abs.exists():
        print(f"ERROR: model not found: {model_abs}", file=sys.stderr)
        return 2

    print(f"[E0] journal={journal_path}")
    print(f"[E0] model_version={args.model_version} rel={model_rel}")
    print(f"[E0] authority={AUTHORITY}")

    units, parse_stats = parse_journal_units(journal_path)
    print(
        f"[E0] parsed units={parse_stats['n_units_parsed']} "
        f"train={parse_stats['n_train_parsed']} oos={parse_stats['n_oos_parsed']}"
    )

    # Parity pins vs known journal
    if args.expected_holdout_count > 0:
        n_h = parse_stats["kind_counts_extracted"].get("HOLDOUT", 0)
        if n_h != args.expected_holdout_count:
            print(
                f"ERROR: HOLDOUT count {n_h} != expected {args.expected_holdout_count}",
                file=sys.stderr,
            )
            return 3
    if args.expected_label_accepted_count > 0:
        n_a = parse_stats["kind_counts_extracted"].get("LABEL_ACCEPTED", 0)
        if n_a != args.expected_label_accepted_count:
            print(
                f"ERROR: LABEL_ACCEPTED count {n_a} != expected "
                f"{args.expected_label_accepted_count}",
                file=sys.stderr,
            )
            return 3

    print("[E0] building features on corpus (warmup)...")
    enr, ts_to_i, feat_meta = build_feature_lookup(ROOT / args.corpus)
    feature_order = list(feat_meta["canonical_feature_order"])
    if feat_meta["canonical_dim"] != 39:
        print(
            f"ERROR: expected canonical dim 39, got {feat_meta['canonical_dim']}",
            file=sys.stderr,
        )
        return 4

    print("[E0] scoring units with name-anchored Gaussian...")
    scored, runtime = score_units(units, enr, ts_to_i, model_rel, feature_order)
    print(
        f"[E0] scored={runtime['n_scored']} "
        f"train={runtime['n_train_scored']} oos={runtime['n_oos_scored']} "
        f"fails={runtime['fail_counts']}"
    )
    if runtime["model_n_features"] != 39:
        print(
            f"ERROR: model n_features {runtime['model_n_features']} != 39",
            file=sys.stderr,
        )
        return 4

    if runtime["n_scored"] == 0:
        print("ERROR: zero units scored", file=sys.stderr)
        return 5

    # Sort for determinism
    scored.sort(key=lambda u: (u["timestamp"], u["direction"], u["journal_line"]))

    ts = _utc()
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    units_path = out_dir / f"units_{ts}.jsonl"
    latest_units = out_dir / "units_LATEST.jsonl"
    with units_path.open("w", encoding="utf-8") as f:
        for u in scored:
            f.write(json.dumps(u, default=str) + "\n")
    latest_units.write_text(units_path.read_text(encoding="utf-8"), encoding="utf-8")

    # registry active check (informational)
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    active_xau = (reg.get("__active__") or {}).get("XAUUSD")
    entry_active = bool(reg_entry.get("active")) if isinstance(reg_entry, dict) else False

    manifest = {
        "phase": PHASE,
        "run_id": f"xauusd_gaussian_econ_units_{ts}",
        "timestamp_utc": ts,
        "authority": AUTHORITY,
        "instrument": INSTRUMENT,
        "design_doc": (
            "docs/implementation_plan/xauusd-gaussian-toward-economics-2026-07-23.md"
        ),
        "inputs": {
            "journal": parse_stats,
            "model_version": args.model_version,
            "model_rel": model_rel,
            "model_sha256": _sha256_file(model_abs),
            "model_registry_active_XAUUSD": active_xau,
            "model_entry_active": entry_active,
            "registry_promoted_matches_version": active_xau == args.model_version,
            "corpus": feat_meta,
        },
        "runtime": runtime,
        "outputs": {
            "units_jsonl": str(units_path).replace("\\", "/"),
            "units_latest": str(latest_units).replace("\\", "/"),
            "units_sha256": _sha256_file(units_path),
            "n_units": len(scored),
        },
        "parity_pins": {
            "expected_holdout_count": args.expected_holdout_count,
            "expected_label_accepted_count": args.expected_label_accepted_count,
            "holdout_count_ok": (
                args.expected_holdout_count == 0
                or parse_stats["kind_counts_extracted"].get("HOLDOUT")
                == args.expected_holdout_count
            ),
            "label_accepted_count_ok": (
                args.expected_label_accepted_count == 0
                or parse_stats["kind_counts_extracted"].get("LABEL_ACCEPTED")
                == args.expected_label_accepted_count
            ),
            "feature_dim_is_39": feat_meta["canonical_dim"] == 39,
            "model_n_features_is_39": runtime["model_n_features"] == 39,
        },
        "not_in_scope": [
            "forward_walk economics / NET R arms (E1)",
            "M4 QualificationGate (E2)",
            "gaussian_impl config change (E3)",
            "ΔG001 / economic authority",
        ],
        "next_phase": "E1 — economic ledger on these units (pre-registered arms)",
    }

    man_path = out_dir / f"e0_manifest_{ts}.json"
    latest_man = out_dir / "e0_manifest_LATEST.json"
    for p in (man_path, latest_man):
        p.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    print("--- E0 DONE ---")
    print(f"units:    {units_path}")
    print(f"manifest: {man_path}")
    print(f"n_train={runtime['n_train_scored']} n_oos={runtime['n_oos_scored']}")
    print(f"score_stats_all={runtime['score_stats_all']}")
    print(f"promoted_pointer_match={manifest['inputs']['registry_promoted_matches_version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
