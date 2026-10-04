"""M-GATE-01 — gate-ON re-measurement of RF-CRT-STRUCTURE (SCOPE measurement only).

Context: F-058 (shipped 2026-07-23) made `backtest.engine_gate_enabled` a strict, config-declared
key. The ACTIVE config (`v2_multi_2026_04`) sets it `true`. But the entire gate-OFF research corpus
behind F-019/F-036/F-037 (and the ~19 `qualify_*` variants) was measured under the PRE-2026-07-23
epoch, where an untracked `.env` forced the gate OFF, and nothing has re-run since the config
declaration. Config and corpus now describe two different objects while still looking comparable.

This script measures the delta directly, two arms, same corpus, same config version
(`spine.prod_version` in configs/research/research_config_spine_majors.json = v2_multi_2026_04):

    OFF arm — BACKTEST_ENGINE_GATE=0 (explicit env override; WARNs by design, backtest_v2.py:2058)
              = the historical F-019/F-036/F-037 object (CRT-only)
    ON  arm — no env var set, so `engine_gate_enabled: true` from config governs
              = the CURRENT active-config object (4-engine fusion)

It reuses `ProductionSpineSource` (src/research/adapters/spine_signal_source.py) unmodified — no
engine code changes. The only lever is the pre-existing env-var override that F-058 itself added.

AUTHORITY: NONE (CLAUDE.md 6.5 Authority Ladder). This is a SCOPE measurement — it establishes
which object the current config epoch produces, nothing more. It cannot promote, re-enable, or
reverse any economic conclusion. Lands in docs/governance/research_family_registry.json ->
RF-CRT-STRUCTURE.L5 as a claim once registered; not itself an ANSWERED_UNDER_CONTRACT event (no
sealed MC-* instance exists for this run).

Non-vacuity guard (mandatory, F-037's original probe found EngineRunner.run() called 0 times once):
before trusting the ON arm's entry set, this script monkeypatches EngineRunner.run to count calls
and HARD-STOPS if the ON arm made zero calls — a zero count means the gate did not actually engage
and every downstream number in this run would be meaningless.

F-058 residue closed here: the resolved engine_gate_mode is WRITTEN onto the output artifact per
instrument+arm, not merely logged as a runtime WARNING — so this run's gate state is recoverable
from its own artifact.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

SPINE_CONFIG = "configs/research/research_config_spine_majors.json"
INSTRUMENTS = ["BNBUSDT", "ETHUSDT", "BTCUSDT", "SOLUSDT"]
OUT_DIR = REPO_ROOT / "results" / "research" / "gate_measurement_2026_08_06"

# F-037's recorded gate-ON figures under the pre-2026-07-23 epoch, kept here only as the
# reconciliation target — a mismatch is itself a finding, not silently overwritten.
F037_RECORDED_GATE_ON = {"BNBUSDT": 11, "SOLUSDT": 6}
F037_RECORDED_GATE_OFF = {"BNBUSDT": 13, "SOLUSDT": 7}

log = logging.getLogger("research.gate_measurement_m_gate_01")
logging.basicConfig(level=logging.WARNING)


def _run_arm(instrument: str, *, env_override: str | None, arm_name: str) -> dict:
    """Run one arm for one instrument via ProductionSpineSource; return a result dict.

    env_override: "0" to force gate OFF, None to leave BACKTEST_ENGINE_GATE unset (config governs).
    Each arm gets its own out_root so the adapter's rglob-most-recent trades.csv lookup can never
    pick up the other arm's artifact.
    """
    from research.adapters.spine_signal_source import ProductionSpineSource

    prev = os.environ.get("BACKTEST_ENGINE_GATE")
    if env_override is None:
        os.environ.pop("BACKTEST_ENGINE_GATE", None)
    else:
        os.environ["BACKTEST_ENGINE_GATE"] = env_override

    call_count = {"n": 0}
    from core.engine_runner import EngineRunner
    _orig_run = EngineRunner.run

    def _counting_run(self, *a, **kw):
        call_count["n"] += 1
        return _orig_run(self, *a, **kw)

    EngineRunner.run = _counting_run
    try:
        src = ProductionSpineSource(
            config_path=SPINE_CONFIG,
            out_root=str(OUT_DIR / arm_name),
        )
        entries = src.entries(instrument)
    finally:
        EngineRunner.run = _orig_run
        if prev is None:
            os.environ.pop("BACKTEST_ENGINE_GATE", None)
        else:
            os.environ["BACKTEST_ENGINE_GATE"] = prev

    pnl = [
        e.meta.get("backtest_pnl_rr_net")
        for e in entries.values()
        if isinstance(e.meta.get("backtest_pnl_rr_net"), (int, float))
    ]
    return {
        "instrument": instrument,
        "arm": arm_name,
        "env_BACKTEST_ENGINE_GATE": env_override,
        "resolved_engine_gate_mode": (
            "gate_off_crt_only" if env_override == "0" else "gate_on_fusion_config_default"
        ),
        "engine_runner_run_call_count": call_count["n"],
        "n_entries": len(entries),
        "entry_indices": sorted(entries.keys()),
        "entry_timestamps": sorted(e.timestamp for e in entries.values() if e.timestamp),
        "mean_pnl_rr_net_backtest_native": (sum(pnl) / len(pnl)) if pnl else None,
        "pnl_rr_net_source_caveat": (
            "backtest-native exit engine output (BacktestRunner's own intrabar exit model), "
            "NOT an independent forward_walk re-derivation under a sealed MC-* label contract. "
            "Diagnostic only per the contract's forbidden-substitution list."
        ),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per_instrument: dict[str, dict] = {}
    hard_stops: list[str] = []

    for instrument in INSTRUMENTS:
        log.warning("=== %s ===", instrument)
        off = _run_arm(instrument, env_override="0", arm_name="off")
        on = _run_arm(instrument, env_override=None, arm_name="on")

        # --- non-vacuity guard: hard stop, do not silently trust a zero-call ON arm ---
        if on["engine_runner_run_call_count"] == 0:
            hard_stops.append(
                f"{instrument}: ON arm made 0 EngineRunner.run() calls — the fusion gate did "
                "NOT engage; every ON-arm number for this instrument is VACUOUS and must not "
                "be trusted (this is exactly the F-037 original-probe failure mode)."
            )

        off_idx = set(off["entry_indices"])
        on_idx = set(on["entry_indices"])
        subset_holds = on_idx.issubset(off_idx)

        entry = {
            "off": off,
            "on": on,
            "on_subset_of_off": subset_holds,
            "removed_by_gate_indices": sorted(off_idx - on_idx),
            "added_by_gate_indices": sorted(on_idx - off_idx),  # should be empty if veto-only
        }

        if instrument in F037_RECORDED_GATE_ON:
            expected_on = F037_RECORDED_GATE_ON[instrument]
            expected_off = F037_RECORDED_GATE_OFF[instrument]
            entry["f037_reconciliation"] = {
                "expected_gate_on_trades": expected_on,
                "measured_gate_on_trades": on["n_entries"],
                "on_matches_f037": on["n_entries"] == expected_on,
                "expected_gate_off_trades": expected_off,
                "measured_gate_off_trades": off["n_entries"],
                "off_matches_f037": off["n_entries"] == expected_off,
            }

        per_instrument[instrument] = entry

    if hard_stops:
        for msg in hard_stops:
            log.error("NON-VACUITY GUARD FAILED: %s", msg)

    summary = {
        "_doc": (
            "M-GATE-01 SCOPE measurement (authority: NONE, CLAUDE.md 6.5). Quantifies the "
            "identity gap between the gate-OFF (pre-2026-07-23 epoch, F-037) and gate-ON "
            "(current active-config epoch, F-058) CRT-structure objects. Does not promote, "
            "re-enable, or economically qualify anything."
        ),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "spine_config": SPINE_CONFIG,
        "prod_version_measured": "v2_multi_2026_04",
        "instruments": INSTRUMENTS,
        "non_vacuity_guard_passed": not hard_stops,
        "non_vacuity_guard_failures": hard_stops,
        "per_instrument": per_instrument,
    }

    out_path = OUT_DIR / "summary.json"
    out_path.write_text(json.dumps(summary, indent=2, sort_keys=False), encoding="utf-8")
    log.warning("wrote %s", out_path)

    if hard_stops:
        log.error("M-GATE-01 FAILED non-vacuity guard for %d instrument(s) — see summary.json", len(hard_stops))
        return 1

    for instrument, entry in per_instrument.items():
        recon = entry.get("f037_reconciliation")
        recon_str = ""
        if recon:
            recon_str = (
                f" | F-037 recon: ON {recon['measured_gate_on_trades']}"
                f"(expected {recon['expected_gate_on_trades']}, "
                f"{'MATCH' if recon['on_matches_f037'] else 'MISMATCH'}) "
                f"OFF {recon['measured_gate_off_trades']}"
                f"(expected {recon['expected_gate_off_trades']}, "
                f"{'MATCH' if recon['off_matches_f037'] else 'MISMATCH'})"
            )
        log.warning(
            "%-10s OFF=%3d ON=%3d subset=%s%s",
            instrument, entry["off"]["n_entries"], entry["on"]["n_entries"],
            entry["on_subset_of_off"], recon_str,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
