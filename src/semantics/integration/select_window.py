"""R1-C: deterministic selection of a trade-exercising corpus window (spec §16).

Provenance rule: the selection reads ONLY the engine's own output of a plain backtest of the full
corpus (the trades CSV and events.jsonl). It never reads a Semantic OS verdict, an UNEXPLAINED row or a
contract disagreement, so the chosen window cannot be biased toward or away from a semantic result.

Algorithm (deterministic, no randomness):
  1. Classify each closed engine trade by lifecycle: LONG/SHORT, stop exit, TP1 reached, TP2 reached.
  2. Enumerate every contiguous run of trades (in open order). Its window starts `lead_bars` before the
     SWEEP that founded its first trade and ends on the bar after its last close.
  3. Pick the run that satisfies the most HARD criteria (trade, LONG, SHORT, stop, TP1, TP2), then the
     PREFERENCE (>= 2 trades), then the fewest bars, then the earliest start.
  4. Verify by a plain backtest of the cut slice that the engine reproduces the same trades
     (opened_at, direction, exit_reason). If not, widen the lead deterministically and retry.
  Grid alignment: with backtest.htf_clock_basis = "count" the HTF period is a bar counter anchored at
  the FIRST ROW OF THE LOADED FILE, so a slice reproduces the full run only if it starts on the full
  corpus's period grid. `grid` aligns the start row down to a multiple of htf_candles_per_range
  (found 2026-10-03: an unaligned slice re-tiled every HTF period and opened 0 of 2 expected trades).
A criterion no run can satisfy is reported as unavailable, never manufactured.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

HARD = ("trade", "long", "short", "stop_exit", "tp1", "tp2")
PREFERENCE = ("multiple_trades",)
STOP_EXITS = ("STOPPED", "TP1_BE_STOP")
TP2_EXITS = ("TP2", "TP1_TP2")


@dataclass(frozen=True)
class EngineTrade:
    trade_id: str
    direction: str
    exit_reason: str
    opened_at: datetime
    closed_at: datetime

    @property
    def lifecycle(self) -> set:
        tags = {"trade", self.direction.lower()}
        if self.exit_reason in STOP_EXITS:
            tags.add("stop_exit")
        if self.exit_reason.startswith("TP1") or self.exit_reason in TP2_EXITS:
            tags.add("tp1")
        if self.exit_reason in TP2_EXITS:
            tags.add("tp2")
        return tags

    def key(self) -> tuple:
        return (self.opened_at.isoformat(), self.direction, self.exit_reason)


@dataclass
class Window:
    first: int
    last: int
    start_row: int
    end_row: int
    satisfied: list = field(default_factory=list)

    @property
    def bars(self) -> int:
        return self.end_row - self.start_row + 1


def read_trades(path: Path) -> list[EngineTrade]:
    out = []
    with Path(path).open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if not row.get("closed_at"):
                continue
            out.append(EngineTrade(row["trade_id"], row["direction"].upper(), row["exit_reason"],
                                   datetime.fromisoformat(row["opened_at"]),
                                   datetime.fromisoformat(row["closed_at"])))
    return sorted(out, key=lambda t: (t.opened_at, t.trade_id))


def read_timestamps(corpus: Path) -> list[datetime]:
    from data_ingestion.corpus_store import load as _corpus_load   # CH-corpus-ssot

    return [datetime.fromisoformat(row["timestamp"])
            for row in _corpus_load(corpus, sequence_check=False).records()]


def founding_sweeps(events: Sequence[dict]) -> list[datetime]:
    return sorted(datetime.fromisoformat(e["timestamp"]) for e in events if e.get("event") == "SWEEP")


def _row_at_or_before(stamps: Sequence[datetime], ts: datetime) -> int:
    lo, hi = 0, len(stamps) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if stamps[mid] <= ts:
            lo = mid
        else:
            hi = mid - 1
    return lo


def satisfied(trades: Sequence[EngineTrade]) -> list[str]:
    tags = set().union(*(t.lifecycle for t in trades)) if trades else set()
    found = [c for c in HARD if c in tags]
    if len(trades) >= 2:
        found.append("multiple_trades")
    return found


def choose_window(trades: Sequence[EngineTrade], stamps: Sequence[datetime], sweeps: Sequence[datetime],
                  lead_bars: int, grid: int = 1) -> Optional[Window]:
    best: Optional[Window] = None
    best_key = None
    for i in range(len(trades)):
        sweep_before = [s for s in sweeps if s <= trades[i].opened_at]
        anchor = sweep_before[-1] if sweep_before else trades[i].opened_at
        start = max(0, _row_at_or_before(stamps, anchor) - lead_bars)
        start -= start % max(1, grid)
        for j in range(i, len(trades)):
            end = min(len(stamps) - 1, _row_at_or_before(stamps, trades[j].closed_at) + 1)
            got = satisfied(trades[i:j + 1])
            hard = sum(1 for c in got if c in HARD)
            key = (-hard, -int("multiple_trades" in got), end - start, start)
            if best_key is None or key < best_key:
                best, best_key = Window(i, j, start, end, got), key
    return best


def unavailable(trades: Sequence[EngineTrade], window: Window) -> list[str]:
    """Criteria the chosen window lacks, split by whether ANY run of the corpus could have them."""
    corpus_has = set(satisfied(trades))
    missing = [c for c in HARD + PREFERENCE if c not in window.satisfied]
    return [f"{c} ({'not in the corpus' if c not in corpus_has else 'cannot coexist with the higher-ranked criteria in a smaller window'})"
            for c in missing]


def write_slice(corpus: Path, start_row: int, end_row: int, out_dir: Path) -> Path:
    """Copy rows [start_row, end_row] verbatim (header kept). Name XAUUSD_W<start>-to-<end>.csv.

    Never overwrites a file with different content (it may carry a clock declaration for its sha):
    a different cut on the same dates gets `-r<start_row>` before the suffix (no extra underscore,
    so the last-underscore symbol parser still reads XAUUSD)."""
    from data_ingestion.corpus_store import load as _corpus_load   # CH-corpus-ssot

    lines = _corpus_load(corpus, sequence_check=False).text.splitlines()
    header, rows = lines[0], lines[1 + start_row: 2 + end_row]
    first = rows[0].split(",", 1)[0][:10]
    last = rows[-1].split(",", 1)[0][:10]
    text = "\n".join([header, *rows]) + "\n"
    path = Path(out_dir) / f"XAUUSD_W{first}-to-{last}.csv"
    if path.exists() and path.read_text(encoding="utf-8") != text:
        path = Path(out_dir) / f"XAUUSD_W{first}-to-{last}-r{start_row}.csv"
        if path.exists() and path.read_text(encoding="utf-8") != text:
            raise FileExistsError(f"{path} exists with different content")
    if not path.exists():
        path.write_text(text, encoding="utf-8")
    return path


def window_trades(trades: Sequence[EngineTrade], window: Window) -> list[EngineTrade]:
    return list(trades[window.first: window.last + 1])
