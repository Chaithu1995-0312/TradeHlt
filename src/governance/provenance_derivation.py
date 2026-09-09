"""provenance_derivation.py — the backfill engine (MPA v1, Phase 3).

**The rule this module exists to obey:** backfill writes `DERIVED` or `ATTESTED`. It NEVER writes
`EXPLICIT`, and it never converts a recorded UNKNOWN into anything. An unresolvable slot is
OMITTED, and the omission is the result.

That is the 2026-08-26 audit's cardinal rule — *"GAPS ARE THE RESULT. No edge is backfilled,
guessed, or filled from a sibling artifact"* — honoured rather than argued with. The audit measures
the ORIGINAL records and is not modified; this module writes a SEPARATE, additive ledger of links a
named rule or a named person stands behind. Two instruments. The audit's UNKNOWN percentages stay
byte-identical after a backfill run, and `tests/test_provenance_ledger.py` asserts exactly that.

**Every rule is named, versioned, and re-runnable.** A DERIVED binding carries `rule_id` +
`rule_version` + the inputs it consumed, so anyone can re-compute it and get the same answer. A rule
that cannot be re-run is a guess wearing a label, and `provenance_record._validate_binding` rejects
a binding naming an unregistered rule.

**Rules are not equally strong, and the weak ones say so.** D3/D4 reconstruct a hypothesis through
`hypothesis_registry`, whose 18-of-20 records were authored on 2026-07-03 about work already
completed. Reproducible is not contemporaneous. Those bindings carry that caveat in their
`derivation.inputs` so a reader cannot mistake a reconstruction for a record.

**Deliberately NOT a rule: promotion evidence.** A promotion line carries no field that could bind
it to evidence, so there is nothing to derive FROM. Deriving one by date proximity would be exactly
the `I3_DATE_COLOCATION` inference the audit already names as its weakest. Promotions are the
natural first ATTESTED candidates and need a human decision (`--attest`).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Optional

from governance.provenance_record import (
    ATTESTED,
    DERIVATION_RULES,
    DERIVED,
    build_binding,
    tracked_paths,
)
from governance import provenance_resolver as R

_ROOT = Path(__file__).resolve().parents[2]

#: Rules that must never be applied to a subject type, with the reason. Enforced, not documented.
FORBIDDEN: dict[str, dict[str, str]] = {
    "PROMOTION": {
        "D5_MANIFEST_AFFECTED_FILES": "a promotion line has no affected_files",
        "D6_FINDING_EVIDENCE_PATHS": "a promotion line has no Evidence block",
    },
}


def _rule(rule_id: str, inputs: list[str], caveat: str = "") -> dict:
    """Assemble the derivation block. `rule_version` comes from the registry, never the caller."""
    block = {"rule_id": rule_id, "rule_version": DERIVATION_RULES[rule_id], "inputs": list(inputs)}
    if caveat:
        block["caveat"] = caveat
    return block


# --- D1: contract by content hash ----------------------------------------------------------------


def d1_contract_content_hash(subject_type: str, subject_id: str,
                             chain: R.ChainResult) -> Optional[dict]:
    """A bare 64-hex `Contract:` resolves to the sealed instance whose FILE bytes hash to it.

    Proven exactly on this repository: all six bare-sha256 Contract fields (F-081, F-090..F-094)
    matched a sealed instance byte-for-byte. The audit reported them as resolving to nothing only
    because its extractor resolves by ID; the links were exact the whole time.
    """
    if subject_type != "FINDING":
        return None
    slot = chain.slots["contract"]
    sha = slot.details.get("sha256")
    if not sha:
        return None
    _, by_hash = R.contract_ids_and_hashes()
    cid = by_hash.get(sha)
    if not cid:
        return None
    ids, _ = R.contract_ids_and_hashes()
    return build_binding(
        slot="contract", target_id=cid, resolution=DERIVED, resolves=True,
        witness=sha,
        target_sha256=sha,
        derivation=_rule("D1_CONTRACT_CONTENT_HASH", [f"sha256({ids[cid]})=={sha}"]),
    )


# --- D2: execution by resolved contract ----------------------------------------------------------


def d2_execution_by_contract(subject_type: str, subject_id: str,
                             chain: R.ChainResult,
                             contract_binding: Optional[dict] = None) -> Optional[dict]:
    """A result-log line for the (possibly D1-derived) contract id proves the run EXECUTED.

    Reads `configs/research/measurement_result_log.jsonl` — the one already-wired gate. An absent
    line is NOT an error here: it is the declared-but-unexecuted state, and it is recorded by
    returning None so the slot stays honestly empty.
    """
    binding = contract_binding or (chain.slots["contract"].bindings[0]
                                   if chain.slots["contract"].bindings else None)
    if not binding or not binding.get("resolves"):
        return None
    cid = binding["target_id"]
    lines = R.executions_by_contract().get(cid) or []
    if not lines:
        return None
    line = lines[-1]
    run_id = str(line.get("run_id"))
    return build_binding(
        slot="execution", target_id=f"MX-{run_id}", resolution=DERIVED, resolves=True,
        witness=f"{cid} run {run_id} mt00={line.get('trust_mt00')}",
        derivation=_rule("D2_EXECUTION_BY_CONTRACT",
                         [f"measurement_result_log.jsonl:{cid}:{run_id}"]),
    )


# --- D3 / D4: hypothesis reconstruction ----------------------------------------------------------

_BACKSEED_CAVEAT = (
    "RECONSTRUCTION, not a contemporaneous link: the H-* registry begins 2026-07-03 and 18 of its "
    "20 records were authored that single day about work already completed. Reproducible is not "
    "contemporaneous."
)


def d3_hypothesis_backlink(subject_type: str, subject_id: str,
                           chain: R.ChainResult) -> Optional[dict]:
    """`hypothesis_registry.findings[]` names this finding, but the finding never cited the H-id."""
    if subject_type != "FINDING":
        return None
    if chain.slots["hypothesis"].bindings:
        return None  # already EXPLICIT — never overwrite a stronger class
    for h in R.hypotheses():
        if subject_id in (h.get("findings") or []):
            return build_binding(
                slot="hypothesis", target_id=str(h["id"]), resolution=DERIVED, resolves=True,
                witness=f"hypothesis_registry[{h['id']}].findings contains {subject_id}",
                derivation=_rule("D3_HYPOTHESIS_BACKLINK",
                                 [f"data/hypothesis_registry.jsonl:{h['id']}"],
                                 _BACKSEED_CAVEAT),
            )
    return None


def d4_family_claim_cell(subject_type: str, subject_id: str,
                         chain: R.ChainResult) -> Optional[dict]:
    """An `RF-*` family cell's `claims[]` names this finding — a family-level QUESTION, not an H-*.

    Weaker than D3 and typed as such: the target is `RF-<family>.<layer>`, never an `H-*`, because
    a research family poses a question and does not state a falsifiable hypothesis.
    """
    if subject_type != "FINDING" or chain.slots["hypothesis"].bindings:
        return None
    try:
        reg = json.loads(R.FAMILY_REGISTRY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for fam in reg.get("families") or []:
        for layer, cell in (fam.get("cells") or {}).items():
            if subject_id in (cell.get("claims") or []):
                target = f"{fam['family_id']}.{layer}"
                return build_binding(
                    slot="hypothesis", target_id=target, resolution=DERIVED, resolves=True,
                    witness=f"research_family_registry[{target}].claims contains {subject_id}",
                    derivation=_rule(
                        "D4_FAMILY_CLAIM_CELL",
                        [f"docs/governance/research_family_registry.json:{target}"],
                        "A family cell poses a QUESTION about an object; it is not a falsifiable "
                        "hypothesis. Weaker than D3.",
                    ),
                )
    return None


# --- D5 / D6: evidence ---------------------------------------------------------------------------


def d5_manifest_affected_files(subject_type: str, subject_id: str,
                               chain: R.ChainResult) -> list[dict]:
    """Evidence-class, git-tracked paths in a manifest's `affected_files[]` that were not cited."""
    if subject_type != "DECISION" or chain.slots["evidence"].bindings:
        return []
    path = R.MANIFEST_DIR / f"{subject_id}.impact.json"
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    tracked = tracked_paths()
    out = []
    for rel in body.get("affected_files") or []:
        p = str(rel).replace("\\", "/")
        if not R._is_evidence(p) or p not in tracked:
            continue
        out.append(build_binding(
            slot="evidence", target_id=p, resolution=DERIVED, resolves=True, witness=p,
            target_sha256=_sha256(_ROOT / p),
            derivation=_rule("D5_MANIFEST_AFFECTED_FILES",
                             [f"{subject_id}.impact.json:affected_files"]),
        ))
    return out


