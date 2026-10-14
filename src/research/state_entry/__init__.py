"""state_entry — CRT engine state-transition events as hypothetical entries (MC-STATEENTRY).

Question (user, 2026-10-05): at which CRT ENGINE transition events would an entry have
carried positive ``multi_tp_walk`` R over N future candles, ignoring intrabar ordering?

The engine trades exactly one of these events (the RETEST close, confirmed one bar later,
F-110). Every other transition is an entry it never takes. This package measures all of
them on one footing:

    extract.py   events.jsonl + corpus bars -> EntryUnit rows (joined by timestamp)
    walk.py      EntryUnit x geometry x horizon x arm -> R rows via multi_tp_walk
    evaluate.py  chronological split, BH-FDR, long_only + random_entry controls, verdicts

Grants no authority (CLAUDE.md §6.5). Nothing here promotes, gates, or changes
``ACTIVE_VERSION``. Contract:
``configs/research/measurement_contracts/instances/MC-STATEENTRY-XAUUSD-M15-V1.json``.
"""

from research.state_entry.extract import (
    ENTRY_KINDS,
    Bar,
    EntryUnit,
    bars_from_candles,
    extract_units,
    load_events,
)

__all__ = [
    "ENTRY_KINDS",
    "Bar",
    "EntryUnit",
    "bars_from_candles",
    "extract_units",
    "load_events",
]
