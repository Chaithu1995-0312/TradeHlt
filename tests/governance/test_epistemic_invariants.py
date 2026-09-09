"""
test_epistemic_invariants.py — Program E-001 Track B invariant enforcement.

Purpose:
  CI-detectable tests that guard against the six E-001 failure classes.
  These invariants make recurrence of the F-030 rollup-inflation bug
  a test failure, not a human-noticed-after-the-fact artifact.

Invariants:
  E-001A: No strong verdict (REGIME_HARMFUL / REGIME_EXPLOITABLE / PROMOTE)
          on populations with n < configured minimum.
  E-001E: No rollup verdict stronger than the weakest child cell.
  Evidence-link: Every confident (Certain/Likely) finding in
          docs/current-findings.md resolves to a real accessible artifact.

See docs/governance/EPISTEMIC_INTEGRITY.md for the full charter.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

# ── paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURRENT_FINDINGS = REPO_ROOT / "docs" / "current-findings.md"
EPISTEMIC_CHARTER = REPO_ROOT / "docs" / "governance" / "EPISTEMIC_INTEGRITY.md"
KNOWN_ILLUSIONS = REPO_ROOT / "docs" / "operations" / "KNOWN_ILLUSIONS.md"
CONFIG_DIR = REPO_ROOT / "configs" / "production"


# ═══════════════════════════════════════════════════════════════════════════════
# E-001C — Evidence-link invariant
# ═══════════════════════════════════════════════════════════════════════════════

# Pattern for evidence lines in current-findings.md
_EVIDENCE_RE = re.compile(
    r"^\s*-\s*Evidence:\s*(.+)$",
    re.MULTILINE,
)

# Pattern for "confidence" lines
_CONFIDENCE_RE = re.compile(
    r"^\s*-\s*Confidence:\s*(Certain|Likely|Possible)\s*$",
    re.MULTILINE,
)

# Pattern for numbered finding header
_FINDING_HEADER_RE = re.compile(
    r"^###\s+(F-\d+)\s",
    re.MULTILINE,
)


def _parse_findings() -> list[dict]:
    """Parse current-findings.md into structured blocks (header→{lines})."""
    text = CURRENT_FINDINGS.read_text("utf-8")

    # Split on finding headers
    parts = _FINDING_HEADER_RE.split(text)
    if not parts:
        return []

    findings: list[dict] = []
    # parts[0] is preamble; after that it's alternating [f_id, body, f_id, body, ...]
    for i in range(1, len(parts), 2):
        fid = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        findings.append({"id": fid, "body": body})

    return findings


def _extract_field(body: str, field: str) -> str | None:
    """Extract the value of a field like `- Evidence: ...` from the body text."""
    m = re.search(rf"^\s*-\s*{re.escape(field)}:\s*(.+)$", body, re.MULTILINE)
    return m.group(1).strip() if m else None


def _resolve_evidence(evidence: str) -> list[Path]:
    """Return resolved file paths from an evidence string.
    Handles comma-separated, file:line, embedded narrative, and
    multi-file references with parenthetical notes.
    """
    paths: list[Path] = []
    # Strategy: extract likely file paths using a regex pattern for
    # repo-common path roots, then verify existence.
    # Matches: src/... docs/... results/... scripts/... tests/... configs/...
    # Also matches backtick-wrapped paths: `src/foo.py:123`
    path_pattern = re.compile(
        r"`?((?:src|docs|results|scripts|tests|configs|data|logs|reports)"
        r"(?:/[-\w.]+)+)`?\s*(?::\d+)?"
    )
    for match in path_pattern.finditer(evidence):
        candidate = REPO_ROOT / match.group(1)
        # R4 (bounded): an empty file is not real supporting evidence.
        if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 0:
            paths.append(candidate.resolve())
    return paths


# R4 (bounded): when evidence cites `path:line`, the line must exist. This does NOT
# attempt to prove the line *supports* the claim (semantic — future E-002), only that
# the citation is not dangling. Pattern captures the line number explicitly.
_PATH_LINE_RE = re.compile(
    r"`?((?:src|docs|results|scripts|tests|configs|data|logs|reports)"
    r"(?:/[-\w.]+)+):(\d+)`?"
)


def _dangling_line_citations(evidence: str) -> list[str]:
    """Return citations of the form path:line where the line is past EOF."""
    bad: list[str] = []
    for m in _PATH_LINE_RE.finditer(evidence):
        rel, line_s = m.group(1), m.group(2)
        f = REPO_ROOT / rel
        if not f.is_file():
            continue  # missing-file case handled by the evidence-link test
        n_lines = sum(1 for _ in f.open("r", encoding="utf-8", errors="ignore"))
        if int(line_s) > n_lines:
            bad.append(f"{rel}:{line_s} (file has {n_lines} lines)")
    return bad


# ═══════════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════════


def _load_consumer_verdict():
    """Import the pure rollup helper from the research harness.

    Returns None (caller skips) if the harness is not in the working tree,
    so the suite degrades gracefully outside a full checkout.
    """
    try:
        from research.regime_conditioning import _consumer_verdict
    except Exception:  # noqa: BLE001 — absence is a skip, not a failure
        return None
    return _consumer_verdict


class TestEpistemicInvariantE001A:
    """E-001A — Overclaim: no strong verdict on an all-underpowered population.

    BEHAVIORAL (not substring-grep): drives the pure `_consumer_verdict` rollup
    with synthetic inputs and asserts the *output*, so the invariant survives
    refactors/renames and a logically-broken guard goes red. This is what makes
    "the F-030 bug pattern is now a test failure" literally true rather than
    aspirational — see the red->green proof in test_red_green_guard below.
    """

    def test_all_insufficient_yields_insufficient_not_harmful(self):
        """The exact F-030 shape: every cell underpowered + negative sign counts
        must roll up to REGIME_INSUFFICIENT, never REGIME_HARMFUL."""
        cv = _load_consumer_verdict()
        if cv is None:
            pytest.skip("research.regime_conditioning not importable")

        # All cells failed the sample gate; sign-counts say "harmful" (noise).
        verdict = cv(
            has_exploitable=False,
            all_insufficient=True,
            redundant=False,
            n_harmful=3,        # noise — would be HARMFUL without the guard
            n_beneficial=0,
        )
        assert verdict == "REGIME_INSUFFICIENT", (
            "E-001A: all-INSUFFICIENT population must NOT overclaim — "
            f"got {verdict!r} (the F-030 bug)"
        )

    def test_powered_harmful_still_reported(self):
        """The guard must not over-suppress: a genuinely powered harmful
        population (not all-insufficient) still reports REGIME_HARMFUL."""
        cv = _load_consumer_verdict()
        if cv is None:
            pytest.skip("research.regime_conditioning not importable")

        verdict = cv(
            has_exploitable=False,
            all_insufficient=False,   # powered
            redundant=False,
            n_harmful=2,
            n_beneficial=0,
        )
        assert verdict == "REGIME_HARMFUL", (
            "E-001A guard over-suppressed: a powered harmful population must "
            f"still report REGIME_HARMFUL, got {verdict!r}"
        )

    def test_exploitable_precedence(self):
        """An exploitable cell dominates regardless of the insufficiency flag."""
        cv = _load_consumer_verdict()
        if cv is None:
            pytest.skip("research.regime_conditioning not importable")
        assert cv(
            has_exploitable=True, all_insufficient=True,
            redundant=False, n_harmful=3, n_beneficial=0,
        ) == "REGIME_EXPLOITABLE"

    @pytest.mark.parametrize(
        ("path", "label"),
        [
            ("src/research/qualification.py",
             "qualification gate verdict INSUFFICIENT guard"),
        ],
    )
    def test_qualification_insufficient_guard(self, path: str, label: str):
        """The 7-gate qualification pipeline must emit INSUFFICIENT
        (not REJECT) when the sample-size gate fails. (Structural check: the
        gate logic is the spine's and out of E-001 scope to refactor.)"""
        full = REPO_ROOT / path
        if not full.exists():
            pytest.skip(f"{path} not in working tree")

        code = full.read_text("utf-8")

        # The finalize() function must distinguish INSUFFICIENT from REJECT
        assert "insufficient" in code, (
            f"{label}: missing 'insufficient' flag — "
            "underpowered hypotheses must be INSUFFICIENT, not REJECT"
        )
        assert "INSUFFICIENT" in code, (
            f"{label}: INSUFFICIENT verdict string missing"
        )


class TestEpistemicInvariantE001E:
    """E-001E — Rollup Inflation: a parent verdict may not exceed the support
    of its children. BEHAVIORAL — exercises the pure rollup helper directly."""

    def test_parent_not_stronger_than_children(self):
        """When all child cells are INSUFFICIENT, the parent consumer verdict
        must be INSUFFICIENT — it cannot be 'stronger' (HARMFUL/INFORMATIONAL)
        than the weakest child that supports it."""
        cv = _load_consumer_verdict()
        if cv is None:
            pytest.skip("research.regime_conditioning not importable")
        assert cv(
            has_exploitable=False, all_insufficient=True,
            redundant=False, n_harmful=1, n_beneficial=1,
        ) == "REGIME_INSUFFICIENT"

    def test_red_green_guard_proof(self):
        """The acceptance criterion (plan R1): emulate REMOVING the
        all_insufficient guard and prove the overclaim re-appears — i.e. the
        guard is load-bearing, not decorative. With the guard (all_insufficient
        honored) -> INSUFFICIENT; without it (flag ignored) -> HARMFUL.
        This is the 'break it once, watch it go red' proof, run permanently."""
        cv = _load_consumer_verdict()
        if cv is None:
            pytest.skip("research.regime_conditioning not importable")

        guarded = cv(
            has_exploitable=False, all_insufficient=True,
            redundant=False, n_harmful=3, n_beneficial=0,
        )
        # Emulating the pre-v1.2 (guard-removed) path: the same sign-counts on a
        # population the harness believed was powered would overclaim HARMFUL.
        unguarded_equivalent = cv(
            has_exploitable=False, all_insufficient=False,
            redundant=False, n_harmful=3, n_beneficial=0,
        )
        assert guarded == "REGIME_INSUFFICIENT"
        assert unguarded_equivalent == "REGIME_HARMFUL"
        assert guarded != unguarded_equivalent, (
            "The all_insufficient guard makes a measurable difference — "
            "this is the F-030 overclaim being held at bay by the invariant."
        )


class TestEpistemicInvariantEvidenceLink:
    """Evidence-link invariant: every confident finding must resolve to artifact."""

    @pytest.fixture(scope="class")
    def findings(self):
        return _parse_findings()

    def test_charter_exists(self):
        """The Epistemic Integrity charter must exist."""
        assert EPISTEMIC_CHARTER.exists(), (
            "EPISTEMIC_INTEGRITY.md charter not found at "
            f"{EPISTEMIC_CHARTER}"
        )

    @pytest.mark.parametrize("confidence_filter", ["Certain", "Likely"])
    def test_confident_findings_have_real_evidence(
        self, findings, confidence_filter
    ):
        """Every finding with confidence Certain or Likely must cite at least
        one evidence artifact that resolves to a real file."""
        failures: list[str] = []
        for f in findings:
            conf = _extract_field(f["body"], "Confidence")
            if conf != confidence_filter:
                continue

            evidence = _extract_field(f["body"], "Evidence")
            if not evidence:
                failures.append(
                    f"{f['id']}: {confidence_filter} confidence but NO evidence field"
                )
                continue

            resolved = _resolve_evidence(evidence)
            if not resolved:
                failures.append(
                    f"{f['id']}: {confidence_filter} confidence but evidence "
                    f"'{evidence[:80]}...' resolves to NO existing file"
                )

        assert not failures, (
            f"{len(failures)} {confidence_filter}-confidence finding(s) "
            f"with unresolvable evidence:\n" + "\n".join(failures)
        )

    def test_advisory_possible_findings_evidence(
        self, findings
    ):
        """ADVISORY (does not enforce): Possible-confidence findings get a lower
        evidence bar than Certain/Likely, so unresolved evidence is surfaced via
        skip for review, not failed. Honestly labeled Advisory per E-001 R2."""
        warnings: list[str] = []
        for f in findings:
            conf = _extract_field(f["body"], "Confidence")
            if conf != "Possible":
                continue

            evidence = _extract_field(f["body"], "Evidence")
            if not evidence:
                warnings.append(
                    f"{f['id']}: Possible confidence with no evidence"
                )
                continue

            resolved = _resolve_evidence(evidence)
            if not resolved:
                warnings.append(
                    f"{f['id']}: Possible confidence evidence '{evidence[:80]}' "
                    f"resolves to no file"
                )

        if warnings:
            pytest.skip(
                f"Warning: {len(warnings)} Possible findings with weak evidence:\n"
                + "\n".join(warnings)
            )

    def test_cited_lines_exist(self, findings):
        """R4: every `path:line` citation in any finding must point to a line
        that exists (not past EOF). Bounded — does not check semantic support."""
        failures: list[str] = []
        for f in findings:
            evidence = _extract_field(f["body"], "Evidence")
            if not evidence:
                continue
            for bad in _dangling_line_citations(evidence):
                failures.append(f"{f['id']}: dangling citation {bad}")
        assert not failures, (
            "Dangling path:line evidence citation(s):\n" + "\n".join(failures)
        )

    def test_evidence_paths_are_absolute_or_git_root_relative(self, findings):
        """Evidence paths should use repo-root-relative paths (no /abs/paths)."""
        for f in findings:
            evidence = _extract_field(f["body"], "Evidence")
            if not evidence:
                continue
            for token in re.split(r"[;,]\s*", evidence):
                path_part = re.sub(r"\s*\(.*\)\s*$", "", token).strip().strip("`\"'")
                # A Windows drive letter is ALWAYS followed by a separator: `C:\` or `C:/`.
                # 2026-08-27: this previously flagged any token whose 2nd char was ':', which
                # fired on F-051's prose enumeration label ("C: rr_model zero_indices leaves
                # 10/10 contaminated dims") — a list marker, not a path. The instrument was
                # wrong, not the finding, so the heuristic is tightened rather than the
                # published Evidence edited.
                if path_part.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", path_part):
                    pytest.fail(
                        f"{f['id']}: evidence path '{path_part}' appears absolute"
                    )


class TestEpistemicCharterSelfConsistency:
    """The EPISTEMIC_INTEGRITY.md charter must be self-consistent."""

    def test_charter_reflects_f030_correction(self):
        """The charter must document the F-030 incident."""
        text = EPISTEMIC_CHARTER.read_text("utf-8") if EPISTEMIC_CHARTER.exists() else ""
        assert "F-030" in text or "REGIME_HARMFUL" in text or "v1.1" in text, (
            "EPISTEMIC_INTEGRITY.md does not reference the F-030 overclaim incident"
        )

    def test_charter_defines_mandatory_phrase(self):
        """The mandatory phrase must be present."""
        text = EPISTEMIC_CHARTER.read_text("utf-8") if EPISTEMIC_CHARTER.exists() else ""
        phrase = "Caught me overclaiming; I owe you a correction."
        assert phrase in text, (
            f"EPISTEMIC_INTEGRITY.md missing the mandatory phrase:\n  {phrase}"
        )

    def test_charter_defines_all_six_failure_classes(self):
        """All six E-001xx failure classes must be defined."""
        text = EPISTEMIC_CHARTER.read_text("utf-8") if EPISTEMIC_CHARTER.exists() else ""
        for eclass in ("E-001A", "E-001B", "E-001C", "E-001D", "E-001E", "E-001F"):
            assert eclass in text, (
                f"EPISTEMIC_INTEGRITY.md missing failure class {eclass}"
            )

    def test_charter_defines_pre_registration_ritual(self):
        """The 6-question ritual must be present."""
        text = EPISTEMIC_CHARTER.read_text("utf-8") if EPISTEMIC_CHARTER.exists() else ""
        questions = (
            "What artifact supports this",
            "Could INSUFFICIENT explain",
            "Am I upgrading sign noise",
            "statistical or economic",
            "parent stronger than",
            "raw counts",
        )
        for q in questions:
            assert q in text, (
                f"EPISTEMIC_INTEGRITY.md pre-registration ritual missing: '{q}'"
            )


class TestEpistemicSweepReport:
    """The epistemic sweep findings report must exist and be populated."""

    def test_sweep_report_exists(self):
        """The sweep findings report must be present."""
        report = REPO_ROOT / "reports" / "epistemic_sweep_findings.md"
        assert report.exists(), "reports/epistemic_sweep_findings.md not found"


# ═══════════════════════════════════════════════════════════════════════════════
# E-001F — Decorative Wiring (KNOWN_ILLUSIONS cross-check)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEpistemicInvariantE001F:
    """E-001F — Decorative Wiring: config present but unused.
    Cross-checks KNOWN_ILLUSIONS.md entries are still accurate."""

    def test_known_illusions_document_exists(self):
        assert KNOWN_ILLUSIONS.exists(), "KNOWN_ILLUSIONS.md not found"
        text = KNOWN_ILLUSIONS.read_text("utf-8")
        assert "H-Dead" in text or "H-Shadow" in text, (
            "KNOWN_ILLUSIONS.md missing illusion classifications"
        )

    def test_known_illusions_has_nonzero_entries(self):
        text = KNOWN_ILLUSIONS.read_text("utf-8")
        # Count illusion entries by "### #" headers
        count = len(re.findall(r"^###\s+#\d+", text, re.MULTILINE))
        assert count >= 10, (
            f"KNOWN_ILLUSIONS.md only has {count} entries; "
            "expected >= 10"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# E-001B — Statistical ≠ Economic (Authority-Ladder check)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEpistemicAdvisoryE001B:
    """E-001B — Statistical ≠ Economic. ADVISORY ONLY (does not enforce).

    Whether a p-value line carries economic context cannot be decided
    mechanically without semantics, so this test never fails — it surfaces
    candidates via `pytest.skip` for human review. Honestly labeled Advisory
    (not "Test asserts") per E-001 R2: a test that cannot fail is not
    enforcement, and must not be presented as such. Promotion to a real
    assertion would itself risk an E-001 error (forcing p-value -> economic
    meaning into deterministic logic). Future E-002 (semantic support) territory.
    """

    def test_advisory_flag_statistical_only_claims(self):
        """ADVISORY: surface (do not fail on) findings whose p-value line lacks
        any economic term, for human review."""
        text = CURRENT_FINDINGS.read_text("utf-8") if CURRENT_FINDINGS.exists() else ""

        # Look for patterns like "p < 0.05" without economic context
        p_value_lines = re.findall(
            r"^.*[pP]\s*[<≤].*0[.,]0[0-9].*$", text, re.MULTILINE
        )
        concerning: list[str] = []
        for line in p_value_lines:
            # Check if the line also mentions economic quantities
            has_economic = any(
                term in line.lower()
                for term in ("expectancy", "profit factor", "edge",
                             "e[r]", "pf", "economic", "roi", "mean_r")
            )
            if not has_economic:
                concerning.append(line.strip()[:120])

        if concerning:
            pytest.skip(
                f"Found {len(concerning)} p-value references potentially "
                f"without economic context:\n" + "\n".join(concerning[:5])
            )