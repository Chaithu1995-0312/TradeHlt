"""Gate 5 reproducibility-compliance pass: count UNKNOWNs, extract exact record IDs."""
import json
import hashlib
import sys

# ---- CHECK 2: Count the UNKNOWN reachability cells in the adjudication matrix ----
records = []
with open('docs/governance/geometry_semantic_adjudication.jsonl') as f:
    for line in f:
        line = line.strip()
        if line:
            records.append(json.loads(line))

print(f"Total adjudication records: {len(records)}")

# Count UNKNOWNs per reachability field
reachability_fields = [
    'artifact_reachable', 'training_reachable', 'decision_reachable',
    'score_reachable', 'runtime_reachable', 'research_reachable'
]

counts = {}
for field in reachability_fields:
    uk = [r for r in records if r.get(field) == 'UNKNOWN']
    counts[field] = len(uk)
    print(f"  {field} UNKNOWN: {len(uk)}")

# Historical pre-Gate-5: 62 artifact_reachable UNKNOWN + 9 training_reachable UNKNOWN = 71
# But the 62 and 9 may overlap (records can be UNKNOWN in both).
# The session log reports: "artifact_reachable 62 (ALL Gate-5-deferred by design), training_reachable 9"
# These are separate counts from separate fields, possibly on overlapping records.
# The report says "UNKNOWNs collapsed 71→3" meaning unique records with UNKNOWN in at least one field.
# Let's check unique records with UNKNOWN in ANY field:
any_uk_ids = set()
for r in records:
    for field in reachability_fields:
        if r.get(field) == 'UNKNOWN':
            any_uk_ids.add(r['derivation_id'])

# Pre-Gate-5, some records had "gate5_followup" non-empty indicating they were deferred to Gate 5.
# Let's count those.
g5_followup = [r for r in records if r.get('gate5_followup')]
print(f"\nRecords with gate5_followup (deferred to Gate 5): {len(g5_followup)}")

# After Gate 5, what remains UNKNOWN?
# The only remaining UNKNOWNs are 3 decision_reachable UNKNOWN.
post_g5_uk = [r for r in records if r.get('decision_reachable') == 'UNKNOWN']
print(f"\nAfter Gate 5 -- decision_reachable UNKNOWNs: {len(post_g5_uk)}")

# Check if artifact_reachable or training_reachable still have UNKNOWNs
print(f"After Gate 5 -- artifact_reachable UNKNOWNs: {counts['artifact_reachable']}")
print(f"After Gate 5 -- training_reachable UNKNOWNs: {counts['training_reachable']}")

print(f"\n=== FINAL UNKNOWN RECORDS ===")
for r in post_g5_uk:
    print(f"  ID: {r['derivation_id']}")
    print(f"  File: {r['file']}:{r['line']}")
    print(f"  Symbol: {r['target_symbol']}")
    print(f"  Family: {r['semantic_family_id']}")
    print(f"  Relation: {r['semantic_relation']}")
    print(f"  decision_reachable: {r.get('decision_reachable')}")
    print(f"  artifact_reachable: {r.get('artifact_reachable')}")
    print(f"  training_reachable: {r.get('training_reachable')}")
    print(f"  score_reachable: {r.get('score_reachable')}")
    print(f"  evidence: {r.get('reachability_evidence', '')[:100]}")
    print()

# ---- CHECK 1: Compute SHA-256 of the adjudication JSONL ----
sha = hashlib.sha256()
with open('docs/governance/geometry_semantic_adjudication.jsonl', 'rb') as f:
    sha.update(f.read())
print(f"Adjudication JSONL SHA-256: {sha.hexdigest()}")

# Also hash the contradiction report
sha2 = hashlib.sha256()
with open('docs/governance/geometry_contradiction_report.md', 'rb') as f:
    sha2.update(f.read())
print(f"Contradiction report SHA-256: {sha2.hexdigest()}")

# Family registry
sha3 = hashlib.sha256()
with open('docs/governance/geometry_family_registry.json', 'rb') as f:
    sha3.update(f.read())
print(f"Family registry SHA-256: {sha3.hexdigest()}")

# ---- FIND F-050 specific records ----
print("\n=== F-050 RELATED RECORDS ===")
for r in records:
    if 'crt_gaussian_scorer' in r['file']:
        print(f"  {r['derivation_id']} | {r['file']}:{r['line']} | {r['target_symbol']} | relation={r['semantic_relation']}")
    if 'crt_engine_v2' in r['file'] and r['line'] == 1372:
        print(f"  {r['derivation_id']} | {r['file']}:{r['line']} | {r['target_symbol']} | relation={r['semantic_relation']}")

print("\n=== CS-3 RELATED RECORDS ===")
for r in records:
    if 'feature_pipeline' in r['file'] and r['line'] == 214:
        print(f"  {r['derivation_id']} | {r['file']}:{r['line']} | {r['target_symbol']} | relation={r['semantic_relation']}")

print("\n=== FINAL REPORT FOR CHECK 6 ===")
print(f"HISTORICAL_REPORTED_PRE_COUNT = 71")
print(f"MECHANICALLY_REPRODUCIBLE_FINAL_UNKNOWN_COUNT = {len(post_g5_uk)}")
print(f"EXACT_FINAL_UNKNOWN_RECORD_IDS = {[r['derivation_id'] for r in post_g5_uk]}")
print(f"PLACEHOLDER_RECORD_IDS_REMAINING = (report will be checked)")