"""
_enrich_xauusd_engines.py — Phase 2: Enrich XAUUSD trace corpus with engine outputs.

DESCRIPTIVE — information not authority (§6.5); no edge/profit claim; failure structure only.

For each enriched trace, runs all 4 engines (CRT, Gaussian, Zone Gate, RR) and
computes fusion composite scores. Adds engine_* fields to each trace line.

Usage:
    python scripts/research/_enrich_xauusd_engines.py

Input:
    results/research/trace_corpus/xauusd/trace_corpus_enriched.jsonl

Output:
    results/research/trace_corpus/xauusd/trace_corpus_enriched.jsonl  (updated)
"""
import json
import sys
import math
import logging
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from engines.crt_engine import compute as crt_compute
from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
from engines.rr_engine import RREngine
from features.feature_schema import CANONICAL_FEATURES

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("enrich_engines")

INPUT_PATH = "results/research/trace_corpus/xauusd/trace_corpus_enriched.jsonl"
OUTPUT_PATH = "results/research/trace_corpus/xauusd/trace_corpus_enriched.jsonl"

# Fusion weights (from ENGINE_RUNNER_DEFAULTS in engine_runner.py)
FUSION_WEIGHTS = {
    "crt": 0.4,
    "gaussian": 0.3,
    "zone_gate": 0.2,
    "rr": 0.1,
}

# CRT score component weights (PLAN-002)
CRT_SCORE_WEIGHTS = (0.35, 0.25, 0.20, 0.20)


def compute_crt_score(features: dict) -> dict:
    """Run CRT engine on a feature dict."""
    try:
        result = crt_compute(
            trade_id="enrich",
            features=features,
            context={"score_component_weights": CRT_SCORE_WEIGHTS},
        )
        return {
            "score": result.get("score", 0.0),
            "reason": result.get("reason", ""),
        }
    except Exception as e:
        log.warning("CRT engine failed: %s", e)
        return {"score": 0.0, "reason": str(e)}


def compute_gaussian_score(features: dict, engine: HeuristicGaussianEngine) -> dict:
    """Run Gaussian engine on a feature dict."""
    try:
        result = engine.compute(features)
        return {
            "score": float(result.get("score", 0.5)),
        }
    except Exception as e:
        log.warning("Gaussian engine failed: %s", e)
        return {"score": 0.5}


def compute_zone_score(features: dict) -> dict:
    """
    Compute a simple zone-proxy score based on feature geometry.
    Since we don't have a full zone registry loaded, we use a heuristic:
    - body_ratio > 0.7 → strong candle → higher zone score
    - sweep_detected → zone activation
    - retest_depth > 0 → retest zone
    """
    try:
        body_ratio = float(features.get("body_ratio", 0.0))
        sweep = bool(features.get("sweep_detected", False))
        retest = float(features.get("retest_depth", 0.0))
        disp = float(features.get("disp_strength", 0.0))

        # Simple heuristic zone score
        score = 0.0
        if body_ratio > 0.7:
            score += 0.3
        if sweep:
            score += 0.3
        if retest > 0.1:
            score += 0.2
        if disp > 0.5:
            score += 0.2

        score = min(score, 1.0)
        return {"score": round(score, 4), "zone_id": -1}
    except Exception as e:
        log.warning("Zone score failed: %s", e)
        return {"score": 0.5, "zone_id": -1}


# RR engine singleton (created once in main())
rr_engine = None

def compute_rr_score(features: dict) -> dict:
    """Run RR engine on a feature dict's OHLC data."""
    global rr_engine
    try:
        result = rr_engine.compute({
            "close": float(features.get("close", 0)),
            "high": float(features.get("high", 0)),
            "low": float(features.get("low", 0)),
        })
        return {
            "score": float(result.get("score", 0.5)),
        }
    except Exception as e:
        log.warning("RR engine failed: %s", e)
        return {"score": 0.5}


def compute_fusion(engine_scores: dict) -> dict:
    """Compute weighted fusion score from all 4 engine scores."""
    composite = 0.0
    total_w = 0.0
    scores = {}
    for name, weight in FUSION_WEIGHTS.items():
        s = engine_scores.get(name, {}).get("score", 0.5)
        scores[name] = s
        composite += weight * s
        total_w += weight

    composite = composite / total_w if total_w > 0 else 0.5

    # Decision: EXECUTE if composite >= 0.5, VETO otherwise
    decision = "EXECUTE" if composite >= 0.5 else "VETO"

    # Disagreement: std of engine scores
    score_vals = list(scores.values())
    disagreement = float(np.std(score_vals)) if len(score_vals) > 1 else 0.0

    return {
        "composite": round(composite, 4),
        "decision": decision,
        "disagreement": round(disagreement, 4),
        "scores": scores,
    }


