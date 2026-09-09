"""
test_semantic_review_protocol.py — CLAUDE.md §6.8 Adversarial Semantic Review Protocol floor.

Purpose:
  Turn the prose mandate into a test floor (the repo pattern: doctrine prose →
  CI-detectable invariant). Asserts the charter exists with its required structure,
  that the closing classification vocabulary and the required review-output headings
  are defined, that the two-ladder reconciliation clause is present (the guard against
  this charter silently becoming a sixth competing authority list), and that the
  CLAUDE.md §6.8 thin rule points to it and sits between §6.7 and §7.

  These are presence/section checks (like test_documentation_drift_protocol), not
  behavioral — a review's reasoning quality is process, not a unit. See the charter's
  "Honest residuals" section, which discloses that limit.

See docs/governance/SEMANTIC_REVIEW_PROTOCOL.md for the full charter.
"""

from __future__ import annotations

import re
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CHARTER = REPO_ROOT / "docs" / "governance" / "SEMANTIC_REVIEW_PROTOCOL.md"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"

# The ten terminal classifications (§16). Exactly one closes every review.
CLASSIFICATIONS = (
    "CONFIRMED DEFECT",
    "INTENTIONAL SEMANTIC SEPARATION",
    "STALE / LEGACY ARTIFACT",
    "COMPATIBILITY ARTIFACT",
    "DEFENSE-IN-DEPTH OPPORTUNITY",
    "TEST / CONTRACT GAP",
    "DOCUMENTATION GAP",
    "DORMANT BUT VALID",
    "INSUFFICIENT EVIDENCE",
    "USER AUTHORIZATION REQUIRED",
)

# The required review-output headings (§15).
OUTPUT_HEADINGS = (
    "RECOMMENDATION",
    "CONFIDENCE",
    "DOMAIN REASONING",
    "CURRENT BEHAVIOR",
    "INTENDED SEMANTICS",
    "CODEBASE EVIDENCE",
    "SEMANTIC OWNERSHIP",
    "ALTERNATIVE INTERPRETATION",
    "FAILURE / CONTAMINATION RISK",
    "WHAT SHOULD BE TESTED",
    "WHAT SHOULD NOT YET BE CHANGED",
    "USER AUTHORIZATION REQUIRED",
)

# The six "never conclude defect from difference alone" rules (§4), as (left, right)
# pairs so the check survives reflow and either "≠" or "!=" spelling.
NEQ_RULES = (
    ("different", "wrong"),
    ("unreachable", "bug"),
    ("configured", "must be reachable"),
    ("validated", "fully valid"),
    ("absent", "defective"),
    ("current", "correct"),
)


def _norm(text: str) -> str:
    """Lowercase + drop markdown emphasis + collapse whitespace.

    Phrasing checks must survive reflow, case, and bold/italic/code markup — a rule
    written "grants **no new authority**" states the same thing as the plain form.
    Underscores are preserved: several checks match snake_case filenames.
    """
    text = text.replace("*", "").replace("`", "")
    return re.sub(r"\s+", " ", text).lower()


def _neq_present(body_norm: str, left: str, right: str) -> bool:
    """True if '<left> ≠ <right>' (or '!=') appears, tolerant of spacing."""
    pattern = rf"{re.escape(left)}\s*(?:≠|!=)\s*{re.escape(right)}"
    return re.search(pattern, body_norm) is not None


# ═══════════════════════════════════════════════════════════════════════════════
# The charter
# ═══════════════════════════════════════════════════════════════════════════════

def test_charter_exists():
    assert CHARTER.is_file(), f"missing semantic review charter: {CHARTER}"


def test_charter_declares_no_authority():
    body = _norm(CHARTER.read_text(encoding="utf-8"))
    assert "grants no new authority" in body, (
        "charter must close with the no-new-authority disclaimer (repo charter convention)"
    )
    assert "review discipline only" in body, (
        "charter header must scope its authority to review discipline"
    )


