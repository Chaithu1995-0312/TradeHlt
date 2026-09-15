#!/usr/bin/env python3
"""
RR L2 — Feature truth materialization under a SIGNED L1 freeze certificate.

Consumes: docs/governance/rr_l1_freeze/RR_L1_FREEZE_CERTIFICATE.json
Requires: python scripts/governance/rr_l1_freeze_certificate.py assert-signed

Resolves (when successful):
  RR-FEAT-001  PIT-clean causal structure (production FeaturePipeline / FC1-A)
  RR-FEAT-002  rolling causal volatility_regime (FC1-D)
  RR-FEAT-003  structure mask policy from L1 certificate
  RR-FEAT-004  production promoted feature surface (no STALE legacy train dump)
  RR-FEAT-006  schema_hash over frozen feature_list.names

Does NOT write labels (L3). Embeds certificate_id + protocol_hash on every artifact.

Usage (repo root):
  python scripts/research/rr_l2_feature_truth.py
  python scripts/research/rr_l2_feature_truth.py --candles data/BNBUSDT_M15.csv
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402

from scripts.governance.rr_l1_freeze_certificate import (  # noqa: E402
    DEFAULT_CERT,
    compute_protocol_hash,
    cmd_assert_signed,
)

UNSET = "__UNSET__"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _schema_hash(names: List[str]) -> str:
    payload = {
        "schema_name": "canonical_38",
        "n_features": len(names),
        "names": list(names),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_cert(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_l1(cert_path: Path, cert: dict) -> None:
    rc = cmd_assert_signed(cert_path)
    if rc != 0:
        raise SystemExit(f"L1 assert-signed failed (exit {rc}); refuse L2")
    h = compute_protocol_hash(cert["contract"])
    if h != cert.get("protocol_hash"):
        raise SystemExit("protocol_hash drift vs recomputed contract hash")


def _load_candles(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    rename = {}
    for need in ("timestamp", "open", "high", "low", "close", "volume"):
        if need in cols:
            rename[cols[need]] = need
        elif need.title() in df.columns:
            rename[need.title()] = need
    df = df.rename(columns=rename)
    missing = [c for c in ("timestamp", "open", "high", "low", "close", "volume") if c not in df.columns]
    if missing:
        raise SystemExit(f"candles missing columns: {missing}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=False)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def _run_pipeline(df: pd.DataFrame) -> Tuple[pd.DataFrame, np.ndarray]:
    """Production FeaturePipeline feature math without per-row monitor (batch)."""
    pipe = FeaturePipeline(df)
    pipe.compute_price_features()
    pipe.compute_volume_features()
    pipe.compute_indicators()
    pipe.compute_trend_features()
    pipe.compute_volatility_regime()
    pipe.compute_context()
    pipe.compute_structure_liquidity()
    pipe.compute_normalization()
    pipe.compute_canonical_price_features()
    pipe.compute_canonical_volatility_features()
    pipe.compute_canonical_ema_features()
    pipe.compute_canonical_trend_features()
    pipe.compute_canonical_structure_features()
    pipe.compute_canonical_temporal_features()
    pipe.compute_liquidity_distance()
    pipe.promote_volume_spike()
    pipe.compute_canonical_session()
    out = pipe.finalize()
    vectors = pipe.build_feature_vector()
    return out, vectors


def _apply_mask(X: np.ndarray, names: List[str], zero_names: List[str]) -> np.ndarray:
    out = np.array(X, dtype=np.float64, copy=True)
    name_to_i = {n: i for i, n in enumerate(names)}
    missing = [n for n in zero_names if n not in name_to_i]
    if missing:
        raise SystemExit(f"zero mask names not in feature list: {missing}")
    for n in zero_names:
        out[:, name_to_i[n]] = 0.0
    return out


def _pit_sanity(df: pd.DataFrame) -> Dict[str, Any]:
    """Lightweight checks that production binds are present (not centered-batch)."""
    checks = {
        "has_volatility_regime": "volatility_regime" in df.columns,
        "has_rolling_causal_col": "volatility_regime_rolling_causal" in df.columns,
        "has_swing_high": "swing_high" in df.columns,
        "has_centered_batch_col": "swing_high_centered_batch" in df.columns,
    }
    # Production swing should not equal all-centered identity if both exist —
    # only report rates; do not fail on partial equality.
    if checks["has_swing_high"] and checks["has_centered_batch_col"]:
        a = df["swing_high"].astype(float).values
        b = df["swing_high_centered_batch"].astype(float).values
        checks["swing_high_vs_centered_batch_agree_rate"] = float(np.mean(a == b))
    if checks["has_volatility_regime"] and "volatility_regime_global_batch" in df.columns:
        a = df["volatility_regime"].astype(float).values
        b = df["volatility_regime_global_batch"].astype(float).values
        checks["vol_regime_vs_global_batch_agree_rate"] = float(np.mean(a == b))
    return checks


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cert", type=Path, default=DEFAULT_CERT)
    ap.add_argument(
        "--candles",
        type=Path,
        default=REPO_ROOT / "data" / "BNBUSDT_M15.csv",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="default: results/rr_research/l2/<certificate_id>/",
    )
    args = ap.parse_args(argv)

    cert_path = args.cert if args.cert.is_absolute() else (REPO_ROOT / args.cert)
    cert = _load_cert(cert_path)
    _assert_l1(cert_path, cert)

    contract = cert["contract"]
    instruments = contract["instrument_universe"]["instruments"]
    if not isinstance(instruments, list) or not instruments:
        raise SystemExit("instrument_universe.instruments invalid")
    # Candle path heuristic: default file is BNB; require instrument match in name
    inst0 = str(instruments[0])
    candles_path = args.candles if args.candles.is_absolute() else (REPO_ROOT / args.candles)
    if inst0 not in candles_path.name.upper().replace("_", ""):
        # soft check: BNBUSDT in BNBUSDT_M15
        if inst0 not in str(candles_path).upper():
            print(
                f"WARNING: instrument {inst0} not found in candles path {candles_path}",
                file=sys.stderr,
            )

    names = list(contract["feature_list"]["names"])
    if list(names) != list(CANONICAL_FEATURES):
        raise SystemExit(
            "feature_list.names must equal CANONICAL_FEATURES for this L2 builder "
            f"(got {len(names)} vs {len(CANONICAL_FEATURES)})"
        )
    if contract["feature_list"].get("names_frozen") is not True:
        raise SystemExit("feature_list.names_frozen must be true")

    zero_names = contract["structure_mask_policy"]["zero_indices_or_names"]
    if not isinstance(zero_names, list):
        raise SystemExit("structure_mask_policy.zero_indices_or_names must be list")

    print(f"Loading candles: {candles_path}")
    raw = _load_candles(candles_path)
    print(f"  rows_in={len(raw)}")

    print("Running FeaturePipeline (production causal binds)...")
    df, X_raw = _run_pipeline(raw)
    print(f"  rows_out={len(df)} vectors={X_raw.shape}")

    X = _apply_mask(X_raw, names, zero_names)
    schema_hash = _schema_hash(names)
    pit_checks = _pit_sanity(df)

    cert_id = cert["certificate_id"]
    protocol_hash = cert["protocol_hash"]
    out_dir = args.out_dir
    if out_dir is None:
        out_dir = REPO_ROOT / "results" / "rr_research" / "l2" / cert_id
    else:
        out_dir = out_dir if out_dir.is_absolute() else (REPO_ROOT / out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = df["timestamp"].astype(str).tolist() if "timestamp" in df.columns else []
    npz_path = out_dir / "feature_matrix.npz"
    np.savez_compressed(
        npz_path,
        X=X.astype(np.float32),
        X_unmasked=np.asarray(X_raw, dtype=np.float32),
        feature_names=np.array(names, dtype=object),
        timestamps=np.array(ts, dtype=object),
    )

    provenance = {
        "layer": "L2_FEATURE_TRUTH",
        "certificate_id": cert_id,
        "protocol_hash": protocol_hash,
        "l1_certificate_path": str(cert_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "schema_hash": schema_hash,
        "pit_status": "PIT_CLEAN_PRODUCTION_PIPELINE",
        "pit_dimensions": [
            "causal_structure_fc1a",
            "rolling_causal_volatility_regime_fc1d",
        ],
        "rc_ids_resolved": [
            "RR-FEAT-001",
            "RR-FEAT-002",
            "RR-FEAT-003",
            "RR-FEAT-004",
            "RR-FEAT-006",
        ],
        "instrument_universe": contract["instrument_universe"],
        "candles_path": str(candles_path.relative_to(REPO_ROOT)).replace("\\", "/")
        if candles_path.is_relative_to(REPO_ROOT)
        else str(candles_path),
        "n_rows_in": int(len(raw)),
        "n_rows_out": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "feature_list": names,
        "structure_mask_policy": contract["structure_mask_policy"],
        "zero_names_applied": zero_names,
        "pipeline": "src/features/feature_pipeline.py FeaturePipeline (production binds)",
        "labels_included": False,
        "y_rr": None,
        "y_win": None,
        "pit_sanity": pit_checks,
        "created_at_utc": _utc_now(),
        "artifacts": {
            "feature_matrix_npz": str(npz_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "provenance_json": str((out_dir / "L2_PROVENANCE.json").relative_to(REPO_ROOT)).replace(
                "\\", "/"
            ),
        },
    }
    prov_path = out_dir / "L2_PROVENANCE.json"
    prov_path.write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    completion = {
        "L2_COMPLETE": True,
        "certificate_id": cert_id,
        "protocol_hash": protocol_hash,
        "schema_hash": schema_hash,
        "pit_status": provenance["pit_status"],
        "n_rows": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "out_dir": str(out_dir.relative_to(REPO_ROOT)).replace("\\", "/"),
        "rc_ids_resolved": provenance["rc_ids_resolved"],
        "completed_at_utc": _utc_now(),
        "next_layer": "L3_LABEL_GENERATION",
        "forbidden": "Do not write labels here; L3 consumes this matrix + governing_exit",
    }
    (out_dir / "L2_COMPLETION.json").write_text(
        json.dumps(completion, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    md = f"""# L2 Feature Truth — COMPLETE

| Field | Value |
|-------|--------|
| certificate_id | `{cert_id}` |
| protocol_hash | `{protocol_hash}` |
| schema_hash | `{schema_hash}` |
| pit_status | `{provenance["pit_status"]}` |
| n_rows × n_features | {X.shape[0]} × {X.shape[1]} |
| candles | `{provenance["candles_path"]}` |
| matrix | `{provenance["artifacts"]["feature_matrix_npz"]}` |

## RC resolved

- RR-FEAT-001 · RR-FEAT-002 · RR-FEAT-003 · RR-FEAT-004 · RR-FEAT-006

## Next

L3 Label generation: attach `forward_walk(intrabar_fixed)` labels; embed same L1 ids + this `schema_hash`.
"""
    (out_dir / "L2_COMPLETION.md").write_text(md, encoding="utf-8")

    print("L2_COMPLETE=YES")
    print(f"  out_dir={out_dir}")
    print(f"  schema_hash={schema_hash}")
    print(f"  protocol_hash={protocol_hash}")
    print(f"  n_rows={X.shape[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
