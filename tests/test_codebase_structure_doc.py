"""Structure-doc alignment - the enforceable floor for the package-tree docs.

Mirrors tests/test_doc_citations.py / tests/test_topic_docs.py (read-a-doc-and-assert).
Guards the hand-written role-per-module map against silent drift: every real `src/` package
(a subdir containing at least one .py file) must have a row in
`docs/architecture/codebase-state-map.md` §1. A newly-added package fails this test until it
is documented there - the mechanical "code grew, docs didn't" cure.

Roles (per CLAUDE.md): the AUTHORITATIVE complete tree is the generated
`docs/architecture/code-map.generated.md` (+ graph.dot); this test only enforces that the
*human role-per-module* map stays complete - it does not check that each role line is correct.
"""
from __future__ import annotations

from pathlib import Path

_SRC = Path("src")
_STATE_MAP = Path("docs/architecture/codebase-state-map.md")
# Dirs under src/ that are never importable packages.
_SKIP = {"__pycache__"}


def _real_packages() -> list[str]:
    """Immediate src/ subdirs that contain at least one .py file (recursively)."""
    pkgs = []
    for d in sorted(p for p in _SRC.iterdir() if p.is_dir()):
        if d.name in _SKIP or d.name.endswith(".egg-info"):
            continue
        if any(d.rglob("*.py")):
            pkgs.append(d.name)
    return pkgs


def test_state_map_exists() -> None:
    assert _STATE_MAP.exists(), f"{_STATE_MAP} is missing"


def test_every_src_package_is_documented() -> None:
    """Each real src/ package appears in codebase-state-map.md §1."""
    text = _STATE_MAP.read_text(encoding="utf-8")
    pkgs = _real_packages()
    assert pkgs, "no src/ packages discovered (cwd should be repo root)"
    missing = [p for p in pkgs if f"src/{p}/" not in text]
    assert not missing, (
        "src/ packages missing a row in docs/architecture/codebase-state-map.md §1 "
        f"(add `src/<pkg>/` rows): {missing}"
    )
