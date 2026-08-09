# -*- coding: utf-8 -*-
"""Predicate-level failure census for CRT transitions on the 6-month RB1 window.

Replays CRTEngine (same config as backtest) with baseline-trace hooks enabled and
tallies every guard evaluation for:
  SWEEP → DISPLACEMENT
  DISPLACEMENT → EXPANSION
  EXPANSION → RETEST
  (+ summary of other transitions)

Read-only research script. Does not mutate production code or config.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

# Quiet CRT engine logs for census speed
logging.getLogger("CRT_ENGINE_V2").setLevel(logging.WARNING)
logging.getLogger("CRT.StateMachine").setLevel(logging.WARNING)
logging.getLogger("CRT.Backtest").setLevel(logging.WARNING)

from config_layer.crt_engine_v2 import CRTEngine  # noqa: E402
from config_layer.production_config import (  # noqa: E402
    get_active_version,
    load_prod_config_from_registry,
)
from runtime.backtest_v2 import (  # noqa: E402
    BacktestConfig,
    CandleLoader,
    HTFBuilder,
)
from runtime.crt_baseline_trace import CRTBaselineTraceHooks  # noqa: E402

CSV = ROOT / "data" / "XAUUSD_W2025-11-21-to-2026-05-21.csv"
OUT_DIR = ROOT / "results" / "runtime_benchmarks" / "window_search_xauusd"
OUT_JSON = OUT_DIR / "predicate_failure_census_6m.json"
OUT_MD = OUT_DIR / "predicate_failure_census_6m.md"
INSTRUMENT = "XAUUSD"


@dataclass
class EdgeCensus:
    from_state: str
    to_state: str
    attempts: int = 0
    passes: int = 0
    fails: int = 0
    failure_reasons: dict = field(default_factory=dict)
    pass_guard_ids: dict = field(default_factory=dict)
    # first-failure short-circuit: which guard killed the attempt
    first_fail_guard: dict = field(default_factory=dict)
    # optional value snapshots for top fail reasons (bounded)
    fail_examples: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["pass_rate"] = round(self.passes / self.attempts, 4) if self.attempts else None
        d["fail_rate"] = round(self.fails / self.attempts, 4) if self.attempts else None
        return d


def _edge_key(fr: str, to: str) -> str:
    return f"{fr}->{to}"


def main() -> int:
    if not CSV.is_file():
        raise SystemExit(f"missing CSV: {CSV}")

    crt_cfg = load_prod_config_from_registry("v2_multi_2026_04", INSTRUMENT)
    bt_cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
    bt_cfg.instrument = INSTRUMENT

    loader = CandleLoader(str(CSV), INSTRUMENT)
    candles = list(loader.stream())
    total = len(candles)

    engine = CRTEngine(crt_cfg)
    hooks = CRTBaselineTraceHooks()
    hooks.enabled = True
    # Permanent attach: process_candle sets sm.trace_hooks = baseline_trace when enabled
    engine.baseline_trace = hooks

    htf = HTFBuilder(bt_cfg.htf_candles_per_range, INSTRUMENT)
    warmup = bt_cfg.warmup_candles

    edges: dict[str, EdgeCensus] = {
        "SWEEP->DISPLACEMENT": EdgeCensus("SWEEP", "DISPLACEMENT"),
        "DISPLACEMENT->EXPANSION": EdgeCensus("DISPLACEMENT", "EXPANSION"),
        "EXPANSION->RETEST": EdgeCensus("EXPANSION", "RETEST"),
        "SWEEP->EXPANSION": EdgeCensus("SWEEP", "EXPANSION"),
    }
    # catch-all for other from→candidate pairs seen in guards
    other_edges: dict[str, EdgeCensus] = {}

    state_bars = Counter()
    transitions = Counter()
    actions = Counter()

    # Also count structural outcomes without hooks (state change)
    structural_pass = Counter()

    t0 = time.perf_counter()
    initialised = False
    warmup_done = False
    candle_idx = 0

    # session helper — same as backtest (string label for range init)
    def session_label(ts) -> str:
        # minimal: use OFF_SESSION-safe path via engine config windows if available
        try:
            from runtime.backtest_v2 import BacktestRunner

            # use a tiny runner only for _session method if needed
        except Exception:
            pass
        # Fallback matching CRT: resolve from crt_cfg.session_windows if present
        hour = ts.hour if hasattr(ts, "hour") else pd_hour(ts)
        # Prefer CRT engine's own session if exposed; else simple label for range init
        return "LONDON" if 8 <= hour < 16 else ("ASIA" if hour < 8 else "NEWYORK")

    def pd_hour(ts):
        import pandas as pd

        return pd.Timestamp(ts).hour

    # Use same session resolution as backtest if possible
    from runtime.backtest_v2 import BacktestRunner

    runner_for_session = BacktestRunner(bt_cfg, csv_path=str(CSV))

    for candle in candles:
        candle_idx += 1
        htf.push(candle)

        if not warmup_done:
            if candle_idx < warmup:
                continue
            warmup_done = True

        if not initialised:
            seeds = htf.seed_candles()
            if seeds:
                lab = runner_for_session._session(candle.timestamp)
                engine.initialise_range(seeds, htf.current_htf_id, lab)
                initialised = True
            continue

        state_before = engine.state.current_state.name
        state_bars[state_before] += 1

        # reset hook bar buffer; process_candle will reset again when enabled
        hooks.reset_bar()
        hooks.enabled = True
        engine.baseline_trace = hooks

        result = engine.process_candle(candle, htf.current_htf_id)
        state_after = engine.state.current_state.name
        action = result.get("action", "NONE")
        actions[action] += 1

        if state_before != state_after:
            transitions[f"{state_before}->{state_after}"] += 1
            structural_pass[f"{state_before}->{state_after}"] += 1

        # Classify guards for primary edges
        guards = list(hooks.guards)
        # Group by candidate edge
        by_edge: dict[str, list] = defaultdict(list)
        for g in guards:
            ek = _edge_key(g.from_state, g.candidate_to_state)
            by_edge[ek].append(g)

        for ek, glist in by_edge.items():
            if ek in edges:
                cen = edges[ek]
            else:
                if ek not in other_edges:
                    fr, to = ek.split("->", 1)
                    other_edges[ek] = EdgeCensus(fr, to)
                cen = other_edges[ek]

            # An "attempt" for primary edges = we were in from_state and the try_* ran.
            # Detect via presence of any guard for that edge OR structural from_state match.
            # Prefer: if any guard for edge, count one attempt this bar.
            if not glist:
                continue
            cen.attempts += 1

            # Pass if any guard result True with PASS id or state changed to target
            passed = state_before == cen.from_state and state_after == cen.to_state
            # also G_*_PASS guard
            pass_g = [g for g in glist if g.result is True]
            fail_g = [g for g in glist if g.result is False]

            if passed or (pass_g and not fail_g):
                cen.passes += 1
                for g in pass_g:
                    cen.pass_guard_ids[g.guard_id] = cen.pass_guard_ids.get(g.guard_id, 0) + 1
            elif fail_g:
                cen.fails += 1
                # short-circuit: first fail in evaluation_order
                fail_g_sorted = sorted(fail_g, key=lambda x: x.evaluation_order)
                first = fail_g_sorted[0]
                reason = first.failure_reason or first.guard_name or first.guard_id
                cen.failure_reasons[reason] = cen.failure_reasons.get(reason, 0) + 1
                cen.first_fail_guard[first.guard_id] = (
                    cen.first_fail_guard.get(first.guard_id, 0) + 1
                )
                # store up to 3 examples per reason
                ex = cen.fail_examples.setdefault(reason, [])
                if len(ex) < 3:
                    ex.append(
                        {
                            "candle_index": candle_idx,
                            "timestamp": str(getattr(candle, "timestamp", "")),
                            "guard_id": first.guard_id,
                            "guard_name": first.guard_name,
                            "operator": first.operator,
                            "operands": [
                                {
                                    "name": getattr(o, "name", None),
                                    "value": getattr(o, "runtime_value", None),
                                }
                                for o in (first.operands or [])
                            ],
                            "thresholds": [
                                {
                                    "name": getattr(t, "name", None),
                                    "value": getattr(t, "runtime_value", None),
                                    "config_key": getattr(t, "config_key", None),
                                }
                                for t in (first.thresholds or [])
                            ],
                        }
                    )
            else:
                # guards present but neither clear pass nor fail — rare
                cen.fails += 1
                cen.failure_reasons["unknown_no_result"] = (
                    cen.failure_reasons.get("unknown_no_result", 0) + 1
                )

        # Attempt accounting for bars in SWEEP/EXPANSION/DISPLACEMENT even if
        # no guard fired (shouldn't happen for try_* paths):
        if state_before == "SWEEP" and "SWEEP->DISPLACEMENT" not in by_edge:
            # shadow path may skip to EXPANSION without DISPLACEMENT guards
            if state_after == "EXPANSION":
                edges["SWEEP->EXPANSION"].attempts += 1
                edges["SWEEP->EXPANSION"].passes += 1
            elif state_after == "SWEEP":
                # try_sweep_to_displacement returned False without guards? count as attempt miss
                pass

        if candle_idx % 3000 == 0:
            print(
                f"  progress {candle_idx}/{total} state={state_after} "
                f"SWEEP→DISP attempts={edges['SWEEP->DISPLACEMENT'].attempts}",
                flush=True,
            )

    elapsed = time.perf_counter() - t0

    # Reconcile: for primary edges, attempts while in from_state may exceed
    # guard-tagged attempts if hooks missed. Report both.
    # Prefer structural: bars_in_from_state for attempt denominator alternative
    report = {
        "scope": "READ_ONLY predicate failure census — 6-month RB1 XAUUSD",
        "active_version": get_active_version(),
        "csv": str(CSV.relative_to(ROOT)).replace("\\", "/"),
        "csv_rows": total,
        "instrument": INSTRUMENT,
        "elapsed_s": round(elapsed, 2),
        "warmup_candles": warmup,
        "config_thresholds": {
            "atr_min_displacement": crt_cfg.atr_min_displacement,
            "body_ratio_min": crt_cfg.body_ratio_min,
            "atr_multiplier_min": crt_cfg.atr_multiplier_min,
            "max_sweep_age_candles": crt_cfg.max_sweep_age_candles,
            "expansion_atr_min_distance": crt_cfg.expansion_atr_min_distance,
            "retest_min_depth_atr_fraction": crt_cfg.retest_min_depth_atr_fraction,
            "retest_depth_max": crt_cfg.retest_depth_max,
            "retest_atr_depth_fraction": crt_cfg.retest_atr_depth_fraction,
            "max_displacement_strength": crt_cfg.max_displacement_strength,
        },
        "state_bar_counts": dict(state_bars.most_common()),
        "observed_transitions": dict(transitions.most_common()),
        "actions": dict(actions.most_common(30)),
        "edges": {k: v.to_dict() for k, v in edges.items()},
        "other_guard_edges": {k: v.to_dict() for k, v in other_edges.items()},
        "method": (
            "CRTEngine.process_candle replay with CRTBaselineTraceHooks.enabled; "
            "each failed guard short-circuit failure_reason is counted once per attempt "
            "(first fail by evaluation_order). Pass = state transition to target or "
            "PASS guard without fails."
        ),
    }

    # Consistency check vs known 6m funnel
    report["consistency_check"] = {
        "expected_retest_approx": 9,
        "observed_EXPANSION_to_RETEST_passes": edges["EXPANSION->RETEST"].passes,
        "observed_SWEEP_to_DISPLACEMENT_passes": edges["SWEEP->DISPLACEMENT"].passes,
        "structural_SWEEP_to_DISPLACEMENT": transitions.get("SWEEP->DISPLACEMENT", 0),
        "structural_EXPANSION_to_RETEST": transitions.get("EXPANSION->RETEST", 0),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=True, default=str) + "\n", encoding="utf-8")

    # Markdown
    lines = [
        "# Predicate Failure Census — XAUUSD 6-month RB1",
        "",
        "**Read-only.** Replay of `CRTEngine` with guard hooks; no production changes.",
        "",
        f"- CSV: `{CSV.name}` ({total} rows)",
        f"- Config: `{get_active_version()}`",
        f"- Wall time: {elapsed:.1f}s",
        "",
        "## Method",
        "",
        report["method"],
        "",
        "## Config thresholds",
        "",
        "| Key | Value |",
        "|---|---:|",
    ]
    for k, v in report["config_thresholds"].items():
        lines.append(f"| `{k}` | {v} |")
    lines += ["", "## Primary edges", ""]

    for name in (
        "SWEEP->DISPLACEMENT",
        "DISPLACEMENT->EXPANSION",
        "EXPANSION->RETEST",
        "SWEEP->EXPANSION",
    ):
        e = edges[name].to_dict()
        lines += [
            f"### {name}",
            "",
            f"| Metric | Value |",
            f"|---|---:|",
            f"| Attempts | {e['attempts']} |",
            f"| Passes | {e['passes']} |",
            f"| Fails | {e['fails']} |",
            f"| Pass rate | {e['pass_rate']} |",
            f"| Fail rate | {e['fail_rate']} |",
            "",
            "**Failure reasons (first short-circuit):**",
            "",
            "| Reason | Count | Share of fails |",
            "|---|---:|---:|",
        ]
        fails = e["fails"] or 1
        for reason, cnt in sorted(
            e["failure_reasons"].items(), key=lambda x: -x[1]
        ):
            lines.append(f"| `{reason}` | {cnt} | {cnt/fails:.1%} |")
        if not e["failure_reasons"]:
            lines.append("| *(none)* | 0 | — |")
        lines += [
            "",
            "**First-fail guard_id:**",
            "",
            "| guard_id | Count |",
            "|---|---:|",
        ]
        for gid, cnt in sorted(e["first_fail_guard"].items(), key=lambda x: -x[1]):
            lines.append(f"| `{gid}` | {cnt} |")
        if not e["first_fail_guard"]:
            lines.append("| *(none)* | 0 |")
        lines.append("")

    lines += [
        "## Observed state transitions (structural)",
        "",
        "| Transition | Count |",
        "|---|---:|",
    ]
    for k, v in transitions.most_common():
        lines.append(f"| `{k}` | {v} |")
    lines += [
        "",
        "## Consistency vs 6m funnel",
        "",
        "```json",
        json.dumps(report["consistency_check"], indent=2),
        "```",
        "",
        f"Full JSON: `{OUT_JSON.relative_to(ROOT).as_posix()}`",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=== CENSUS DONE ===", flush=True)
    print(f"elapsed {elapsed:.1f}s", flush=True)
    for name, e in edges.items():
        d = e.to_dict()
        print(
            f"{name}: attempts={d['attempts']} pass={d['passes']} "
            f"fail={d['fails']} reasons={d['failure_reasons']}",
            flush=True,
        )
    print("Wrote", OUT_JSON, flush=True)
    print("Wrote", OUT_MD, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
