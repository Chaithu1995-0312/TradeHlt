"""DEX-02 portfolio admission. Over a cap the plan is FILTERED, never trimmed (D3-4).

Open risk is each open position's risk_fraction at entry; a stop moved after TP1 does not
lower it. Positions of the same thesis count like any other and may overlap (D3-5).
`PortfolioAllocator` is deliberately not called: it trims risk to fit (recorded divergence).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from semantics.execution.size import PositionSize
from semantics.identity import parameterization_id

PORTFOLIO_ADMISSION = "DEX-02"
ADMITTED = "ADMITTED"
FILTERED = "FILTERED"
PORTFOLIO_CAP = "portfolio_cap"


@dataclass(frozen=True)
class Admission:
    """DEX-02. reason_code is None when ADMITTED. size is the unchanged DEX-01 size."""

    concept_id: str
    parameterization_id: str
    available_at: int
    verdict: str
    reason_code: Optional[str]
    size: PositionSize
    bar: int


def admit(
    size: PositionSize,
    open_positions: Sequence[PositionSize],
    *,
    max_concurrent_positions: int,
    max_open_risk: float,
    bar: int,
) -> Admission:
    """`open_positions` are the sizes of the positions open at `bar`'s close.

    The risk sum uses math.fsum so three positions of 0.01 equal a cap of 0.03 (no hidden epsilon).
    """
    if type(max_concurrent_positions) is not int or max_concurrent_positions < 0:
        raise ValueError(f"DEX-02 max_concurrent_positions {max_concurrent_positions!r} must be an int >= 0")
    cap = float(max_open_risk)
    if not 0.0 <= cap <= 1.0:
        raise ValueError(f"DEX-02 max_open_risk {max_open_risk!r} must be a fraction of equity, never a percent")
    if bar < size.available_at:
        raise ValueError(f"DEX-02 bar {bar} is earlier than the size's available_at {size.available_at} (I-6)")
    pid = parameterization_id(
        PORTFOLIO_ADMISSION,
        {"max_concurrent_positions": max_concurrent_positions, "max_open_risk": cap},
        ("max_concurrent_positions", "max_open_risk"),
    )
    fits_count = len(open_positions) + 1 <= max_concurrent_positions
    fits_risk = math.fsum([p.risk_fraction for p in open_positions] + [size.risk_fraction]) <= cap
    if fits_count and fits_risk:
        return Admission(PORTFOLIO_ADMISSION, pid, bar, ADMITTED, None, size, bar)
    return Admission(PORTFOLIO_ADMISSION, pid, bar, FILTERED, PORTFOLIO_CAP, size, bar)
