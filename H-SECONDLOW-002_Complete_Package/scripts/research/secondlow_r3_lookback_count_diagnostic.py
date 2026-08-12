#!/usr/bin/env python3
"""R3 count-only: 10d/15d vs 20d trading-day lookback — no outcomes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from research.secondlow_v1.corpus import CANONICAL_XAUUSD_M15
from research.secondlow_v1.detector import (
    DISCOVERY_END,
    DISCOVERY_START,
    _detect_raw_purge_mask,
    _independent_indices,
    compute_trading_day_second_low,
    compute_true_range_atr,
    load_ohlcv,
    sha256_prefix,
)

DEPTH_V02 = 1.0
SPACING_MIN = 120
LOOKBACK_BASE = 20
LOOKBACK_CANDIDATES = (15, 10)
LEDGER = _REPO / "data/secondlow_prospective_events.jsonl"
OUTPUT = _REPO / "H-SECONDLOW-002_Complete_Package/results/r3_lookback_count_diagnostic"


def independent_times_at_lookback(df: pd.DataFrame, lookback: int) -> list[pd.Timestamp]:
    work = df.copy()
    work["atr"] = compute_true_range_atr(work)
    work["sl"] = compute_trading_day_second_low(work, lookback=lookback)
    raw = _detect_raw_purge_mask(work, "sl")
    idx = _independent_indices(work.index, raw, min_spacing_min=SPACING_MIN)
    return [work.index[i] for i in idx]


def event_metrics(df: pd.DataFrame, times: list[pd.Timestamp], lookback: int) -> list[dict]:
    work = df.copy()
    work["atr"] = compute_true_range_atr(work)
    work["sl"] = compute_trading_day_second_low(work, lookback=lookback)
    rows = []
    for t in times:
        pos = work.index.get_loc(t)
        sl = float(work["sl"].iloc[pos])
        atr = float(work["atr"].iloc[pos])
        low = float(work["low"].iloc[pos])
        close = float(work["close"].iloc[pos])
        pre_start = max(0, pos - 8)
        pre_close = float(work["close"].iloc[pre_start])
        depth_atr = (sl - low) / atr if atr > 0 else float("nan")
        pre_2h = (close - pre_close) / atr if atr > 0 else float("nan")
        rows.append(
            {
                "purge_time": str(t),
                "lookback_days": lookback,
                "purge_depth_atr": round(depth_atr, 4),
                "pre_2h_return_atr": round(pre_2h, 4),
                "v02_exposed": bool(depth_atr >= DEPTH_V02),
            }
        )
    return rows


def partition(times: list[pd.Timestamp]) -> dict[str, int]:
    s = pd.Series(times)
    pre = int((s < DISCOVERY_START).sum())
    disc = int(((s >= DISCOVERY_START) & (s <= DISCOVERY_END)).sum())
    post = int((s > DISCOVERY_END).sum())
    return {"pre_discovery": pre, "discovery": disc, "post_discovery": post}


def summarize(label: str, lookback: int, times: list[pd.Timestamp], metrics: list[dict]) -> dict:
    post_times = [t for t in times if t > DISCOVERY_END]
    post_metrics = [m for m in metrics if pd.Timestamp(m["purge_time"]) > DISCOVERY_END]
    return {
        "label": label,
        "lookback_trading_days": lookback,
        "spacing_min": SPACING_MIN,
        "n_independent": len(times),
        "partition": partition(times),
        "n_v02_exposed": sum(1 for m in metrics if m["v02_exposed"]),
        "pct_v02_exposed": round(sum(1 for m in metrics if m["v02_exposed"]) / len(times), 4) if times else None,
        "n_post_discovery": len(post_times),
        "n_post_v02_exposed": sum(1 for m in post_metrics if m["v02_exposed"]),
    }


def main() -> None:
    corpus = _REPO / CANONICAL_XAUUSD_M15
    df = load_ohlcv(corpus)

    ledger_times: set[pd.Timestamp] = set()
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            if line.strip():
                ledger_times.add(pd.Timestamp(json.loads(line)["purge_time"]))

    baseline_times = independent_times_at_lookback(df, LOOKBACK_BASE)
    baseline_metrics = event_metrics(df, baseline_times, LOOKBACK_BASE)
    baseline_set = set(baseline_times)

    variants: dict[str, dict] = {
        "baseline_20d": {
            "summary": summarize("baseline_20d", LOOKBACK_BASE, baseline_times, baseline_metrics),
            "metrics": baseline_metrics,
            "times": baseline_times,
        }
    }

    for lb in LOOKBACK_CANDIDATES:
        times = independent_times_at_lookback(df, lb)
        metrics = event_metrics(df, times, lb)
        variants[f"r3_lb{lb}"] = {
            "summary": summarize(f"r3_lb{lb}", lb, times, metrics),
            "metrics": metrics,
            "times": times,
        }

    report_variants = {}
    for key, data in variants.items():
        times_set = set(data["times"])
        incremental = sorted(times_set - baseline_set)
        dropped = sorted(baseline_set - times_set)
        inc_metrics = [m for m in data["metrics"] if pd.Timestamp(m["purge_time"]) in set(incremental)]
        inc_post = [m for m in inc_metrics if pd.Timestamp(m["purge_time"]) > DISCOVERY_END]
        inc_v02 = [m for m in inc_metrics if m["v02_exposed"]]
        report_variants[key] = {
            **data["summary"],
            "delta_vs_baseline_20d": {
                "n_independent": data["summary"]["n_independent"] - variants["baseline_20d"]["summary"]["n_independent"],
                "n_v02_exposed": data["summary"]["n_v02_exposed"] - variants["baseline_20d"]["summary"]["n_v02_exposed"],
                "n_post_discovery": data["summary"]["n_post_discovery"] - variants["baseline_20d"]["summary"]["n_post_discovery"],
                "n_post_v02_exposed": data["summary"]["n_post_v02_exposed"] - variants["baseline_20d"]["summary"]["n_post_v02_exposed"],
            },
            "incremental_vs_20d_not_in_baseline": {
                "n": len(incremental),
                "n_post_discovery": len(inc_post),
                "n_v02_exposed": len(inc_v02),
                "events": inc_metrics[:50],
                "events_truncated": len(inc_metrics) > 50,
            },
            "in_baseline_not_in_variant": {
                "n": len(dropped),
                "events": [str(t) for t in dropped[:30]],
                "events_truncated": len(dropped) > 30,
            },
            "overlap_with_current_ledger": sum(1 for t in data["times"] if t in ledger_times),
        }

    report = {
        "governance": "COUNT_ONLY_NO_OUTCOMES",
        "hypothesis_candidate": "H-SECONDLOW-006 R3 lookback variant",
        "detector_pin": "trading-day second_low ladder; lookback is the variant axis",
        "lookback_baseline_days": LOOKBACK_BASE,
        "lookback_candidates_days": list(LOOKBACK_CANDIDATES),
        "spacing_min": SPACING_MIN,
        "exposure_count_rule": f"purge_depth_atr >= {DEPTH_V02} (v0.2 depth threshold, count only)",
        "corpus": str(corpus),
        "corpus_hash_prefix": sha256_prefix(corpus),
        "variants": report_variants,
        "ledger_note": "Current ledger uses 20d lookback pin; R3 events require separate ledger tag if pursued.",
        "promotion_gate_count_only": {
            "min_post_v02_exposed_delta": 2,
            "rationale": "Need material prospective EXPOSED gain before outcome prereg; depth/spacing relaxations failed at +0 POST.",
        },
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    out = OUTPUT / "r3_lookback_count_diagnostic.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()