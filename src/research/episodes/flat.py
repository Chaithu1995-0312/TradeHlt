"""Tier-2 flat projection — one row per (episode, timestep).

Derived idempotently from Tier 1: re-running the projection on the same episodes
produces byte-identical rows, and nothing here is ever a source of truth. Delete the
flat corpus and rebuild it; that is the point of the tier split (substrate §13).

Format is gzipped CSV rather than JSONL because this tier exists to be *queried* —
pandas, DuckDB and every spreadsheet read CSV natively, and Parquet is unavailable in
this environment (see `store.py`). Columns are stable and ordered.

Label and event columns are OPT-IN. They denormalize a derived artifact onto every
step of an episode, so they inflate the table and re-state a per-episode fact N times;
useful for a single-pass analysis, wrong as a default.
"""
from __future__ import annotations

import csv
import gzip
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from research.episodes.events import EventSet
from research.episodes.policy import LabelSet
from research.episodes.schema import Derived, OpportunityEpisode, resolved_derived

# Stable column order: identity → observation → derived.
IDENTITY_COLUMNS = ("episode_id", "population", "instrument", "timeframe",
                    "direction", "entry_bar_index", "entry_timestamp",
                    "entry_price", "sl_price", "tp_price", "risk_distance")
OBS_COLUMNS = ("t", "bar_index", "timestamp", "open", "high", "low", "close", "volume")
DERIVED_COLUMNS = tuple(f.name for f in fields(Derived))

# Per-episode label fields worth denormalizing when labels are joined.
LABEL_COLUMNS = ("exit_policy_id", "outcome", "rr_achieved", "rr_net",
                 "duration_candles", "time_to_tp", "time_to_failure", "reached_1r")


def columns(*, with_labels: bool = False, with_events: bool = False) -> list[str]:
    cols = [*IDENTITY_COLUMNS, *OBS_COLUMNS, *DERIVED_COLUMNS]
    if with_labels:
        cols += [f"label_{c}" for c in LABEL_COLUMNS]
    if with_events:
        cols += ["event_kinds"]
    return cols


def flat_rows(
    episode: OpportunityEpisode,
    *,
    labels: LabelSet | None = None,
    events: EventSet | None = None,
    include_entry_bar: bool = True,
) -> list[dict[str, Any]]:
    """Rows for one episode. Pure — same episode in, same rows out."""
    entry = episode.entry
    derived = resolved_derived(episode)
    base = {
        "episode_id": episode.episode_id,
        "population": episode.population,
        "instrument": episode.instrument,
        "timeframe": episode.timeframe,
        "direction": entry.direction,
        "entry_bar_index": entry.bar_index,
        "entry_timestamp": entry.timestamp,
        "entry_price": entry.entry_price,
        "sl_price": entry.sl_price,
        "tp_price": entry.tp_price,
        "risk_distance": entry.risk_distance,
    }
    if labels is not None:
        base.update({f"label_{c}": getattr(labels, c) for c in LABEL_COLUMNS})

    by_step: dict[int, list[str]] = {}
    if events is not None:
        for e in events.events:
            by_step.setdefault(e.t, []).append(e.kind)

    rows: list[dict[str, Any]] = []
    for step, d in zip(episode.steps, derived):
        if not include_entry_bar and step.obs.t < 1:
            continue
        row = dict(base)
        row.update({k: getattr(step.obs, k) for k in OBS_COLUMNS})
        # t=0 has no derived state by contract — emit blanks, never zeros, so a
        # reader cannot mistake "not applicable" for "flat path".
        row.update(asdict(d) if d is not None else {c: None for c in DERIVED_COLUMNS})
        if events is not None:
            row["event_kinds"] = "|".join(sorted(by_step.get(step.obs.t, [])))
        rows.append(row)
    return rows


def flat_table(
    episodes: Iterable[OpportunityEpisode],
    *,
    labels: dict[str, LabelSet] | None = None,
    events: dict[str, EventSet] | None = None,
    include_entry_bar: bool = True,
) -> Iterator[dict[str, Any]]:
    """Stream rows for many episodes. Lazy — never materializes the whole corpus."""
    for ep in episodes:
        yield from flat_rows(
            ep,
            labels=(labels or {}).get(ep.episode_id),
            events=(events or {}).get(ep.episode_id),
            include_entry_bar=include_entry_bar,
        )


def write_flat(
    episodes: Sequence[OpportunityEpisode],
    out_dir: Path | str,
    *,
    filename: str = "episodes_flat.csv.gz",
    labels: dict[str, LabelSet] | None = None,
    events: dict[str, EventSet] | None = None,
    include_entry_bar: bool = True,
) -> dict[str, Any]:
    """Write the Tier-2 table. Returns a manifest."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    cols = columns(with_labels=labels is not None, with_events=events is not None)

    n_rows = 0
    with gzip.open(path, "wt", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for row in flat_table(episodes, labels=labels, events=events,
                              include_entry_bar=include_entry_bar):
            writer.writerow(row)
            n_rows += 1

    return {
        "path": str(path),
        "n_episodes": len(episodes),
        "n_rows": n_rows,
        "columns": cols,
        "bytes_on_disk": path.stat().st_size,
        "tier": 2,
        "derived_from": "tier1_episodes",
        "backend": "gzip_csv_v1",
    }


def read_flat(path: Path | str) -> Iterator[dict[str, str]]:
    """Stream the flat table back. Values are strings — this tier is for analytics
    tools that do their own typing (pandas/DuckDB), not for round-tripping episodes."""
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as fh:
        yield from csv.DictReader(fh)
