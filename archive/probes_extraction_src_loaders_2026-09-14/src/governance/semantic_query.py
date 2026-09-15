"""semantic_query — L5, the Semantic Query Engine.

Generalizes ``scripts/governance/feature_surface_query.py`` beyond the feature surface. Where that
tool answers questions about a FEATURE, this answers questions about a CONCEPT, a BOUNDARY, a
JOURNEY, or an OBJECT, by joining the hand-authored semantic layer to every registry that already
exists.

Three properties carried over deliberately from the feature-surface prototype:

  1. **Every row carries an evidence class.** ``PROVEN`` / ``HEURISTIC`` / ``TEXT_REFERENCE``. An
     ``Answer`` also reports ``weakest_evidence_class`` so nobody over-trusts the aggregate.
  2. **Ambiguity fails closed.** A name that resolves to more than one record raises
     ``AmbiguousAliasError`` rather than silently picking the first.
  3. **A question that cannot be answered honestly returns PARTIAL or UNANSWERABLE**, with the
     reason attached. Verdicts are never inflated to look complete.

``QUESTION_REGISTRY`` is a CLOSED slug vocabulary — there is no natural-language parsing here, for
the same reason CLAUDE.md §3.3 keeps agent planning deterministic.

Usage:
    from governance.semantic_query import SemanticIndex
    idx = SemanticIndex.load()
    answer = idx.answer("authoritative", target="CN-001")
"""
from __future__ import annotations

import importlib.util
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

_ROOT = Path(__file__).resolve().parents[2]
_PROJECTION = _ROOT / "data" / "semantic_os"
_FINDINGS_JSONL = _ROOT / "data" / "findings.jsonl"
_HYPOTHESIS_JSONL = _ROOT / "data" / "hypothesis_registry.jsonl"
_CLOSURE = _ROOT / "docs" / "governance" / "closure_authority_index.json"
_FEATURE_SURFACE = _ROOT / "scripts" / "governance" / "feature_surface_query.py"

PROVEN, HEURISTIC, TEXT_REFERENCE = "PROVEN", "HEURISTIC", "TEXT_REFERENCE"
_CLASS_RANK = {PROVEN: 0, HEURISTIC: 1, TEXT_REFERENCE: 2}

ANSWERED, PARTIAL, UNANSWERABLE, AMBIGUOUS = "ANSWERED", "PARTIAL", "UNANSWERABLE", "AMBIGUOUS"


class AmbiguousAliasError(KeyError):
    """A name resolves to more than one record — the query fails closed rather than guessing."""

    def __init__(self, alias: str, candidates: list[str]):
        super().__init__(alias)
        self.alias = alias
        self.candidates = sorted(candidates)

    def __str__(self) -> str:  # noqa: D105
        return f"alias {self.alias!r} is AMBIGUOUS — candidates: {self.candidates}"


@dataclass(frozen=True)
class Answer:
    """One question's result. ``rows`` carry the claims; the verdict never overstates them."""

    question: str
    target: str
    verdict: str
    rows: list[dict] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    unanswerable_reason: Optional[str] = None

    @property
    def weakest_evidence_class(self) -> Optional[str]:
        classes = [r.get("evidence_class") for r in self.rows if r.get("evidence_class")]
        if not classes:
            return None
        return max(classes, key=lambda c: _CLASS_RANK.get(c, 99))

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "target": self.target,
            "verdict": self.verdict,
            "weakest_evidence_class": self.weakest_evidence_class,
            "row_count": len(self.rows),
            "rows": self.rows,
            "caveats": self.caveats,
            "unanswerable_reason": self.unanswerable_reason,
        }


def _row(claim: str, evidence_class: str, artifacts: list[str], detail: Any = None) -> dict:
    return {
        "claim": claim,
        "evidence_class": evidence_class,
        "artifacts": sorted(set(artifacts)),
        "detail": detail,
    }


def _read_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:  # noqa: BLE001
                    continue
    except Exception:  # noqa: BLE001
        return []
    return out


