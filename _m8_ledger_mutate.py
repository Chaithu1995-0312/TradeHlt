"""
M8 / F-054-MACD — Ledger Mutation Script
==========================================
Appends CERTIFIED + PROMOTED events sequentially with DAG recompute between each.
"""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
LEDGER = REPO_ROOT / "docs" / "governance" / "feature_certification_ledger.jsonl"
EVIDENCE_ARTIFACT = REPO_ROOT / "docs" / "governance" / "feature_dag_macd_certification-2026-07-14.json"
ARTIFACT_SHA256 = hashlib.sha256(EVIDENCE_ARTIFACT.read_bytes()).hexdigest()

AUTHORITY = "research/governance only — descriptive certification record; grants no runtime/production authority (§6.5)"

def read_ledger():
    lines = LEDGER.read_text("utf-8").strip().splitlines()
    return [json.loads(l) for l in lines if l.strip()]

def compute_dag(events):
    """Compute latest state and READY/BLOCKED from ledger events."""
    feature_state = {}
    feature_deps = {}
    for e in events:
        fn = e.get("feature_name")
        if not fn:
            continue
        fs = e.get("frontier_state", e.get("event"))
        feature_state[fn] = fs
        if e.get("event") == "SEEDED" and e.get("deps") is not None:
            feature_deps[fn] = set(e["deps"])
        elif e.get("event") == "PROMOTED":
            feature_state[fn] = "PROMOTED_PRODUCTION"
    
    promoted = sum(1 for fs in feature_state.values() if fs == "PROMOTED_PRODUCTION")
    superseded = sum(1 for fs in feature_state.values() if fs == "SUPERSEDED")
    
    ready = sorted([
        f for f, deps in feature_deps.items()
        if feature_state.get(f) != "PROMOTED_PRODUCTION"
        and feature_state.get(f) != "SUPERSEDED"
        and all(feature_state.get(d) == "PROMOTED_PRODUCTION" for d in deps)
    ])
    blocked = sorted([
        f for f, deps in feature_deps.items()
        if feature_state.get(f) != "PROMOTED_PRODUCTION"
        and feature_state.get(f) != "SUPERSEDED"
        and not all(feature_state.get(d) == "PROMOTED_PRODUCTION" for d in deps)
    ])
    
    return {
        "total_nodes": len(feature_state),
        "promoted": promoted,
        "superseded": superseded,
        "ready": ready,
        "blocked": blocked,
        "feature_state": feature_state,
    }

def append_event(event_dict):
    """Append a single event to the ledger."""
    line = json.dumps(event_dict, ensure_ascii=False) + "\n"
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(line)
    return line

def make_certified_event(name, formula_id, layer, layer_name, deps, intended_quantity):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "event": "CERTIFIED",
        "feature_name": name,
        "formula_id": formula_id,
        "layer": layer,
        "layer_name": layer_name,
        "frontier_state": "CERTIFIED",
        "intended_quantity": intended_quantity,
        "dependency_contract": deps,
        "certified_at": now,
        "certification_evidence": {
            "artifact": str(EVIDENCE_ARTIFACT.relative_to(REPO_ROOT).as_posix()),
            "sha256": ARTIFACT_SHA256,
            "verdict": "CERTIFIED",
        },
        "timestamp": now,
        "authority": AUTHORITY,
        "reason": "deps promoted; formula + PIT + parity + determinism + future-mutation certified against promoted dependency contract",
    }

def make_promoted_event(name, formula_id, layer, layer_name, deps, intended_quantity):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "event": "PROMOTED",
        "feature_name": name,
        "formula_id": formula_id,
        "layer": layer,
        "layer_name": layer_name,
        "frontier_state": "PROMOTED_PRODUCTION",
        "intended_quantity": intended_quantity,
        "dependency_contract": deps,
        "promotion_authority": "src/research/qualification.py",
        "timestamp": now,
        "authority": AUTHORITY,
        "reason": "certified against promoted dependency contract; identity promoted to production-intended",
    }

