"""run_manifest.py — provenance manifest for research/tool runs (ERP testing-plan §3.3).

The anti-hallucination spine (H1/H2/H3): every run that produces an economic or market claim writes
a machine-readable manifest of HOW it was produced, plus assertions and a content hash, under
    results/test_runs/<run_id>/   (or any run_dir a producer chooses)
        run_manifest.json   assertions.json   RUN_SHA256.txt

`build_manifest` is FAIL-CLOSED: a missing required field raises — a claim without provenance cannot
be constructed. Importable by producers (scripts/src) AND tests; no test-only dependencies.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# §3.3 minimum manifest fields — the full provenance contract.
REQUIRED_FIELDS: tuple[str, ...] = (
    "run_id", "timestamp_utc",
    "command", "argv", "cwd",
    "git_sha", "branch",
    "ACTIVE_VERSION", "config_hash",
    "validation_lens", "exit_model", "cost_model_bps", "label_source",
    "instruments", "timeframe", "data_source",
    "network", "dry_run",
    "intended_work_item_id", "validation_flow_review",
)

# Fields the caller MUST supply (the rest are auto-filled / defaulted).
_CALLER_REQUIRED: tuple[str, ...] = (
    "command", "argv", "validation_lens", "exit_model", "cost_model_bps",
    "label_source", "instruments", "timeframe", "data_source",
    "intended_work_item_id",
)

_MANIFEST_NAME = "run_manifest.json"
_ASSERTIONS_NAME = "assertions.json"
_HASH_NAME = "RUN_SHA256.txt"


class ManifestFieldError(ValueError):
    """A required manifest field is missing — fail-closed, never a silent default."""


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001 — provenance best-effort; never blocks a run
        return "unknown"


def active_version_and_hash() -> tuple[str, str]:
    """(ACTIVE_VERSION, config_hash) via optional import — fail-open to ('unknown','unknown').

    Used so fixture/synthetic runs need no live production config to build a manifest."""
    try:
        from config_layer.production_config import get_active_version  # optional
        version = get_active_version()
    except Exception:  # noqa: BLE001
        return "unknown", "unknown"
    try:
        cfg_path = Path("configs/production") / f"{version}.json"
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        return version, str(data.get("config_hash", "unknown"))
    except Exception:  # noqa: BLE001
        return version, "unknown"


def build_manifest(**fields: Any) -> dict[str, Any]:
    """Build a fully-populated manifest. Raises ManifestFieldError if any required field is absent.

    Auto-fills run_id/timestamp_utc/cwd/git_sha/branch and ACTIVE_VERSION/config_hash (unless the
    caller overrides). Defaults: validation_flow_review='UNTRUSTED_RAW', dry_run=True, network='none'.
    """
    version, cfg_hash = active_version_and_hash()
    manifest: dict[str, Any] = {
        "run_id": fields.pop("run_id", None) or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-" + uuid.uuid4().hex[:8],
        "timestamp_utc": fields.pop("timestamp_utc", None) or datetime.now(timezone.utc).isoformat(),
        "cwd": fields.pop("cwd", None) or str(Path.cwd()),
        "git_sha": fields.pop("git_sha", None) or _git("rev-parse", "HEAD"),
        "branch": fields.pop("branch", None) or _git("rev-parse", "--abbrev-ref", "HEAD"),
        "ACTIVE_VERSION": fields.pop("ACTIVE_VERSION", None) or version,
        "config_hash": fields.pop("config_hash", None) or cfg_hash,
        "network": fields.pop("network", "none"),
        "dry_run": fields.pop("dry_run", True),
        "validation_flow_review": fields.pop("validation_flow_review", "UNTRUSTED_RAW"),
    }
    manifest.update(fields)

    missing = [f for f in REQUIRED_FIELDS if f not in manifest or manifest[f] is None]
    if missing:
        raise ManifestFieldError(
            f"run_manifest missing required field(s): {missing} — a claim without provenance "
            f"cannot be built (anti-H1)."
        )
    return manifest


def run_sha256(manifest: dict[str, Any], assertions: dict[str, Any]) -> str:
    """Content hash of the run = sha256 of canonical JSON of {manifest, assertions}."""
    canonical = json.dumps({"manifest": manifest, "assertions": assertions}, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_run(run_dir: Path | str, manifest: dict[str, Any],
              assertions: dict[str, Any]) -> dict[str, str]:
    """Write run_manifest.json + assertions.json + RUN_SHA256.txt. Returns the written paths."""
    d = Path(run_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / _MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    (d / _ASSERTIONS_NAME).write_text(json.dumps(assertions, indent=2, sort_keys=True), encoding="utf-8")
    digest = run_sha256(manifest, assertions)
    (d / _HASH_NAME).write_text(digest + "\n", encoding="utf-8")
    return {"manifest": str(d / _MANIFEST_NAME), "assertions": str(d / _ASSERTIONS_NAME),
            "hash": str(d / _HASH_NAME), "sha256": digest}


def read_run(run_dir: Path | str) -> dict[str, Any]:
    """Read back {manifest, assertions, sha256, hash_ok}. Raises FileNotFoundError if no manifest."""
    d = Path(run_dir)
    mpath = d / _MANIFEST_NAME
    if not mpath.exists():
        raise FileNotFoundError(f"no {_MANIFEST_NAME} in {d}")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    assertions = json.loads((d / _ASSERTIONS_NAME).read_text(encoding="utf-8"))
    stored = (d / _HASH_NAME).read_text(encoding="utf-8").strip() if (d / _HASH_NAME).exists() else ""
    computed = run_sha256(manifest, assertions)
    return {"manifest": manifest, "assertions": assertions, "sha256": computed,
            "hash_ok": stored == computed}
