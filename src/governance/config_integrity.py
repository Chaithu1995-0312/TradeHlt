"""
config_integrity.py — governance guards for production-config lineage.

Catches the two failure classes the `v2_multi_2026_04 - deepdeektry` incident
exposed (see docs/analysis intelligence-artifact / lineage notes):

  1. **Stale validation evidence** — a config's `validation_summary` describes
     *different* params than the config currently carries. The existing
     `config_hash` check does NOT catch this (it only hashes params↔themselves),
     so a hand-edited config keeps a self-consistent hash while its validation
     record silently describes the old params.
  2. **Ungoverned active config** — `ACTIVE_VERSION` points at a version with no
     `PROMOTED` entry in `promotion_log.jsonl` (it bypassed the governance gate),
     and/or a non-clean version key (spaces / ad-hoc suffixes).

Pure functions + a CLI audit. No side effects. Designed so the freshness anchor
(`validation_summary.params_fingerprint`) is written at validation time by the
promotion path and re-checked on every load/audit.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def params_fingerprint(params: dict) -> str:
    """SHA-256 of params (sort_keys) — same scheme as the config_hash, reused as
    the freshness anchor embedded in validation_summary."""
    return hashlib.sha256(json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()


def validation_summary_is_fresh(config: dict) -> bool:
    """True iff `config.validation_summary` corresponds to `config.params`.

    Anchored on `validation_summary.params_fingerprint == sha256(params)`. A
    config whose params were edited after validation (stale summary, or no
    fingerprint at all) returns False.
    """
    vs = config.get("validation_summary")
    params = config.get("params")
    if not isinstance(vs, dict) or not isinstance(params, dict):
        return False
    fp = vs.get("params_fingerprint")
    return bool(fp) and fp == params_fingerprint(params)


def active_version_is_governed(
    registry_dir: "str | Path",
    log_path: "str | Path | None" = None,
) -> tuple[bool, str]:
    """True iff ACTIVE_VERSION names a clean version key that has a PROMOTED
    entry in the promotion log. Returns (ok, human_reason)."""
    registry_dir = Path(registry_dir)
    active_file = registry_dir / "ACTIVE_VERSION"
    if not active_file.exists():
        return False, "no ACTIVE_VERSION pointer"
    active = active_file.read_text(encoding="utf-8").strip()
    if not active:
        return False, "empty ACTIVE_VERSION"
    if " " in active:
        return False, f"ACTIVE_VERSION '{active}' is not a clean key (contains spaces)"
    log_path = Path(log_path) if log_path else registry_dir / "promotion_log.jsonl"
    if not log_path.exists():
        return False, "no promotion_log.jsonl"
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("event") == "PROMOTED" and rec.get("version") == active:
            return True, f"governed: PROMOTED entry found for '{active}'"
    return False, f"ungoverned: no PROMOTED entry for ACTIVE version '{active}'"


def audit(registry_dir: "str | Path") -> dict:
    """Run both guards against a registry dir; returns a structured report."""
    registry_dir = Path(registry_dir)
    gov_ok, gov_reason = active_version_is_governed(registry_dir)
    out: dict = {"active_governed": {"ok": gov_ok, "reason": gov_reason}, "validation_freshness": {}}
    active_file = registry_dir / "ACTIVE_VERSION"
    if active_file.exists():
        active = active_file.read_text(encoding="utf-8").strip()
        apath = registry_dir / f"{active}.json"
        if apath.exists():
            try:
                cfg = json.load(open(apath, encoding="utf-8"))
                fresh = validation_summary_is_fresh(cfg)
                out["validation_freshness"] = {"version": active, "fresh": fresh}
            except Exception as e:
                out["validation_freshness"] = {"version": active, "error": str(e)}
    return out


if __name__ == "__main__":
    import sys
    rd = sys.argv[1] if len(sys.argv) > 1 else "configs/production"
    rep = audit(rd)
    print(json.dumps(rep, indent=2))
    sys.exit(0 if rep["active_governed"]["ok"] and rep.get("validation_freshness", {}).get("fresh") else 1)
