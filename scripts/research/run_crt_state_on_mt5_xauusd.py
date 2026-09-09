"""
Run CRT State Resolver on fresh MT5 XAUUSD data.
=================================================
Pipeline:
  1. Load raw OHLCV from data/mt5/XAUUSD_M15.csv
  2. Run FeaturePipeline to produce canonical 39-dim feature vectors
  3. Run CRTStateResolver on every bar's feature vector
  4. Generate comparison report

Usage:
    python scripts/research/run_crt_state_on_mt5_xauusd.py
"""

import json
import logging
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from features.feature_pipeline import FeaturePipeline
from features.feature_schema import CANONICAL_FEATURES
from features.crt_state_resolver import CRTStateResolver, build_htf_id_timeline
from features.resolver_supply import build_resolver_supply
from data_ingestion.corpus_gate import admit_corpus
from features.feature_states import FeatureStateEncoder
from features.registry import load_ontology
from config_layer.production_config import get_prod_section

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("crt_state_xauusd")

OHLCV_PATH = "data/mt5/XAUUSD_M15.csv"
REPORT_PATH = "reports/crt_state_fresh_run_xauusd.md"


SUPPLY_STATS = {}  # supply-set provenance for the report header
ADMISSION = None  # CorpusAdmission for this run; stamped into the report header


def load_ohlcv(path: str) -> pd.DataFrame:
    # Corpus gate: IDENTITY (bound dataset + verified sha256) then SEQUENCE
    # then PLAUSIBILITY (D-1..D-4), before a single row is parsed. write_report
    # is False because the fingerprint slot is {symbol}_{tf}.json and collides
    # with the forensic data/XAUUSD_M15.csv -- the report is carried in the run
    # artifact instead. A REJECT raises; a WARN proceeds and is recorded.
    global ADMISSION
    ADMISSION = admit_corpus(path, "XAUUSD", write_report=False, log=log)
    df = pd.read_csv(ADMISSION.filepath)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    log.info("Loaded %d OHLCV rows from %s", len(df), path)
    return df


def run_feature_pipeline(df: pd.DataFrame) -> tuple:
    """Return BOTH halves. `vectors` is the canonical, order-defined surface the
    resolver supply must be sourced from -- returning only `enriched_df` is what
    forced callers to reconstruct the supply by hand, each differently."""
    pipeline = FeaturePipeline(df)
    enriched_df, vectors = pipeline.run()
    log.info("FeaturePipeline produced %d enriched rows (%d-dim vectors)",
             len(enriched_df), vectors.shape[1] if vectors is not None else 0)
    return enriched_df, vectors


