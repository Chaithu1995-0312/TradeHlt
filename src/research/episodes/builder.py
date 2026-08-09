"""EpisodeBuilder — candles + entry geometry → observation timeline.

Owns the TIMELINE. Owns NO exit policy: it never decides when a position closes,
never reads an outcome, never touches `forward_walk`. That separation is what makes
one episode evaluable under many policies (substrate §10).

No-lookahead is structural, not asserted: the builder slices exactly
`candles[entry_index : entry_index + 1 + max_forward]` and stamps `t` from the slice
offset, so a forward bar with `t>=1` always has `bar_index > entry.bar_index`. The
kernel's own guard then re-checks this independently at label time.
"""
from __future__ import annotations

import hashlib
import inspect
from datetime import datetime, timezone
from typing import Any, Sequence

from research.episodes.protocol import (
    MAX_FORWARD,
    PIT_STATUS,
    PROTOCOL_ID,
    TIMEFRAME,
    compute_protocol_hash,
)
from research.episodes.schema import (
    EntrySnapshot,
    EpisodeProvenance,
    EpisodeStep,
    Observation,
    OpportunityEpisode,
    entry_geometry_hash,
    episode_id,
    recompute_derived,
)

BUILDER_ID = "research.episodes.builder.build_episode"


def builder_hash() -> str:
    """SHA-256 of this module's source — pins which code produced an episode."""
    import research.episodes.builder as _self

    src = inspect.getsource(_self)
    return hashlib.sha256(src.encode("utf-8")).hexdigest()[:32]


def _norm_ts(value: Any) -> str:
    """Canonical timestamp string. Mirrors clean_labels.builder._norm_ts."""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    return str(value).replace("T", " ").strip()


def build_episode(
    *,
    instrument: str,
    population: str,
    entry: EntrySnapshot,
    candles: Sequence,
    max_forward: int = MAX_FORWARD,
    timeframe: str = TIMEFRAME,
    candle_source: str = "",
    candle_source_hash: str = "",
    feature_schema_hash: str = "",
    source_run_id: str = "",
    metadata: dict[str, Any] | None = None,
    cache_derived: bool = True,
    protocol_hash: str | None = None,
) -> OpportunityEpisode:
    """Build one canonical episode.

    Args:
        entry: frozen decision context. `entry.bar_index` must index into `candles`.
        candles: the FULL instrument candle sequence (indexable, bars carry
            .timestamp/.open/.high/.low/.close/.volume/.index).
        max_forward: number of post-entry bars to capture. The timeline is
            therefore at most `1 + max_forward` steps (t=0 .. t=max_forward).
        cache_derived: store the recomputable Derived layer inline. Set False for
            observation-minimal storage on large populations.

    Raises:
        ValueError: on out-of-range entry index, zero risk distance, or a candle
            sequence whose global indices disagree with their positions.
    """
    i0 = entry.bar_index
    if i0 < 0 or i0 >= len(candles):
        raise ValueError(
            f"build_episode: entry.bar_index {i0} out of range (n_candles={len(candles)})"
        )
    if entry.risk_distance <= 0:
        raise ValueError(
            f"build_episode: non-positive risk_distance "
            f"(entry={entry.entry_price}, sl={entry.sl_price})"
        )
    if entry.direction not in ("long", "short"):
        raise ValueError(f"build_episode: bad direction {entry.direction!r}")
    if max_forward < 0:
        raise ValueError(f"build_episode: negative max_forward ({max_forward})")

    window = candles[i0 : i0 + 1 + max_forward]
    if not window:
        raise ValueError(f"build_episode: empty window at entry index {i0}")

    observations: list[Observation] = []
    for t, bar in enumerate(window):
        # Global index is load-bearing: it joins to the feature matrix and it is
        # what the kernel's no-lookahead guard compares against. If a caller hands
        # us a re-indexed slice, fail loudly rather than emit a mislabelled episode.
        bar_index = int(getattr(bar, "index", i0 + t))
        if bar_index != i0 + t:
            raise ValueError(
                f"build_episode: candle index mismatch at t={t} — bar.index={bar_index}, "
                f"expected {i0 + t}. Pass the full candle sequence, not a slice."
            )
        observations.append(Observation(
            t=t,
            bar_index=bar_index,
            timestamp=_norm_ts(getattr(bar, "timestamp", "")),
            open=float(bar.open),
            high=float(bar.high),
            low=float(bar.low),
            close=float(bar.close),
            volume=float(getattr(bar, "volume", 0.0) or 0.0),
        ))

    derived = recompute_derived(entry, observations) if cache_derived else [None] * len(observations)
    steps = [EpisodeStep(obs=o, derived=d) for o, d in zip(observations, derived)]

    prov = EpisodeProvenance(
        protocol_id=PROTOCOL_ID,
        protocol_hash=protocol_hash or compute_protocol_hash({"instrument": instrument}),
        builder_id=BUILDER_ID,
        builder_hash=builder_hash(),
        candle_source=candle_source,
        candle_source_hash=candle_source_hash,
        feature_schema_hash=feature_schema_hash,
        entry_geometry_hash=entry_geometry_hash(entry),
        pit_status=PIT_STATUS,
        source_run_id=source_run_id,
        created_utc=datetime.now(timezone.utc).isoformat(),
    )

    return OpportunityEpisode(
        episode_id=episode_id(
            instrument, entry.timestamp, entry.direction,
            entry.entry_price, entry.sl_price, population,
        ),
        population=population,
        instrument=instrument,
        timeframe=timeframe,
        entry=entry,
        steps=steps,
        provenance=prov,
        metadata=dict(metadata or {}),
    )
