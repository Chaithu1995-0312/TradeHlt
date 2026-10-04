"""DEX-03 fill. An admitted plan becomes a position at the TRS-04 entry's bar and price.

Entry slippage is a TRS-07 cost, never folded into the price, so it is charged once.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from semantics.execution.portfolio import ADMITTED, Admission
from semantics.identity import parameterization_id
from semantics.trading.entry import Entry

FILL = "DEX-03"


@dataclass(frozen=True)
class Fill:
    """DEX-03. divergence carries the TRS-04 legacy note when the entry is approval_bar_legacy."""

    concept_id: str
    parameterization_id: str
    available_at: int
    price: float
    bar: int
    entry_semantics: str
    divergence: Optional[str] = None


def fill(entry: Entry, admission: Admission) -> Optional[Fill]:
    """None when the plan was FILTERED. Never earlier than the entry or the admission (I-6)."""
    if admission.verdict != ADMITTED:
        return None
    pid = parameterization_id(FILL, {"entry_semantics": entry.entry_semantics}, ("entry_semantics",))
    available = max(entry.available_at, admission.available_at, entry.bar)
    return Fill(FILL, pid, available, float(entry.price), entry.bar, entry.entry_semantics, entry.divergence)
