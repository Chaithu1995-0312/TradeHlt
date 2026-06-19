"""
feature_record_builder — the single stamping/merge point (anti-entropy boundary).

Sub-engines return ONLY their partial dicts; this builder is the one place that stamps
identity (`episode_id`/`position_id`/`symbol`/…) and version (`schema_version`/
`engine_versions`). It guards two ways: a partial may not collide with a reserved/identity
key, and may not smuggle a forbidden aggregate key (purity invariant). This is the schema
authority for FeatureRecord, the way `PositionEpisode` is for episodes.
"""
from __future__ import annotations

from ...registry.engine_registry import engine_versions
from ...schemas.feature_v1_0 import (
    FEATURE_SCHEMA_VERSION,
    FORBIDDEN_AGGREGATE_KEYS,
    RESERVED_KEYS,
)


def build(episode, partials: "list[dict]") -> dict:
    """Stamp identity/version and merge sub-engine partials into one FeatureRecord."""
    record = {
        "schema_version": FEATURE_SCHEMA_VERSION,
        "episode_id": episode.episode_id,
        "position_id": episode.position_id,
        "symbol": episode.symbol,
        "direction": episode.direction,
        "entry_time": episode.entry_time,
        "exit_time": episode.exit_time,
        "engine_versions": engine_versions(),
    }
    for part in partials:
        for key, value in part.items():
            if key in RESERVED_KEYS or key in record:
                raise ValueError(
                    f"feature_record_builder: sub-engine key '{key}' collides with a "
                    f"reserved/identity field"
                )
            if key in FORBIDDEN_AGGREGATE_KEYS:
                raise ValueError(
                    f"feature_record_builder: aggregate key '{key}' is forbidden in the "
                    f"feature layer (purity invariant) — belongs in analytics/"
                )
            record[key] = value
    return record
