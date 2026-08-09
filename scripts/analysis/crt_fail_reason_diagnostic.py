"""
CRT try_* fail-reason diagnostic — OBSERVATION_ONLY.

Uses default-off FailReasonCounters attached as CRTEngine.baseline_trace.
Runs a small deterministic corpus (default: first 3000 post-guard candles of
Phase-1 XAUUSD) — NOT a full 47k hash-preservation run.

TASK_CLASS = OBSERVATION_ONLY
Policy: docs/governance/TASK_CLASSIFICATION_BEHAVIOR_POLICY.md
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from config_layer.production_config import PROD_VERSION  # noqa: E402
from config_layer.crt_engine_v2 import CRTEngine  # noqa: E402
from runtime.backtest_v2 import (  # noqa: E402
    BacktestConfig,
    CandleLoader,
    HTFBuilder,
    guard_xauusd_csv_path,
    load_prod_config_from_registry,
)
from runtime.crt_fail_reason_counters import CRTFailReasonCounters  # noqa: E402

OUT = ROOT / "docs" / "governance"
DEFAULT_MAX_PROCESS = 3000  # post-init process_candle calls


def run_once(*, enable_counters: bool, max_process: int) -> tuple[list[tuple], dict]:
    """Return list of (state_before, state_after, action) + counter dict."""
    csv_path = guard_xauusd_csv_path(str(ROOT / "data/XAUUSD_M15.csv"), "XAUUSD")
    crt_cfg = load_prod_config_from_registry(PROD_VERSION, "XAUUSD")
    bt_cfg = BacktestConfig.from_prod_config(instrument="XAUUSD", crt_config=crt_cfg)
    engine = CRTEngine(crt_cfg)
    counters = CRTFailReasonCounters()
    if enable_counters:
        engine.baseline_trace = counters
        counters.enabled = True
    htf = HTFBuilder(bt_cfg.htf_candles_per_range, "XAUUSD")
    loader = CandleLoader(str(csv_path), "XAUUSD")

    seq = []
    candle_idx = 0
    warmup_done = False
    initialised = False
    processed = 0

    for candle in loader.stream():
        candle_idx += 1
        htf.push(candle)
        if not warmup_done:
            if candle_idx < bt_cfg.warmup_candles:
                continue
            warmup_done = True
        if not initialised:
            if htf.seed_candles():
                engine.initialise_range(htf.seed_candles(), htf.current_htf_id, "UNKNOWN")
                initialised = True
            continue

        if enable_counters:
            counters.enabled = True
        sb = engine.state.current_state.name
        result = engine.process_candle(candle, htf.current_htf_id)
        sa = engine.state.current_state.name
        seq.append((sb, sa, result.get("action", "NONE")))
        processed += 1
        if processed >= max_process:
            break

    return seq, counters.as_dict()


def main() -> int:
    max_p = DEFAULT_MAX_PROCESS
    seq_off, _ = run_once(enable_counters=False, max_process=max_p)
    seq_on, counts = run_once(enable_counters=True, max_process=max_p)
    parity = seq_off == seq_on

    report = {
        "_doc": "CRT fail-reason diagnostic (OBSERVATION_ONLY)",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "task_class": "OBSERVATION_ONLY",
        "policy_ref": "docs/governance/TASK_CLASSIFICATION_BEHAVIOR_POLICY.md",
        "max_process_candles": max_p,
        "on_off_action_parity": parity,
        "processed_off": len(seq_off),
        "processed_on": len(seq_on),
        "fail_reason_counts": counts,
        "baseline_hash_parity_required": False,
        "note": (
            "Full 47k historical hash equality not required. "
            "Neutrality validated on smallest sufficient deterministic prefix."
        ),
    }
    out = OUT / "crt_fail_reason_diagnostic-2026-07-14.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("parity", parity)
    print("evaluations", counts.get("evaluations"))
    print("top fails", (counts.get("raw_counts") or [])[:15])
    print("WROTE", out)
    return 0 if parity else 1


if __name__ == "__main__":
    raise SystemExit(main())
