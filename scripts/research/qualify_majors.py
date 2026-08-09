# -*- coding: utf-8 -*-
"""
qualify_majors.py — "Run the Gate First": cross-instrument M4 qualification (thin CLI).

Reuses the M4 gate math in research.qualification VERBATIM (evaluate_pre_bh /
benjamini_hochberg / finalize) and HypothesisRunner. It adds NO statistics — it only
re-scopes the existing pooled QualificationGate over

    [BNBUSDT, ETHUSDT, BTCUSDT, SOLUSDT, POOLED]   (per-instrument first, pooled last)

and over two config families that cannot share a single invocation because they need
incompatible `apply_signal_defaults` (spine carries its own SL/TP geometry; toys do not):

  * toy family   — configs/research/research_config_majors.json        (apply_signal_defaults=true)
        candidates: expansion_breakout, mean_reversion   vs falsification controls
  * spine family — configs/research/research_config_spine_majors.json   (apply_signal_defaults=false)
        candidate:  spine (production composite, prod_version=v2_multi_2026_04) vs controls

Per (scope, family) the WINNING control is recomputed UNDER THAT FAMILY'S config (a fair
gate-4 beats-control / gate-6 permutation baseline), then gates 1-6 + cohort BH (gate 7)
run exactly as in cli.cmd_qualify. Per-instrument outcomes are computed once per hypothesis
(so the spine backtest runs once per instrument, not once per scope).

MEASURE-ONLY — no optimization, no new hypotheses, no promotion, no spine/config edits.
The deterministic JSON body carries NO wall-clock (matches the edge_report discipline); the
run manifest (timestamp / git) is written separately.

Usage:
    python scripts/research/qualify_majors.py
    python scripts/research/qualify_majors.py --out results/research/qualification
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import research.controls    # noqa: F401  (register controls)
import research.hypotheses  # noqa: F401  (register hypotheses, incl. spine)
from research.config import ResearchConfig                       # noqa: E402
from research.costs import CostModel                             # noqa: E402
from research.measurement.metrics import EdgeAggregator          # noqa: E402
from research.provenance import provenance_block                 # noqa: E402
from research.qualification import (                             # noqa: E402
    BH_METHOD_VERSION, PERMUTATION_METHOD_VERSION, QUALIFICATION_VERSION,
    QualConfig, benjamini_hochberg, evaluate_pre_bh, finalize, _net_rrs,
)
from research.registry import HYPOTHESIS_REGISTRY                # noqa: E402
from research.runner import HypothesisRunner                     # noqa: E402
from utils.console_safe import safe_print                        # noqa: E402

MAJORS = ["BNBUSDT", "ETHUSDT", "BTCUSDT", "SOLUSDT"]
SCOPES = MAJORS + ["POOLED"]   # per-instrument first, pooled last (load-bearing order)

TOY_CONFIG = "configs/research/research_config_majors.json"
SPINE_CONFIG = "configs/research/research_config_spine_majors.json"
TOY_CANDIDATES = ["expansion_breakout", "mean_reversion"]
SPINE_CANDIDATES = ["spine"]


def _csv_map(cfg: ResearchConfig, instruments: list[str]) -> dict[str, str]:
    data_dir = Path(cfg.data_dir)
    keep = set(instruments)
    out: dict[str, str] = {}
    for p in sorted(data_dir.glob(cfg.pattern)):
        inst = p.stem.split("_")[0]
        if inst in keep:
            out[inst] = str(p)
    return out


def _winning_control(per_by_hyp, control_names, scope_instruments, agg, cost):
    """Highest pooled NET-expectancy control over the scope (== cli.cmd_qualify semantics)."""
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


def _run_family(cfg_path: str, candidate_names: list[str]) -> tuple[ResearchConfig, dict]:
    # The spine source reads prod_version/universe from THIS config (via RESEARCH_SPINE_CONFIG);
    # pin it so the spine family measures v2_multi_2026_04 (no-op for the toy family).
    os.environ["RESEARCH_SPINE_CONFIG"] = cfg_path
    cfg = ResearchConfig.from_file(cfg_path)
    runner = HypothesisRunner(cfg)
    cost = CostModel(cfg.round_trip_bps)
    agg = EdgeAggregator()
    qcfg = QualConfig.from_research_config(cfg)

    csv_map = _csv_map(cfg, MAJORS)
    if not csv_map:
        raise SystemExit(f"No CSVs matched {cfg.pattern} in {cfg.data_dir} for {MAJORS}")
    control_names = sorted(n for n, h in HYPOTHESIS_REGISTRY.items() if h.family == "control")

    # Compute per-instrument outcomes ONCE per hypothesis (spine backtest runs once/instrument).
    per_by_hyp: dict[str, dict] = {}
    for name in list(candidate_names) + control_names:
        per_by_hyp[name] = runner.collect(name, csv_map)

    family: dict[str, dict] = {}
    for scope in SCOPES:
        wanted = MAJORS if scope == "POOLED" else [scope]
        scope_instruments = [i for i in wanted if i in csv_map]
        win_name, win_rrs, win_exp = _winning_control(
            per_by_hyp, control_names, scope_instruments, agg, cost)

        states = {}
        for name in candidate_names:
            per = {i: per_by_hyp[name][i] for i in scope_instruments}
            report = agg.aggregate(name, sorted(scope_instruments),
                                   [o for outs in per.values() for o in outs], cost_model=cost)
            states[name] = evaluate_pre_bh(report, per, win_name, win_rrs, win_exp, qcfg, cost)

        bh_inputs = {n: st.p_value for n, st in states.items() if st.passed_1_to_6}
        bh_survivors = benjamini_hochberg(bh_inputs, qcfg.significance_alpha)
        finals = {n: finalize(st, bh_survivors, qcfg) for n, st in states.items()}

        family[scope] = {
            "winning_control": win_name,
            "winning_control_exp": round(win_exp, 6),
            "hypotheses": {n: dataclasses.asdict(finals[n]) for n in sorted(finals)},
        }
    return cfg, family


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _print_table(report_doc: dict) -> None:
    safe_print("\nQUALIFY-MAJORS — per-instrument first, pooled last "
               "(intrabar_fixed, 12bps; alpha=0.05)\n")
    header = f"| {'Hypothesis':18s} | {'Instrument':10s} | {'n':>7s} | {'PF':>8s} | {'E(net)':>9s} | {'p':>8s} | {'Verdict':12s} |"
    sep = "|" + "-" * 20 + "|" + "-" * 12 + "|" + "-" * 9 + "|" + "-" * 10 + "|" + "-" * 11 + "|" + "-" * 10 + "|" + "-" * 14 + "|"
    safe_print(header)
    safe_print(sep)
    for fam_key in ("toy", "spine"):
        fam = report_doc["families"][fam_key]
        cand_names = sorted({n for sc in SCOPES for n in fam[sc]["hypotheses"]})
        for name in cand_names:
            for scope in SCOPES:
                r = fam[scope]["hypotheses"][name]
                safe_print(
                    f"| {name:18s} | {scope:10s} | {r['n']:7d} | {r['profit_factor']:8.3f} | "
                    f"{r['expectancy_rr']:+9.4f} | {r['p_value']:8.4f} | {r['verdict']:12s} |")
        safe_print(sep)
    promoted = [
        f"{fam_key}:{name}@{scope}"
        for fam_key in ("toy", "spine")
        for scope in SCOPES
        for name, r in report_doc["families"][fam_key][scope]["hypotheses"].items()
        if r["verdict"] == "PROMOTE"
    ]
    safe_print(f"\nPROMOTE: {promoted or 'none'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="qualify_majors",
        description="Cross-instrument M4 qualification of the existing hypothesis pool (crypto majors)")
    parser.add_argument("--out", default="results/research/qualification")
    args = parser.parse_args(argv)

    toy_cfg, toy_family = _run_family(TOY_CONFIG, TOY_CANDIDATES)
    spine_cfg, spine_family = _run_family(SPINE_CONFIG, SPINE_CANDIDATES)

    # Deterministic body — NO wall-clock; safe to byte-compare across runs.
    report_doc = {
        "qualification_version": QUALIFICATION_VERSION,
        "permutation_method_version": PERMUTATION_METHOD_VERSION,
        "permutation_count": toy_cfg.q_n_permutations,
        "bh_method_version": BH_METHOD_VERSION,
        "alpha": toy_cfg.q_significance_alpha,
        "scope_order": SCOPES,
        "majors": MAJORS,
        **provenance_block(toy_cfg.exit_model, toy_cfg.round_trip_bps),
        "families": {
            "toy": {
                "config_path": TOY_CONFIG,
                "config_sha256": toy_cfg.sha256(),
                **toy_family,
            },
            "spine": {
                "config_path": SPINE_CONFIG,
                "config_sha256": spine_cfg.sha256(),
                "prod_version": "v2_multi_2026_04",
                **spine_family,
            },
        },
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "qualify_majors.json").write_text(
        json.dumps(report_doc, sort_keys=True, indent=2), encoding="utf-8")
    # Wall-clock / environment provenance lives separately (keeps the body byte-comparable).
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "toy_config_sha256": toy_cfg.sha256(),
        "spine_config_sha256": spine_cfg.sha256(),
    }
    (out_dir / "qualify_majors_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")

    _print_table(report_doc)
    safe_print(f"\n-> {out_dir / 'qualify_majors.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
