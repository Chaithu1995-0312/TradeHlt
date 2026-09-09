"""g3_append_v4_crt_sot_registration.py — Phase G3 of the CRT single-source-of-truth plan.

Appends EXACTLY ONE line to configs/promotion_log.jsonl for v4_crt_sot_2026_08, mirroring the
v3_unified_market_structure_2026_09 REGISTERED entry's shape and candour. This is an append-only
governed audit trail in a repository with many concurrent sessions -- the one genuinely
hard-to-reverse write in the whole "CRT single source of truth" plan, which is why it is gated
behind (a) G1's config already written and hash-verified, and (b) G2's parity proof having
returned PASS. This script REFUSES to run if either precondition is not independently re-checked
here (not just trusted from an earlier terminal message).

Why event=REGISTERED, not PROMOTED (same reasoning as the v3 precedent, restated because it is
load-bearing): config_integrity.active_version_is_governed is the only consumer that filters on
the event value, and it only inspects the version named by ACTIVE_VERSION. A PROMOTED line for a
version that was never activated would be a FALSE governance record. score/score_std_dev are null
because ConfigValidator was not run and is not claimed (G-BLOCK-2: XAUUSD cannot clear the
10-trade hard gate).

Usage
    python scripts/maintenance/g3_append_v4_crt_sot_registration.py --confirm-parity-pass
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = ROOT / "configs" / "promotion_log.jsonl"
CONFIG_PATH = ROOT / "configs" / "production" / "v4_crt_sot_2026_08.json"
VERSION = "v4_crt_sot_2026_08"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--confirm-parity-pass", action="store_true", required=True,
        help="required acknowledgement that g2_v4_crt_sot_parity.py returned PASS before running "
             "this script -- there is no automatic re-run of the backtest here, on purpose "
             "(this script's job is the log write, not re-proving parity)",
    )
    args = ap.parse_args()

    if not CONFIG_PATH.exists():
        raise SystemExit(f"{CONFIG_PATH} does not exist -- run g1_build_v4_crt_sot_config.py first")

    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if cfg.get("version") != VERSION:
        raise SystemExit(f"{CONFIG_PATH} has version={cfg.get('version')!r}, expected {VERSION!r}")

    # Refuse a duplicate append -- idempotency check against the log's OWN content, not memory.
    existing = []
    if LOG_PATH.exists():
        with LOG_PATH.open(encoding="utf-8") as fh:
            existing = [json.loads(line) for line in fh if line.strip()]
    if any(e.get("version") == VERSION for e in existing):
        raise SystemExit(f"a promotion_log.jsonl entry for {VERSION} already exists -- refusing "
                          "to append a duplicate. Inspect the log if this is unexpected.")

    active_version = (ROOT / "configs" / "production" / "ACTIVE_VERSION").read_text(
        encoding="utf-8"
    ).strip()

    entry = {
        "event": "REGISTERED",
        "version": VERSION,
        "config_id": cfg["config_id"],
        "params": cfg["params"],
        "config_hash": cfg["config_hash"],
        "score": None,
        "score_std_dev": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": (
            "CH-crt-sot-2026-08-31 (Phase G3). REGISTERED, NOT PROMOTED and NOT ACTIVATED -- "
            f"ACTIVE_VERSION remains {active_version} and was not written by this script or by "
            "any step in this plan. Deliberately event=REGISTERED rather than PROMOTED (same "
            "reasoning as v3_unified_market_structure_2026_09's entry): "
            "config_integrity.active_version_is_governed only inspects the version named by "
            "ACTIVE_VERSION, so a PROMOTED line for a never-activated version would be a false "
            "governance record. score/score_std_dev are null because ConfigValidator was NOT "
            "run and is NOT claimed -- XAUUSD's ~4 executions across the 47,275-bar corpus "
            "cannot clear config_validator.min_trades_per_instrument=10 "
            "(G-BLOCK-2, plan file). PromotionManager.promote_* was deliberately NOT used "
            "(G-BLOCK-3): it merges only 9 metadata keys onto a v1_multi_2026_03 base and was "
            "measured to drop 11 top-level sections + silently revert 10 more, corroborated by "
            "_promote_v4_bnb_cutover.py's independent prior workaround of the same defect. "
            f"params declares all 47 scalar-required CRTConfig fields (was 5 on {active_version}"
            "), replacing the crt_engine/params split-brain measured in Phase A; config_hash "
            "computed via config_layer.production_config._compute_params_hash. Parity proof: "
            f"g2_v4_crt_sot_parity.py PASS -- byte-identical XAUUSD ledger (events.jsonl, "
            f"crt_telemetry.jsonl, trades.csv, summary.json) vs {active_version}, full "
            "47,275-bar corpus, config_version the only differing column (expected -- two "
            "distinct version labels)."
        ),
    }

    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"appended 1 line to {LOG_PATH.relative_to(ROOT)}")
    print(f"  event   : {entry['event']}")
    print(f"  version : {entry['version']}")
    print(f"  ACTIVE_VERSION unchanged: {active_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
