"""
build_rr_dataset_from_clean_labels.py
=====================================
Adapter: TN_ENV_CLEAN_L2 clean-label rows -> rr_dataset.json payload shape.

WHY THIS EXISTS
---------------
The default RR dataset path (scripts/data/build_rr_dataset.py ->
config_layer.rr.rr_dataset_builder.extract_target) reads the raw
`outcome` / `rr_achieved` fields straight off opportunities.jsonl. That stream is
the F-022 detection stream, only ~36.8% self-consistent (SL_HIT recorded on paths
that never touch the stop). F-045 registered the RR kill-test as INDETERMINATE
*because* its labels came from there, and F-041B showed those labels flip once
re-derived through forward_walk.

This adapter instead consumes `results/clean_labels/{instrument}/<run>/clean_labels.jsonl`,
whose y-fields are derived by research.measurement.forward_walk(exit_model=intrabar_fixed)
with cost applied (see src/research/clean_labels/builder.py). Stream fields never
become primary y.

RESHAPE ONLY — no new label logic:
    X      <- feature_vector      (38-dim; macd_hist_raw deferred, see below)
    y_rr   <- y_R_net             (net R after cost, forward_walk-derived)
    y_win  <- y_tp1               (path reached unit TP1)

FEATURE WIDTH (38, not the live 39)
-----------------------------------
Schema v4.0 (2026-07-22) split `macd_hist` into `macd_hist_raw` (new, index 18) +
`macd_hist_z` (the pre-existing value, index 19), taking CANONICAL_FEATURE_DIM to 39.
`macd_hist_raw` is deferred as a future feature pending separate research validation,
so the clean-label builder already emits the legacy 38-dim layout. Dropping index 18
reproduces the v3.0 layout EXACTLY — which is the layout
scripts/training/train_rr_model.py `_PRICE_FEATURE_INDICES` already assumes
(body_size=26, candle_range=27). Training RR at 39 would silently point those
--zero-price-features indices at lower_low/body_size instead.

This script does NOT modify config_layer/rr/rr_dataset_builder.py — that module is
shared production code on the train_pipeline Gaussian path and stays at the live
39-dim contract. Read the emitted file with
`train_rr_model.py --legacy-38-dim`, which validates rows against the file's own
stored n_features.

Research artifact only: writes a dataset, registers nothing, promotes nothing.

Usage
-----
    python scripts/research/build_rr_dataset_from_clean_labels.py \\
        --instrument XAUUSD --run-id xauusd_phase1_20260723
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config_layer.rr.rr_dataset_builder import validate_dataset_integrity  # noqa: E402
from research.clean_labels.builder import (  # noqa: E402
    LEGACY_FEATURE_DIM,
    LEGACY_FEATURE_NAMES,
)
from research.clean_labels.protocol import PROTOCOL_ID  # noqa: E402

# Fingerprint over the 38 legacy names, so the emitted file is self-describing.
# Deliberately NOT features.feature_schema.SCHEMA_HASH (which covers all 39 names).
LEGACY_SCHEMA_HASH: str = hashlib.md5("".join(LEGACY_FEATURE_NAMES).encode()).hexdigest()


def _resolve_clean_labels(instrument: str, explicit: str | None) -> Path:
    """Explicit path wins; otherwise follow the instrument's LATEST pointer."""
    if explicit:
        p = Path(explicit)
        return p if p.is_absolute() else ROOT / p

    pointer = ROOT / "results" / "clean_labels" / instrument / "LATEST" / "pointer.json"
    if not pointer.is_file():
        raise SystemExit(
            f"No clean-labels LATEST pointer at {pointer}. "
            f"Run scripts/research/build_clean_labels_tn_env.py --instrument {instrument} first."
        )
    payload = json.loads(pointer.read_text(encoding="utf-8"))
    return Path(payload["paths"]["dataset"])


