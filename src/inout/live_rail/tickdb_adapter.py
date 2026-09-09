"""File-backed JSONL tick replay. Default data venue. Zero network. Zero money."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from data_ingestion.ohlcv_schema import ClockProvenanceError, require_reviewed_clock
from inout.live_rail.config import LiveRailConfig
from inout.live_rail.types import ClockBasis, NormalizedTick, VenueName
from utils.logging_config import get_flow_logger

logger = get_flow_logger("LIVE_RAIL")


class TickDBAdapter:
    """File-backed JSONL tick replay. Default venue. Zero network. Zero money."""

    name = VenueName.TICKDB

    def __init__(self, cfg: LiveRailConfig) -> None:
        self._cfg = cfg
        self._path = Path(cfg.tickdb.path)
        self._speed = cfg.tickdb.speed_mult
        self._require_clock = cfg.tickdb.require_clock_record
        self._running = False

    async def start(self) -> None:
        if not self._path.is_file():
            raise FileNotFoundError(f"TickDB: missing {self._path}")
        if self._require_clock:
            # Phase-3: a file's own 'UTC' claim is not evidence (F-066).
            # basis= is feature_pipeline.session_timestamp_basis, NOT ClockBasis.
            from config_layer.production_config import get_prod_section

            fp = get_prod_section("feature_pipeline") or {}
            session_basis = fp.get("session_timestamp_basis")
            if session_basis is None:
                require_reviewed_clock(self._path)
            else:
                require_reviewed_clock(self._path, basis=str(session_basis))
        if self._cfg.clock_basis is ClockBasis.UTC and self._cfg.symbol == "XAUUSD":
            raise RuntimeError(
                "TickDB: clock_basis=utc on XAUUSD refuses start — "
                "XAUUSD corpus is broker_local (F-066 / F-080). "
                "A true-UTC tick file mislabeled broker_local would silently mis-bucket M15."
            )
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def ticks(self) -> AsyncIterator[NormalizedTick]:
        last_ts: datetime | None = None
        last_seq: int | None = None
        with self._path.open("r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                if not self._running:
                    return
                if not line.strip():
                    continue
                raw = json.loads(line)
                tick = self._parse(raw, line_no)
                tick.validate()
                if tick.clock_basis is not self._cfg.clock_basis:
                    raise ClockProvenanceError(
                        f"TickDB line {line_no}: clock_basis {tick.clock_basis} "
                        f"!= configured {self._cfg.clock_basis}"
                    )
                if last_seq is not None and tick.seq is not None and tick.seq != last_seq + 1:
                    raise RuntimeError(f"TickDB SEQ_GAP at line {line_no}")
                if last_ts is not None and tick.ts < last_ts:
                    raise RuntimeError(f"TickDB time-reversed at line {line_no}")
                if self._speed > 0.0 and last_ts is not None:
                    dt = (tick.ts - last_ts).total_seconds() / self._speed
                    if dt > 0:
                        await asyncio.sleep(min(dt, 1.0))
                last_ts, last_seq = tick.ts, tick.seq
                yield tick

    def _parse(self, raw: dict, line_no: int) -> NormalizedTick:
        try:
            ts = datetime.fromisoformat(str(raw["ts"]).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                raise ValueError(
                    f"TickDB line {line_no}: naive timestamp refused "
                    "(do not stamp timezone.utc — F-066)"
                )
            return NormalizedTick(
                ts=ts,
                symbol=str(raw["symbol"]),
                bid=float(raw["bid"]),
                ask=float(raw["ask"]),
                last=float(raw["last"]),
                size=float(raw.get("size", 0.0)),
                seq=int(raw["seq"]) if raw.get("seq") is not None else None,
                clock_basis=ClockBasis(str(raw["clock_basis"])),
                venue=VenueName.TICKDB,
                raw_kind=str(raw.get("raw_kind", "replay")),
            )
        except (KeyError, ValueError) as exc:
            raise ValueError(f"TickDB schema fail line {line_no}: {exc}") from exc
