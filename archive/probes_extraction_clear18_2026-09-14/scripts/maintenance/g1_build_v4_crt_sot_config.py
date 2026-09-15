"""g1_build_v4_crt_sot_config.py — Phase G1 of the CRT single-source-of-truth plan.

Hand-writes the new production config v4_crt_sot_2026_08.json via the v3 precedent
(configs/promotion_log.jsonl's v3_unified_market_structure_2026_09 REGISTERED entry), NOT via
PromotionManager -- G-BLOCK-3 (documented in the plan file) established that
PromotionManager._write_to_registry clones `_BASE_VERSION_FALLBACK` (v1_multi_2026_03, a March
baseline) and would drop 11 top-level sections + silently revert 10 more, including
crt_engine 45->29 keys -- losing 16 of the very knobs this whole plan exists to declare.
_promote_v4_bnb_cutover.py already documented this exact same defect independently, for a
different config, confirming it is not a one-off.

WHAT THIS SCRIPT DOES
    1. Deep-clones the ACTIVE config (v2_htfcrt_2026_08.json) -- preserves all 21 top-level
       sections, not the 9-key PromotionManager metadata subset.
    2. Overwrites `params` with the 47-field declaration Phase B already proved byte-identical
       (reuses crt_declare_all_knobs_parity.build_declared_params -- not re-derived a third time).
    3. Recomputes `config_hash` via config_layer.production_config._compute_params_hash (the
       same function _compute_hash.py now delegates to, so the two can never disagree).
    4. Updates version/config_id/created_at/notes. Does NOT touch ACTIVE_VERSION.

WHAT THIS SCRIPT DOES NOT DO
    Does not run ConfigValidator (G-BLOCK-2: XAUUSD's ~4 trades cannot clear the 10-trade hard
    gate -- see the plan). Does not call PromotionManager. Does not write to promotion_log.jsonl
    (that is Phase G3, a separate, explicitly-gated step, done only after G2's parity proof).

Usage
    python scripts/maintenance/g1_build_v4_crt_sot_config.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config_layer.production_config import _compute_params_hash  # noqa: E402

NEW_VERSION = "v4_crt_sot_2026_08"
SOURCE_VERSION = "v2_htfcrt_2026_08"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_declared_params_47() -> dict:
    """Reuse Phase A/B's own proven functions rather than re-deriving the field set."""
    census = _load_module(
        "crt_threshold_authority_census",
        ROOT / "scripts" / "analysis" / "crt_threshold_authority_census.py",
    )
    report = census.build_census()
    if report["active_version"] != SOURCE_VERSION:
        raise SystemExit(
            f"census ran against {report['active_version']!r}, expected {SOURCE_VERSION!r} -- "
            "ACTIVE_VERSION moved since this script was authored, re-verify before running."
        )

    parity = _load_module(
        "crt_declare_all_knobs_parity",
        ROOT / "scripts" / "analysis" / "crt_declare_all_knobs_parity.py",
    )
    active_cfg = json.loads(
        (ROOT / "configs" / "production" / f"{SOURCE_VERSION}.json").read_text(encoding="utf-8")
    )
    return parity.build_declared_params(active_cfg, report)


def main() -> int:
    active_path = ROOT / "configs" / "production" / f"{SOURCE_VERSION}.json"
    out_path = ROOT / "configs" / "production" / f"{NEW_VERSION}.json"

    if out_path.exists():
        raise SystemExit(f"{out_path} already exists -- refusing to overwrite. Delete it first "
                          "if you intend to regenerate.")

    active_cfg = json.loads(active_path.read_text(encoding="utf-8"))
    declared_params = build_declared_params_47()
    print(f"declared params: {len(declared_params)} fields")

    new_cfg = json.loads(json.dumps(active_cfg))  # deep clone, preserves ALL 21 top-level sections
    new_cfg["version"] = NEW_VERSION
    new_cfg["config_id"] = f"{NEW_VERSION}_registered"
    new_cfg["params"] = declared_params
    new_cfg["config_hash"] = _compute_params_hash(declared_params)
    new_cfg["created_at"] = datetime.now(timezone.utc).isoformat()
    new_cfg.pop("promoted_at", None)  # this config is REGISTERED, not promoted -- no promoted_at

    new_cfg["notes"] = (
        f"CH-crt-sot-2026-08-31 (Phase G). REGISTERED, NOT PROMOTED and NOT ACTIVATED -- "
        f"ACTIVE_VERSION remains {SOURCE_VERSION} and was not written. Declares all 47 "
        "scalar-required CRTConfig fields explicitly in `params` (Phase A-E census + parity "
        "proof), replacing the 5-key params / 45-key crt_engine split-brain. `crt_engine` is "
        "left intact (§6.2 rule 4: never delete truth) and is now fully redundant since "
        "params wins on every shared key. Base is the ACTIVE config "
        f"({SOURCE_VERSION}), NOT PromotionManager's v1_multi_2026_03 fallback -- that path was "
        "measured to drop 11 top-level sections (parent_crt, feature_pipeline, "
        "dataset_integrity, model_runners, regime_governor, convergence_controller, "
        "acceptance_controller, live_integration, perp_funding_data, uat, "
        "_comment_parent_crt) and silently revert 10 more (crt_engine 45->29 keys among them) "
        "-- confirmed by direct measurement, and independently corroborated by "
        "_promote_v4_bnb_cutover.py's own documented reason for bypassing PromotionManager. "
        "ConfigValidator was NOT run and is NOT claimed: XAUUSD's ~4 executions across 47,275 "
        "bars cannot clear config_validator.min_trades_per_instrument=10, so score/"
        "score_std_dev stay null, matching the v3_unified_market_structure_2026_09 precedent. "
        "Parity proof (byte-identical XAUUSD ledger vs the active config) is Phase G2, run "
        "separately after this file is written."
    )

    out_path.write_text(json.dumps(new_cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out_path.relative_to(ROOT)}")
    print(f"  version     : {new_cfg['version']}")
    print(f"  config_id   : {new_cfg['config_id']}")
    print(f"  config_hash : {new_cfg['config_hash']}")
    print(f"  params keys : {len(new_cfg['params'])}")
    print(f"  top-level sections: {len(new_cfg)} (source had {len(active_cfg)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
