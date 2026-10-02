"""MKT-P01 projection over a run-scoped events.jsonl.

Reads records the engine already wrote. Does not re-run or edit the engine.

Market stages are RANGE/SWEEP/SHADOW_PENDING/DISPLACEMENT/EXPANSION/RETEST.
EXECUTION and RESOLUTION are a separate position track (concept_id is None; the
Execution layer is a later slice). EXPIRED and the parent C1/C2/C3 states are
unmapped: the market stage is left as it was.

A RESET terminates the open episode and is classified by terminal_reason_map.yaml.
An unmatched reason raises. The successor AWAITING opened by that RESET is kept
only if a later market stage arrives.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from semantics.identity import InstanceKey, SemanticIdentity, instance_id, parameterization_id
from semantics.registry import UnmatchedTerminalReason, load_terminal_reason_map, match_terminal
from semantics.types import TerminalAuthority, TerminalClass

EPISODE = "MKT-P01"

# Engine CRTState name -> market stage concept id.
_STAGE = {
    "RANGE": "MKT-P01.AWAITING_SWEEP",
    "SWEEP": "MKT-P01.SWEPT",
    "SHADOW_PENDING": "MKT-P01.SHADOW_PENDING",
    "DISPLACEMENT": "MKT-P01.DISPLACED",
    "EXPANSION": "MKT-P01.EXTENDED",
    "RETEST": "MKT-P01.RETESTING",
}
_AWAITING = "MKT-P01.AWAITING_SWEEP"
_POSITION = {"EXECUTION", "RESOLUTION"}
_UNMAPPED = {"EXPIRED", "RANGE_C1", "MANIPULATION_C2", "DISTRIBUTION_C3"}


@dataclass(frozen=True)
class Termination:
    authority: TerminalAuthority
    terminal_class: TerminalClass
    reason_code: str
    legacy_reason: str


@dataclass(frozen=True)
class StageOccupancy:
    concept_id: str
    entered_at: int
    left_at: Optional[int]
    dwell: Optional[int]

    @property
    def stage(self) -> str:
        return self.concept_id.split(".", 1)[1]


@dataclass(frozen=True)
class PositionMark:
    """Execution-layer state observed on the engine log. concept_id stays None (slice 2)."""
    concept_id: Optional[str]
    engine_state: str
    available_at: int
    run_id: str


@dataclass(frozen=True)
class Episode:
    concept_id: str
    parameterization_id: str
    run_id: str
    instance_bar: Optional[int]
    available_at: Optional[int]
    stages: tuple[StageOccupancy, ...]
    termination: Optional[Termination]

    @property
    def instance_key(self) -> InstanceKey:
        """Spec §5 instance_key for MKT-P01: anchor = first non-AWAITING stage bar
        ("-" for an episode that never left AWAITING), no side, parent = run_id."""
        anchor = "-" if self.instance_bar is None else str(self.instance_bar)
        return InstanceKey(anchor=anchor, side=None, parent=self.run_id)

    def instance_id(self, semantic: SemanticIdentity) -> str:
        """INSTANCE identity (no producer). `semantic` is MKT-P01's contract identity."""
        if semantic.concept_id != self.concept_id:
            raise ValueError(f"semantic identity {semantic.concept_id} is not {self.concept_id}")
        return instance_id(semantic, self.parameterization_id, self.instance_key)


class UnterminatedEpisode(ValueError):
    """An episode that left AWAITING_SWEEP ended without a RESET (no terminal authority)."""


@dataclass
class Projection:
    episodes: tuple[Episode, ...]
    position_track: tuple[PositionMark, ...]
    policy_shaped: bool
    observation_shaped: bool
    producer_shaped: bool
    termination_counts: dict
    unmapped_states: tuple
    unmatched_reasons: int = 0


@dataclass
class _Open:
    run_id: str
    param_id: str
    stages: list = field(default_factory=list)
    termination: Optional[Termination] = None
    opened_by_reset: bool = False

    def close_stage(self, at: int) -> None:
        if not self.stages or self.stages[-1].left_at is not None:
            return
        cur = self.stages[-1]
        self.stages[-1] = StageOccupancy(cur.concept_id, cur.entered_at, at, at - cur.entered_at)

    def enter(self, concept_id: str, at: int) -> None:
        self.close_stage(at)
        self.stages.append(StageOccupancy(concept_id, at, None, None))

    def has_left_awaiting(self) -> bool:
        return any(s.concept_id != _AWAITING for s in self.stages)

    def finish(self) -> Episode:
        instance = next((s.entered_at for s in self.stages if s.concept_id != _AWAITING), None)
        available = self.stages[0].entered_at if self.stages else None
        return Episode(
            EPISODE, self.param_id, self.run_id, instance, available,
            tuple(self.stages), self.termination,
        )


