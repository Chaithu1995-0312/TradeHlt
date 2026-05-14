#!/usr/bin/env python
"""
Update or verify the 'config_hash' field in a production config JSON file.

Usage:
    python scripts/update_config_hash.py <config_file>          # update hash
    python scripts/update_config_hash.py <config_file> --check  # verify only
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

def compute_hash(config_path: Path) -> tuple[str, dict]:
    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)
    params = data.get("params", {})
    canonical = json.dumps(params, sort_keys=True)
    new_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return new_hash, data

def update_hash(config_path: Path, dry_run: bool = False) -> bool:
    new_hash, data = compute_hash(config_path)
    old_hash = data.get("config_hash")
    if old_hash == new_hash:
        print(f"✅ Hash already correct: {new_hash}")
        return True
    if dry_run:
        print(f"Would update from {old_hash} to {new_hash}")
        return False
    data["config_hash"] = new_hash
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Hash updated from {old_hash} to {new_hash}")
    return True

def check_hash(config_path: Path) -> bool:
    new_hash, data = compute_hash(config_path)
    old_hash = data.get("config_hash")
    if old_hash == new_hash:
        print(f"✅ Hash matches: {old_hash}")
        return True
    print(f"❌ Hash mismatch: stored={old_hash}, computed={new_hash}")
    return False

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("config_file", help="Path to config JSON")
    ap.add_argument("--check", action="store_true", help="Only verify, do not update")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be updated")
    args = ap.parse_args()
    path = Path(args.config_file)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)
    if args.check:
        ok = check_hash(path)
    else:
        ok = update_hash(path, dry_run=args.dry_run)
    sys.exit(0 if ok else 1)