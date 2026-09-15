"""
feature_dag_certify.py — bottom-up certification mutation engine + transitive invalidation.

Appends the mutation events (CERTIFIED / PROMOTED / INVALIDATED_STALE / BLOCKED) that move the
feature-certification frontier, enforcing the governing invariants:

  * ORDERING GATE (invariant 1): a feature cannot be CERTIFIED while any direct dependency is not
    PROMOTED_PRODUCTION.
  * VALIDATE-AGAINST-PROMOTED (invariant 2): dependency_contract_hash binds a certification to the
    exact promoted formula_hash of each direct dependency.
  * CONTAGIOUS PROMOTION (invariant 3): promoting/correcting a formula whose hash changes marks
    every transitive downstream certification STALE (dependency_contract_hash no longer resolves).
  * DESCRIPTIVE (invariant 5): promotion authority is attributed to promotion_manager.py /
    qualification.py; the ledger sets no runtime value.

Content hash = the canonical sha256(json.dumps(x, sort_keys=True)) used across the repo
(promotion_manager._compute_config_hash / config_integrity.params_fingerprint). formula_hash is a
WITNESS of the frozen callable (the kernel stays code-frozen per §6.5 STRUCTURAL) — it does not make
the formula config-driven.

Pure planners (compute_*/transitive_downstream/plan_*) are unit-tested on synthetic state; the CLI
wraps them with ledger I/O.

Usage:
  python scripts/governance/feature_dag_certify.py status
  python scripts/governance/feature_dag_certify.py hashes [<feature>]
  python scripts/governance/feature_dag_certify.py certify <feature> [--evidence <artifact>] [--verdict CERTIFIED]
  python scripts/governance/feature_dag_certify.py promote <feature> --authority src/governance/promotion_manager.py
  python scripts/governance/feature_dag_certify.py invalidate <feature> [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# reuse the ledger + resolver from the sibling module
_STATE_PATH = _ROOT / "scripts" / "governance" / "feature_certification_state.py"
_spec = importlib.util.spec_from_file_location("feature_certification_state", _STATE_PATH)
_fcs = importlib.util.module_from_spec(_spec)
sys.modules["feature_certification_state"] = _fcs
_spec.loader.exec_module(_fcs)

LEDGER = _fcs.LEDGER
_RAW = _fcs._RAW
AUTHORITY_DISCLAIMER = _fcs.AUTHORITY_DISCLAIMER
PROMOTION_AUTHORITY_SOURCES = _fcs.PROMOTION_AUTHORITY_SOURCES


class OrderingViolation(RuntimeError):
    """Raised when an invariant-1/2 precondition is not met."""


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── pure hashing / graph ─────────────────────────────────────────────────────────

def _node_map(dag: dict) -> dict[str, dict]:
    return {nd["name"]: nd for nd in dag["nodes"]}


def compute_formula_hash(feature: str, dag: dict, formula_witness: dict[str, str]) -> str:
    """Witness of the frozen identity: {formula/intended, formula_id, sorted deps}."""
    nd = _node_map(dag)[feature]
    return _sha({
        "formula_id": nd["formula_id"],
        "witness": formula_witness.get(feature, ""),
        "deps": sorted(nd["deps"]),
    })


def compute_dep_contract_hash(feature: str, dag: dict, own_formula_hash: str,
                              promoted_formula_hashes: dict[str, str]) -> str:
    """Binds a certification to the currently-PROMOTED formula_hash of each direct dependency."""
    nd = _node_map(dag)[feature]
    dep_hashes = {d: promoted_formula_hashes.get(d) for d in sorted(nd["deps"])}
    return _sha({"own": own_formula_hash, "deps": dep_hashes})


def transitive_downstream(feature: str, dag: dict) -> list[str]:
    """Every feature transitively depending on `feature` (BFS over the used_by transpose)."""
    users: dict[str, list[str]] = {nd["name"]: [] for nd in dag["nodes"]}
    for nd in dag["nodes"]:
        for d in nd["deps"]:
            users.setdefault(d, []).append(nd["name"])
    seen: set[str] = set()
    stack = list(users.get(feature, []))
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(users.get(n, []))
    return sorted(seen)


def _promoted_formula_hashes(state: dict[str, dict]) -> dict[str, str]:
    return {f: s["formula_hash"] for f, s in state.items()
            if s.get("frontier_state") == "PROMOTED_PRODUCTION" and s.get("formula_hash")}


# ── pure planners (return event dicts; raise on invariant violation) ───────────────

def plan_certify(feature: str, state: dict[str, dict], dag: dict, formula_witness: dict[str, str],
                 evidence: dict | None = None) -> dict:
    s = state[feature]
    blocking = s.get("blocking_dependencies", [])
    if blocking:
        raise OrderingViolation(
            f"cannot CERTIFY {feature}: direct dependencies not PROMOTED: {blocking} (invariant 1)")
    promoted = _promoted_formula_hashes(state)
    fh = compute_formula_hash(feature, dag, formula_witness)
    dch = compute_dep_contract_hash(feature, dag, fh, promoted)
    return {
        "event": "CERTIFIED", "feature_name": feature, "formula_id": _node_map(dag)[feature]["formula_id"],
        "layer": s["layer"], "frontier_state": "CERTIFIED",
        "intended_quantity": formula_witness.get(feature, ""),   # established quantity (invariant 4)
        "formula_hash": fh, "dependency_contract_hash": dch, "certified_at": _now(),
        "certification_evidence": evidence or {"artifact": "recorded-inline", "verdict": "CERTIFIED"},
        "timestamp": _now(), "authority": AUTHORITY_DISCLAIMER,
        "reason": "deps promoted; formula + PIT + parity certified against promoted dependency contract",
    }


def plan_promote(feature: str, state: dict[str, dict], dag: dict, formula_witness: dict[str, str],
                 authority: str, supersedes: str | None = None,
                 invalidates_refs: list[str] | None = None) -> tuple[dict, list[dict]]:
    s = state[feature]
    if s.get("frontier_state") != "CERTIFIED":
        raise OrderingViolation(
            f"cannot PROMOTE {feature}: current state {s.get('frontier_state')} != CERTIFIED (invariant 1)")
    if authority not in PROMOTION_AUTHORITY_SOURCES:
        raise OrderingViolation(
            f"promotion authority must be code ({PROMOTION_AUTHORITY_SOURCES}), got {authority} (§6.5)")
    fh = s.get("formula_hash") or compute_formula_hash(feature, dag, formula_witness)
    promote_ev = {
        "event": "PROMOTED", "feature_name": feature, "formula_id": _node_map(dag)[feature]["formula_id"],
        "layer": s["layer"], "frontier_state": "PROMOTED_PRODUCTION",
        "formula_hash": fh, "dependency_contract_hash": s.get("dependency_contract_hash", ""),
        "promotion_authority": authority, "timestamp": _now(), "authority": AUTHORITY_DISCLAIMER,
        "reason": "certified against promoted dependency contract; identity promoted to production-intended",
    }
    # STALE cascade over transitive downstream of BOTH the promoted feature and (if superseding a
    # defective identity) the superseded feature — that is where the real downstream consumers hang.
    stale = cascade_stale(feature, state, dag, trigger="PROMOTED")
    if supersedes:
        stale += cascade_stale(supersedes, state, dag, trigger=f"SUPERSEDED_BY_{feature}")
        promote_ev["supersedes"] = supersedes
        promote_ev["invalidates"] = {"references": invalidates_refs or [],
                                     "note": f"{supersedes} superseded; its downstream evidence is STALE"}
        stale.append({
            "event": "SUPERSEDED", "feature_name": supersedes, "frontier_state": "SUPERSEDED",
            "superseded_by": feature, "timestamp": _now(), "authority": AUTHORITY_DISCLAIMER,
            "invalidates": {"references": invalidates_refs or []},
            "reason": f"{feature} promoted as the production-intended identity for this quantity; "
                      f"downstream evidence/artifacts/thresholds STALE pending L6 activation",
        })
    elif invalidates_refs:
        promote_ev["invalidates"] = {"references": invalidates_refs}
    return promote_ev, stale


def cascade_stale(feature: str, state: dict[str, dict], dag: dict, trigger: str) -> list[dict]:
    """Mark every transitive downstream that was CERTIFIED/PROMOTED as STALE (invariant 3)."""
    out = []
    for d in transitive_downstream(feature, dag):
        st = state.get(d, {}).get("frontier_state")
        if st in ("CERTIFIED", "PROMOTED_PRODUCTION"):
            out.append({
                "event": "INVALIDATED_STALE", "feature_name": d, "frontier_state": "STALE",
                "stale_reason": f"upstream dependency {feature} was {trigger}; dependency_contract_hash no longer resolves",
                "upstream_trigger": feature, "timestamp": _now(), "authority": AUTHORITY_DISCLAIMER,
                "reason": "transitive downstream invalidation (bottom-up invariant 3)",
            })
    return out


def plan_invalidate(feature: str, state: dict[str, dict], dag: dict) -> list[dict]:
    return cascade_stale(feature, state, dag, trigger="INVALIDATED")


# ── ATOMIC family transactions (all-or-none) ──────────────────────────────────────

def plan_certify_family(members: list[str], state: dict[str, dict], dag: dict,
                        formula_witness: dict[str, str], evidence: dict) -> list[dict]:
    """Preflight ALL members, then return the full CERTIFIED event block. Raises (→ caller writes
    NOTHING) if ANY member fails the ordering gate. The family CERTIFICATION is all-or-none."""
    if not evidence or not evidence.get("artifact"):
        raise OrderingViolation("family certify requires an evidence artifact + sha256 (manifest)")
    events: list[dict] = []
    for m in members:
        if m not in state:
            raise OrderingViolation(f"family certify: unknown member {m}")
        events.append(plan_certify(m, state, dag, formula_witness, evidence))  # raises on unpromoted dep
    # all four validated → emit the block (single atomic write by the caller)
    return events


def plan_promote_family(members: list[str], state: dict[str, dict], dag: dict,
                        formula_witness: dict[str, str], authority: str) -> list[dict]:
    """Preflight ALL members are CERTIFIED, then return the full PROMOTED block. Raises (→ write
    NOTHING) if any member is not CERTIFIED. The family PROMOTION is all-or-none."""
    events: list[dict] = []
    for m in members:
        ev, stale = plan_promote(m, state, dag, formula_witness, authority)  # raises if != CERTIFIED
        events.append(ev)
        events.extend(stale)   # new correct identities → no supersession, stale is empty here
    return events


# ── formula witnesses (frozen-code fingerprint source) ────────────────────────────

def _formula_witnesses(dag: dict) -> dict[str, str]:
    """Per-feature witness string = the authoritative intended-quantity/formula identity."""
    return _fcs._intended_quantities(dag)


# ── ledger I/O ─────────────────────────────────────────────────────────────────────

def _append(events: list[dict]) -> None:
    """Single-block append — the whole event list is written in ONE write() call so a family
    block lands atomically (a crash cannot expose a partially-written family)."""
    block = "".join(json.dumps(ev) + "\n" for ev in events)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(block)


def main() -> int:
    ap = argparse.ArgumentParser(description="Feature-DAG certification mutation engine.")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    hp = sub.add_parser("hashes"); hp.add_argument("feature", nargs="?")
    cp = sub.add_parser("certify"); cp.add_argument("feature")
    cp.add_argument("--evidence"); cp.add_argument("--sha256"); cp.add_argument("--verdict", default="CERTIFIED")
    pp = sub.add_parser("promote"); pp.add_argument("feature")
    pp.add_argument("--authority", required=True); pp.add_argument("--supersedes")
    pp.add_argument("--invalidates", help="comma-separated downstream artifact/threshold/finding refs")
    ip = sub.add_parser("invalidate"); ip.add_argument("feature"); ip.add_argument("--dry-run", action="store_true")
    cf = sub.add_parser("certify-family"); cf.add_argument("members", nargs="+")
    cf.add_argument("--evidence", required=True); cf.add_argument("--verdict", default="CERTIFIED")
    pf = sub.add_parser("promote-family"); pf.add_argument("members", nargs="+")
    pf.add_argument("--authority", required=True)
    args = ap.parse_args()

    dag = _fcs._load_dag()
    witness = _formula_witnesses(dag)
    state = _fcs.resolve_state(_fcs.load_events(), dag)

    if args.command == "status":
        _fcs._print_status(state, dag)
        return 0

    if args.command == "hashes":
        promoted = _promoted_formula_hashes(state)
        feats = [args.feature] if args.feature else [nd["name"] for nd in dag["nodes"]]
        for f in feats:
            fh = compute_formula_hash(f, dag, witness)
            dch = compute_dep_contract_hash(f, dag, fh, promoted)
            print(f"{f:26s} formula_hash={fh[:12]}  dep_contract_hash={dch[:12]}")
        return 0

    if args.command == "certify":
        ev_ptr = None
        if args.evidence:
            ev_ptr = {"artifact": args.evidence, "sha256": args.sha256 or "", "verdict": args.verdict}
        try:
            ev = plan_certify(args.feature, state, dag, witness, ev_ptr)
        except OrderingViolation as e:
            print(f"REFUSED: {e}"); return 2
        _append([ev])
        print(f"CERTIFIED {args.feature}  formula_hash={ev['formula_hash'][:12]}")
        return 0

    if args.command == "promote":
        refs = [r.strip() for r in args.invalidates.split(",")] if args.invalidates else None
        try:
            ev, stale = plan_promote(args.feature, state, dag, witness, args.authority,
                                     args.supersedes, refs)
        except OrderingViolation as e:
            print(f"REFUSED: {e}"); return 2
        _append([ev] + stale)
        print(f"PROMOTED {args.feature} (authority {args.authority}); staled {len(stale)} downstream")
        for s in stale:
            print(f"    → {s['event']} {s['feature_name']}")
        return 0

    if args.command == "invalidate":
        stale = plan_invalidate(args.feature, state, dag)
        print(f"invalidate {args.feature} → {len(stale)} transitive downstream marked STALE:")
        for s in stale:
            print(f"    {s['feature_name']}")
        if args.dry_run:
            print("(dry-run — nothing written)")
        else:
            _append(stale)
        return 0

    if args.command == "certify-family":
        ev_path = _ROOT / args.evidence
        if not ev_path.exists():
            print(f"REFUSED: evidence artifact not found: {args.evidence}"); return 2
        sha = hashlib.sha256(ev_path.read_bytes()).hexdigest()
        evidence = {"artifact": args.evidence, "sha256": sha, "verdict": args.verdict}
        try:
            events = plan_certify_family(list(args.members), state, dag, witness, evidence)
        except OrderingViolation as e:
            print(f"REFUSED (family all-or-none — nothing written): {e}"); return 2
        _append(events)   # single atomic block
        print(f"CERTIFIED family ({len(events)}): {', '.join(args.members)}  evidence_sha={sha[:12]}")
        return 0

    if args.command == "promote-family":
        try:
            events = plan_promote_family(list(args.members), state, dag, witness, args.authority)
        except OrderingViolation as e:
            print(f"REFUSED (family all-or-none — nothing written): {e}"); return 2
        _append(events)   # single atomic block
        promoted = [e["feature_name"] for e in events if e["event"] == "PROMOTED"]
        print(f"PROMOTED family ({len(promoted)}): {', '.join(promoted)} (authority {args.authority})")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
