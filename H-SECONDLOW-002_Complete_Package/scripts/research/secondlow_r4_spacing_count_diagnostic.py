#!/usr/bin/env python3
"""R4 count-only: 90min vs 120min independence spacing — no outcomes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

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
    detect_independent_events,
    load_ohlcv,
    sha256_prefix,
)

DEPTH_V02 = 1.0
SPACING_BASE = 120
SPACING_R4 = 90
LEDGER = _REPO / "data/secondlow_prospective_events.jsonl"
OUTPUT = _REPO / "H-SECONDLOW-002_Complete_Package/results/r4_spacing_count_diagnostic"


def independent_events_at_spacing(df: pd.DataFrame, spacing_min: int) -> list[pd.Timestamp]:
    work = df.copy()
    work["atr"] = compute_true_range_atr(work)
    work["sl"] = compute_trading_day_second_low(work)
    raw = _detect_raw_purge_mask(work, "sl")
    idx = _independent_indices(work.index, raw, min_spacing_min=spacing_min)
    return [work.index[i] for i in idx]


def event_metrics(df: pd.DataFrame, times: list[pd.Timestamp]) -> list[dict]:
    _, detected = detect_independent_events(df, require_post_window=False)
    by_time = {e.purge_time: e for e in detected}
    rows = []
    for t in times:
        e = by_time.get(t)
        if e is None:
            # spacing variant may include times not in 120min independent set — compute inline
            pos = df.index.get_loc(t)
            sl = float(compute_trading_day_second_low(df).iloc[pos])
            atr = float(compute_true_range_atr(df).iloc[pos])
            low = float(df["low"].iloc[pos])
            close = float(df["close"].iloc[pos])
            pre_start = max(0, pos - 8)
            pre_close = float(df["close"].iloc[pre_start])
            depth_atr = (sl - low) / atr if atr > 0 else float("nan")
            pre_2h = (close - pre_close) / atr if atr > 0 else float("nan")
            rows.append(
                {
                    "purge_time": str(t),
                    "purge_depth_atr": round(depth_atr, 4),
                    "pre_2h_return_atr": round(pre_2h, 4),
                    "v02_exposed": bool(depth_atr >= DEPTH_V02),
                }
            )
        else:
            rows.append(
                {
                    "purge_time": str(t),
                    "purge_depth_atr": round(e.purge_depth_atr, 4),
                    "pre_2h_return_atr": round(e.pre_2h_return_atr, 4),
                    "v02_exposed": bool(e.purge_depth_atr >= DEPTH_V02),
                }
            )
    return rows


def partition(times: list[pd.Timestamp]) -> dict[str, int]:
    s = pd.Series(times)
    pre = int((s < DISCOVERY_START).sum())
    disc = int(((s >= DISCOVERY_START) & (s <= DISCOVERY_END)).sum())
    post = int((s > DISCOVERY_END).sum())
    return {"pre_discovery": pre, "discovery": disc, "post_discovery": post}


def main() -> None:
    corpus = _REPO / CANONICAL_XAUUSD_M15
    df = load_ohlcv(corpus)

    times_120 = independent_events_at_spacing(df, SPACING_BASE)
    times_90 = independent_events_at_spacing(df, SPACING_R4)
    set_120 = set(times_120)
    set_90 = set(times_90)

    ledger_times: set[pd.Timestamp] = set()
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            if line.strip():
                ledger_times.add(pd.Timestamp(json.loads(line)["purge_time"]))

    incremental_90 = sorted(set_90 - set_120)
    dropped_120_only = sorted(set_120 - set_90)

    def summarize(label: str, times: list[pd.Timestamp]) -> dict:
        metrics = event_metrics(df, times)
        n_v02 = sum(1 for m in metrics if m["v02_exposed"])
        post = [t for t in times if t > DISCOVERY_END]
        post_metrics = event_metrics(df, post)
        n_post_v02 = sum(1 for m in post_metrics if m["v02_exposed"])
        in_ledger = [t for t in times if t in ledger_times]
        return {
            "label": label,
            "spacing_min": SPACING_BASE if "120" in label else SPACING_R4,
            "n_independent": len(times),
            "partition": partition(times),
            "n_v02_exposed": n_v02,
            "pct_v02_exposed": round(n_v02 / len(times), 4) if times else None,
            "n_post_discovery": len(post),
            "n_post_v02_exposed": n_post_v02,
            "n_in_current_ledger": len(in_ledger),
        }

    inc_metrics = event_metrics(df, incremental_90)
    inc_post = [m for m in inc_metrics if pd.Timestamp(m["purge_time"]) > DISCOVERY_END]
    inc_v02 = [m for m in inc_metrics if m["v02_exposed"]]

    report = {
        "governance": "COUNT_ONLY_NO_OUTCOMES",
        "hypothesis_candidate": "H-SECONDLOW-005 R4 spacing variant",
        "detector": "20d trading-day second_low (unchanged)",
        "spacing_baseline_min": SPACING_BASE,
        "spacing_r4_min": SPACING_R4,
        "exposure_count_rule": f"purge_depth_atr >= {DEPTH_V02} (v0.2, count only)",
        "corpus": str(corpus),
        "corpus_hash_prefix": sha256_prefix(corpus),
        "baseline_120": summarize("baseline_120min", times_120),
        "r4_90": summarize("r4_90min", times_90),
        "delta_90_minus_120": {
            "n_independent": len(times_90) - len(times_120),
            "n_v02_exposed": summarize("r4_90min", times_90)["n_v02_exposed"]
            - summarize("baseline_120min", times_120)["n_v02_exposed"],
            "n_post_discovery": summarize("r4_90min", times_90)["n_post_discovery"]
            - summarize("baseline_120min", times_120)["n_post_discovery"],
            "n_post_v02_exposed": summarize("r4_90min", times_90)["n_post_v02_exposed"]
            - summarize("baseline_120min", times_120)["n_post_v02_exposed"],
        },
        "incremental_in_90_not_120": {
            "n": len(incremental_90),
            "n_post_discovery": len(inc_post),
            "n_v02_exposed": len(inc_v02),
            "events": inc_metrics,
        },
        "in_120_not_90": {
            "n": len(dropped_120_only),
            "events": [str(t) for t in dropped_120_only],
        },
        "ledger_note": "Current ledger built at 120min spacing; R4 events are not in ledger until re-append under new detector rule.",
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    out = OUTPUT / "r4_spacing_count_diagnostic.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()