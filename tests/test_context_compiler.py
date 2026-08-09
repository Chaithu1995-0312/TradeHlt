"""Context-compiler floor — the enforceable check for the multi-LLM Portable Mind.

Mirrors tests/test_doc_citations.py (read/run-and-assert). Verifies that
scripts/context/build_context.py and seed_build_queue.py are deterministic, derive from real
sources, and stamp the GENERATED header — so context/*.md stays a trustworthy derived view
(MULTI_LLM_PROTOCOL.md §5) rather than a forkable hand-edited file.

context/*.md is gitignored (a disposable export), so there is no "diff against committed" check;
determinism is proven by building twice in-process and comparing.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(module_name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(module_name, _REPO_ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_BUILD = _load("build_context", "scripts/context/build_context.py")
_SEED = _load("seed_build_queue", "scripts/context/seed_build_queue.py")

_EXPECTED_FILES = {
    "01_GLOBAL_CONTEXT.md", "02_CURRENT_STATE.md", "03_FINDINGS.md",
    "04_DEPENDENCY_AND_INTENT.md", "05_HANDOFF.md", "06_DISCUSSION.md",
}


def test_build_emits_expected_files() -> None:
    files = _BUILD.build()
    assert set(files) == _EXPECTED_FILES


def test_build_files_non_empty() -> None:
    for name, content in _BUILD.build().items():
        assert content.strip(), f"{name} is empty"


def test_build_is_deterministic() -> None:
    """Same inputs -> byte-identical output (no timestamps, sorted reads)."""
    assert _BUILD.build() == _BUILD.build()


def test_build_stamps_generated_header() -> None:
    for name, content in _BUILD.build().items():
        assert "GENERATED — do not edit by hand." in content, f"{name} missing GENERATED header"
        assert "scripts/context/build_context.py" in content, f"{name} missing regen pointer"


def test_build_sources_resolve() -> None:
    """The canonical sources the compiler derives from must exist (else the view is hollow)."""
    must_exist = [
        _REPO_ROOT / "CLAUDE.md",
        _REPO_ROOT / "docs" / "architecture" / "goal.md",
        _REPO_ROOT / "docs" / "current-findings.md",
        _REPO_ROOT / "configs" / "production" / "ACTIVE_VERSION",
        _REPO_ROOT / "multi_llm" / "MULTI_LLM_PROTOCOL.md",
    ]
    missing = [str(p.relative_to(_REPO_ROOT)) for p in must_exist if not p.exists()]
    assert not missing, f"missing compiler sources: {missing}"


def test_global_context_reflects_active_version() -> None:
    """02_CURRENT_STATE must surface the real ACTIVE_VERSION (no stale hardcoding)."""
    active = (_REPO_ROOT / "configs" / "production" / "ACTIVE_VERSION").read_text(
        encoding="utf-8").strip()
    assert active and active in _BUILD.build()["02_CURRENT_STATE.md"]


def test_seed_parses_spec_stories() -> None:
    """The build queue must carry the spec's stories (bridge to Track 1)."""
    records = _SEED.parse()
    assert len(records) >= 40, f"expected >=40 stories, got {len(records)}"
    ids = [r["id"] for r in records]
    assert len(ids) == len(set(ids)), "duplicate story ids"
    assert all(r["id"].startswith("STORY-") for r in records)


def test_seed_render_is_deterministic() -> None:
    recs = _SEED.parse()
    assert _SEED._render(recs) == _SEED._render(recs)
