"""Tests for the canonical JSONL helper (src/utils/jsonl_writer.py)."""
from __future__ import annotations

import pytest

from utils.jsonl_writer import append_jsonl, read_jsonl, iter_jsonl


def test_append_then_read_roundtrip(tmp_path):
    p = tmp_path / "sub" / "log.jsonl"  # parent dir auto-created
    append_jsonl(p, {"a": 1})
    append_jsonl(p, {"b": 2})
    assert read_jsonl(p) == [{"a": 1}, {"b": 2}]
    assert list(iter_jsonl(p)) == [{"a": 1}, {"b": 2}]


def test_read_missing_returns_empty(tmp_path):
    assert read_jsonl(tmp_path / "nope.jsonl") == []


def test_read_skips_corrupt_lines(tmp_path):
    p = tmp_path / "log.jsonl"
    p.write_text('{"ok": 1}\nnot json\n\n{"ok": 2}\n', encoding="utf-8")
    assert read_jsonl(p) == [{"ok": 1}, {"ok": 2}]


def test_fail_silent_swallows_vs_raises(tmp_path):
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")
    target = blocker / "cannot.jsonl"  # parent is a file -> mkdir fails
    append_jsonl(target, {"a": 1}, fail_silent=True)  # must not raise
    with pytest.raises(Exception):
        append_jsonl(target, {"a": 1})
