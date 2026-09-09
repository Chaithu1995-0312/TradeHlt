"""provenance_resolver.py — read-only slot resolution over the EXISTING record systems (Phase 2).

Answers, for one claim-bearing decision, "what does its own record already say?" — without writing
anything and without touching the findings architecture. The resolver only ever produces EXPLICIT
bindings or nothing: it reports what a subject literally carries. Backfill (DERIVED/ATTESTED) is a
separate module, `provenance_derivation.py`, so the two can never be confused.

Result shape deliberately mirrors `src/validation_access/ladder.py` (`RungResult` / `LadderResult`):
per-slot `status` + `summary` + `details` + `blockers` + `evidence_paths`, and an `overall_status`
with an `authority_note`. Reusing that shape means an operator reading a provenance chain reads the
same object they already read for the validation ladder.

Sources, all pre-existing and unmodified:

    FINDING    docs/current-findings.md                        (Contract: / Family: / Evidence:)
    DECISION   docs/governance/build_manifests/*.impact.json   (objective / affected_files)
    PROMOTION  configs/promotion_log.jsonl                     (10 keys, ZERO evidence binding)
    CLOSURE    docs/governance/closure_authority_index.json    (authoritative_artifact)

    hypothesis data/hypothesis_registry.jsonl                  (H-*, findings[] back-links)
    contract   configs/research/measurement_contracts/**       (MC-* / MP-*)
    execution  configs/research/measurement_result_log.jsonl   (run_id + artifact SHAs)

`PROMOTION` resolving to almost nothing is the CORRECT output, not a resolver bug: a promotion line
carries `event`/`reason`/`timestamp`/`version`/`config_id`/`params`/`config_hash`/`score`/
`score_std_dev`/`notes` and nothing that binds it to the evidence it was promoted on. That is the
96.67%-UNKNOWN finding, reproduced rather than papered over.

Authority: reporting only. Grants nothing (CLAUDE.md §6.5).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from governance.provenance_record import (
    EXPLICIT,
    SLOTS,
    UNKNOWN,
    build_binding,
    tracked_paths,
)

_ROOT = Path(__file__).resolve().parents[2]

FINDINGS_DOC = _ROOT / "docs" / "current-findings.md"
MANIFEST_DIR = _ROOT / "docs" / "governance" / "build_manifests"
PROMOTION_LOG = _ROOT / "configs" / "promotion_log.jsonl"
CLOSURE_INDEX = _ROOT / "docs" / "governance" / "closure_authority_index.json"
HYPOTHESIS_REGISTRY = _ROOT / "data" / "hypothesis_registry.jsonl"
FAMILY_REGISTRY = _ROOT / "docs" / "governance" / "research_family_registry.json"
MC_DIR = _ROOT / "configs" / "research" / "measurement_contracts"
RESULT_LOG = _ROOT / "configs" / "research" / "measurement_result_log.jsonl"

#: Prefixes that count as EVIDENCE. `src/` and `configs/` are change TARGETS, not evidence — the
#: audit's own precedence decision, reused so both instruments agree on what "evidence" means.
#: Including them would inflate the slot with files a decision EDITED rather than artifacts that
#: JUSTIFIED it.
EVIDENCE_PREFIXES: tuple[str, ...] = (
    "docs/analysis/", "docs/research/", "docs/research-readiness/",
    "results/", "reports/", "tests/", "scripts/analysis/", "scripts/research/",
)

#: A manifest listing its own directory is bookkeeping, not evidence.
EVIDENCE_EXCLUDE_PREFIXES: tuple[str, ...] = ("docs/governance/build_manifests/",)

_FIELD_RE = re.compile(r"^-\s+(Contract|Family|Evidence):\s*(.+?)\s*$", re.M)
_FINDING_HEAD_RE = re.compile(r"^###\s+(F-\d{3})\b", re.M)
_PATH_RE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|json|jsonl|py|csv|yaml|yml|parquet|xlsx))`")
_HID_RE = re.compile(r"\bH-\d{3}\b")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")

PASS, PARTIAL, ABSENT = "RESOLVED", "DANGLING", "UNRESOLVED"


@dataclass
class SlotResult:
    """One slot's resolution. Mirrors validation_access.ladder.RungResult deliberately."""

    slot: str
    status: str                                   # RESOLVED | DANGLING | UNRESOLVED
    summary: str
    bindings: list[dict] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChainResult:
    """The four slots for one subject, plus the derived classification."""

    subject_type: str
    subject_id: str
    source_path: str
    source_sha256: Optional[str]
    slots: dict[str, SlotResult]
    chain_class: str
    chain_complete: bool
    authority_note: str = (
        "Reporting only. A complete chain means the ORIGIN of this claim is recoverable — never "
        "that the claim is true, economic, or authorised (CLAUDE.md §6.5)."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def bindings_by_slot(self) -> dict[str, Any]:
        """Shape accepted by provenance_record.build_record."""
        out: dict[str, Any] = {}
        for slot in SLOTS:
            found = self.slots[slot].bindings
            out[slot] = found if slot == "evidence" else (found[0] if found else None)
        return out


# --- shared loaders -----------------------------------------------------------------------------


def _sha256(path: Path) -> Optional[str]:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def finding_blocks() -> dict[str, str]:
    """{F-id: block text} from the AUTHORITATIVE doc. Read-only; the doc is never modified."""
    try:
        text = FINDINGS_DOC.read_text(encoding="utf-8")
    except OSError:
        return {}
    marks = [(m.group(1), m.start()) for m in _FINDING_HEAD_RE.finditer(text)]
    out: dict[str, str] = {}
    for i, (fid, start) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        out[fid] = text[start:end]
    return out


def contract_ids_and_hashes() -> tuple[dict[str, str], dict[str, str]]:
    """({contract_id: rel_path}, {content_sha256: contract_id}) over every MC-*/MP-* on disk."""
    ids: dict[str, str] = {}
    hashes: dict[str, str] = {}
    if not MC_DIR.is_dir():
        return ids, hashes
    for p in sorted(MC_DIR.rglob("*.json")):
        try:
            raw = p.read_bytes()
            body = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError):
            continue
        cid = body.get("contract_id") or body.get("profile_id")
        if isinstance(cid, str) and cid.startswith(("MC-", "MP-")):
            ids[cid] = _rel(p)
            hashes[hashlib.sha256(raw).hexdigest()] = cid
    return ids, hashes


