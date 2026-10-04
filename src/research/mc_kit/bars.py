"""bars.py — CSV bar loading shared by sealed-contract drivers.

Replaces byte-identical (AST-fingerprint `df0a572077`) `load_bars`/`_parse_ts` copies in
`research.mother_range.driver` and `research.evidence.mother_range_prior`, and the
computationally-identical (`_parse_ts`, fingerprint `9cb6fe78b0`) copy in
`research.sujan_crt.driver`. `sujan_crt`'s own `load_bars` differs in exactly one respect —
`row.get("volume") or 0.0` instead of `row["volume"]` — named here as `volume="zero_default"`
rather than silently unified with the strict form.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Literal, Type, TypeVar

import csv

BarT = TypeVar("BarT")


def parse_ts_iso19(raw: str) -> datetime:
    """`"2026-01-01T00:00:00..."` or `"2026-01-01 00:00:00..."` -> the first 19 chars, ISO-parsed.

    Identical to every replaced `_parse_ts`: strip, swap a `T` separator for a space, then parse
    only the first 19 characters (drops sub-second precision the sources never carry).
    """
    s = raw.strip().replace("T", " ")
    return datetime.fromisoformat(s[:19])


def load_bars(
    path: Path,
    bar_cls: Type[BarT],
    *,
    parse_ts: Callable[[str], datetime] = parse_ts_iso19,
    volume: Literal["required", "zero_default"] = "required",
) -> list[BarT]:
    """Read a `timestamp,open,high,low,close,volume` CSV into `[bar_cls(...), ...]`, index-stamped.

    `volume="required"` raises `KeyError` on a missing column (matches `mother_range.driver` /
    `evidence.mother_range_prior`); `"zero_default"` falls back to `0.0` (matches
    `sujan_crt.driver`, whose corpus's volume column is not load-bearing for that contract).
    `bar_cls` is called positionally-by-keyword with exactly the 7 fields every target `Bar`
    dataclass declares (`timestamp, open, high, low, close, volume, index`).
    """
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    bars: list[BarT] = []
    for i, row in enumerate(rows):
        # Exact per-mode behavior, not a merged approximation: "required" raises KeyError on a
        # missing column and ValueError on an empty one (matches row["volume"] in the originals);
        # "zero_default" only falls back on a missing/empty/falsy value (matches sujan_crt's
        # `row.get("volume") or 0.0`).
        vol = float(row["volume"]) if volume == "required" else float(row.get("volume") or 0.0)
        bars.append(bar_cls(
            timestamp=parse_ts(row["timestamp"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=vol,
            index=i,
        ))
    return bars
