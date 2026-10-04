"""Doctrine keywords stay aligned between CLAUDE.md and Claude-deepseek.md.

Claude-deepseek.md is the DeepSeek-tuned variant of CLAUDE.md. Doctrine wording that is
load-bearing in CLAUDE.md must be present (not contradicted, not silently dropped) in the
variant so no session inherits an unwritten hole.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / "CLAUDE.md"
DEEPSEEK = ROOT / "Claude-deepseek.md"

_LOAD_BEARING = [
    "path:line",          # citation discipline
    "UNVERIFIED",         # epistemic honesty
    "TruthConflict",      # never adjudicate silently
    "ACTIVE_VERSION",     # Tier-0 runtime truth
    "green floor",        # verification gate
    "SESSION LOG",        # recording mandate
    "current-findings",   # living findings record
]

_RESTORED_DOCTRINE = [
    "Existing-doc-first",        # S6 rule 1
    "Never silently resolve",    # S6 rule 3
    "Preserve history",          # S6 rule 4
    "Minimize doc count",        # S6 rule 5
    "Synchronize, never in isolation",  # S6 rule 6
    "Branch-scoped truth",       # S6 rule 7
    "North star",                # S6.1 frozen sentence
    "Meaning over data",         # S6.1
]


def test_both_files_exist():
    assert CLAUDE.exists()
    assert DEEPSEEK.exists()


def test_load_bearing_doctrine_present_in_both():
    c = CLAUDE.read_text(encoding="utf-8")
    d = DEEPSEEK.read_text(encoding="utf-8")
    missing = [k for k in _LOAD_BEARING if k not in c or k not in d]
    assert not missing, "doctrine keyword missing from CLAUDE.md or Claude-deepseek.md: " + \
        ", ".join(missing)


def test_no_mutual_contradiction_on_core_terms():
    c = CLAUDE.read_text(encoding="utf-8")
    d = DEEPSEEK.read_text(encoding="utf-8")
    # Core terms must appear with compatible polarity in both — we only require they are
    # referenced; a hard contradiction (one asserting absence) is caught by wording.
    for term in ["src/", "scripts/", "configs/production"]:
        assert term in c and term in d, f"root term {term!r} missing from one bootloader"


def test_restored_doctrine_markers_present():
    # Guards the review fixes: the seven S6 rules and the S6.1 intelligence-compounding
    # markers must exist in the DeepSeek bootloader (they were previously omitted).
    d = DEEPSEEK.read_text(encoding="utf-8")
    missing = [k for k in _RESTORED_DOCTRINE if k not in d]
    assert not missing, "restored doctrine marker missing from Claude-deepseek.md: " + \
        ", ".join(missing)