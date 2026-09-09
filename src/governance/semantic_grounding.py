"""semantic_grounding — closed-world claim grounder (Semantic OS L5 companion).

The LLM may reason and communicate freely. It may not introduce a repository noun,
relationship, implementation claim, or evidence claim that this module did not return.

Four claim kinds, closed:

  NOUN             a name/id that must resolve to one authority record
  RELATIONSHIP     a typed join between two already-grounded endpoints
  IMPLEMENTATION   a path (and optional symbol) that must exist on disk
  EVIDENCE         a finding / hypothesis / test / closure surface

Statuses, closed: GROUNDED | UNKNOWN | AMBIGUOUS | UNANSWERABLE

Fail closed. UNKNOWN is the honest answer. Never invent a CN/BD/JN/CT/FM/F-id,
never pick a winner on alias collision, never upgrade a missing join into a fact.

Authority: advisory. Grants no production, promotion, or G001 weight (CLAUDE.md §6.5).
This is not a semantically-executable trading OS.

Usage:
    from governance.semantic_grounding import SemanticGrounder
    g = SemanticGrounder.load()
    hit = g.ground("NOUN", "CN-001")
    hit = g.ground("IMPLEMENTATION", "src/core/engine_runner.py", symbol="EngineRunner")
    hit = g.ground("EVIDENCE", "F-048")
    hit = g.ground("RELATIONSHIP", "owns", source="CN-001", target="BD-001")
"""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from governance.framework_registry import valid_finding_ids
from governance.semantic_os import (
    SemanticOSRegistry,
    change_class_names,
    closure_surface_ids,
    ontology_ids,
)
from governance.semantic_query import AmbiguousAliasError, SemanticIndex

_ROOT = Path(__file__).resolve().parents[2]
_FINDINGS_JSONL = _ROOT / "data" / "findings.jsonl"
_HYPOTHESIS_JSONL = _ROOT / "data" / "hypothesis_registry.jsonl"
_ACTIVE_VERSION = _ROOT / "configs" / "production" / "ACTIVE_VERSION"
_CLOSURE = _ROOT / "docs" / "governance" / "closure_authority_index.json"

CLAIM_KINDS = frozenset({
    "NOUN",
    "RELATIONSHIP",
    "IMPLEMENTATION",
    "EVIDENCE",
    # CH-jsonl-claim-surface PR-2: may a JSONL stream CLOSE this claim? relation=CC-* required.
    "JSONL",
})
GROUNDED, UNKNOWN, AMBIGUOUS, UNANSWERABLE, REFUSED = (
    "GROUNDED",
    "UNKNOWN",
    "AMBIGUOUS",
    "UNANSWERABLE",
    # Fifth status. NOT a flavour of UNKNOWN: "in the vocabulary, and this JSONL is forbidden
    # for this claim" is a different fact from "outside the vocabulary". Callers that only
    # check GROUNDED (truth.ground_claim sets passed = status == GROUNDED) fail closed on it.
    "REFUSED",
)
STATUSES = frozenset({GROUNDED, UNKNOWN, AMBIGUOUS, UNANSWERABLE, REFUSED})
PROVEN, HEURISTIC, TEXT_REFERENCE = "PROVEN", "HEURISTIC", "TEXT_REFERENCE"

#: The three measurement-contract claim classes. They take an MC-* id or an instances/ path,
#: resolved through the instance JSON + result log — never through ``stream_for_path``. PR-3.
_MC_CLAIM_CLASSES = frozenset({
    "CC-MC-SCHEMA-SHAPE",
    "CC-MC-RESULT-BINDING",
    "CC-MC-DECLARED-UNEXECUTED",
})

# Closed relation vocabulary. A string outside this set is UNANSWERABLE, not a new kind.
RELATION_KINDS = frozenset(
    {
        "owns",
        "owned_by",
        "member_of",
        "imports",
        "imported_by",
        "cites_ontology",
        "cites_finding",
        "governs",
        "governed_by",
        "journey_step",
        "identity_of",
    }
)

# L0 identity kinds from SEMANTIC_OS_V1_DESIGN.md §2 — closed enum, not file types.
IDENTITY_KINDS = frozenset(
    {
        "MarketStructure",
        "NumericSurface",
        "DecisionAct",
        "OrderGeometry",
        "ConfigIdentity",
        "EvidenceUnit",
        "ResearchProgram",
        "RuntimeModule",
        "AgentAct",
    }
)

# SP- added 2026-08-18 (SK-0 / CH-structural-kernel): structural_predicates + structural_walks.
# ontology_ids() already walks the whole document, so these ids were COLLECTED but not
# RECOGNIZED — grounding returned UNKNOWN for a declared node, the §6.7 gap this closes.
# SPP- added 2026-08-19 (RC-9): structure-profile ids, declared in the sibling
# configs/formulas/structure_profiles.yaml. BOTH halves are required and each is useless alone
# — the regex makes an id RECOGNIZED, ontology_id_sources() makes it COLLECTED. SK-0 shipped
# collected-but-not-recognized; regex-only would be the exact inverse.
_ONTOLOGY_ID_RE = re.compile(r"^(FM|SEM|UNK|RC|IND|SP|SPP)-\d+$")
_FINDING_ID_RE = re.compile(r"^F-\d{3}$")
_HYPOTHESIS_ID_RE = re.compile(r"^H-[A-Z0-9-]+$", re.IGNORECASE)
_OBJ_RE = re.compile(r"^OBJ:(.+)$")


def _read_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        return []
    return out


def _norm_path(raw: str) -> str:
    token = str(raw).strip().replace("\\", "/")
    if token.startswith("OBJ:"):
        token = token[4:]
    return token.lstrip("./")


def _read_jsonl_lines(path: Path):
    """Yield parsed JSONL records, skipping malformed lines. Never raises."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if isinstance(record, dict):
                    yield record
    except OSError:
        return


def _file_symbols(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


@dataclass
class Grounding:
    """One claim's tool-returned authority. Status never overstates the payload."""

    claim_kind: str
    token: str
    status: str
    authority: Optional[str] = None
    record_id: Optional[str] = None
    record_kind: Optional[str] = None
    evidence_class: Optional[str] = None
    artifacts: list[str] = field(default_factory=list)
    payload: dict = field(default_factory=dict)
    caveats: list[str] = field(default_factory=list)
    ungrounded_reason: Optional[str] = None
    # JSONL kind only; None on the four original kinds (additive, no caller breaks).
    refusal_class: Optional[str] = None          # CC-* id when status == REFUSED
    catalog_stream_status: Optional[str] = None  # catalog §11 census label, NEVER a CheckResult

    def to_dict(self) -> dict:
        return {
            "claim_kind": self.claim_kind,
            "token": self.token,
            "status": self.status,
            "authority": self.authority,
            "record_id": self.record_id,
            "record_kind": self.record_kind,
            "evidence_class": self.evidence_class,
            "artifacts": list(self.artifacts),
            "payload": self.payload,
            "caveats": list(self.caveats),
            "ungrounded_reason": self.ungrounded_reason,
            "refusal_class": self.refusal_class,
            "catalog_stream_status": self.catalog_stream_status,
        }


