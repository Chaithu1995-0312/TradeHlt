# -*- coding: utf-8 -*-
"""
session_override_scoping_proof.py — B3 scoping + non-regression proof.

The pre-promotion gate (ConfigValidator) is session-config-blind: it builds one
CRTConfig from the `params` section and reuses it for every instrument, never
reading engine_runner.allowed_sessions or allowed_sessions_overrides. So it
cannot validate (or prove non-regression for) an instrument-scoped session
override.

This proves the override at the REAL runtime resolution layer
(load_prod_config_from_registry — the path backtest_v2 / live use after
promotion):

  1. SCOPING: BNBUSDT under the V3 candidate resolves to the expanded session
     set (+ASIA +OFF_SESSION).
  2. NON-REGRESSION: ETHUSDT / BTCUSDT / SOLUSDT under the SAME candidate resolve
     byte-identically to the active prod config (the override is keyed to
     BNBUSDT only). allowed_sessions is the ONLY field the override touches, so
     identical resolution ⇒ deterministically identical backtests for those
     instruments.

MEASURE-ONLY: writes one candidate config to results/session_override/. No
edit to the active prod config, no re-hash, no promotion.
"""
import sys
import json
import copy
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.production_config import (  # noqa: E402
    PROD_VERSION, get_prod_metadata, load_prod_config_from_registry,
)

# V3 (all sessions) — the operator's choice. Base + ASIA + OFF_SESSION.
BNB_V3_SESSIONS = ["london", "new_york", "overlap", "asia", "off_session"]
EXPECT_BNB = ("LONDON", "NEWYORK", "OVERLAP", "ASIA", "OFF_SESSION")

OUT_DIR = _ROOT / "results" / "session_override"
CANDIDATE_NAME = "v2_bnb_sessions_candidate"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Derive the candidate from the active prod config (no mutation of prod).
    meta = get_prod_metadata()
    candidate = copy.deepcopy(meta)
    er = candidate.setdefault("engine_runner", {})
    er["allowed_sessions_overrides"] = {"BNBUSDT": BNB_V3_SESSIONS}
    candidate_path = OUT_DIR / f"{CANDIDATE_NAME}.json"
    candidate_path.write_text(json.dumps(candidate, indent=2), encoding="utf-8")
    print(f"[proof] active prod   : {PROD_VERSION}")
    print(f"[proof] candidate     : {candidate_path}")
    print(f"[proof] BNBUSDT override -> {BNB_V3_SESSIONS}\n")

    instruments = ["BNBUSDT", "ETHUSDT", "BTCUSDT", "SOLUSDT"]
    failures = []
    print(f"{'instrument':<10}{'baseline allowed_sessions':<42}{'candidate allowed_sessions':<42}{'verdict'}")
    print("-" * 110)
    for inst in instruments:
        base = load_prod_config_from_registry(PROD_VERSION, inst).allowed_sessions
        cand = load_prod_config_from_registry(
            CANDIDATE_NAME, inst, registry_dir=str(OUT_DIR), verify_hash=False
        ).allowed_sessions

        if inst == "BNBUSDT":
            ok = (cand == EXPECT_BNB) and (cand != base)
            verdict = "SCOPED (expanded)" if ok else "FAIL"
        else:
            ok = (cand == base)
            verdict = "UNCHANGED" if ok else "FAIL (regression!)"
        if not ok:
            failures.append(inst)
        print(f"{inst:<10}{str(base):<42}{str(cand):<42}{verdict}")

    print()
    if failures:
        print(f"[proof] *** FAIL for {failures} — scoping/non-regression broken. ***")
        return 1
    print("[proof] PASS — BNBUSDT scoped to V3; ETH/BTC/SOL resolution byte-identical "
          "to active prod (deterministic non-regression).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
