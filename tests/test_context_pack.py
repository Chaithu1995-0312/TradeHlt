"""Tests for bounded context packs (src/multi_llm/context_pack.py).

Uses the real multi_llm/build_queue.jsonl (STORY-1.1 exists after seeding). Robust to whether
context/*.md (the Portable Mind) has been generated — that's gitignored/optional.
"""
from __future__ import annotations

from multi_llm.context_pack import build_pack, get_story


def test_story_exists_in_queue():
    s = get_story("STORY-1.1")
    assert s is not None and s["id"] == "STORY-1.1"


def test_pack_has_header_and_manifest():
    pack = build_pack("STORY-1.1")
    assert "# CONTEXT PACK — STORY-1.1" in pack
    assert "## Manifest" in pack
    assert "## Story files" in pack


def test_pack_is_deterministic():
    assert build_pack("STORY-1.1", budget=8000) == build_pack("STORY-1.1", budget=8000)


def test_tiny_budget_flags_truncation_not_silent():
    # A tiny budget forces truncation of any real story file; it must be FLAGGED.
    pack = build_pack("STORY-1.1", budget=5)
    assert ("TRUNCATED" in pack) or ("not found" in pack) or ("OMITTED" in pack)


def test_unknown_story_still_builds():
    pack = build_pack("STORY-999.9")
    assert "STORY-999.9" in pack and "## Manifest" in pack