def _termination(reason: str, entries: Sequence[dict]) -> Termination:
    hit = match_terminal(reason, entries)
    return Termination(
        TerminalAuthority(hit["authority"]),
        TerminalClass(hit["class"]),
        str(hit["code"]),
        reason,
    )


def _resolve_run_id(rows: Sequence[dict], run_id: Optional[str]) -> str:
    seen = {r["run_id"] for r in rows if r.get("run_id")}
    if run_id is None:
        if len(seen) != 1:
            raise ValueError(f"run_id is required; records carry {sorted(seen) or 'none'}")
        return next(iter(seen))
    foreign = seen - {run_id}
    if foreign:
        raise ValueError(f"run_id {run_id!r} disagrees with records {sorted(foreign)}")
    return run_id


def project_events(rows: Sequence[dict], *, founding: str, run_id: Optional[str] = None,
                   entries: Optional[Sequence[dict]] = None) -> Projection:
    """Project engine event dicts onto MKT-P01. `founding` is the episode parameter."""
    table = list(entries) if entries is not None else load_terminal_reason_map()["entries"]
    resolved = _resolve_run_id(rows, run_id)
    param_id = parameterization_id(EPISODE, {"founding": founding}, ("founding",))
    ordered = [row for _i, row in sorted(enumerate(rows), key=lambda iv: (iv[1].get("candle_index", 0), iv[0]))]

    episodes: list[Episode] = []
    positions: list[PositionMark] = []
    unmapped: list[tuple[int, str]] = []
    counts: dict[tuple[str, str], int] = {}
    flags = {"DECISION": False, "OBSERVATION": False, "PRODUCER": False}
    current: Optional[_Open] = None

    def finish_current() -> None:
        nonlocal current
        if current is None:
            return
        episodes.append(current.finish())
        current = None

    def note(term: Termination) -> None:
        key = (term.authority.value, term.terminal_class.value)
        counts[key] = counts.get(key, 0) + 1
        if term.authority.value in flags:
            flags[term.authority.value] = True

    for row in ordered:
        kind = row.get("event")
        bar = int(row["candle_index"])
        if kind == "STATE_TRANSITION":
            dest = row.get("state_to")
            if dest in _POSITION:
                positions.append(PositionMark(None, str(dest), bar, resolved))
                continue
            if dest in _UNMAPPED:
                unmapped.append((bar, str(dest)))
                continue
            if dest not in _STAGE:
                raise ValueError(f"unmapped engine state {dest!r} at bar {bar}")
            stage = _STAGE[dest]
            if current is None:
                current = _Open(resolved, param_id)
                current.enter(stage, bar)
                continue
            if stage == _AWAITING and current.stages and current.stages[-1].concept_id == _AWAITING \
                    and current.stages[-1].left_at is None:
                continue
            if stage == _AWAITING and current.has_left_awaiting():
                # Every termination carries a terminal authority (spec §8); the engine logs a
                # RESET for each one. A return to RANGE without it has no authority to record.
                raise UnterminatedEpisode(
                    f"episode left AWAITING_SWEEP and returned to RANGE at bar {bar} without a RESET"
                )
            current.enter(stage, bar)
        elif kind == "RESET":
            reason = row.get("reason")
            if not isinstance(reason, str) or reason == "":
                raise UnmatchedTerminalReason(f"RESET at bar {bar} has no reason")
            term = _termination(reason, table)
            note(term)
            if current is None:
                episodes.append(Episode(EPISODE, param_id, resolved, None, bar, (), term))
            else:
                current.close_stage(bar)
                current.termination = term
                finish_current()
            current = _Open(resolved, param_id, opened_by_reset=True)
            current.enter(_AWAITING, bar)

    if current is not None:
        if current.opened_by_reset and not current.has_left_awaiting() and current.termination is None:
            current = None
        else:
            finish_current()

    return Projection(
        tuple(episodes),
        tuple(positions),
        flags["DECISION"],
        flags["OBSERVATION"],
        flags["PRODUCER"],
        counts,
        tuple(unmapped),
        0,
    )


def project_events_file(path: Path | str, *, founding: str, run_id: Optional[str] = None) -> Projection:
    rows = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return project_events(rows, founding=founding, run_id=run_id)
