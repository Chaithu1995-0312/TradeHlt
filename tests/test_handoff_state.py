"""HANDOFF.md validity — the enforceable floor for the Claude-Side Handoff Mandate (CLAUDE.md §13).

A test can only enforce a durable artifact, not chat text, so the persisted handoff state
(HANDOFF.md) is what we check: required keys present, actors are real roles, and any STORY id it
names resolves in the build queue. Mirrors tests/test_session_log.py / test_context_compiler.py
(read-and-assert, stdlib only).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HANDOFF = _REPO_ROOT / "HANDOFF.md"
_QUEUE = _REPO_ROOT / "multi_llm" / "build_queue.jsonl"
_PROTOCOL = _REPO_ROOT / "multi_llm" / "MULTI_LLM_PROTOCOL.md"
_ROLES_DIR = _REPO_ROOT / "multi_llm" / "roles"

_ROLES = {"DeepSeek", "Gemini", "ChatGPT", "Claude"}
_REQUIRED_KEYS = ("current_actor", "current_story", "completed", "blocked",
                  "next_actor", "next_prompt", "confirmation")
_KEY_RE = re.compile(r"^\s{0,4}([a-z_]+):\s*(.*)$")
_STORY_RE = re.compile(r"STORY-\d+\.\d+")


def _inline_values() -> dict[str, str]:
    """Map top-level `key: inline value` from the HANDOFF.md yaml-ish block."""
    vals: dict[str, str] = {}
    for line in _HANDOFF.read_text(encoding="utf-8").splitlines():
        m = _KEY_RE.match(line)
        if m and m.group(1) in _REQUIRED_KEYS and m.group(1) not in vals:
            vals[m.group(1)] = m.group(2).strip()
    return vals


def test_handoff_exists() -> None:
    assert _HANDOFF.exists(), "HANDOFF.md missing"


def test_protocol_and_roles_exist() -> None:
    assert _PROTOCOL.exists(), "MULTI_LLM_PROTOCOL.md missing"
    missing = [f"ROLE_{r.upper()}.md" for r in ("DEEPSEEK", "GEMINI", "CHATGPT", "CLAUDE")
               if not (_ROLES_DIR / f"ROLE_{r.upper()}.md").exists()]
    assert not missing, f"missing role files: {missing}"


def test_required_keys_present() -> None:
    vals = _inline_values()
    missing = [k for k in _REQUIRED_KEYS if k not in vals]
    assert not missing, f"HANDOFF.md missing keys: {missing}"


def test_actors_are_real_roles() -> None:
    vals = _inline_values()
    for key in ("current_actor", "next_actor"):
        actor = vals.get(key, "").split()[0] if vals.get(key) else ""
        assert actor in _ROLES, f"HANDOFF.md {key}={actor!r} not in {_ROLES}"


def test_story_reference_resolves_in_queue() -> None:
    """If current_story names a STORY id, it must exist in the build queue (no dangling reference)."""
    vals = _inline_values()
    m = _STORY_RE.search(vals.get("current_story", ""))
    if not m:
        return  # free-text task is allowed
    ids = {json.loads(ln)["id"] for ln in _QUEUE.read_text(encoding="utf-8").splitlines() if ln.strip()}
    assert m.group(0) in ids, f"HANDOFF.md current_story {m.group(0)} not found in build_queue.jsonl"