# ── MACD feature metadata ──────────────────────────────────────────────────
MACD_FEATURES = {
    "macd_line": {
        "formula_id": None,
        "layer": 1,
        "layer_name": "L1_rolling_indicator",
        "deps": ["close"],
        "intended_quantity": "EWM(close, span=12, adjust=False).mean() - EWM(close, span=26, adjust=False).mean()",
    },
    "macd_signal": {
        "formula_id": None,
        "layer": 1,
        "layer_name": "L1_rolling_indicator",
        "deps": ["macd_line"],
        "intended_quantity": "EWM(macd_line, span=9, adjust=False).mean()",
    },
    "macd_hist": {
        "formula_id": None,
        "layer": 2,
        "layer_name": "L2_direct_derived",
        "deps": ["macd_line", "macd_signal"],
        "intended_quantity": "macd_line - macd_signal",
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# EXECUTION
# ═══════════════════════════════════════════════════════════════════════════
print("=" * 72)
print("M8 / F-054-MACD — LEDGER MUTATION")
print("=" * 72)

# ── Snapshot before ────────────────────────────────────────────────────────
events_before = read_ledger()
dag_before = compute_dag(events_before)
print(f"\nBefore: {dag_before['promoted']} PROMOTED, {dag_before['superseded']} SUPERSEDED, "
      f"{len(dag_before['ready'])} READY, {len(dag_before['blocked'])} BLOCKED")
print(f"  READY: {dag_before['ready']}")
print(f"  BLOCKED: {dag_before['blocked']}")

# ── STEP 12-13: CERTIFY + PROMOTE macd_line ────────────────────────────────
print("\n--- STEP 12-13: CERTIFY + PROMOTE macd_line ---")
f = MACD_FEATURES["macd_line"]
cert_line = make_certified_event("macd_line", f["formula_id"], f["layer"], f["layer_name"], f["deps"], f["intended_quantity"])
append_event(cert_line)
print(f"  CERTIFIED macd_line appended")

prom_line = make_promoted_event("macd_line", f["formula_id"], f["layer"], f["layer_name"], f["deps"], f["intended_quantity"])
append_event(prom_line)
print(f"  PROMOTED macd_line appended")

# ── STEP 14-15: Recompute DAG, verify macd_signal READY ────────────────────
print("\n--- STEP 14-15: Recompute DAG after macd_line promotion ---")
events_after_line = read_ledger()
dag_after_line = compute_dag(events_after_line)
print(f"  After macd_line: {dag_after_line['promoted']} PROMOTED, {dag_after_line['superseded']} SUPERSEDED, "
      f"{len(dag_after_line['ready'])} READY, {len(dag_after_line['blocked'])} BLOCKED")
print(f"  READY: {dag_after_line['ready']}")
print(f"  BLOCKED: {dag_after_line['blocked']}")

assert "macd_signal" in dag_after_line["ready"], (
    f"Expected macd_signal=READY after macd_line promotion, "
    f"got state={dag_after_line['feature_state'].get('macd_signal')}"
)
print("  macd_signal transitioned BLOCKED → READY ✓")

# ── STEP 16-17: CERTIFY + PROMOTE macd_signal ──────────────────────────────
print("\n--- STEP 16-17: CERTIFY + PROMOTE macd_signal ---")
f = MACD_FEATURES["macd_signal"]
cert_signal = make_certified_event("macd_signal", f["formula_id"], f["layer"], f["layer_name"], f["deps"], f["intended_quantity"])
append_event(cert_signal)
print(f"  CERTIFIED macd_signal appended")

prom_signal = make_promoted_event("macd_signal", f["formula_id"], f["layer"], f["layer_name"], f["deps"], f["intended_quantity"])
append_event(prom_signal)
print(f"  PROMOTED macd_signal appended")

# ── STEP 18-19: Recompute DAG, verify macd_hist READY ──────────────────────
print("\n--- STEP 18-19: Recompute DAG after macd_signal promotion ---")
events_after_signal = read_ledger()
dag_after_signal = compute_dag(events_after_signal)
print(f"  After macd_signal: {dag_after_signal['promoted']} PROMOTED, {dag_after_signal['superseded']} SUPERSEDED, "
      f"{len(dag_after_signal['ready'])} READY, {len(dag_after_signal['blocked'])} BLOCKED")
print(f"  READY: {dag_after_signal['ready']}")
print(f"  BLOCKED: {dag_after_signal['blocked']}")

assert "macd_hist" in dag_after_signal["ready"], (
    f"Expected macd_hist=READY after macd_signal promotion, "
    f"got state={dag_after_signal['feature_state'].get('macd_hist')}"
)
print("  macd_hist transitioned BLOCKED → READY ✓")

# ── STEP 20-21: CERTIFY + PROMOTE macd_hist ────────────────────────────────
print("\n--- STEP 20-21: CERTIFY + PROMOTE macd_hist ---")
f = MACD_FEATURES["macd_hist"]
cert_hist = make_certified_event("macd_hist", f["formula_id"], f["layer"], f["layer_name"], f["deps"], f["intended_quantity"])
append_event(cert_hist)
print(f"  CERTIFIED macd_hist appended")

prom_hist = make_promoted_event("macd_hist", f["formula_id"], f["layer"], f["layer_name"], f["deps"], f["intended_quantity"])
append_event(prom_hist)
print(f"  PROMOTED macd_hist appended")

# ── STEP 22: Final frontier ────────────────────────────────────────────────
print("\n--- STEP 22: Final Frontier ---")
events_final = read_ledger()
dag_final = compute_dag(events_final)
print(f"  Final: {dag_final['promoted']} PROMOTED, {dag_final['superseded']} SUPERSEDED, "
      f"{len(dag_final['ready'])} READY, {len(dag_final['blocked'])} BLOCKED")
print(f"  READY: {dag_final['ready']}")
print(f"  BLOCKED: {dag_final['blocked']}")

# Verify expected final state
assert dag_final["promoted"] == 40, f"Expected 40 PROMOTED, got {dag_final['promoted']}"
assert dag_final["superseded"] == 2, f"Expected 2 SUPERSEDED, got {dag_final['superseded']}"
assert len(dag_final["ready"]) == 6, f"Expected 6 READY, got {len(dag_final['ready'])}"
assert len(dag_final["blocked"]) == 0, f"Expected 0 BLOCKED, got {len(dag_final['blocked'])}"
print("  Frontier verified ✓")

# ── STEP 23: Verify no unexpected invalidation ─────────────────────────────
print("\n--- STEP 23: Invalidation Check ---")
# The only nodes that should have changed state are the MACD family
# All other nodes should be unchanged
for name, state_before in dag_before["feature_state"].items():
    state_after = dag_final["feature_state"].get(name)
    if name in ("macd_line", "macd_signal", "macd_hist"):
        continue  # expected to change
    if state_before != state_after:
        print(f"  UNEXPECTED STATE CHANGE: {name}: {state_before} → {state_after}")
        raise AssertionError(f"Unexpected state change for {name}")
print("  No unexpected state changes ✓")

# ── Final report ───────────────────────────────────────────────────────────
print("\n" + "=" * 72)
print("M8 / F-054-MACD — COMPLETE")
print("=" * 72)
print(f"""
M8_STATUS = COMPLETE

CHECKPOINT_START:
  PROMOTED: {dag_before['promoted']}
  SUPERSEDED: {dag_before['superseded']}
  READY: {len(dag_before['ready'])}
  BLOCKED: {len(dag_before['blocked'])}

TARGETS: macd_line, macd_signal, macd_hist

INTENDED_QUANTITY_ALIGNMENT:
  macd_line:   ALIGNED (executably established, no FM-ID)
  macd_signal: ALIGNED (executably established, no FM-ID)
  macd_hist:   ALIGNED (executably established, no FM-ID)

EXECUTABLE_DEPENDENCY_ALIGNMENT:
  macd_line:   ALIGNED (depends on close)
  macd_signal: ALIGNED (depends on macd_line)
  macd_hist:   ALIGNED (depends on macd_line, macd_signal)

MACD_PARAMETER_AUTHORITY:
  FAST_PERIOD: 12
  SLOW_PERIOD: 26
  SIGNAL_PERIOD: 9
  AUTHORITY_SOURCE: src/features/feature_pipeline.py:290-295
  DRIFT_RISK: NONE

INDEPENDENT_ORACLE: explicit recursive EMA (numpy loop, no pandas ewm)

CERTIFICATION_RESULTS:
  macd_line:   CERTIFIED (parity=PASS, PIT=PASS, future_mutation=PASS, determinism=PASS)
  macd_signal: CERTIFIED (parity=PASS, PIT=PASS, future_mutation=PASS, determinism=PASS)
  macd_hist:   CERTIFIED (parity=PASS, PIT=PASS, future_mutation=PASS, determinism=PASS, algebraic_identity=PASS)

EVIDENCE_ARTIFACT: docs/governance/feature_dag_macd_certification-2026-07-14.json
EVIDENCE_SHA256: {ARTIFACT_SHA256}

LEDGER_EVENTS_APPENDED:
  CERTIFIED macd_line
  PROMOTED macd_line
  CERTIFIED macd_signal
  PROMOTED macd_signal
  CERTIFIED macd_hist
  PROMOTED macd_hist

DAG_TRANSITIONS:
  after macd_line promotion:  macd_signal BLOCKED → READY ✓
  after macd_signal promotion: macd_hist BLOCKED → READY ✓
  after macd_hist promotion:  final frontier verified ✓

INVALIDATIONS: NONE (no unexpected state changes)

CHECKPOINT_END:
  PROMOTED: {dag_final['promoted']}
  SUPERSEDED: {dag_final['superseded']}
  READY: {len(dag_final['ready'])}
  BLOCKED: {len(dag_final['blocked'])}

PRODUCTION_BEHAVIOR_CHANGED: NO

KNOWN_DEBT_UNCHANGED:
  FM-025: HISTORICALLY_PROMOTED (provenance defect unresolved)
  FM-026: PROMOTED (M7V verified)
  GOV_INFRA: deferred

ONTOLOGY_REGISTRATION_DEBT:
  macd_line
  macd_signal
  macd_hist

MUTATIONS:
  _m8_cert_probe.py (new — certification probe script)
  _m8_ledger_mutate.py (new — ledger mutation script)
  docs/governance/feature_dag_macd_certification-2026-07-14.json (new — evidence artifact)
  docs/governance/feature_certification_ledger.jsonl (appended — 6 events)

AMBIGUITIES: NONE

NEXT_AUTHORIZED_ACTION: STOP
""")