def test_charter_has_non_duplication_clause():
    """The charter composes existing doctrine; it must say what it does not restate."""
    body = _norm(CHARTER.read_text(encoding="utf-8"))
    assert "does not restate" in body, (
        "charter must carry the non-duplication clause naming the doctrines it composes"
    )
    for owner in (
        "semantic_os_contract.md",
        "documentation_drift_protocol.md",
        "task_classification_behavior_policy.md",
        "epistemic_integrity.md",
        "market_ontology_evolution_contract.md",
        "model_intent_authority_register.md",
        "repository_construction_protocol.md",
    ):
        assert owner in body, f"non-duplication clause must name its owner doc: {owner}"


def test_charter_states_five_review_questions():
    body = _norm(CHARTER.read_text(encoding="utf-8"))
    for phrase in ("currently mean", "should", "established", "violate", "authorized"):
        assert phrase in body, f"the five review questions must include '{phrase}'"


def test_charter_has_two_ladder_reconciliation():
    """The guard against this charter becoming a sixth competing authority list."""
    raw = CHARTER.read_text(encoding="utf-8")
    body = _norm(raw)

    assert "reconciliation clause" in body, (
        "charter must carry an explicit reconciliation clause between the two ladders"
    )
    # Both ladders must be named as distinct objects.
    assert "current-truth ladder" in body, "charter must name the CURRENT-truth ladder"
    assert "meaning ladder" in body, "charter must name the MEANING ladder"
    # The reconciliation must defer to the existing meaning authorities, not replace them.
    assert "market_ontology_evolution_contract.md" in body and "miar" in body, (
        "reconciliation must cite the ontology contract and MIAR as the meaning authorities"
    )
    # The two directional non-override statements.
    assert "never grants meaning" in body, (
        "reconciliation must state the CURRENT ladder never grants meaning"
    )
    assert "never asserts runtime state" in body, (
        "reconciliation must state the MEANING ladder never asserts runtime state"
    )
    # Divergence is reported, not resolved by the reviewer.
    assert "truthconflict" in body, (
        "ladder divergence must route to a §6.2 TruthConflict"
    )


def test_charter_evidence_bands_are_distinct_from_confidence():
    body = _norm(CHARTER.read_text(encoding="utf-8"))
    for band in ("high", "medium", "low"):
        assert band in body, f"evidence-quality band missing: {band}"
    # Must explicitly separate source quality from claim strength, so the two
    # vocabularies do not merge (the repo already has 5 parallel status scales).
    assert "certain" in body and "likely" in body and "possible" in body, (
        "charter must name the Certain/Likely/Possible claim scale it is distinct from"
    )
    assert "grades the source" in body, (
        "charter must state that HIGH/MEDIUM/LOW grades the source, not the claim"
    )


def test_charter_has_all_six_neq_rules():
    body = _norm(CHARTER.read_text(encoding="utf-8"))
    for left, right in NEQ_RULES:
        assert _neq_present(body, left, right), (
            f"charter missing primary rule: {left} != {right}"
        )


def test_charter_has_validation_ownership_distinction():
    body = _norm(CHARTER.read_text(encoding="utf-8"))
    assert "validator does not check x" in body, (
        "charter must state the 'validator does not check X' half of the distinction"
    )
    assert "permits x to reach the trading engine" in body, (
        "charter must state the 'system permits X to reach the trading engine' half"
    )


def test_charter_has_contamination_chain():
    body = _norm(CHARTER.read_text(encoding="utf-8"))
    # Ordered spine from raw input to a placed order.
    for stage in (
        "input", "validation", "normalization", "features", "state", "context",
        "shape", "crt", "model testimony", "decision", "execution geometry",
        "risk", "order",
    ):
        assert stage in body, f"contamination trace missing stage: {stage}"


def test_charter_has_external_claim_rule():
    body = _norm(CHARTER.read_text(encoding="utf-8"))
    assert "hypothes" in body, (
        "charter must classify an external bug claim as a hypothesis"
    )
    # The two worked precedents where an external trace was verified and found wrong.
    assert "f-067" in body and "f-068" in body, (
        "external-claim rule must cite the F-067 / F-068 precedents"
    )


