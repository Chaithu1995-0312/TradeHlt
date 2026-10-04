#!/usr/bin/env python3
"""Deterministic legacy FeaturePipeline fingerprint on frozen XAUUSD Phase-1 candidate.

  python scripts/analysis/legacy_feature_fingerprint.py
  python scripts/analysis/legacy_feature_fingerprint.py --check

Does not modify production feature code. Env TRUST_SWING_CAUSAL / TRUST_VOLREGIME_CAUSAL cleared.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from data_ingestion.xauusd_phase1_candidate import (  # noqa: E402
    PHASE1_PHYSICAL_PATH,
    PHASE1_ROWS,
    PHASE1_SHA256,
    PHASE1_STATUS,
    require_phase1_frozen_candidate,
)
from features.feature_pipeline import FeaturePipeline, SWING_WINDOW  # noqa: E402
from features.feature_schema import (  # noqa: E402
    CANONICAL_FEATURES,
    FEATURE_ORDER_HASH,
    SCHEMA_HASH,
)

OUT = ROOT / "docs" / "governance" / "legacy_feature_output_fingerprint_xauusd-2026-07-10.json"


def _file_sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def build_fingerprint() -> dict:
    require_phase1_frozen_candidate(repo_root=ROOT)
    for k in ("TRUST_SWING_CAUSAL", "TRUST_VOLREGIME_CAUSAL"):
        os.environ.pop(k, None)

    path = ROOT / PHASE1_PHYSICAL_PATH
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    pipe = FeaturePipeline(df)
    enriched, vectors = pipe.run()
    mat = enriched[list(CANONICAL_FEATURES)].astype(np.float32).to_numpy()
    joint = hashlib.sha256(mat.tobytes(order="C")).hexdigest()
    col_hashes = {
        name: hashlib.sha256(mat[:, i].tobytes(order="C")).hexdigest()
        for i, name in enumerate(CANONICAL_FEATURES)
    }
    ts = pd.to_datetime(enriched["timestamp"])
    impl_paths = [
        "src/features/feature_pipeline.py",
        "src/features/candle_math.py",
        "src/features/derived_math.py",
        "src/features/feature_schema.py",
        "configs/formulas/market_ontology.yaml",
    ]
    impl = {
        p: {"sha256": _file_sha(ROOT / p), "size_bytes": (ROOT / p).stat().st_size}
        for p in impl_paths
    }
    return {
        "_doc": "LEGACY feature-output fingerprint on frozen XAUUSD. Not VALIDATED/APPROVED.",
        "fingerprint_id": "LEGACY_FEATURE_OUTPUT_FP_XAUUSD_2026_07_10",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corpus": {
            "path": PHASE1_PHYSICAL_PATH.as_posix(),
            "sha256": PHASE1_SHA256,
            "rows_input": PHASE1_ROWS,
            "status": PHASE1_STATUS,
        },
        "pipeline": {
            "class": "FeaturePipeline.run",
            "env_flags_at_run": {
                "TRUST_SWING_CAUSAL": "",
                "TRUST_VOLREGIME_CAUSAL": "",
            },
            "swing_window": SWING_WINDOW,
        },
        "output": {
            "rows_after_finalize": int(len(enriched)),
            "vector_rows": int(len(vectors)),
            "first_timestamp": str(ts.iloc[0]),
            "last_timestamp": str(ts.iloc[-1]),
            "feature_order": list(CANONICAL_FEATURES),
            "n_features": len(CANONICAL_FEATURES),
            "joint_float32_sha256": joint,
            "per_column_float32_sha256": col_hashes,
        },
        "implementation_hashes": impl,
        "schema_hash_md5": SCHEMA_HASH,
        "feature_order_hash": FEATURE_ORDER_HASH,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="Compare to stored fingerprint")
    ap.add_argument("--write", action="store_true", help="Write/overwrite fingerprint file")
    args = ap.parse_args()
    fp = build_fingerprint()
    if args.check:
        if not OUT.is_file():
            print(f"missing {OUT}")
            return 1
        stored = json.loads(OUT.read_text(encoding="utf-8"))
        keys = [
            "joint_float32_sha256",
            "rows_after_finalize",
            "n_features",
            "feature_order",
            "per_column_float32_sha256",
        ]
        ok = True
        for k in keys:
            a = fp["output"][k] if k != "joint_float32_sha256" else fp["output"]["joint_float32_sha256"]
            if k == "joint_float32_sha256":
                a = fp["output"]["joint_float32_sha256"]
                b = stored["output"]["joint_float32_sha256"]
            else:
                a = fp["output"][k]
                b = stored["output"][k]
            if a != b:
                print(f"MISMATCH {k}")
                ok = False
        if fp["output"]["joint_float32_sha256"] != stored["output"]["joint_float32_sha256"]:
            ok = False
        print("CHECK", "PASS" if ok else "FAIL", fp["output"]["joint_float32_sha256"][:16])
        return 0 if ok else 1
    if args.write or not OUT.is_file():
        OUT.write_text(json.dumps(fp, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {OUT}")
    print(fp["output"]["joint_float32_sha256"], fp["output"]["rows_after_finalize"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