def _hit(
    kind: str,
    token: str,
    *,
    authority: str,
    record_id: str,
    record_kind: str,
    evidence_class: str,
    artifacts: list[str],
    payload: dict,
    caveats: Optional[list[str]] = None,
) -> Grounding:
    return Grounding(
        claim_kind=kind,
        token=token,
        status=GROUNDED,
        authority=authority,
        record_id=record_id,
        record_kind=record_kind,
        evidence_class=evidence_class,
        artifacts=sorted(set(artifacts)),
        payload=payload,
        caveats=list(caveats or []),
    )


def _unknown(kind: str, token: str, reason: str, caveats: Optional[list[str]] = None) -> Grounding:
    return Grounding(
        claim_kind=kind,
        token=token,
        status=UNKNOWN,
        ungrounded_reason=reason,
        caveats=list(caveats or ["UNKNOWN is the honest answer — do not invent a record."]),
    )


def _ambiguous(kind: str, token: str, candidates: list[str]) -> Grounding:
    return Grounding(
        claim_kind=kind,
        token=token,
        status=AMBIGUOUS,
        payload={"candidates": sorted(candidates)},
        ungrounded_reason=f"alias {token!r} is AMBIGUOUS — candidates: {sorted(candidates)}",
        caveats=["Resolution failed closed rather than picking a candidate."],
    )


def _unanswerable(kind: str, token: str, reason: str) -> Grounding:
    return Grounding(
        claim_kind=kind,
        token=token,
        status=UNANSWERABLE,
        ungrounded_reason=reason,
        caveats=["The claim kind or relation is outside the closed vocabulary, or no join is defined."],
    )


def _refused(
    token: str,
    cc_id: str,
    reason: str,
    *,
    catalog_stream_status: Optional[str] = None,
    payload: Optional[dict] = None,
) -> Grounding:
    """A NAMED refusal: this JSONL may not close this claim.

    ``record_id`` is the CC-* id, which already exists in the catalog — so this does not violate
    "never invent a record_id on a non-GROUNDED result". ``evidence_class`` stays TEXT_REFERENCE:
    a refusal is never PROVEN evidence for a market fact.
    """
    return Grounding(
        claim_kind="JSONL",
        token=token,
        status=REFUSED,
        record_id=cc_id,
        record_kind="claim_class",
        evidence_class=TEXT_REFERENCE,
        payload=dict(payload or {}),
        ungrounded_reason=reason,
        caveats=[
            "REFUSED is not GROUNDED and not UNKNOWN — do not use this JSONL as a check.",
        ],
        refusal_class=cc_id,
        catalog_stream_status=catalog_stream_status,
    )


def _contained_repo_path(raw: str, root: Path = _ROOT) -> Optional[Path]:
    """Resolve a repo-relative token inside the repo, or None. NEVER opens the file.

    Absolute tokens, NUL bytes and ``..`` escapes return None so the caller can answer UNKNOWN
    without touching the filesystem. On Windows ``root / "C:/Users/x"`` would otherwise resolve
    outside the repo entirely, which ``is_absolute()`` closes before ``resolve()`` is reached.
    """
    if not raw or "\x00" in raw:
        return None
    candidate = Path(str(raw).strip().replace("\\", "/"))
    if candidate.is_absolute():
        return None
    try:
        resolved = (root / candidate).resolve()
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    return resolved


