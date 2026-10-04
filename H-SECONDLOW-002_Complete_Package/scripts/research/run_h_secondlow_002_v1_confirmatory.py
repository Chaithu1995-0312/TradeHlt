#!/usr/bin/env python3
"""
H-SECONDLOW-002 v1.0 — ARCHIVED contract audit on canonical MT5 corpus.

H-SECONDLOW-002 was mined on the xlsx regression fixture. Under CORPUS_POLICY.md it is
not promotable from MT5 results. This script prints an MT5 audit for provenance only.
New hypotheses require fresh pre-registration on data/XAUUSD_M15.csv.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from research.secondlow_v1.corpus import CANONICAL_XAUUSD_M15
from research.secondlow_v1.detector import (
    DISCOVERY_END,
    DISCOVERY_START,
    classify_exposure,
    detect_independent_events,
    load_ohlcv,
    partition_event_times,
    sha256_prefix,
)

CONTRACT_ID = "H-SECONDLOW-002"
CONTRACT_VERSION = "v1.0"
CONTRACT_STATUS = "ARCHIVED — xlsx discovery only; MT5 audit is non-promotable"


def main() -> None:
    parser = argparse.ArgumentParser(description="Archived H-SECONDLOW-002 MT5 audit (non-promotable)")
    parser.add_argument(
        "--csv",
        type=Path,
        default=_REPO_ROOT / CANONICAL_XAUUSD_M15,
        help="Canonical MT5 XAUUSD M15 CSV",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_REPO_ROOT / "H-SECONDLOW-002_Complete_Package/results/mt5_audit",
        help="Optional CSV output directory",
    )
    args = parser.parse_args()
    corpus = args.csv.resolve()

    print("=" * 90)
    print(f"{CONTRACT_ID} {CONTRACT_VERSION} — MT5 CORPUS AUDIT (NON-PROMOTABLE)")
    print("=" * 90)
    print(f"contract_status: {CONTRACT_STATUS}")

    df = load_ohlcv(corpus)
    source_sha256 = sha256_prefix(corpus)
    print(f"\nSource: {corpus}")
    print(f"Source SHA256 prefix: {source_sha256}")
    print(f"Source rows: {len(df)}")
    print(f"Source period: {df.index[0]} -> {df.index[-1]}")

    raw_mask, events = detect_independent_events(df, require_post_window=True)
    all_times = [e.purge_time for e in events]
    parts = partition_event_times(all_times)

    confirmatory = [e for e in events if e.purge_time < DISCOVERY_START]
    discovery_n = len(parts["discovery"])

    print(f"\nDiscovery exclusion (event-level): {DISCOVERY_START.date()} -> {DISCOVERY_END.date()}")
    print(f"INDEPENDENT events (full corpus, valid 8-bar window): {len(events)}")
    print(f"INDEPENDENT events (confirmatory / PRE): {len(confirmatory)}")
    print(f"INDEPENDENT events (discovery, excluded): {discovery_n}")

    groups = {"EXPOSED": 0, "PARTIAL": 0, "BASELINE": 0}
    rows = []
    for e in confirmatory:
        group = classify_exposure(e.pre_2h_return_atr, e.purge_depth_atr)
        groups[group] += 1
        rows.append(
            {
                "purge_time": e.purge_time,
                "pre_2h_return_atr": e.pre_2h_return_atr,
                "purge_depth_atr": e.purge_depth_atr,
                "close_disp_atr": e.close_disp_atr,
                "group": group,
            }
        )

    exposed_n, partial_n, baseline_n = groups["EXPOSED"], groups["PARTIAL"], groups["BASELINE"]
    print(f"\nConfirmatory classification (frozen -2.0 / 1.5):")
    print(f"  EXPOSED:  {exposed_n}")
    print(f"  PARTIAL:  {partial_n}")
    print(f"  BASELINE: {baseline_n}")

    if exposed_n > 0 and baseline_n > 0:
        exposed_med = np.median([r["close_disp_atr"] for r in rows if r["group"] == "EXPOSED"])
        baseline_med = np.median([r["close_disp_atr"] for r in rows if r["group"] == "BASELINE"])
        print(f"\nPRIMARY_EFFECT (informational only): {exposed_med - baseline_med:.4f}")

    if exposed_n < 30 or baseline_n < 30:
        decision = "INSUFFICIENT"
    else:
        decision = "SAMPLE_GATE_PASSED — still non-promotable without new pre-registration"
    print(f"DECISION (archived contract): {decision}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.output_dir / "mt5_confirmatory_pool_classified.csv"
    if rows:
        import pandas as pd

        pd.DataFrame(rows).to_csv(out_path, index=False)
        print(f"\nWrote: {out_path}")
    print("=" * 90)


if __name__ == "__main__":
    main()