def executions_by_contract() -> dict[str, list[dict]]:
    """{contract_id: [result-log line, ...]} — the MEASUREMENT EXECUTION slot's source."""
    out: dict[str, list[dict]] = {}
    try:
        text = RESULT_LOG.read_text(encoding="utf-8")
    except OSError:
        return out
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("kind") == "MEASUREMENT_RESULT":
            out.setdefault(str(rec.get("contract_id")), []).append(rec)
    return out


def hypotheses() -> list[dict]:
    try:
        text = HYPOTHESIS_REGISTRY.read_text(encoding="utf-8")
    except OSError:
        return []
    rows = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        if isinstance(rec, dict) and str(rec.get("id", "")).startswith("H-"):
            rows.append(rec)
    return rows


def _is_evidence(path: str) -> bool:
    if path.startswith(EVIDENCE_EXCLUDE_PREFIXES):
        return False
    return path.startswith(EVIDENCE_PREFIXES)


# --- slot resolution ----------------------------------------------------------------------------


def _slot_from_bindings(slot: str, bindings: list[dict], summary: str,
                        details: Optional[dict] = None) -> SlotResult:
    if not bindings:
        return SlotResult(slot, ABSENT, summary, [], [], details or {})
    resolving = [b for b in bindings if b["resolves"]]
    if resolving:
        return SlotResult(slot, PASS, summary, bindings, [], details or {})
    return SlotResult(
        slot, PARTIAL,
        summary + " — named, but nothing resolves",
        bindings,
        [f"{b['target_id']} does not resolve" for b in bindings],
        details or {},
    )


