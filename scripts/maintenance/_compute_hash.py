"""_compute_hash.py — recompute (and verify) a production config's `params` hash.

CLAUDE.md Section 3.1 step 4 and docs/reference/example-service.py both cite the bare invocation
`python scripts/maintenance/_compute_hash.py` as THE rehash step after editing a config's `params`
block. Before this rewrite (2026-08-31, Phase G / CH-crt-sot-2026-08-31) that instruction was
FALSE: the script computed a hash over a hardcoded, stale params dict
(`retest_depth_max: 0.30` -- matching no live config; code default is 0.25, resolved production
value 0.15) and read no file at all. Rewritten to actually do what the doc says: resolve
ACTIVE_VERSION (or an explicit `--version`) and hash ITS `params`.

Delegates to `config_layer.production_config._compute_params_hash` rather than
re-implementing SHA-256-over-sorted-JSON a second time -- so this script and the loader's
`_verify_config_hash` (which every `load_prod_config_from_registry` call runs) can never silently
disagree on the algorithm. Reads with `encoding="utf-8"` -- production configs carry
box-drawing/math glyphs in comments that break Windows' cp1252 default (the same trap hit
repeatedly elsewhere this session, including PromotionManager._load_full_base_config).

Backward-compat note: scripts/groq_bridge/ingest_response.py invokes this script as a
no-argument subprocess and checks ONLY `returncode == 0` (it discards stdout entirely -- a
separate, pre-existing, out-of-scope decorative-call pattern in that unrelated subsystem,
targeting a different config, v1_multi_2026_03.json). This rewrite preserves exit 0 on success
and does not change that caller.

Usage
    python scripts/maintenance/_compute_hash.py                  # ACTIVE_VERSION, verify + print
    python scripts/maintenance/_compute_hash.py --version v4_x   # a specific config
    python scripts/maintenance/_compute_hash.py --write          # write the computed hash into
                                                                  # the config's config_hash field
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config_layer.production_config import _compute_params_hash  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--version", default=None,
        help="config version to hash (default: whatever ACTIVE_VERSION names)",
    )
    ap.add_argument(
        "--write", action="store_true",
        help="write the computed hash into the config file's config_hash field "
             "(default: print-only, never mutates)",
    )
    args = ap.parse_args()

    version = args.version
    if version is None:
        version = (ROOT / "configs" / "production" / "ACTIVE_VERSION").read_text(
            encoding="utf-8"
        ).strip()

    cfg_path = ROOT / "configs" / "production" / f"{version}.json"
    if not cfg_path.exists():
        print(f"ERROR: no such config: {cfg_path}", file=sys.stderr)
        return 1

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    params = cfg.get("params", {})
    if not params:
        print(f"ERROR: {cfg_path.name} has no (or empty) 'params' -- refusing to hash "
              "an empty dict silently.", file=sys.stderr)
        return 1

    computed = _compute_params_hash(params)
    stored = cfg.get("config_hash")

    print(f"version      : {version}")
    print(f"params keys  : {len(params)}")
    print(f"computed hash: {computed}")
    print(f"stored hash  : {stored!r}")
    print(f"match        : {'YES' if computed == stored else 'NO -- config_hash is stale/wrong'}")

    if args.write:
        cfg["config_hash"] = computed
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote config_hash into {cfg_path.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
