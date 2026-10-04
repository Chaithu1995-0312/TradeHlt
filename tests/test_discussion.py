"""Tests for the discussion rewind (src/multi_llm/discussion.py)."""
from __future__ import annotations

from multi_llm import discussion as D
from multi_llm.turn_ledger import TurnLedger


def _seed(tmp_path):
    led = TurnLedger(root=tmp_path)
    r1 = led.append(actor="DeepSeek",
                    response_text="CURRENT_TASK: plan epic 1\nCONTEXT_DELTA:\n- decided to fix tests first\nFOR_NEXT_MODEL: Gemini",
                    cycle_id="cyc1")
    r2 = led.append(actor="Gemini",
                    response_text="CURRENT_TASK: navigate\nCONTEXT_DELTA:\n- gap: missing replay test\nFOR_NEXT_MODEL: ChatGPT",
                    cycle_id="cyc1", parent_turn_id=r1.turn_id)
    r3 = led.append(actor="Claude",
                    response_text="CURRENT_TASK: implement\nFOR_NEXT_MODEL: Gemini",
                    cycle_id="cyc1", parent_turn_id=r2.turn_id)
    return led.load(), r1, r2, r3


def test_full_lists_all_turns(tmp_path):
    recs, r1, r2, r3 = _seed(tmp_path)
    out = D.full(recs)
    for r in (r1, r2, r3):
        assert r.turn_id in out
    assert "decided to fix tests first" in out


def test_rewind_hides_later_turns(tmp_path):
    recs, r1, r2, r3 = _seed(tmp_path)
    out = D.rewind(recs, r2.turn_id)
    assert r1.turn_id in out and r2.turn_id in out
    assert r3.turn_id not in out          # view-only time-travel: later turns hidden


def test_rewind_unknown_turn(tmp_path):
    recs, *_ = _seed(tmp_path)
    assert "not found" in D.rewind(recs, "nope")


def test_digest_and_determinism(tmp_path):
    recs, *_ = _seed(tmp_path)
    assert D.digest(recs) == D.digest(recs)
    assert "Decisions so far" in D.digest(recs) or "decided" in D.digest(recs)


def test_empty_ledger_placeholder(tmp_path):
    assert "no multi-LLM discussion" in D.digest([])
    assert "no multi-LLM discussion" in D.render_digest_from_ledger(tmp_path)
