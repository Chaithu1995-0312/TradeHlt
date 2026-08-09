"""F-041A invariant — the zone_gate_registry.json manifest's ACTIVE entry must point at the same
file the runtime config actually loads (sha256 equality). Machine-enforces the drift class that
produced F-041 (manifest active=aade29c4 vs config-loaded e73e0893), so it can never silently recur.

Red before the B1 reconciliation (register+promote the converted runtime file); green after.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "models" / "zone_gate_registry.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _config_loaded_zone_path() -> Path:
    """The path the runtime scores through: engine_runner.zone_registry_path of ACTIVE_VERSION."""
    version = (ROOT / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    cfg = json.loads((ROOT / "configs" / "production" / f"{version}.json").read_text(encoding="utf-8"))
    rel = cfg["engine_runner"]["zone_registry_path"]
    return ROOT / rel


def _active_manifest_model_file() -> Path:
    reg = json.loads(MANIFEST.read_text(encoding="utf-8"))
    active = [e for e in reg.values() if e.get("active")]
    assert len(active) == 1, f"expected exactly one active zone-gate version, got {len(active)}"
    rel = active[0]["model_file"].replace("\\", "/")   # manifest stores Windows-style paths
    return ROOT / rel


def test_active_zone_manifest_matches_runtime():
    runtime = _config_loaded_zone_path()
    manifest = _active_manifest_model_file()
    assert runtime.exists(), f"config-loaded zone file missing: {runtime}"
    assert manifest.exists(), f"manifest active model_file missing: {manifest}"
    rt_sha, mf_sha = _sha256(runtime), _sha256(manifest)
    assert rt_sha == mf_sha, (
        "F-041A drift: zone_gate_registry.json active entry does not match the runtime-loaded file.\n"
        f"  runtime  (config engine_runner.zone_registry_path): {runtime}  sha={rt_sha[:16]}\n"
        f"  manifest (active model_file):                        {manifest} sha={mf_sha[:16]}\n"
        "Fix: register+promote the runtime file (B1) so manifest.active == config-loaded path."
    )
