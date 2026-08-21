"""pools.py — chart-visible liquidity pools for the Visual CRT trade object (SEM-012).

A *pool* is a price level a trader could already have drawn on the chart BEFORE the sweep
bar printed: the high/low of a prior CLOSED calendar H4, or the prior day's high/low.

This is deliberately NOT ``M15StructuralLiquidityRange`` (SEM-011). M15-SLR is the engine's
trailing 14-bar (first-seed 16-bar) count-window envelope — a local extreme, not a level
anyone marked in advance. The monthly TV↔production comparison measured the divergence: of
84 M15-SLR pierces, only 4/84 sat on a prior closed H4 high/low or PDH/PDL at spread
tolerance, and 51/84 touched no SMC level at all. Founding on pools instead of M15-SLR is
what makes this a NEW ontology rather than a re-run of F-019…F-042.

ISOLATION (Hypothesis Protocol, following the ``research.weekly_sweep`` precedent): this
package never imports the live spine at runtime. ``Candle`` is a TYPE_CHECKING-only import.
Enforced by ``tests/research/test_visual_crt_trade_object.py``.

NO-LOOKAHEAD: pools are derived only from parent candles that have already CLOSED.
``features.parent_candle.ParentCandleBuilder.parent_history`` guarantees this — its
in-progress accumulator is never exposed. This module adds no state of its own.

SCOPE (V1, pre-registered): calendar pools only — prior closed H4 high/low and PDH/PDL.
Session-so-far extremes are deliberately EXCLUDED: F-066 established that MT5-sourced
session labels on this exact XAUUSD corpus derive from broker-server time mislabelled UTC
(53.36% of bars carry the wrong session), so a session-extreme pool would inherit a known
clock defect. Adding it is a separate authorized change, not an oversight.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:  # type-only; never a runtime dependency on the spine
    from config_layer.crt_engine_v2 import Candle

#: Pool kinds this module can produce. Closed vocabulary — a new kind is a spec change.
POOL_KINDS = ("PRIOR_H4_HIGH", "PRIOR_H4_LOW", "PDH", "PDL")

#: Which side of price each kind sits on. HIGH pools are swept upward, LOW pools downward.
_POOL_SIDE = {
    "PRIOR_H4_HIGH": "HIGH",
    "PRIOR_H4_LOW": "LOW",
    "PDH": "HIGH",
    "PDL": "LOW",
}


@dataclass(frozen=True)
class LiquidityPool:
    """One chart-visible level, already closed and therefore already drawable."""

    kind: str                # one of POOL_KINDS
    side: str                # "HIGH" | "LOW"
    price: float
    formed_at_index: int     # .index of the last child of the parent that produced it
    source_rule: str         # "H4" | "D1"

    def __post_init__(self) -> None:
        if self.kind not in POOL_KINDS:
            raise ValueError(f"LiquidityPool: unknown kind {self.kind!r} (expected one of {POOL_KINDS})")
        if self.side != _POOL_SIDE[self.kind]:
            raise ValueError(f"LiquidityPool: kind {self.kind!r} must have side {_POOL_SIDE[self.kind]!r}")


def _pools_from_parent(parent: "Candle", rule: str, high_kind: str, low_kind: str) -> list[LiquidityPool]:
    """Both edges of one CLOSED parent candle as pools."""
    return [
        LiquidityPool(
            kind=high_kind,
            side="HIGH",
            price=float(parent.high),
            formed_at_index=int(parent.index),
            source_rule=rule,
        ),
        LiquidityPool(
            kind=low_kind,
            side="LOW",
            price=float(parent.low),
            formed_at_index=int(parent.index),
            source_rule=rule,
        ),
    ]


def visible_pools(
    h4_history: Sequence["Candle"],
    d1_history: Sequence["Candle"],
    *,
    n_prior_h4: int = 1,
) -> tuple[LiquidityPool, ...]:
    """Every pool a trader could have drawn, given the CLOSED parents supplied.

    Args:
        h4_history: trailing CLOSED calendar-H4 parents, oldest → newest
            (``ParentCandleBuilder(rule="H4", keep=n).parent_history``).
        d1_history: trailing CLOSED calendar-D1 parents, oldest → newest.
        n_prior_h4: how many most-recent closed H4s contribute edges. 1 = "the prior H4",
            the classic CRT read. Pre-registered per experiment; not tuned in-flight.

    Returns pools ordered newest-first within each source. Empty when no parent has closed
    yet — never a partial or in-progress level.
    """
    if n_prior_h4 < 1:
        raise ValueError(f"visible_pools: n_prior_h4 must be >= 1 (got {n_prior_h4})")

    pools: list[LiquidityPool] = []

    h4 = list(h4_history)
    for parent in reversed(h4[-n_prior_h4:]):
        pools.extend(_pools_from_parent(parent, "H4", "PRIOR_H4_HIGH", "PRIOR_H4_LOW"))

    d1 = list(d1_history)
    if d1:
        pools.extend(_pools_from_parent(d1[-1], "D1", "PDH", "PDL"))

    return tuple(pools)
