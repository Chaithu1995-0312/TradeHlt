"""features.smc._geometry — shared, pure helpers for the SMC primitive modules.

Reimplemented locally (not imported from `features.causal_structure`) for the same isolation
reason `research.weekly_sweep.weekly_range` reimplements `RangeDetector.detect_sweep`: these
modules must stay pure, config-free, and independently testable, with an explicit `k` argument
rather than resolving `feature_pipeline.resolve_swing_window()` at call time.

CAUSALITY: `detect_causal_swing` only considers a pivot at position `j` CONFIRMED once at least
`k` bars have closed after it — i.e. the pivot is a local extreme over `[j-k, j+k]` and the
window has data through at least index `j+k`. This is the CAUSAL (lag-k) swing definition, not
the CENTERED batch-only definition the repo has separately flagged as leakage-adjacent for live
use (F-029/F-051 discussions) — a production feature must use the causal form.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Sequence

if TYPE_CHECKING:
    from config_layer.crt_engine_v2 import Candle


@dataclass(frozen=True)
class SwingPoint:
    index: int
    price: float
    kind: str   # "high" | "low"


@dataclass(frozen=True)
class Zone:
    """A price zone with a formation index and mitigation state. `near`/`far` are the zone's
    two edges — for a bullish zone `near` is the edge closer to price approaching from above
    (i.e. the top of the zone), for a bearish zone `near` is the bottom; callers pass them
    already oriented so `near` is always "the edge price reaches first on a retrace"."""

    high: float
    low: float
    formed_at_index: int
    bullish: bool   # True = support zone (price expected to react up from it)
    mitigated: bool = False


def detect_causal_swings(window: "Sequence[Candle]", k: int) -> tuple[Optional[SwingPoint], Optional[SwingPoint]]:
    """Most recent CONFIRMED swing high and swing low visible in `window` (oldest-first,
    ending at the current bar). A candidate at local window-position `j` is confirmed once at
    least `k` later bars exist in `window` (so `j <= len(window) - 1 - k`), and is a strict
    local extreme over `[j-k, j+k]` (ties broken toward the earliest occurrence — matches
    `causal_structure`'s `.max()`/`.min()` equality convention).

    Returns (None, None) components independently — a swing high may be confirmed while no
    swing low is, or vice versa. Pure; only inspects `window`.
    """
    bars = list(window)
    n = len(bars)
    if n < 2 * k + 1:
        return None, None

    last_high: Optional[SwingPoint] = None
    last_low: Optional[SwingPoint] = None
    # Scan from the most recent confirmable candidate backward so the FIRST match found is the
    # most recent confirmed swing (what every caller wants).
    for j in range(n - 1 - k, k - 1, -1):
        lo = j - k
        hi = j + k + 1
        seg_h = [b.high for b in bars[lo:hi]]
        seg_l = [b.low for b in bars[lo:hi]]
        if last_high is None and bars[j].high == max(seg_h):
            last_high = SwingPoint(index=bars[j].index, price=bars[j].high, kind="high")
        if last_low is None and bars[j].low == min(seg_l):
            last_low = SwingPoint(index=bars[j].index, price=bars[j].low, kind="low")
        if last_high is not None and last_low is not None:
            break
    return last_high, last_low


def collect_causal_swings(window: "Sequence[Candle]", k: int, kind: str, max_count: int = 8) -> list[SwingPoint]:
    """All CONFIRMED swings of `kind` ("high"|"low") visible in `window`, most-recent-first,
    up to `max_count`. Unlike `detect_causal_swings` (which returns only the single latest
    high AND low), this collects a short history of ONE kind — needed for equal-highs/lows
    clustering, which requires comparing several recent swings to each other."""
    bars = list(window)
    n = len(bars)
    out: list[SwingPoint] = []
    if n < 2 * k + 1:
        return out
    for j in range(n - 1 - k, k - 1, -1):
        lo, hi = j - k, j + k + 1
        if kind == "high":
            seg = [b.high for b in bars[lo:hi]]
            if bars[j].high == max(seg):
                out.append(SwingPoint(index=bars[j].index, price=bars[j].high, kind="high"))
        else:
            seg = [b.low for b in bars[lo:hi]]
            if bars[j].low == min(seg):
                out.append(SwingPoint(index=bars[j].index, price=bars[j].low, kind="low"))
        if len(out) >= max_count:
            break
    return out


def signed_atr_distance(close: float, zone_edge: float, atr: float, *, favorable_sign: int) -> float:
    """ATR-normalized, tanh-bounded signed distance from `close` to `zone_edge`.

    `favorable_sign` is +1 if being ABOVE the edge is the "inside/favorable" reading (e.g. a
    bullish support zone: price above its top edge is fine, price crossing below is a break),
    -1 for the opposite. Returns `0.0` (not NaN) when `atr` is non-positive — matches the
    repo's existing NaN-discipline for degenerate ATR (feature_pipeline.py's `_valid` guards).
    """
    if atr is None or atr <= 0:
        return 0.0
    raw = favorable_sign * (close - zone_edge) / atr
    return math.tanh(raw)


def is_mitigated(zone: Zone, candle: "Candle") -> bool:
    """A zone is mitigated once price has traded back INTO it (any overlap), regardless of
    close — mitigation is about the wick reaching the zone, not a close-based confirmation
    (matches the standard ICT/SMC definition: a single touch mitigates)."""
    return candle.low <= zone.high and candle.high >= zone.low
