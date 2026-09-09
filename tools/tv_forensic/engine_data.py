"""Engine-side bars, and the clock that ties them to TradingView.

The engine's CSV timestamps are *broker* (MT5 server) local time; TradingView is
driven in UTC. The offset between them is resolved by MEASUREMENT, never assumed:
we take engine bars whose OHLC we know, try each candidate hour offset, and keep
the one whose OHLC actually lines up.

This matters beyond tidiness. Per F-066 the MT5 server tracks *US* DST, so the
offset is +3 in summer and +2 in winter — a hardcoded -3 silently mis-frames any
winter window, and a mis-framed window is exactly how shot 04 came to assert a
mapping onto candles that were not in the picture.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_CSV = Path("data/XAUUSD_M15.csv")

# The engine feed and TradingView's feed are different brokers, so bars agree to
# within a spread, not exactly. Observed on OANDA:XAUUSD vs this corpus: ~0.1-0.5
# total absolute error across O/H/L/C. A whole-bar clock error scores 15-40.
MATCH_TOLERANCE = 3.0
DECISIVE_RATIO = 5.0


@dataclass(frozen=True)
class Bar:
    ts: datetime  # broker-local, naive
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0

    def ohlc(self) -> tuple[float, float, float, float]:
        return (self.o, self.h, self.l, self.c)


@dataclass
class OffsetResult:
    hours: int
    error: float
    runner_up_hours: int | None
    runner_up_error: float | None
    anchors: list[str]
    ranked: list[dict] = field(default_factory=list)

    @property
    def decisive(self) -> bool:
        # D-2 (semantic + screenshot layer review, 2026-08-16): the mean-error
        # comparison below is computed over however many anchors each candidate
        # offset happened to match (`resolve_offset` silently drops an anchor for
        # a candidate when no TV bar exists at that candidate's epoch). A
        # candidate that keeps only its 2 luckiest anchors can out-mean the true
        # offset averaging over all 19 -- `matched` was already tracked into
        # `ranked` but never fed into this decision. Require the winner to have
        # matched every USABLE anchor before its mean is trusted at all; this is
        # checked first and fails closed (not decisive) if it doesn't hold,
        # regardless of how good the mean error looks.
        if self.ranked:
            n_usable = len(self.anchors)
            winner_matched = self.ranked[0].get("anchors_matched")
            if n_usable and winner_matched != n_usable:
                return False
        else:
            # No ranked detail at all (e.g. constructed directly, not via
            # resolve_offset) -- nothing to verify the winner against. Fail
            # closed rather than assume the anchor floor was met.
            return False

        if self.error > MATCH_TOLERANCE:
            return False
        if self.runner_up_error is None:
            # D-2: a single scored candidate ruled nothing out by comparison.
            # It no longer wins automatically -- the anchor-floor check above is
            # now the ONLY evidence for this case, and it already ran.
            return True
        return self.runner_up_error >= self.error * DECISIVE_RATIO

    def as_dict(self) -> dict:
        return {
            "resolved_offset_hours": self.hours,
            "match_error": round(self.error, 4),
            "runner_up_hours": self.runner_up_hours,
            "runner_up_error": (
                round(self.runner_up_error, 4)
                if self.runner_up_error is not None
                else None
            ),
            "decisive": self.decisive,
            "anchors": self.anchors,
            "ranked": self.ranked[:5],
        }


# D-4 (semantic + screenshot layer review, 2026-08-16): shot_plan.json's
# `engine_events` are hand-transcribed -- no code anywhere derived, regenerated,
# or cross-checked a `time`/`level` pair against the engine CSV before this.
# A mistyped digit in either field would draw with full pixel precision and
# look exactly as authoritative as a correct one. This does NOT aggregate to
# any coarser timeframe (H4 etc.) -- that logic belongs to
# src/features/parent_candle.py, and this tool is deliberately standalone
# ("Does not touch the trading engine" -- module docstring); duplicating HTF
# aggregation here would be a second, unverified reimplementation of the same
# geometry the codebase's own doctrine warns against. Cross-timeframe events
# (H4_C3) are time-checked like everything else but explicitly EXEMPTED from
# the level check, not silently skipped without saying so.
_CROSS_TIMEFRAME_EVENTS = frozenset({"H4_C3"})


def validate_engine_events(
    events: list[dict], engine_bars: dict[datetime, "Bar"],
) -> list[dict]:
    """Cross-check every engine_events entry's `time` and `level` against the
    engine CSV. Returns a list of problems (empty = clean); never raises --
    callers decide whether a problem is fatal."""
    problems: list[dict] = []
    for ev in events:
        try:
            ts = datetime.strptime(ev["time"], "%Y-%m-%d %H:%M")
        except (KeyError, ValueError) as exc:
            problems.append({
                "event": ev.get("event"), "time": ev.get("time"),
                "problem": "UNPARSEABLE_TIME", "detail": str(exc),
            })
            continue
        bar = engine_bars.get(ts)
        if bar is None:
            problems.append({
                "event": ev.get("event"), "time": ev["time"],
                "problem": "MISSING_BAR",
                "detail": f"no engine bar at {ev['time']} broker time",
            })
            continue
        level = ev.get("level")
        if level is None:
            continue
        if ev.get("event") in _CROSS_TIMEFRAME_EVENTS:
            continue  # exempted, not skipped silently -- see module note above
        lo, hi = min(bar.o, bar.h, bar.l, bar.c), max(bar.o, bar.h, bar.l, bar.c)
        if not (lo <= level <= hi):
            problems.append({
                "event": ev.get("event"), "time": ev["time"],
                "problem": "LEVEL_OUT_OF_RANGE",
                "detail": (
                    f"level={level} outside this bar's O/H/L/C envelope "
                    f"[{lo}, {hi}] (O={bar.o} H={bar.h} L={bar.l} C={bar.c})"
                ),
            })
    return problems


def load_engine_bars(csv_path: Path | str = DEFAULT_CSV) -> dict[datetime, Bar]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(
            f"engine bar CSV not found: {path}. "
            "Jul/Aug 2026 lives in data/XAUUSD_M15.csv (data/mt5/ ends 2026-05-21)."
        )
    out: dict[datetime, Bar] = {}
    with path.open(encoding="utf-8") as fh:
        header = fh.readline()
        if not header.lower().startswith("timestamp"):
            raise ValueError(f"unexpected header in {path}: {header!r}")
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            ts = datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S")
            out[ts] = Bar(
                ts,
                float(parts[1]),
                float(parts[2]),
                float(parts[3]),
                float(parts[4]),
                float(parts[5]) if len(parts) > 5 else 0.0,
            )
    return out


def to_utc_epoch(broker_dt: datetime, offset_hours: int) -> int:
    utc = broker_dt - timedelta(hours=offset_hours)
    return int(utc.replace(tzinfo=timezone.utc).timestamp())


def from_utc_epoch(epoch: int, offset_hours: int) -> datetime:
    utc = datetime.fromtimestamp(int(epoch), tz=timezone.utc).replace(tzinfo=None)
    return utc + timedelta(hours=offset_hours)


def _l1(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b))


def resolve_offset(
    engine_bars: dict[datetime, Bar],
    tv_by_epoch: dict[int, dict],
    anchors: list[datetime],
    candidates: range = range(-12, 13),
) -> OffsetResult:
    """Find the broker->UTC offset whose OHLC actually matches, and prove it is decisive."""
    usable = [a for a in anchors if a in engine_bars]
    if not usable:
        raise ValueError(
            "no anchor timestamps found in the engine CSV; cannot resolve the clock"
        )

    scored: list[tuple[float, int, int]] = []
    for hours in candidates:
        total, matched = 0.0, 0
        for anchor in usable:
            tv = tv_by_epoch.get(to_utc_epoch(anchor, hours))
            if tv is None:
                continue
            total += _l1(
                engine_bars[anchor].ohlc(), (tv["o"], tv["h"], tv["l"], tv["c"])
            )
            matched += 1
        if matched:
            scored.append((total / matched, hours, matched))

    if not scored:
        raise ValueError(
            "no candidate offset produced a TradingView bar to compare against; "
            "the loaded window probably does not cover these timestamps"
        )

    scored.sort(key=lambda row: row[0])
    best_err, best_hours, _ = scored[0]
    runner = scored[1] if len(scored) > 1 else None

    return OffsetResult(
        hours=best_hours,
        error=best_err,
        runner_up_hours=runner[1] if runner else None,
        runner_up_error=runner[0] if runner else None,
        anchors=[a.strftime("%Y-%m-%d %H:%M") for a in usable],
        ranked=[
            {"offset_hours": h, "mean_abs_error": round(e, 4), "anchors_matched": n}
            for e, h, n in scored
        ],
    )


def diff_table(
    engine_bars: dict[datetime, Bar],
    tv_by_epoch: dict[int, dict],
    offset_hours: int,
    start_broker: datetime,
    end_broker: datetime,
    step_minutes: int = 15,
    record_missing_engine: bool = False,
) -> list[dict]:
    """Per-bar engine vs TradingView comparison across the window.

    `step_minutes` is the bar period of BOTH sides. It defaults to 15 so every
    existing M15 caller is unchanged; an HTF caller passes the aggregated bars
    (see `htf_bars.aggregate_engine_bars` — aggregation is NOT done here, per
    the module note above) together with their step.

    `record_missing_engine` emits an explicit `NO_ENGINE_BAR` row where the
    window extends past the corpus instead of skipping the slot. Default False
    keeps every existing M15 sidecar byte-identical (an M15 window routinely
    spans weekends, where a skipped slot is correct and a row would be noise).
    Callers whose window can start BEFORE the corpus does — `01_h4_july_macro`
    asks for Jul 1 while `data/XAUUSD_M15.csv` starts Jul 7 — pass True so the
    uncovered span is counted in the denominator rather than quietly dropped.
    """
    rows = []
    cursor = start_broker
    step = timedelta(minutes=step_minutes)
    while cursor <= end_broker:
        eng = engine_bars.get(cursor)
        if eng is None and record_missing_engine:
            # Look TV up even though the engine side is empty: a slot where the
            # engine has no bar but TradingView does is a real one-sided gap,
            # and recording `tv: None` without checking would assert an absence
            # that was never measured (the D-1 failure class, one layer down).
            epoch = to_utc_epoch(cursor, offset_hours)
            tv = tv_by_epoch.get(epoch)
            rows.append({
                "broker": cursor.strftime("%Y-%m-%d %H:%M"),
                "utc": datetime.fromtimestamp(epoch, tz=timezone.utc).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "engine": None,
                "tv": (
                    None if tv is None
                    else {"O": tv["o"], "H": tv["h"], "L": tv["l"], "C": tv["c"]}
                ),
                "status": "NO_ENGINE_BAR" if tv is None else "ENGINE_BAR_MISSING_TV_HAS_ONE",
            })
        if eng is not None:
            epoch = to_utc_epoch(cursor, offset_hours)
            tv = tv_by_epoch.get(epoch)
            row = {
                "broker": cursor.strftime("%Y-%m-%d %H:%M"),
                "utc": datetime.fromtimestamp(epoch, tz=timezone.utc).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "engine": {"O": eng.o, "H": eng.h, "L": eng.l, "C": eng.c},
            }
            if tv is None:
                row["tv"] = None
                row["status"] = "NO_TV_BAR"
            else:
                row["tv"] = {"O": tv["o"], "H": tv["h"], "L": tv["l"], "C": tv["c"]}
                row["delta"] = {
                    "O": round(tv["o"] - eng.o, 4),
                    "H": round(tv["h"] - eng.h, 4),
                    "L": round(tv["l"] - eng.l, 4),
                    "C": round(tv["c"] - eng.c, 4),
                }
                row["abs_error"] = round(
                    _l1(eng.ohlc(), (tv["o"], tv["h"], tv["l"], tv["c"])), 4
                )
                row["status"] = (
                    "OK" if row["abs_error"] <= MATCH_TOLERANCE else "DIVERGENT"
                )
            rows.append(row)
        cursor += step
    return rows


def summarize_diff(rows: list[dict]) -> dict:
    scored = [r["abs_error"] for r in rows if r.get("abs_error") is not None]
    return {
        "bars": len(rows),
        "compared": len(scored),
        "missing_tv_bar": sum(1 for r in rows if r["status"] == "NO_TV_BAR"),
        "missing_engine_bar": sum(1 for r in rows if r["status"] == "NO_ENGINE_BAR"),
        "engine_gap_tv_has_bar": sum(
            1 for r in rows if r["status"] == "ENGINE_BAR_MISSING_TV_HAS_ONE"
        ),
        "divergent": sum(1 for r in rows if r["status"] == "DIVERGENT"),
        "mean_abs_error": round(sum(scored) / len(scored), 4) if scored else None,
        "max_abs_error": round(max(scored), 4) if scored else None,
    }
