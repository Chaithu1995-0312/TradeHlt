"""
turn_ledger.py — append-only, no-loss record of every multi-LLM turn.

Each turn (one model's response in a DeepSeek→Gemini→ChatGPT→Claude cycle) is:
  - stored VERBATIM at multi_llm/turns/<cycle_id>/<turn_id>__<actor>.md  (the no-loss guarantee)
  - indexed by one JSON line in multi_llm/turn_ledger.jsonl

Reuses: utils.jsonl_writer (append/read), events.event_fabric (envelope + monotonic generation),
and the audit.py hashing convention (sha256[:16]). The ledger + turns are gitignored (local-only,
owner's choice); integrity is provable locally via verify().

The §3 handoff block is parsed out of each response into structured fields
(current_task / next_actor / confirmation / decisions / open_questions) so discussion.py can
reconstruct and rewind the discussion. The verbatim file is always kept regardless of parse quality.
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from utils.jsonl_writer import append_jsonl, read_jsonl
from events.event_fabric import make_event_envelope, EventType

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ROOT = _REPO_ROOT / "multi_llm"

ROLES = ("DeepSeek", "Gemini", "ChatGPT", "Claude")
_ROLE_LOOKUP = {r.lower(): r for r in ROLES}

# §3 mandatory-block labels (MULTI_LLM_PROTOCOL.md §3) + a few lenient aliases.
_BLOCK_LABELS = (
    "CURRENT_TASK", "NEXT_10_STEPS", "CONTEXT_DELTA", "FOR_NEXT_MODEL",
    "PROMPT_FOR_NEXT_MODEL", "CONFIRMATION", "NEXT_ACTOR", "DECISIONS", "OPEN_QUESTIONS",
)


def _sha256_short(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _canon_actor(actor: str) -> str:
    return _ROLE_LOOKUP.get(actor.strip().lower(), actor.strip())


def _bullets(text: str) -> list[str]:
    out = []
    for ln in text.splitlines():
        s = ln.strip().lstrip("-*").strip()
        if s:
            out.append(s)
    return out


def parse_handoff_block(text: str) -> dict:
    """Lenient parse of the §3 block. Returns structured fields; never raises."""
    # Capture each LABEL: <value...> up to the next known label or EOF.
    labels_re = "|".join(_BLOCK_LABELS)
    pat = re.compile(
        rf"^\s*({labels_re})\s*:\s*(.*?)(?=^\s*(?:{labels_re})\s*:|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    found: dict[str, str] = {}
    for m in pat.finditer(text):
        found[m.group(1).upper()] = m.group(2).strip()

    # next_actor: explicit NEXT_ACTOR wins, else scan FOR_NEXT_MODEL for a role token.
    next_actor = ""
    for key in ("NEXT_ACTOR", "FOR_NEXT_MODEL", "PROMPT_FOR_NEXT_MODEL"):
        val = found.get(key, "")
        for token in re.findall(r"[A-Za-z]+", val):
            if token.lower() in _ROLE_LOOKUP:
                next_actor = _ROLE_LOOKUP[token.lower()]
                break
        if next_actor:
            break

    decisions = _bullets(found.get("DECISIONS") or found.get("CONTEXT_DELTA", ""))
    open_questions = _bullets(found.get("OPEN_QUESTIONS", ""))
    return {
        "current_task": found.get("CURRENT_TASK", "").splitlines()[0] if found.get("CURRENT_TASK") else "",
        "context_delta": found.get("CONTEXT_DELTA", ""),
        "next_actor": next_actor,
        "confirmation": found.get("CONFIRMATION", "").splitlines()[0] if found.get("CONFIRMATION") else "",
        "decisions": decisions,
        "open_questions": open_questions,
    }


@dataclass
class TurnRecord:
    turn_id: str
    seq: int          # ledger-wide append position (monotonic across processes — ordering key)
    event_id: str
    generation: int   # per-process counter (informational only; resets each invocation)
    ts: str
    cycle_id: str
    actor: str
    story_id: str = ""
    model_version: str = ""
    parent_turn_id: str = ""
    prompt_ref: str = ""
    response_ref: str = ""
    context_fingerprint: str = ""
    pack_ref: str = ""
    current_task: str = ""
    next_actor: str = ""
    confirmation: str = ""
    decisions: list = field(default_factory=list)
    open_questions: list = field(default_factory=list)
    prompt_hash: str = ""
    response_hash: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TurnRecord":
        known = {k: d.get(k) for k in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        known["decisions"] = list(d.get("decisions") or [])
        known["open_questions"] = list(d.get("open_questions") or [])
        return cls(**{k: v for k, v in known.items() if v is not None})


class TurnLedger:
    def __init__(self, root: "Path | str" = _DEFAULT_ROOT):
        self.root = Path(root)
        self.ledger_path = self.root / "turn_ledger.jsonl"
        self.turns_dir = self.root / "turns"

    def default_cycle_id(self) -> str:
        return "cycle_" + time.strftime("%Y%m%d", time.gmtime())

    def append(
        self,
        *,
        actor: str,
        response_text: str,
        story_id: str = "",
        cycle_id: Optional[str] = None,
        parent_turn_id: str = "",
        model_version: str = "",
        context_fingerprint: str = "",
        pack_ref: str = "",
        prompt_text: str = "",
    ) -> TurnRecord:
        actor = _canon_actor(actor)
        cycle_id = cycle_id or self.default_cycle_id()
        env = make_event_envelope(
            event_type=EventType.LLM_TURN, instrument="", source=actor, payload={},
            parent_event_id="",
        )
        # seq = ledger-wide append position (monotonic ACROSS processes, unlike generation).
        seq = len(read_jsonl(self.ledger_path)) + 1
        turn_id = f"t{seq:05d}_{env['event_id']}"

        # Verbatim storage — the no-loss guarantee.
        cycle_dir = self.turns_dir / cycle_id
        cycle_dir.mkdir(parents=True, exist_ok=True)
        resp_file = cycle_dir / f"{turn_id}__{actor}.md"
        resp_file.write_text(response_text, encoding="utf-8")
        response_ref = resp_file.relative_to(self.root).as_posix()

        prompt_ref = ""
        if prompt_text:
            prompt_file = cycle_dir / f"{turn_id}__{actor}.prompt.md"
            prompt_file.write_text(prompt_text, encoding="utf-8")
            prompt_ref = prompt_file.relative_to(self.root).as_posix()

        parsed = parse_handoff_block(response_text)
        rec = TurnRecord(
            turn_id=turn_id,
            seq=seq,
            event_id=env["event_id"],
            generation=env["generation"],
            ts=env["timestamp"],
            cycle_id=cycle_id,
            actor=actor,
            story_id=story_id,
            model_version=model_version,
            parent_turn_id=parent_turn_id,
            prompt_ref=prompt_ref,
            response_ref=response_ref,
            context_fingerprint=context_fingerprint,
            pack_ref=pack_ref,
            current_task=parsed["current_task"],
            next_actor=parsed["next_actor"],
            confirmation=parsed["confirmation"],
            decisions=parsed["decisions"],
            open_questions=parsed["open_questions"],
            prompt_hash=_sha256_short(prompt_text) if prompt_text else "",
            response_hash=_sha256_short(response_text),
        )
        append_jsonl(self.ledger_path, rec.to_dict())  # durable: raises on failure
        return rec

    def load(self) -> list[TurnRecord]:
        """All turns in append (generation) order."""
        recs = [TurnRecord.from_dict(d) for d in read_jsonl(self.ledger_path)]
        return sorted(recs, key=lambda r: r.seq)

    def verify(self) -> list[str]:
        """Re-hash each stored verbatim response vs the ledger. Returns problem strings ([] = clean)."""
        problems: list[str] = []
        for rec in self.load():
            if not rec.response_ref:
                problems.append(f"{rec.turn_id}: no response_ref")
                continue
            f = self.root / rec.response_ref
            if not f.exists():
                problems.append(f"{rec.turn_id}: verbatim file missing ({rec.response_ref})")
                continue
            actual = _sha256_short(f.read_text(encoding="utf-8"))
            if actual != rec.response_hash:
                problems.append(f"{rec.turn_id}: response_hash mismatch (tampered/lost)")
        return problems
