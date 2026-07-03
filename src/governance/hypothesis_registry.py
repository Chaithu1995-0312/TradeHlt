"""HypothesisRegistry — queryable, append-only registry of research hypotheses (H-ids).

One JSONL line per hypothesis at ``data/hypothesis_registry.jsonl``, linking each falsifiable
statement to its findings (``docs/current-findings.md``), the ``active_models.yaml`` models it
speaks about, its in-code twins (research ``HYPOTHESIS_REGISTRY``), and pre-registration docs.
Sibling of ``governance.framework_registry`` — same persistence (``utils.jsonl_writer``), same
seed-script committed-truth pattern (``scripts/governance/seed_hypothesis_registry.py``), same
append-only discipline (§6.2 rule 4: a status flip is a NEW line; ``load()`` keeps latest per id).

Authority (CLAUDE.md §6.5 Authority Ladder — non-negotiable): every record's ``authority`` is
the pinned literal ``"research"``. ``status: validated`` is a *research* verdict only; this
registry defines NO promotion thresholds — the only promotion path remains the M4
``QualificationGate`` (``src/research/qualification.py``) → ``ConfigValidator`` →
``PromotionManager``. ``validate_record`` rejects unknown keys so authority-granting fields
(``promotion_requirements``, ``min_delta_g001``, …) can never enter the schema.

Schema doc: ``docs/reference/schemas.md §9.6``. Enforced by ``tests/test_hypothesis_registry.py``.
CI gate: ``python scripts/governance/query_hypotheses.py --validate``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from governance.framework_registry import ValidationError, valid_finding_ids
from utils.jsonl_writer import append_jsonl, read_jsonl

STATUS_ENUM = frozenset({"open", "validated", "falsified", "frozen", "superseded"})
AUTHORITY = "research"  # pinned — the registry can never grant more (§6.5)

_ID_RE = re.compile(r"^H-\d{3}$")

_REQUIRED_FIELDS = (
    "id", "statement", "family", "status", "authority", "findings", "models",
    "code_hypotheses", "programs", "evidence", "created", "last_validated", "notes",
)
_LIST_FIELDS = ("findings", "models", "code_hypotheses", "programs", "evidence")

_EVIDENCE_TYPE_ENUM = frozenset({"code", "config", "doc", "test", "finding"})
_FINDINGS_DOC = Path("docs/current-findings.md")


class HypothesisRegistry:
    """In-memory view of the JSONL registry (latest line per id) + validators."""

    def __init__(self, path: "Path | str | None" = None) -> None:
        self.path: Optional[Path] = Path(path) if path else None
        self._records: dict[str, dict] = {}

    # ---------------------------------------------------------------- load / query

    def load(self, path: "Path | str | None" = None) -> int:
        if path is not None:
            self.path = Path(path)
        if self.path is None:
            raise ValueError("HypothesisRegistry.load: no path given")
        self._records = {}
        for rec in read_jsonl(self.path):  # later lines override earlier (append-only)
            hid = rec.get("id")
            if hid:
                self._records[hid] = rec
        return len(self._records)

    @property
    def records(self) -> list[dict]:
        return list(self._records.values())

    def get(self, hypothesis_id: str) -> dict:
        if hypothesis_id not in self._records:
            raise KeyError(f"no hypothesis with id {hypothesis_id!r}")
        return self._records[hypothesis_id]

    def filter(
        self,
        status: Optional[str] = None,
        model: Optional[str] = None,
        finding: Optional[str] = None,
        family: Optional[str] = None,
    ) -> list[dict]:
        out = self.records
        if status is not None:
            out = [r for r in out if r.get("status") == status]
        if model is not None:
            out = [r for r in out if model in (r.get("models") or [])]
        if finding is not None:
            out = [r for r in out if finding in (r.get("findings") or [])]
        if family is not None:
            out = [r for r in out if r.get("family") == family]
        return sorted(out, key=lambda r: r.get("id", ""))

    def summary(self) -> dict:
        def _tally(key: str) -> dict:
            out: dict = {}
            for r in self.records:
                out[r.get(key)] = out.get(r.get(key), 0) + 1
            return dict(sorted(out.items(), key=lambda kv: str(kv[0])))

        return {"total": len(self._records), "by_status": _tally("status"), "by_family": _tally("family")}

    # ---------------------------------------------------------------- validation

    def validate_findings(self, findings_doc: "Path | str" = _FINDINGS_DOC) -> list[ValidationError]:
        """Every findings[] id exists in docs/current-findings.md (reuses the framework parser)."""
        known = valid_finding_ids(findings_doc)
        errors: list[ValidationError] = []
        for r in self.records:
            for fid in r.get("findings") or []:
                if fid not in known:
                    errors.append(ValidationError(r["id"], "finding", f"unknown finding {fid}"))
        return errors

    def validate_models(self, known_models: set[str]) -> list[ValidationError]:
        """Every models[] entry is a known active_models.yaml model key (caller supplies the set)."""
        errors: list[ValidationError] = []
        for r in self.records:
            for m in r.get("models") or []:
                if m not in known_models:
                    errors.append(ValidationError(r["id"], "model", f"unknown model {m}"))
        return errors

    def validate_paths(self) -> list[ValidationError]:
        """Every programs[] path and evidence[].path resolves on disk (existence only)."""
        errors: list[ValidationError] = []
        for r in self.records:
            for p in r.get("programs") or []:
                if not Path(p).exists():
                    errors.append(ValidationError(r["id"], "program", f"path not found: {p}"))
            for ev in r.get("evidence") or []:
                if not Path(ev.get("path", "")).exists():
                    errors.append(ValidationError(r["id"], "evidence", f"path not found: {ev.get('path')}"))
        return errors

    def validate_all(self, findings_doc: "Path | str" = _FINDINGS_DOC) -> list[ValidationError]:
        return self.validate_findings(findings_doc) + self.validate_paths()

    # ---------------------------------------------------------------- mutation

    def append(self, record: dict) -> None:
        """Append one validated line (append-only), updating the in-memory view."""
        self.validate_record(record)
        if self.path is None:
            raise ValueError("HypothesisRegistry.append: no path set (call load() or pass path=)")
        append_jsonl(self.path, record)
        self._records[record["id"]] = record

    # ---------------------------------------------------------------- schema / io

    @staticmethod
    def validate_record(record: dict) -> None:
        """Raise ValueError on schema / enum / authority violation. Unknown keys are REJECTED —
        the §6.5 defense: authority-granting fields can never be smuggled into the schema."""
        missing = [f for f in _REQUIRED_FIELDS if f not in record]
        if missing:
            raise ValueError(f"record {record.get('id')!r} missing fields: {missing}")
        unknown = [k for k in record if k not in _REQUIRED_FIELDS]
        if unknown:
            raise ValueError(
                f"{record.get('id')!r}: unknown keys {unknown} — the hypothesis schema is closed "
                "(§6.5: no promotion/threshold fields may enter a registry)"
            )
        hid = record["id"]
        if not isinstance(hid, str) or not _ID_RE.match(hid):
            raise ValueError(f"id must match H-NNN, got {hid!r}")
        if not record["statement"] or not isinstance(record["statement"], str):
            raise ValueError(f"{hid}: statement must be a non-empty string")
        if record["status"] not in STATUS_ENUM:
            raise ValueError(f"{hid}: status {record['status']!r} not in {sorted(STATUS_ENUM)}")
        if record["authority"] != AUTHORITY:
            raise ValueError(f"{hid}: authority must be the pinned literal {AUTHORITY!r} (§6.5)")
        for list_field in _LIST_FIELDS:
            if not isinstance(record[list_field], list):
                raise ValueError(f"{hid}: {list_field} must be a list")
        for ev in record["evidence"]:
            if not isinstance(ev, dict) or "path" not in ev:
                raise ValueError(f"{hid}: evidence entry missing 'path': {ev!r}")
            if ev.get("type") not in _EVIDENCE_TYPE_ENUM:
                raise ValueError(f"{hid}: evidence type {ev.get('type')!r} not in {sorted(_EVIDENCE_TYPE_ENUM)}")

    @staticmethod
    def dump(path: "Path | str", records: list[dict]) -> int:
        """Validate + write all records deterministically (overwrite, sorted by id).

        Used by the seed script. Byte-stable across reruns (no timestamps generated here).
        """
        import json

        seen: set[str] = set()
        for rec in records:
            HypothesisRegistry.validate_record(rec)
            if rec["id"] in seen:
                raise ValueError(f"duplicate id in seed set: {rec['id']}")
            seen.add(rec["id"])
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(records, key=lambda r: r["id"])
        with p.open("w", encoding="utf-8") as fh:
            for rec in ordered:
                fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        return len(ordered)
