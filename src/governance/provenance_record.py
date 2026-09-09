"""provenance_record.py — the Provenance Spine's append-only record (MPA v1, Phase 1).

Closes the hole the 2026-08-26 research-DAG audit measured: the repository had no PLACE to record
why a decision was made. Provenance lived as free text scattered across artifacts never designed to
carry it, so `originating_measurement_basis` was 100% UNKNOWN and `DECISION_PROMOTION` — the only
surface that changes what production runs — was 96.67% UNKNOWN.

A record binds one claim-bearing decision to four typed slots:

    EVIDENCE  ·  HYPOTHESIS  ·  MEASUREMENT CONTRACT  ·  MEASUREMENT EXECUTION

**The contract/execution split is the point.** The audit had ONE `originating_measurement_basis`
slot, so naming a contract and running it were indistinguishable (its `U4_DECLARED_NOT_EXECUTED`
rule fired 56 times). Separating them makes "declared but never executed" a queryable state instead
of a footnote — the same F-083 defect class, promoted to a first-class field.

**Four resolution classes, strongest to weakest, and a slot NEVER silently upgrades:**

    EXPLICIT   the subject's own record names the target and it resolves.
               *** Backfill can never produce this. ***
    DERIVED    mechanically reproducible by a named, versioned rule; re-computable.
    ATTESTED   a human/agent adjudication; records who, when, and on what basis.
    UNKNOWN    no link — recorded by OMISSION, never asserted.

`chain_class` is the WEAKEST non-UNKNOWN class present. One ATTESTED slot makes an ATTESTED chain
however many EXPLICIT slots sit beside it. That is deliberate: it is what stops coverage being
gamed by attesting everything.

**This grants no authority.** `grants_authority` is const false and pinned by a test, mirroring
`economic_claims_allowed` in `measurement_result_log.py`. Provenance completeness is not validity,
is not economic value, and is not authority (CLAUDE.md §6.5). A complete chain says the origin of a
claim is recoverable — never that the claim is true.

**Why this file does not contaminate the audit.** `scripts/analysis/research_dag_provenance.py`
reads the ORIGINAL artifacts and does not read this ledger for classification. Its UNKNOWN
percentages stay honest forever; this ledger's coverage is a second, separately-labelled number.
Two instruments, never averaged.

Design: `docs/governance/MEASUREMENT_PROVENANCE_ARCHITECTURE.md`.
Schema:  `configs/research/provenance/provenance_record.schema.json`.
Sibling: `src/governance/measurement_result_log.py` (this file mirrors its structure deliberately).
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional, Sequence

_ROOT = Path(__file__).resolve().parents[2]

LEDGER = _ROOT / "configs" / "research" / "provenance_ledger.jsonl"

KIND = "PROVENANCE_RECORD"
SCHEMA = "provenance_ledger/1"

#: Subject types. Each has an EXISTING natural key — this layer mints no ids for them.
#: SESSION LOG entries are deliberately absent: 1,052 of the audit's 1,170 decisions are session
#: entries and most record no architectural decision, so admitting them would rebuild the audit's
#: denominator problem inside the ledger. A record may still CITE one as evidence.
SUBJECT_TYPES = frozenset({"FINDING", "DECISION", "PROMOTION", "CLOSURE"})

#: Slot names, in the order the design states them.
SLOTS: tuple[str, ...] = ("evidence", "hypothesis", "contract", "execution")

#: Slots that hold at most one binding. `evidence` is the exception: a claim may rest on several
#: artifacts, and collapsing them would lose which one carried which part.
SINGLE_VALUED = frozenset({"hypothesis", "contract", "execution"})

TARGET_KINDS = {
    "evidence": "EVIDENCE_PATH",
    "hypothesis": "HYPOTHESIS",
    "contract": "CONTRACT",
    "execution": "EXECUTION",
}

EXPLICIT, DERIVED, ATTESTED, UNKNOWN = "EXPLICIT", "DERIVED", "ATTESTED", "UNKNOWN"

#: Weakest LAST. `chain_class` takes the weakest present, so ordering here is load-bearing.
RESOLUTION_ORDER: tuple[str, ...] = (EXPLICIT, DERIVED, ATTESTED)
RESOLUTIONS = frozenset(RESOLUTION_ORDER)

#: Registered derivation rules -> version. A DERIVED binding naming an unregistered rule is
#: REJECTED: a rule that cannot be named cannot be re-run, and a backfill that cannot be re-run is
#: indistinguishable from a guess. Implementations live in `provenance_derivation.py`; the
#: vocabulary lives here so that module can import it without a cycle.
DERIVATION_RULES: dict[str, str] = {
    "D1_CONTRACT_CONTENT_HASH": "1.0.0",
    "D2_EXECUTION_BY_CONTRACT": "1.0.0",
    "D3_HYPOTHESIS_BACKLINK": "1.0.0",
    "D4_FAMILY_CLAIM_CELL": "1.0.0",
    "D5_MANIFEST_AFFECTED_FILES": "1.0.0",
    "D6_FINDING_EVIDENCE_PATHS": "1.0.0",
}

_ATTESTATION_FIELDS: tuple[str, ...] = ("by", "utc", "basis", "authority")

_RECORD_ID_RE = re.compile(r"^PV-\d{8}T\d{6}Z-(?:FINDING|DECISION|PROMOTION|CLOSURE)-[A-Za-z0-9._:-]+$")

META_LINE = {
    "kind": "meta",
    "schema": SCHEMA,
    "authority": "research",
    "grants_authority": False,
    "subject_types": sorted(SUBJECT_TYPES),
    "slots": list(SLOTS),
    "resolution_classes": list(RESOLUTION_ORDER) + [UNKNOWN],
    "note": (
        "Append-only. A correction is a NEW record, never an overwrite. A record proves the ORIGIN "
        "of a claim is recoverable — never that the claim is true, economic, or authorised. "
        "Backfill may write DERIVED or ATTESTED and NEVER EXPLICIT. An unresolvable slot is "
        "OMITTED; the omission is the result."
    ),
}


class ProvenanceError(ValueError):
    """A record violates the append-only / honest-class contract."""


# --- tracked-path resolution ------------------------------------------------------------------


def tracked_paths(root: Path = _ROOT) -> frozenset[str]:
    """Every git-TRACKED path, as forward-slash repo-relative strings.

    Deliberately `git ls-files`, not a filesystem walk: an untracked evidence path points at
    nothing from any other clone. Same instrument as
    `measurement_result_log.scanned_instance_paths` and the findings evidence-resolvability gate —
    the F-071 class this repository keeps re-encountering. This session found MC-ASYM and
    MC-MRPRIOR untracked and therefore invisible to the F-083 gate; that must not recur here.

    Fails CLOSED to an empty set: with no git, nothing resolves, rather than everything.
    """
    try:
        out = subprocess.run(
            ["git", "ls-files"], capture_output=True, text=True, timeout=120,
            check=False, cwd=root,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    return frozenset(line.strip().replace("\\", "/") for line in out.splitlines() if line.strip())


# --- slot bindings ----------------------------------------------------------------------------


def build_binding(
    *,
    slot: str,
    target_id: str,
    resolution: str,
    resolves: bool,
    witness: str = "",
    target_sha256: Optional[str] = None,
    derivation: Optional[Mapping[str, Any]] = None,
    attestation: Optional[Mapping[str, Any]] = None,
) -> dict:
    """Assemble one validated slot binding. `target_kind` is derived from the slot, never passed."""
    if slot not in SLOTS:
        raise ProvenanceError(f"unknown slot {slot!r}; expected one of {list(SLOTS)}")
    binding = {
        "target_kind": TARGET_KINDS[slot],
        "target_id": target_id,
        "resolution": resolution,
        "resolves": bool(resolves),
        "witness": witness,
        "target_sha256": target_sha256,
        "derivation": dict(derivation) if derivation is not None else None,
        "attestation": dict(attestation) if attestation is not None else None,
    }
    _validate_binding(slot, binding)
    return binding


def _validate_binding(slot: str, b: Mapping[str, Any]) -> None:
    if b.get("target_kind") != TARGET_KINDS[slot]:
        raise ProvenanceError(
            f"{slot}: target_kind {b.get('target_kind')!r} != {TARGET_KINDS[slot]!r}")
    if not str(b.get("target_id") or "").strip():
        raise ProvenanceError(f"{slot}: target_id is required")

    resolution = b.get("resolution")
    if resolution not in RESOLUTIONS:
        raise ProvenanceError(
            f"{slot}: resolution must be one of {sorted(RESOLUTIONS)} — UNKNOWN is recorded by "
            f"OMITTING the binding, never by asserting it"
        )

    derivation, attestation = b.get("derivation"), b.get("attestation")

    # INVARIANT 1: DERIVED <=> a registered, versioned rule.
    if resolution == DERIVED:
        if not isinstance(derivation, Mapping):
            raise ProvenanceError(f"{slot}: resolution=DERIVED requires a derivation block")
        rule_id = derivation.get("rule_id")
        if rule_id not in DERIVATION_RULES:
            raise ProvenanceError(
                f"{slot}: derivation.rule_id {rule_id!r} is not a registered rule "
                f"{sorted(DERIVATION_RULES)} — an unnameable rule cannot be re-run, and a backfill "
                f"that cannot be re-run is a guess"
            )
        if derivation.get("rule_version") != DERIVATION_RULES[rule_id]:
            raise ProvenanceError(
                f"{slot}: derivation.rule_version {derivation.get('rule_version')!r} != registered "
                f"{DERIVATION_RULES[rule_id]!r} for {rule_id}"
            )
    elif derivation is not None:
        raise ProvenanceError(f"{slot}: derivation present but resolution is {resolution!r}")

    # INVARIANT 2: ATTESTED <=> all four attestation fields, non-empty.
    if resolution == ATTESTED:
        if not isinstance(attestation, Mapping):
            raise ProvenanceError(f"{slot}: resolution=ATTESTED requires an attestation block")
        missing = [f for f in _ATTESTATION_FIELDS if not str(attestation.get(f) or "").strip()]
        if missing:
            raise ProvenanceError(
                f"{slot}: attestation missing {missing} — an attestation is a claim someone stands "
                f"behind, so it records who, when, on what basis, and under whose authority"
            )
    elif attestation is not None:
        raise ProvenanceError(f"{slot}: attestation present but resolution is {resolution!r}")

    digest = b.get("target_sha256")
    if digest is not None and not (isinstance(digest, str) and len(digest) == 64):
        raise ProvenanceError(f"{slot}: target_sha256 is not a sha256 hex digest")


# --- chain classification ----------------------------------------------------------------------


def classify_chain(slots: Mapping[str, Any]) -> tuple[str, bool]:
    """Return (chain_class, chain_complete). DERIVED, never caller-supplied.

    `chain_complete` requires every one of the four slots to carry at least one binding that
    RESOLVES. A binding that names a target which does not exist is recorded (so the dangling
    citation is visible) but does not complete the chain — the audit's own rule that a dangling
    citation never scores EXPLICIT.
    """
    resolving: list[str] = []
    complete = True
    for slot in SLOTS:
        bindings = _as_list(slots.get(slot))
        ok = [b for b in bindings if b.get("resolves")]
        if not ok:
            complete = False
            continue
        resolving.extend(str(b.get("resolution")) for b in ok)

    if not resolving:
        return UNKNOWN, False
    # Weakest present wins.
    weakest = max(resolving, key=lambda r: RESOLUTION_ORDER.index(r))
    return weakest, complete


def _as_list(value: Any) -> list[dict]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [dict(v) for v in value]
    raise ProvenanceError(f"slot value must be a binding, a list of bindings, or None: {value!r}")


# --- records -------------------------------------------------------------------------------------


def build_record(
    *,
    timestamp: str,
    subject_type: str,
    subject_id: str,
    source_path: str,
    source_sha256: Optional[str] = None,
    slots: Optional[Mapping[str, Any]] = None,
    notes: str = "",
) -> dict:
    """Assemble a validated record. `chain_class`/`chain_complete` are DERIVED, never supplied."""
    if subject_type not in SUBJECT_TYPES:
        raise ProvenanceError(
            f"subject_type {subject_type!r} not in {sorted(SUBJECT_TYPES)}")

    normalised: dict[str, Any] = {}
    for slot in SLOTS:
        bindings = _as_list((slots or {}).get(slot))
        for b in bindings:
            _validate_binding(slot, b)
        if slot in SINGLE_VALUED and len(bindings) > 1:
            raise ProvenanceError(f"{slot} holds at most one binding, got {len(bindings)}")
        normalised[slot] = bindings if slot == "evidence" else (bindings[0] if bindings else None)

    chain_class, chain_complete = classify_chain(normalised)
    stamp = re.sub(r"[^0-9T]", "", timestamp.split(".")[0]).rstrip("Z")[:15]
    slug = re.sub(r"[^A-Za-z0-9._:-]", "-", subject_id)[:48].strip("-") or "unknown"

    record = {
        "record_id": f"PV-{stamp}Z-{subject_type}-{slug}",
        "timestamp": timestamp,
        "kind": KIND,
        "schema": SCHEMA,
        "subject": {
            "type": subject_type,
            "id": subject_id,
            "source_path": source_path,
            "source_sha256": source_sha256,
        },
        "slots": normalised,
        "chain_class": chain_class,
        "chain_complete": chain_complete,
        "authority": "research",
        "grants_authority": False,
        "notes": notes,
    }
    _validate_line(record)
    return record


def _validate_line(line: Mapping[str, Any]) -> None:
    if line.get("kind") != KIND:
        raise ProvenanceError(f"kind must be {KIND!r}")
    if line.get("schema") != SCHEMA:
        raise ProvenanceError(f"schema must be {SCHEMA!r}")
    for key in ("record_id", "timestamp"):
        if not str(line.get(key) or "").strip():
            raise ProvenanceError(f"{key} is required")
    if not _RECORD_ID_RE.match(str(line.get("record_id"))):
        raise ProvenanceError(f"record_id {line.get('record_id')!r} is malformed")

    subject = line.get("subject")
    if not isinstance(subject, Mapping):
        raise ProvenanceError("subject block is required")
    if subject.get("type") not in SUBJECT_TYPES:
        raise ProvenanceError(f"subject.type must be one of {sorted(SUBJECT_TYPES)}")
    for key in ("id", "source_path"):
        if not str(subject.get(key) or "").strip():
            raise ProvenanceError(f"subject.{key} is required")

    # PINNED: this surface never grants authority (CLAUDE.md §6.5). Provenance completeness is not
    # validity. A chain being recoverable says nothing about whether the claim it leads to is true.
    if line.get("grants_authority") is not False:
        raise ProvenanceError("grants_authority is const false on a provenance record")
    if line.get("authority") != "research":
        raise ProvenanceError("authority is const 'research' on a provenance record")

    slots = line.get("slots")
    if not isinstance(slots, Mapping):
        raise ProvenanceError("slots block is required")
    for slot in SLOTS:
        for b in _as_list(slots.get(slot)):
            _validate_binding(slot, b)

    # INVARIANT 3: the computed classification is the only classification.
    expected_class, expected_complete = classify_chain(slots)
    if line.get("chain_class") != expected_class:
        raise ProvenanceError(
            f"chain_class {line.get('chain_class')!r} disagrees with the bindings "
            f"({expected_class!r}) — it is DERIVED, never caller-supplied"
        )
    if line.get("chain_complete") is not expected_complete:
        raise ProvenanceError(
            f"chain_complete {line.get('chain_complete')!r} disagrees with the bindings "
            f"({expected_complete!r}) — it is DERIVED, never caller-supplied"
        )


def append_record(record: Mapping[str, Any], path: Optional[Path] = None) -> None:
    """Append one validated record. Append-only — a correction is a NEW record, never an edit."""
    path = LEDGER if path is None else path
    _validate_line(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(META_LINE, ensure_ascii=False, sort_keys=True) + "\n",
                        encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(record), ensure_ascii=False, sort_keys=True) + "\n")


def iter_records(path: Optional[Path] = None) -> Iterator[dict]:
    """Yield non-meta records in append order. A missing ledger yields nothing."""
    path = LEDGER if path is None else path
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            record = json.loads(raw)
        except ValueError:
            continue
        if isinstance(record, dict) and record.get("kind") == KIND:
            yield record


def records_for(subject_type: str, subject_id: str,
                path: Optional[Path] = None) -> list[dict]:
    """Every record for one subject, in append order — the last is the current correction."""
    return [
        r for r in iter_records(path)
        if (r.get("subject") or {}).get("type") == subject_type
        and (r.get("subject") or {}).get("id") == subject_id
    ]


def current_record(subject_type: str, subject_id: str,
                   path: Optional[Path] = None) -> Optional[dict]:
    """The newest record for a subject, or None. Append-only means last wins."""
    rows = records_for(subject_type, subject_id, path)
    return rows[-1] if rows else None
