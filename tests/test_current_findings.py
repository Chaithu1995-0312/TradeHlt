"""Current-findings alignment — the enforceable floor for the Repository Truths layer.

Mirrors tests/test_topic_docs.py (read-a-doc-and-assert) and extends it with the
knowledge-governance contract per CLAUDE.md §6.2:
  - each finding is dated, confidence-rated, and has a non-empty Evidence link;
  - VALIDATED/OPEN findings must not be past their Revalidate-by date (the mechanical
    "nobody reviewed it" cure — this test can go red from the passage of time alone);
  - the CLAUDE.md "Repository Truths Index" and the living doc agree on the non-terminal F-ids.

It checks the mechanical contract only — NOT that each conclusion still matches the source
(that is the per-response Findings Mandate's job, §6.2).
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

_FINDINGS_DOC = Path("docs/current-findings.md")
_CLAUDE_MD = Path("CLAUDE.md")

_CREATED_RE = re.compile(r"Created:\s*\d{4}-\d{2}-\d{2}")
_UPDATED_RE = re.compile(r"Updated:\s*\d{4}-\d{2}-\d{2}")

# A finding block header: "### F-001 · <title>"
_HEADER_RE = re.compile(r"^###\s+(F-\d{3})\b", re.MULTILINE)
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

_VALID_STATUS = {"VALIDATED", "OPEN", "DURABLE", "SUPERSEDED", "RETIRED"}
_TERMINAL_STATUS = {"SUPERSEDED", "RETIRED"}
_VALID_CONFIDENCE = {"Certain", "Likely", "Possible"}
_VALID_TYPE = {"ARCHITECTURE", "ECONOMIC", "GOVERNANCE", "OPERATIONAL", "RISK"}

# Revalidation-window ceilings (Revalidate-by − Validated), in days, per status.
_WINDOW_CEILING_DAYS = {"VALIDATED": 180, "OPEN": 180, "DURABLE": 400}

# Index rows in CLAUDE.md look like a markdown table cell beginning with the F-id.
_INDEX_ROW_RE = re.compile(r"^\|\s*(F-\d{3})\s*\|", re.MULTILINE)

# A committed-tree path token (optionally :line) inside a finding block. Restricted to the
# stable source roots so prose-mentioned bare basenames (e.g. "dead-dormant-inventory.md:26")
# and volatile results/ artifacts are out of scope — we check that cited *committed* docs/code
# still exist, the Evidence analogue of the §6.3 citation-resolution contract.
_EVIDENCE_PATH_RE = re.compile(r"(?<![\w./-])((?:docs|src|tests|scripts)/[\w./-]+\.(?:md|py))(?::\d+)?")

_VALID_FUNDING = {"FUNDED", "FROZEN", "KILLED", "RESEARCH", "UNFUNDED"}
_FUNDING_REOPEN_REQUIRED = {"FROZEN", "KILLED"}
# Funding-Ledger block header: "### <Initiative> — <STATUS>"
_FUNDING_HEADER_RE = re.compile(r"^###\s+(.+?)\s+[—-]\s+([A-Z]+)\s*$", re.MULTILINE)
_FID_REF_RE = re.compile(r"F-\d{3}")


def _field(block: str, name: str) -> str:
    """Extract a '- <name>: <value>' field value from a finding block (empty if absent)."""
    m = re.search(rf"^- {re.escape(name)}:\s*(.*)$", block, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _section(start_heading: str, *stop_headings: str) -> str:
    """Return the text of one '## ' section, from start_heading up to the next stop heading."""
    text = _FINDINGS_DOC.read_text(encoding="utf-8")
    start = text.find(start_heading)
    if start == -1:
        return ""
    ends = [text.find(h, start + len(start_heading)) for h in stop_headings]
    ends = [e for e in ends if e != -1]
    return text[start : min(ends)] if ends else text[start:]


def _parse_findings() -> dict[str, str]:
    """Return {F-id: block_text} for every finding block in the Findings section only."""
    body = _section("## Findings", "## Funding Ledger", "## Terminal")
    headers = list(_HEADER_RE.finditer(body))
    blocks: dict[str, str] = {}
    for i, h in enumerate(headers):
        start = h.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(body)
        blocks[h.group(1)] = body[start:end]
    return blocks


def _parse_funding() -> dict[str, str]:
    """Return {initiative: block_text} for every Funding-Ledger block."""
    body = _section("## Funding Ledger", "## Terminal")
    headers = list(_FUNDING_HEADER_RE.finditer(body))
    blocks: dict[str, str] = {}
    for i, h in enumerate(headers):
        start = h.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(body)
        blocks[h.group(0).strip()] = body[start:end]
    return blocks


def test_findings_doc_exists_and_is_dated() -> None:
    assert _FINDINGS_DOC.exists(), "docs/current-findings.md (the living truths doc) is missing"
    text = _FINDINGS_DOC.read_text(encoding="utf-8")
    assert _CREATED_RE.search(text) and _UPDATED_RE.search(text), (
        "docs/current-findings.md missing a 'Created:'/'Updated: YYYY-MM-DD' header"
    )


def test_findings_have_required_fields() -> None:
    blocks = _parse_findings()
    assert blocks, "no F-NNN finding blocks found under '## Findings' in docs/current-findings.md"
    for fid, block in blocks.items():
        ftype = _field(block, "Type")
        status = _field(block, "Status")
        confidence = _field(block, "Confidence")
        evidence = _field(block, "Evidence")
        validated = _field(block, "Validated")
        revalidate = _field(block, "Revalidate-by")

        assert ftype in _VALID_TYPE, f"{fid}: Type '{ftype}' not in {_VALID_TYPE}"
        assert status in _VALID_STATUS, f"{fid}: Status '{status}' not in {_VALID_STATUS}"
        assert confidence in _VALID_CONFIDENCE, (
            f"{fid}: Confidence '{confidence}' not in {_VALID_CONFIDENCE}"
        )
        assert evidence and evidence != "—", f"{fid}: Evidence is required and must be non-empty"
        assert _DATE_RE.fullmatch(validated), f"{fid}: Validated '{validated}' not YYYY-MM-DD"
        assert _DATE_RE.fullmatch(revalidate), (
            f"{fid}: Revalidate-by '{revalidate}' not YYYY-MM-DD"
        )


def test_revalidation_window_respects_status_ceiling() -> None:
    """The Revalidate-by horizon must fit the status window (90d-class vs DURABLE 365d-class)."""
    blocks = _parse_findings()
    violations: list[str] = []
    for fid, block in blocks.items():
        status = _field(block, "Status")
        ceiling = _WINDOW_CEILING_DAYS.get(status)
        if ceiling is None:  # terminal statuses have no horizon
            continue
        try:
            v = _dt.date.fromisoformat(_field(block, "Validated"))
            r = _dt.date.fromisoformat(_field(block, "Revalidate-by"))
        except ValueError:
            continue  # covered by test_findings_have_required_fields
        span = (r - v).days
        if span > ceiling:
            violations.append(f"{fid} ({status}: {span}d > {ceiling}d ceiling)")
    assert not violations, (
        "Revalidate-by exceeds the status window ceiling — promote to DURABLE or tighten the date: "
        + ", ".join(violations)
    )


def test_nonterminal_findings_are_fresh() -> None:
    """VALIDATED/OPEN findings must not be past their Revalidate-by date."""
    today = _dt.date.today()
    blocks = _parse_findings()
    stale: list[str] = []
    for fid, block in blocks.items():
        status = _field(block, "Status")
        if status in _TERMINAL_STATUS:
            continue
        revalidate = _field(block, "Revalidate-by")
        try:
            due = _dt.date.fromisoformat(revalidate)
        except ValueError:
            continue  # covered by test_findings_have_required_fields
        if today > due:
            stale.append(f"{fid} (revalidate-by {revalidate})")
    assert not stale, (
        "stale findings — re-verify and bump Revalidate-by, or mark SUPERSEDED/RETIRED: "
        + ", ".join(stale)
    )


def test_index_and_doc_agree_on_nonterminal_ids() -> None:
    """Every non-terminal finding appears in the CLAUDE.md Repository Truths Index and vice-versa."""
    blocks = _parse_findings()
    doc_nonterminal = {
        fid for fid, block in blocks.items() if _field(block, "Status") not in _TERMINAL_STATUS
    }
    claude_text = _CLAUDE_MD.read_text(encoding="utf-8")
    index_ids = set(_INDEX_ROW_RE.findall(claude_text))

    missing_from_index = doc_nonterminal - index_ids
    missing_from_doc = index_ids - set(blocks)
    assert not missing_from_index, (
        f"non-terminal findings absent from CLAUDE.md Repository Truths Index: {sorted(missing_from_index)}"
    )
    assert not missing_from_doc, (
        f"CLAUDE.md index rows with no matching finding in docs/current-findings.md: {sorted(missing_from_doc)}"
    )


def test_findings_evidence_paths_resolve() -> None:
    """Every committed docs/src/tests/scripts path cited in a finding block exists on disk.

    Closes the gap where test_findings_have_required_fields only checks Evidence is *present*:
    a finding could cite a doc/source file that has since moved or been deleted and still pass.
    """
    blocks = _parse_findings()
    problems: list[str] = []
    for fid, block in blocks.items():
        for m in _EVIDENCE_PATH_RE.finditer(block):
            if not Path(m.group(1)).exists():
                problems.append(f"{fid}: cites missing path {m.group(1)}")
    assert not problems, (
        "findings cite committed paths that no longer resolve (CLAUDE.md §6.2/§6.3):\n"
        + "\n".join(problems)
    )


def test_terminal_findings_record_their_supersession() -> None:
    """A SUPERSEDED/RETIRED finding must say WHY — a non-empty Reversal or Superseded-by pointer.

    Enforces the append-discipline half of CLAUDE.md §6.2 rule 4: history is preserved, not
    deleted, but a terminal row is only useful if it records what overturned it.
    """
    blocks = _parse_findings()
    problems: list[str] = []
    for fid, block in blocks.items():
        if _field(block, "Status") not in _TERMINAL_STATUS:
            continue
        reversal = _field(block, "Reversal")
        superseded_by = _field(block, "Superseded-by")
        has_reversal = bool(reversal) and reversal != "—"
        has_superseded = bool(superseded_by) and superseded_by != "—"
        if not (has_reversal or has_superseded):
            problems.append(fid)
    assert not problems, (
        "terminal findings missing a Reversal or Superseded-by pointer (CLAUDE.md §6.2 rule 4): "
        + ", ".join(problems)
    )


def test_nonterminal_findings_declare_family_and_contract() -> None:
    """Every non-terminal finding records WHICH object it is about and HOW it was measured.

    Enforces the measurement-identity layer (MEASUREMENT_CONTRACT.md §9–§10): a conclusion whose
    measurement basis is unrecorded cannot be selectively invalidated. `Contract: UNKNOWN` is
    permitted and honest — it just carries no comparability. What is NOT permitted is silence.
    Terminal findings are exempt: they already carry no authority by status.
    """
    registry = json.loads(
        Path("docs/governance/research_family_registry.json").read_text(encoding="utf-8")
    )
    known_families = {f["family_id"] for f in registry["families"]}

    blocks = _parse_findings()
    problems: list[str] = []
    for fid, block in blocks.items():
        if _field(block, "Status") in _TERMINAL_STATUS:
            continue
        family = _field(block, "Family")
        contract = _field(block, "Contract")
        if not family:
            problems.append(f"{fid}: missing Family")
        elif not (family in known_families or family.startswith("—")):
            problems.append(
                f"{fid}: Family '{family}' is neither a registered RF-* id nor an explicit exclusion"
            )
        if not contract:
            problems.append(f"{fid}: missing Contract (use UNKNOWN if unrecorded)")
    assert not problems, (
        "findings missing measurement identity (MEASUREMENT_CONTRACT.md §9–§10):\n"
        + "\n".join(problems)
    )


def test_contract_bound_findings_name_a_real_measurement_identity() -> None:
    """A finding may only claim a contract that exists — UNKNOWN is the only free pass."""
    profile_ids = set()
    profile_dir = Path("configs/research/measurement_contracts")
    if profile_dir.is_dir():
        for p in profile_dir.glob("*.json"):
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("profile_id"):
                profile_ids.add(data["profile_id"])

    blocks = _parse_findings()
    problems: list[str] = []
    for fid, block in blocks.items():
        if _field(block, "Status") in _TERMINAL_STATUS:
            continue
        contract = _field(block, "Contract")
        if contract == "UNKNOWN":
            continue
        # Anything else must resolve to a known profile/contract identity or a sha256.
        if contract not in profile_ids and not re.fullmatch(r"[0-9a-f]{64}", contract):
            problems.append(f"{fid}: Contract '{contract}' resolves to no known identity")
    assert not problems, (
        "findings cite a measurement identity that does not exist:\n" + "\n".join(problems)
    )


def test_funding_ledger_is_well_formed() -> None:
    """Funding-Ledger initiatives: valid status vocab, resolvable finding refs, reopen conditions."""
    funding = _parse_funding()
    assert funding, "no Funding-Ledger blocks found under '## Funding Ledger'"
    known_fids = set(_parse_findings())
    problems: list[str] = []
    for header, block in funding.items():
        m = _FUNDING_HEADER_RE.match(header)
        name, status = (m.group(1).strip(), m.group(2)) if m else (header, "")
        if status not in _VALID_FUNDING:
            problems.append(f"'{name}': status '{status}' not in {_VALID_FUNDING}")
            continue
        # Evidence must cite at least one resolvable finding id.
        refs = set(_FID_REF_RE.findall(_field(block, "Evidence")))
        if not refs:
            problems.append(f"'{name}': Evidence cites no finding id")
        unresolved = refs - known_fids
        if unresolved:
            problems.append(f"'{name}': Evidence cites unknown findings {sorted(unresolved)}")
        # KILLED/FROZEN must carry non-empty Reopen Conditions.
        if status in _FUNDING_REOPEN_REQUIRED:
            reopen = _field(block, "Reopen Conditions")
            if not reopen or reopen == "—":
                problems.append(f"'{name}': {status} requires non-empty Reopen Conditions")
    assert not problems, "Funding-Ledger problems: " + "; ".join(problems)
