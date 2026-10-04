"""Identity store — Phase 4 writers/readers for the frozen layer identities.

Subordinate to:
  CANONICAL_LAYER_IDENTITY_CONTRACT.md v1.0.0 / CH-canonical-layer-identity
  STORAGE_PRESERVATION_CONTRACT.md v1.0.0 / CH-storage-preservation-contract
  PHYSICAL_STORAGE_ARCHITECTURE.md v1.0.0 / CH-physical-storage-architecture

Load is Identity Check only. Recompute from HEAD pipeline/encoder/engine is not recovery.
Not on the live decision path. Grants no G001.
"""
from identity.check import CheckResult, identity_check, identity_check_event_series
from identity.outcome import L5WriteError, build_l5_record
from identity.query import BarReplay, IdentityQuery
from identity.store import IdentityStore
from identity.tokens import (
    STATUS_IDENTITY_INCOMPLETE,
    STATUS_IDENTITY_MISMATCH,
    STATUS_PRESERVED,
    STATUS_UNIDENTIFIED,
    STATUS_UNJOINABLE,
)

__all__ = [
    "BarReplay",
    "CheckResult",
    "IdentityQuery",
    "IdentityStore",
    "L5WriteError",
    "build_l5_record",
    "STATUS_IDENTITY_INCOMPLETE",
    "STATUS_IDENTITY_MISMATCH",
    "STATUS_PRESERVED",
    "STATUS_UNIDENTIFIED",
    "STATUS_UNJOINABLE",
    "identity_check",
    "identity_check_event_series",
]
