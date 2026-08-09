"""
baseline_capture.py
Capture a reproducible baseline manifest for the current repository state.

Output:
  results/baseline/<timestamp>_<label>/manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# REPO_ROOT is the actual repository root (D:\Tradelatest) — distinct from ROOT_DIR
# (src/, needed above so `from utils...`/`from features...` resolve). Fixing this
# split is Phase 0 in scope: `build_manifest` used to receive ROOT_DIR as `root` and
# resolve `configs/production/...`, `models/...` against src/configs, src/models —
# neither exists, so `config_sha256` silently returned None and `registry_entries`
# silently returned 0 for as long as this script has existed. Nothing raised because
# `_sha256_file`/`_count_entries` treat a missing path as "not present" rather than
# an error — the exact "results are not stack-pinned" symptom this phase exists to fix.
REPO_ROOT = ROOT_DIR.parent

from utils.console_safe import safe_print
from features.feature_schema import (
    CANONICAL_FEATURE_DIM,
    CANONICAL_FEATURES,
    SCHEMA_HASH,
    SCHEMA_VERSION,
)
from core.model_registry import get_active, get_active_gaussian
from config_layer.production_config import PROD_VERSION, get_prod_metadata
from config_layer.production_bundle import load_production_bundle
from config_layer.stack_version import StackVersionError, compute_stack_version


def _sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _count_entries(path: Path) -> int:
    data = _read_json(path)
    if isinstance(data, dict):
        return len(data)
    return 0


def build_manifest(root: Path, label: str) -> dict[str, Any]:
    models_dir = root / "models"
    prod_cfg_path = root / "configs/production" / f"{PROD_VERSION}.json"

    timestamp_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    production_meta: dict[str, Any] | None
    try:
        production_meta = get_prod_metadata()
    except Exception as exc:  # Defensive: baseline capture should still complete.
        production_meta = {"_error": str(exc)}

    # ── Research Provenance Spine Phase 0 (config_layer/stack_version.py) ──────
    # `load_production_bundle()` reconciles Selected (registry __active__) vs
    # Enabled (WHO identity + HOW config flags) across ALL 6 model families — this
    # replaces the previous 2-family get_active()/get_active_gaussian() view and,
    # critically, hashes each family's ACTUAL resolved artifact_path rather than a
    # hand-picked filename. That fixes a real bug: this module used to hash
    # `models/zone_registry.json` (the v3 rollback artifact) unconditionally, while
    # the active config's `zone_registry_path` has pointed at
    # `models/zone_registry_v4_2026_07.json` since promotion — so the old
    # `zone_registry_json_sha256` field pinned a file that was NOT what loaded.
    families: dict[str, Any] = {}
    bundle_divergences: tuple[str, ...] = ()
    try:
        bundle = load_production_bundle(repo_root=root, active_version=PROD_VERSION)
        bundle_divergences = bundle.divergences
        for family, member in bundle.members.items():
            families[family] = {
                "selected_version": member.selected_version,
                "artifact_path": (
                    str(member.artifact_path) if member.artifact_path else None
                ),
                "artifact_sha256": (
                    _sha256_file(member.artifact_path) if member.artifact_path else None
                ),
                "execution_status": member.execution_status,
                "executes_checkpoint": member.executes_checkpoint,
                "contested": member.contested,
            }
    except Exception as exc:  # Defensive: baseline capture should still complete.
        families = {"_error": str(exc)}

    stack_version: dict[str, Any]
    try:
        sv = compute_stack_version(repo_root=root, active_version=PROD_VERSION)
        stack_version = {
            "behavior_hash": sv.behavior_hash,
            "provenance_hash": sv.provenance_hash,
            "executing_families": list(sv.executing_families),
            "divergences": list(sv.divergences),
            "git_sha_reliable": sv.meta.get("git_sha_reliable"),
        }
    except StackVersionError as exc:
        stack_version = {"_error": str(exc)}

    return {
        "captured_at_utc": timestamp_utc,
        "label": label,
        "root": str(root.resolve()),
        "schema": {
            "schema_version": SCHEMA_VERSION,
            "schema_hash": SCHEMA_HASH,
            "feature_dim": CANONICAL_FEATURE_DIM,
            "feature_count": len(CANONICAL_FEATURES),
        },
        "production": {
            "version": PROD_VERSION,
            "config_path": str(prod_cfg_path),
            "config_sha256": _sha256_file(prod_cfg_path),
            "metadata": production_meta,
            "validation_final_score": (
                (production_meta or {}).get("validation_summary", {}).get("final_score")
                if isinstance(production_meta, dict)
                else None
            ),
        },
        "models": {
            # Retained for back-compat with any existing consumer of this shape —
            # both are a strict subset of `families` below, which is now authoritative.
            "active_main_model": get_active(),
            "active_gaussian_model": get_active_gaussian(),
            "registry_entries": _count_entries(models_dir / "registry.json"),
            "gaussian_registry_entries": _count_entries(models_dir / "gaussian_registry.json"),
            # All 6 families (zone_gate/rr/rr_fusion/gaussian/bitnet/tradenet), each
            # hashed at its BUNDLE-RESOLVED artifact path — not a hardcoded filename.
            "families": families,
            "bundle_divergences": list(bundle_divergences),
        },
        "stack_version": stack_version,
    }


def _safe_label(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text.strip())
    return cleaned or "baseline"


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture baseline manifest for current repo state.")
    parser.add_argument("--label", default="phase0", help="Short tag included in output directory.")
    parser.add_argument(
        "--output-dir",
        default="results/baseline",
        help="Base directory for captured baseline bundle.",
    )
    args = parser.parse_args()

    root = REPO_ROOT
    label = _safe_label(args.label)
    manifest = build_manifest(root=root, label=label)

    run_id = f"{manifest['captured_at_utc']}_{label}"
    out_dir = (root / args.output_dir / run_id).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")
    safe_print(f"[baseline_capture] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