def main():
    # Step 1: Load raw MT5 XAUUSD data
    log.info("=" * 60)
    log.info("STEP 1: Loading MT5 XAUUSD M15 OHLCV data")
    log.info("=" * 60)
    df = load_ohlcv(OHLCV_PATH)
    total_raw = len(df)

    # Step 2: Run FeaturePipeline
    log.info("")
    log.info("=" * 60)
    log.info("STEP 2: Running FeaturePipeline")
    log.info("=" * 60)
    enriched, vectors = run_feature_pipeline(df)
    total_enriched = len(enriched)

    log.info("Raw OHLCV rows: %d", total_raw)
    log.info("Enriched rows (after warmup drop): %d", total_enriched)
    log.info("Dropped (warmup): %d", total_raw - total_enriched)

    # HTF phase-lock: build the id timeline over the RAW stream length (matching the engine's
    # own HTFBuilder, which counts from candle 0 of the raw corpus), then slice off the same
    # leading prefix FeaturePipeline.finalize() dropped, so htf_ids[i] lines up 1:1 with
    # enriched.iloc[i]. Without this, the resolver's internal HTF counter restarts at 0 on the
    # post-warmup slice instead of continuing from the engine's actual cycle position.
    _candles_per_htf = int(get_prod_section("backtest")["htf_candles_per_range"])
    _dropped = total_raw - total_enriched
    _full_htf_ids = build_htf_id_timeline(
        total_raw, candles_per_htf=_candles_per_htf, instrument="XAUUSD",
    )
    htf_ids = _full_htf_ids[_dropped:]
    assert len(htf_ids) == total_enriched, (
        f"htf_id timeline length {len(htf_ids)} != enriched row count {total_enriched} — "
        "the warmup drop is not a clean leading prefix."
    )
    log.info("HTF phase-lock: candles_per_htf=%d, first htf_id=%s", _candles_per_htf, htf_ids[0])

    # Step 3: Build the resolver supply through the ONE contract-driven adapter.
    # Previously this hand-rolled a dict of `canonical-intersection + retest_flag +
    # displacement_flag` with a silent `if pd.isna(val): val = 0.0` coercion, and
    # omitted rsi_state entirely. Since `resolve()` classifies EVERY supplied key
    # and .update()s over classify()'s output, that made feature_states a function
    # of the caller. resolver_supply sources canonical names from the vector,
    # non-vector `when:` features from the enriched frame, and passes nothing else.
    resolver = CRTStateResolver()
    global SUPPLY_STATS
    supply_rows, supply_stats = build_resolver_supply(resolver, enriched, vectors)
    SUPPLY_STATS = supply_stats
    log.info("Supply set: %s (%s)", supply_stats["supply_set_id"],
             supply_stats["supply_fingerprint"][:16])
    log.info("  %d canonical from vector + %s from enriched; nan_policy=%s",
             supply_stats["keys_from_vector"], supply_stats["keys_from_enriched"],
             supply_stats["nan_policy"])

    log.info("")
    log.info("=" * 60)
    log.info("STEP 3: Running CRT State Resolver")
    log.info("=" * 60)
    log.info("Total bars to resolve: %d", total_enriched)

    state_sequence = []
    resolver.reset_counts()
    resolver.reset_memory()

    timestamps = enriched["timestamp"].tolist()
    for i, feat_dict in enumerate(supply_rows):
        state = resolver.resolve(feat_dict, timestamp=timestamps[i], htf_id=htf_ids[i])
        state_sequence.append(state)

    counts = resolver.counts
    total_resolved = sum(counts.values())

    log.info("Resolved %d bars", total_resolved)
    log.info("State counts:")
    for state, count in sorted(counts.items()):
        pct = count / total_resolved * 100 if total_resolved > 0 else 0
        log.info("  %-20s %8d  (%5.2f%%)", state, count, pct)

    # Step 5: Compute transition counts
    transitions = Counter()
    for i in range(1, len(state_sequence)):
        prev = state_sequence[i - 1]
        curr = state_sequence[i]
        if prev != curr:
            transitions[(prev, curr)] += 1

    # Step 6: Compute funnel
    log.info("")
    log.info("=" * 60)
    log.info("STEP 4: State Funnel Analysis")
    log.info("=" * 60)

    funnel_states = ["RANGE", "SWEEP", "DISPLACEMENT", "EXPANSION", "RETEST", "EXECUTION", "RESOLUTION"]
    funnel = {}
    for s in funnel_states:
        funnel[s] = counts.get(s, 0)

    log.info("Funnel (progression from RANGE to EXECUTION):")
    for i, s in enumerate(funnel_states):
        c = funnel[s]
        pct = c / total_resolved * 100 if total_resolved > 0 else 0
        if i > 0:
            prev_count = funnel[funnel_states[i - 1]]
            retention = c / prev_count * 100 if prev_count > 0 else 0
            log.info("  %-20s %8d  (%5.2f%%)  retention from prev: %5.2f%%",
                     s, c, pct, retention)
        else:
            log.info("  %-20s %8d  (%5.2f%%)", s, c, pct)

    # Step 7: Write report
    log.info("")
    log.info("=" * 60)
    log.info("STEP 5: Writing report to %s", REPORT_PATH)
    log.info("=" * 60)

    lines = []
    lines.append("# CRT State Resolver — Fresh Run on MT5 XAUUSD M15")
    lines.append("")
    lines.append("> **Generated:** %s" % pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("> **Data source:** `%s`" % (ADMISSION.filepath if ADMISSION else OHLCV_PATH))
    if ADMISSION is not None:
        lines.append("> **dataset_id:** `%s` (bound=%s, decision=%s)"
                     % (ADMISSION.dataset_id, ADMISSION.bound, ADMISSION.decision))
        lines.append("> **file_hash:** `%s`" % ADMISSION.file_hash)
        lines.append("> **plausibility:** `%s`" % ADMISSION.plausibility)
    if SUPPLY_STATS:
        lines.append("> **supply_set:** `%s` / `%s` (nan_policy=%s)"
                     % (SUPPLY_STATS["supply_set_id"],
                        SUPPLY_STATS["supply_fingerprint"][:16],
                        SUPPLY_STATS["nan_policy"]))
    lines.append("> **CRT states config:** `configs/formulas/market_crt_states.yaml`")
    lines.append("> **Resolver:** `src/features/crt_state_resolver.py`")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append("| Raw OHLCV rows | %d |" % total_raw)
    lines.append("| Enriched rows (after warmup) | %d |" % total_enriched)
    lines.append("| Resolved bars | %d |" % total_resolved)
    lines.append("| State transitions | %d |" % resolver.transition_count)
    lines.append("| Warmup bars dropped | %d |" % (total_raw - total_enriched))
    lines.append("")

    # Per-state counts
    lines.append("## Per-State Bar Counts")
    lines.append("")
    lines.append("| State | Count | %% of Total |")
    lines.append("|-------|-------|------------|")
    for state in sorted(counts.keys()):
        c = counts[state]
        pct = c / total_resolved * 100 if total_resolved > 0 else 0
        lines.append("| %s | %d | %.2f%% |" % (state, c, pct))
    lines.append("")

    # Funnel
    lines.append("## State Funnel (Progression)")
    lines.append("")
    lines.append("| Step | State | Count | %% of Total | Retention from Prev |")
    lines.append("|------|-------|-------|------------|---------------------|")
    for i, s in enumerate(funnel_states):
        c = funnel[s]
        pct = c / total_resolved * 100 if total_resolved > 0 else 0
        if i > 0:
            prev_count = funnel[funnel_states[i - 1]]
            retention = c / prev_count * 100 if prev_count > 0 else 0
            lines.append("| %d | %s | %d | %.2f%% | %.2f%% |" % (i + 1, s, c, pct, retention))
        else:
            lines.append("| %d | %s | %d | %.2f%% | — |" % (i + 1, s, c, pct))
    lines.append("")

    # Key ratios
    lines.append("## Key Ratios")
    lines.append("")
    if funnel["RANGE"] > 0:
        sweep_rate = funnel["SWEEP"] / funnel["RANGE"] * 100
        lines.append("- **SWEEP/RANGE rate**: %.2f%% (%d sweeps per %d range bars)" % (
            sweep_rate, funnel["SWEEP"], funnel["RANGE"]))
    if funnel["SWEEP"] > 0:
        disp_rate = funnel["DISPLACEMENT"] / funnel["SWEEP"] * 100
        lines.append("- **DISPLACEMENT/SWEEP rate**: %.2f%% (%d displacements per %d sweeps)" % (
            disp_rate, funnel["DISPLACEMENT"], funnel["SWEEP"]))
    if funnel["DISPLACEMENT"] > 0:
        exp_rate = funnel["EXPANSION"] / funnel["DISPLACEMENT"] * 100
        lines.append("- **EXPANSION/DISPLACEMENT rate**: %.2f%% (%d expansions per %d displacements)" % (
            exp_rate, funnel["EXPANSION"], funnel["DISPLACEMENT"]))
    if funnel["EXPANSION"] > 0:
        retest_rate = funnel["RETEST"] / funnel["EXPANSION"] * 100
        lines.append("- **RETEST/EXPANSION rate**: %.2f%% (%d retests per %d expansions)" % (
            retest_rate, funnel["RETEST"], funnel["EXPANSION"]))
    if funnel["RETEST"] > 0:
        exec_rate = funnel["EXECUTION"] / funnel["RETEST"] * 100
        lines.append("- **EXECUTION/RETEST rate**: %.2f%% (%d executions per %d retests)" % (
            exec_rate, funnel["EXECUTION"], funnel["RETEST"]))
    lines.append("")

    # Top transitions
    lines.append("## Top State Transitions")
    lines.append("")
    lines.append("| From | To | Count |")
    lines.append("|------|----|-------|")
    for (frm, to), cnt in transitions.most_common(20):
        lines.append("| %s | %s | %d |" % (frm, to, cnt))
    lines.append("")

    # State sequence sample
    lines.append("## State Sequence (first 50 bars)")
    lines.append("")
    lines.append("```")
    lines.append(" → ".join(state_sequence[:50]))
    lines.append("```")
    lines.append("")

    # Feature state distribution
    lines.append("## Feature State Distribution (sample)")
    lines.append("")
    lines.append("The CRT resolver uses these feature states from `market_ontology.yaml`:")
    lines.append("")
    encoder = FeatureStateEncoder(load_ontology())
    for fname in sorted(encoder.stateful_features):
        if fname in enriched.columns:
            vals = enriched[fname].dropna().values[:1000]
            state_counts = Counter()
            for v in vals:
                try:
                    state = encoder.classify_value(fname, float(v))
                    state_counts[state] += 1
                except KeyError:
                    pass
            if state_counts:
                most_common = state_counts.most_common(5)
                lines.append("- **%s**: %s" % (fname, ", ".join(
                    "%s=%d" % (s, c) for s, c in most_common
                )))
    lines.append("")

    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    log.info("Report written to %s", REPORT_PATH)
    log.info("")
    log.info("=" * 60)
    log.info("DONE")
    log.info("=" * 60)


if __name__ == "__main__":
    main()