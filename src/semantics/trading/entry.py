"""TRS-04 entry. resting_order is the contract value. approval_bar_legacy is recorded."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from semantics.identity import parameterization_id
from semantics.market.events import MarketEvent
from semantics.types import Bar

ENTRY = "TRS-04"
RESTING_ORDER = "resting_order"
APPROVAL_BAR_LEGACY = "approval_bar_legacy"
LEGACY_DIVERGENCE = "TRS-04 approval_bar_legacy"
RETEST_TOUCH = "MKT-E09"


@dataclass(frozen=True)
class Entry:
    """TRS-04. divergence is set only for the legacy approval-bar booking."""

    concept_id: str
    parameterization_id: str
    available_at: int
    price: float
    bar: int
    entry_semantics: str
    divergence: Optional[str] = None


def _pid(semantics: str) -> str:
    return parameterization_id(ENTRY, {"entry_semantics": semantics}, ("entry_semantics",))


def resting_entry(retest_bar: Bar, event: Optional[MarketEvent] = None) -> Entry:
    """Price and bar are the MKT-E09 retest bar's close. There is no MKT-E09 constructor;
    the bar is the input. A supplied event must be that concept on that bar."""
    if event is not None:
        if event.concept_id != RETEST_TOUCH:
            raise ValueError(f"TRS-04 resting_order expects {RETEST_TOUCH}, got {event.concept_id}")
        if event.bar != retest_bar.index:
            raise ValueError(
                f"TRS-04 retest event bar {event.bar} does not match the retest bar {retest_bar.index}"
            )
    return Entry(
        ENTRY, _pid(RESTING_ORDER), retest_bar.index, float(retest_bar.close),
        retest_bar.index, RESTING_ORDER, None,
    )


def legacy_entry(retest_bar: Bar, approval_bar: int) -> Entry:
    """The retest close booked on a later approval bar. available_at is the approval bar (I-6)."""
    if approval_bar < retest_bar.index:
        raise ValueError(
            f"TRS-04 approval bar {approval_bar} is earlier than the retest bar {retest_bar.index} (I-6)"
        )
    return Entry(
        ENTRY, _pid(APPROVAL_BAR_LEGACY), approval_bar, float(retest_bar.close),
        approval_bar, APPROVAL_BAR_LEGACY, LEGACY_DIVERGENCE,
    )
