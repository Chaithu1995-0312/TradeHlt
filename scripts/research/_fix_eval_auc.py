"""
Hotfix: regenerate ENGINE_EVALUATION.md with correct AUC/IC computation.
"""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
from sklearn.metrics import roc_auc_score
from scipy.stats import spearmanr

from features.feature_schema import CANONICAL_FEATURES

def load_corpus(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]

def has_engines(t):
    return t.get("engine_crt_score") is not None

def compute_auc(traces, engine_key):
    pairs = [(t[engine_key], 1 if t["outcome"] == "TP_HIT" else 0)
             for t in traces if has_engines(t) and t[engine_key] is not None]
    if len(pairs) < 10:
        return 0.0
    try:
        return float(roc_auc_score([p[1] for p in pairs], [p[0] for p in pairs]))
    except Exception:
        return 0.0

def compute_ic(traces, engine_key):
    pairs = [(t[engine_key], 1 if t["outcome"] == "TP_HIT" else 0)
             for t in traces if has_engines(t) and t[engine_key] is not None]
    if len(pairs) < 10:
        return 0.0
    r, _ = spearmanr([p[0] for p in pairs], [p[1] for p in pairs])
    return float(r) if not np.isnan(r) else 0.0

traces = load_corpus("results/research/trace_corpus/xauusd/trace_corpus_enriched.jsonl")
all_eng = [t for t in traces if has_engines(t)]
n = len(all_eng)

print("=== Corrected AUC/IC values ===")
for name, key in [("CRT", "engine_crt_score"), ("Gaussian", "engine_gaussian_score"),
                   ("Zone", "engine_zone_score"), ("RR", "engine_rr_score"),
                   ("Fusion", "fusion_composite")]:
    auc = compute_auc(all_eng, key)
    ic = compute_ic(all_eng, key)
    print(f"{name:10s}: AUC={auc:.6f}, IC={ic:.6f}")

print(f"\nTotal engine-enabled traces: {n}")