def _iter_rows(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def build(rows_iter, instrument: str) -> tuple[list, list, list, dict]:
    """Reshape clean-label rows into (X, y_rr, y_win, skip_counts)."""
    X: list[list[float]] = []
    y_rr: list[float] = []
    y_win: list[int] = []
    skips = {
        "wrong_instrument": 0,
        "bad_vector_width": 0,
        "missing_y_R_net": 0,
        "missing_y_tp1": 0,
        "non_finite": 0,
    }

    for r in rows_iter:
        if r.get("instrument") and r["instrument"] != instrument:
            skips["wrong_instrument"] += 1
            continue

        vec = r.get("feature_vector")
        if not isinstance(vec, list) or len(vec) != LEGACY_FEATURE_DIM:
            skips["bad_vector_width"] += 1
            continue

        rr = r.get("y_R_net")
        if rr is None:
            skips["missing_y_R_net"] += 1
            continue

        win = r.get("y_tp1")
        if win is None:
            skips["missing_y_tp1"] += 1
            continue

        try:
            fvec = [float(v) for v in vec]
            frr = float(rr)
            fwin = int(float(win) > 0.5)
        except (TypeError, ValueError):
            skips["non_finite"] += 1
            continue

        if not all(v == v and v not in (float("inf"), float("-inf")) for v in fvec):
            skips["non_finite"] += 1
            continue
        if frr != frr:
            skips["non_finite"] += 1
            continue

        X.append(fvec)
        y_rr.append(frr)
        y_win.append(fwin)

    return X, y_rr, y_win, skips


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--run-id", "--run", dest="run_id", required=True,
                    help="Run ID scoping the output path: models/{instrument}/{run_id}/")
    ap.add_argument("--clean-labels", default=None,
                    help="Explicit clean_labels.jsonl path (default: instrument LATEST pointer)")
    ap.add_argument("--output", default=None,
                    help="Explicit output path (default: models/{instrument}/{run_id}/rr_dataset.json)")
    args = ap.parse_args(argv)

    src_path = _resolve_clean_labels(args.instrument, args.clean_labels)
    if not src_path.is_file():
        raise SystemExit(f"clean labels not found: {src_path}")

    out_path = (
        Path(args.output)
        if args.output
        else ROOT / "models" / args.instrument / args.run_id / "rr_dataset.json"
    )
    if not out_path.is_absolute():
        out_path = ROOT / out_path

    print(f"[rr-adapter] protocol={PROTOCOL_ID} dim={LEGACY_FEATURE_DIM}")
    print(f"[rr-adapter] source={src_path}")

    X, y_rr, y_win, skips = build(_iter_rows(src_path), args.instrument)
    print(f"[rr-adapter] usable={len(X)} skips={skips}")

    # Reuse the shared, width-agnostic degeneracy gate (empty / all-zero RR /
    # single-class labels). It does not width-check, so it is safe at 38.
    validate_dataset_integrity(X, y_rr, y_win)

    payload = {
        "n_samples": len(X),
        "n_features": LEGACY_FEATURE_DIM,
        "feature_names": list(LEGACY_FEATURE_NAMES),
        "schema_hash": LEGACY_SCHEMA_HASH,
        "X": X,
        "y_rr": y_rr,
        "y_win": y_win,
        "provenance": {
            "builder": "scripts/research/build_rr_dataset_from_clean_labels.py",
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "instrument": args.instrument,
            "run_id": args.run_id,
            "source_dataset": str(src_path),
            "label_protocol": PROTOCOL_ID,
            "label_authority": "forward_walk(intrabar_fixed) + cost — NOT the F-022 stream",
            "y_rr_field": "y_R_net",
            "y_win_field": "y_tp1",
            "excluded_features": ["macd_hist_raw"],
            "skips": skips,
            "authority": "RESEARCH_ONLY — no promote, no production wire",
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    pos = sum(y_win)
    print(f"[rr-adapter] win balance: {pos} pos / {len(y_win) - pos} neg")
    print(f"[rr-adapter] y_rr range: {min(y_rr):.4f} .. {max(y_rr):.4f}")
    print(f"[rr-adapter] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
