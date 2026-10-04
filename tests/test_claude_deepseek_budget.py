"""Hard size ceiling for the DeepSeek Tier-0 bootloader.

Without a budget test the file regrows (CLAUDE.md already grew to 152 KB silently). Cap at 90 KB.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "Claude-deepseek.md"
MAX_BYTES = 90 * 1024  # 92,160


def test_budget_within_90kb():
    assert F.exists(), f"missing {F}"
    size = F.stat().st_size
    assert size <= MAX_BYTES, (
        f"Claude-deepseek.md is {size} bytes; must be <= {MAX_BYTES} "
        "(90 KB). Trim it rather than growing it."
    )


def test_nonzero():
    assert F.stat().st_size > 1000, "file unexpectedly empty/skeleton"


def test_sections_present():
    text = F.read_text(encoding="utf-8")
    for marker in ["## S0.", "## S1.", "## S1.1", "## S1.2", "## S2.", "## S3.",
                   "## S4.", "## S5.", "## S6.", "## S6.1", "## S7.", "## S8.",
                   "## S9.", "## S10.", "## S11.", "## S12.", "## S13."]:
        assert marker in text, f"missing section {marker}"