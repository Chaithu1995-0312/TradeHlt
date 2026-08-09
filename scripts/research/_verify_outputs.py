"""Verify all enrichment outputs."""
import json

print("=== Verification of XAUUSD Trace Corpus Enrichment ===\n")

# 1. Check enriched corpus
with open("results/research/trace_corpus/xauusd/trace_corpus_enriched.jsonl", encoding="utf-8") as f:
    lines = [json.loads(l) for l in f]
print(f"1. Enriched corpus: {len(lines)} traces")

# Count non-null feature fields per trace
sample = lines[0]
feature_keys = [k for k in sample if k.startswith("feature_")]
engine_keys = [k for k in sample if k.startswith("engine_")]
nonnull_features = sum(1 for t in lines if t[feature_keys[0]] is not None)
nonnull_engines = sum(1 for t in lines if t.get("engine_crt_score") is not None)
print(f"   - Traces with features: {nonnull_features}/{len(lines)}")
print(f"   - Traces with engine scores: {nonnull_engines}/{len(lines)}")
print(f"   - Feature fields: {len(feature_keys)}, Engine fields: {len(engine_keys)}")

# Sample
t = lines[0]
print(f"   - Sample trace: {t['trade_id']}, outcome={t['outcome']}, feature_open={t.get('feature_open')}, engine_crt={t.get('engine_crt_score')}, fusion={t.get('fusion_composite')}")

# 2. Check library
with open("results/research/trace_corpus/xauusd/REPRESENTATIVE_LIBRARY.md", encoding="utf-8") as f:
    lib = f.read()
lib_lines = lib.strip().split("\n")
print(f"\n2. Representative Library: {len(lib_lines)} lines")

# 3. Check exemplars
with open("results/research/trace_corpus/xauusd/representative_exemplars.jsonl", encoding="utf-8") as f:
    exemplars = [json.loads(l) for l in f]
print(f"   - Exemplars: {len(exemplars)} traces")
for i, ex in enumerate(exemplars[:3]):
    print(f"     [{i+1}] {ex['trade_id']} {ex['family']} {ex['outcome']} R={ex['rr_achieved']:.2f}")

# 4. Check evaluation
with open("results/research/trace_corpus/xauusd/ENGINE_EVALUATION.md", encoding="utf-8") as f:
    eval_text = f.read()
eval_lines = eval_text.strip().split("\n")
print(f"\n3. Engine Evaluation: {len(eval_lines)} lines")
for line in eval_lines:
    if "| Fusion |" in line or "AUC" in line and "|" in line and "---" not in line:
        print(f"   {line.strip()}")

# 5. File listing
import os
target_dir = "results/research/trace_corpus/xauusd"
print(f"\n4. All files in {target_dir}:")
for fname in sorted(os.listdir(target_dir)):
    fpath = os.path.join(target_dir, fname)
    size = os.path.getsize(fpath)
    print(f"   {fname:45s} {size:>8,} bytes")

print("\n=== Verification complete ===")