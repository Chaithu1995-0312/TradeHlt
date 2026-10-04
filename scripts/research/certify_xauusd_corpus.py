#!/usr/bin/env python
"""certify_xauusd_corpus.py — offline certification of the canonical XAUUSD M15 corpus (ERP T1).

Certifies the ONLY governance-approved XAUUSD M15 load target — the Phase-1 frozen candidate
`data/mt5/XAUUSD_M15.csv` (sha256 4d73f5ce…, 47,275 rows, 2024-05-22 → 2026-05-21) — via the existing
corpus-authority machinery, and stamps a provenance `run_manifest`. It changes NOTHING: the corpus
stays FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION (NOT authoritative / validated / economically
admissible). A WARN/REJECT integrity decision is a RECORDED, honest outcome — not a script failure.

Reuses:
  guard_xauusd_csv_path / verify_phase1_frozen_candidate / authority_status_note  (single load authority)
  dataset_integrity.validate_dataset                                              (L2 integrity gate)
  ohlcv_schema.require_ohlcv_columns / validate_ohlcv_frame                        (schema contract)
  utils.run_manifest                                                              (T0 provenance)

Usage:
  python scripts/research/certify_xauusd_corpus.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

import pandas as pd  # noqa: E402

from data_ingestion.dataset_integrity import validate_dataset  # noqa: E402
from data_ingestion.ohlcv_schema import (  # noqa: E402
    require_ohlcv_columns,
    validate_ohlcv_frame,
)
from data_ingestion.xauusd_phase1_candidate import (  # noqa: E402
    PHASE1_STATUS,
    Phase1CandidateError,
    authority_status_note,
    guard_xauusd_csv_path,
    verify_phase1_frozen_candidate,
)
from utils.run_manifest import build_manifest, write_run  # noqa: E402

RUNS_DIR = _ROOT / "results" / "test_runs"


def certify() -> dict:
    """Run the full certification and return the assertions dict (raises only on drift/corruption)."""
    # 1. Single load authority — rewrites any XAUUSD M15 request to the frozen candidate + verifies.
    guarded = guard_xauusd_csv_path("data/XAUUSD_M15.csv", "XAUUSD")
    verify = verify_phase1_frozen_candidate()  # fail-closed sha256/rows/range/status; raises on drift

    # 2. L2 dataset-integrity gate (record decision; do NOT hard-fail on WARN/REJECT).
    integrity = validate_dataset(guarded, instrument="XAUUSD", raise_on_fail=False)

    # 3. Schema contract + strict monotonic UTC timestamps.
    df = pd.read_csv(guarded)
    require_ohlcv_columns(df.columns)
    validate_ohlcv_frame(df)
    ts = pd.to_datetime(df["timestamp"], utc=False)
    monotonic = bool(ts.is_monotonic_increasing and ts.is_unique)

    return {
        "corpus_path": verify["physical_path"],
        "corpus_sha256": verify["content_hash_sha256"],
        "rows": verify["rows"],
        "range": [verify["first_timestamp"], verify["last_timestamp"]],
        "phase1_status": PHASE1_STATUS,
        "authority_labels_forbidden": verify["authority_labels_forbidden"],
        "integrity_decision": integrity.get("decision"),
        "integrity_hard_failures": integrity.get("hard_failures", []),
        "schema_ok": True,
        "timestamps_monotonic_unique": monotonic,
        "authority_note": authority_status_note(),
        "non_promotable": True,
    }


def main() -> int:
    try:
        assertions = certify()
    except Phase1CandidateError as exc:
        print(f"CERTIFY_FAIL (frozen-candidate drift): {exc}")
        return 1

    manifest = build_manifest(
        command="python scripts/research/certify_xauusd_corpus.py",
        argv=sys.argv,
        validation_lens="dataset_certification",
        exit_model="none",
        cost_model_bps=0,
        label_source="frozen_corpus",
        instruments=["XAUUSD"],
        timeframe="M15",
        data_source="local_csv_mt5",
        network="none",
        dry_run=True,
        intended_work_item_id="WI-004",
    )
    run_dir = RUNS_DIR / manifest["run_id"]
    written = write_run(run_dir, manifest, assertions)

    print(f"XAUUSD corpus certified: {assertions['corpus_path']}")
    print(f"  sha256={assertions['corpus_sha256'][:16]}… rows={assertions['rows']} "
          f"range={assertions['range'][0]}..{assertions['range'][1]}")
    print(f"  integrity_decision={assertions['integrity_decision']} "
          f"monotonic={assertions['timestamps_monotonic_unique']} status={assertions['phase1_status']}")
    print(f"  manifest={written['sha256'][:16]}… -> {run_dir}")
    print("  NOT AUTHORITATIVE / VALIDATED / APPROVED / ECONOMICALLY_ADMISSIBLE (frozen candidate)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
