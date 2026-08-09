#!/usr/bin/env python3
"""crt_config_construction_census.py — P1 OBSERVE static + optional live fingerprint.

Static: find ConfigBuilder.build / load_prod_config_from_registry / CRTConfig( call sites.
Live: three-way SCHEMA / ROUTER_BASE / PRODUCTION_MERGED fingerprints (F-057 demo).

Does not fail-closed. Protocol: docs/governance/CRT_CONFIG_CONSTRUCTION_PROTOCOL.md

Usage:
  PYTHONPATH=src python scripts/governance/crt_config_construction_census.py
  PYTHONPATH=src python scripts/governance/crt_config_construction_census.py --live-fingerprint
  PYTHONPATH=src python scripts/governance/crt_config_construction_census.py --json
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PATTERNS = (
    ("ConfigBuilder.build", "likely ROUTER_BASE unless followed by prod re-stamp"),
    ("load_prod_config_from_registry", "PRODUCTION_MERGED"),
    ("CRTConfig(", "SCHEMA or direct — app-forbidden outside builder/router"),
)


def _scan_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits: list[dict] = []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pat, note in PATTERNS:
            if pat in line:
                hits.append({
                    "path": str(path.relative_to(_ROOT)).replace("\\", "/"),
                    "line": i,
                    "pattern": pat,
                    "note": note,
                    "text": stripped[:160],
                })
    return hits


def static_census() -> dict:
    roots = [_ROOT / "src", _ROOT / "scripts", _ROOT / "tests"]
    hits: list[dict] = []
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            hits.extend(_scan_file(p))
    by_pat: dict[str, int] = {}
    for h in hits:
        by_pat[h["pattern"]] = by_pat.get(h["pattern"], 0) + 1
    return {
        "n_hits": len(hits),
        "by_pattern": by_pat,
        "hits": hits,
        "protocol": "docs/governance/CRT_CONFIG_CONSTRUCTION_PROTOCOL.md",
        "phase": "P1_OBSERVE",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CRT config construction census (P1 observe)")
    ap.add_argument("--live-fingerprint", action="store_true", help="three-way XAUUSD fingerprint")
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = static_census()
    if args.live_fingerprint:
        from config_layer.crt_config_provenance import compare_surfaces

        report["live_fingerprint"] = compare_surfaces(args.instrument)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print("=== CRT Config Construction Census (P1 OBSERVE) ===")
        print(f"hits={report['n_hits']} by_pattern={report['by_pattern']}")
        print("--- sample (first 40) ---")
        for h in report["hits"][:40]:
            print(f"  {h['path']}:{h['line']}  {h['pattern']}  | {h['text'][:80]}")
        if len(report["hits"]) > 40:
            print(f"  ... +{len(report['hits']) - 40} more")
        if "live_fingerprint" in report:
            lf = report["live_fingerprint"]
            print("--- live fingerprint ---")
            print(json.dumps(lf, indent=2))
            if lf.get("router_equals_prod"):
                print("NOTE: router_equals_prod True (unusual)")
            else:
                print("OK: ROUTER_BASE fingerprint ≠ PRODUCTION_MERGED (F-057 visible)")
        print(f"\nProtocol: {report['protocol']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
