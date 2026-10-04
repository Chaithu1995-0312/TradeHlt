"""
engine_registry — frozen version stamps for every scoring/analytics engine.

Stamped into every feature record and every partition manifest so any artifact is
traceable to the exact algorithm set that produced it (replayability pillar). When an
engine's logic changes, bump its version here — old artifacts keep their old stamp and
`rebuild.py` can reproduce or supersede them deterministically.
"""
from __future__ import annotations

import hashlib
import json

# name -> {version, hash}. `hash` is a short fingerprint of the version label; once the
# engines exist it may be upgraded to hash the engine source. Kept additive.
ENGINE_REGISTRY: dict[str, dict[str, str]] = {
    "reconstructor": {"version": "recon_v1.0"},
    "mfe_mae": {"version": "mfe_v1.0"},
    "rr": {"version": "rr_v1.0"},
    "gaussian": {"version": "g_v1.0"},
    "regime": {"version": "regime_v1.0"},
    "crt_validator": {"version": "crt_val_v1.0"},
}

# Backfill a stable per-engine fingerprint from the version label.
for _name, _meta in ENGINE_REGISTRY.items():
    _meta.setdefault(
        "hash", hashlib.sha256(_meta["version"].encode("utf-8")).hexdigest()[:12]
    )


def engine_versions() -> dict[str, str]:
    """Flat {engine: version} map for stamping into records."""
    return {name: meta["version"] for name, meta in ENGINE_REGISTRY.items()}


def registry_hash() -> str:
    """Deterministic SHA-256 of the whole registry (manifest provenance field)."""
    canonical = json.dumps(ENGINE_REGISTRY, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
