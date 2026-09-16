"""remap_registries_v6.py — relabel stored `feature_order` names, schema v5.0 -> v6.0.

WHY A SCRIPT AND NOT A HAND-EDIT
--------------------------------
Same reason as `remap_zone_registry_v4.py` (its direct precedent): these files carry trained
vectors whose alignment is positional, and the freeze pin forbids hand-editing vector data. This
script is the provenance record of HOW the v6 relabel was produced: run it, diff its output, keep
it.

WHAT IT DOES (and what it does NOT)
-----------------------------------
Renames two names wherever they appear inside a `feature_order` list, at any nesting depth:

    trend_strength       -> trend_strength_z        pure relabel: the stored statistics were always
                                                    the z-scored distribution, because <=v5.0's
                                                    compute_normalization overwrote trend_strength
                                                    in place. The trained numbers describe
                                                    trend_strength_z exactly.
    candles_since_retest -> candles_since_sweep     pure relabel: the pipeline column always counted
                                                    bars since the last liquidity sweep.

NOTHING else is touched: no weight, no mu, no sigma, no ordering, no zone geometry. The script
asserts that afterwards. This is an ALIGNMENT_REMAP, not a retrain (CLAUDE.md 6.5): it grants no
authority and does not clean any artifact's PIT status.

PRE-EXISTING STALENESS, DELIBERATELY NOT FIXED
----------------------------------------------
`models/zone_registry.json` also names `wick_size` and `macd_hist` -- v3.0 names that schema v4.0
renamed in 2026-07 and that are ALREADY absent from the live schema, independently of this program.
That is the SCHEMA-V4-VECTOR-MIGRATION residue (its remapped output is the separate artifact
`zone_registry_v4_2026_07.json`). Fixing it here would be adjacent, unauthorized work, so this
script reports it and leaves it. Consequence: after this remap, zone_registry_v4_2026_07.json
names only live features, while zone_registry.json still names two dead ones.

USAGE
-----
    venv/Scripts/python.exe scripts/governance/remap_registries_v6.py           # rewrite in place
    venv/Scripts/python.exe scripts/governance/remap_registries_v6.py --check   # verify, write nothing
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))

RENAMES = {
    "trend_strength": "trend_strength_z",
    "candles_since_retest": "candles_since_sweep",
}

TARGETS = [
    _ROOT / "models" / "zone_registry.json",
    _ROOT / "models" / "zone_registry_v4_2026_07.json",
    _ROOT / "models" / "zone_gate_registry.json",
    _ROOT / "models" / "gaussian_registry.json",
]

PROGRAM_ID = "SCHEMA-V6-NORMALIZATION-IDENTITY-FIX"
CHANGE_ID = "CH-schema-v6-normalization-identity"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


NAME_LIST_KEYS = ("feature_order", "feature_schema")


def _remap(node, counter: dict) -> object:
    """Recursively relabel strings inside any feature-name list. Everything else is copied.

    Two keys carry ordered feature-name lists: `feature_order` (zone/zone-gate registries) and
    `feature_schema` (gaussian registry). Both are positional, so only the LABELS move.
    """
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key in NAME_LIST_KEYS and isinstance(value, list):
                relabelled = []
                for name in value:
                    if isinstance(name, str) and name in RENAMES:
                        counter[name] = counter.get(name, 0) + 1
                        relabelled.append(RENAMES[name])
                    else:
                        relabelled.append(name)
                out[key] = relabelled
            else:
                out[key] = _remap(value, counter)
        return out
    if isinstance(node, list):
        return [_remap(item, counter) for item in node]
    return node


def _strip_feature_order(node) -> object:
    """Copy of the tree with every feature-name list removed — used to prove nothing else moved."""
    if isinstance(node, dict):
        return {k: _strip_feature_order(v) for k, v in node.items() if k not in NAME_LIST_KEYS}
    if isinstance(node, list):
        return [_strip_feature_order(i) for i in node]
    return node


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Relabel stored feature_order names for schema v6.0.")
    ap.add_argument("--check", action="store_true", help="verify only; write nothing")
    args = ap.parse_args(argv)

    from features.feature_schema import CANONICAL_FEATURE_ORDER

    live = set(CANONICAL_FEATURE_ORDER)
    exit_code = 0

    for path in TARGETS:
        if not path.is_file():
            print(f"[skip] {path.relative_to(_ROOT)} — not present")
            continue

        original = path.read_text(encoding="utf-8")
        before_sha = _sha256_bytes(original.encode("utf-8"))
        data = json.loads(original)

        counter: dict = {}
        remapped = _remap(data, counter)

        # The whole claim of this remap: nothing outside feature_order changed.
        assert _strip_feature_order(data) == _strip_feature_order(remapped), (
            f"{path.name}: a value outside feature_order moved — aborting"
        )

        names: list[str] = []

        def _collect(node) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in NAME_LIST_KEYS and isinstance(value, list):
                        names.extend(n for n in value if isinstance(n, str))
                    else:
                        _collect(value)
            elif isinstance(node, list):
                for item in node:
                    _collect(item)

        _collect(remapped)
        still_missing = sorted({n for n in names if n not in live})

        rel = path.relative_to(_ROOT).as_posix()
        print(f"{rel}")
        print(f"  renamed        : {counter or '{} (already remapped)'}")
        print(f"  names absent from live schema AFTER remap: {still_missing or 'none'}")

        if args.check:
            continue

        if not counter:
            print("  [skip write] nothing to rename")
            continue

        payload = json.dumps(remapped, indent=2) + "\n"
        path.write_text(payload, encoding="utf-8")
        after_sha = _sha256_bytes(payload.encode("utf-8"))
        print(f"  [OK] rewritten  sha {before_sha[:16]} -> {after_sha[:16]}")

        prov_path = path.with_name(path.stem + ".provenance.json")
        prov = json.loads(prov_path.read_text(encoding="utf-8")) if prov_path.is_file() else {}
        history = prov.get("remap_history") or []
        history.append({
            "program_id": PROGRAM_ID,
            "change_id": CHANGE_ID,
            "generated_by": "scripts/governance/remap_registries_v6.py",
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "change_class": "ALIGNMENT_REMAP",
            "_change_class_note": "Pure relabel inside feature_order. NOT a retrain: no weight, mu, "
                                  "sigma, ordering or zone geometry changed — asserted by the script.",
            "renames": {k: v for k, v in RENAMES.items() if k in counter},
            "_renames_note": {
                "trend_strength->trend_strength_z": "The stored statistics always described the "
                                                    "z-scored distribution: <=v5.0's "
                                                    "compute_normalization overwrote trend_strength "
                                                    "in place, so the trained numbers are the "
                                                    "z-score's.",
                "candles_since_retest->candles_since_sweep": "The pipeline column always counted "
                                                             "bars since the last liquidity sweep "
                                                             "(FM-065).",
            },
            "sha256_before": before_sha,
            "sha256_after": after_sha,
            "names_absent_from_live_schema_after": still_missing,
            "_absent_note": "Pre-existing SCHEMA-V4-VECTOR-MIGRATION residue (wick_size/macd_hist), "
                            "untouched by this program by design.",
            "authority": "NONE — alignment repair only (CLAUDE.md 6.5). Does not revalidate the "
                         "model, does not clean PIT status, does not re-enable any gate.",
        })
        prov["remap_history"] = history
        prov.setdefault("artifact", rel)
        prov_path.write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
        print(f"  [OK] provenance {prov_path.relative_to(_ROOT).as_posix()}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
