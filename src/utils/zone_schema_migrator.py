"""
zone_schema_migrator.py
=======================
ISSUE 4 FIX — BitNet Zone Schema Migration Utility.

Problem:
  zone_registry.json uses LEGACY schema:
    {center: [...], radius: [...], min_score: float, weight: float}

  Runtime (zone_gate.py) expects NEW schema:
    {mu: [...], sigma: [...], weights: [...], threshold: float}

Migration rules (deterministic, lossless):
  mu        = center          (rename only)
  sigma     = radius          (rename only)
  weights   = uniform vector  len(mu) elements, each = 1/len(mu)
  threshold = min_score       (rename only)

Usage:
    # Migrate a file in-place (creates .bak backup):
    migrate_zone_registry("models/zone_registry.json")

    # Or migrate a dict in memory:
    new_zones = migrate_zone_list(old_zones)

    # Validate a loaded registry against the new schema:
    validate_zone_schema(registry_dict)  # raises ZoneSchemaError if invalid
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# Keys required in the NEW (runtime) zone schema
_NEW_REQUIRED_KEYS = {"mu", "sigma", "weights", "threshold"}

# Keys that indicate a zone is in the OLD (legacy) schema
_LEGACY_INDICATOR_KEYS = {"center", "radius", "min_score"}


# ─────────────────────────────────────────────────────────────────────────────
# EXCEPTION
# ─────────────────────────────────────────────────────────────────────────────

class ZoneSchemaError(ValueError):
    """Raised when a zone registry does not conform to the required schema."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def is_legacy_zone(zone: dict) -> bool:
    """Return True if zone uses the old {center, radius, min_score} schema."""
    return bool(_LEGACY_INDICATOR_KEYS & set(zone.keys()))


def is_new_zone(zone: dict) -> bool:
    """Return True if zone uses the new {mu, sigma, weights, threshold} schema."""
    return _NEW_REQUIRED_KEYS.issubset(zone.keys())


# ─────────────────────────────────────────────────────────────────────────────
# SINGLE ZONE MIGRATION
# ─────────────────────────────────────────────────────────────────────────────

def migrate_zone(zone: dict) -> dict:
    """
    Migrate a single zone dict from legacy → new schema.

    Rules:
      mu        = center
      sigma     = radius
      weights   = uniform vector of length len(mu), each = 1/len(mu)
      threshold = min_score

    Args:
        zone: a zone dict (may be legacy OR already-new schema)

    Returns:
        zone dict in new schema (always — idempotent if already new)

    Raises:
        ZoneSchemaError: if the zone is neither valid legacy nor valid new schema
    """
    if is_new_zone(zone):
        # Already migrated — validate and return as-is
        _validate_new_zone(zone)
        return dict(zone)

    if not is_legacy_zone(zone):
        raise ZoneSchemaError(
            f"zone_schema_migrator: zone has unrecognised schema. "
            f"Expected legacy keys {_LEGACY_INDICATOR_KEYS} or "
            f"new keys {_NEW_REQUIRED_KEYS}. Got: {set(zone.keys())}"
        )

    # ── Legacy → New migration ────────────────────────────────────────────────
    center = zone.get("center")
    radius = zone.get("radius")
    min_score = zone.get("min_score")

    if center is None:
        raise ZoneSchemaError("migrate_zone: legacy zone missing 'center' field")
    if radius is None:
        raise ZoneSchemaError("migrate_zone: legacy zone missing 'radius' field")
    if min_score is None:
        raise ZoneSchemaError("migrate_zone: legacy zone missing 'min_score' field")

    # Coerce to list if scalar
    mu: List[float] = [float(center)] if not isinstance(center, list) else [float(v) for v in center]
    sigma: List[float] = [float(radius)] if not isinstance(radius, list) else [float(v) for v in radius]

    if len(mu) != len(sigma):
        raise ZoneSchemaError(
            f"migrate_zone: center length ({len(mu)}) != radius length ({len(sigma)}). "
            "Cannot determine uniform weights — zone data is inconsistent."
        )

    n = len(mu)
    weights: List[float] = [round(1.0 / n, 8)] * n if n > 0 else []

    threshold = float(min_score)

    new_zone: dict = {
        "mu":        mu,
        "sigma":     sigma,
        "weights":   weights,
        "threshold": threshold,
    }

    # Preserve any extra fields (e.g. "weight" used as zone importance score)
    preserved_extras = {
        k: v for k, v in zone.items()
        if k not in _LEGACY_INDICATOR_KEYS and k not in _NEW_REQUIRED_KEYS
    }
    new_zone.update(preserved_extras)

    logger.debug(
        "migrate_zone: migrated legacy zone | mu=%s sigma=%s threshold=%.4f",
        mu, sigma, threshold,
    )
    return new_zone


# ─────────────────────────────────────────────────────────────────────────────
# LIST MIGRATION
# ─────────────────────────────────────────────────────────────────────────────

