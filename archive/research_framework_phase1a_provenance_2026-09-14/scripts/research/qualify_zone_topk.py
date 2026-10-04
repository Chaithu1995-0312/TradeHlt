# -*- coding: utf-8 -*-
"""
qualify_zone_topk.py — measure ΔG001 of the engine_runner.zone_gate knobs
(top_k / cluster_min_n / cluster_spread_max) across crypto majors.

WHY: the config-first migration shipped these as BEHAVIORAL knobs (default {3,2,0.15},
byte-parity proven). Per CLAUDE.md §6.5 Authority Ladder that grants *tunability, not
authority*; a non-default value earns production weight only via measured ΔG001. This is
that measurement — the doctrine-correct way to either earn authority or kill the lever.
Prior is null (F-021 zone-selection / F-019 spine INSUFFICIENT); a confirmed ΔG001≈0 is a
high-knowledge-ROI null, not a failure.

TWO LAYERS per knob-cell (user-approved scope = both):
  Layer 1 — ΔG001: the spine's OWN goal_report (BacktestMetrics, governing intrabar_touch
            exit). expectancy_r / trades_per_month / win_rate / max_dd / PF + goal PASS-count.
  Layer 2 — M4 authority: the cell's spine entries → forward_walk → the 7-gate
            QualificationGate vs controls (permutation/BH + beats-control + OOS retention),
            on the research intrabar_fixed truth standard. Verdict per scope.

ISOLATION: a single full-history spine backtest is run per (cell, instrument); its metrics
feed Layer 1 and its trades.csv (parsed via ProductionSpineSource._parse_trades) feed a
CANNED spine source so Layer 2 forward-walks the SAME entries with no re-run. The knob is
injected by wrapping config_layer.production_config.get_prod_section (deep-copy the
engine_runner section, override zone_gate) — NO JSON edit, NO rehash, NO promotion. Same
MEASURE-ONLY discipline as session_sweep.py / exit_grid.py / qualify_majors.py.

Usage:
    python scripts/research/qualify_zone_topk.py                 # Stage A (top_k axis)
    python scripts/research/qualify_zone_topk.py --stage B       # full 3-knob grid
    python scripts/research/qualify_zone_topk.py --instruments BNBUSDT
    python scripts/research/qualify_zone_topk.py --no-selfcheck  # skip injection-neutrality gate
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import itertools
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
os.chdir(_ROOT)

import research.controls    # noqa: F401,E402  (register controls)
import research.hypotheses  # noqa: F401,E402  (register hypotheses, incl. spine)
import config_layer.production_config as _pc                       # noqa: E402
import runtime.backtest_v2 as _bt                                  # noqa: E402
from config_layer.goal_validator import GoalValidator             # noqa: E402
from research.adapters.spine_signal_source import ProductionSpineSource  # noqa: E402
from research.config import ResearchConfig                         # noqa: E402
from research.costs import CostModel                               # noqa: E402
from research.hypotheses.spine_hypothesis import SpineHypothesis   # noqa: E402
from research.measurement.metrics import EdgeAggregator            # noqa: E402
from research.provenance import provenance_block                   # noqa: E402
from research.qualification import (                               # noqa: E402
    BH_METHOD_VERSION, PERMUTATION_METHOD_VERSION, QUALIFICATION_VERSION,
    QualConfig, benjamini_hochberg, evaluate_pre_bh, finalize, _net_rrs,
)
from research.registry import HYPOTHESIS_REGISTRY                  # noqa: E402
from research.runner import HypothesisRunner                       # noqa: E402
from utils.console_safe import safe_print                          # noqa: E402

SPINE_CONFIG = "configs/research/research_config_spine_majors.json"
MAJORS = ["BNBUSDT", "ETHUSDT", "BTCUSDT", "SOLUSDT"]
SCOPES_TAIL = "POOLED"

# Default cell = the byte-parity baseline (top_k, cluster_min_n, cluster_spread_max).
BASELINE = (3, 2, 0.15)
# Stage A — the top_k axis (cluster knobs at default). 8 zones ⇒ top_k≥8 saturates.
STAGE_A_TOPK = [1, 2, 3, 5, 8]
# Stage B — the full 3-knob grid (only run on a Stage-A lead, per the plan).
STAGE_B_TOPK = [1, 2, 3, 5, 8]
STAGE_B_MINN = [1, 2, 3]
STAGE_B_SPREAD = [0.10, 0.15, 0.25]


# ─────────────────────────────────────────────────────────────────────────────
# Knob injection — wrap get_prod_section so the engine_runner read carries the cell.
# ─────────────────────────────────────────────────────────────────────────────
class _InjectZoneGate:
    """Context manager: monkeypatch production_config.get_prod_section so a read of the
    'engine_runner' section returns a deep copy with zone_gate.{top_k,cluster_min_n,
    cluster_spread_max} overridden. backtest_v2 imports get_prod_section at call time
    (function-local `from ... import`), so patching the module attribute is seen."""

    def __init__(self, cell: tuple[int, int, float]):
        self.cell = cell
        self._orig = None

    def __enter__(self):
        orig = _pc.get_prod_section
        tk, cmn, csm = self.cell

        def patched(name, *args, **kwargs):
            sec = orig(name, *args, **kwargs)
            if name == "engine_runner":
                sec = copy.deepcopy(sec)
                zg = dict(sec.get("zone_gate", {}))
                zg["top_k"] = tk
                zg["cluster_min_n"] = cmn
                zg["cluster_spread_max"] = csm
                sec["zone_gate"] = zg
            return sec

        self._orig = orig
        _pc.get_prod_section = patched
        return self

    def __exit__(self, *exc):
        _pc.get_prod_section = self._orig
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Canned spine source (Layer 2): serve pre-harvested entries, no backtest re-run.
# ─────────────────────────────────────────────────────────────────────────────
class _CannedSpineSource:
    def __init__(self, by_instrument: dict[str, dict]):
        self._by = by_instrument

    def entries(self, instrument: str) -> dict:
        return self._by.get(instrument, {})


# ─────────────────────────────────────────────────────────────────────────────
# One spine backtest → (Layer-1 metrics, Layer-2 entries). Run under the cell's knob.
# ─────────────────────────────────────────────────────────────────────────────
def _resolve_csv(instrument: str) -> str:
    cand = Path("data") / f"{instrument}_M15.csv"
    if not cand.exists():
        raise FileNotFoundError(f"no CSV for {instrument}: {cand}")
    return str(cand)


def _run_spine_once(instrument: str, version: str, out_dir: Path) -> tuple[dict, dict, str]:
    """Faithful spine run (mirrors ProductionSpineSource._compute_entries). Returns
    (layer1_metrics, entries_dict, trades_sha). get_prod_section must already be patched."""
    csv_path = _resolve_csv(instrument)
    out_dir.mkdir(parents=True, exist_ok=True)
    crt_cfg = _pc.load_prod_config_from_registry(version, instrument)
    cfg = _bt.BacktestConfig.from_prod_config(
        instrument=instrument,
        pip_size=_bt.MultiInstrumentRunner.INSTRUMENT_PIP.get(instrument, 0.0001),
        crt_config=crt_cfg,
    )
    cfg.scorer_mode = "calibrated"
    loader = _bt.CandleLoader(csv_path, instrument)
    runner = _bt.BacktestRunner(cfg, csv_path=csv_path, overrides={"_spine_adapter": "1"})
    m = runner.run(loader.stream(), loader.count(), str(out_dir))

    expectancy_r = round(float(getattr(m, "avg_rr_net", 0.0)), 6)             # goal expectancy_r
    trades_per_month = round(float(getattr(m, "trades_per_month", 0.0)), 4)
    win_rate = round(float(getattr(m, "win_rate", 0.0)), 4)
    max_dd = round(float(getattr(m, "max_drawdown_pct", 0.0)), 4)
    # Evaluate G001 directly (pure; loads the active GoalSpec) — self-contained, independent
    # of whether this harness path attached goal_report to BacktestMetrics.distribution.
    gr = GoalValidator.evaluate({
        "trades_per_month": trades_per_month, "win_rate": win_rate,
        "max_drawdown_pct": max_dd, "expectancy_r": expectancy_r, "avg_rr": expectancy_r,
    }).to_dict()
    crit = gr.get("criteria", []) or []
    layer1 = {
        "approved_trades":  int(getattr(m, "approved_trades", 0)),
        "expectancy_r":     expectancy_r,
        "trades_per_month": trades_per_month,
        "win_rate":         win_rate,
        "max_drawdown_pct": max_dd,
        "profit_factor":    round(float(getattr(m, "profit_factor", 0.0)), 4),
        "total_pnl_rr_net": round(float(getattr(m, "total_pnl_rr_net", 0.0)), 6),
        "goal_id":          gr.get("goal_id", "UNSET"),
        "goal_decision":    gr.get("decision", "DISABLED"),
        "goal_pass_count":  sum(1 for c in crit if c.get("status") == "PASS"),
        "goal_criteria_n":  len(crit),
    }

    trades = sorted(out_dir.rglob(f"{instrument}_trades.csv"), key=lambda p: p.stat().st_mtime)
    if not trades:
        return layer1, {}, ""
    trades_path = trades[-1]
    trades_sha = hashlib.sha256(trades_path.read_bytes()).hexdigest()
    entries = ProductionSpineSource()._parse_trades(trades_path, instrument)  # reuse parser
    return layer1, entries, trades_sha


# ─────────────────────────────────────────────────────────────────────────────
# Layer 2 — M4 over the canned spine entries vs controls (qualify_majors semantics).
# ─────────────────────────────────────────────────────────────────────────────
def _winning_control(per_by_hyp, control_names, scope_instruments, agg, cost):
    win_name, win_rrs, win_exp = "none", [], float("-inf")
    for name in sorted(control_names):
        per = {i: per_by_hyp[name][i] for i in scope_instruments}
        rrs = [r for outs in per.values() for r in _net_rrs(outs, cost)]
        rep = agg.aggregate(name, sorted(scope_instruments),
                            [o for outs in per.values() for o in outs], cost_model=cost)
        if rep.expectancy_rr > win_exp:
            win_name, win_rrs, win_exp = name, rrs, rep.expectancy_rr
    if win_exp == float("-inf"):
        win_name, win_rrs, win_exp = "none", [], 0.0
    return win_name, win_rrs, win_exp


def _m4_for_cell(entries_by_inst: dict[str, dict], instruments: list[str]) -> dict:
    """Run gates 1–7 for the spine (canned entries) across per-instrument + POOLED scopes."""
    cfg = ResearchConfig.from_file(SPINE_CONFIG)
    runner = HypothesisRunner(cfg)
    cost = CostModel(cfg.round_trip_bps)
    agg = EdgeAggregator()
    qcfg = QualConfig.from_research_config(cfg)

    # Inject the cell's entries as the registry's spine instance (no backtest re-run).
    HYPOTHESIS_REGISTRY["spine"] = SpineHypothesis(source=_CannedSpineSource(entries_by_inst))

    csv_map = {i: _resolve_csv(i) for i in instruments}
    control_names = sorted(n for n, h in HYPOTHESIS_REGISTRY.items() if h.family == "control")

    per_by_hyp: dict[str, dict] = {}
    for name in ["spine"] + control_names:
        per_by_hyp[name] = runner.collect(name, csv_map)

    scopes = [i for i in instruments] + [SCOPES_TAIL]
    out: dict[str, dict] = {}
    for scope in scopes:
        wanted = instruments if scope == SCOPES_TAIL else [scope]
        scope_instruments = [i for i in wanted if i in csv_map]
        win_name, win_rrs, win_exp = _winning_control(
            per_by_hyp, control_names, scope_instruments, agg, cost)
        per = {i: per_by_hyp["spine"][i] for i in scope_instruments}
        report = agg.aggregate("spine", sorted(scope_instruments),
                               [o for outs in per.values() for o in outs], cost_model=cost)
        state = evaluate_pre_bh(report, per, win_name, win_rrs, win_exp, qcfg, cost)
        bh = benjamini_hochberg({"spine": state.p_value} if state.passed_1_to_6 else {},
                                qcfg.significance_alpha)
        final = finalize(state, bh, qcfg)
        out[scope] = {
            "n": final.n,
            "profit_factor": final.profit_factor,
            "expectancy_rr": final.expectancy_rr,
            "p_value": final.p_value,
            "baseline_name": final.baseline_name,
            "baseline_delta": final.baseline_delta,
            "oos_retention": final.oos_retention,
            "verdict": final.verdict,
            "reject_reasons": final.reject_reasons,
        }
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Cells
# ─────────────────────────────────────────────────────────────────────────────
def _cells(stage: str) -> list[tuple[int, int, float]]:
    if stage == "A":
        cells = [(tk, 2, 0.15) for tk in STAGE_A_TOPK]
    else:
        cells = [(tk, mn, sp) for tk, mn, sp in
                 itertools.product(STAGE_B_TOPK, STAGE_B_MINN, STAGE_B_SPREAD)]
    if BASELINE not in cells:
        cells.insert(0, BASELINE)
    # baseline first (so ΔG001 reference is computed up front), then the rest, deduped.
    ordered = [BASELINE] + [c for c in cells if c != BASELINE]
    seen, uniq = set(), []
    for c in ordered:
        if c not in seen:
            seen.add(c); uniq.append(c)
    return uniq


def _cell_id(cell) -> str:
    tk, mn, sp = cell
    return f"k{tk}_n{mn}_s{str(sp).replace('.', 'p')}"


# ─────────────────────────────────────────────────────────────────────────────
def _selfcheck(version: str, root: Path, instrument: str = "BNBUSDT") -> dict:
    """Injection-neutrality gate: an UNPATCHED run and a PATCHED-default run must produce a
    byte-identical trade ledger (the wrap is a no-op at the active-config defaults).
    Uses repo-relative dirs (the Windows ReportWriter needs its run-subdir under a real path)."""
    l_un, _, sha_un = _run_spine_once(instrument, version, root / "_selfcheck_unpatched")  # no patch
    with _InjectZoneGate(BASELINE):
        l_pa, _, sha_pa = _run_spine_once(instrument, version, root / "_selfcheck_patched")
    ok = bool(sha_un) and sha_un == sha_pa
    return {"instrument": instrument, "unpatched_sha": sha_un, "patched_default_sha": sha_pa,
            "byte_identical": ok, "trades": l_un["approved_trades"]}


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _delta(cell_m: dict, base_m: dict) -> dict:
    keys = ["expectancy_r", "trades_per_month", "win_rate", "max_drawdown_pct",
            "profit_factor", "approved_trades", "goal_pass_count"]
    return {f"d_{k}": round(cell_m[k] - base_m[k], 6) for k in keys}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="qualify_zone_topk",
                                description="Measure ΔG001 of the zone_gate knobs (crypto majors).")
    p.add_argument("--stage", choices=["A", "B"], default="A")
    p.add_argument("--instruments", nargs="*", default=MAJORS)
    p.add_argument("--out", default="results/research/zone_topk_sweep")
    p.add_argument("--no-selfcheck", action="store_true")
    args = p.parse_args(argv)

    os.environ["RESEARCH_SPINE_CONFIG"] = SPINE_CONFIG          # tp_target for _parse_trades
    logging.getLogger("CRT").setLevel(logging.ERROR)           # spine is deterministic; hush
    logging.getLogger("ENGINE_RUNNER").setLevel(logging.ERROR)

    _spine_block = json.loads(Path(SPINE_CONFIG).read_text(encoding="utf-8")).get("spine", {})
    version = _spine_block.get("prod_version") or _bt.PROD_VERSION
    instruments = [i for i in args.instruments if (Path("data") / f"{i}_M15.csv").exists()]
    if not instruments:
        raise SystemExit(f"no data CSVs for {args.instruments}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    spine_root = out_dir / "_spine"

    # ── V0 self-check ─────────────────────────────────────────────────────────
    selfcheck = None
    if not args.no_selfcheck:
        safe_print("V0 self-check (injection neutrality at defaults)…")
        selfcheck = _selfcheck(version, spine_root, instruments[0])
        safe_print(f"  {selfcheck['instrument']}: byte_identical={selfcheck['byte_identical']} "
                   f"(unpatched={selfcheck['unpatched_sha'][:12]} "
                   f"patched={selfcheck['patched_default_sha'][:12]})")
        if not selfcheck["byte_identical"]:
            raise SystemExit("V0 self-check FAILED — get_prod_section wrap is not neutral at "
                             "defaults. STOP (do not trust ΔG001).")

    # ── sweep ─────────────────────────────────────────────────────────────────
    cells = _cells(args.stage)
    safe_print(f"\nStage {args.stage}: {len(cells)} cells × {len(instruments)} instruments "
               f"(baseline={BASELINE})\n")
    cell_results: dict[str, dict] = {}
    base_layer1: dict[str, dict] = {}     # baseline metrics per instrument (ΔG001 reference)

    for cell in cells:
        cid = _cell_id(cell)
        safe_print(f"[cell {cid}] top_k={cell[0]} cluster_min_n={cell[1]} spread_max={cell[2]}")
        layer1_by_inst: dict[str, dict] = {}
        entries_by_inst: dict[str, dict] = {}
        sha_by_inst: dict[str, str] = {}
        with _InjectZoneGate(cell):
            for inst in instruments:
                try:
                    l1, entries, sha = _run_spine_once(
                        inst, version, spine_root / cid / inst)
                    layer1_by_inst[inst] = l1
                    entries_by_inst[inst] = entries
                    sha_by_inst[inst] = sha
                    safe_print(f"    {inst}: trades={l1['approved_trades']} "
                               f"E_r={l1['expectancy_r']:+.4f} PF={l1['profit_factor']:.3f} "
                               f"entries={len(entries)} goal={l1['goal_decision']}")
                except Exception as e:                                   # noqa: BLE001
                    safe_print(f"    {inst}: ERROR {e}")
                    layer1_by_inst[inst] = {"error": str(e)}
        # Layer 2 — M4 over the cell's entries (skip instruments that errored).
        ok_inst = [i for i in instruments if entries_by_inst.get(i) is not None
                   and "error" not in layer1_by_inst.get(i, {})]
        m4 = _m4_for_cell({i: entries_by_inst[i] for i in ok_inst}, ok_inst) if ok_inst else {}

        if cell == BASELINE:
            base_layer1 = layer1_by_inst
        deltas = {
            inst: (_delta(layer1_by_inst[inst], base_layer1[inst])
                   if inst in base_layer1 and "error" not in layer1_by_inst.get(inst, {})
                   and "error" not in base_layer1.get(inst, {}) else {})
            for inst in instruments
        }
        cell_results[cid] = {
            "cell": {"top_k": cell[0], "cluster_min_n": cell[1], "cluster_spread_max": cell[2]},
            "layer1_g001": layer1_by_inst,
            "delta_g001_vs_baseline": deltas,
            "entry_counts": {i: len(entries_by_inst.get(i, {})) for i in instruments},
            "trades_sha": sha_by_inst,
            "layer2_m4": m4,
        }

    # ── deterministic body + manifest ─────────────────────────────────────────
    rc = ResearchConfig.from_file(SPINE_CONFIG)
    body = {
        "experiment": "zone_topk_g001",
        "stage": args.stage,
        "baseline_cell": {"top_k": BASELINE[0], "cluster_min_n": BASELINE[1],
                          "cluster_spread_max": BASELINE[2]},
        "instruments": instruments,
        "prod_version": version,
        "qualification_version": QUALIFICATION_VERSION,
        "permutation_method_version": PERMUTATION_METHOD_VERSION,
        "bh_method_version": BH_METHOD_VERSION,
        "permutation_count": rc.q_n_permutations,
        "alpha": rc.q_significance_alpha,
        "spine_config_sha256": rc.sha256(),
        **provenance_block(rc.exit_model, rc.round_trip_bps),
        "selfcheck": selfcheck,
        "cells": cell_results,
    }
    body_json = json.dumps(body, sort_keys=True, indent=2)
    body_sha = hashlib.sha256(body_json.encode("utf-8")).hexdigest()
    (out_dir / "zone_topk_sweep.json").write_text(body_json, encoding="utf-8")
    (out_dir / "zone_topk_sweep_manifest.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "body_sha256": body_sha,
        "spine_config_sha256": rc.sha256(),
    }, sort_keys=True, indent=2), encoding="utf-8")

    _print_summary(body)
    safe_print(f"\nbody_sha256={body_sha}")
    safe_print(f"-> {out_dir / 'zone_topk_sweep.json'}")
    return 0


def _print_summary(body: dict) -> None:
    safe_print("\nΔG001 SUMMARY — Layer-1 expectancy_r (spine goal_report) vs baseline; "
               "Layer-2 = M4 POOLED verdict\n")
    base = body["baseline_cell"]
    safe_print(f"baseline cell = top_k {base['top_k']} / min_n {base['cluster_min_n']} / "
               f"spread {base['cluster_spread_max']}")
    header = (f"| {'cell':16s} | {'inst':8s} | {'trades':>6s} | {'E_r':>9s} | "
              f"{'dE_r':>9s} | {'entries':>7s} | {'M4(pooled)':10s} |")
    safe_print(header)
    safe_print("|------------------|----------|--------|-----------|-----------|---------|------------|")
    for cid, cr in body["cells"].items():
        pooled = cr["layer2_m4"].get("POOLED", {})
        verdict = pooled.get("verdict", "-")
        for inst in body["instruments"]:
            l1 = cr["layer1_g001"].get(inst, {})
            if "error" in l1:
                safe_print(f"| {cid:16s} | {inst:8s} | {'ERR':>6s} | {'-':>9s} | "
                           f"{'-':>9s} | {'-':>7s} | {verdict:10s} |")
                continue
            d = cr["delta_g001_vs_baseline"].get(inst, {})
            de = d.get("d_expectancy_r", 0.0)
            safe_print(f"| {cid:16s} | {inst:8s} | {l1.get('approved_trades',0):6d} | "
                       f"{l1.get('expectancy_r',0.0):+9.4f} | {de:+9.4f} | "
                       f"{cr['entry_counts'].get(inst,0):7d} | {verdict:10s} |")
    promoted = [f"{cid}@{sc}"
                for cid, cr in body["cells"].items()
                for sc, r in cr["layer2_m4"].items()
                if r.get("verdict") == "PROMOTE"]
    safe_print(f"\nM4 PROMOTE: {promoted or 'none'}")


if __name__ == "__main__":
    raise SystemExit(main())