class SemanticGrounder:
    """Fail-closed resolver over Semantic OS + existing authorities."""

    def __init__(self, registry: SemanticOSRegistry, index: Optional[SemanticIndex] = None) -> None:
        self.registry = registry
        self._index = index
        self._ontology_ids: Optional[set[str]] = None
        self._ontology_id_sources: Optional[dict] = None
        self._finding_ids: Optional[set[str]] = None
        self._findings_rows: Optional[dict[str, dict]] = None
        self._hypotheses: Optional[dict[str, dict]] = None
        self._closure_ids: Optional[set[str]] = None
        self._change_classes: Optional[set[str]] = None

    @classmethod
    def load(cls, rebuild_objects: bool = False) -> "SemanticGrounder":
        registry = SemanticOSRegistry.load()
        index = SemanticIndex.load(rebuild_objects=rebuild_objects)
        return cls(registry, index)

    @property
    def index(self) -> SemanticIndex:
        if self._index is None:
            self._index = SemanticIndex.load()
        return self._index

    @property
    def ontology_ids(self) -> set[str]:
        if self._ontology_ids is None:
            self._ontology_ids = ontology_ids()
        return self._ontology_ids

    @property
    def ontology_id_sources(self) -> dict[str, str]:
        """id -> declaring file. RC-9: ids span the ontology + its external sections."""
        if self._ontology_id_sources is None:
            from governance.semantic_os import ontology_id_sources as _srcs
            self._ontology_id_sources = _srcs()
        return self._ontology_id_sources

    @property
    def finding_ids(self) -> set[str]:
        if self._finding_ids is None:
            self._finding_ids = valid_finding_ids()
        return self._finding_ids

    @property
    def findings_rows(self) -> dict[str, dict]:
        if self._findings_rows is None:
            self._findings_rows = {
                r["id"]: r for r in _read_jsonl(_FINDINGS_JSONL) if r.get("id") and r.get("kind") != "meta"
            }
        return self._findings_rows

    @property
    def hypotheses(self) -> dict[str, dict]:
        if self._hypotheses is None:
            self._hypotheses = {r["id"]: r for r in _read_jsonl(_HYPOTHESIS_JSONL) if r.get("id")}
        return self._hypotheses

    @property
    def closure_ids(self) -> set[str]:
        if self._closure_ids is None:
            self._closure_ids = closure_surface_ids()
        return self._closure_ids

    @property
    def change_classes(self) -> set[str]:
        if self._change_classes is None:
            self._change_classes = change_class_names()
        return self._change_classes

    def ground(
        self,
        claim_kind: str,
        token: str,
        *,
        source: str = "",
        target: str = "",
        symbol: str = "",
        relation: str = "",
    ) -> Grounding:
        kind = str(claim_kind or "").strip().upper()
        if kind not in CLAIM_KINDS:
            return _unanswerable(
                str(claim_kind),
                token,
                f"unknown claim kind {claim_kind!r}; closed set: {sorted(CLAIM_KINDS)}",
            )
        if kind == "NOUN":
            return self.ground_noun(token)
        if kind == "RELATIONSHIP":
            rel = relation or token
            return self.ground_relationship(rel, source, target)
        if kind == "IMPLEMENTATION":
            return self.ground_implementation(token, symbol=symbol or None)
        if kind == "JSONL":
            return self.ground_jsonl(token, relation=relation, source=source, target=target)
        return self.ground_evidence(token)

    # ------------------------------------------------------------------ NOUN

    def ground_noun(self, token: str) -> Grounding:
        raw = str(token or "").strip()
        if not raw:
            return _unknown("NOUN", token, "empty noun")

        obj_match = _OBJ_RE.match(raw)
        if obj_match:
            return self._ground_object_path(obj_match.group(1), display=raw)

        try:
            record = self.registry.get(raw)
        except KeyError:
            record = None
        if record is not None:
            kind = record.get("kind") or "semantic_record"
            artifact = {
                "concept": "docs/governance/semantic_os/concepts.yaml",
                "boundary": "docs/governance/semantic_os/boundaries.yaml",
                "journey": "docs/governance/semantic_os/journeys.yaml",
                "contract": "docs/governance/semantic_os/contracts.yaml",
                "file_identity": "docs/governance/semantic_os/file_identities.yaml",
            }.get(kind, "docs/governance/semantic_os/")
            payload = {
                "id": record.get("id"),
                "kind": kind,
                "name": record.get("name") or record.get("semantic_name"),
                "status": record.get("status"),
                "authority": record.get("authority"),
            }
            if kind == "file_identity":
                payload["physical_path"] = record.get("physical_path")
                payload["filename_semantic_status"] = record.get("filename_semantic_status")
            return _hit(
                "NOUN",
                raw,
                authority=artifact,
                record_id=str(record.get("id")),
                record_kind=str(kind),
                evidence_class=PROVEN,
                artifacts=[artifact],
                payload=payload,
            )

        if _ONTOLOGY_ID_RE.match(raw):
            if raw in self.ontology_ids:
                # RC-9: cite the file that ACTUALLY declares the id. Hard-coding the main
                # ontology would be a false citation for a sibling-declared SPP-*.
                declaring = self.ontology_id_sources.get(
                    raw, "configs/formulas/market_ontology.yaml"
                )
                return _hit(
                    "NOUN",
                    raw,
                    authority=declaring,
                    record_id=raw,
                    record_kind="ontology_id",
                    evidence_class=PROVEN,
                    artifacts=[declaring],
                    payload={"id": raw, "namespace": raw.split("-", 1)[0]},
                )
            return _unknown("NOUN", raw, f"ontology id {raw} is not declared")

        if _FINDING_ID_RE.match(raw):
            return self.ground_evidence(raw)

        if _HYPOTHESIS_ID_RE.match(raw):
            return self.ground_evidence(raw)

        if raw in self.closure_ids:
            return _hit(
                "NOUN",
                raw,
                authority="docs/governance/closure_authority_index.json",
                record_id=raw,
                record_kind="closure_surface",
                evidence_class=PROVEN,
                artifacts=["docs/governance/closure_authority_index.json"],
                payload={"surface_id": raw},
            )

        if raw in self.change_classes:
            return _hit(
                "NOUN",
                raw,
                authority="docs/governance/change_contracts.json",
                record_id=raw,
                record_kind="change_class",
                evidence_class=PROVEN,
                artifacts=["docs/governance/change_contracts.json"],
                payload={"change_class": raw},
            )

        if raw in IDENTITY_KINDS:
            return _hit(
                "NOUN",
                raw,
                authority="docs/governance/SEMANTIC_OS_V1_DESIGN.md",
                record_id=raw,
                record_kind="identity_kind",
                evidence_class=PROVEN,
                artifacts=["docs/governance/SEMANTIC_OS_V1_DESIGN.md"],
                payload={"identity_kind": raw, "layer": "L0"},
                caveats=["L0 kinds are reasoning labels, not file types."],
            )

        if raw in {"ACTIVE_VERSION", "active_version"}:
            version = None
            if _ACTIVE_VERSION.is_file():
                version = _ACTIVE_VERSION.read_text(encoding="utf-8").strip() or None
            if version is None:
                return _unknown("NOUN", raw, "ACTIVE_VERSION pointer missing or empty")
            return _hit(
                "NOUN",
                raw,
                authority="configs/production/ACTIVE_VERSION",
                record_id=version,
                record_kind="ConfigIdentity",
                evidence_class=PROVEN,
                artifacts=["configs/production/ACTIVE_VERSION"],
                payload={"active_version": version},
            )

        path = _norm_path(raw)
        if path.endswith(".py") or path.startswith(("src/", "scripts/", "tests/")):
            impl = self.ground_implementation(path)
            if impl.status == GROUNDED:
                impl.claim_kind = "NOUN"
                impl.token = raw
                return impl

        try:
            resolved = self.index.resolve(raw)
        except AmbiguousAliasError as exc:
            return _ambiguous("NOUN", raw, exc.candidates)
        except KeyError:
            resolved = None
        if resolved:
            return self.ground_noun(resolved)

        return _unknown("NOUN", raw, f"no authority record matches {raw!r}")

    def _ground_object_path(self, path: str, display: str) -> Grounding:
        key = _norm_path(path)
        obj = self.index.objects.get(key)
        disk = (_ROOT / key).is_file()
        # S-1 (semantic + screenshot layer review, 2026-08-16): this used to
        # proceed to GROUNDED whenever EITHER the file was on disk OR a
        # (possibly stale, gitignored, regenerable) projection row existed for
        # it -- so a file that was deleted or renamed after the projection was
        # last built would still ground as PROVEN with on_disk:False. Fail
        # closed on disk absence, matching this module's own docstring
        # ("IMPLEMENTATION a path ... that must exist on disk") and CT-008
        # ("Unknown tokens fail closed").
        if not disk:
            return _unknown("NOUN", display, f"no disk file for {key!r}")
        payload = {"path": key, "on_disk": disk}
        if obj:
            payload["classes"] = obj.get("classes") or []
            payload["functions"] = (obj.get("functions") or [])[:20]
            payload["semantic_id"] = obj.get("semantic_id")
        return _hit(
            "NOUN",
            display,
            authority="data/semantic_os/objects.jsonl" if obj else "disk",
            record_id=f"OBJ:{key}",
            record_kind="object",
            evidence_class=PROVEN,
            artifacts=[key],
            payload=payload,
        )

    # ------------------------------------------------------------------ RELATIONSHIP

    def ground_relationship(self, relation: str, source: str, target: str) -> Grounding:
        rel = str(relation or "").strip().lower()
        if rel not in RELATION_KINDS:
            return _unanswerable(
                "RELATIONSHIP",
                rel,
                f"unknown relation {relation!r}; closed set: {sorted(RELATION_KINDS)}",
            )
        src_raw = str(source or "").strip()
        dst_raw = str(target or "").strip()
        if not src_raw or not dst_raw:
            return _unknown(
                "RELATIONSHIP",
                rel,
                "relationship requires grounded source and target",
            )
        src = self.ground_noun(src_raw)
        dst = self.ground_noun(dst_raw)
        token = f"{src_raw} --{rel}--> {dst_raw}"
        if src.status != GROUNDED:
            return _unknown("RELATIONSHIP", token, f"source not grounded: {src.ungrounded_reason}")
        if dst.status != GROUNDED:
            return _unknown("RELATIONSHIP", token, f"target not grounded: {dst.ungrounded_reason}")

        held, evidence_class, artifacts, detail = self._relation_holds(rel, src, dst)
        if held is None:
            return _unanswerable("RELATIONSHIP", token, detail)
        if not held:
            return _unknown(
                "RELATIONSHIP",
                token,
                detail or "join not present in any authority",
                caveats=["Endpoints exist; the typed join does not. Do not invent the edge."],
            )
        return _hit(
            "RELATIONSHIP",
            token,
            authority=artifacts[0] if artifacts else "semantic_os",
            record_id=token,
            record_kind=rel,
            evidence_class=evidence_class or PROVEN,
            artifacts=artifacts,
            payload={
                "relation": rel,
                "source": src.record_id,
                "target": dst.record_id,
                "detail": detail,
            },
        )

    def _relation_holds(
        self, rel: str, src: Grounding, dst: Grounding
    ) -> tuple[Optional[bool], Optional[str], list[str], str]:
        src_rec = self._record_for(src)
        dst_rec = self._record_for(dst)

        if rel in {"owns", "owned_by"}:
            owner, owned = (src, dst) if rel == "owns" else (dst, src)
            owned_rec = self._record_for(owned)
            owner_id = owner.record_id
            if owned_rec and owned_rec.get("owner_boundary") == owner_id:
                return True, PROVEN, ["docs/governance/semantic_os/concepts.yaml"], "owner_boundary"
            return False, None, [], "owner_boundary does not match"

        if rel == "member_of":
            path = src.payload.get("path") or src.payload.get("physical_path") or src.record_id
            bid = dst.record_id if dst.record_kind == "boundary" else None
            if not bid or not path:
                return False, None, [], "member_of requires a path noun and a boundary"
            members = self.index.boundary_members(bid)
            key = _norm_path(str(path).replace("OBJ:", ""))
            if key in members:
                return True, PROVEN, ["docs/governance/semantic_os/boundaries.yaml"], "boundary member"
            return False, None, [], f"{key} is not a member of {bid}"

        if rel in {"imports", "imported_by"}:
            importer, imported = (src, dst) if rel == "imports" else (dst, src)
            a = self._object_path(importer)
            b = self._object_path(imported)
            if not a or not b:
                return None, None, [], "imports join needs two implementation/object paths"
            obj = self.index.objects.get(a) or {}
            edges = obj.get("imports") or []
            if b in edges:
                return True, PROVEN, [a], "AST import edge"
            if not self.index.objects:
                return None, None, [], "object projection unavailable; import join unanswerable"
            return False, None, [], f"{a} does not import {b}"

        if rel == "cites_ontology":
            concept = src_rec if src.record_kind == "concept" else dst_rec
            oid = dst.record_id if dst.record_kind == "ontology_id" else src.record_id
            if not concept or dst.record_kind != "ontology_id" and src.record_kind != "ontology_id":
                return False, None, [], "cites_ontology requires a concept and an ontology id"
            ids = concept.get("ontology_ids") or []
            if oid in ids:
                return True, PROVEN, ["docs/governance/semantic_os/concepts.yaml"], "ontology_ids"
            return False, None, [], f"{concept.get('id')} does not cite {oid}"

        if rel == "cites_finding":
            concept = src_rec if src.record_kind == "concept" else dst_rec
            fid = dst.record_id if dst.record_kind == "finding" else src.record_id
            if not concept or not fid:
                return False, None, [], "cites_finding requires a concept and a finding"
            cited = set(concept.get("research_findings") or [])
            for assumption in concept.get("assumptions") or []:
                if assumption.get("falsified_by"):
                    cited.add(assumption["falsified_by"])
            for mode in concept.get("failure_modes") or []:
                if mode.get("finding"):
                    cited.add(mode["finding"])
            if fid in cited:
                return True, PROVEN, ["docs/governance/semantic_os/concepts.yaml"], "declared finding FK"
            return False, None, [], f"{concept.get('id')} does not declare {fid}"

        if rel in {"governs", "governed_by"}:
            gov, governed = (src, dst) if rel == "governs" else (dst, src)
            crec = self._record_for(gov)
            if not crec or gov.record_kind != "contract":
                return False, None, [], "governs requires a CT-* source"
            bucket = (
                crec.get("governs_concepts") or []
                if governed.record_kind == "concept"
                else crec.get("governs_boundaries") or []
            )
            if governed.record_id in bucket:
                return True, PROVEN, ["docs/governance/semantic_os/contracts.yaml"], "CT governs"
            return False, None, [], f"{gov.record_id} does not govern {governed.record_id}"

        if rel == "journey_step":
            journey = src_rec if src.record_kind == "journey" else dst_rec
            other = dst if src.record_kind == "journey" else src
            if not journey:
                return False, None, [], "journey_step requires a JN-* endpoint"
            steps = journey.get("steps") or []
            oid = other.record_id
            for step in steps:
                if oid in {step.get("concept"), step.get("boundary"), step.get("step_id")}:
                    return True, PROVEN, ["docs/governance/semantic_os/journeys.yaml"], step.get("step_id")
            return False, None, [], f"{oid} is not a step of {journey.get('id')}"

        if rel == "identity_of":
            ident = src if src.record_kind == "file_identity" else dst
            path_g = dst if ident is src else src
            ident_rec = self._record_for(ident)
            path = path_g.payload.get("path") or path_g.payload.get("physical_path") or path_g.record_id
            if not ident_rec or not path:
                return False, None, [], "identity_of requires a FileIdentity and a path"
            physical = _norm_path(str(ident_rec.get("physical_path") or ""))
            key = _norm_path(str(path).replace("OBJ:", ""))
            if physical == key:
                return True, PROVEN, ["docs/governance/semantic_os/file_identities.yaml"], "physical_path"
            return False, None, [], "FileIdentity path does not match"

        return None, None, [], f"no join evaluator for {rel}"

    def _record_for(self, g: Grounding) -> Optional[dict]:
        if not g.record_id:
            return None
        try:
            return self.registry.get(g.record_id)
        except KeyError:
            return None

    def _object_path(self, g: Grounding) -> Optional[str]:
        if g.record_kind in {"object", "implementation"}:
            return _norm_path(str(g.payload.get("path") or g.record_id or "").replace("OBJ:", ""))
        if g.record_kind == "file_identity":
            rec = self._record_for(g)
            if rec and rec.get("physical_path"):
                return _norm_path(str(rec["physical_path"]))
        if g.payload.get("path"):
            return _norm_path(str(g.payload["path"]))
        if g.payload.get("physical_path"):
            return _norm_path(str(g.payload["physical_path"]))
        return None

    # ------------------------------------------------------------------ IMPLEMENTATION

    def ground_implementation(self, path: str, symbol: Optional[str] = None) -> Grounding:
        key = _norm_path(path)
        if not key:
            return _unknown("IMPLEMENTATION", path, "empty path")
        disk_path = _ROOT / key
        on_disk = disk_path.is_file()
        obj = self.index.objects.get(key)
        identity_id = None
        try:
            identity_id = self.registry.identity_by_path().get(key)
        except Exception:  # noqa: BLE001
            identity_id = None

        # S-1 (semantic + screenshot layer review, 2026-08-16): this used to
        # only bail when BOTH disk and the projection missed, so a path that
        # existed solely as a stale `data/semantic_os/objects.jsonl` row (that
        # file is gitignored, regenerable, and was 8 days staler than
        # concepts.yaml when this was found) proceeded to a GROUNDED /
        # evidence_class=PROVEN hit with `on_disk: False` in its own payload —
        # a claim about a file that does not exist, backed by the module's
        # strongest evidence tier. Contradicts this function's own docstring
        # contract ("a path ... that must exist on disk") and CT-008 ("Unknown
        # tokens fail closed"). The projection alone is never sufficient;
        # disk presence is now required regardless of what the projection
        # says, and symbol lookup (a few lines below) no longer falls back to
        # trusting the projection's stale symbol list when the file is absent.
        if not on_disk:
            return _unknown("IMPLEMENTATION", key, f"no file on disk at {key!r}")

        payload: dict[str, Any] = {
            "path": key,
            "on_disk": on_disk,
            "object_present": obj is not None,
            "semantic_id": identity_id,
        }
        artifacts = [key]
        if identity_id:
            artifacts.append("docs/governance/semantic_os/file_identities.yaml")

        if symbol:
            names = _file_symbols(disk_path)
            if symbol not in names:
                return _unknown(
                    "IMPLEMENTATION",
                    f"{key}::{symbol}",
                    f"symbol {symbol!r} is not defined in {key}",
                )
            payload["symbol"] = symbol
            payload["symbol_present"] = True

        if obj:
            payload["classes"] = obj.get("classes") or []
            payload["parse_error"] = obj.get("parse_error")

        return _hit(
            "IMPLEMENTATION",
            f"{key}::{symbol}" if symbol else key,
            authority="disk+ast",
            record_id=f"OBJ:{key}",
            record_kind="implementation",
            evidence_class=PROVEN,
            artifacts=artifacts,
            payload=payload,
        )

    # ------------------------------------------------------------------ EVIDENCE

    def ground_evidence(self, token: str) -> Grounding:
        raw = str(token or "").strip()
        if not raw:
            return _unknown("EVIDENCE", token, "empty evidence token")

        if _FINDING_ID_RE.match(raw):
            if raw not in self.finding_ids:
                return _unknown("EVIDENCE", raw, f"finding {raw} is not in docs/current-findings.md")
            row = self.findings_rows.get(raw, {})
            status = row.get("status")
            payload = {
                "id": raw,
                "title": row.get("title"),
                "status": status,
                "confidence": row.get("confidence"),
                "in_living_doc": True,
                "jsonl_row": bool(row),
            }
            # S-2 (semantic + screenshot layer review, 2026-08-16): `valid_finding_ids`
            # is documented "terminal included; existence only" — a SUPERSEDED
            # finding grounds exactly like a fresh VALIDATED one, both PROVEN,
            # with the terminality visible only if a caller happens to read
            # `payload["status"]` unprompted. Surface it as a caveat so it
            # can't be missed by a caller that only checks GROUNDED/PROVEN.
            caveats: list[str] = []
            if not row:
                caveats.append(
                    "Living-doc id is real; generated findings.jsonl row is absent this checkout."
                )
            if status and status.upper() in {"SUPERSEDED", "RETIRED", "KILLED", "FROZEN"}:
                caveats.append(
                    f"Finding status is {status} — this is TERMINAL, not the living "
                    f"conclusion (CLAUDE.md 6.2 rule 4: superseded rows are kept, not "
                    f"deleted). Do not cite as current evidence without checking "
                    f"its Reversal/Supersedes fields in docs/current-findings.md."
                )
            return _hit(
                "EVIDENCE",
                raw,
                authority="docs/current-findings.md",
                record_id=raw,
                record_kind="finding",
                evidence_class=PROVEN,
                artifacts=["docs/current-findings.md"]
                + (["data/findings.jsonl"] if row else []),
                payload=payload,
                caveats=caveats,
            )

        if _HYPOTHESIS_ID_RE.match(raw):
            hyp = self.hypotheses.get(raw)
            if hyp is None:
                return _unknown(
                    "EVIDENCE",
                    raw,
                    f"hypothesis {raw} is not in data/hypothesis_registry.jsonl (generated; may be unseeded)",
                )
            return _hit(
                "EVIDENCE",
                raw,
                authority="data/hypothesis_registry.jsonl",
                record_id=raw,
                record_kind="hypothesis",
                evidence_class=PROVEN,
                artifacts=["data/hypothesis_registry.jsonl"],
                payload={
                    "id": raw,
                    "status": hyp.get("status"),
                    "statement": hyp.get("statement"),
                },
            )

        if raw in self.closure_ids:
            surfaces = {}
            try:
                surfaces = {
                    s["surface_id"]: s
                    for s in (json.loads(_CLOSURE.read_text(encoding="utf-8")).get("surfaces") or [])
                    if s.get("surface_id")
                }
            except Exception:  # noqa: BLE001
                surfaces = {}
            surface = surfaces.get(raw, {"surface_id": raw})
            return _hit(
                "EVIDENCE",
                raw,
                authority="docs/governance/closure_authority_index.json",
                record_id=raw,
                record_kind="closure_surface",
                evidence_class=PROVEN,
                artifacts=["docs/governance/closure_authority_index.json"],
                payload={
                    "surface_id": raw,
                    "status": surface.get("status"),
                    "scope_boundary": surface.get("scope_boundary"),
                },
                caveats=["CLOSURE IS BOUNDARY-SCOPED AND NON-TRANSITIVE."],
            )

        test_key = _norm_path(raw)
        if test_key.startswith("tests/") and test_key.endswith(".py"):
            disk = _ROOT / test_key
            if disk.is_file():
                return _hit(
                    "EVIDENCE",
                    test_key,
                    authority="disk",
                    record_id=test_key,
                    record_kind="test_module",
                    evidence_class=PROVEN,
                    artifacts=[test_key],
                    payload={"path": test_key, "on_disk": True},
                    caveats=["A test file existing is not behavioural coverage."],
                )
            return _unknown("EVIDENCE", test_key, f"test path {test_key} is not on disk")

        return _unknown("EVIDENCE", raw, f"no evidence authority matches {raw!r}")

    # ------------------------------------------------------------------ JSONL

    def ground_jsonl(
        self,
        token: str,
        *,
        relation: str = "",
        source: str = "",
        target: str = "",
    ) -> Grounding:
        """Fail closed over the JSONL claim catalog. May this stream CLOSE this claim?

        ``token``    stream path or STR-* id. Empty is legal ONLY for a join-only call (both
                     ``source`` and ``target`` set). Never opened raw — see ``_contained_repo_path``.
        ``relation`` REQUIRED CC-* id. Missing or non-CC-* is UNANSWERABLE: catalog existence is
                     not a check.
        ``source`` / ``target``  join endpoints (``STR-*`` | ``producer:engine`` |
                     ``producer:resolver`` | ``family:*``) when BOTH are non-empty. For
                     ``CC-AGENT-AUDIT-RAN`` only, ``source`` is the tool name and ``target`` must
                     be empty.

        Steps 1-7 are normative and ordered; see docs/governance/JSONL_CLAIM_SURFACE.md §6.
        """
        from governance.jsonl_claim_catalog import (
            ADMITTED,
            NOT_ADMITTED,
            UNKNOWN_CLASS,
            UNKNOWN_STREAM,
            CatalogError,
            load_catalog,
        )

        raw_token = str(token or "").strip()
        rel = str(relation or "").strip()
        src = str(source or "").strip()
        dst = str(target or "").strip()

        try:
            catalog = self._jsonl_catalog()
        except CatalogError as exc:  # fail closed — a broken catalog never grounds
            return _unanswerable("JSONL", raw_token, f"claim catalog is unusable: {exc}")

        # 1. relation required.
        if not rel.startswith("CC-"):
            return _unanswerable(
                "JSONL",
                raw_token,
                "kind=JSONL requires relation=CC-*; catalog existence is not a check",
            )

        # 2. closed vocabulary — never invent a CC-id.
        row = catalog.claim_class(rel)
        if row is None:
            return _unanswerable("JSONL", raw_token, f"unknown claim class {rel!r}; the catalog is closed")

        # 3. join first: two individually-true lines joined illegally is still a hallucination.
        #    A forbidden join REFUSES even when `relation` is a CAN. Token may be empty here.
        if src and dst:
            join_id = catalog.join_cc(src, dst)
            if join_id is not None:
                return _refused(
                    raw_token,
                    join_id,
                    f"forbidden join {src!r} x {dst!r} — this pair cannot form one object",
                    payload={"source": src, "target": dst, "requested_relation": rel},
                )

        # 4. polarity CANNOT is always REFUSED (a stream's forbidden_cc is documentation only).
        if row["polarity"] == "CANNOT":
            return _refused(
                raw_token,
                rel,
                f"{rel}: {row['why']}",
                catalog_stream_status=row["catalog_stream_status"],
                payload={"llm_claim": row["llm_claim"], "against": row["against"],
                         "findings": list(row["findings"])},
            )

        # ---- CAN classes from here on ----

        # 5. token grammar. The three CC-MC-* classes take an MC-* id or an instances/ path and
        #    resolve through the instance JSON + result log; that grammar ships in PR-3.
        if rel in _MC_CLAIM_CLASSES:
            return self._ground_measurement_contract(raw_token, rel)

        if rel == "CC-AGENT-AUDIT-RAN":
            return self._ground_agent_audit_ran(catalog, raw_token, src, dst)

        if rel == "CC-FINDING-EXPORT":
            return self._ground_finding_export(catalog, raw_token)

        # Join-only leftover: step 3 did not refuse and there is nothing to resolve.
        if not raw_token:
            return _unanswerable("JSONL", raw_token, "token required unless the call is join-only")

        stream = catalog.stream_for_path(raw_token)

        # 6. allowed_cc — this stream may simply not close this CAN.
        verdict = catalog.admissibility(stream, rel)
        if verdict == UNKNOWN_CLASS:  # unreachable after step 2; kept so the matrix stays total
            return _unanswerable("JSONL", raw_token, f"unknown claim class {rel!r}")
        if verdict == UNKNOWN_STREAM:
            return _unknown(
                "JSONL",
                raw_token,
                f"{raw_token!r} is not a catalogued stream — do not treat it as a check",
            )
        if verdict == NOT_ADMITTED:
            return _unanswerable(
                "JSONL",
                raw_token,
                f"stream {stream['id']} does not close {rel} (allowed_cc: {stream['allowed_cc']})",
            )
        assert verdict == ADMITTED  # noqa: S101 - the matrix is total; a new member is a bug

        # 7. class-specific extra checks. ADMITTED alone never grounds.
        if rel == "CC-ENVELOPE-SHAPE":
            return self._ground_envelope_shape(stream, raw_token)
        if rel == "CC-PROMOTION-LOG":
            return self._ground_committed_stream(stream, raw_token, rel)
        if rel in ("CC-HYPOTHESIS-REGISTRY", "CC-SCRIPT-REGISTRY", "CC-SEMANTIC-OS"):
            return self._ground_generated_registry(stream, raw_token, rel)
        if rel == "CC-CTX-RUN-SCOPED-OBSERVATION":
            return self._ground_bar_structure_snapshot(stream, raw_token, rel)
        return _unknown("JSONL", raw_token, f"no extra check implemented for {rel}")

    # -- JSONL helpers --

    def _jsonl_catalog(self):
        """Cached catalog handle. Loaded lazily so non-JSONL callers never pay for PyYAML."""
        cached = getattr(self, "_jsonl_catalog_cache", None)
        if cached is None:
            from governance.jsonl_claim_catalog import load_catalog

            cached = load_catalog()
            self._jsonl_catalog_cache = cached
        return cached

    def _ground_measurement_contract(self, raw_token: str, rel: str) -> Grounding:
        """The three CC-MC-* classes. Token is an MC-* id or a contained instances/ path.

        Resolved through the instance JSON + the committed result log — deliberately NOT through
        ``stream_for_path``: an instance is a contract document, not a catalogued JSONL stream.

        SHAPE is not EXECUTION (F-083). ``CC-MC-SCHEMA-SHAPE`` grounds on a valid document even
        when ``mt00`` is ``UNRUN``; ``CC-MC-RESULT-BINDING`` refuses while UNRUN and grounds only
        against a real result line. A ``FAIL`` or ``PARTIAL`` run with an honest line GROUNDS —
        that means the run EXECUTED, not that the experiment passed.
        """
        import json as _json

        from governance import measurement_result_log as _mrl
        from governance.measurement_result_log import classify_l5_basis, sha256_file

        INSTANCE_DIR = _mrl.INSTANCE_DIR
        lines_for_contract = _mrl.lines_for_contract

        # -- token grammar --
        path: Optional[Path] = None
        if raw_token.startswith("MC-"):
            candidate = INSTANCE_DIR / f"{raw_token}.json"
            if candidate.exists():
                path = candidate
        elif "measurement_contracts/instances/" in _norm_path(raw_token):
            path = _contained_repo_path(raw_token)
        else:
            return _unanswerable(
                "JSONL",
                raw_token,
                f"{rel} token must be an MC-* id or a path under "
                "configs/research/measurement_contracts/instances/",
            )
        if path is None or not path.exists():
            return _unknown("JSONL", raw_token, f"no measurement-contract instance for {raw_token!r}")

        try:
            doc = _json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return _unknown("JSONL", raw_token, f"instance is unreadable: {exc}")

        contract_id = doc.get("contract_id") or path.stem
        trust = doc.get("trust_status") or {}
        # The frozen schema's key is `mt01_matrix_coverage`; `trust_status` is
        # additionalProperties:false, so a bare `mt01` cannot exist.
        mt00 = trust.get("mt00")
        rel_path = str(path.relative_to(_ROOT)).replace("\\", "/")

        # -- CC-MC-DECLARED-UNEXECUTED is a CANNOT and never reaches here (step 4 refused it) --

        if rel == "CC-MC-SCHEMA-SHAPE":
            missing = [k for k in ("schema_version", "contract_id", "evidence_artifacts",
                                   "trust_status") if k not in doc]
            if missing:
                return _unknown("JSONL", raw_token, f"instance is missing required keys: {missing}")
            if mt00 not in ("UNRUN", "PASS", "FAIL", "PARTIAL"):
                return _unknown("JSONL", raw_token, f"trust_status.mt00 is not an honest token: {mt00!r}")
            return _hit(
                "JSONL",
                raw_token,
                authority=rel_path,
                record_id=contract_id,
                record_kind="measurement_contract",
                evidence_class=TEXT_REFERENCE,
                artifacts=[rel_path],
                payload={
                    "contract_id": contract_id,
                    "trust_mt00": mt00,
                    "proves": "the document validates against the frozen contract schema",
                    "does_not_prove": "that the measurement ever ran (see CC-MC-RESULT-BINDING)",
                    "authority": "research",
                },
                caveats=["Shape is not execution — UNRUN is a legal, honest shape (F-083)."],
            )

        # -- CC-MC-RESULT-BINDING --
        if mt00 == "UNRUN":
            return _refused(
                raw_token,
                "CC-MC-DECLARED-UNEXECUTED",
                f"{contract_id}: trust_status.mt00 is UNRUN — the measurement has not executed",
                payload={"contract_id": contract_id, "trust_mt00": mt00},
            )

        lines = lines_for_contract(contract_id)
        if not lines:
            return _refused(
                raw_token,
                "CC-MC-DECLARED-UNEXECUTED",
                f"{contract_id}: mt00={mt00!r} but no line in configs/research/"
                "measurement_result_log.jsonl — declared, not evidenced (F-083)",
                payload={"contract_id": contract_id, "trust_mt00": mt00},
            )

        line = lines[-1]
        hashes = line.get("artifact_hashes") or {}
        for key, declared in (doc.get("evidence_artifacts") or {}).items():
            if not declared:
                continue
            if declared not in hashes:
                return _refused(
                    raw_token,
                    "CC-MC-DECLARED-UNEXECUTED",
                    f"{contract_id}: evidence_artifacts.{key} ({declared}) is unbound by the result line",
                    payload={"contract_id": contract_id, "unbound_artifact": declared},
                )
            actual = sha256_file(_ROOT / declared)
            if actual != hashes[declared]:
                return _refused(
                    raw_token,
                    "CC-MC-DECLARED-UNEXECUTED",
                    f"{contract_id}: evidence_artifacts.{key} ({declared}) hash does not match the "
                    "result line",
                    payload={"contract_id": contract_id, "artifact": declared},
                )

        basis_status = classify_l5_basis(line.get("l5_basis"))
        if basis_status == "UNIDENTIFIED":
            return _refused(
                raw_token,
                "CC-L5-UNIDENTIFIED",
                f"{contract_id}: the run-level l5_basis is incomplete or carries an illegal token",
                payload={"contract_id": contract_id, "basis_status": basis_status},
            )

        return _hit(
            "JSONL",
            raw_token,
            authority="configs/research/measurement_result_log.jsonl",
            record_id=contract_id,
            record_kind="measurement_result",
            evidence_class=TEXT_REFERENCE,
            artifacts=[rel_path, "configs/research/measurement_result_log.jsonl"],
            payload={
                "contract_id": contract_id,
                "trust_mt00": mt00,
                "basis_status": basis_status,
                "run_id": line.get("run_id"),
                "authority": "research",
                "proves": "the measurement EXECUTED and its declared artifacts hash-match",
                "does_not_prove": "that it passed, or that its result is economic",
            },
            caveats=[
                "GROUNDED means EXECUTED, not PASSED — a FAIL or PARTIAL run grounds here too.",
                "A run-level basis is not an L5 object and is never PRESERVED.",
            ],
        )

    def _ground_finding_export(self, catalog, raw_token: str) -> Grounding:
        """GROUNDs from the PRIMARY markdown, which is clone-visible.

        Deliberately does NOT require gitignored ``data/findings.jsonl`` — that projection is
        enrichment (see ``ground_evidence``), and a fresh clone must still be able to run this.
        """
        stream = catalog.stream_for_path(raw_token)
        if stream is None or stream["id"] != "STR-FINDINGS-EXPORT":
            return _unanswerable(
                "JSONL",
                raw_token,
                "CC-FINDING-EXPORT token must be docs/current-findings.md, data/findings.jsonl, "
                "or STR-FINDINGS-EXPORT",
            )
        primary = _contained_repo_path(stream["primary_source"])
        if primary is None or not primary.exists():
            return _unknown("JSONL", raw_token, "PRIMARY findings doc is not readable")
        count = len(self.finding_ids)
        if not count:
            return _unknown("JSONL", raw_token, "no finding ids parsed from the PRIMARY doc")
        return _hit(
            "JSONL",
            raw_token,
            authority=stream["primary_source"],
            record_id="CC-FINDING-EXPORT",
            record_kind="claim_class",
            evidence_class=TEXT_REFERENCE,
            artifacts=[stream["primary_source"]],
            payload={
                "proves": "the finding id exists in the living conclusions doc",
                "does_not_prove": "that the conclusion is true, current, or economic",
                "finding_count": count,
                "authority": "research",
            },
            caveats=["Existence only — a registered conclusion is not a validated one."],
        )

    def _ground_agent_audit_ran(self, catalog, raw_token: str, src: str, dst: str) -> Grounding:
        """`source` is the TOOL NAME. Missing file is UNKNOWN (not clone-visible), never REFUSED."""
        if dst:
            return _unanswerable("JSONL", raw_token, "CC-AGENT-AUDIT-RAN takes no target")
        if not src:
            return _unanswerable(
                "JSONL", raw_token, "CC-AGENT-AUDIT-RAN requires source=<tool name>"
            )
        stream = catalog.stream_for_path(raw_token) if raw_token else None
        if stream is None or stream["id"] != "STR-AGENT-AUDIT":
            return _unanswerable(
                "JSONL",
                raw_token,
                "CC-AGENT-AUDIT-RAN token must be logs/agent_audit.jsonl or STR-AGENT-AUDIT",
            )
        # Read the ALLOWLISTED catalog path, never the raw token.
        path = _contained_repo_path(stream["path"])
        if path is None or not path.exists():
            return _unknown(
                "JSONL",
                raw_token,
                f"{stream['path']} is absent — runtime_untracked, not clone-visible",
                caveats=["Absence is not a refusal; this stream is gitignored (F-071)."],
            )
        for record in _read_jsonl_lines(path):
            if record.get("tool") == src or record.get("tool_name") == src:
                return _hit(
                    "JSONL",
                    raw_token,
                    authority=stream["path"],
                    record_id="CC-AGENT-AUDIT-RAN",
                    record_kind="claim_class",
                    evidence_class=TEXT_REFERENCE,
                    artifacts=[stream["path"]],
                    payload={
                        "tool_name": src,
                        "timestamp": record.get("timestamp"),
                        "success": record.get("success"),
                        "proves": "the tool ran in THIS checkout",
                        "does_not_prove": "that its result was correct",
                    },
                    caveats=["Session-local evidence — another clone cannot reproduce it."],
                )
        return _unknown("JSONL", raw_token, f"no {src!r} invocation in {stream['path']}")

    def _ground_envelope_shape(self, stream: dict, raw_token: str) -> Grounding:
        """Proves the SCHEMA carries the envelope keys — from committed sources only.

        Does not require the gitignored stream file and does not prove any occupancy.
        """
        fabric = _ROOT / "src" / "events" / "event_fabric.py"
        if not fabric.exists():
            return _unknown("JSONL", raw_token, "src/events/event_fabric.py is absent")
        if "make_event_envelope" not in _file_symbols(fabric):
            return _unknown("JSONL", raw_token, "make_event_envelope not found in event_fabric.py")
        return _hit(
            "JSONL",
            raw_token,
            authority="docs/reference/schemas.md §9.4 + src/events/event_fabric.py",
            record_id="CC-ENVELOPE-SHAPE",
            record_kind="claim_class",
            evidence_class=TEXT_REFERENCE,
            artifacts=["docs/reference/schemas.md", "src/events/event_fabric.py"],
            payload={
                "stream_id": stream["id"],
                "proves": "the stream's SCHEMA carries the event-fabric envelope keys",
                "does_not_prove": "that any line exists, or any occupancy the stream would imply",
            },
            caveats=["Shape of the contract only — never occupancy."],
        )

    def _ground_committed_stream(self, stream: dict, raw_token: str, rel: str) -> Grounding:
        """A committed audit stream: prove the file is present and non-empty in this clone."""
        path = _contained_repo_path(stream["path"])
        if path is None or not path.exists():
            return _unknown("JSONL", raw_token, f"{stream['path']} is absent from this checkout")
        lines = sum(1 for _ in _read_jsonl_lines(path))
        if not lines:
            return _unknown("JSONL", raw_token, f"{stream['path']} carries no records")
        return _hit(
            "JSONL",
            raw_token,
            authority=stream["path"],
            record_id=rel,
            record_kind="claim_class",
            evidence_class=TEXT_REFERENCE,
            artifacts=[stream["path"]],
            payload={
                "stream_id": stream["id"],
                "record_count": lines,
                "proves": "an audited governance event was recorded",
                "does_not_prove": "that the promoted or recorded object is profitable",
                "authority": "governance",
            },
            caveats=["An audit line records that something happened, not that it was good."],
        )

    def _ground_bar_structure_snapshot(self, stream: dict, raw_token: str, rel: str) -> Grounding:
        """CC-CTX-RUN-SCOPED-OBSERVATION: the identity that separates this stream from the
        unidentified ones must be PRESENT, not merely declared.

        `logs/crt_transitions.jsonl` is `CC-L3-GLOBAL-UNIDENTIFIED` for two concrete reasons —
        an empty instrument and no RESET record — so a claim of the form "the state at bar i was
        X" cannot be grounded against it. This class is the same claim against a stream that
        DOES carry identity, so the check verifies exactly the properties that difference rests
        on rather than trusting the catalog row:

          - the file exists and carries records;
          - `instrument`, `corpus_sha256` and `run_id` are populated on the first record;
          - the file describes ONE run of ONE corpus (a concatenation of two runs would make
            `bar_index` ambiguous and silently re-create the unidentified failure mode);
          - `bar_index` is gapless from 0, which is what makes it an occupancy series.

        Grounding this proves the stream can support "the engine state at this bar of this run".
        It proves nothing about whether that state is useful, correct, or profitable — the
        sibling `CC-CTX-NOT-DECISION` refuses that claim outright.
        """
        path = _contained_repo_path(raw_token)
        if path is None or not path.exists():
            return _unknown(
                "JSONL", raw_token,
                f"{raw_token} is absent from this checkout (the stream is runtime-untracked; "
                "produce it with scripts/research/emit_bar_structure_snapshots.py)",
            )
        first = None
        instruments, corpora, runs = set(), set(), set()
        indices = []
        # `_read_jsonl_lines` yields already-PARSED dicts, not raw strings.
        for rec in _read_jsonl_lines(path):
            if first is None:
                first = rec
            instruments.add(rec.get("instrument"))
            corpora.add(rec.get("corpus_sha256"))
            runs.add(rec.get("run_id"))
            idx = rec.get("bar_index")
            if isinstance(idx, int):
                indices.append(idx)
        if first is None:
            return _unknown("JSONL", raw_token, f"{raw_token} carries no records")

        missing = [k for k in ("instrument", "corpus_sha256", "run_id") if not first.get(k)]
        if missing:
            return _unknown(
                "JSONL", raw_token,
                f"identity fields absent/empty: {missing} — this stream is UNIDENTIFIED and "
                "cannot close a per-bar state claim",
            )
        if len(runs) != 1 or len(corpora) != 1 or len(instruments) != 1:
            return _unknown(
                "JSONL", raw_token,
                f"stream mixes {len(runs)} runs / {len(corpora)} corpora / "
                f"{len(instruments)} instruments — bar_index is ambiguous across them",
            )
        gapless = bool(indices) and sorted(indices) == list(range(len(indices)))
        if not gapless:
            return _unknown(
                "JSONL", raw_token,
                "bar_index is not a gapless 0..N-1 series — the stream has coverage holes and "
                "is not an occupancy series",
            )
        return _hit(
            "JSONL",
            raw_token,
            authority=f"{stream['path']} (SEM-035)",
            record_id=rel,
            record_kind="claim_class",
            evidence_class=TEXT_REFERENCE,
            artifacts=[raw_token],
            payload={
                "stream_id": stream["id"],
                "instrument": first.get("instrument"),
                "run_id": first.get("run_id"),
                "corpus_sha256": first.get("corpus_sha256"),
                "bars": len(indices),
                "proves": "this stream identifies the run, instrument and corpus, and covers "
                          "every bar, so a per-bar ENGINE state can be resolved from it",
                "does_not_prove": "that the state is correct, useful, or profitable; nor "
                                  "anything about the resolver state (that join is "
                                  "CC-L3-FORBIDDEN-JOIN)",
                "authority": "research",
            },
            caveats=[
                "Observation only. CC-CTX-NOT-DECISION refuses any claim that a context "
                "feature influenced a decision.",
            ],
        )

    def _ground_generated_registry(self, stream: dict, raw_token: str, rel: str) -> Grounding:
        """A GENERATED registry: the PRIMARY source is the authority, the projection is a view."""
        primary = stream.get("primary_source")
        primary_path = _contained_repo_path(primary) if primary else None
        if primary_path is None or not primary_path.exists():
            return _unknown(
                "JSONL", raw_token, f"PRIMARY source {primary!r} is absent — cannot ground the view"
            )
        return _hit(
            "JSONL",
            raw_token,
            authority=primary,
            record_id=rel,
            record_kind="claim_class",
            evidence_class=TEXT_REFERENCE,
            artifacts=[primary],
            payload={
                "stream_id": stream["id"],
                "proves": "the registry is generated from a committed PRIMARY source",
                "does_not_prove": "that any entry in it is validated or correct",
                "authority": "inventory",
            },
            caveats=["Registration is inventory, never authority (CLAUDE.md §6.5)."],
        )
