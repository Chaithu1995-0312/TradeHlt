"""FrameworkRegistry — queryable, append-only map of the trading-system architecture.

Every component (kernel / domain / style / strategy / implementation / intent / risk /
execution / component) is one JSONL line at ``data/framework_registry.jsonl``, linked to its
code evidence, parent/children, and research findings (``docs/current-findings.md``).

Schema + contract: ``docs/reference/framework_registry_schema.md``.
Enforced by ``tests/test_framework_registry.py``. CI gate:
``python scripts/governance/query_registry.py --validate``.

Design notes (reuse, don't reinvent — CLAUDE.md §3.1):
  - persistence via ``src/utils/jsonl_writer`` (the canonical append-only helper);
  - evidence validation mirrors ``tests/test_doc_citations.py`` (±30-line symbol-drift window);
  - finding validation mirrors ``tests/test_current_findings.py`` (``### F-NNN`` block regex).

Append-only (§6.2 rule 4): a status change is a NEW line with a new ``last_validated``; prior
lines are never mutated. ``load()`` keeps the latest line per ``id``.

Usage:
    reg = FrameworkRegistry()
    reg.load("data/framework_registry.jsonl")
    styles = reg.filter(type="style")
    tree = reg.get_tree("DOMAIN-001")
    errors = reg.validate_evidence()
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from utils.jsonl_writer import append_jsonl, read_jsonl

# --------------------------------------------------------------------------- enums

TYPE_ENUM = frozenset(
    {"kernel", "domain", "style", "strategy", "implementation", "intent", "risk", "execution", "component"}
)
STATUS_ENUM = frozenset({"extant", "implicit", "orphaned", "killed", "dormant", "planned", "stub"})
EVIDENCE_TYPE_ENUM = frozenset({"code", "config", "doc", "test", "finding"})

# Types that pin a level (intent/component are cross-cutting, any level).
_TYPE_LEVEL = {
    "kernel": 0,
    "domain": 1,
    "style": 2,
    "strategy": 3,
    "implementation": 4,
    "risk": 5,
    "execution": 6,
}

_REQUIRED_FIELDS = (
    "id", "type", "level", "name", "parent", "children", "evidence",
    "findings", "tests", "status", "created", "last_validated", "notes",
)

# Mirror tests/test_doc_citations.py: symbol authoritative, line a hint within this window.
_DRIFT_WINDOW = 30
_SEARCH_ROOTS = ("src", "tests", "scripts")

# Mirror tests/test_current_findings.py finding-block header.
_FINDINGS_DOC = Path("docs/current-findings.md")
_FINDING_HEADER_RE = re.compile(r"^###\s+(F-\d{3})\b", re.MULTILINE)


@dataclass(frozen=True)
class ValidationError:
    """A structured registry-validation failure (printable + introspectable)."""

    component_id: str
    kind: str          # "evidence" | "finding" | "parent" | "child" | "duplicate" | "schema"
    detail: str

    def __str__(self) -> str:  # CLI-friendly
        return f"[{self.kind}] {self.component_id}: {self.detail}"


def valid_finding_ids(findings_doc: "Path | str" = _FINDINGS_DOC) -> set[str]:
    """All F-NNN ids declared in the living findings doc (terminal included; existence only)."""
    p = Path(findings_doc)
    if not p.exists():
        return set()
    return set(_FINDING_HEADER_RE.findall(p.read_text(encoding="utf-8")))


def _resolve(path_str: str) -> list[Path]:
    """Resolve a path: full repo-relative path, else unique basename under src/tests/scripts."""
    if "/" in path_str or "\\" in path_str:
        p = Path(path_str)
        return [p] if p.exists() else []
    hits: list[Path] = []
    for root in _SEARCH_ROOTS:
        hits.extend(Path(root).rglob(path_str))
    return sorted(set(hits))


class FrameworkRegistry:
    """In-memory view of the JSONL registry (latest line per id) + validators."""

    def __init__(self, path: "Path | str | None" = None) -> None:
        self.path: Optional[Path] = Path(path) if path else None
        self._records: dict[str, dict] = {}  # id -> latest record

    # ---------------------------------------------------------------- load / query

    def load(self, path: "Path | str | None" = None) -> int:
        """Load JSONL, keeping the latest line per id. Returns the unique-id count."""
        if path is not None:
            self.path = Path(path)
        if self.path is None:
            raise ValueError("FrameworkRegistry.load: no path given")
        self._records = {}
        for rec in read_jsonl(self.path):  # later lines override earlier (append-only)
            rid = rec.get("id")
            if rid:
                self._records[rid] = rec
        return len(self._records)

    @property
    def records(self) -> list[dict]:
        return list(self._records.values())

    def filter(
        self,
        type: Optional[str] = None,
        level: Optional[int] = None,
        status: Optional[str] = None,
        parent: Optional[str] = None,
    ) -> list[dict]:
        out = self.records
        if type is not None:
            out = [r for r in out if r.get("type") == type]
        if level is not None:
            out = [r for r in out if r.get("level") == level]
        if status is not None:
            out = [r for r in out if r.get("status") == status]
        if parent is not None:
            out = [r for r in out if r.get("parent") == parent]
        return sorted(out, key=lambda r: r.get("id", ""))

    def get(self, component_id: str) -> dict:
        if component_id not in self._records:
            raise KeyError(f"no component with id {component_id!r}")
        return self._records[component_id]

    def get_tree(self, root_id: str) -> dict:
        """Recursively build a parent→children nested tree (cycle-safe)."""
        def _build(cid: str, seen: frozenset[str]) -> dict:
            rec = dict(self._records.get(cid, {"id": cid, "missing": True}))
            if cid in seen:
                rec["_cycle"] = True
                rec["children"] = []
                return rec
            seen = seen | {cid}
            kids = self._records.get(cid, {}).get("children", []) or []
            rec["children"] = [_build(k, seen) for k in kids]
            return rec

        return _build(root_id, frozenset())

    def find_by_finding(self, finding_id: str) -> list[dict]:
        return sorted(
            (r for r in self.records if finding_id in (r.get("findings") or [])),
            key=lambda r: r.get("id", ""),
        )

    def get_orphaned(self) -> list[dict]:
        """STRUCTURAL orphans: no parent AND no children (disconnected from the tree).

        Distinct from ``status == "orphaned"`` (runtime wiring, F-006/F-013).
        """
        return sorted(
            (
                r
                for r in self.records
                if not r.get("parent") and not (r.get("children") or [])
            ),
            key=lambda r: r.get("id", ""),
        )

    def summary(self) -> dict:
        """Counts per type, level, and status."""
        def _tally(key: str) -> dict:
            out: dict = {}
            for r in self.records:
                out[r.get(key)] = out.get(r.get(key), 0) + 1
            return dict(sorted(out.items(), key=lambda kv: str(kv[0])))

        return {
            "total": len(self._records),
            "by_type": _tally("type"),
            "by_level": _tally("level"),
            "by_status": _tally("status"),
        }

    # ---------------------------------------------------------------- validation

    def validate_evidence(self) -> list[ValidationError]:
        """Every evidence path resolves; code-evidence symbol sits within ±30 lines of line."""
        errors: list[ValidationError] = []
        for r in self.records:
            for ev in r.get("evidence") or []:
                path_str = ev.get("path", "")
                matches = _resolve(path_str)
                if not matches:
                    errors.append(ValidationError(r["id"], "evidence", f"path not found: {path_str}"))
                    continue
                if len(matches) > 1:
                    errors.append(
                        ValidationError(r["id"], "evidence", f"ambiguous path {path_str}: {[str(m) for m in matches]}")
                    )
                    continue
                if ev.get("type") != "code":
                    continue  # config/doc/test/finding: existence only
                symbol = ev.get("symbol")
                line = ev.get("line")
                if not symbol or line is None:
                    continue  # code evidence without a precise anchor — existence is enough
                lines = matches[0].read_text(encoding="utf-8").splitlines()
                if symbol not in "\n".join(lines):
                    errors.append(ValidationError(r["id"], "evidence", f"symbol {symbol!r} absent from {matches[0]}"))
                    continue
                lo = max(0, line - 1 - _DRIFT_WINDOW)
                hi = min(len(lines), line - 1 + _DRIFT_WINDOW + 1)
                if not any(symbol in lines[k] for k in range(lo, hi)):
                    found = [k + 1 for k, ln in enumerate(lines) if symbol in ln]
                    errors.append(
                        ValidationError(r["id"], "evidence", f"{symbol!r} drifted >±{_DRIFT_WINDOW} from line {line} (at {found})")
                    )
        return errors

    def validate_findings(self, findings_doc: "Path | str" = _FINDINGS_DOC) -> list[ValidationError]:
        """Every findings[] id exists in docs/current-findings.md."""
        known = valid_finding_ids(findings_doc)
        errors: list[ValidationError] = []
        for r in self.records:
            for fid in r.get("findings") or []:
                if fid not in known:
                    errors.append(ValidationError(r["id"], "finding", f"unknown finding {fid}"))
        return errors

    def validate_links(self) -> list[ValidationError]:
        """No dangling parent / children ids."""
        ids = set(self._records)
        errors: list[ValidationError] = []
        for r in self.records:
            parent = r.get("parent")
            if parent and parent not in ids:
                errors.append(ValidationError(r["id"], "parent", f"dangling parent {parent}"))
            for child in r.get("children") or []:
                if child not in ids:
                    errors.append(ValidationError(r["id"], "child", f"dangling child {child}"))
        return errors

    def validate_all(self, findings_doc: "Path | str" = _FINDINGS_DOC) -> list[ValidationError]:
        return self.validate_evidence() + self.validate_findings(findings_doc) + self.validate_links()

    # ---------------------------------------------------------------- mutation

    def append(self, record: dict) -> None:
        """Append one validated line (append-only), updating the in-memory view."""
        self.validate_record(record)
        if self.path is None:
            raise ValueError("FrameworkRegistry.append: no path set (call load() or pass path=)")
        append_jsonl(self.path, record)
        self._records[record["id"]] = record

    def to_dataframe(self):
        """Export records as a pandas DataFrame (pandas imported lazily — analysis-only)."""
        import pandas as pd  # local: keeps the core load/validate path pandas-free

        return pd.DataFrame(self.records)

    # ---------------------------------------------------------------- schema / io

    @staticmethod
    def validate_record(record: dict) -> None:
        """Raise ValueError on any schema / enum / level-binding violation."""
        missing = [f for f in _REQUIRED_FIELDS if f not in record]
        if missing:
            raise ValueError(f"record {record.get('id')!r} missing fields: {missing}")
        rid = record["id"]
        if not isinstance(rid, str) or not rid:
            raise ValueError(f"record id must be a non-empty string, got {rid!r}")
        if record["type"] not in TYPE_ENUM:
            raise ValueError(f"{rid}: type {record['type']!r} not in {sorted(TYPE_ENUM)}")
        if record["status"] not in STATUS_ENUM:
            raise ValueError(f"{rid}: status {record['status']!r} not in {sorted(STATUS_ENUM)}")
        level = record["level"]
        if level not in range(0, 7):
            raise ValueError(f"{rid}: level {level!r} not in 0..6")
        bound = _TYPE_LEVEL.get(record["type"])
        if bound is not None and level != bound:
            raise ValueError(f"{rid}: type {record['type']!r} requires level {bound}, got {level}")
        for ev in record["evidence"]:
            if not isinstance(ev, dict) or "path" not in ev:
                raise ValueError(f"{rid}: evidence entry missing 'path': {ev!r}")
            et = ev.get("type")
            if et not in EVIDENCE_TYPE_ENUM:
                raise ValueError(f"{rid}: evidence type {et!r} not in {sorted(EVIDENCE_TYPE_ENUM)}")
        for list_field in ("children", "findings", "tests"):
            if not isinstance(record[list_field], list):
                raise ValueError(f"{rid}: {list_field} must be a list")

    @staticmethod
    def dump(path: "Path | str", records: list[dict]) -> int:
        """Validate + write all records deterministically (overwrite, sorted by id).

        Used by the seed script. Byte-stable across reruns (no timestamps generated here).
        """
        import json

        seen: set[str] = set()
        for rec in records:
            FrameworkRegistry.validate_record(rec)
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