def _resolve_evidence(text: str, declared: Iterable[str], tracked: frozenset[str],
                      *, declared_are_authoritative: bool = False) -> SlotResult:
    """EXPLICIT evidence = a path the subject's own record names, that is evidence-class AND tracked.

    An untracked path is recorded with `resolves: false` rather than dropped: a dangling citation
    must stay visible (39 of 374 finding evidence refs are untracked today).

    `declared_are_authoritative` distinguishes the audit's own two rules. A path in a DEDICATED
    field that exists to name the evidence — a closure surface's `authoritative_artifact` — IS the
    evidence whatever tree it lives in, so the prefix filter is bypassed for it (rule
    E1_STRUCTURED_FIELD). A manifest's `affected_files[]` is a list of change TARGETS and keeps the
    filter (rule E2 plus the audit's `src/`-and-`configs/`-are-not-evidence precedence). Applying
    one rule to both surfaces is what left every closure with zero evidence.
    """
    candidates: list[str] = []
    for path in declared:
        p = str(path).replace("\\", "/")
        keep = (not p.startswith(EVIDENCE_EXCLUDE_PREFIXES)) if declared_are_authoritative \
            else _is_evidence(p)
        if keep and p not in candidates:
            candidates.append(p)
    for m in _PATH_RE.finditer(text or ""):
        p = m.group(1).replace("\\", "/")
        if _is_evidence(p) and p not in candidates:
            candidates.append(p)

    bindings = []
    for p in candidates:
        resolves = p in tracked
        bindings.append(build_binding(
            slot="evidence", target_id=p, resolution=EXPLICIT, resolves=resolves,
            witness=p,
            target_sha256=_sha256(_ROOT / p) if resolves else None,
        ))
    return _slot_from_bindings(
        "evidence", bindings,
        f"{len(bindings)} evidence-class path(s) cited by the record itself",
        {"untracked": [b["target_id"] for b in bindings if not b["resolves"]]},
    )


def _resolve_hypothesis(text: str, known: set[str]) -> SlotResult:
    """EXPLICIT hypothesis = the subject literally cites an H-id that exists.

    The registry BACK-LINK (hypothesis.findings[] naming this finding) is deliberately NOT resolved
    here: that is rule D3, a reconstruction through a registry whose 18-of-20 records were authored
    on one day about completed work. Reproducible is not contemporaneous, so it belongs to
    derivation, not to EXPLICIT.
    """
    cited = []
    for m in _HID_RE.finditer(text or ""):
        if m.group(0) not in cited:
            cited.append(m.group(0))
    if not cited:
        return SlotResult("hypothesis", ABSENT, "no H-id cited by the record itself")
    hid = cited[0]
    binding = build_binding(
        slot="hypothesis", target_id=hid, resolution=EXPLICIT, resolves=hid in known, witness=hid,
    )
    return _slot_from_bindings("hypothesis", [binding], f"cites {hid}",
                               {"also_cited": cited[1:]})


def _resolve_contract(contract_field: Optional[str], ids: dict[str, str],
                      tracked: Optional[frozenset[str]] = None) -> SlotResult:
    """EXPLICIT contract = the record names an MC-*/MP-* id that exists.

    A bare sha256 is NOT resolved here — that is rule D1 (content-hash resolution), backfill.
    `UNKNOWN` written literally in the field is honest absence, not a target.
    """
    value = (contract_field or "").strip()
    if not value or value == UNKNOWN:
        return SlotResult("contract", ABSENT,
                          "Contract field absent or literally UNKNOWN (honest)")
    if _SHA_RE.match(value):
        return SlotResult("contract", ABSENT,
                          "Contract is a bare sha256 — content-hash resolution is rule D1 "
                          "(DERIVED), never EXPLICIT",
                          details={"sha256": value})
    # A contract must be GIT-TRACKED to resolve, exactly as an evidence path must. Until
    # 2026-08-27 this checked the filesystem only, so an untracked instance resolved on the author's
    # machine and vanished in every other clone — and the resolver could not warn about the very
    # gap it exists to surface. MC-ASYM (F-091) and MC-MRPRIOR (F-094) were in exactly that state:
    # two of the repository's four provenance-complete chains were complete on one disk only.
    # Same instrument as measurement_result_log.scanned_instance_paths, which was already
    # git-ls-files-based; this closes the inconsistency between the two.
    tracked = tracked_paths() if tracked is None else tracked
    rel = ids.get(value)
    is_tracked = bool(rel) and rel in tracked
    binding = build_binding(
        slot="contract", target_id=value, resolution=EXPLICIT, resolves=is_tracked,
        witness=f"- Contract: {value}",
        target_sha256=_sha256(_ROOT / rel) if is_tracked else None,
    )
    result = _slot_from_bindings("contract", [binding], f"names {value}")
    if rel and not is_tracked:
        result.blockers.append(
            f"{rel} exists on disk but is UNTRACKED — it resolves to nothing from any other "
            f"clone (F-071 class)"
        )
    return result


