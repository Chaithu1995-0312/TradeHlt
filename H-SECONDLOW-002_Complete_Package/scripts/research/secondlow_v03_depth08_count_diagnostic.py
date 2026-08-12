#!/usr/bin/env python3
"""H-SECONDLOW-005 v0.3 count-only: depth >= 0.8 vs v0.2 depth >= 1.0 — no outcomes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from research.secondlow_v1.corpus import CANONICAL_XAUUSD_M15
from research.secondlow_v1.detector import DISCOVERY_END, detect_independent_events, load_ohlcv, sha256_prefix

DEPTH_V02 = 1.0
DEPTH_V03 = 0.8
LEDGER = _REPO / "data/secondlow_prospective_events.jsonl"
OUTPUT = _REPO / "H-SECONDLOW-002_Complete_Package/results/v03_depth08_count_diagnostic"


def is_exposed(depth: float, threshold: float) -> bool:
    return depth >= threshold


def count_and_list(events: list, threshold: float) -> tuple[int, list[dict]]:
    rows = []
    for e in events:
        if is_exposed(e.purge_depth_atr, threshold):
            rows.append(
                {
                    "purge_time": str(e.purge_time),
                    "purge_depth_atr": round(e.purge_depth_atr, 4),
                    "pre_2h_return_atr": round(e.pre_2h_return_atr, 4),
                }
            )
    return len(rows), rows


def main() -> None:
    corpus = _REPO / CANONICAL_XAUUSD_M15
    df = load_ohlcv(corpus)
    _, all_events = detect_independent_events(df, require_post_window=False)

    ledger_times: set[pd.Timestamp] = set()
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            if line.strip():
                ledger_times.add(pd.Timestamp(json.loads(line)["purge_time"]))

    post_events = [e for e in all_events if e.purge_time > DISCOVERY_END]
    pre_disc = [e for e in all_events if e.purge_time < pd.Timestamp("2026-04-17")]
    ledger_events = [e for e in all_events if e.purge_time in ledger_times]

    scopes = {
        "all_independent_50": all_events,
        "pre_discovery_21": pre_disc,
        "post_discovery_14": post_events,
        "prospective_ledger_14": ledger_events,
    }

    scope_rows = []
    incremental_v03_only = []
    for name, evs in scopes.items():
        n02, _ = count_and_list(evs, DEPTH_V02)
        n03, exposed03 = count_and_list(evs, DEPTH_V03)
        scope_rows.append(
            {
                "scope": name,
                "n_events": len(evs),
                "v02_depth_ge_1.0": n02,
                "v03_depth_ge_0.8": n03,
                "delta_v03_minus_v02": n03 - n02,
                "pct_exposed_v02": round(n02 / len(evs), 4) if evs else None,
                "pct_exposed_v03": round(n03 / len(evs), 4) if evs else None,
            }
        )

    v02_set = {e.purge_time for e in all_events if is_exposed(e.purge_depth_atr, DEPTH_V02)}
    for e in all_events:
        if is_exposed(e.purge_depth_atr, DEPTH_V03) and e.purge_time not in v02_set:
            incremental_v03_only.append(
                {
                    "purge_time": str(e.purge_time),
                    "purge_depth_atr": round(e.purge_depth_atr, 4),
                    "pre_2h_return_atr": round(e.pre_2h_return_atr, 4),
                    "in_post_discovery": bool(e.purge_time > DISCOVERY_END),
                    "in_prospective_ledger": bool(e.purge_time in ledger_times),
                }
            )

    report = {
        "governance": "COUNT_ONLY_NO_OUTCOMES",
        "hypothesis_candidate": "H-SECONDLOW-005 v0.3",
        "exposure_v02": f"purge_depth_atr >= {DEPTH_V02}",
        "exposure_v03": f"purge_depth_atr >= {DEPTH_V03}",
        "corpus": str(corpus),
        "corpus_hash_prefix": sha256_prefix(corpus),
        "scopes": scope_rows,
        "incremental_v03_not_v02": {
            "n": len(incremental_v03_only),
            "events": incremental_v03_only,
        },
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    out = OUTPUT / "depth08_count_diagnostic.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()