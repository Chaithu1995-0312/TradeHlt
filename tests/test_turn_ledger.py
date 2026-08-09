"""Tests for the multi-LLM turn ledger (src/multi_llm/turn_ledger.py)."""
from __future__ import annotations

from multi_llm.turn_ledger import TurnLedger, parse_handoff_block

_SAMPLE = """Some reasoning text...

CURRENT_TASK: STORY-1.1 fix the LLM fallback contract
NEXT_10_STEPS: STORY-1.2, STORY-1.3
CONTEXT_DELTA:
- decided fallback returns 0.5 (neutral)
- new constraint: no API in backtest
FOR_NEXT_MODEL: Claude — implement the fix
PROMPT_FOR_NEXT_MODEL: please implement STORY-1.1
CONFIRMATION: yes (ChatGPT -> Claude)
OPEN_QUESTIONS:
- is 0.5 correct vs 1.0?
"""


def test_parse_handoff_block():
    p = parse_handoff_block(_SAMPLE)
    assert p["next_actor"] == "Claude"
    assert "decided fallback returns 0.5 (neutral)" in p["decisions"]
    assert any("0.5 correct" in q for q in p["open_questions"])
    assert "fix the LLM fallback" in p["current_task"]


def test_append_stores_verbatim_and_indexes(tmp_path):
    led = TurnLedger(root=tmp_path)
    rec = led.append(actor="chatgpt", response_text=_SAMPLE, story_id="STORY-1.1", cycle_id="cyc1")
    assert rec.actor == "ChatGPT"           # canonicalized
    assert rec.next_actor == "Claude"
    verbatim = tmp_path / rec.response_ref
    assert verbatim.read_text(encoding="utf-8") == _SAMPLE   # no loss
    assert len(led.load()) == 1


def test_append_only_no_shrink(tmp_path):
    led = TurnLedger(root=tmp_path)
    r1 = led.append(actor="DeepSeek", response_text="plan A", cycle_id="cyc1")
    first_line = (tmp_path / "turn_ledger.jsonl").read_text(encoding="utf-8").splitlines()[0]
    r2 = led.append(actor="Gemini", response_text="gaps B", cycle_id="cyc1", parent_turn_id=r1.turn_id)
    lines = (tmp_path / "turn_ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0] == first_line           # earlier line unchanged (append-only)
    assert r2.parent_turn_id == r1.turn_id   # causal chain


def test_verify_detects_tampering(tmp_path):
    led = TurnLedger(root=tmp_path)
    rec = led.append(actor="Claude", response_text="original", cycle_id="cyc1")
    assert led.verify() == []                # clean
    (tmp_path / rec.response_ref).write_text("TAMPERED", encoding="utf-8")
    problems = led.verify()
    assert any("mismatch" in p for p in problems)