def d6_finding_evidence_paths(subject_type: str, subject_id: str,
                              chain: R.ChainResult) -> list[dict]:
    """Tracked evidence paths in a finding's block that the EXPLICIT pass did not already bind.

    Untracked paths are NOT bound: 39 of 374 finding evidence refs point at nothing from any other
    clone, and a derived binding to one would assert a link that does not exist off this machine.
    """
    if subject_type != "FINDING" or chain.slots["evidence"].bindings:
        return []
    return []  # the EXPLICIT pass already scans the block; nothing further is derivable


def _sha256(path: Path) -> Optional[str]:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


# --- orchestration -------------------------------------------------------------------------------

SINGLE_RULES: tuple[tuple[str, str, Callable], ...] = (
    ("contract", "D1_CONTRACT_CONTENT_HASH", d1_contract_content_hash),
    ("hypothesis", "D3_HYPOTHESIS_BACKLINK", d3_hypothesis_backlink),
    ("hypothesis", "D4_FAMILY_CLAIM_CELL", d4_family_claim_cell),
)

LIST_RULES: tuple[tuple[str, str, Callable], ...] = (
    ("evidence", "D5_MANIFEST_AFFECTED_FILES", d5_manifest_affected_files),
    ("evidence", "D6_FINDING_EVIDENCE_PATHS", d6_finding_evidence_paths),
)


