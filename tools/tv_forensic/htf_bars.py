"""Higher-timeframe engine bars, and the grid phase that ties them to TradingView.

WHY THIS MODULE EXISTS
----------------------
`engine_data.diff_table` compares engine bars to TradingView bars on a fixed
15-minute cursor, so `capture_tv.py` could only reconcile M15 shots. Every H4
shot's sidecar therefore carried `engine_vs_tv.status = NOT_APPLICABLE` by
construction — a permanent structural absence, not a per-shot accident. This
module supplies the two missing pieces (aggregated engine bars, and a MEASURED
grid phase) so an H4 shot can carry a real OK/DIVERGENT verdict.

WHY IT IS A SEPARATE FILE
-------------------------
`engine_data.py`'s own module note (see `_CROSS_TIMEFRAME_EVENTS`) states that
HTF aggregation "belongs to src/features/parent_candle.py, and this tool is
deliberately standalone; duplicating HTF aggregation here would be a second,
unverified reimplementation of the same geometry the codebase's own doctrine
warns against." That constraint is honoured exactly: no aggregation arithmetic
is written here. `ParentCandleBuilder` — the canonical, no-lookahead,
calendar-true builder the parent-CRT track itself is built on — does the work,
and this file is the ONLY place in `tools/tv_forensic/` that reaches into
`src/`. `engine_data.py` stays dependency-free, so the tool still runs (in M15
mode) with no repo on the path.

GRID PHASE IS MEASURED, NEVER ASSUMED
-------------------------------------
TradingView's `OANDA:XAUUSD` H4 bars are exchange-session anchored; the engine's
are calendar-true broker-time buckets, and the resolved broker offset is +3 (an
ODD number), so broker 00:00/04:00/08:00 land on UTC 21:00/01:00/05:00. Whether
the two grids share a phase is an empirical question, and it is resolved the
same way `engine_data.resolve_offset` resolves the clock: re-aggregate the
engine bars at every candidate phase, score each against TradingView's actual
OHLC, and keep the winner only if it is decisive. Each candidate is a genuinely
different bucketing (the children really are regrouped), not the same bars
looked up at a different key — so a phase-shifted TradingView grid is
DISCOVERED rather than merely rejected.

Fails closed: no decisive candidate -> `HTFAnchor.decisive is False` and the
caller keeps `NOT_APPLICABLE` with reason `H4_GRID_UNRESOLVED`. An unresolved
grid is a recorded absence, never a silent pass.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from engine_data import (
    DECISIVE_RATIO,
    MATCH_TOLERANCE,
    Bar,
    _l1,
    to_utc_epoch,
)

#: TradingView interval string -> (ParentCandleBuilder rule, bar step in minutes).
#: Only rules `ParentCandleBuilder` actually supports appear here; anything else
#: keeps the historical NOT_APPLICABLE path.
SUPPORTED_INTERVALS: dict[str, tuple[str, int]] = {
    "60": ("H1", 60),
    "240": ("H4", 240),
    "1D": ("D1", 1440),
    "D": ("D1", 1440),
}


class SrcUnavailable(RuntimeError):
    """`src/` could not be imported, so no canonical aggregation is available.

    Raised (not swallowed) so the caller records `SRC_UNAVAILABLE` explicitly
    rather than silently degrading to an unreconciled shot — the exact
    absent-vs-skipped ambiguity D-1 was filed for.
    """


def _import_builder():
    """Import `ParentCandleBuilder` + `Candle`, putting `src/` on the path if needed.

    Mirrors the bootstrap in `scripts/research/htf_parent_telemetry_extract.py`.
    Deliberately lazy: importing this module must stay free for callers that
    only want `SUPPORTED_INTERVALS`.
    """
    root = Path(__file__).resolve().parents[2]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    try:
        from config_layer.crt_engine_v2 import Candle  # noqa: PLC0415
        from features.parent_candle import ParentCandleBuilder  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001 — any import failure is the same outcome
        raise SrcUnavailable(
            f"cannot import features.parent_candle from {src}: {exc}"
        ) from exc
    return ParentCandleBuilder, Candle


@dataclass
class HTFAnchor:
    """Which grid phase lines the engine's HTF buckets up with TradingView's."""

    phase_hours: int
    error: float
    runner_up_phase: int | None
    runner_up_error: float | None
    anchors_usable: int
    ranked: list[dict] = field(default_factory=list)

    @property
    def decisive(self) -> bool:
        # Same two-part test as engine_data.OffsetResult.decisive, including the
        # D-2 anchor-floor rule: a candidate that keeps only its luckiest few
        # anchors can out-mean the true phase, so the winner must have matched
        # EVERY usable anchor before its mean error is trusted at all.
        if not self.ranked:
            return False
        if self.ranked[0].get("anchors_matched") != self.anchors_usable:
            return False
        if self.error > MATCH_TOLERANCE:
            return False
        if self.runner_up_error is None:
            return True
        return self.runner_up_error >= self.error * DECISIVE_RATIO

    def as_dict(self) -> dict:
        return {
            "resolved_phase_hours": self.phase_hours,
            "match_error": round(self.error, 4),
            "runner_up_phase_hours": self.runner_up_phase,
            "runner_up_error": (
                round(self.runner_up_error, 4)
                if self.runner_up_error is not None
                else None
            ),
            "decisive": self.decisive,
            "anchors_usable": self.anchors_usable,
            "ranked": self.ranked[:5],
        }


def aggregate_engine_bars(
    engine_bars: dict[datetime, Bar], rule: str, phase_hours: int = 0,
) -> dict[datetime, Bar]:
    """Aggregate M15 engine bars into closed `rule` parents, keyed by broker bucket-start.

    All arithmetic is `ParentCandleBuilder`'s — this function only converts
    between `engine_data.Bar` and the engine's `Candle`, and applies the phase
    shift. `phase_hours` shifts the bucketing grid itself (children are really
    regrouped, then the parent timestamp is shifted back), so each phase is a
    genuine alternative grid rather than the same buckets read differently.

    NO-LOOKAHEAD is inherited, not re-implemented: `ParentCandleBuilder` only
    ever exposes CLOSED periods, so the final in-progress bucket is absent by
    design — a partial parent is not a parent.
    """
    ParentCandleBuilder, Candle = _import_builder()

    builder = ParentCandleBuilder(rule, keep=1)
    shift = timedelta(hours=phase_hours)
    out: dict[datetime, Bar] = {}

    for ts in sorted(engine_bars):
        src = engine_bars[ts]
        closed = builder.push(
            Candle(
                timestamp=ts - shift,
                open=src.o,
                high=src.h,
                low=src.l,
                close=src.c,
                volume=src.v,
            )
        )
        if closed:
            p = builder.parent_candle
            stamp = p.timestamp + shift
            out[stamp] = Bar(stamp, p.open, p.high, p.low, p.close, p.volume)

    return out


def resolve_htf_anchor(
    engine_bars: dict[datetime, Bar],
    tv_by_epoch: dict[int, dict],
    rule: str,
    step_minutes: int,
    offset_hours: int,
) -> tuple[HTFAnchor, dict[datetime, Bar]]:
    """Find the grid phase whose aggregated OHLC actually matches TradingView.

    Returns the scored anchor and the engine bars aggregated at the winning
    phase. Callers MUST check `.decisive` before trusting the bars — a
    non-decisive result means the grids do not line up and the shot stays
    unreconciled.
    """
    step_hours = max(1, step_minutes // 60)
    scored: list[tuple[float, int, int]] = []
    aggregated: dict[int, dict[datetime, Bar]] = {}
    in_range: dict[int, int] = {}

    # The engine corpus spans a month; a shot frames days of it. Only parents
    # that fall inside the captured TradingView window can possibly match, so
    # they are the honest denominator for the anchor floor below — scoring a
    # phase against every month parent would demand matches for bars that were
    # never on screen and no phase could ever be decisive.
    if not tv_by_epoch:
        return (
            HTFAnchor(
                phase_hours=0, error=float("inf"), runner_up_phase=None,
                runner_up_error=None, anchors_usable=0, ranked=[],
            ),
            {},
        )
    tv_lo, tv_hi = min(tv_by_epoch), max(tv_by_epoch)

    # Phases beyond one step repeat the same grid, so 0..step_hours-1 is exhaustive.
    for phase in range(step_hours):
        parents = aggregate_engine_bars(engine_bars, rule, phase_hours=phase)
        aggregated[phase] = parents

        total, matched, framed = 0.0, 0, 0
        for ts, bar in parents.items():
            epoch = to_utc_epoch(ts, offset_hours)
            if not (tv_lo <= epoch <= tv_hi):
                continue
            framed += 1
            tv = tv_by_epoch.get(epoch)
            if tv is None:
                continue
            total += _l1(bar.ohlc(), (tv["o"], tv["h"], tv["l"], tv["c"]))
            matched += 1
        in_range[phase] = framed
        if matched:
            scored.append((total / matched, phase, matched))

    if not scored:
        return (
            HTFAnchor(
                phase_hours=0, error=float("inf"), runner_up_phase=None,
                runner_up_error=None, anchors_usable=max(in_range.values(), default=0),
                ranked=[],
            ),
            {},
        )

    scored.sort(key=lambda row: row[0])
    best_err, best_phase, best_matched = scored[0]
    runner = scored[1] if len(scored) > 1 else None

    # The anchor floor compares against the winner's own IN-FRAME parent count:
    # a phase that puts fewer buckets on screen must still have matched all of them.
    anchors_usable = in_range[best_phase]

    anchor = HTFAnchor(
        phase_hours=best_phase,
        error=best_err,
        runner_up_phase=runner[1] if runner else None,
        runner_up_error=runner[0] if runner else None,
        anchors_usable=anchors_usable,
        ranked=[
            {"phase_hours": p, "mean_abs_error": round(e, 4), "anchors_matched": n}
            for e, p, n in scored
        ],
    )
    return anchor, aggregated[best_phase]
