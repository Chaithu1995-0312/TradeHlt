"""h5_feature_alignment.py — H5: does FeaturePipeline ever drop MID-FILE rows (not just leading
warmup), and is that gap actually covered by the fail-closed check?

Plan reference: pure-conversation-share-only-rosy-parnas.md §4 H5.

WHAT THE SOURCE ALREADY SAYS (backtest_v2.py:2037-2069)
---------------------------------------------------------
`feature_ts_to_idx` is built directly from the SAME `enriched_df` that `feature_vectors` rows come
from (`enriched_df, self.feature_vectors = pipeline.run()`) — the dict and the array can never
disagree with EACH OTHER, they are two views of one object. So the real question is not "can the
dict and the array drift apart" (they cannot, by construction) but "does `enriched_df` skip any
bars the raw candle loop still tries to process". The code's own T-16 comment names the risk
explicitly: "a mid-file NaN drop (finalize() tolerates up to max(300, 2%))". The fail-closed
FeatureAlignmentError guard only fires where a lookup is actually performed — and H2's source read
already established that lookup ONLY happens inside the TRADE_OPENED block (the EngineRunner gate
and `_bar_structure_choch_inputs`). A mid-file drop on a bar that is NOT a trade-open bar is
therefore UNCHECKED — CRT's own `process_candle` never consumes `feature_vectors` at all, so a
missing feature row for a non-trade bar produces no error anywhere.

METHOD
------
Builds `FeaturePipeline` once (no full backtest needed — this is a property of the pipeline output
alone, not of the bar-by-bar replay loop) and compares:
  - `len(raw_df)` — total rows read from the CSV.
  - `len(enriched_df)` — rows FeaturePipeline actually returns.
  - `required_warmup_rows()` — the DECLARED leading-warmup count (T-16's own accounting).
A deficit beyond the declared warmup count is a MID-FILE drop, and the script additionally finds
WHERE by diffing the two timestamp series (a raw timestamp with no matching enriched-df entry,
that is not among the first `required_warmup_rows()` raw rows).

KILL RULE
---------
`len(raw_df) - len(enriched_df) == required_warmup_rows()` exactly, and the gap set is exactly
the LEADING rows (hypothesis falsified — no mid-file drop on this corpus, the fail-closed guard's
TRADE_OPENED-only coverage is a non-issue here even though it would be a real gap on a corpus that
does drop mid-file).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(REPO_ROOT / "data" / "mt5" / "XAUUSD_M15.csv"))
    args = ap.parse_args()

    if not Path(args.csv).exists():
        print(f"H5: ABORT — corpus not found at {args.csv}", file=sys.stderr)
        return 2

    import pandas as pd
    from features.feature_pipeline import FeaturePipeline, required_warmup_rows

    raw_df = pd.read_csv(args.csv)
    raw_df.columns = [c.strip().lower() for c in raw_df.columns]
    if "timestamp" not in raw_df.columns and "date" in raw_df.columns and "time" in raw_df.columns:
        raw_df["timestamp"] = raw_df["date"].astype(str) + " " + raw_df["time"].astype(str)

    pipeline = FeaturePipeline(raw_df)
    enriched_df, feature_vectors = pipeline.run()

    expected_warmup = required_warmup_rows()
    raw_ts = pd.to_datetime(raw_df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    enriched_ts = set(pd.to_datetime(enriched_df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S"))

    dropped_positions = [i for i, ts in enumerate(raw_ts) if ts not in enriched_ts]
    leading_dropped = [i for i in dropped_positions if i < expected_warmup]
    mid_file_dropped = [i for i in dropped_positions if i >= expected_warmup]

    verdict = {
        "hypothesis": "H5",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "csv": args.csv,
        "raw_rows": len(raw_df),
        "enriched_rows": len(enriched_df),
        "feature_vectors_rows": len(feature_vectors) if feature_vectors is not None else None,
        "declared_warmup_rows": expected_warmup,
        "total_dropped_rows": len(dropped_positions),
        "leading_dropped_count": len(leading_dropped),
        "mid_file_dropped_count": len(mid_file_dropped),
        "mid_file_dropped_positions_sample": mid_file_dropped[:20],
        "dict_array_construction_note": (
            "feature_ts_to_idx and feature_vectors are built from the SAME enriched_df in the "
            "SAME loop (backtest_v2.py:2022,2042-2045) -- they cannot disagree with each other "
            "by construction. This script tests enriched_df vs the raw candle stream instead."
        ),
        "fail_closed_coverage_note": (
            "The FeatureAlignmentError lookup-miss guard (T-16) only fires where feature_vector "
            "is actually looked up, which H2's source read established is ONLY inside the "
            "TRADE_OPENED block. A mid-file drop on a non-trade-open bar would be UNCHECKED."
        ),
        "result": (
            "FALSIFIED_ONLY_LEADING_WARMUP_DROPPED" if not mid_file_dropped else
            "CONFIRMED_MID_FILE_DROP_EXISTS_AND_IS_UNCHECKED_ON_NON_TRADE_BARS"
        ),
    }

    out_path = REPO_ROOT / "results" / f"h5_feature_alignment_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    print(f"H5 result: {verdict['result']}")
    print(f"  raw_rows={len(raw_df)} enriched_rows={len(enriched_df)} declared_warmup={expected_warmup}")
    print(f"  total_dropped={len(dropped_positions)} leading={len(leading_dropped)} mid_file={len(mid_file_dropped)}")
    print(f"  -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
