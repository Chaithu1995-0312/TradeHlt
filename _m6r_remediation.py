"""
M6R — FM-025 Provenance Remediation

Append-only provenance-remediation event for FM-025 (liquidity_distance).
No recertification, no repromotion, no formula/ontology/registry modification.

Run: python _m6r_remediation.py
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

LEDGER = Path("docs/governance/feature_certification_ledger.jsonl")
ARTIFACT = Path("docs/governance/feature_dag_structural_certification-2026-07-12.json")

# ── Step 1: Confirm FM-025 ledger state ──────────────────────────────────
lines = LEDGER.read_text(encoding="utf-8").strip().splitlines()

# Find FM-025 CERTIFIED event (line index 108, 0-based = line 109 in display)
fm025_cert_line = None
fm025_cert_idx = None
for i, line in enumerate(lines):
    try:
        ev = json.loads(line)
        if ev.get("event") == "CERTIFIED" and ev.get("feature_name") == "liquidity_distance":
            fm025_cert_line = line
            fm025_cert_idx = i
            break
    except json.JSONDecodeError:
        continue

if fm025_cert_line is None:
    print("ERROR: FM-025 CERTIFIED event not found in ledger")
    raise SystemExit(1)

fm025_cert = json.loads(fm025_cert_line)

# Confirm the empty hash defect
sha = fm025_cert.get("certification_evidence", {}).get("sha256", "MISSING")
if sha != "":
    print(f"ERROR: FM-025 evidence hash is not empty: {sha!r}")
    print("  (may already be remediated — check ledger)")
    raise SystemExit(1)

print(f"FM-025 CERTIFIED event found at ledger line {fm025_cert_idx + 1}")
print(f"  evidence.sha256: {sha!r}  ← empty hash defect confirmed")

# ── Step 2: Compute event identity hash ──────────────────────────────────
original_event_hash = hashlib.sha256(fm025_cert_line.encode("utf-8")).hexdigest()
print(f"  event_identity_hash: {original_event_hash}")

# ── Step 3: Compute artifact SHA-256 ─────────────────────────────────────
artifact_bytes = ARTIFACT.read_bytes()
artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
print(f"  evidence_artifact: {ARTIFACT.name}")
print(f"  evidence_sha256:   {artifact_sha256}")

# ── Step 4: Verify artifact is untracked (not git-committed) ─────────────
import subprocess
r = subprocess.run(
    ["git", "status", "--porcelain", str(ARTIFACT)],
    capture_output=True, text=True, cwd=Path.cwd()
)
artifact_git_status = r.stdout.strip() if r.stdout else ""
is_tracked = "?? " not in artifact_git_status[:3] if artifact_git_status else False
print(f"  artifact_git_tracked: {not artifact_git_status or '??' not in artifact_git_status[:3]}")

# Check if content changed since certification by checking git log
r_log = subprocess.run(
    ["git", "log", "--all", "--oneline", "--", str(ARTIFACT)],
    capture_output=True, text=True, cwd=Path.cwd()
)
has_git_history = bool(r_log.stdout.strip())
print(f"  artifact_git_history: {has_git_history}")

# ── Step 5: Provenance determination ─────────────────────────────────────
# The artifact exists on disk and its content supports the FM-025 claim,
# but it was never committed to git. We CANNOT mechanically prove it is the
# exact artifact used at certification time.
provenance_status = "UNRESOLVED" if not has_git_history else "RESOLVED"
print(f"  provenance_status:   {provenance_status}")
print(f"  → Artifact was never git-committed. Cannot mechanically bind it to the certification event.")
print(f"  → FM-025 PROMOTION STATE = HISTORICALLY PROMOTED")
print(f"  → FM-025 PROVENANCE STATUS = UNRESOLVED")
print(f"  → DOWNSTREAM AUTHORITY = TAINTED_BY_UNRESOLVED_PROVENANCE")

# ── Step 6: Append provenance-remediation event ──────────────────────────
remediation_event = {
    "event": "PROVENANCE_REMEDIATION",
    "target_feature": "liquidity_distance",
    "target_formula": "FM-025",
    "original_event_identity_hash": original_event_hash,
    "original_event_timestamp": fm025_cert.get("certified_at", fm025_cert.get("timestamp", "")),
    "evidence_path": "docs/governance/feature_dag_structural_certification-2026-07-12.json",
    "evidence_sha256": artifact_sha256,
    "evidence_git_tracked": has_git_history,
    "remediation_reason": "empty evidence SHA-256 in original CERTIFIED event — artifact exists on disk but was never git-committed, so mechanical binding is impossible",
    "provenance_status": "UNRESOLVED",
    "certification_identity_changed": "NO",
    "production_behavior_changed": "NO",
    "downstream_authority": "TAINTED_BY_UNRESOLVED_PROVENANCE",
    "effective_action": "documented provenance defect; no recertification or repromotion performed",
    "remediated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),
    "remediation_authority": "M6R / F-054-LD-PROV — research/governance only; grants no runtime/production authority",
}

# Append to ledger
with LEDGER.open("a", encoding="utf-8") as f:
    f.write("\n")
    f.write(json.dumps(remediation_event, ensure_ascii=False) + "\n")

print(f"\n✅ Remediation event appended to {LEDGER.name}")
print(f"   Line: {len(lines) + 2}")  # +1 for zero-index, +1 for newline before

# ── Step 7: Summary ──────────────────────────────────────────────────────
print(f"""
═══════════════════════════════════════════════════════════════
M6R REMEDIATION SUMMARY
═══════════════════════════════════════════════════════════════
  Feature:         liquidity_distance
  Formula:         FM-025
  Original event:  line {fm025_cert_idx + 1} (CERTIFIED)
  Event hash:      {original_event_hash}
  Artifact:        {ARTIFACT.name}
  Artifact SHA-256: {artifact_sha256}
  Git tracked:     {has_git_history}
  Provenance:      {provenance_status}
  Authority:       TAINTED_BY_UNRESOLVED_PROVENANCE
  Action:          Append-only remediation event — no rewrite of history
═══════════════════════════════════════════════════════════════
""")