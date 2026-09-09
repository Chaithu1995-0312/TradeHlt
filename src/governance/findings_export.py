"""Findings export — GENERATED machine-readable derived view of docs/current-findings.md.

Parses the living findings doc into one JSON record per finding for LLM/tool consumption
(``data/findings.jsonl``). This is a **derived view** under CLAUDE.md §6.2: the markdown doc
stays the single authoritative conclusions store; the JSONL is regenerated, never hand-edited
(the §6.2 rule-1/rule-5 defense against truth duplication — same discipline as the Portable
Mind ``context/*.md``, machine-consumer flavor).

Grammar is reused, not reinvented (CLAUDE.md §3.1): the block regexes mirror
``tests/test_current_findings.py`` (``### F-NNN`` headers, ``- Field:`` lines, section split on
``## Findings`` / ``## Funding Ledger`` / ``## Terminal``) — the same grammar
``governance.framework_registry.valid_finding_ids`` trusts. Values are copied verbatim; the
only normalization is the em-dash placeholder ``—`` → ``None``.

Deterministic by construction: no timestamps are generated (the meta line is static), records
follow doc order, and ``json.dumps(..., sort_keys=True)`` pins key order — rendering twice is
byte-identical (proved by ``tests/test_findings_export.py``).

CLI: ``python scripts/governance/export_findings.py`` (regenerate) / ``--check`` (print only).
Schema doc: ``docs/reference/schemas.md §9.5``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_FINDINGS_DOC = Path("docs/current-findings.md")

# Mirror tests/test_current_findings.py exactly.
_HEADER_RE = re.compile(r"^###\s+(F-\d{3})\b(?:\s*·\s*(.*))?$", re.MULTILINE)
_EVIDENCE_PATH_RE = re.compile(
    r"(?<![\w./-])((?:docs|src|tests|scripts)/[\w./-]+\.(?:md|py))(?::\d+)?"
)
_TERMINAL_STATUS = {"SUPERSEDED", "RETIRED"}

_EMDASH = "—"

# doc field name -> record key (order = record semantics, not output order; sort_keys pins that)
_FIELDS = (
    ("Type", "type"),
    ("Status", "status"),
    # Added 2026-08-26 (CH-measurement-provenance-boundary). These two fields entered the findings
    # doc with the 2026-08-06 measurement-contract work and were never mirrored here, so the
    # GENERATED view named in CLAUDE.md §2 as a truth artifact could not answer "what measurement
    # basis?" or "what research family?" at all — the gap the 2026-08-26 provenance audit hit.
    ("Family", "family"),
    ("Contract", "contract"),
    ("Confidence", "confidence"),
    ("Validated", "validated"),
    ("Revalidate-by", "revalidate_by"),
    ("Evidence", "evidence"),
    ("Supersedes", "supersedes"),
    ("Superseded-by", "superseded_by"),
    ("Reversal", "reversal"),
    ("Owner", "owner"),
    ("Note", "note"),
)

META_LINE = {
    "kind": "meta",
    "schema": "findings_export/1",
    "source": "docs/current-findings.md",
    "generated_by": "scripts/governance/export_findings.py",
}

DEFAULT_OUT = Path("data/findings.jsonl")


def _field(block: str, name: str) -> str | None:
    """Extract a '- <name>: <value>' field verbatim; em-dash placeholder -> None."""
    m = re.search(rf"^- {re.escape(name)}:\s*(.*)$", block, re.MULTILINE)
    if m is None:
        return None
    value = m.group(1).strip()
    return None if value in ("", _EMDASH) else value


def _section(text: str, start_heading: str, *stop_headings: str) -> str:
    """One '## ' section of the doc (mirrors the test helper)."""
    start = text.find(start_heading)
    if start == -1:
        return ""
    ends = [text.find(h, start + len(start_heading)) for h in stop_headings]
    ends = [e for e in ends if e != -1]
    return text[start : min(ends)] if ends else text[start:]


def _blocks(body: str) -> list[tuple[str, str, str]]:
    """[(F-id, title, block_text)] in doc order for one section body."""
    headers = list(_HEADER_RE.finditer(body))
    out: list[tuple[str, str, str]] = []
    for i, h in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(body)
        out.append((h.group(1), (h.group(2) or "").strip(), body[h.start() : end]))
    return out


def parse_findings(doc: Path = _FINDINGS_DOC) -> list[dict]:
    """All finding records in doc order: '## Findings' section, then '## Terminal'."""
    text = doc.read_text(encoding="utf-8")
    findings_body = _section(text, "## Findings", "## Funding Ledger", "## Terminal")
    terminal_body = _section(text, "## Terminal")
    records: list[dict] = []
    for in_terminal_section, body in ((False, findings_body), (True, terminal_body)):
        for fid, title, block in _blocks(body):
            rec: dict = {"kind": "finding", "id": fid, "title": title}
            for doc_name, key in _FIELDS:
                rec[key] = _field(block, doc_name)
            rec["evidence_paths"] = [m.group(1) for m in _EVIDENCE_PATH_RE.finditer(block)]
            rec["terminal"] = in_terminal_section or rec["status"] in _TERMINAL_STATUS
            records.append(rec)
    return records


def render(records: list[dict]) -> str:
    """Meta line + one line per finding. Deterministic (no timestamps, sorted keys)."""
    lines = [json.dumps(META_LINE, ensure_ascii=False, sort_keys=True)]
    lines.extend(json.dumps(rec, ensure_ascii=False, sort_keys=True) for rec in records)
    return "\n".join(lines) + "\n"


def export(doc: Path = _FINDINGS_DOC, out: Path = DEFAULT_OUT) -> int:
    """Parse + write the derived view. Returns the finding count."""
    records = parse_findings(doc)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(records), encoding="utf-8")
    return len(records)