def _resolve_execution(contract_slot: SlotResult, execs: dict[str, list[dict]]) -> SlotResult:
    """EXECUTION resolves only through an already-EXPLICIT contract.

    A contract that resolves but has no result line is the F-083 shape made queryable: DECLARED but
    NEVER EXECUTED. It returns UNRESOLVED with that exact blocker rather than silence.
    """
    if contract_slot.status != PASS or not contract_slot.bindings:
        return SlotResult("execution", ABSENT,
                          "no resolved contract to execute against")
    cid = contract_slot.bindings[0]["target_id"]
    lines = execs.get(cid) or []
    if not lines:
        return SlotResult(
            "execution", ABSENT,
            f"{cid} is declared but has NO result line — declared-but-unexecuted (F-083)",
            blockers=[f"{cid}: no line in configs/research/measurement_result_log.jsonl"],
        )
    line = lines[-1]
    run_id = str(line.get("run_id"))
    binding = build_binding(
        slot="execution", target_id=f"MX-{run_id}", resolution=EXPLICIT, resolves=True,
        witness=f"{cid} run {run_id} mt00={line.get('trust_mt00')}",
    )
    return _slot_from_bindings(
        "execution", [binding],
        f"{cid} executed: mt00={line.get('trust_mt00')} "
        f"mt01={line.get('trust_mt01_matrix_coverage')}",
        {"economic_claims_allowed": line.get("economic_claims_allowed", False)},
    )


# --- subjects ------------------------------------------------------------------------------------


def _chain(subject_type: str, subject_id: str, source_path: str,
           source_sha256: Optional[str], slots: dict[str, SlotResult]) -> ChainResult:
    from governance.provenance_record import classify_chain

    shaped = {
        s: (slots[s].bindings if s == "evidence"
            else (slots[s].bindings[0] if slots[s].bindings else None))
        for s in SLOTS
    }
    chain_class, complete = classify_chain(shaped)
    return ChainResult(subject_type, subject_id, source_path, source_sha256,
                       slots, chain_class, complete)


def resolve_finding(fid: str, *, blocks: Optional[dict[str, str]] = None) -> ChainResult:
    blocks = blocks if blocks is not None else finding_blocks()
    text = blocks.get(fid, "")
    fields = {k.lower(): v for k, v in _FIELD_RE.findall(text)}
    tracked = tracked_paths()
    ids, _ = contract_ids_and_hashes()
    known_h = {h["id"] for h in hypotheses()}

    contract = _resolve_contract(fields.get("contract"), ids, tracked)
    slots = {
        "evidence": _resolve_evidence(text, [], tracked),
        "hypothesis": _resolve_hypothesis(text, known_h),
        "contract": contract,
        "execution": _resolve_execution(contract, executions_by_contract()),
    }
    return _chain("FINDING", fid, _rel(FINDINGS_DOC), _sha256(FINDINGS_DOC), slots)


