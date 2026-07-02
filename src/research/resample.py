"""resample.py — deterministic calendar OHLCV resampler (Program 3 harness; Program 9
adds the minute-grid "M15" rule so an M5 base can build the M5->{M15,H1,H4} ladder).

Behaviour-agnostic, measure-only. Takes a chronologically-ordered list of M15
`Candle`s and aggregates them into higher-timeframe candles by CALENDAR boundary
(floor-to-hour for H1, floor-to-4h-aligned-to-00:00 for H4). The output candles are
re-read by the SAME `CandleLoader` the rest of the research harness uses, so the
audited measurement spine (`forward_walk` intrabar_fixed + `CostModel` + the M4 gate)
consumes resampled files with zero changes.

WHY A SEPARATE FILE (additive, isolated): Program 3 is a NEW horizon ontology, not a
Program-1 parameter pass. It must not touch `runner.py` / `forward_walk.py` /
`qualification.py` or any live-spine module. This resampler only produces input data.

THE LOAD-BEARING INVARIANT — CAUSALITY (no exceptions)
------------------------------------------------------
A bucket is emitted ONLY when the first child of the NEXT bucket arrives. The current
(in-progress) bucket is never finalized from inside itself, and the TRAILING partial
bucket is dropped UNCONDITIONALLY (it is never flushed because no later candle triggers
it). This is conservative on purpose — it is impossible to leak a not-yet-closed bar's
information into a higher-timeframe candle, and it makes the resampler associative
(see below). At most one trailing bucket per file is dropped, deterministically.

NEVER FABRICATE CANDLES. Only the M15 children that actually exist in a bucket are
aggregated (intra-hour gaps -> fewer children, still a valid bucket). A weekend/holiday
gap simply yields no bucket for the empty spans: Friday's bucket flushes when the next
(Monday) candle arrives, and no synthetic bars are emitted between them.

DETERMINISM / ASSOCIATIVITY. OHLC are grouping-invariant by construction (max/min are
associative; open=first, close=last). Volume is summed with `Decimal` over the exact
decimal each input represents, which is exact and grouping-invariant — so
`resample(resample(M15, "H1"), "H4")` is byte-identical to `resample(M15, "H4")`.
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from config_layer.crt_engine_v2 import Candle

# Higher-timeframe rules supported by Program 3. Value = bucket width in hours; the
# floor is always aligned to 00:00 of the candle's calendar day (so H4 buckets start
# at 00,04,08,12,16,20 — and H4 boundaries are a superset of H1 boundaries, which is
# what makes M15->H1->H4 == M15->H4).
_RULE_HOURS = {"H1": 1, "H4": 4}

# Minute-width rules (Program 9 additive extension: M5 base needs M5->M15). Same
# 00:00-of-day alignment (M15 buckets start at :00/:15/:30/:45), so M15 boundaries are
# a subset of H1 boundaries, which are a subset of H4 boundaries — associativity holds
# across the whole ladder (M5->M15->H1 == M5->H1, etc.). `_RULE_HOURS` stays untouched
# on purpose: the H1/H4 code path (incl. `mtf_conjunction`'s import) is byte-identical.
_RULE_MINUTES = {"M15": 15}

CSV_HEADER = "timestamp,open,high,low,close,volume"
_TS_FORMAT = "%Y-%m-%d %H:%M:%S"   # canonical OHLCV format (ohlcv_schema.OHLCV_DATE_FORMATS[0])


def _bucket_start(ts, hours: int):
    """Floor `ts` to its bucket start (hour-aligned; 4h aligned to 00:00 of the day)."""
    floored_hour = (ts.hour // hours) * hours
    return ts.replace(hour=floored_hour, minute=0, second=0, microsecond=0)


def _bucket_start_minutes(ts, minutes: int):
    """Floor `ts` to its bucket start on a minute grid aligned to 00:00 of the day."""
    total = ts.hour * 60 + ts.minute
    floored = (total // minutes) * minutes
    return ts.replace(hour=floored // 60, minute=floored % 60, second=0, microsecond=0)


def bucket_floor(ts, rule: str):
    """Bucket start of `ts` under `rule` — the one public floor for all supported rules.

    Hour rules dispatch to the original `_bucket_start` (identical values by
    construction); minute rules to `_bucket_start_minutes`."""
    if rule in _RULE_HOURS:
        return _bucket_start(ts, _RULE_HOURS[rule])
    if rule in _RULE_MINUTES:
        return _bucket_start_minutes(ts, _RULE_MINUTES[rule])
    raise ValueError(
        f"bucket_floor: unsupported rule '{rule}' "
        f"(expected one of {sorted(_RULE_HOURS) + sorted(_RULE_MINUTES)})")


def _emit(children: list[Candle], start, index: int) -> Candle:
    """Aggregate a non-empty list of child candles into one HTF candle.

    open=first.open, high=max, low=min, close=last.close, volume=Decimal-exact sum,
    timestamp=bucket start, index=stream position in the emitted series.
    """
    vol = sum((Decimal(str(c.volume)) for c in children), Decimal(0))
    return Candle(
        timestamp=start,
        open=children[0].open,
        high=max(c.high for c in children),
        low=min(c.low for c in children),
        close=children[-1].close,
        volume=float(vol),
        index=index,
    )


def resample(candles: list[Candle], rule: str) -> list[Candle]:
    """Aggregate chronologically-ordered `candles` into `rule` ({"M15","H1","H4"}) candles.

    Input MUST be time-ordered (the `CandleLoader` guarantees this and raises on
    out-of-order/duplicate timestamps). Emits a bucket only when a later bucket's first
    candle arrives; drops the trailing partial bucket. Returns a fresh list whose
    `index` is the emitted-series position (0..len-1).
    """
    if rule not in _RULE_HOURS and rule not in _RULE_MINUTES:
        raise ValueError(
            f"resample: unsupported rule '{rule}' "
            f"(expected one of {sorted(_RULE_HOURS) + sorted(_RULE_MINUTES)})")

    out: list[Candle] = []
    cur_start = None
    cur_children: list[Candle] = []

    for c in candles:
        start = bucket_floor(c.timestamp, rule)
        if cur_start is None:
            cur_start = start
        elif start != cur_start:
            # First child of a later bucket has arrived -> the previous bucket is closed.
            out.append(_emit(cur_children, cur_start, len(out)))
            cur_start = start
            cur_children = []
        cur_children.append(c)

    # The final (cur_start) bucket is intentionally NOT flushed — drop the trailing
    # partial bucket unconditionally (no later candle proves it is closed).
    return out


# ── CSV round-trip (so CandleLoader can re-read resampled candles) ──────────────────
def _fmt(x: float) -> str:
    """Shortest round-trip float string (deterministic; never loses precision).

    `repr(float)` is the shortest string that round-trips to the same double — unlike
    `%g` (6 sig-figs) it never silently truncates a large/precise value.
    """
    return repr(float(x))


def write_csv(candles: list[Candle], path: str | Path) -> None:
    """Write resampled candles to `path` in the canonical OHLCV schema (no wall-clock).

    Uses `\\n` line terminator and the canonical timestamp format so the bytes are a
    pure function of the input candles (byte-comparable across runs)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(CSV_HEADER.split(","))
        for c in candles:
            w.writerow([
                c.timestamp.strftime(_TS_FORMAT),
                _fmt(c.open), _fmt(c.high), _fmt(c.low), _fmt(c.close), _fmt(c.volume),
            ])
