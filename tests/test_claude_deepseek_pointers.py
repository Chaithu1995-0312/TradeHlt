"""Every repo path referenced from Claude-deepseek.md must resolve on disk.

Directive D-6 forbids invented paths. This test enforces it mechanically: every `docs/...`,
`configs/...`, `scripts/...`, `multi_llm/...`, and the handful of root files named in the
bootloader must exist. Markdown links and backtick paths are both covered.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "Claude-deepseek.md"

_PATH_RE = re.compile(
    r"(?:docs/[\w./\-]+|configs/[\w./\-]+|scripts/[\w./\-]+"
    r"|tests/[\w./\-]+|multi_llm/[\w./\-]+|active_models\.yaml|assistant_project\.md"
    r"|CLAUDE\.md|Claude-deepseek\.md)"
)


def _referenced_paths() -> set[Path]:
    text = F.read_text(encoding="utf-8")
    return {Path(m) for m in _PATH_RE.findall(text)}


def test_at_least_twenty_references():
    assert len(_referenced_paths()) >= 20


def test_all_references_resolve():
    missing = [p for p in sorted(_referenced_paths()) if not (ROOT / p).exists()]
    assert not missing, "referenced paths do not exist:\n- " + "\n- ".join(map(str, missing))


def test_core_anchors_present():
    for anchor in [
        "docs/architecture/unified-workflow.md",
        "docs/architecture/retrieval-layer.md",
        "docs/current-findings.md",
        "docs/current-findings-index.md",
        "configs/production/ACTIVE_VERSION",
        "active_models.yaml",
    ]:
        assert anchor in F.read_text(encoding="utf-8"), f"anchor missing: {anchor}"