def resolve_decision(change_id: str) -> ChainResult:
    path = MANIFEST_DIR / f"{change_id}.impact.json"
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        body, text = {}, ""
    tracked = tracked_paths()
    ids, _ = contract_ids_and_hashes()
    known_h = {h["id"] for h in hypotheses()}

    contract = _resolve_contract(body.get("measurement_contract"), ids, tracked)
    slots = {
        "evidence": _resolve_evidence(text, body.get("affected_files") or [], tracked),
        "hypothesis": _resolve_hypothesis(text, known_h),
        "contract": contract,
        "execution": _resolve_execution(contract, executions_by_contract()),
    }
    return _chain("DECISION", change_id, _rel(path), _sha256(path), slots)


def promotion_lines() -> list[dict]:
    try:
        text = PROMOTION_LOG.read_text(encoding="utf-8")
    except OSError:
        return []
    rows = []
    for raw in text.splitlines():
        raw = raw.strip()
        if raw:
            try:
                rows.append(json.loads(raw))
            except ValueError:
                continue
    return rows


def resolve_promotion(timestamp: str) -> ChainResult:
    """A promotion line's natural key is its `timestamp`. The line schema is NEVER modified."""
    line = next((r for r in promotion_lines() if r.get("timestamp") == timestamp), {})
    text = json.dumps(line, ensure_ascii=False)
    tracked = tracked_paths()
    ids, _ = contract_ids_and_hashes()

    contract = _resolve_contract(None, ids, tracked)
    slots = {
        "evidence": _resolve_evidence(text, [], tracked),
        "hypothesis": _resolve_hypothesis(text, {h["id"] for h in hypotheses()}),
        "contract": contract,
        "execution": _resolve_execution(contract, executions_by_contract()),
    }
    for slot in slots.values():
        if slot.status == ABSENT:
            slot.blockers.append(
                "a promotion line carries no field that could bind it to evidence — nothing to "
                "derive FROM (see MPA §G: ATTESTED is the only honest path here)"
            )
    return _chain("PROMOTION", timestamp, _rel(PROMOTION_LOG), _sha256(PROMOTION_LOG), slots)


def closure_surfaces() -> list[dict]:
    try:
        return json.loads(CLOSURE_INDEX.read_text(encoding="utf-8")).get("surfaces", [])
    except (OSError, ValueError):
        return []


def resolve_closure(surface_id: str) -> ChainResult:
    surface = next((s for s in closure_surfaces() if s.get("surface_id") == surface_id), {})
    text = json.dumps(surface, ensure_ascii=False)
    declared = [surface["authoritative_artifact"]] if surface.get("authoritative_artifact") else []
    tracked = tracked_paths()
    ids, _ = contract_ids_and_hashes()

    contract = _resolve_contract(None, ids, tracked)
    slots = {
        "evidence": _resolve_evidence(text, declared, tracked,
                                      declared_are_authoritative=True),
        "hypothesis": _resolve_hypothesis(text, {h["id"] for h in hypotheses()}),
        "contract": contract,
        "execution": _resolve_execution(contract, executions_by_contract()),
    }
    return _chain("CLOSURE", surface_id, _rel(CLOSURE_INDEX), _sha256(CLOSURE_INDEX), slots)


def resolve(subject_type: str, subject_id: str) -> ChainResult:
    dispatch = {
        "FINDING": resolve_finding,
        "DECISION": resolve_decision,
        "PROMOTION": resolve_promotion,
        "CLOSURE": resolve_closure,
    }
    if subject_type not in dispatch:
        raise ValueError(f"unknown subject_type {subject_type!r}")
    return dispatch[subject_type](subject_id)


def all_subjects() -> list[tuple[str, str]]:
    """Every subject the four record systems currently contain."""
    out: list[tuple[str, str]] = []
    out.extend(("FINDING", fid) for fid in sorted(finding_blocks()))
    out.extend(("DECISION", p.name[: -len(".impact.json")])
               for p in sorted(MANIFEST_DIR.glob("*.impact.json")))
    out.extend(("PROMOTION", str(r.get("timestamp"))) for r in promotion_lines()
               if r.get("timestamp"))
    out.extend(("CLOSURE", str(s.get("surface_id"))) for s in closure_surfaces()
               if s.get("surface_id"))
    return out
