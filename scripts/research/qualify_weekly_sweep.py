# -*- coding: utf-8 -*-
"""
qualify_weekly_sweep.py — Program 8: "Run the Gate First" on the weekly CRT-sweep ontology (FX).

Tests the ICT/CRT weekly liquidity theory (Monday+Tuesday accumulation -> Wed-Fri sweep ->
reversal) on the same 5 FX majors qualified for F-035 (EURUSD, AUDUSD, EURCAD, GBPUSD, USDJPY;
XAUUSD deferred, same holiday-gap-gate rationale). Reuses the M4 gate math in
research.qualification VERBATIM (evaluate_pre_bh / benjamini_hochberg / finalize) and
HypothesisRunner.run_instrument(). Adds NO new statistics; the only new machinery is the
weekly-range/sweep geometry (research.weekly_sweep) and the Direction x Vol 3x3 diagnostic
breakdown (informational only, never a second gate -- see `_regime_breakdown`).

Single config family (no spine arm -- the spine's own SL/TP geometry and CRT-only-by-design
scope, F-037, make a spine-vs-weekly_sweep comparison out of scope for this pass):

    configs/research/research_config_weekly_sweep.json   (apply_signal_defaults=false --
        the hypothesis computes its own range-width-derived SL/TP)
    candidate: weekly_sweep_reversal   vs falsification controls

PER-INSTRUMENT WEEKLY MASK: `HypothesisRunner.collect()` fetches ONE shared hypothesis instance
by name from the global registry and reuses it across every instrument -- it cannot express
per-instrument constructor state. Since each FX instrument/broker has its own tradable weekly
mask (`data_ingestion.session_autoderive.derive_weekly_mask`), this driver bypasses `collect()`
for the candidate ONLY: it loads each instrument's candles once (via the runner's own
`_load_candles`), derives that instrument's mask, constructs a freshly-configured
`WeeklySweepReversal` instance carrying it, and calls `run_instrument()` directly -- the frozen
runner code itself is never modified. Controls (no per-instrument state needed) still go
through the standard `runner.collect()` registry path.

MEASURE-ONLY -- no optimization, no new hypotheses, no promotion, no spine/config edits. The
deterministic JSON body carries NO wall-clock (matches qualify_fx_metals); the run manifest
(timestamp / git) is written separately.

Usage:
    python scripts/research/qualify_weekly_sweep.py
    python scripts/research/qualify_weekly_sweep.py --out results/research/weekly_sweep
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import research.controls    # noqa: F401  (register controls)
import research.hypotheses  # noqa: F401  (register hypotheses, incl. weekly_sweep_reversal)
from data_ingestion.session_autoderive import derive_weekly_mask        # noqa: E402
from research.candle_state.encoder import (                             # noqa: E402
    DIR_BEAR_STRONG, DIR_BEAR_WEAK, DIR_BULL_STRONG, DIR_BULL_WEAK, DIR_DOJI,
)
from research.config import ResearchConfig                              # noqa: E402
from research.costs import CostModel                                    # noqa: E402
from research.hypotheses.weekly_sweep_reversal import WeeklySweepReversal  # noqa: E402
from research.measurement.metrics import EdgeAggregator                 # noqa: E402
from research.provenance import provenance_block                        # noqa: E402
from research.qualification import (                                    # noqa: E402
    BH_METHOD_VERSION, PERMUTATION_METHOD_VERSION, QUALIFICATION_VERSION,
    QualConfig, benjamini_hochberg, evaluate_pre_bh, finalize, _net_rrs,
)
from research.registry import HYPOTHESIS_REGISTRY                       # noqa: E402
from research.runner import HypothesisRunner                            # noqa: E402
from utils.console_safe import safe_print                               # noqa: E402

FX = ["EURUSD", "AUDUSD", "EURCAD", "GBPUSD", "USDJPY"]
SCOPES = FX + ["POOLED"]   # per-instrument first, pooled last (load-bearing order)

CONFIG_PATH = "configs/research/research_config_weekly_sweep.json"
CANDIDATE = "weekly_sweep_reversal"

# Reporting-layer-only collapse of CandleStateEncoder's 5-state direction to 3 buckets for the
# Direction x Vol 3x3 diagnostic. The encoder itself is untouched; this lives here because the
# collapse is specific to this program's reporting, not a general encoder concern.
_DIRECTION_COLLAPSE = {
    DIR_BULL_STRONG: "BULL",
    DIR_BULL_WEAK: "BULL",
    DIR_BEAR_STRONG: "BEAR",
    DIR_BEAR_WEAK: "BEAR",
    DIR_DOJI: "DOJI",
}


def _collapse_direction(direction: str) -> str:
    return _DIRECTION_COLLAPSE.get(direction, direction)


def _csv_map(cfg: ResearchConfig, instruments: list[str]) -> dict[str, str]:
    data_dir = Path(cfg.data_dir)
    keep = set(instruments)
    out: dict[str, str] = {}
    for p in sorted(data_dir.glob(cfg.pattern)):
        inst = p.stem.split("_")[0]
        if inst in keep:
            out[inst] = str(p)
    return out


def _weekly_sweep_per_instrument(
    cfg: ResearchConfig, ws_cfg: dict, csv_map: dict[str, str]
) -> dict[str, list]:
    """Per-instrument Outcomes for `weekly_sweep_reversal`, one freshly-configured hypothesis
    instance per instrument (carries that instrument's own derived weekly mask) -- see the
    module docstring for why `HypothesisRunner.collect()` cannot be used here directly."""
    runner = HypothesisRunner(cfg)
    per_instrument: dict[str, list] = {}
    for instrument in sorted(csv_map):
        candles = runner._load_candles(csv_map[instrument], instrument)
        mask = derive_weekly_mask((c.timestamp for c in candles), presence_min=0.5)
        hyp = WeeklySweepReversal(
            min_accumulation_bars=ws_cfg["min_accumulation_bars"],
            sl_range_frac=ws_cfg["sl_range_frac"],
            atr_period=ws_cfg["atr_period"],
            max_intraweek_gap_minutes=ws_cfg["max_intraweek_gap_minutes"],
            regime_tercile_window=ws_cfg["regime_tercile_window"],
            check_week_validity=ws_cfg["check_week_validity"],
            weekly_mask=mask,
        )
        _, outs = runner.run_instrument(hyp, csv_map[instrument], instrument)
        per_instrument[instrument] = outs
    return per_instrument


def _winning_control(per_by_hyp, control_names, scope_instruments, agg, cost):
    """Highest pooled NET-expectancy control over the scope (== qualify_fx_metals semantics)."""
    win_name, win_rrs, win_exp = "none", [], float("-inf")
    for name in sorted(control_names):
        per = {i: per_by_hyp[name][i] for i in scope_instruments}
        rrs: list[float] = []
        for outs in per.values():
            rrs.extend(_net_rrs(outs, cost))
        rep = agg.aggregate(name, sorted(scope_instruments),
                            [o for outs in per.values() for o in outs], cost_model=cost)
        if rep.expectancy_rr > win_exp:
            win_name, win_rrs, win_exp = name, rrs, rep.expectancy_rr
    if win_exp == float("-inf"):
        win_name, win_rrs, win_exp = "none", [], 0.0
    return win_name, win_rrs, win_exp


def _regime_breakdown(outcomes: list, agg: EdgeAggregator, cost: CostModel) -> dict:
    """Diagnostic-only Direction x Vol 3x3 breakdown of `outcomes` -- NOT a gate: no
    permutation test, no BH correction, no OOS split per cell (small-N would make per-cell
    significance meaningless). Mirrors Program 6b's diagnostics-appendix discipline
    (information is not authority, CLAUDE.md section 6.5)."""
    cells: dict[str, list] = {}
    for o in outcomes:
        raw = o.signal.meta.get("direction_vol_cell", "UNKNOWN/UNKNOWN")
        direction_raw, _, vol = raw.partition("/")
        cell = f"{_collapse_direction(direction_raw)}/{vol or 'UNKNOWN'}"
        cells.setdefault(cell, []).append(o)

    breakdown: dict[str, dict] = {}
    for cell, outs in sorted(cells.items()):
        rep = agg.aggregate(CANDIDATE, [], outs, cost_model=cost)
        breakdown[cell] = {
            "n": rep.n, "wins": rep.wins,
            "profit_factor": rep.profit_factor,
            "expectancy_rr": rep.expectancy_rr,
        }
    return breakdown


def _run(cfg_path: str, ws_cfg: dict) -> tuple[ResearchConfig, dict]:
    cfg = ResearchConfig.from_file(cfg_path)
    runner = HypothesisRunner(cfg)
    cost = CostModel(cfg.round_trip_bps)
    agg = EdgeAggregator()
    qcfg = QualConfig.from_research_config(cfg)

    csv_map = _csv_map(cfg, FX)
    if not csv_map:
        raise SystemExit(f"No CSVs matched {cfg.pattern} in {cfg.data_dir} for {FX}")
    control_names = sorted(n for n, h in HYPOTHESIS_REGISTRY.items() if h.family == "control")

    per_by_hyp: dict[str, dict] = {CANDIDATE: _weekly_sweep_per_instrument(cfg, ws_cfg, csv_map)}
    for name in control_names:
        per_by_hyp[name] = runner.collect(name, csv_map)

    family: dict[str, dict] = {}
    for scope in SCOPES:
        wanted = FX if scope == "POOLED" else [scope]
        scope_instruments = [i for i in wanted if i in csv_map]
        win_name, win_rrs, win_exp = _winning_control(
            per_by_hyp, control_names, scope_instruments, agg, cost)

        per = {i: per_by_hyp[CANDIDATE][i] for i in scope_instruments}
        outs = [o for v in per.values() for o in v]
        report = agg.aggregate(CANDIDATE, sorted(scope_instruments), outs, cost_model=cost)
        state = evaluate_pre_bh(report, per, win_name, win_rrs, win_exp, qcfg, cost)

        bh_inputs = {CANDIDATE: state.p_value} if state.passed_1_to_6 else {}
        bh_survivors = benjamini_hochberg(bh_inputs, qcfg.significance_alpha)
        final = finalize(state, bh_survivors, qcfg)

        family[scope] = {
            "winning_control": win_name,
            "winning_control_exp": round(win_exp, 6),
            "hypotheses": {CANDIDATE: dataclasses.asdict(final)},
            "regime_breakdown": _regime_breakdown(outs, agg, cost),
        }
    return cfg, family


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _print_table(report_doc: dict) -> None:
    safe_print("\nQUALIFY-WEEKLY-SWEEP (Program 8) — per-instrument first, pooled last "
               "(intrabar_fixed, 12bps; alpha=0.05)\n")
    header = f"| {'Scope':10s} | {'n':>7s} | {'PF':>8s} | {'E(net)':>9s} | {'p':>8s} | {'Verdict':12s} |"
    sep = "|" + "-" * 12 + "|" + "-" * 9 + "|" + "-" * 10 + "|" + "-" * 11 + "|" + "-" * 10 + "|" + "-" * 14 + "|"
    safe_print(header)
    safe_print(sep)
    for scope in report_doc["scope_order"]:
        r = report_doc["scopes"][scope]["hypotheses"][report_doc["candidate"]]
        safe_print(
            f"| {scope:10s} | {r['n']:7d} | {r['profit_factor']:8.3f} | "
            f"{r['expectancy_rr']:+9.4f} | {r['p_value']:8.4f} | {r['verdict']:12s} |")
    safe_print(sep)

    promoted = [
        scope for scope in report_doc["scope_order"]
        if report_doc["scopes"][scope]["hypotheses"][report_doc["candidate"]]["verdict"] == "PROMOTE"
    ]
    safe_print(f"\nPROMOTE: {promoted or 'none'}")

    safe_print("\nDirection x Vol regime breakdown (POOLED scope, diagnostic only — not a gate):\n")
    rb = report_doc["scopes"]["POOLED"]["regime_breakdown"]
    header2 = f"| {'Cell':16s} | {'n':>6s} | {'wins':>6s} | {'PF':>8s} | {'E(net)':>9s} |"
    sep2 = "|" + "-" * 18 + "|" + "-" * 8 + "|" + "-" * 8 + "|" + "-" * 10 + "|" + "-" * 11 + "|"
    safe_print(header2)
    safe_print(sep2)
    for cell, stats in sorted(rb.items()):
        safe_print(
            f"| {cell:16s} | {stats['n']:6d} | {stats['wins']:6d} | "
            f"{stats['profit_factor']:8.3f} | {stats['expectancy_rr']:+9.4f} |")
    safe_print(sep2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="qualify_weekly_sweep",
        description="Program 8: M4 qualification of the weekly CRT-sweep ontology (FX majors)")
    parser.add_argument("--out", default="results/research/weekly_sweep")
    args = parser.parse_args(argv)

    cfg_dict = json.loads(Path(CONFIG_PATH).read_text(encoding="utf-8"))
    ws_cfg = cfg_dict["weekly_sweep"]   # _require semantics: KeyError if absent, no soft default

    cfg, family = _run(CONFIG_PATH, ws_cfg)

    # Deterministic body — NO wall-clock; safe to byte-compare across runs.
    report_doc = {
        "qualification_version": QUALIFICATION_VERSION,
        "permutation_method_version": PERMUTATION_METHOD_VERSION,
        "permutation_count": cfg.q_n_permutations,
        "bh_method_version": BH_METHOD_VERSION,
        "alpha": cfg.q_significance_alpha,
        "scope_order": SCOPES,
        "universe": FX,
        "candidate": CANDIDATE,
        **provenance_block(cfg.exit_model, cfg.round_trip_bps),
        "config_path": CONFIG_PATH,
        "config_sha256": cfg.sha256(),
        "weekly_sweep_params": {k: v for k, v in ws_cfg.items() if k != "_doc"},
        "scopes": family,
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "qualify_weekly_sweep.json").write_text(
        json.dumps(report_doc, sort_keys=True, indent=2), encoding="utf-8")
    # Wall-clock / environment provenance lives separately (keeps the body byte-comparable).
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "config_sha256": cfg.sha256(),
    }
    (out_dir / "qualify_weekly_sweep_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")

    _print_table(report_doc)
    safe_print(f"\n-> {out_dir / 'qualify_weekly_sweep.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
