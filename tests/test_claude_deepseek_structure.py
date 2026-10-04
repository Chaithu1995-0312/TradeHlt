"""Section ORDER + placement guard for Claude-deepseek.md.

The earlier defect (S4 body displaced to the bottom, S8 after S11) was invisible to the
presence-only tests. This test asserts the sections appear in strict file order AND the S4
P0-P8 body sits inside the S4 span - so a reorder can never silently pass again.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "Claude-deepseek.md"

# Expected order, exactly as authored. S1.1/S1.2/S6.1 are subsections that interleave.
EXPECTED = [
    "S0.", "S1.", "S1.1", "S1.2", "S2.", "S3.",
    "S4.", "S5.", "S6.", "S6.1", "S7.", "S8.",
    "S9.", "S10.", "S11.", "S12.", "S13.",
]


def _headings_with_lines() -> list[tuple[int, str]]:
    out = []
    for i, line in enumerate(F.read_text(encoding="utf-8").splitlines(), start=1):
        if re.match(r"^## S", line):
            out.append((i, line.split()[1]))  # e.g. "S4." from "## S4. ..."
    return out


def test_sections_in_strict_order():
    lines = [token for _, token in _headings_with_lines()]
    # token order must equal EXPECTED (S1.1 lexicographic caveat handled by exact list)
    assert len(lines) == len(EXPECTED), f"got {len(lines)} sections, expected {len(EXPECTED)}"
    for got, want in zip(lines, EXPECTED):
        assert got == want, f"section order drift: {got!r} where {want!r} expected"


def test_each_section_once():
    tokens = [t for _, t in _headings_with_lines()]
    assert len(set(tokens)) == len(tokens), "a section header appears more than once"


def test_s4_body_inside_s4_span():
    text = F.read_text(encoding="utf-8").splitlines()
    s4 = next(i for i, t in _headings_with_lines() if t == "S4.")
    s5 = next(i for i, t in _headings_with_lines() if t == "S5.")
    # The P0 row of the phase table must be physically between the S4 and S5 headers.
    p0 = next(i for i, ln in enumerate(text, start=1) if "| P0 Boot | repo |" in ln)
    assert s4 < p0 < s5, f"P0-P8 table (line {p0}) must sit inside S4 span ({s4}..{s5})"