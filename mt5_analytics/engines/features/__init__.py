"""
Feature engines (Kernel 2) — PositionEpisode → FeatureRecord.

The SECOND sacred boundary. Strict purity invariant: one episode → one feature record,
NO aggregation (expectancy/PF/win-rate/distribution belong to the later analytics/ layer).
Each sub-engine is pure and returns only its partial dict; `feature_record_builder` is the
single place that stamps identity/version and merges the partials.
"""
