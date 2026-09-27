"""
bar_clock_bridge.py — the canonical bar-clock bridge (bar_identity.jsonl) emitter (Phase 3).

One observation-only JSONL per run translating every per-bar index dialect into the ONE
canonical bar-open clock::

    {run_id, instrument, timeframe, corpus_sha256,
     bar_index, engine_candle_index, bar_ts, bar_open_ts}

`bar_open_ts` is the canonical UTC ``YYYY-MM-DD HH:MM:SS`` (identity_spine.normalize_bar_ts).
A consumer holding any local index (`bar_index`, `engine_candle_index`, `bar_idx`,
`candle_index`, `candle_open`, `_pos`) can recover its `bar_open_ts` from this file and join
against the frozen PK ``(instrument, timeframe, bar_open_ts, corpus_sha256)``.

OBSERVATION ONLY — same invariant as bar_structure_snapshot / layer_trace:
- `emit()` is called AFTER the bar's decision is final, returns None, and nothing reads it back.
- Enabled ONLY when the production config carries a `bar_clock_bridge` section with
  `enabled: true` and every key declared (fail fast via `_require`). Absent section -> None
  on every pre-existing config, so construction failure can never take a backtest down.
- Uses `identity_spine.normalize_bar_ts` — the registered bar-clock spec, never inlined math.
"""
from __future__ import annotations

import json
import logging
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from governance.identity_spine import normalize_bar_ts

logger = logging.getLogger("CRT.BarClock")

BRIDGE_SCHEMA_VERSION = "1.0.0"
EMITTED_BY = "runtime.bar_clock_bridge"
DEFAULT_OUTPUT_DIR = "results/bar_clock"
DEFAULT_FILENAME_SUFFIX = "_bar_identity.jsonl"
DEFAULT_FLUSH_EVERY = 500


def _require(section: dict, key: str) -> Any:
    """Strict config accessor — CLAUDE.md 6.5 forbids silent defaults for new behavioural keys."""
    if key not in section:
        raise KeyError(
            f"bar_clock_bridge.{key} is required (no silent default). "
            "Add it to the production config bar_clock_bridge section."
        )
    return section[key]
# SEAM-1


@dataclass(frozen=True)
class BarClockConfig:
    """Resolved `bar_clock_bridge` config. Frozen: read once at construction."""

    enabled: bool
    schema_version: str
    output_dir: str
    filename_suffix: str
    flush_every: int

    @classmethod
    def from_prod_config(cls, version: Optional[str] = None) -> Optional["BarClockConfig"]:
        """None when the section is absent or `enabled` is false (all pre-existing configs).

        A PRESENT-but-incomplete section still fails fast via `_require` — same discipline as
        `bar_structure_snapshot`'s SnapshotConfig.
        """
        from config_layer.production_config import get_prod_section

        try:
            section = get_prod_section("bar_clock_bridge", version=version)
        except (RuntimeError, KeyError):
            return None
        if not bool(_require(section, "enabled")):
            return None
        declared = str(_require(section, "schema_version"))
        if declared != BRIDGE_SCHEMA_VERSION:
            raise ValueError(
                f"bar_clock_bridge.schema_version={declared!r} does not match this module's "
                f"BRIDGE_SCHEMA_VERSION={BRIDGE_SCHEMA_VERSION!r}."
            )
        return cls(
            enabled=True,
            schema_version=declared,
            output_dir=str(_require(section, "output_dir")),
            filename_suffix=str(_require(section, "filename_suffix")),
            flush_every=int(_require(section, "flush_every")),
        )
# SEAM-2


class BarClockBridgeEmitter:
    """Streaming per-bar index->bar_open_ts bridge writer. One per run per instrument."""

    def __init__(
        self,
        cfg: BarClockConfig,
        *,
        run_id: str,
        instrument: str,
        timeframe: str,
        corpus_hash: str,
    ) -> None:
        self.cfg = cfg
        self.run_id = run_id
        self._buffer: list = []
        self._rows = 0
        self._path = Path(cfg.output_dir) / f"{instrument}{cfg.filename_suffix}"
        self._identity = OrderedDict(
            [
                ("schema_version", cfg.schema_version),
                ("emitted_by", EMITTED_BY),
                ("run_id", run_id),
                ("instrument", instrument),
                ("timeframe", timeframe),
                ("corpus_sha256", corpus_hash),
            ]
        )

    @property
    def path(self) -> Path:
        return self._path

    @property
    def rows_written(self) -> int:
        return self._rows

    def emit(
        self,
        *,
        candle,
        bar_index: int,
        engine_candle_index: Optional[int] = None,
    ) -> None:
        """Record one bar's local-index pair + its canonical clock.

        Called AFTER the bar's decision is already final (same placement discipline as
        `BarStructureEmitter.emit`). Returns None; no caller consumes a value.
        """
        if not self.cfg.enabled:
            return
        rec = OrderedDict(self._identity)
        rec["bar_index"] = int(bar_index)
        rec["engine_candle_index"] = (
            int(engine_candle_index) if engine_candle_index is not None else None
        )
        rec["bar_ts"] = candle.timestamp.isoformat() if candle.timestamp is not None else None
        rec["bar_open_ts"] = (
            normalize_bar_ts(candle.timestamp) if candle.timestamp is not None else None
        )
        self._buffer.append(rec)
        self._rows += 1
        if len(self._buffer) >= self.cfg.flush_every:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8", newline="\n") as fh:
            for rec in self._buffer:
                fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        self._buffer.clear()

    def close(self) -> dict:
        """Flush and return a small run manifest (mirrors LayerTraceEmitter.close)."""
        self.flush()
        return {
            "path": str(self._path),
            "rows": self._rows,
            "schema_version": self.cfg.schema_version,
            "identity": dict(self._identity),
        }