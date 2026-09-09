"""t=0 mother-range inside-close geometry (SEM-026).

No CRT engine. No TradeLib. No outcomes. Thresholds are frozen in
docs/research/mother_range_trade_object.md / MC-MRANGE-XAUUSD-M15-V1.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

BLOCK_BARS = 16
LOOKBACK = 20
ATR_MULT = 1.5
BLOCK_HOURS = 4.0


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    index: int


@dataclass(frozen=True)
class InsideCloseEntry:
    entry_index: int
    timestamp: datetime
    direction: str
    entry: float
    sl: float
    tp: float
    risk: float
    inside_score: float
    mother_high: float
    mother_low: float
    mother_range: float
    big_threshold: float


@dataclass(frozen=True)
class _Block:
    start_index: int
    end_index: int  # inclusive, last bar
    high: float
    low: float
    last_close: float
    last_ts: datetime


def _floor_4h(ts: datetime) -> datetime:
    hour = (ts.hour // 4) * 4
    return ts.replace(hour=hour, minute=0, second=0, microsecond=0)


def build_calendar_blocks(bars: Sequence[Bar]) -> list[_Block]:
    if not bars:
        return []
    groups: dict[datetime, list[Bar]] = {}
    order: list[datetime] = []
    for b in bars:
        key = _floor_4h(b.timestamp)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(b)
    out: list[_Block] = []
    for key in order:
        chunk = groups[key]
        out.append(
            _Block(
                start_index=chunk[0].index,
                end_index=chunk[-1].index,
                high=max(x.high for x in chunk),
                low=min(x.low for x in chunk),
                last_close=chunk[-1].close,
                last_ts=chunk[-1].timestamp,
            )
        )
    return out


def detect_inside_close_entries(
    bars: Sequence[Bar],
    *,
    lookback: int = LOOKBACK,
    atr_mult: float = ATR_MULT,
) -> list[InsideCloseEntry]:
    """Causal entries. Decision uses only bars at or before C2."""
    blocks = build_calendar_blocks(bars)
    if len(blocks) < lookback + 2:
        return []
    entries: list[InsideCloseEntry] = []
    for i in range(lookback, len(blocks) - 1):
        mother = blocks[i]
        test = blocks[i + 1]
        r1 = mother.high - mother.low
        if r1 <= 0:
            continue
        prior = [blocks[j].high - blocks[j].low for j in range(i - lookback, i)]
        thresh = atr_mult * (sum(prior) / lookback)
        if r1 <= thresh:
            continue
        c2 = test.last_close
        if c2 < mother.low or c2 > mother.high:
            continue
        score = (c2 - mother.low) / r1
        if score == 0.5:
            continue
        if score < 0.5:
            direction = "long"
            sl = mother.low
            tp = mother.high
        else:
            direction = "short"
            sl = mother.high
            tp = mother.low
        risk = abs(c2 - sl)
        if risk <= 0:
            continue
        entries.append(
            InsideCloseEntry(
                entry_index=test.end_index,
                timestamp=test.last_ts,
                direction=direction,
                entry=c2,
                sl=sl,
                tp=tp,
                risk=risk,
                inside_score=score,
                mother_high=mother.high,
                mother_low=mother.low,
                mother_range=r1,
                big_threshold=thresh,
            )
        )
    return entries
