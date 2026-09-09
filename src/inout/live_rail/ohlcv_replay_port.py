"""Deterministic historical replay source for live-rail certification.

Two arms, one corpus:

* **Arm A - bar injection** (``load_corpus_bars``): CSV rows become ``ClosedBar``
  objects fed straight to ``LiveRailOrchestrator.ingest_closed_bar``. ``BarBuilder``
  is out of the picture, which isolates the feature -> decision seam.
* **Arm B - tick replay** (``OhlcvTickReplayPort``): each bar is expanded into four
  ticks (open, high, low, close) so ``BarBuilder`` must reconstruct it. The rebuilt
  bar is asserted equal to the source bar; if it differs the arm is testing a
  fiction and fails rather than warns.

This is NOT a venue. It reads a historical OHLCV corpus off disk: zero network,
zero broker, zero money. Nothing here decides anything - it only supplies bars
that the existing spine already knows how to consume.

Clock: the corpus is broker-local labeled (F-066 / F-080 - XAUUSD opens 01:00
broker). Timestamps are made timezone-aware at +00:00 and labeled
``ClockBasis.BROKER_LOCAL``, matching the existing tick-fixture convention. They
are NOT converted to true UTC; doing so would silently re-bucket M15.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Sequence

from config_layer.crt_engine_v2 import Candle
from inout.live_rail.config import LiveRailConfig
from inout.live_rail.types import ClockBasis, ClosedBar, NormalizedTick, VenueName
from utils.logging_config import get_flow_logger

logger = get_flow_logger("LIVE_RAIL")

_REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")

# Synthetic per-tick spread. Reaches ClosedBar.extras only - never OHLCV, never a
# feature. Constant so replay stays deterministic.
_SYNTHETIC_HALF_SPREAD = 0.05


def _parse_ts(raw: str) -> datetime:
    ts = datetime.fromisoformat(raw.strip())
    if ts.tzinfo is None:
        # Label only. The corpus is broker-local; attaching +00:00 makes the value
        # tz-aware for NormalizedTick without claiming it is true UTC.
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def read_corpus_rows(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Read a 6-column OHLCV CSV. Strict header, strict chronology, no gap filling."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"replay corpus not found: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in _REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(
                f"replay corpus {path} missing required columns: {missing} "
                f"(header={reader.fieldnames})"
            )
        prev: datetime | None = None
        for line_no, raw in enumerate(reader, start=2):
            ts = _parse_ts(str(raw["timestamp"]))
            if prev is not None and ts <= prev:
                raise ValueError(
                    f"replay corpus {path} line {line_no}: non-monotonic timestamp "
                    f"{ts} <= {prev} (fail-closed; no reordering)"
                )
            prev = ts
            rows.append({
                "timestamp": ts,
                "open": float(raw["open"]),
                "high": float(raw["high"]),
                "low": float(raw["low"]),
                "close": float(raw["close"]),
                "volume": float(raw["volume"]),
            })
            if limit is not None and len(rows) >= limit:
                break
    if not rows:
        raise ValueError(f"replay corpus {path} produced 0 rows")
    return rows


def load_corpus_bars(
    path: Path,
    cfg: LiveRailConfig,
    *,
    limit: int | None = None,
) -> list[ClosedBar]:
    """Arm A: corpus rows -> ClosedBar, bypassing BarBuilder."""
    tf = int(cfg.timeframe_seconds)
    bars: list[ClosedBar] = []
    for idx, row in enumerate(read_corpus_rows(path, limit)):
        start = row["timestamp"]
        candle = Candle(
            timestamp=start,
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
            index=idx,
        )
        bar = ClosedBar(
            candle=candle,
            extras={},
            symbol=cfg.symbol,
            clock_basis=cfg.clock_basis,
            venue=cfg.data_venue,
            n_ticks=0,          # injected, not aggregated - do not claim tick support
            period_start=start,
            period_end=start + timedelta(seconds=tf),
        )
        bar.validate()
        bars.append(bar)
    return bars


def bar_to_ticks(
    row: dict[str, Any],
    *,
    symbol: str,
    clock_basis: ClockBasis,
    venue: VenueName,
    seq_start: int,
) -> list[NormalizedTick]:
    """Expand one OHLCV row into four ticks: open, high, low, close - in that order.

    ``max`` over the four prices is the bar high and ``min`` is the bar low by
    construction, so ``BarBuilder`` reproduces the source bar exactly. Sizes sum to
    the bar volume under ``volume_mode="sum_size"``; the whole volume rides the last
    tick so the sum is exact with no float-division drift.
    """
    start = row["timestamp"]
    prices = (row["open"], row["high"], row["low"], row["close"])
    sizes = (0.0, 0.0, 0.0, float(row["volume"]))
    ticks: list[NormalizedTick] = []
    for offset, (px, size) in enumerate(zip(prices, sizes)):
        tick = NormalizedTick(
            ts=start + timedelta(seconds=offset),
            symbol=symbol,
            bid=px - _SYNTHETIC_HALF_SPREAD,
            ask=px + _SYNTHETIC_HALF_SPREAD,
            last=px,
            size=size,
            seq=seq_start + offset,
            clock_basis=clock_basis,
            venue=venue,
            raw_kind="replay",
        )
        tick.validate()
        ticks.append(tick)
    return ticks


class OhlcvTickReplayPort:
    """Arm B: historical OHLCV corpus -> ticks -> BarBuilder -> ClosedBar.

    ``expected_bars`` is the source truth the round-trip assertion compares against.
    BarBuilder closes a bar only when a tick from the NEXT period arrives, so the
    final corpus row never emits: expect ``len(rows) - 1`` closed bars.
    """

    name = VenueName.TICKDB  # file-backed replay; not a live venue

    def __init__(
        self,
        cfg: LiveRailConfig,
        corpus: Path,
        *,
        limit: int | None = None,
    ) -> None:
        self._cfg = cfg
        self._corpus = Path(corpus)
        self._limit = limit
        self._rows: list[dict[str, Any]] = []
        self._running = False

    @property
    def expected_bars(self) -> list[dict[str, Any]]:
        """Source rows BarBuilder is expected to reproduce (all but the last)."""
        return self._rows[:-1]

    async def start(self) -> None:
        self._rows = read_corpus_rows(self._corpus, self._limit)
        if len(self._rows) < 2:
            raise ValueError(
                "OhlcvTickReplayPort: need >=2 rows (BarBuilder closes on the next period)"
            )
        logger.info(
            "LIVE_RAIL: replay corpus %s rows=%d symbol=%s basis=%s",
            self._corpus, len(self._rows), self._cfg.symbol, self._cfg.clock_basis.value,
        )
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def ticks(self) -> AsyncIterator[NormalizedTick]:
        seq = 1
        for row in self._rows:
            if not self._running:
                return
            for tick in bar_to_ticks(
                row,
                symbol=self._cfg.symbol,
                clock_basis=self._cfg.clock_basis,
                venue=self._cfg.data_venue,
                seq_start=seq,
            ):
                yield tick
            seq += 4


def assert_round_trip(
    expected: Sequence[dict[str, Any]],
    produced: Sequence[ClosedBar],
) -> None:
    """Fail-closed: a rebuilt bar differing from its source means Arm B is a fiction."""
    if len(produced) != len(expected):
        raise AssertionError(
            f"replay round-trip: produced {len(produced)} bars, expected {len(expected)}"
        )
    for i, (src, bar) in enumerate(zip(expected, produced)):
        c = bar.candle
        for field in ("open", "high", "low", "close", "volume"):
            if float(getattr(c, field)) != float(src[field]):
                raise AssertionError(
                    f"replay round-trip bar {i} field {field}: "
                    f"rebuilt {getattr(c, field)!r} != source {src[field]!r}"
                )
        if c.timestamp != src["timestamp"]:
            raise AssertionError(
                f"replay round-trip bar {i} timestamp: {c.timestamp} != {src['timestamp']}"
            )