def derive(subject_type: str, subject_id: str,
           chain: Optional[R.ChainResult] = None) -> dict[str, Any]:
    """Return {slot: binding|[bindings]} for slots the EXPLICIT pass left empty. Never EXPLICIT.

    Ordered first-match-wins per slot, mirroring the audit's own classifier design so a slot can
    never accumulate two competing derivations.
    """
    chain = chain or R.resolve(subject_type, subject_id)
    forbidden = FORBIDDEN.get(subject_type, {})
    out: dict[str, Any] = {}

    for slot, rule_id, fn in SINGLE_RULES:
        if slot in out or rule_id in forbidden:
            continue
        if chain.slots[slot].bindings:
            continue  # EXPLICIT already present — a weaker class never overwrites a stronger one
        binding = fn(subject_type, subject_id, chain)
        if binding:
            out[slot] = binding

    # D2 runs after D1 so a content-hash-derived contract can carry its execution with it.
    if not chain.slots["execution"].bindings and "D2_EXECUTION_BY_CONTRACT" not in forbidden:
        binding = d2_execution_by_contract(
            subject_type, subject_id, chain,
            contract_binding=out.get("contract"),
        )
        if binding:
            out["execution"] = binding

    for slot, rule_id, fn in LIST_RULES:
        if slot in out or rule_id in forbidden:
            continue
        bindings = fn(subject_type, subject_id, chain)
        if bindings:
            out[slot] = bindings

    return out


def merged_slots(chain: R.ChainResult, derived: dict[str, Any]) -> dict[str, Any]:
    """EXPLICIT bindings from the chain, plus DERIVED ones only where the chain had none."""
    merged = chain.bindings_by_slot()
    for slot, value in derived.items():
        existing = merged.get(slot)
        if slot == "evidence":
            if not existing:
                merged[slot] = value if isinstance(value, list) else [value]
        elif existing is None:
            merged[slot] = value
    return merged


def attestation_binding(*, slot: str, target_id: str, by: str, utc: str,
                        basis: str, authority: str, resolves: bool = True) -> dict:
    """Build one ATTESTED binding. All four attestation fields are required and validated."""
    return build_binding(
        slot=slot, target_id=target_id, resolution=ATTESTED, resolves=resolves,
        witness=basis,
        attestation={"by": by, "utc": utc, "basis": basis, "authority": authority},
    )
