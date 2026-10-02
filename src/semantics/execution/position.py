"""DEX-05 position under DEX-06 exit schedule and DEX-07 exit rule.

The resting exits (stop, TP1 partial, trailed runner, TP2, stop first on a shared bar) ARE
`research.oracle.multi_tp_walk`; nothing here re-walks them. A DEX-07 rule that fires on the
k-th bar after the fill closes the position at that bar's close AFTER the bar's resting fills
(after_resting_fills). That is exactly a walk truncated to k bars with TIMEOUT_MARK_TO_CLOSE:
the walk settles every bar's stop/targets first and marks the remainder at the last close.

The thesis invalidation is recorded on the thesis by slice-2 code (mark_failed) whatever the
rule says; this module only reads it (D3-1). Closing a position never changes the thesis.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

from research.oracle.multi_tp_walk import (
    OUT_STOPPED, OUT_TIMEOUT, OUT_TP1_BE_STOP, OUT_TP1_TP2,
    TIE_BREAK_PRODUCTION, TIMEOUT_MARK_TO_CLOSE, multi_tp_walk,
)

from semantics import geometry as gp
from semantics.execution.approval import FILTERED as APPROVAL_FILTERED, Approval
from semantics.execution.fill import Fill
from semantics.identity import parameterization_id
from semantics.trading.plan import TradePlan
from semantics.trading.roles import breach
from semantics.types import Bias, Side

POSITION = "DEX-05"
EXIT_SCHEDULE = "DEX-06"
EXIT_RULE = "DEX-07"

OPEN = "OPEN"
PARTIAL = "PARTIAL"
CLOSED = "CLOSED"

STOP_FIRST = "stop_first"
HOLD = "hold"
CLOSE_ON_INVALIDATION = "close_on_invalidation"
CLOSE_ON_ORIGIN = "close_on_origin"
ON_INVALIDATION = (HOLD, CLOSE_ON_INVALIDATION, CLOSE_ON_ORIGIN)
AFTER_RESTING_FILLS = "after_resting_fills"


class ExitReason(str, Enum):
    """DEX-05 lifecycle.exit_reasons (V-18 pins this list to the contract)."""
    STOP = "STOP"
    TRAIL_STOP = "TRAIL_STOP"
    TARGET_FINAL = "TARGET_FINAL"
    INVALIDATION = "INVALIDATION"
    ORIGIN = "ORIGIN"
    TIMEOUT = "TIMEOUT"
    UNCONFIRMED = "UNCONFIRMED"


#: Cost-model exit kind of each reason. Rule exits are market closes: not stop orders.
STOP_EXIT_REASONS = (ExitReason.STOP, ExitReason.TRAIL_STOP)

_WALK_REASON = {
    OUT_STOPPED: ExitReason.STOP,
    OUT_TP1_BE_STOP: ExitReason.TRAIL_STOP,
    OUT_TP1_TP2: ExitReason.TARGET_FINAL,
}

#: Same-bar order when several rules fire on one bar (deterministic, documented).
_RULE_ORDER = (ExitReason.UNCONFIRMED, ExitReason.INVALIDATION, ExitReason.ORIGIN, ExitReason.TIMEOUT)


@dataclass(frozen=True)
class ExitSchedule:
    """DEX-06. trail_fraction 0 = breakeven, 0.5 = half way (production, F-088)."""

    concept_id: str
    parameterization_id: str
    available_at: int
    partial_fraction: float
    trail_fraction: float
    tie_break: str


@dataclass(frozen=True)
class ExitRule:
    """DEX-07. ttl_bars None = no time limit."""

    concept_id: str
    parameterization_id: str
    available_at: int
    on_invalidation: str
    precedence: str
    ttl_bars: Optional[int]


@dataclass(frozen=True)
class Position:
    """DEX-05. gross_r / exit_* are None while the position is not CLOSED."""

    concept_id: str
    parameterization_id: str
    available_at: int
    state: str
    direction: Bias
    fill: Fill
    schedule: ExitSchedule
    rule: ExitRule
    exit_reason: Optional[ExitReason]
    exit_bar: Optional[int]
    exit_price: Optional[float]
    gross_r: Optional[float]
    reached_tp1: bool
    tp1_bar: Optional[int]
    risk_distance: float

    @property
    def stop_exit(self) -> bool:
        return self.exit_reason in STOP_EXIT_REASONS


def exit_schedule(partial_fraction: float, trail_fraction: float, *, plan_bar: int,
                  tie_break: str = STOP_FIRST) -> ExitSchedule:
    if not 0.0 < float(partial_fraction) <= 1.0:
        raise ValueError(f"DEX-06 partial_fraction {partial_fraction!r} must be in (0, 1]")
    if not 0.0 <= float(trail_fraction) <= 1.0:
        raise ValueError(f"DEX-06 trail_fraction {trail_fraction!r} must be in [0, 1]")
    if tie_break != STOP_FIRST:
        raise ValueError(f"DEX-06 tie_break {tie_break!r} is outside ['{STOP_FIRST}']")
    params = {"partial_fraction": float(partial_fraction), "trail_fraction": float(trail_fraction),
              "tie_break": tie_break}
    pid = parameterization_id(EXIT_SCHEDULE, params, tuple(params))
    return ExitSchedule(EXIT_SCHEDULE, pid, plan_bar, float(partial_fraction), float(trail_fraction), tie_break)


def exit_rule(on_invalidation: str, *, plan_bar: int, ttl_bars: Optional[int] = None,
              precedence: str = AFTER_RESTING_FILLS) -> ExitRule:
    if on_invalidation not in ON_INVALIDATION:
        raise ValueError(f"DEX-07 on_invalidation {on_invalidation!r} is outside {ON_INVALIDATION}")
    if precedence != AFTER_RESTING_FILLS:
        # `absolute` is a legacy value with a recorded divergence (it can cancel a fill that
        # already happened on the bar); the contract never builds it.
        raise ValueError(f"DEX-07 precedence {precedence!r}: only '{AFTER_RESTING_FILLS}' is the contract value")
    if ttl_bars is not None and (type(ttl_bars) is not int or ttl_bars < 1):
        raise ValueError(f"DEX-07 ttl_bars {ttl_bars!r} must be an int >= 1 or None")
    params = {"on_invalidation": on_invalidation, "precedence": precedence, "ttl_bars": ttl_bars}
    pid = parameterization_id(EXIT_RULE, params, tuple(params))
    return ExitRule(EXIT_RULE, pid, plan_bar, on_invalidation, precedence, ttl_bars)


def _target_price(plan: TradePlan, ordinal: int) -> float:
    for target in plan.targets:
        if target.ordinal == ordinal:
            return float(target.price)
    raise ValueError(f"DEX-06 the plan needs a target of ordinal {ordinal}")


def _first(bars: Sequence, predicate) -> Optional[int]:
    """1-based position of the first bar satisfying the predicate."""
    for k, bar in enumerate(bars, start=1):
        if predicate(bar):
            return k
    return None


def _rule_firings(plan: TradePlan, fill: Fill, rule: ExitRule, bars: Sequence,
                  origin_price: Optional[float], approval: Optional[Approval]) -> dict:
    thesis = plan.thesis
    firings: dict = {}
    if approval is not None and approval.verdict == APPROVAL_FILTERED:
        if approval.bar <= fill.bar:
            raise ValueError("DEX-04 a plan FILTERED on or before its fill bar never fills (no position)")
        k = _first(bars, lambda b: b.index == approval.bar)
        if k is not None:
            firings[ExitReason.UNCONFIRMED] = k
    if rule.on_invalidation == CLOSE_ON_INVALIDATION:
        k = _first(bars, lambda b: breach(thesis.invalidation, b, thesis.direction) is not None)
        if k is not None:
            firings[ExitReason.INVALIDATION] = k
    if rule.on_invalidation == CLOSE_ON_ORIGIN:
        if origin_price is None:
            raise ValueError("DEX-07 close_on_origin needs the founding MKT-E04 candle's open")
        side = Side.LOWER if thesis.direction is Bias.LONG else Side.UPPER
        k = _first(bars, lambda b: gp.beyond(b, float(origin_price), side))
        if k is not None:
            firings[ExitReason.ORIGIN] = k
    if rule.ttl_bars is not None and rule.ttl_bars <= len(bars):
        firings[ExitReason.TIMEOUT] = rule.ttl_bars
    return firings


def replay_position(
    plan: TradePlan,
    fill: Fill,
    schedule: ExitSchedule,
    rule: ExitRule,
    future_bars: Sequence,
    *,
    origin_price: Optional[float] = None,
    approval: Optional[Approval] = None,
) -> Position:
    """bar_replay of one position. `future_bars` are the bars strictly after the fill bar.

    `approval` is the DEX-04 verdict when it follows a resting fill; FILTERED closes the
    position at that bar's close (UNCONFIRMED). The earliest firing rule wins; on one bar the
    order is UNCONFIRMED, INVALIDATION, ORIGIN, TIMEOUT. Without a firing rule the walk runs
    over every bar given; reaching their end leaves the position OPEN or PARTIAL.
    """
    if fill.price != plan.entry.price:
        raise ValueError("DEX-03 the fill price must be the plan's entry price")
    direction = plan.thesis.direction
    if direction not in (Bias.LONG, Bias.SHORT):
        raise ValueError(f"DEX-05 direction {direction!r} is not LONG or SHORT")
    bars = list(future_bars)
    for bar in bars:
        if bar.index <= fill.bar:
            raise ValueError(f"DEX-05 bar {bar.index} is not after the fill bar {fill.bar} (I-6)")
    pid = parameterization_id(POSITION, {}, ())
    risk = plan.R
    tp1 = _target_price(plan, 1)
    tp2 = _target_price(plan, 2)
    firings = _rule_firings(plan, fill, rule, bars, origin_price, approval)
    reason_at = None
    horizon = len(bars)
    if firings:
        horizon = min(firings.values())
        reason_at = next(r for r in _RULE_ORDER if firings.get(r) == horizon)
    walked = bars[:horizon]
    if not walked:
        return Position(POSITION, pid, fill.available_at, OPEN, direction, fill, schedule, rule,
                        None, None, None, None, False, None, risk)
    result = multi_tp_walk(
        fill.price, "long" if direction is Bias.LONG else "short", plan.stop.price, tp1, tp2, walked,
        partial_fraction=schedule.partial_fraction, trail_fraction=schedule.trail_fraction,
        tie_break=TIE_BREAK_PRODUCTION, timeout_pricing=TIMEOUT_MARK_TO_CLOSE,
        max_forward=len(walked), entry_index=fill.bar,
    )
    last_bar = int(walked[result.duration_candles - 1].index)
    tp1_bar = None if result.bars_to_tp1 is None else int(walked[result.bars_to_tp1 - 1].index)
    if result.outcome == OUT_TIMEOUT:
        if reason_at is None:
            state = PARTIAL if result.reached_tp1 else OPEN
            return Position(POSITION, pid, last_bar, state, direction, fill, schedule, rule,
                            None, None, None, None, result.reached_tp1, tp1_bar, risk)
        exit_reason = reason_at
    else:
        exit_reason = _WALK_REASON[result.outcome]
    return Position(POSITION, pid, last_bar, CLOSED, direction, fill, schedule, rule,
                    exit_reason, last_bar, float(result.exit_price), float(result.rr_gross),
                    result.reached_tp1, tp1_bar, risk)
