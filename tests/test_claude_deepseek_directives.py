"""Guard the DeepSeek behavioral contract (D-1..D-6) of Claude-deepseek.md.

If a later edit blurs or removes any of the six directives, this test fails. The file is the
DeepSeek Tier-0 bootloader; these directives are its reason to exist. See Claude-deepseek.md %0.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "Claude-deepseek.md"

DIRECTIVES = {
    # marker: (visible token, anchor phrase that must survive)
    "D-1": "Never emit chain-of-thought",
    "D-2": "conclusions + citations",
    "D-3": "UNVERIFIED",
    "D-4": "P0",
    "D-5": "venv",
    "D-6": "No invented paths",
}


def _text() -> str:
    assert F.exists(), f"missing {F}"
    return F.read_text(encoding="utf-8")


def test_file_exists():
    assert F.exists()


def test_all_directives_present():
    text = _text()
    for token, phrase in DIRECTIVES.items():
        assert f"| {token} |" in text, f"directive marker {token} missing"
        assert phrase in text, f"directive {token} anchor phrase missing: {phrase!r}"


def test_directive_section_present():
    assert "## S0. DeepSeek behavioral contract" in _text()


def test_no_chain_of_thought_section_leaks():
    # The contract forbids a section that narrates model deliberation as a workflow.
    text = _text()
    for forbidden in ["## Let me think", "## Chain of thought", "## Deliberation"]:
        assert forbidden not in text