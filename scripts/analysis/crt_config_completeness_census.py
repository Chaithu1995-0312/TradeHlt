"""
crt_config_completeness_census.py
==================================
READ-ONLY: applies the Phase C completeness check
(src/config_layer/crt_config_completeness.py) to every file under
configs/production/*.json, not just the active one.

Why
    Phase C's completeness primitive is proven against the single active config. Before anyone
    considers wiring it into the shared production loader as a hard raise, the blast radius
    needs to be measured, not guessed. This script is that measurement: which of the 24 (as of
    2026-08-31) production config files would fail today, and how badly. Mutates nothing; reads
    JSON files only.

`regime_map.json` is a known non-CRTConfig file (zero params, zero crt_engine keys by design --
a different config shape) and is reported as SKIPPED, not FAIL, so it does not pollute the count.

Usage
    python scripts/analysis/crt_config_completeness_census.py            # prints + writes JSON
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from config_layer.crt_config_completeness import (  # noqa: E402
    missing_externally_owned_fields,
    missing_nonscalar_fields,
    missing_scalar_fields,
)

OUT_JSON = ROOT / "data" / "crt_config_completeness_census.json"

#: Files with zero params AND zero crt_engine keys are a structurally different config shape
#: (e.g. regime_map.json), not an incomplete CRTConfig-shaped one -- reported SKIPPED.
_SKIP_IF_BOTH_EMPTY = True


def build_census() -> dict:
    prod_dir = ROOT / "configs" / "production"
    results = []
    for path in sorted(prod_dir.glob("*.json")):
        if path.name == "config_hash":
            continue
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            results.append({"file": path.name, "status": "UNREADABLE", "error": str(exc)})
            continue
        if not isinstance(cfg, dict):
            results.append({"file": path.name, "status": "NOT_A_CRT_CONFIG_SHAPE"})
            continue
        crt_engine = cfg.get("crt_engine", {})
        params = cfg.get("params", {})
        engine_runner = cfg.get("engine_runner", {})
        if _SKIP_IF_BOTH_EMPTY and not crt_engine and not params:
            results.append({"file": path.name, "status": "SKIPPED_NOT_CRT_SHAPED"})
            continue

        missing_scalar = sorted(missing_scalar_fields(crt_engine, params))
        missing_nonscalar = sorted(missing_nonscalar_fields(crt_engine))
        missing_external = sorted(missing_externally_owned_fields(engine_runner))
        total_missing = len(missing_scalar) + len(missing_external)
        results.append({
            "file": path.name,
            "status": "COMPLETE" if not (missing_scalar or missing_nonscalar or missing_external)
                      else "INCOMPLETE",
            "crt_engine_count": len(crt_engine),
            "params_count": len(params),
            "missing_scalar_count": total_missing,
            "missing_scalar_fields": missing_scalar,
            "missing_nonscalar_fields": missing_nonscalar,
            "missing_externally_owned_fields": missing_external,
        })

    n_complete = sum(1 for r in results if r["status"] == "COMPLETE")
    n_incomplete = sum(1 for r in results if r["status"] == "INCOMPLETE")
    n_skipped = sum(1 for r in results if r["status"] not in ("COMPLETE", "INCOMPLETE"))
    return {
        "total_files": len(results),
        "complete": n_complete,
        "incomplete": n_incomplete,
        "skipped_or_unreadable": n_skipped,
        "results": results,
    }


def main() -> int:
    report = build_census()
    print(f"total files            : {report['total_files']}")
    print(f"COMPLETE (47/47)        : {report['complete']}")
    print(f"INCOMPLETE              : {report['incomplete']}")
    print(f"skipped / unreadable    : {report['skipped_or_unreadable']}")
    print()
    header = f"{'file':56s} {'engine':>7s} {'params':>7s} {'missing':>8s}  status"
    print(header)
    print("-" * len(header))
    for r in report["results"]:
        if r["status"] in ("COMPLETE", "INCOMPLETE"):
            print(f"{r['file']:56s} {r['crt_engine_count']:>7d} {r['params_count']:>7d} "
                  f"{r['missing_scalar_count']:>8d}  {r['status']}")
        else:
            print(f"{r['file']:56s} {'--':>7s} {'--':>7s} {'--':>8s}  {r['status']}")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
