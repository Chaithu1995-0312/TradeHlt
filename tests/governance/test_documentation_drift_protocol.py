"""
test_documentation_drift_protocol.py — CLAUDE.md §6.2 Documentation Drift Protocol floor.

Purpose:
  Turn the prose mandate into a test floor (the repo pattern: doctrine prose →
  CI-detectable invariant). Asserts the long-form protocol doc exists with its
  invariant + 5-step structure, and that the CLAUDE.md §6.2 thin rule points to it.
  These are presence/section checks (like test_current_findings / test_session_log),
  not behavioral — the approval gate and completion criterion are process, not units.

See docs/governance/DOCUMENTATION_DRIFT_PROTOCOL.md for the full charter.
"""

from __future__ import annotations

import re
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROTOCOL_DOC = REPO_ROOT / "docs" / "governance" / "DOCUMENTATION_DRIFT_PROTOCOL.md"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"


def _norm(text: str) -> str:
    """Lowercase + collapse whitespace so phrasing checks survive reflow / case."""
    return re.sub(r"\s+", " ", text).lower()


# ═══════════════════════════════════════════════════════════════════════════════
# The long-form doc
# ═══════════════════════════════════════════════════════════════════════════════

def test_protocol_doc_exists():
    assert PROTOCOL_DOC.is_file(), f"missing long-form protocol doc: {PROTOCOL_DOC}"


def test_protocol_doc_states_invariant():
    body = _norm(PROTOCOL_DOC.read_text(encoding="utf-8"))
    # The invariant sentence (punctuation-insensitive: "code / config / runtime-truth").
    assert "triggers a documentation-truth decision" in body, (
        "protocol doc must state the core invariant"
    )
    for token in ("code", "config", "runtime-truth"):
        assert token in body, f"invariant must name '{token}' as a trigger"


def test_protocol_doc_has_five_steps():
    body = PROTOCOL_DOC.read_text(encoding="utf-8")
    for n in range(1, 6):
        assert re.search(rf"^###\s*Step\s*{n}\b", body, re.MULTILINE), (
            f"protocol doc missing 'Step {n}' header"
        )


def test_protocol_doc_has_gate_and_completion_criterion():
    body = _norm(PROTOCOL_DOC.read_text(encoding="utf-8"))
    assert "approval gate" in body, "protocol doc must describe the approval gate"
    assert "completion criterion" in body, (
        "protocol doc must define the completion criterion"
    )
    # Audit-trail format fields (Step 5).
    for field in ("previous belief", "verified reality", "verification method"):
        assert field in body, f"audit-trail format missing field: {field}"


# ═══════════════════════════════════════════════════════════════════════════════
# The CLAUDE.md §6.2 thin rule
# ═══════════════════════════════════════════════════════════════════════════════

def test_claude_md_has_thin_rule_pointer():
    body = CLAUDE_MD.read_text(encoding="utf-8")
    assert "Documentation Drift Protocol" in body, (
        "CLAUDE.md §6.2 must carry the Documentation Drift Protocol thin rule"
    )
    assert "docs/governance/DOCUMENTATION_DRIFT_PROTOCOL.md" in body, (
        "CLAUDE.md thin rule must link the long-form doc"
    )


def test_claude_md_thin_rule_states_invariant_and_gate():
    body = _norm(CLAUDE_MD.read_text(encoding="utf-8"))
    assert "triggers a documentation-truth decision" in body, (
        "CLAUDE.md thin rule must state the invariant"
    )
    # The calibrated gate distinction (auto-fix vs require approval).
    assert "auto-fix" in body and "require user approval" in body, (
        "CLAUDE.md thin rule must state the gate calibration"
    )