def main():
    log.info("=" * 60)
    log.info("Phase 2: Enrich XAUUSD trace corpus with engine outputs")
    log.info("=" * 60)

    # 1. Load enriched corpus
    with open(INPUT_PATH) as f:
        traces = [json.loads(line) for line in f]
    log.info("Loaded %d enriched traces", len(traces))

    # 2. Initialise engines once (reused for all traces)
    global rr_engine
    gauss_engine = HeuristicGaussianEngine(
        {"gaussian_mu": 0.0, "gaussian_sigma": 1.0},
        instrument="XAUUSD",
        preload_registry=False,
    )
    rr_engine = RREngine(config={"min_rr": 1.5})

    # 3. Score each trace
    enriched_count = 0
    for i, trace in enumerate(traces):
        # Build feature dict from feature_* fields
        features = {}
        for feat_name in CANONICAL_FEATURES:
            key = f"feature_{feat_name}"
            val = trace.get(key)
            if val is not None:
                try:
                    features[feat_name] = float(val)
                except (TypeError, ValueError):
                    features[feat_name] = 0.0
            else:
                features[feat_name] = 0.0

        # Skip traces without features (warmup period)
        if all(v == 0.0 for v in features.values()):
            trace["engine_crt_score"] = None
            trace["engine_gaussian_score"] = None
            trace["engine_zone_score"] = None
            trace["engine_rr_score"] = None
            trace["fusion_composite"] = None
            trace["fusion_decision"] = None
            trace["engine_disagreement"] = None
            continue

        # CRT
        crt_result = compute_crt_score(features)
        trace["engine_crt_score"] = crt_result["score"]

        # Gaussian
        gauss_result = compute_gaussian_score(features, gauss_engine)
        trace["engine_gaussian_score"] = gauss_result["score"]

        # Zone (heuristic proxy)
        zone_result = compute_zone_score(features)
        trace["engine_zone_score"] = zone_result["score"]
        trace["engine_zone_id"] = zone_result["zone_id"]

        # RR
        rr_result = compute_rr_score(features)
        trace["engine_rr_score"] = rr_result["score"]

        # Fusion
        engine_scores = {
            "crt": crt_result,
            "gaussian": gauss_result,
            "zone_gate": zone_result,
            "rr": rr_result,
        }
        fusion = compute_fusion(engine_scores)
        trace["fusion_composite"] = fusion["composite"]
        trace["fusion_decision"] = fusion["decision"]
        trace["engine_disagreement"] = fusion["disagreement"]

        enriched_count += 1

        if (i + 1) % 5000 == 0:
            log.info("  Processed %d / %d traces (engine-enriched=%d)",
                     i + 1, len(traces), enriched_count)

    log.info("Done: %d engine-enriched out of %d total", enriched_count, len(traces))

    # 4. Write updated corpus
    with open(OUTPUT_PATH, "w") as f:
        for trace in traces:
            f.write(json.dumps(trace, default=str) + "\n")
    log.info("Wrote engine-enriched corpus to %s", OUTPUT_PATH)

    # 5. Summary statistics
    scores = {
        "crt": [],
        "gaussian": [],
        "zone": [],
        "rr": [],
        "fusion": [],
        "disagreement": [],
    }
    for t in traces:
        if t.get("engine_crt_score") is not None:
            scores["crt"].append(t["engine_crt_score"])
            scores["gaussian"].append(t["engine_gaussian_score"])
            scores["zone"].append(t["engine_zone_score"])
            scores["rr"].append(t["engine_rr_score"])
            scores["fusion"].append(t["fusion_composite"])
            scores["disagreement"].append(t["engine_disagreement"])

    log.info("\nEngine score summary (mean ± std):")
    for name, vals in scores.items():
        if vals:
            log.info("  %-12s: %.4f ± %.4f  [%.4f, %.4f]",
                     name, np.mean(vals), np.std(vals), min(vals), max(vals))

    # Agreement analysis
    crt_arr = np.array(scores["crt"])
    gauss_arr = np.array(scores["gaussian"])
    zone_arr = np.array(scores["zone"])
    rr_arr = np.array(scores["rr"])

    # Pairwise correlations
    log.info("\nPairwise Pearson correlations:")
    pairs = [("CRT", "Gaussian", crt_arr, gauss_arr),
             ("CRT", "Zone", crt_arr, zone_arr),
             ("CRT", "RR", crt_arr, rr_arr),
             ("Gaussian", "Zone", gauss_arr, zone_arr),
             ("Gaussian", "RR", gauss_arr, rr_arr),
             ("Zone", "RR", zone_arr, rr_arr)]
    for n1, n2, a1, a2 in pairs:
        if np.std(a1) > 0 and np.std(a2) > 0:
            corr = float(np.corrcoef(a1, a2)[0, 1])
            log.info("  %s ↔ %s: r=%.4f", n1, n2, corr)

    # Agreement: all 4 engines agree on direction (score >= 0.5 = bullish)
    # Use logical AND of pairwise equality
    agree_mask = ((crt_arr >= 0.5) == (gauss_arr >= 0.5)) & \
                 ((gauss_arr >= 0.5) == (zone_arr >= 0.5)) & \
                 ((zone_arr >= 0.5) == (rr_arr >= 0.5))
    all_agree = int(np.sum(agree_mask))
    log.info("\nAll-4-engine agreement: %d / %d (%.1f%%)",
             all_agree, len(crt_arr), 100 * all_agree / len(crt_arr))

    # Fusion decision distribution
    decisions = {}
    for t in traces:
        d = t.get("fusion_decision", "NONE")
        decisions[d] = decisions.get(d, 0) + 1
    log.info("\nFusion decision distribution:")
    for d, n in sorted(decisions.items(), key=lambda x: -x[1]):
        log.info("  %s: %d (%.1f%%)", d, n, 100 * n / len(traces))

    log.info("\nEngine enrichment complete.")


if __name__ == "__main__":
    main()