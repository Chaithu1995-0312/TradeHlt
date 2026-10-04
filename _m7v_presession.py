"""
M7V Pre-Session: Load maintained authoritative state, verify frontier, capture event data.
"""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
LEDGER = REPO_ROOT / "docs" / "governance" / "feature_certification_ledger.jsonl"
FM026_CERT = REPO_ROOT / "docs" / "governance" / "fm026_certification-2026-07-13.json"
FM026_SESSION_LOG = REPO_ROOT / "docs" / "governance" / "fm026_session_log-2026-07-13.json"
PROBE = REPO_ROOT / "_fm026_cert_probe.py"

print("=" * 72)
print("M7V PRE-SESSION: STATE LOAD")
print("=" * 72)

# ── 1. Frontier verification ──────────────────────────────────────────
from collections import Counter
lines = LEDGER.read_text("utf-8").strip().splitlines()
states = Counter()
events = []
for line in lines:
    try:
        ev = json.loads(line)
        events.append(ev)
        s = ev.get("frontier_state", ev.get("event"))
        if s:
            states[s] += 1
    except json.JSONDecodeError:
        continue

print(f"\nLedger events: {len(events)}")
print(f"Frontier states: {dict(states)}")

# Count promoted (SEEDED PROMOTED_PRODUCTION + PROMOTED events)
promoted = sum(1 for e in events if e.get("frontier_state") == "PROMOTED_PRODUCTION" or e.get("event") == "PROMOTED")
superseded = sum(1 for e in events if e.get("event") == "SUPERSEDED" or e.get("frontier_state") == "SUPERSEDED")
certified = sum(1 for e in events if e.get("frontier_state") == "CERTIFIED")
seeded_raw = sum(1 for e in events if e.get("event") == "SEEDED" and e.get("layer") == -1)
seeded_feature = sum(1 for e in events if e.get("event") == "SEEDED" and e.get("layer", -2) >= 0)
provenance_remediation = sum(1 for e in events if e.get("event") == "PROVENANCE_REMEDIATION")

print(f"  PROMOTED: {promoted}")
print(f"  SUPERSEDED: {superseded}")
print(f"  CERTIFIED: {certified}")
print(f"  SEEDED (raw): {seeded_raw}")
print(f"  SEEDED (features): {seeded_feature}")
print(f"  PROVENANCE_REMEDIATION: {provenance_remediation}")
print(f"  Total unique feature nodes: {seeded_raw + seeded_feature - seeded_raw}")  # rough

# ── 2. FM-026 event detail ────────────────────────────────────────────
print(f"\n--- FM-026 Event Detail ---")
for ev in events:
    if ev.get("feature_name") == "liquidity_pressure_score":
        line_str = json.dumps(ev, ensure_ascii=False)
        eh = hashlib.sha256(line_str.encode("utf-8")).hexdigest()
        ts = ev.get("timestamp", ev.get("certified_at", "?"))
        print(f"  Event: {ev.get('event')}")
        print(f"  Timestamp: {ts}")
        print(f"  Identity hash: {eh}")
        print(f"  Layer: {ev.get('layer')} ({ev.get('layer_name')})")
        if "certification_evidence" in ev:
            ce = ev["certification_evidence"]
            print(f"  Evidence artifact: {ce.get('artifact')}")
            print(f"  Evidence SHA-256: {ce.get('sha256')}")
            print(f"  Evidence verdict: {ce.get('verdict')}")
        if "dependency_contract" in ev:
            print(f"  Dependency contract: {ev.get('dependency_contract')}")
        if "dependency_contract_hash" in ev:
            print(f"  Dependency contract hash: {ev.get('dependency_contract_hash')}")
        if "formula_hash" in ev:
            print(f"  Formula hash: {ev.get('formula_hash')}")
        print()

# ── 3. Evidence artifact check ────────────────────────────────────────
print(f"\n--- Evidence Artifact Check ---")
print(f"  Path: {FM026_CERT}")
print(f"  Exists: {FM026_CERT.exists()}")
if FM026_CERT.exists():
    actual_hash = hashlib.sha256(FM026_CERT.read_bytes()).hexdigest()
    print(f"  Actual SHA-256: {actual_hash}")
    # Compare with ledger
    for ev in events:
        if ev.get("feature_name") == "liquidity_pressure_score" and "certification_evidence" in ev:
            ledger_hash = ev["certification_evidence"].get("sha256", "")
            print(f"  Ledger SHA-256:  {ledger_hash}")
            print(f"  Match: {actual_hash == ledger_hash}")

# ── 4. Git tracking ───────────────────────────────────────────────────
r = subprocess.run(["git", "status", "--porcelain", str(FM026_CERT)], capture_output=True, text=True, cwd=REPO_ROOT)
status = r.stdout.strip()
print(f"  Git tracked: {not status or '??' not in status[:3]}")
print(f"  Git status: '{status[:60] if status else 'tracked'}'")

# ── 5. Session log check ──────────────────────────────────────────────
print(f"\n--- Session Log Check ---")
print(f"  Path: {FM026_SESSION_LOG}")
print(f"  Exists: {FM026_SESSION_LOG.exists()}")
if FM026_SESSION_LOG.exists():
    slog = json.loads(FM026_SESSION_LOG.read_text("utf-8"))
    print(f"  Session type: {slog.get('session_type')}")
    print(f"  Start: {slog.get('session_start_utc')}")
    print(f"  End: {slog.get('session_end_utc')}")
    print(f"  Steps: {len(slog.get('delta_execution', []))}")
    print(f"  Terminal disposition: {slog.get('terminal_disposition')}")
    artifact_hash = slog.get("certification_artifact_hash", "")
    print(f"  Certification artifact hash: {artifact_hash}")

# ── 6. Probe check ────────────────────────────────────────────────────
print(f"\n--- Probe Script Check ---")
print(f"  Path: {PROBE}")
print(f"  Exists: {PROBE.exists()}")
if PROBE.exists():
    probe_text = PROBE.read_text("utf-8")
    # Check for FM-025 reconstruction pattern
    has_independent_fm025_reconstruction = "liquidity_distance" in probe_text and ("compute" in probe_text or "scalar" in probe_text or "numpy" in probe_text)
    has_pipeline_import = "feature_pipeline" in probe_text
    has_derived_math_import = "derived_math" in probe_text
    print(f"  References liquidity_distance: {'liquidity_distance' in probe_text}")
    print(f"  Has pipeline import: {has_pipeline_import}")
    print(f"  Has derived_math import: {has_derived_math_import}")
    print(f"  Likely independent reconstruction: {has_independent_fm025_reconstruction}")
    # Check the oracle path
    if "oracle" in probe_text.lower():
        print("  Contains oracle/reconstruction pattern")

# ── 7. Forbidden surfaces hash manifest ───────────────────────────────
print(f"\n--- Forbidden Surfaces Hash Manifest ---")
forbidden = [
    "configs/formulas/market_ontology.yaml",
    "src/features/derived_math.py",
    "src/features/feature_pipeline.py",
    "src/features/registry/derived_registry.py",
    "src/features/causal_structure.py",
]
for path_str in forbidden:
    p = REPO_ROOT / path_str
    if p.exists():
        h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        print(f"  {path_str}: {h}...")
    else:
        print(f"  {path_str}: NOT FOUND")

# ── 8. Timestamp ──────────────────────────────────────────────────────
print(f"\nPre-session complete at: {datetime.now(timezone.utc).isoformat()}")
print("=" * 72)