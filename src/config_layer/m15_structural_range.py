"""M15 structural liquidity range — the CRT sweep envelope.

Distinct from:
  * ``runtime.backtest_v2.HTFBuilder`` — reset CLOCK only (count window / id flip).
  * ``config_layer.parent_crt.ParentRange`` — calendar-true parent C1 high/low.

This module owns the *name* and *type* of the object ``detect_sweep`` reads.
It does not own a new formula: ``h_ref`` / ``l_ref`` remain max-high / min-low
of the child window the caller supplies (CH-m15-structural-liquidity-range;
geometry unchanged).

CURRENT construction (CHARACTERIZED, not domain-certified):
  first seed  = HTFBuilder completed list (``htf_candles_per_range`` bars)
  later rebuild = ``candle_buffer[-atr_period:]``
The name does not certify institutional structure. Binding a different
geometry is a separate authorized change.

``htf_candle_id`` is a LEGACY field name kept so existing ``Range(...)``
constructors stay valid. It stores the HTFBuilder *clock* id used by
``ResetLogic``. It does not mean this range IS that HTF window.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from config_layer.state_identity import Direction

OBJECT_ID = "M15-SLR"
CANONICAL_NAME = "M15_STRUCTURAL_LIQUIDITY_RANGE"
DISPLAY_NAME = "M15 structural liquidity range"
SEMANTIC_NODE_ID = "SEM-011"


@dataclass
class M15StructuralLiquidityRange:
    """Sweep envelope for the M15 CRT lifecycle (RANGE → SWEEP → …)."""

    h_ref: float
    l_ref: float
    equilibrium: float
    formed_at: datetime
    htf_candle_id: str
    session: str = "UNKNOWN"
    child_count: int = 0

    @property
    def clock_id(self) -> str:
        """HTFBuilder reset-clock id. Same value as ``htf_candle_id`` (legacy name)."""
        return self.htf_candle_id

    @property
    def object_id(self) -> str:
        return OBJECT_ID

    @property
    def size(self) -> float:
        return self.h_ref - self.l_ref

    def is_inside(self, price: float) -> bool:
        return self.l_ref <= price <= self.h_ref

    def retrace_depth(self, price: float, direction: Direction) -> float:
        if direction == Direction.LONG:
            return (price - self.l_ref) / self.size if self.size > 0 else 0.0
        return (self.h_ref - price) / self.size if self.size > 0 else 0.0


def from_child_window(
    candles: list,
    clock_id: str,
    session: str = "UNKNOWN",
    formed_at: datetime | None = None,
) -> M15StructuralLiquidityRange:
    """Build the envelope from a child-candle list. Same identities as the
    former ``RangeDetector.detect_htf_range`` body: h=max high, l=min low,
    eq=(h+l)/2. Callers choose *which* children; this function does not.
    """
    if not candles:
        raise ValueError("M15 structural liquidity range requires at least one child candle")
    h_ref = max(c.high for c in candles)
    l_ref = min(c.low for c in candles)
    ts = formed_at if formed_at is not None else candles[-1].timestamp
    return M15StructuralLiquidityRange(
        h_ref=h_ref,
        l_ref=l_ref,
        equilibrium=(h_ref + l_ref) / 2,
        formed_at=ts,
        htf_candle_id=clock_id,
        session=session,
        child_count=len(candles),
    )


# Historical name. Call sites that still say ``Range`` mean this object.
Range = M15StructuralLiquidityRange
