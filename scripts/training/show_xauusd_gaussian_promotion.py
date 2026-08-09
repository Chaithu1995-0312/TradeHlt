#!/usr/bin/env python3
"""
show_xauusd_gaussian_promotion.py
=================================
Read gaussian_registry.json (+ optional train journal / LATEST manifest) and
print whether the XAUUSD Gaussian NB is promoted/active.

Usage:
  python scripts/training/show_xauusd_gaussian_promotion.py
  python scripts/training/show_xauusd_gaussian_promotion.py --version xauusd_nb_20260722T194904Z
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser(description="Show XAUUSD Gaussian promotion status")
    ap.add_argument(
        "--version",
        default=None,
        help="Registry version key (default: __active__['XAUUSD'] or primary train version)",
    )
    ap.add_argument(
        "--registry",
        default="models/gaussian_registry.json",
        help="Path to gaussian_registry.json",
    )
    args = ap.parse_args()

    reg_path = ROOT / args.registry
    if not reg_path.exists():
        print(f"ERROR: registry not found: {reg_path}")
        return 2

    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    active_map = reg.get("__active__") or {}
    if not isinstance(active_map, dict):
        active_map = {}

    version = args.version or active_map.get("XAUUSD")
    if not version:
        # fall back to any XAUUSD entry with active=true
        for k, v in reg.items():
            if k == "__active__" or not isinstance(v, dict):
                continue
            if v.get("instrument") == "XAUUSD" and v.get("active"):
                version = k
                break
    if not version:
        print("Promoted: No")
        print("detail: no XAUUSD active pointer and no active XAUUSD entry")
        return 1

    entry = reg.get(version)
    if not isinstance(entry, dict):
        print("Promoted: No")
        print(f"detail: version {version!r} not in registry")
        return 1

    pointer_ok = active_map.get("XAUUSD") == version
    entry_active = bool(entry.get("active"))
    model_file = entry.get("model_file")
    model_exists = False
    if model_file:
        mf = Path(str(model_file).replace("\\", "/"))
        if not mf.is_absolute():
            mf = ROOT / mf
        model_exists = mf.exists()

    promoted = pointer_ok and entry_active and model_exists

    # Optional LATEST manifest
    latest = ROOT / "results" / "gaussian_xauusd_train" / "LATEST.json"
    latest_promoted = None
    if latest.exists():
        try:
            m = json.loads(latest.read_text(encoding="utf-8"))
            latest_promoted = (m.get("artifact") or {}).get("promoted")
        except Exception:
            latest_promoted = None

    # Optional journal presence (primary tracked run)
    journal = (
        ROOT
        / "results"
        / "gaussian_xauusd_train"
        / "gaussian_xauusd_train_20260722T194904Z"
        / "bar_semantic_journal.jsonl"
    )
    journal_lines = 0
    if journal.exists():
        with journal.open("rb") as f:
            journal_lines = sum(1 for _ in f)

    print("=" * 60)
    print(f"Promoted: {'Yes' if promoted else 'No'}")
    print("=" * 60)
    print(f"version:              {version}")
    print(f"instrument:           {entry.get('instrument')}")
    print(f"registry entry.active:{entry_active}")
    print(f"__active__['XAUUSD']: {active_map.get('XAUUSD')}")
    print(f"pointer_matches:      {pointer_ok}")
    print(f"model_file:           {model_file}")
    print(f"model_exists:         {model_exists}")
    print(f"corr_expected_rr:     {(entry.get('metrics') or {}).get('corr_expected_rr')}")
    print(f"n_train:              {(entry.get('metrics') or {}).get('n_train')}")
    print(f"LATEST.artifact.promoted: {latest_promoted}")
    print(f"bar_semantic_journal: {journal if journal.exists() else 'missing'}")
    if journal.exists():
        print(f"journal_lines:        {journal_lines}")
    print("=" * 60)

    # Machine-readable one-liner for scripts
    print(json.dumps({"Promoted": "Yes" if promoted else "No", "version": version}))
    return 0 if promoted else 1


if __name__ == "__main__":
    raise SystemExit(main())
