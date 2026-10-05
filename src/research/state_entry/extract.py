"""Engine events -> hypothetical entry units (MC-STATEENTRY population).

A SETUP starts at an engine ``SWEEP`` event — its direction is the setup direction
(``crt_engine_v2.try_range_to_sweep`` sets ``state.direction = sweep.direction``) — and
ends at the next ``SWEEP`` event. Every later event of the setup inherits that direction,
the sweep candle and (once seen) the displacement candle.

Events are joined to corpus bars by TIMESTAMP. The engine's ``candle_index`` is its own
counter and does not equal the corpus row, so joining by index would silently shift every
entry.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Sequence

# Sealed by the contract. Order is the funnel order.
ENTER_SWEEP = "ENTER_SWEEP"
ENTER_SHADOW_PENDING = "ENTER_SHADOW_PENDING"
ENTER_DISPLACEMENT = "ENTER_DISPLACEMENT"
ENTER_EXPANSION = "ENTER_EXPANSION"
ENTER_RETEST = "ENTER_RETEST"
EXECUTION_LEGACY = "EXECUTION_LEGACY"
EXECUTION_AT_APPROVAL = "EXECUTION_AT_APPROVAL"
REJECTED_AT_CONFIRMATION = "REJECTED_AT_CONFIRMATION"

ENTRY_KINDS = (
    ENTER_SWEEP,
    ENTER_SHADOW_PENDING,
    ENTER_DISPLACEMENT,
    ENTER_EXPANSION,
    ENTER_RETEST,
    EXECUTION_LEGACY,
    EXECUTION_AT_APPROVAL,
    REJECTED_AT_CONFIRMATION,
)

_TRANSITION_KIND = {
    "SWEEP": ENTER_SWEEP,
    "SHADOW_PENDING": ENTER_SHADOW_PENDING,
    "DISPLACEMENT": ENTER_DISPLACEMENT,
    "EXPANSION": ENTER_EXPANSION,
    "RETEST": ENTER_RETEST,
}

# Engine events that end a confirmed setup without a trade (the counterfactual control).
REJECTION_EVENTS = frozenset({
    "FILTER_REJECTED",
    "SHADOW_ADVISORY_BLOCK",
    "TRADE_BUILD_REJECTED",
    "TRADE_UNCONFIRMED",
})

_TS_FMT = "%Y-%m-%dT%H:%M:%S"


@dataclass(frozen=True)
class Bar:
    """One corpus bar. ``index`` is the corpus ROW (0-based), the walk kernel's clock."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    index: int


@dataclass(frozen=True)
class EntryUnit:
    """One hypothetical entry: (setup, entry_kind, direction) at one bar close."""

    entry_kind: str
    direction: str                 # "long" | "short"
    entry_row: int                 # corpus row of the bar whose close is the decision
    entry_price: float
    setup_sweep_row: int
    sweep_row: int                 # the sweep candle (structural stop for ENTER_SWEEP)
    displacement_row: Optional[int]
    engine_atr: Optional[float]    # metadata.atr carried by the event, price units
    # EXECUTION_LEGACY only: the engine's own levels (stale retest-close fill, F-110).
    engine_levels: Optional[tuple[float, float, float]] = None
    event_ts: str = ""


def ts_key(ts) -> str:
    """Timestamp -> join key. Accepts datetime or the events.jsonl ISO string."""
    if isinstance(ts, str):
        return ts[:19].replace(" ", "T")
    if getattr(ts, "tzinfo", None) is not None:
        ts = ts.replace(tzinfo=None)
    return ts.strftime(_TS_FMT)


def bars_from_candles(candles: Iterable) -> list[Bar]:
    """Corpus candles -> Bars re-indexed by ROW (ignores any engine-stamped index)."""
    return [
        Bar(timestamp=c.timestamp, open=float(c.open), high=float(c.high),
            low=float(c.low), close=float(c.close), index=i)
        for i, c in enumerate(candles)
    ]


