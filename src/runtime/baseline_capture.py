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

from utils.console_safe import safe_print
from features.feature_schema import (
    CANONICAL_FEATURE_DIM,
    CANONICAL_FEATURES,
    SCHEMA_HASH,
    SCHEMA_VERSION,
)
from core.model_registry import get_active, get_active_gaussian
from config_layer.production_config import PROD_VERSION, get_prod_metadata


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
            "active_main_model": get_active(),
            "active_gaussian_model": get_active_gaussian(),
            "registry_entries": _count_entries(models_dir / "registry.json"),
            "gaussian_registry_entries": _count_entries(models_dir / "gaussian_registry.json"),
            "artifacts": {
                "registry_json_sha256": _sha256_file(models_dir / "registry.json"),
                "gaussian_registry_json_sha256": _sha256_file(models_dir / "gaussian_registry.json"),
                "zone_registry_json_sha256": _sha256_file(models_dir / "zone_registry.json"),
            },
        },
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

    root = ROOT_DIR
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
