"""structural_event_source.py — Phase E1 harvester: the full CRT structural-event population.

Runs ONE deterministic backtest (reusing the execution_planner_replay backtest runner) and parses the
`{INSTR}_events.jsonl` STATE_TRANSITION stream into a `StructuralEvent` list, tracking episodes so each
event carries its CONTINUATION direction (derived causally from the displacement candle body) and a
`completed` flag (did the sweep's episode reach RETEST). Yields BOTH the completed
sweep→displacement→retest population (the test) AND the sweep-only population (control D), plus the
funnel counts. Measure-only, deterministic, no spine state run inline — pure artifact parse.

Direction & entry are NULL in the transition records, so: entry = the event candle's close (matched by
TIMESTAMP to the CandleLoader stream, avoiding index-base ambiguity), continuation direction = the
displacement candle's body sign (sweep-only uses the sweep candle's body sign = implied reversal).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from utils.parquet_store import iter_records

from research.indicators import atr as _research_atr

_STAGES = ("SWEEP", "DISPLACEMENT", "EXPANSION", "RETEST")


@dataclass(frozen=True)
class StructuralEvent:
    stage: str            # one of _STAGES
    entry_index: int      # CandleLoader stream index (via timestamp match)
    entry: float          # close at the event candle
    direction: str        # "long" | "short" — continuation direction
    atr: float            # research ATR at the event candle
    completed: bool       # episode reached RETEST (meaningful for SWEEP → control D)


def _body_dir(candle) -> str:
    o = float(getattr(candle, "open", candle.close))
    return "long" if float(candle.close) >= o else "short"


def harvest(instrument: str, csv: str, out_root: Path, *, atr_period: int = 14):
    """Return (events, funnel, candles). Runs one backtest, parses events.jsonl into StructuralEvents."""
    from scripts.research.execution_planner_replay import _run_backtest, _norm_ts
    from runtime.backtest_v2 import CandleLoader

    tel, _trd, _metrics = _run_backtest(instrument, csv, out_root / "_run" / instrument)
    run_dir = Path(tel).parent
    ev_files = sorted(run_dir.rglob(f"{instrument}_events.jsonl"), key=lambda p: p.stat().st_mtime)
    if not ev_files:
        ev_files = sorted(Path(tel).parents[1].rglob(f"{instrument}_events.jsonl"),
                          key=lambda p: p.stat().st_mtime)
    if not ev_files:
        raise SystemExit(f"no {instrument}_events.jsonl under {run_dir}")
    ev_path = ev_files[-1]

    candles = list(CandleLoader(csv, instrument).stream())
    for i, c in enumerate(candles):
        c.index = i
    ts_map = {_norm_ts(str(c.timestamp)): i for i, c in enumerate(candles)}

    def _atr(i: int) -> float:
        return _research_atr(candles[max(0, i - atr_period):i + 1], atr_period)

    events: list[StructuralEvent] = []
    funnel: Counter = Counter()
    pending_sweep = None     # (idx, entry, direction, atr) — current episode's sweep
    disp_dir = None
    reached_retest = False

    def _flush():
        nonlocal pending_sweep
        if pending_sweep is not None and not reached_retest:   # incomplete → sweep-only (control D)
            events.append(StructuralEvent("SWEEP", *pending_sweep, completed=False))
        pending_sweep = None

    # Only three of the nine columns are read, so a Parquet projection (when one exists)
    # skips the polymorphic `metadata` blob entirely. Falls back to the JSONL source
    # whenever no fresh projection is present -- same records either way.
    for d in iter_records(ev_path, columns=["event", "state_to", "timestamp"]):
        if d.get("event") != "STATE_TRANSITION":
            continue
        st = d.get("state_to")
        if st == "EXECUTION":
            funnel["execution"] += 1
            continue
        if st not in ("SWEEP", "DISPLACEMENT", "EXPANSION", "RETEST", "RANGE"):
            continue
        if st == "RANGE":                         # episode end (reset)
            _flush(); disp_dir = None; reached_retest = False
            continue
        idx = ts_map.get(_norm_ts(d.get("timestamp", "")))
        if idx is None:
            continue
        if st == "SWEEP":
            _flush()                              # close previous episode first
            disp_dir = None; reached_retest = False
            sdir = _body_dir(candles[idx])
            pending_sweep = (idx, float(candles[idx].close), sdir, _atr(idx))
            funnel["sweep"] += 1
        elif st == "DISPLACEMENT":
            disp_dir = _body_dir(candles[idx])
            funnel["displacement"] += 1
            events.append(StructuralEvent("DISPLACEMENT", idx, float(candles[idx].close),
                                          disp_dir, _atr(idx), completed=False))
        elif st == "EXPANSION":
            funnel["expansion"] += 1
            dd = disp_dir or _body_dir(candles[idx])
            events.append(StructuralEvent("EXPANSION", idx, float(candles[idx].close),
                                          dd, _atr(idx), completed=False))
        elif st == "RETEST":
            reached_retest = True
            funnel["retest"] += 1
            dd = disp_dir or _body_dir(candles[idx])
            events.append(StructuralEvent("RETEST", idx, float(candles[idx].close),
                                          dd, _atr(idx), completed=True))
    _flush()
    return events, dict(funnel), candles
