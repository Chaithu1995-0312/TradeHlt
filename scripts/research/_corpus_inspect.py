"""Quick inspection of the XAUUSD trace corpus."""
import json

with open("results/research/trace_corpus/xauusd/trace_corpus.jsonl") as f:
    lines = [json.loads(l) for l in f]

print("Total traces:", len(lines))
families = set(l["family"] for l in lines)
outcomes = set(l["outcome"] for l in lines)
print("Families:", families)
print("Outcomes:", outcomes)
print("Directions:", set(l["direction"] for l in lines))
print("Max entry_index:", max(l["entry_index"] for l in lines))
timestamps = [l["entry_timestamp"] for l in lines]
print("Date range:", min(timestamps), "to", max(timestamps))

# Check how many have null feature_* fields
sample = lines[0]
feature_fields = [k for k in sample if k.startswith("feature_")]
null_count = sum(1 for l in lines if all(l[f] is None for f in feature_fields))
print(f"\nTraces with ALL feature_* null: {null_count} / {len(lines)}")
print(f"Feature fields: {len(feature_fields)}")

# Per-family counts
from collections import Counter
fam_counts = Counter(l["family"] for l in lines)
for fam, n in fam_counts.most_common():
    print(f"  {fam}: {n}")

# Per-outcome counts
oc_counts = Counter(l["outcome"] for l in lines)
for oc, n in oc_counts.most_common():
    print(f"  {oc}: {n}")

# Check source data files
import glob
xauusd_files = glob.glob("data/*XAUUSD*") + glob.glob("data/**/*XAUUSD*", recursive=True)
print(f"\nXAUUSD data files found: {xauusd_files}")