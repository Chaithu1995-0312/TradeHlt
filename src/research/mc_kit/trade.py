"""trade.py — forward-walk step and exit classification shared by trade-contract drivers.

`walk_horizon` replaces the byte-identical (AST-fingerprint `c7be2db92a`) `_walk` copies in
`research.mother_range.driver` and `research.sujan_crt.driver`. `exit_kind` replaces the 3-way
ternary (`"SL_HIT" if out.outcome == "SL_HIT" else ("TP_HIT" if ... else "TIMEOUT")`) repeated
verbatim at every net-R call site in both drivers (and in every control loop within them) — it
is not itself a duplicated function (never named the same way twice) but is the identical
literal expression copy-pasted 5+ times.

`Signal` construction (`_signal` in each driver) is deliberately NOT here: it differs per
contract for a real reason — a different source dataclass, and a real behavioral difference on
zero risk (`mother_range` raises `ZeroDivisionError`, `sujan_crt` guards to `1.0`). Unifying it
would either erase that difference or require a construction DSL; left local.
"""
from __future__ import annotations

from typing import Any, Sequence

from research.contracts import Signal
from research.measurement.forward_walk import AdverseFill, forward_walk


def walk_horizon(
    sig: Signal,
    bars: Sequence[Any],
    *,
    horizon_bars: int,
    adverse: AdverseFill,
    exit_model: str = "intrabar_fixed",
) -> Any | None:
    """Forward-walk `sig` over up to `horizon_bars` bars strictly after its entry; `None` if none
    remain (the walk cannot resolve past the end of the corpus)."""
    future = [b for b in bars if b.index > sig.entry_index][:horizon_bars]
    if not future:
        return None
    return forward_walk(sig, future, max_forward=horizon_bars, exit_model=exit_model,
                        adverse_fill=adverse)


def exit_kind(outcome: str) -> str:
    """`Outcome.outcome` ('TP_HIT'|'SL_HIT'|anything else) -> the 3-value exit-kind vocabulary
    `ComponentCostModel.net_rr(exit_kind=...)` expects. Anything not TP_HIT/SL_HIT is TIMEOUT —
    matches every replaced call site exactly (never raises on an unrecognised outcome)."""
    if outcome == "SL_HIT":
        return "SL_HIT"
    if outcome == "TP_HIT":
        return "TP_HIT"
    return "TIMEOUT"
