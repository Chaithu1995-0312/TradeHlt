# -*- coding: utf-8 -*-
"""
qualify_htf.py — Program 3: higher-timeframe (H1/H4) M4 qualification (thin CLI).

Self-contained sibling of qualify_majors.py. Reuses the SAME audited M4 core
(research.qualification: evaluate_pre_bh / benjamini_hochberg / finalize) and
HypothesisRunner VERBATIM — adds NO statistics. It only re-scopes the existing pooled
QualificationGate over the crypto majors on RESAMPLED higher-timeframe data:

    [BNBUSDT, ETHUSDT, BTCUSDT, SOLUSDT, POOLED]   (per-instrument first, pooled last)

over the same two config families as qualify_majors (toy needs apply_signal_defaults=true,
spine needs false), but pointed at configs/research/research_config_htf_majors.json /
research_config_spine_htf_majors.json and the data/resampled/{INST}_{TF}.csv universe.

This is a NEW horizon ontology (Program 3), NOT a Program-1 parameter pass. Horizon mode =
BAR_COUNT_CONSTANT (Program 3A): harness bar-counts are held constant across timeframes.

MEASURE-ONLY — no optimization, no new hypotheses, no promotion, no spine/config edits.
Deterministic JSON body (NO wall-clock); the manifest (timestamp / git) is written separately.

Prerequisite: run scripts/research/build_resampled_data.py first.

Usage:
    python scripts/research/qualify_htf.py --tf H1
    python scripts/research/qualify_htf.py --tf H4 --out results/research/qualification_htf
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

TOY_CONFIG = "configs/research/research_config_htf_majors.json"
SPINE_CONFIG = "configs/research/research_config_spine_htf_majors.json"
TOY_CANDIDATES = ["expansion_breakout", "mean_reversion"]
SPINE_CANDIDATES = ["spine"]
HORIZON_MODE = "BAR_COUNT_CONSTANT"   # Program 3A


def _csv_map(cfg: ResearchConfig, instruments: list[str], tf: str) -> dict[str, str]:
    """Build {instrument: csv} from the resampled universe, substituting {TF} in pattern."""
    data_dir = Path(cfg.data_dir)
    pattern = cfg.pattern.replace("{TF}", tf)
    keep = set(instruments)
    out: dict[str, str] = {}
    for p in sorted(data_dir.glob(pattern)):
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


def _resolve_config(cfg_path: str, tf: str, out_dir: Path) -> tuple[dict, str]:
    """Substitute {TF} in universe.pattern and write a resolved config to disk.

    Both the runner's _csv_map AND the spine source (ProductionSpineSource, which globs
    universe.pattern itself) consume a concrete pattern this way, and the resolved config's
    sha256 honestly reflects the per-TF universe. Deterministic location, inspectable."""
    d = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    d["universe"]["pattern"] = d["universe"]["pattern"].replace("{TF}", tf)
    resolved_dir = out_dir / "_resolved"
    resolved_dir.mkdir(parents=True, exist_ok=True)
    resolved_path = resolved_dir / f"{Path(cfg_path).stem}__{tf}.json"
    resolved_path.write_text(json.dumps(d, indent=2, sort_keys=True), encoding="utf-8")
    return d, str(resolved_path)


def _run_family(cfg_path: str, candidate_names: list[str], tf: str, out_dir: Path) -> tuple[ResearchConfig, dict]:
    # Resolve {TF} -> concrete pattern and pin RESEARCH_SPINE_CONFIG at the resolved file so the
    # spine source (which self-globs universe.pattern) and ResearchConfig agree on the universe.
    resolved_dict, resolved_path = _resolve_config(cfg_path, tf, out_dir)
    os.environ["RESEARCH_SPINE_CONFIG"] = resolved_path
    cfg = ResearchConfig.from_dict(resolved_dict)
    runner = HypothesisRunner(cfg)
    cost = CostModel(cfg.round_trip_bps)
    agg = EdgeAggregator()
    qcfg = QualConfig.from_research_config(cfg)

    csv_map = _csv_map(cfg, MAJORS, tf)
    if not csv_map:
        raise SystemExit(
            f"No CSVs matched {cfg.pattern.replace('{TF}', tf)} in {cfg.data_dir} for {MAJORS}. "
            f"Run scripts/research/build_resampled_data.py first.")
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
    tf = report_doc["timeframe"]
    safe_print(f"\nQUALIFY-HTF [{tf}, {report_doc['horizon_mode']}] — per-instrument first, pooled last "
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
        prog="qualify_htf",
        description="Program 3: higher-timeframe M4 qualification of the existing hypothesis pool")
    parser.add_argument("--tf", required=True, choices=["H1", "H4"], help="resampled timeframe")
    parser.add_argument("--out", default="results/research/qualification_htf")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    toy_cfg, toy_family = _run_family(TOY_CONFIG, TOY_CANDIDATES, args.tf, out_dir)

    # Spine arm: throughput-starved at HTF (fewer CRT events on coarser bars) AND its adapter's
    # INDEX CONTRACT (`candle_idx-1 == research stream position`, spine_signal_source.py) assumes
    # M15-native `candle_open` indexing that does NOT hold for RESAMPLED candles. Rather than hack
    # the production spine adapter from a research driver, record the arm as NOT_MEASURABLE with the
    # reason when the contract breaks — the decisive TOY arm (n=2k-22k) is unaffected and a spine
    # PROMOTE is impossible at HTF n<30 regardless. Surfaced, never hidden.
    spine_status, spine_err = "MEASURED", ""
    try:
        spine_cfg, spine_family = _run_family(SPINE_CONFIG, SPINE_CANDIDATES, args.tf, out_dir)
    except Exception as ex:   # noqa: BLE001 — record any spine-adapter failure as a measurement caveat
        spine_status, spine_err = "NOT_MEASURABLE", f"{type(ex).__name__}: {ex}"
        spine_cfg = ResearchConfig.from_dict(_resolve_config(SPINE_CONFIG, args.tf, out_dir)[0])
        spine_family = {
            sc: {"winning_control": "n/a", "winning_control_exp": 0.0,
                 "hypotheses": {n: {"n": 0, "profit_factor": 0.0, "expectancy_rr": 0.0,
                                    "p_value": 1.0, "verdict": "NOT_MEASURABLE",
                                    "reject_reasons": [spine_err]} for n in SPINE_CANDIDATES}}
            for sc in SCOPES
        }

    # Deterministic body — NO wall-clock; safe to byte-compare across runs.
    report_doc = {
        "program": "Program 3 — Higher-Timeframe Directional Ontology",
        "timeframe": args.tf,
        "horizon_mode": HORIZON_MODE,
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
                "status": spine_status,
                "status_reason": spine_err,
                **spine_family,
            },
        },
    }

    body_path = out_dir / f"qualify_htf_{args.tf}.json"
    body_path.write_text(json.dumps(report_doc, sort_keys=True, indent=2), encoding="utf-8")
    # Wall-clock / environment provenance lives separately (keeps the body byte-comparable).
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "timeframe": args.tf,
        "toy_config_sha256": toy_cfg.sha256(),
        "spine_config_sha256": spine_cfg.sha256(),
    }
    (out_dir / f"qualify_htf_{args.tf}_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")

    _print_table(report_doc)
    safe_print(f"\n-> {body_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