def test_charter_protects_tests_and_xfails():
    body = _norm(CHARTER.read_text(encoding="utf-8"))
    assert "xfail" in body, "charter must address xfail handling"
    assert "green" in body, (
        "charter must forbid modifying a test to make the implementation green"
    )


def test_charter_defines_all_ten_classifications():
    body = CHARTER.read_text(encoding="utf-8")
    for token in CLASSIFICATIONS:
        assert token in body, f"charter missing terminal classification: {token}"
    assert 'name the violated semantic contract' in _norm(body), (
        "charter must forbid the word 'bug' without naming the violated contract"
    )


def test_charter_defines_required_output_headings():
    body = CHARTER.read_text(encoding="utf-8")
    for heading in OUTPUT_HEADINGS:
        assert heading in body, f"required review-output heading missing: {heading}"


def test_charter_forbids_silent_remediation():
    body = _norm(CHARTER.read_text(encoding="utf-8"))
    assert "no silent remediation" in body, (
        "charter must carry the no-silent-remediation section"
    )
    assert "separate authorized turn" in body, (
        "charter must route implementation to a separate authorized turn"
    )


def test_charter_discloses_honest_residuals():
    """Repo convention (REPOSITORY_CONSTRUCTION_PROTOCOL): charters name their blind spots."""
    body = _norm(CHARTER.read_text(encoding="utf-8"))
    assert "honest residuals" in body, (
        "charter must disclose its own residuals rather than imply full coverage"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# The CLAUDE.md §6.8 thin rule
# ═══════════════════════════════════════════════════════════════════════════════

def test_claude_md_has_thin_rule_pointer():
    body = CLAUDE_MD.read_text(encoding="utf-8")
    assert re.search(r"^##\s*6\.8\s", body, re.MULTILINE), (
        "CLAUDE.md must carry a §6.8 section (top-level '##', like §6.1-§6.7)"
    )
    assert "Adversarial Semantic Review Protocol" in body, (
        "CLAUDE.md §6.8 must name the protocol"
    )
    assert "docs/governance/SEMANTIC_REVIEW_PROTOCOL.md" in body, (
        "CLAUDE.md thin rule must link the charter"
    )


def test_claude_md_thin_rule_ordering():
    """§6.8 sits between §6.7 and §7 — the doctrine block stays contiguous."""
    body = CLAUDE_MD.read_text(encoding="utf-8")
    pos_67 = body.find("## 6.7 ")
    pos_68 = body.find("## 6.8 ")
    pos_7 = body.find("## 7. ")
    assert -1 not in (pos_67, pos_68, pos_7), "missing §6.7, §6.8, or §7 header"
    assert pos_67 < pos_68 < pos_7, (
        "§6.8 must appear after §6.7 and before §7"
    )


def test_claude_md_thin_rule_carries_the_neq_rules():
    body = _norm(CLAUDE_MD.read_text(encoding="utf-8"))
    for left, right in NEQ_RULES:
        assert _neq_present(body, left, right), (
            f"CLAUDE.md §6.8 missing primary rule: {left} != {right}"
        )


def test_claude_md_thin_rule_states_no_silent_remediation():
    body = _norm(CLAUDE_MD.read_text(encoding="utf-8"))
    assert "no silent remediation" in body, (
        "CLAUDE.md §6.8 must state the no-silent-remediation rule"
    )
    assert "xfail" in body, (
        "CLAUDE.md §6.8 must name xfails among what review never edits"
    )


def test_claude_md_thin_rule_states_ladder_reconciliation():
    body = _norm(CLAUDE_MD.read_text(encoding="utf-8"))
    assert "never grants meaning" in body, (
        "CLAUDE.md §6.8 must state the CURRENT ladder never grants meaning"
    )
    assert "never" in body and "asserts runtime state" in body, (
        "CLAUDE.md §6.8 must state the MEANING ladder never asserts runtime state"
    )


def test_claude_md_thin_rule_lists_classifications():
    body = CLAUDE_MD.read_text(encoding="utf-8")
    for token in CLASSIFICATIONS:
        assert token in body, (
            f"CLAUDE.md §6.8 must list terminal classification: {token}"
        )