def migrate_zone_list(zones: List[dict]) -> List[dict]:
    """
    Migrate a list of zone dicts.

    Args:
        zones: list of zone dicts (mixed legacy/new allowed)

    Returns:
        list of zone dicts all in new schema

    Raises:
        ZoneSchemaError: if any zone cannot be migrated
    """
    migrated = []
    for i, zone in enumerate(zones):
        try:
            migrated.append(migrate_zone(zone))
        except ZoneSchemaError as exc:
            raise ZoneSchemaError(f"migrate_zone_list: zone[{i}] failed: {exc}") from exc
    return migrated


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY MIGRATION (FILE)
# ─────────────────────────────────────────────────────────────────────────────

def migrate_zone_registry(
    registry_path: str,
    backup: bool = True,
) -> dict:
    """
    Migrate a zone_registry.json file from legacy → new schema IN PLACE.

    Args:
        registry_path: path to zone_registry.json
        backup: if True, creates .bak copy before overwriting

    Returns:
        Migrated registry dict (new schema)

    Raises:
        FileNotFoundError: if registry_path does not exist
        ZoneSchemaError: if any zone cannot be migrated
    """
    if not os.path.exists(registry_path):
        raise FileNotFoundError(
            f"migrate_zone_registry: registry not found at '{registry_path}'"
        )

    with open(registry_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if "zones" not in raw or not isinstance(raw["zones"], list):
        raise ZoneSchemaError(
            f"migrate_zone_registry: expected top-level 'zones' list in {registry_path}"
        )

    # Check if migration is needed
    any_legacy = any(is_legacy_zone(z) for z in raw["zones"])
    all_new = all(is_new_zone(z) for z in raw["zones"])

    if all_new and not any_legacy:
        logger.info(
            "migrate_zone_registry: '%s' already uses new schema — no migration needed.",
            registry_path,
        )
        return raw

    if backup:
        bak_path = registry_path + ".bak"
        shutil.copy2(registry_path, bak_path)
        logger.info("migrate_zone_registry: backup written to '%s'", bak_path)

    new_zones = migrate_zone_list(raw["zones"])
    raw["zones"] = new_zones
    raw["schema_version"] = "v2"
    raw["migrated"] = True

    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)

    logger.info(
        "migrate_zone_registry: migrated %d zone(s) in '%s' to new schema.",
        len(new_zones), registry_path,
    )
    return raw


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def _validate_new_zone(zone: dict) -> None:
    """
    Strict validation of a zone in the new schema.

    Raises:
        ZoneSchemaError: if any required field is missing or malformed
    """
    missing = _NEW_REQUIRED_KEYS - set(zone.keys())
    if missing:
        raise ZoneSchemaError(
            f"_validate_new_zone: missing required keys: {sorted(missing)}"
        )

    mu = zone["mu"]
    sigma = zone["sigma"]
    weights = zone["weights"]
    threshold = zone["threshold"]

    if not isinstance(mu, list) or len(mu) == 0:
        raise ZoneSchemaError("_validate_new_zone: 'mu' must be a non-empty list")
    if not isinstance(sigma, list) or len(sigma) == 0:
        raise ZoneSchemaError("_validate_new_zone: 'sigma' must be a non-empty list")
    if not isinstance(weights, list) or len(weights) == 0:
        raise ZoneSchemaError("_validate_new_zone: 'weights' must be a non-empty list")
    if len(mu) != len(sigma) or len(mu) != len(weights):
        raise ZoneSchemaError(
            f"_validate_new_zone: mu/sigma/weights length mismatch: "
            f"len(mu)={len(mu)}, len(sigma)={len(sigma)}, len(weights)={len(weights)}"
        )

    try:
        float(threshold)
    except (TypeError, ValueError):
        raise ZoneSchemaError(
            f"_validate_new_zone: 'threshold' must be numeric, got {type(threshold).__name__}"
        )


def validate_zone_schema(registry: dict) -> None:
    """
    Validate an entire zone registry dict against the new schema.

    Args:
        registry: loaded zone registry dict (must have 'zones' list)

    Raises:
        ZoneSchemaError: if any zone fails new-schema validation
    """
    if "zones" not in registry or not isinstance(registry["zones"], list):
        raise ZoneSchemaError(
            "validate_zone_schema: registry must have a top-level 'zones' list"
        )

    for i, zone in enumerate(registry["zones"]):
        try:
            _validate_new_zone(zone)
        except ZoneSchemaError as exc:
            raise ZoneSchemaError(
                f"validate_zone_schema: zone[{i}] invalid: {exc}"
            ) from exc


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description="Migrate zone_registry.json to new schema")
    ap.add_argument("registry", nargs="?", default="models/zone_registry.json",
                    help="Path to zone_registry.json (default: models/zone_registry.json)")
    ap.add_argument("--no-backup", action="store_true",
                    help="Skip .bak backup before overwriting")
    ap.add_argument("--validate-only", action="store_true",
                    help="Validate schema only (no migration)")
    args = ap.parse_args()

    try:
        if args.validate_only:
            with open(args.registry) as f:
                reg = json.load(f)
            validate_zone_schema(reg)
            print(f"✅ {args.registry}: schema is VALID (new format)")
        else:
            result = migrate_zone_registry(args.registry, backup=not args.no_backup)
            print(f"✅ Migrated {len(result['zones'])} zone(s) in {args.registry}")
    except (FileNotFoundError, ZoneSchemaError) as e:
        print(f"❌ ERROR: {e}", file=sys.stderr)
        sys.exit(1)
