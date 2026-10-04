"""SEM-031 primitives: calendar parents, SP-001 sweep, SP-002 displacement, return, RR.

No CRT engine. No ParentCRT C1/C2/C3. No visual_crt. Thresholds live on VetoParams
(docs/research/sujan_veto_chain_object.md). No silent defaults.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from features.calendar_periods import period_key, period_start
from structure.predicates import directional_impulse, swept_high, swept_low

MEASURABLE_PARENTS = ("MN1", "W1", "D1", "H4")
UNMEASURABLE_PARENTS = ("6M", "3M")


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
class VetoParams:
    expansion_min_range_ratio: float
    accumulation_max_range_ratio: float
    distribution_min_range_ratio: float
    location_tolerance_atr: float
    rr_floor: float
    max_sweep_age_bars: int
    max_return_age_bars: int

    def __post_init__(self) -> None:
        if self.expansion_min_range_ratio <= 0:
            raise ValueError("expansion_min_range_ratio must be > 0")
        if self.accumulation_max_range_ratio <= 0:
            raise ValueError("accumulation_max_range_ratio must be > 0")
        if self.distribution_min_range_ratio <= 0:
            raise ValueError("distribution_min_range_ratio must be > 0")
        if self.location_tolerance_atr < 0:
            raise ValueError("location_tolerance_atr must be >= 0")
        if self.rr_floor <= 0:
            raise ValueError("rr_floor must be > 0")
        if self.max_sweep_age_bars < 1:
            raise ValueError("max_sweep_age_bars must be >= 1")
        if self.max_return_age_bars < 1:
            raise ValueError("max_return_age_bars must be >= 1")


@dataclass(frozen=True)
class SweepEvent:
    direction: str
    sweep_price: float
    level_price: float
    bar_index: int
    formed_at_index: int
    level_kind: str


@dataclass(frozen=True)
class DisplacementEvent:
    sweep: SweepEvent
    bar_index: int
    high: float
    low: float
    close: float


def body_bias(bar: Bar) -> str:
    if bar.close > bar.open:
        return "long"
    if bar.close < bar.open:
        return "short"
    return "none"


def closed_parents(bars: Sequence[Bar], rule: str) -> list[Bar]:
    """Calendar-true closed parents. The in-progress bucket is dropped."""
    if not bars:
        return []
    groups: list[tuple[object, list[Bar]]] = []
    current_key = None
    bucket: list[Bar] = []
    for b in bars:
        key = period_key(b.timestamp, rule)
        if current_key is None:
            current_key = key
            bucket = [b]
            continue
        if key != current_key:
            groups.append((current_key, bucket))
            current_key = key
            bucket = [b]
        else:
            bucket.append(b)
    out: list[Bar] = []
    for i, (key, chunk) in enumerate(groups):
        ts = period_start(key, rule)
        out.append(
            Bar(
                timestamp=ts,
                open=chunk[0].open,
                high=max(x.high for x in chunk),
                low=min(x.low for x in chunk),
                close=chunk[-1].close,
                volume=sum(x.volume for x in chunk),
                index=chunk[-1].index,
            )
        )
    return out


def parent_levels(parents: Sequence[Bar], kind_prefix: str) -> list[tuple[str, float, int]]:
    """(kind, price, formed_at_index) for high / low / mid of the last closed parent."""
    if not parents:
        return []
    last = parents[-1]
    mid = (last.high + last.low) / 2.0
    return [
        (f"{kind_prefix}_high", last.high, last.index),
        (f"{kind_prefix}_low", last.low, last.index),
        (f"{kind_prefix}_mid", mid, last.index),
    ]


def detect_parent_sweep(
    bar: Bar,
    levels: Sequence[tuple[str, float, int]],
) -> SweepEvent | None:
    """SP-001 against prior closed-parent levels. Deepest pierce wins."""
    best: SweepEvent | None = None
    best_depth = 0.0
    for kind, price, formed_at in levels:
        if formed_at >= bar.index:
            continue
        if kind.endswith("_high") or kind.endswith("_mid"):
            if kind.endswith("_high") and swept_high(bar.high, bar.close, price):
                depth = bar.high - price
                if depth > best_depth or best is None:
                    best_depth = depth
                    best = SweepEvent(
                        direction="short",
                        sweep_price=bar.high,
                        level_price=price,
                        bar_index=bar.index,
                        formed_at_index=formed_at,
                        level_kind=kind,
                    )
        if kind.endswith("_low"):
            if swept_low(bar.low, bar.close, price):
                depth = price - bar.low
                if depth > best_depth or best is None:
                    best_depth = depth
                    best = SweepEvent(
                        direction="long",
                        sweep_price=bar.low,
                        level_price=price,
                        bar_index=bar.index,
                        formed_at_index=formed_at,
                        level_kind=kind,
                    )
    return best


def detect_displacement(
    bars: Sequence[Bar],
    sweep: SweepEvent,
    max_age: int,
) -> DisplacementEvent | None:
    is_long = sweep.direction == "long"
    start = sweep.bar_index + 1
    end = min(len(bars), sweep.bar_index + 1 + max_age)
    for i in range(start, end):
        b = bars[i]
        if directional_impulse(b.open, b.close, sweep.sweep_price, is_long=is_long):
            return DisplacementEvent(
                sweep=sweep,
                bar_index=b.index,
                high=b.high,
                low=b.low,
                close=b.close,
            )
    return None


def detect_return(
    bars: Sequence[Bar],
    disp: DisplacementEvent,
    max_age: int,
) -> Bar | None:
    start = disp.bar_index + 1
    end = min(len(bars), disp.bar_index + 1 + max_age)
    for i in range(start, end):
        b = bars[i]
        overlaps = b.low <= disp.high and b.high >= disp.low
        if overlaps:
            return b
    return None


def structural_stop(disp: DisplacementEvent) -> float:
    if disp.sweep.direction == "long":
        return min(disp.sweep.sweep_price, disp.low)
    return max(disp.sweep.sweep_price, disp.high)


def daily_target(daily: Bar, direction: str) -> float:
    if direction == "long":
        return daily.high
    return daily.low


def reward_to_risk(entry: float, stop: float, target: float) -> float | None:
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    return abs(target - entry) / risk


def location_admitted(
    entry: float,
    levels: Sequence[tuple[str, float, int]],
    *,
    entry_index: int,
    atr: float,
    tolerance_atr: float,
) -> tuple[bool, str | None]:
    band = tolerance_atr * atr
    best_kind: str | None = None
    best_dist = None
    for kind, price, formed_at in levels:
        if formed_at >= entry_index:
            continue
        dist = abs(entry - price)
        if dist <= band and (best_dist is None or dist < best_dist):
            best_dist = dist
            best_kind = kind
    return best_kind is not None, best_kind
