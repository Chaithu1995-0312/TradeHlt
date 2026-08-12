"""Benchmark dataset manifest — identical market reality for every engine.

Primary candidate binds the XAUUSD M15 Phase-1 frozen candidate
(docs/governance/xauusd_m15_phase1_frozen_candidate.json).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class DatasetManifest:
    """Pin of a shared OHLCV corpus for OSS Lab benchmarks."""

    dataset_id: str
    data_hash: str
    instrument: str
    timeframe: str
    start: str
    end: str
    row_count: int
    timezone: str
    schema_hash: str
    missing_bar_policy: str
    normalization_policy: str
    source_authority: str
    physical_path: str
    authority_status: str
    notes: tuple[str, ...] = field(default_factory=tuple)
    explicitly_not: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["notes"] = list(self.notes)
        d["explicitly_not"] = list(self.explicitly_not)
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "DatasetManifest":
        return cls(
            dataset_id=str(raw["dataset_id"]),
            data_hash=str(raw["data_hash"]),
            instrument=str(raw["instrument"]),
            timeframe=str(raw["timeframe"]),
            start=str(raw["start"]),
            end=str(raw["end"]),
            row_count=int(raw["row_count"]),
            timezone=str(raw["timezone"]),
            schema_hash=str(raw["schema_hash"]),
            missing_bar_policy=str(raw["missing_bar_policy"]),
            normalization_policy=str(raw["normalization_policy"]),
            source_authority=str(raw["source_authority"]),
            physical_path=str(raw["physical_path"]),
            authority_status=str(raw["authority_status"]),
            notes=tuple(raw.get("notes") or ()),
            explicitly_not=tuple(raw.get("explicitly_not") or ()),
        )


# Canonical primary pin — mirrors CORPUS_AUTHORITY Phase-1 frozen candidate.
# schema_hash: OHLCV column contract is owned by data_ingestion/ohlcv_schema;
# when unknown at lab bootstrap we record UNKNOWN rather than invent a hash.
XAUUSD_M15_PHASE1_PRIMARY = DatasetManifest(
    dataset_id="BM-XAUUSD-M15-PHASE1-FROZEN",
    data_hash="4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56",
    instrument="XAUUSD",
    timeframe="M15",
    start="2024-05-22T01:00:00",
    end="2026-05-21T23:45:00",
    row_count=47275,
    timezone="broker_local_labeled_utc",  # F-066: MT5 broker-server time labeled UTC
    schema_hash="UNKNOWN",  # closed by ohlcv-output-contract when lab run binds it
    missing_bar_policy="fail_closed_no_silent_fill",
    normalization_policy="raw_ohlcv_no_price_rescale",
    source_authority="docs/governance/xauusd_m15_phase1_frozen_candidate.json",
    physical_path="data/mt5/XAUUSD_M15.csv",
    authority_status="FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION",
    notes=(
        "Scope freeze only — not AUTHORITATIVE / not ECONOMICALLY_ADMISSIBLE.",
        "All OSS adapters MUST consume this pin or a later APPROVED successor of the SAME hash.",
        "Do not use data/XAUUSD_M15.csv (extended root) for this benchmark.",
        "Timezone semantics residual F-066 — document, do not silently re-label.",
    ),
    explicitly_not=(
        "AUTHORITATIVE",
        "VALIDATED",
        "ECONOMICALLY_ADMISSIBLE",
        "APPROVED",
        "PRODUCTION_AUTHORITY",
    ),
)
