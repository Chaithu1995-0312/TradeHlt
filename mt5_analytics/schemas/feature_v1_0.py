"""
feature_v1_0 — the FeatureRecord schema (Kernel 2 output).

One record per PositionEpisode. Identity + version fields are stamped by
`feature_record_builder`; the analytical fields are merged from the pure sub-engines.
NO aggregate fields ever live here (purity invariant) — expectancy/PF/win-rate belong to
the later analytics layer. Field evolution bumps FEATURE_SCHEMA_VERSION + adds a migration.
"""
from __future__ import annotations

FEATURE_SCHEMA_VERSION = "1.0"

# Identity/version keys the builder always stamps (used to guard against a sub-engine
# accidentally emitting one of them).
RESERVED_KEYS = frozenset(
    {
        "schema_version",
        "episode_id",
        "position_id",
        "symbol",
        "direction",
        "entry_time",
        "exit_time",
        "engine_versions",
    }
)

# Aggregate keys that must NEVER appear in a feature record (purity guard — enforced by
# tests/mt5_analytics/test_feature_engine.py).
FORBIDDEN_AGGREGATE_KEYS = frozenset(
    {
        "expectancy",
        "expectancy_mean",
        "profit_factor",
        "win_rate",
        "winrate",
        "max_drawdown",
        "max_drawdown_rr",
        "sharpe",
        "cagr",
    }
)
