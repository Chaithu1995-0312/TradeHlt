"""
discussion.py — reconstruct and REWIND the multi-LLM discussion (view-only time-travel).

Owner's intent: let Claude (or any model) reconstruct the entire DeepSeek→Gemini→ChatGPT→Claude
thread FROM THE START and step back through how decisions evolved — comprehension, not integrity.

Read-only. Linear (ordered by the event_fabric generation counter; parent_turn_id shown for
threading). Three views:
  - full(records)            : the whole discussion from start
  - rewind(records, turn_id) : the discussion + accumulated state AS IT STOOD up to that turn
  - digest(records)          : a compact "discussion so far" for cheap model ingestion

render_digest_from_ledger() is what build_context.py embeds as context/06_DISCUSSION.md.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from multi_llm.turn_ledger import TurnLedger, TurnRecord

_EMPTY = "_[no multi-LLM discussion recorded yet — use scripts/context/log_turn.py]_"


def load_records(root: "Path | str | None" = None) -> list[TurnRecord]:
    ledger = TurnLedger(root) if root is not None else TurnLedger()
    return ledger.load()


def _turn_line(r: TurnRecord) -> str:
    bits = f"- `{r.turn_id}` **{r.actor}**"
    if r.story_id:
        bits += f" · {r.story_id}"
    if r.current_task:
        bits += f" — {r.current_task}"
    if r.next_actor:
        bits += f"  -> {r.next_actor}"
    return bits


def _accumulate(records: list[TurnRecord]) -> tuple[list[str], list[str]]:
    """Running decisions (deduped, in order) and open questions across the included turns."""
    decisions: list[str] = []
    opens: list[str] = []
    for r in records:
        for d in r.decisions:
            if d not in decisions:
                decisions.append(d)
        for q in r.open_questions:
            if q not in opens:
                opens.append(q)
    return decisions, opens


def _render(records: list[TurnRecord], title: str) -> str:
    if not records:
        return f"## {title}\n\n{_EMPTY}\n"
    out = [f"## {title}", "", f"_{len(records)} turn(s) across "
           f"{len({r.cycle_id for r in records})} cycle(s)._", ""]
    last_cycle = None
    for r in records:
        if r.cycle_id != last_cycle:
            out.append(f"\n### {r.cycle_id}")
            last_cycle = r.cycle_id
        out.append(_turn_line(r))
    decisions, opens = _accumulate(records)
    out.append("\n### Decisions so far")
    out.extend([f"- {d}" for d in decisions] or ["- (none recorded)"])
    out.append("\n### Open questions")
    out.extend([f"- {q}" for q in opens] or ["- (none recorded)"])
    return "\n".join(out) + "\n"


def full(records: list[TurnRecord]) -> str:
    return _render(records, "Multi-LLM discussion — full (from start)")


def rewind(records: list[TurnRecord], turn_id: str) -> str:
    """View-only time-travel: the discussion as it stood up to and including `turn_id`."""
    cut: list[TurnRecord] = []
    found = False
    for r in records:
        cut.append(r)
        if r.turn_id == turn_id:
            found = True
            break
    if not found:
        return f"## Rewind\n\n_turn `{turn_id}` not found in the ledger._\n"
    return _render(cut, f"Multi-LLM discussion — rewound to {turn_id}")


def digest(records: list[TurnRecord], limit: int = 14) -> str:
    """Compact 'discussion so far' — the most recent `limit` turns + accumulated state."""
    if not records:
        return _EMPTY + "\n"
    recent = records[-limit:]
    out = [f"_{len(records)} total turn(s); showing last {len(recent)}._", ""]
    for r in recent:
        out.append(_turn_line(r))
    decisions, opens = _accumulate(records)
    if decisions:
        out.append("\n**Decisions so far:**")
        out.extend([f"- {d}" for d in decisions[-12:]])
    if opens:
        out.append("\n**Open questions:**")
        out.extend([f"- {q}" for q in opens[-12:]])
    return "\n".join(out) + "\n"


def render_digest_from_ledger(root: "Path | str | None" = None) -> str:
    """Stable digest for embedding in context/06_DISCUSSION.md. Empty ledger -> placeholder."""
    return digest(load_records(root))
