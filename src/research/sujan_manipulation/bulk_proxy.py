"""SEM-034 — the bulk-candle proxy. APPROVED by the human bridge, UNVALIDATED.

WHAT THIS IS
------------
UNK-007 (`UNKNOWN_FOUNDING__SUJAN_BULK_CANDLE`) asks which candle counts as the "parent
bulk candle" SEM-033 monitors. The recorded evidence is four statements and no threshold:

    visually dominant / often large-bodied / may also be wick-dominant /
    no approved percentage threshold exists

This module does NOT answer that question. It is a **mechanical proxy** the human bridge
approved on 2026-08-29 (drift log Record 6) to produce a SHORTLIST for visual confirmation.
Its status is `UNVALIDATED`: no agreement check against a hand-labelled set exists yet,
because this build is what finally produces that set.

The identity charter permits a proxy only when it is (1) bridge-approved, (2) recorded, and
(3) still linked to the original. All three hold: the approval is in Record 6, the node is
SEM-034, and UNK-007 stays OPEN pointing at it.

    A candidate is a candidate. Ranking 50 candles by size makes no statement about the
    market, and none about what Sujan means.

TWO LISTS, NEVER MERGED
-----------------------
"Often large-bodied" and "may also be wick-dominant" point at two DIFFERENT quantities.
Blending them into one score would silently resolve the ambiguity the specification asked
to preserve, so this module emits a range-ranked list and a body-ranked list side by side
and reports their overlap as a measurement rather than folding it away.

NO LOCAL ARITHMETIC
-------------------
Magnitudes come from `features.candle_math` (FM-002 `candle_range`, FM-001 `body_size`).
Writing `high - low` inline here would be ungoverned feature math — the exact class
`scripts/analysis/feature_math_lint.py` exists to catch, and the debt it already pins at
`research/mother_range/geometry.py:104-105`, which survives only because that package sits
outside the lint's scan dirs. No new `FM-*` id is minted: nothing here enters the 48-dim
vector. This is a SELECTION PROCEDURE over registered quantities, not a new feature.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from features.candle_math import body_size, candle_range

from research.sujan_manipulation.parent import Bar, ParentBulkCandle

#: Human bridge, 2026-08-29 (drift log Record 6). A RECORDED value, not a default —
#: constructors below require `n` explicitly so no silent default can drift (§6.5).
FROZEN_TOP_N = 50

PROXY_ID = "SEM-034"
PROXY_STATUS = "UNVALIDATED"

#: The two rankings, by the registered quantity each uses.
RANKING_RANGE = "candle_range"
RANKING_BODY = "body_size"
RANKINGS = (RANKING_RANGE, RANKING_BODY)


@dataclass(frozen=True)
class RankedCandidate:
    """One shortlisted candle, with the evidence for why it was shortlisted."""

    parent: ParentBulkCandle
    rank: int          # 1 = largest
    magnitude: float
    ranking: str       # RANKING_RANGE | RANKING_BODY


class _TopNProxySelector:
    """Top-N over the WHOLE corpus by one registered magnitude.

    Conforms to `parent.ParentSelector`. Deliberately not a rolling or windowed rule:
    "top-N over the whole corpus" is the comparison the bridge chose, and a window would
    have introduced a second invented parameter.
    """

    _ranking: str
    _magnitude: Callable[[Bar], float]

    def __init__(self, n: int) -> None:
        if not isinstance(n, int) or isinstance(n, bool):
            raise TypeError(f"n must be an int, got {type(n).__name__}")
        if n < 1:
            raise ValueError(f"n must be >= 1, got {n}")
        self._n = n

    @property
    def n(self) -> int:
        return self._n

    @property
    def ranking(self) -> str:
        return self._ranking

    @property
    def source(self) -> str:
        return f"{PROXY_ID} proxy ({PROXY_STATUS}): top-{self._n} by {self._ranking}"

    def rank(self, bars: Sequence[Bar]) -> tuple[RankedCandidate, ...]:
        """Shortlist in RANK order (largest first).

        Ties break by ascending bar index, explicitly — leaving it to sort stability would
        make the output depend on the input order rather than on the data.
        """
        if not bars:
            raise ValueError("no bars supplied to the bulk-candle proxy")
        ordered = sorted(bars, key=lambda b: (-self._magnitude(b), b.index))
        return tuple(
            RankedCandidate(
                parent=ParentBulkCandle(
                    timestamp=bar.timestamp,
                    high=bar.high,
                    low=bar.low,
                    index=bar.index,
                    source=self.source,
                ),
                rank=i + 1,
                magnitude=self._magnitude(bar),
                ranking=self._ranking,
            )
            for i, bar in enumerate(ordered[: self._n])
        )

    def select(self, bars: Sequence[Bar]) -> tuple[ParentBulkCandle, ...]:
        """`ParentSelector` conformance: the same shortlist in CHRONOLOGICAL order."""
        chosen = [c.parent for c in self.rank(bars)]
        return tuple(sorted(chosen, key=lambda p: p.index))


class TopNRangeSelector(_TopNProxySelector):
    """Ranks by FM-002 `candle_range` — full wick-to-wick extent.

    The wick-inclusive reading. Also the same quantity the parent range itself uses.
    """

    _ranking = RANKING_RANGE

    @staticmethod
    def _magnitude(bar: Bar) -> float:
        return candle_range(bar.high, bar.low)


class TopNBodySelector(_TopNProxySelector):
    """Ranks by FM-001 `body_size` — |close - open|.

    The "often large-bodied" reading. Blind to wick-dominant candles by construction,
    which is why it is emitted alongside the range list and never merged with it.
    """

    _ranking = RANKING_BODY

    @staticmethod
    def _magnitude(bar: Bar) -> float:
        return body_size(bar.open, bar.close)


def build_selectors(n: int) -> tuple[TopNRangeSelector, TopNBodySelector]:
    """The two un-merged readings, in a fixed order."""
    return TopNRangeSelector(n), TopNBodySelector(n)


def overlap_indices(
    a: Sequence[RankedCandidate], b: Sequence[RankedCandidate]
) -> tuple[int, ...]:
    """Bar indices shortlisted by BOTH readings.

    Reported, never used to merge or re-rank. Where the two disagree is information about
    how under-determined "visually dominant" is, and folding it away would destroy that.
    """
    return tuple(sorted({c.parent.index for c in a} & {c.parent.index for c in b}))