def _load_feature_surface() -> tuple[Any, Optional[str]]:
    """Load ``feature_surface_query`` by file path.

    ``scripts/governance/`` has no ``__init__.py``, so that module's own documented
    ``from scripts.governance...`` import does not actually work; ``tests/
    test_feature_surface_query.py`` loads it this way too.
    """
    if not _FEATURE_SURFACE.is_file():
        return None, "feature_surface_query.py not found"
    try:
        spec = importlib.util.spec_from_file_location("_fsq", _FEATURE_SURFACE)
        if spec is None or spec.loader is None:
            return None, "spec could not be created"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.FeatureSurfaceIndex.load(), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


class SemanticIndex:
    """Read-only join over the semantic layer + every registry it references."""

    def __init__(self, registry, objects: list[dict], meta: dict) -> None:
        self.registry = registry
        self.objects = {o["path"]: o for o in objects}
        self.meta = meta
        self._findings = {
            r["id"]: r for r in _read_jsonl(_FINDINGS_JSONL) if r.get("id") and r.get("kind") != "meta"
        }
        self._hypotheses = {r["id"]: r for r in _read_jsonl(_HYPOTHESIS_JSONL) if r.get("id")}
        try:
            self._closure = {
                s["surface_id"]: s
                for s in (json.loads(_CLOSURE.read_text(encoding="utf-8")).get("surfaces") or [])
                if s.get("surface_id")
            }
        except Exception:  # noqa: BLE001
            self._closure = {}
        self._feature_surface: Any = None
        self._feature_surface_error: Optional[str] = None
        self._feature_surface_loaded = False

    # ------------------------------------------------------------------ load

    @classmethod
    def load(cls, projection: Path = _PROJECTION, rebuild_objects: bool = False) -> "SemanticIndex":
        from governance.semantic_os import SemanticOSRegistry

        registry = SemanticOSRegistry.load()
        meta: dict = {"projection": str(projection.relative_to(_ROOT).as_posix()), "warnings": []}

        objects: list[dict] = []
        objects_path = projection / "objects.jsonl"
        if objects_path.is_file() and not rebuild_objects:
            objects = _read_jsonl(objects_path)
            meta["objects_source"] = "projection"
        else:
            from governance.semantic_objects import build_objects

            objects = build_objects(universe="code")
            meta["objects_source"] = "rebuilt"
            if not objects_path.is_file():
                meta["warnings"].append(
                    "objects.jsonl absent — rebuilt in-process; run seed_semantic_os.py --objects"
                )
        meta_path = projection / "index_meta.json"
        if meta_path.is_file():
            try:
                meta["projection_meta"] = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                meta["warnings"].append("index_meta.json unreadable")
        return cls(registry, objects, meta)

    @property
    def feature_surface(self) -> Any:
        """The feature-surface index, or ``None`` with a recorded reason (never a silent skip)."""
        if not self._feature_surface_loaded:
            self._feature_surface, self._feature_surface_error = _load_feature_surface()
            self._feature_surface_loaded = True
            if self._feature_surface_error:
                self.meta.setdefault("warnings", []).append(
                    f"feature_surface UNAVAILABLE: {self._feature_surface_error}"
                )
        return self._feature_surface

    # ------------------------------------------------------------------ resolution

    def _alias_map(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for cid, concept in self.registry.concepts.items():
            for key in [concept.get("name", "")] + list(concept.get("aliases") or []):
                if key:
                    out.setdefault(str(key).strip().lower(), []).append(cid)
        for bid, boundary in self.registry.boundaries.items():
            name = boundary.get("name")
            if name:
                out.setdefault(str(name).strip().lower(), []).append(bid)
        for jid, journey in self.registry.journeys.items():
            name = journey.get("name")
            if name:
                out.setdefault(str(name).strip().lower(), []).append(jid)
        return out

    def resolve(self, text: str) -> str:
        """Name/alias/id -> a single record id. Raises ``AmbiguousAliasError`` on a tie."""
        token = str(text).strip()
        for table in (self.registry.concepts, self.registry.boundaries, self.registry.journeys):
            if token in table:
                return token
        hits = self._alias_map().get(token.lower(), [])
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise AmbiguousAliasError(text, hits)
        raise KeyError(f"no semantic record matches {text!r}")

    def concepts_citing_ontology(self, ontology_id: str) -> list[str]:
        return sorted(
            cid for cid, c in self.registry.concepts.items()
            if ontology_id in (c.get("ontology_ids") or [])
        )

    def boundary_members(self, boundary_id: str) -> list[str]:
        from governance.semantic_os import resolve_members

        boundary = self.registry.boundaries.get(boundary_id) or {}
        return resolve_members(
            boundary.get("members") or [], boundary.get("members_exclude") or [], _ROOT
        )

    # ------------------------------------------------------------------ generic access

    def get_concept(self, target: str) -> dict:
        return self.registry.concepts[self.resolve(target)]

    def get_boundary(self, target: str) -> dict:
        return self.registry.boundaries[self.resolve(target)]

    def get_journey(self, target: str) -> dict:
        return self.registry.journeys[self.resolve(target)]

    def get_object(self, path: str) -> dict:
        key = str(path).replace("\\", "/")
        if key not in self.objects:
            raise KeyError(f"no object for path {path!r}")
        return self.objects[key]

    def search(self, text: str) -> list[dict]:
        needle = str(text).strip().lower()
        hits: list[dict] = []
        for record in self.registry.records:
            blob = json.dumps(record, ensure_ascii=False).lower()
            if needle in blob:
                hits.append({"id": record["id"], "kind": record["kind"], "name": record.get("name")})
        return sorted(hits, key=lambda r: r["id"])

    def summary(self) -> dict:
        out = dict(self.registry.summary())
        out["objects"] = len(self.objects)
        out["objects_source"] = self.meta.get("objects_source")
        out["warnings"] = self.meta.get("warnings", [])
        out["findings_loaded"] = len(self._findings)
        out["hypotheses_loaded"] = len(self._hypotheses)
        return out

    @property
    def sources(self) -> dict[str, str]:
        return {
            "concepts/boundaries/journeys": "docs/governance/semantic_os/*.yaml",
            "objects": "data/semantic_os/objects.jsonl",
            "findings": "data/findings.jsonl",
            "hypotheses": "data/hypothesis_registry.jsonl",
            "closure": "docs/governance/closure_authority_index.json",
            "change_contracts": "docs/governance/change_contracts.json",
            "config_graph": "docs/architecture/config-consumer-graph.generated.json",
            "citations": "docs/architecture/citation-map.generated.md",
            "ontology": "configs/formulas/market_ontology.yaml",
            "feature_surface": "scripts/governance/feature_surface_query.py",
        }

    # ------------------------------------------------------------------ questions

    def answer(self, slug: str, target: str) -> Answer:
        handler = QUESTION_REGISTRY.get(slug)
        if handler is None:
            raise KeyError(f"unknown question {slug!r}; known: {sorted(QUESTION_REGISTRY)}")
        try:
            return handler(self, target)
        except AmbiguousAliasError as exc:
            return Answer(
                question=slug, target=target, verdict=AMBIGUOUS,
                rows=[_row(f"candidate {c}", PROVEN, ["docs/governance/semantic_os/"], c)
                      for c in exc.candidates],
                caveats=["Resolution failed closed rather than picking a candidate."],
                unanswerable_reason=str(exc),
            )
        except KeyError as exc:
            return Answer(
                question=slug, target=target, verdict=UNANSWERABLE,
                unanswerable_reason=str(exc),
            )


# ── question resolvers ──────────────────────────────────────────────────────────────────────

def _q_guarantees(idx: SemanticIndex, target: str) -> Answer:
    """"What guarantees X?" — the DECLARED enforcement set. Completeness is never provable."""
    needle = str(target).replace("_", " ").strip().lower()
    rows: list[dict] = []
    matched_boundaries: set[str] = set()

    for cid, concept in sorted(idx.registry.concepts.items()):
        tags = {str(t).replace("_", " ").lower() for t in concept.get("semantic_tags") or []}
        inv_hit = [i for i in concept.get("invariants") or [] if needle in str(i).lower()]
        if needle in tags or inv_hit:
            for inv in (inv_hit or concept.get("invariants") or []):
                rows.append(_row(f"{cid} invariant: {inv}", PROVEN,
                                 ["docs/governance/semantic_os/concepts.yaml"], cid))
            owner = concept.get("owner_boundary")
            if owner:
                matched_boundaries.add(owner)
            for mode in concept.get("failure_modes") or []:
                if mode.get("detection"):
                    rows.append(_row(
                        f"{cid} detection for {mode['mode']}: {mode['detection']}",
                        PROVEN, ["docs/governance/semantic_os/concepts.yaml"], mode.get("finding"),
                    ))

    for bid in sorted(matched_boundaries):
        boundary = idx.registry.boundaries.get(bid) or {}
        rows.append(_row(f"{bid} protects: {boundary.get('invariant_protected')}", PROVEN,
                         ["docs/governance/semantic_os/boundaries.yaml"], bid))
        contract = boundary.get("contract") or {}
        for guarantee in contract.get("guarantees") or []:
            rows.append(_row(f"{bid} guarantees: {guarantee}", PROVEN,
                             ["docs/governance/semantic_os/boundaries.yaml"], bid))
        for non in contract.get("non_guarantees") or []:
            rows.append(_row(f"{bid} explicitly does NOT guarantee: {non}", PROVEN,
                             ["docs/governance/semantic_os/boundaries.yaml"], bid))
        for test_path in contract.get("enforced_by_tests") or []:
            exists = (_ROOT / test_path).is_file()
            rows.append(_row(
                f"{bid} enforced by {test_path}" + ("" if exists else " (MISSING ON DISK)"),
                PROVEN if exists else TEXT_REFERENCE, [test_path], bid,
            ))
        for member in idx.boundary_members(bid):
            obj = idx.objects.get(member) or {}
            for test in obj.get("tests_importing") or []:
                rows.append(_row(f"{test} imports {member}", PROVEN, [test], member))

    if not rows:
        return Answer("guarantees", target, UNANSWERABLE,
                      unanswerable_reason=f"no concept declares a tag or invariant matching {target!r}")

    return Answer(
        "guarantees", target, PARTIAL, rows,
        caveats=[
            "This is the DECLARED enforcement set. No artifact in this repository can prove "
            "exhaustiveness — 'nothing else can violate this invariant' is not a provable claim "
            "here, so the verdict is PARTIAL by construction and never ANSWERED.",
            "A test that imports a member is evidence of exercise, not of behavioural coverage; "
            "there is no coverage data in this repo.",
        ],
    )


def _q_owner(idx: SemanticIndex, target: str) -> Answer:
    """"Who owns X?" — fails closed when a quantity has several legitimate owners."""
    rows: list[dict] = []
    candidates: list[str] = []
    token = str(target).strip()

    if re.match(r"^(FM|SEM|UNK|RC|IND)-\d+$", token):
        candidates = idx.concepts_citing_ontology(token)
        if not candidates:
            surface = idx.feature_surface
            reason = (
                f"no concept cites ontology id {token}"
                + ("" if surface is not None else "; feature surface unavailable for fallback")
            )
            return Answer("owner", target, UNANSWERABLE, unanswerable_reason=reason)
    else:
        try:
            candidates = [idx.resolve(token)]
        except AmbiguousAliasError:
            raise
        except KeyError:
            needle = token.replace("_", " ").lower()
            candidates = [
                cid for cid, c in sorted(idx.registry.concepts.items())
                if needle in str(c.get("name", "")).lower()
                or any(needle in str(a).lower() for a in c.get("aliases") or [])
                or any(needle in str(k).lower() for k in c.get("retrieval_keywords") or [])
            ]
            if not candidates:
                return Answer("owner", target, UNANSWERABLE,
                              unanswerable_reason=f"nothing resolves {token!r}")

    for cid in candidates:
        record = idx.registry.concepts.get(cid) or idx.registry.boundaries.get(cid)
        if record is None:
            continue
        if record.get("kind") == "boundary":
            bid = cid
        else:
            rows.append(_row(f"{cid} canonical_source = {record.get('canonical_source')}", PROVEN,
                             [record.get("canonical_source") or ""], cid))
            bid = record.get("owner_boundary")
        boundary = idx.registry.boundaries.get(bid) if bid else None
        if boundary:
            rows.append(_row(
                f"{bid} owner = {boundary.get('owner')} ({boundary.get('owner_symbol')}) "
                f"[authority_layer {boundary.get('authority_layer')}]",
                PROVEN, [boundary.get("owner") or ""], bid,
            ))
        obj = idx.objects.get((record.get("canonical_source") or "")) or {}
        surface = obj.get("owner_surface")
        if surface:
            rows.append(_row(
                f"module_attribution owner_surface = {surface}"
                + (" (registry declares no attribution — NOT an answer)" if surface == "UNATTRIBUTED" else ""),
                PROVEN, ["docs/governance/module_attribution_stubs.jsonl"], surface,
            ))

    verdict = AMBIGUOUS if len(candidates) > 1 else (ANSWERED if rows else UNANSWERABLE)
    caveats = ["Boundary `owner` is the authoritative answer; module_attribution cannot answer "
               "ownership today (it reports UNATTRIBUTED on every row)."]
    if verdict == AMBIGUOUS:
        caveats.insert(0, f"{len(candidates)} distinct owners claim this quantity: {candidates}. "
                          "Reported as AMBIGUOUS rather than picking one.")
    return Answer("owner", target, verdict, rows, caveats=caveats)


def _q_writers(idx: SemanticIndex, target: str) -> Answer:
    """"What can modify X?" — module-level reach only. An import edge is NOT a mutation."""
    rid = idx.resolve(target)
    record = idx.registry.concepts.get(rid) or idx.registry.boundaries.get(rid) or {}
    bid = rid if record.get("kind") == "boundary" else record.get("owner_boundary")
    if not bid:
        return Answer("writers", target, UNANSWERABLE,
                      unanswerable_reason=f"{rid} has no owning boundary")
    boundary = idx.registry.boundaries.get(bid) or {}
    members = idx.boundary_members(bid)
    rows: list[dict] = []

    for member in members:
        obj = idx.objects.get(member) or {}
        for importer in obj.get("imported_by") or []:
            rows.append(_row(f"{importer} imports {member}", PROVEN, [importer], member))
        for key in obj.get("config_keys") or []:
            rows.append(_row(f"{member} reads config key {key} (READ_AND_USED)", PROVEN,
                             ["docs/architecture/config-consumer-graph.generated.json"], key))
        for key in obj.get("config_keys_heuristic") or []:
            rows.append(_row(f"{member} may read config key {key} (weaker verdict)", HEURISTIC,
                             ["docs/architecture/config-consumer-graph.generated.json"], key))

    from governance.semantic_os import required_checks_for_classes

    checks = required_checks_for_classes(boundary.get("change_classes") or [])
    for check in checks:
        rows.append(_row(f"changing {bid} requires {check}", PROVEN,
                         ["docs/governance/change_contracts.json"], check))

    return Answer(
        "writers", target, PARTIAL if rows else UNANSWERABLE, rows,
        caveats=[
            "Import edge != mutation. These are MODULE-level reach relationships; this repo has no "
            "reliable call-level graph, so 'which function writes which field' is not answerable.",
            "Config rows are PROVEN only where the reachability report says READ_AND_USED; "
            "weaker verdicts are name-based and marked HEURISTIC.",
        ],
        unanswerable_reason=None if rows else f"{bid} resolves to no members",
    )


def _q_disproved(idx: SemanticIndex, target: str) -> Answer:
    """"Which research disproved this?" — strongest where the concept DECLARES falsified_by."""
    rid = idx.resolve(target)
    concept = idx.registry.concepts.get(rid)
    if concept is None:
        return Answer("disproved", target, UNANSWERABLE,
                      unanswerable_reason=f"{rid} is not a concept")

    rows: list[dict] = []
    declared = False
    for assumption in concept.get("assumptions") or []:
        fid = assumption.get("falsified_by")
        if not fid:
            continue
        declared = True
        finding = idx._findings.get(fid, {})
        rows.append(_row(
            f"assumption {assumption.get('status')}: {assumption.get('assumption')} "
            f"-> {fid} {finding.get('title', '(title unavailable)')}",
            PROVEN, ["docs/current-findings.md"],
            {"finding": fid, "status": finding.get("status"),
             "confidence": finding.get("confidence"), "reversal": finding.get("reversal")},
        ))
    for mode in concept.get("failure_modes") or []:
        fid = mode.get("finding")
        if fid:
            declared = True
            finding = idx._findings.get(fid, {})
            rows.append(_row(
                f"failure mode {mode['mode']} observed by {fid}: {finding.get('title', '')}",
                PROVEN, ["docs/current-findings.md"], fid,
            ))
    for fid in concept.get("research_findings") or []:
        finding = idx._findings.get(fid, {})
        rows.append(_row(f"cited finding {fid}: {finding.get('title', '')}", PROVEN,
                         ["docs/current-findings.md"], fid))
    for hid in concept.get("hypotheses") or []:
        hyp = idx._hypotheses.get(hid, {})
        if hyp.get("status") == "falsified":
            declared = True
            rows.append(_row(
                f"hypothesis {hid} FALSIFIED: {hyp.get('statement', '')}", PROVEN,
                ["data/hypothesis_registry.jsonl"], hyp.get("findings"),
            ))

    if not declared:
        for keyword in concept.get("retrieval_keywords") or []:
            needle = str(keyword).lower()
            for fid, finding in sorted(idx._findings.items()):
                if needle in str(finding.get("title", "")).lower():
                    rows.append(_row(
                        f"keyword {keyword!r} appears in {fid}: {finding.get('title')}",
                        TEXT_REFERENCE, ["data/findings.jsonl"], fid,
                    ))

    verdict = ANSWERED if declared else (PARTIAL if rows else UNANSWERABLE)
    caveats = []
    if not declared:
        caveats.append(
            "The concept declares no falsified_by / hypothesis link, so this degraded to a keyword "
            "scan over the findings corpus — TEXT_REFERENCE, not evidence of falsification."
        )
    return Answer("disproved", target, verdict, rows, caveats=caveats,
                  unanswerable_reason=None if rows else "no declared or textual link found")


def _q_authoritative(idx: SemanticIndex, target: str) -> Answer:
    """"What modules are authoritative for this concept?" — ranked, with membership != authority."""
    rid = idx.resolve(target)
    concept = idx.registry.concepts.get(rid)
    if concept is None:
        return Answer("authoritative", target, UNANSWERABLE,
                      unanswerable_reason=f"{rid} is not a concept")
    rows: list[dict] = []

    canonical = concept.get("canonical_source")
    if canonical:
        rows.append(_row(f"TIER 1 canonical_source: {canonical}", PROVEN, [canonical], canonical))

    bid = concept.get("owner_boundary")
    boundary = idx.registry.boundaries.get(bid) if bid else None
    if boundary:
        rows.append(_row(
            f"TIER 1 boundary owner: {boundary.get('owner')} :: {boundary.get('owner_symbol')}",
            PROVEN, [boundary.get("owner") or ""], bid,
        ))
        for ev in boundary.get("evidence") or []:
            if ev.get("type") == "code":
                rows.append(_row(
                    f"TIER 2 drift-verified evidence: {ev.get('path')} :: {ev.get('symbol')}",
                    PROVEN, [ev.get("path") or ""], ev,
                ))
        for member in idx.boundary_members(bid):
            rows.append(_row(f"TIER 3 boundary member: {member}", PROVEN, [member], member))

    surface_id = concept.get("closure_surface_id")
    if surface_id:
        surface = idx._closure.get(surface_id, {})
        rows.append(_row(
            f"closure surface {surface_id} = {surface.get('status', 'UNKNOWN')} "
            f"(scope: {surface.get('scope_boundary', 'n/a')})",
            PROVEN, ["docs/governance/closure_authority_index.json"], surface.get("status"),
        ))

    return Answer(
        "authoritative", target, ANSWERED if rows else UNANSWERABLE, rows,
        caveats=[
            "Ranked: canonical_source and boundary owner are authority; boundary MEMBERSHIP is not "
            "— a file can sit inside a seam without being authoritative for it.",
            "CLOSURE IS BOUNDARY-SCOPED AND NON-TRANSITIVE: never infer authority for this concept "
            "from an upstream surface being CLOSED.",
        ],
    )


QUESTION_REGISTRY: dict[str, Callable[[SemanticIndex, str], Answer]] = {
    "guarantees": _q_guarantees,
    "owner": _q_owner,
    "writers": _q_writers,
    "disproved": _q_disproved,
    "authoritative": _q_authoritative,
}
