"""
run_summary_v1_0 — the typed result of one pipeline run.

Returned by `shared_pipeline.process_closed_positions`. The cheap counters cost nothing
and make Phase 6.5's audit lines rich for free — this is exactly the payload 6.5 persists
to `audit/{rebuild,daemon}_runs.jsonl`. `episodes` is carried for the parity test and is
NOT part of the persisted audit dict.

Deferred (Phase 4.1): promote `warnings` to typed `WarningRecord {code,message,episode_id}`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

RUN_SUMMARY_SCHEMA_VERSION = "1.0"


@dataclass
class RunSummary:
    episodes_seen: int = 0
    episodes_written: int = 0
    features_written: int = 0
    duplicates_skipped: int = 0
    episodes_skipped: int = 0
    anomaly_count: int = 0
    warning_count: int = 0
    anomalies: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    duration_ms: float = 0.0
    pipeline_version: str = ""
    schema_version: str = RUN_SUMMARY_SCHEMA_VERSION
    # carried for the parity test / callers; excluded from the audit dict.
    episodes: list = field(default_factory=list)

    def to_audit_dict(self) -> dict:
        """The persistable subset (no bulky `episodes` payload)."""
        return {
            "schema_version": self.schema_version,
            "episodes_seen": self.episodes_seen,
            "episodes_written": self.episodes_written,
            "features_written": self.features_written,
            "duplicates_skipped": self.duplicates_skipped,
            "episodes_skipped": self.episodes_skipped,
            "anomaly_count": self.anomaly_count,
            "warning_count": self.warning_count,
            "anomalies": list(self.anomalies),
            "warnings": list(self.warnings),
            "duration_ms": round(self.duration_ms, 3),
            "pipeline_version": self.pipeline_version,
        }
