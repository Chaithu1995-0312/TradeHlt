"""
_enrich_xauusd_corpus.py — Phase 1: Enrich XAUUSD trace corpus with feature vectors.

DESCRIPTIVE — information not authority (§6.5); no edge/profit claim; failure structure only.

Loads XAUUSD M15 OHLCV, runs FeaturePipeline to produce 38-dim canonical features,
then for each trace in the corpus extracts the feature vector at entry_index and
populates the feature_* fields.

Usage:
    python scripts/research/_enrich_xauusd_corpus.py

Output:
    results/research/trace_corpus/xauusd/trace_corpus_enriched.jsonl
"""
import json
import sys
import os
import logging
from pathlib import Path

import pandas as pd
import numpy as np

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from features.feature_pipeline import FeaturePipeline
from features.feature_schema import CANONICAL_FEATURES

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("enrich_xauusd")

CORPUS_PATH = "results/research/trace_corpus/xauusd/trace_corpus.jsonl"
OHLCV_PATH = "data/XAUUSD_M15.csv"
OUTPUT_PATH = "results/research/trace_corpus/xauusd/trace_corpus_enriched.jsonl"


def load_ohlcv(path: str) -> pd.DataFrame:
    """Load XAUUSD M15 CSV and return raw DataFrame."""
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    log.info("Loaded %d OHLCV rows from %s", len(df), path)
    return df


def run_feature_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """Run the full FeaturePipeline and return enriched DataFrame."""
    pipeline = FeaturePipeline(df)
    enriched_df, vectors = pipeline.run()
    log.info("FeaturePipeline produced %d enriched rows (38-dim vectors)", len(enriched_df))
    return enriched_df


def load_corpus(path: str) -> list[dict]:
    """Load trace corpus as list of dicts."""
    with open(path) as f:
        traces = [json.loads(line) for line in f]
    log.info("Loaded %d traces from %s", len(traces), path)
    return traces


def enrich_trace(trace: dict, enriched_df: pd.DataFrame) -> dict:
    """
    Populate feature_* fields in a trace from the enriched DataFrame.

    The trace's entry_index maps to the original OHLCV row index.
    After FeaturePipeline.finalize(), rows are dropped (warmup NaNs).
    We need to map: original OHLCV index → enriched_df row.

    We do this by aligning on the 'timestamp' column.
    """
    entry_idx = trace["entry_index"]
    entry_ts = trace["entry_timestamp"]

    # Find the row in enriched_df matching this timestamp
    match = enriched_df[enriched_df["timestamp"] == entry_ts]
    if len(match) == 0:
        log.warning("No enriched row for trace %s at %s (idx=%d)", trace["trade_id"], entry_ts, entry_idx)
        return trace

    row = match.iloc[0]

    # Map canonical feature names to feature_* keys
    feature_prefix = "feature_"
    for feat_name in CANONICAL_FEATURES:
        key = f"{feature_prefix}{feat_name}"
        if key in trace:
            val = row.get(feat_name)
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                trace[key] = float(val) if isinstance(val, (np.floating, float)) else int(val) if isinstance(val, (np.integer, int)) else val
            else:
                trace[key] = None

    return trace


def main():
    log.info("=" * 60)
    log.info("Phase 1: Enrich XAUUSD trace corpus with feature vectors")
    log.info("=" * 60)

    # 1. Load OHLCV
    df = load_ohlcv(OHLCV_PATH)

    # 2. Run feature pipeline
    enriched_df = run_feature_pipeline(df)

    # 3. Load corpus
    traces = load_corpus(CORPUS_PATH)

    # 4. Enrich each trace
    enriched_count = 0
    skipped_count = 0
    for i, trace in enumerate(traces):
        enriched = enrich_trace(trace, enriched_df)
        if enriched["feature_open"] is not None:
            enriched_count += 1
        else:
            skipped_count += 1
        traces[i] = enriched

        if (i + 1) % 5000 == 0:
            log.info("  Processed %d / %d traces (enriched=%d, skipped=%d)",
                     i + 1, len(traces), enriched_count, skipped_count)

    log.info("Done: %d enriched, %d skipped out of %d total",
             enriched_count, skipped_count, len(traces))

    # 5. Write enriched corpus
    with open(OUTPUT_PATH, "w") as f:
        for trace in traces:
            f.write(json.dumps(trace, default=str) + "\n")
    log.info("Wrote enriched corpus to %s", OUTPUT_PATH)

    # 6. Quick validation: compare per-outcome means to distributions.json
    log.info("Validating against distributions.json...")
    with open("results/research/trace_corpus/xauusd/distributions.json") as f:
        dist = json.load(f)

    # Check a few features
    for outcome in ["SL_HIT", "TP_HIT", "TIMEOUT"]:
        outcome_traces = [t for t in traces if t["outcome"] == outcome]
        if not outcome_traces:
            continue
        for feat in ["atr", "body_ratio", "rsi_14", "volume_ratio"]:
            key = f"feature_{feat}"
            vals = [t[key] for t in outcome_traces if t[key] is not None]
            if not vals:
                continue
            computed_mean = sum(vals) / len(vals)
            stored_mean = dist["by_outcome"][outcome][feat]["mean"]
            diff_pct = abs(computed_mean - stored_mean) / max(abs(stored_mean), 1e-9) * 100
            log.info("  %s/%s: computed_mean=%.6f stored_mean=%.6f diff=%.2f%%",
                     outcome, feat, computed_mean, stored_mean, diff_pct)

    log.info("Enrichment complete.")


if __name__ == "__main__":
    main()