def load_events(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


@dataclass
class _Setup:
    direction: str
    sweep_row: int
    displacement_row: Optional[int] = None
    seen: set = field(default_factory=set)


def _direction(raw) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).upper()
    if s.endswith("LONG"):
        return "long"
    if s.endswith("SHORT"):
        return "short"
    return None


def extract_units(events: Sequence[dict], bars: Sequence[Bar]) -> tuple[list[EntryUnit], dict]:
    """Walk the engine's event stream in order and emit one unit per (setup, kind).

    Returns (units, counts). ``counts`` records every drop by reason so the funnel is
    auditable (an event that cannot be placed is counted, never silently skipped).
    """
    row_by_ts = {ts_key(b.timestamp): b.index for b in bars}
    units: list[EntryUnit] = []
    counts: dict[str, int] = {}

    def bump(k: str) -> None:
        counts[k] = counts.get(k, 0) + 1

    setup: Optional[_Setup] = None

    def emit(kind: str, row: int, ev: dict, *, price: Optional[float] = None,
             levels: Optional[tuple[float, float, float]] = None) -> None:
        if kind in setup.seen:
            bump(f"duplicate_{kind}")
            return
        setup.seen.add(kind)
        meta = ev.get("metadata") or {}
        atr = meta.get("atr")
        units.append(EntryUnit(
            entry_kind=kind,
            direction=setup.direction,
            entry_row=row,
            entry_price=float(bars[row].close if price is None else price),
            setup_sweep_row=setup.sweep_row,
            sweep_row=setup.sweep_row,
            displacement_row=setup.displacement_row,
            engine_atr=float(atr) if isinstance(atr, (int, float)) and atr > 0 else None,
            engine_levels=levels,
            event_ts=str(ev.get("timestamp", "")),
        ))
        bump(f"unit_{kind}")

    for ev in events:
        name = ev.get("event")
        row = row_by_ts.get(ts_key(ev.get("timestamp", "")))
        if name is None:
            continue
        if "SWEEP" in name and name != "SWEEP_EXPIRED" and ev.get("direction") is not None:
            # SWEEP / SHADOW_SWEEP: a new setup begins, carrying the sweep direction.
            d = _direction(ev.get("direction"))
            if d is None or row is None:
                bump("setup_unplaceable")
                setup = None
                continue
            setup = _Setup(direction=d, sweep_row=row)
            continue
        if name == "STATE_TRANSITION":
            kind = _TRANSITION_KIND.get(ev.get("state_to") or "")
            if kind is None:
                continue
            if setup is None:
                bump("no_setup_direction")
                continue
            if row is None:
                bump("event_bar_not_in_corpus")
                continue
            if kind == ENTER_DISPLACEMENT:
                # Later stops anchor on the MOST RECENT displacement candle, as the engine's
                # state.displacement_candle does. A repeat inside one setup is counted.
                if setup.displacement_row is not None:
                    bump("redisplacement_in_setup")
                setup.displacement_row = row
            emit(kind, row, ev)
            continue
        if name == "TRADE_OPENED":
            if setup is None or row is None:
                bump("trade_unplaceable")
                continue
            d = _direction(ev.get("direction"))
            if d is not None and d != setup.direction:
                # Never re-label: a trade whose direction disagrees with its setup is counted.
                bump("trade_direction_mismatch")
                continue
            meta = ev.get("metadata") or {}
            try:
                levels = (float(meta["sl"]), float(meta["tp1"]), float(meta["tp2"]))
            except (KeyError, TypeError, ValueError):
                bump("trade_missing_levels")
                continue
            emit(EXECUTION_LEGACY, row, ev, price=float(ev["price"]), levels=levels)
            # Same engine SL level; walk.py re-anchors TP1/TP2 off the approval-bar close.
            emit(EXECUTION_AT_APPROVAL, row, ev, levels=levels)
            continue
        if name in REJECTION_EVENTS:
            if setup is None or row is None:
                bump("rejection_unplaceable")
                continue
            emit(REJECTED_AT_CONFIRMATION, row, ev)
    return units, counts
