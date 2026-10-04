"""The FOUNDING layer for SEM-033 — still incomplete, now with an approved proxy.

BULK_CANDLE_SELECTOR = APPROVED_PROXY_UNVALIDATED
-------------------------------------------------
A "parent bulk candle" is, on current evidence, a VISUAL CONCEPT: a visually dominant
candle that defines a range. The evidence says it is *often* large-bodied and *may* be
wick-dominant, and **no approved percentage threshold exists**.

Until 2026-08-29 this package shipped NO selector at all and the constant read
``UNRESOLVED``. The human bridge then approved a **mechanical proxy** (drift log Record 6):
top-N over the whole corpus by ``candle_range`` and, separately, by ``body_size``. That
proxy is SEM-034 and its status is ``UNVALIDATED`` — it has never been agreement-checked
against a hand-labelled set, so it shortlists for confirmation and does not define the
concept. **UNK-007 stays OPEN.**

The charter permits a proxy only when it is bridge-approved, recorded, and still linked to
the original; all three hold. What is still forbidden is a SECOND selector appearing here
without its own recorded freeze.

Two conforming implementations therefore ship:

* ``ExplicitTimestampSelector`` — decides nothing; resolves timestamps the bridge already
  chose and fails closed on any it cannot find.
* ``bulk_proxy.TopNRangeSelector`` / ``TopNBodySelector`` — the recorded SEM-034 proxy.

This mirrors ``structure.predicates``' own doctrine: the arithmetic is shared, the
FOUNDING (which level counts as liquidity) stays with the caller. That independence is
what makes this a new object rather than a re-run of an existing one.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, Sequence, runtime_checkable

#: Status token, asserted by ``tests/research/test_sujan_manipulation.py``.
#: ``APPROVED_PROXY_UNVALIDATED`` — a bridge-approved mechanical proxy (SEM-034) exists,
#: but the concept itself is NOT resolved: UNK-007 stays open until the proxy is
#: agreement-checked against a hand-labelled set. Any FURTHER selector requires its own
#: freeze recorded in ``docs/research/sujan_identity_drift_log.md``.
BULK_CANDLE_SELECTOR = "APPROVED_PROXY_UNVALIDATED"

#: What is known about the concept, verbatim from the Phase-1 specification. Recorded
#: here so the ambiguity travels with the code instead of living only in a doc.
BULK_CANDLE_EVIDENCE = (
    "visually dominant",
    "often large-bodied",
    "may also be wick-dominant",
    "no approved percentage threshold exists",
)


@dataclass(frozen=True)
class Bar:
    """One candle. ``index`` is the row ordinal and is the no-lookahead currency."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    index: int


@dataclass(frozen=True)
class ParentBulkCandle:
    """A bulk candle SUPPLIED from outside. ``source`` records who chose it."""

    timestamp: datetime
    high: float
    low: float
    index: int
    source: str


@dataclass(frozen=True)
class ParentRange:
    """Range High = parent HIGH, Range Low = parent LOW. Full wick-to-wick.

    Body-only interpretations are REJECTED by the frozen definition, so this object
    has no body fields at all — the rejected reading is not constructible from it.
    """

    high: float
    low: float
    parent_index: int
    parent_timestamp: datetime

    def __post_init__(self) -> None:
        if not self.high > self.low:
            raise ValueError(
                f"parent range high must exceed low (high={self.high}, low={self.low})"
            )


def parent_range(parent: ParentBulkCandle) -> ParentRange:
    """Full wick-to-wick range of a supplied bulk candle."""
    return ParentRange(
        high=parent.high,
        low=parent.low,
        parent_index=parent.index,
        parent_timestamp=parent.timestamp,
    )


@runtime_checkable
class ParentSelector(Protocol):
    """How bulk candles enter the system.

    Implementations live OUTSIDE this package unless they merely resolve a choice the
    caller already made. A conforming implementation that inspects ``bars`` to decide
    which candle is "bulk" would be resolving BULK_CANDLE_SELECTOR, and that requires a
    human-bridge freeze first.
    """

    def select(self, bars: Sequence[Bar]) -> Sequence[ParentBulkCandle]:  # pragma: no cover
        ...


class ExplicitTimestampSelector:
    """Resolves caller-supplied timestamps to bars. Chooses nothing itself.

    Fails closed: a timestamp with no exactly matching bar raises. A near-match is not
    silently accepted, because "nearest bar" would be an invented rule.
    """

    def __init__(self, timestamps: Sequence[datetime], *, source: str) -> None:
        if not timestamps:
            raise ValueError("no parent bulk-candle timestamps supplied")
        if not source:
            raise ValueError("source is required — who chose these candles must be recorded")
        self._timestamps = tuple(timestamps)
        self._source = source

    @property
    def timestamps(self) -> tuple[datetime, ...]:
        return self._timestamps

    @property
    def source(self) -> str:
        return self._source

    def select(self, bars: Sequence[Bar]) -> tuple[ParentBulkCandle, ...]:
        by_ts = {bar.timestamp: bar for bar in bars}
        missing = [ts for ts in self._timestamps if ts not in by_ts]
        if missing:
            shown = ", ".join(ts.isoformat(sep=" ") for ts in missing[:5])
            raise ValueError(
                f"{len(missing)} supplied parent timestamp(s) match no bar in the corpus: {shown}"
                " — no nearest-bar fallback exists; supply timestamps that match the corpus grid"
            )
        chosen = [by_ts[ts] for ts in self._timestamps]
        return tuple(
            ParentBulkCandle(
                timestamp=bar.timestamp,
                high=bar.high,
                low=bar.low,
                index=bar.index,
                source=self._source,
            )
            for bar in sorted(chosen, key=lambda b: b.index)
        )


def _parse_ts(raw: str) -> datetime:
    s = str(raw).strip().replace("T", " ")
    return datetime.fromisoformat(s[:19])


def load_parent_timestamps(path: Path) -> list[datetime]:
    """Read an externally-produced parent list.

    Accepts a JSON array of timestamp strings, a JSON object with a ``timestamps`` key,
    or a CSV with a ``timestamp`` column. Nothing else — the format is dumb on purpose,
    because the file is the human bridge's chart reading, not a computed artifact.
    """
    if not path.exists():
        raise FileNotFoundError(f"parent bulk-candle list not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".csv":
        rows = list(csv.DictReader(text.splitlines()))
        if not rows or "timestamp" not in rows[0]:
            raise ValueError(f"{path}: CSV parent list needs a 'timestamp' column")
        raw = [row["timestamp"] for row in rows]
    else:
        payload = json.loads(text)
        if isinstance(payload, dict):
            payload = payload.get("timestamps")
        if not isinstance(payload, list):
            raise ValueError(
                f"{path}: expected a JSON array of timestamps or an object with 'timestamps'"
            )
        raw = payload
    if not raw:
        raise ValueError(f"{path}: parent bulk-candle list is empty")
    return [_parse_ts(item) for item in raw]
