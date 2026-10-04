"""RunManifest — reproducibility envelope for every benchmark run."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class EnvironmentFingerprint:
    os_name: str = "UNKNOWN"
    python_version: str = "UNKNOWN"
    rust_version: Optional[str] = None
    cpu_arch: str = "UNKNOWN"
    hostname_hash: Optional[str] = None  # never store raw hostname if privacy-sensitive

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunManifest:
    """Everything needed to re-run and compare triple-run hashes."""

    run_id: str
    experiment_id: str
    engine: str
    engine_version: str
    git_commit: str
    dataset_id: str
    data_hash: str
    config_hash: str
    schema_hash: str
    dependency_lock_hash: str
    random_seed: Optional[int]
    command: list[str]
    timestamp_utc: str
    environment: EnvironmentFingerprint = field(default_factory=EnvironmentFingerprint)
    fill_model_id: Optional[str] = None
    cost_mode: str = "UNKNOWN"  # NO_COST | WITH_COST | DECLARED
    hypothesis: str = ""
    notes: list[str] = field(default_factory=list)
    # Reproducibility hashes (filled after run)
    signals_hash: Optional[str] = None
    orders_hash: Optional[str] = None
    fills_hash: Optional[str] = None
    trades_hash: Optional[str] = None
    equity_hash: Optional[str] = None
    metrics_hash: Optional[str] = None
    # Authority
    authority: str = "RESEARCH_LAB_ONLY"
    trust_status: str = "UNSEALED"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RunManifest":
        env_raw = raw.get("environment") or {}
        env = EnvironmentFingerprint(**{
            k: env_raw[k]
            for k in EnvironmentFingerprint.__dataclass_fields__
            if k in env_raw
        })
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in raw.items() if k in known and k != "environment"}
        return cls(environment=env, **filtered)
