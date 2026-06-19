"""
manifest_builder — per-partition `manifest.json` with full provenance.

sha256 is computed over the records sorted by `episode_id` then serialized with
`sort_keys=True`, so re-running on the same input yields a byte-stable digest
(determinism gate). The provenance block (`source_history_window`, `engine_registry_hash`,
`rebuild_id`, `generated_by`, `python_version`, `timestamp_utc`) makes any artifact
traceable to the exact code + history range that built it.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import platform
from pathlib import Path
from typing import Sequence

from ..registry.engine_registry import engine_versions, registry_hash

MANIFEST_SCHEMA_VERSION = "1.0"

_DEDUP_KEY = "episode_id"


def records_sha256(records: Sequence[dict]) -> str:
    """Deterministic digest of a record set (order-independent via episode_id sort)."""
    ordered = sorted(records, key=lambda r: str(r.get(_DEDUP_KEY, "")))
    canonical = json.dumps(ordered, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_manifest(
    records: Sequence[dict],
    *,
    schema_version: str,
    source_history_window: "dict | None" = None,
    rebuild_id: str = "",
    generated_by: str = "",
) -> dict:
    """Assemble the manifest dict (does not write it)."""
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "records": len(records),
        "sha256": records_sha256(records),
        "schema_version": schema_version,
        "engine_versions": engine_versions(),
        "engine_registry_hash": registry_hash(),
        "source_history_window": source_history_window or {"from": None, "to": None},
        "rebuild_id": rebuild_id,
        "generated_by": generated_by,
        "python_version": platform.python_version(),
        "timestamp_utc": _dt.datetime.now(_dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    }


def write_manifest(manifest: dict, partition_dir: "Path | str") -> Path:
    """Write `manifest.json` next to the partition's data file."""
    p = Path(partition_dir)
    p.mkdir(parents=True, exist_ok=True)
    out = p / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return out
