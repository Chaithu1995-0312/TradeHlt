"""cli.py — thin entrypoint for the research harness.

    python -m research.cli run --hypothesis ALL --config configs/research/research_config.json

Business logic lives in HypothesisRunner; this only wires argparse → runner → disk.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Importing these packages registers controls + hypotheses via their decorators.
import research.controls   # noqa: F401
import research.hypotheses  # noqa: F401
from research.config import DEFAULT_CONFIG_PATH, ResearchConfig
from research.registry import HYPOTHESIS_REGISTRY, get_hypothesis
from research.runner import HypothesisRunner, edge_report_json, run_result_to_dict
from research.provenance import provenance_block
from research.measurement.metrics import EdgeAggregator
from research.costs import CostModel
from research.qualification import (
    BH_METHOD_VERSION,
    PERMUTATION_METHOD_VERSION,
    QUALIFICATION_VERSION,
    QualConfig,
    benjamini_hochberg,
    evaluate_pre_bh,
    finalize,
    _net_rrs,
)
import dataclasses


def _build_csv_map(cfg: ResearchConfig) -> dict[str, str]:
    data_dir = Path(cfg.data_dir)
    paths = sorted(data_dir.glob(cfg.pattern))
    csv_map: dict[str, str] = {}
    for p in paths:
        instrument = p.stem.split("_")[0]               # BTCUSDT_M15 -> BTCUSDT
        csv_map[instrument] = str(p)
    if isinstance(cfg.instruments, list):
        csv_map = {k: v for k, v in csv_map.items() if k in set(cfg.instruments)}
    return csv_map


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _which_hypotheses(arg: str, include_controls: bool) -> list[str]:
    if arg != "ALL":
        return [arg]
    names = []
    for name, hyp in sorted(HYPOTHESIS_REGISTRY.items()):
        if hyp.family == "control" and not include_controls:
            continue
        names.append(name)
    return names


def cmd_run(args: argparse.Namespace) -> int:
    # The spine hypothesis' ProductionSpineSource reads its prod_version from the SAME config
    # file the run uses; pin it so `--config` is authoritative (no-op for non-spine hypotheses).
    import os
    os.environ["RESEARCH_SPINE_CONFIG"] = str(args.config)
    cfg = ResearchConfig.from_file(args.config)
    csv_map = _build_csv_map(cfg)
    if not csv_map:
        print(f"No CSVs matched {cfg.pattern} in {cfg.data_dir}")
        return 1

    runner = HypothesisRunner(cfg)
    out_root = Path(args.out)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    for name in _which_hypotheses(args.hypothesis, args.controls):
        rr = runner.run(name, csv_map)
        out_dir = out_root / name / run_id
        out_dir.mkdir(parents=True, exist_ok=True)

        # Deterministic artifact (no wall-clock) — safe to byte-compare across runs.
        (out_dir / "edge_report.json").write_text(edge_report_json(rr), encoding="utf-8")
        # Wall-clock / environment provenance lives separately.
        manifest = {
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git_commit(),
            "hypothesis": name,
            "config_path": str(args.config),
            "config_sha256": rr.config_sha256,
            "hypothesis_sha256": rr.hypothesis_sha256,
            "instruments": sorted(csv_map),
        }
        (out_dir / "run_manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")

        # §13 item6 / §14.D — measure-only G001 gap report, written SEPARATELY from
        # edge_report.json (which must stay wall-clock-free / byte-comparable across
        # runs, matching run_manifest.json's precedent for anything with a duration
        # or timestamp dependency). Best-effort per instrument: a corpus whose
        # timestamp column can't be parsed just SKIPs trades_per_month for that
        # instrument rather than failing the whole run.
        try:
            from research.goal_alignment import corpus_span_months, goal_report_for_edge
            months_by_instrument = {}
            for instr, csv_path in csv_map.items():
                try:
                    months_by_instrument[instr] = corpus_span_months(csv_path)
                except Exception:
                    months_by_instrument[instr] = None
            pooled_months = next(iter(m for m in months_by_instrument.values() if m), None)
            goal_doc = {
                "pooled": goal_report_for_edge(rr.pooled, pooled_months),
                "per_instrument": {
                    instr: goal_report_for_edge(edge, months_by_instrument.get(instr))
                    for instr, edge in sorted(rr.per_instrument.items())
                },
            }
            (out_dir / "goal_report.json").write_text(
                json.dumps(goal_doc, sort_keys=True, indent=2), encoding="utf-8")
        except Exception as _goal_exc:  # noqa: BLE001
            logging.getLogger("research.cli").warning(
                "goal_report.json generation failed (non-blocking): %s", _goal_exc
            )

        p = rr.pooled
        print(f"[{name:20s}] pooled n={p.n:6d} WR={p.win_rate:.3f} "
              f"PF(net)={p.profit_factor:7.3f} E(net)={p.expectancy_rr:+.4f} "
              f"-> {out_dir / 'edge_report.json'}")
    return 0


def cmd_qualify(args: argparse.Namespace) -> int:
    import os
    os.environ["RESEARCH_SPINE_CONFIG"] = str(args.config)   # see cmd_run note
    cfg = ResearchConfig.from_file(args.config)
    csv_map = _build_csv_map(cfg)
    if not csv_map:
        print(f"No CSVs matched {cfg.pattern} in {cfg.data_dir}")
        return 1

    runner = HypothesisRunner(cfg)
    cost = CostModel(cfg.round_trip_bps)
    agg = EdgeAggregator()
    qcfg = QualConfig.from_research_config(cfg)

    # Controls form the falsification baseline. The WINNING control (highest pooled
    # NET expectancy) is the benchmark every hypothesis must beat (gate 4) + the
    # permutation null (gate 6).
    control_names = sorted(n for n, h in HYPOTHESIS_REGISTRY.items() if h.family == "control")
    win_name, win_rrs, win_exp = "none", [], float("-inf")
    for name in control_names:
        per = runner.collect(name, csv_map)
        rrs = []
        for outs in per.values():
            rrs.extend(_net_rrs(outs, cost))
        rep = agg.aggregate(name, sorted(csv_map), [o for outs in per.values() for o in outs],
                            cost_model=cost)
        if rep.expectancy_rr > win_exp:
            win_name, win_rrs, win_exp = name, rrs, rep.expectancy_rr
    if win_exp == float("-inf"):
        win_name, win_rrs, win_exp = "none", [], 0.0

    # Candidate hypotheses (non-controls). Gates 1–6 per hypothesis, then cohort BH.
    hyp_names = [n for n, h in sorted(HYPOTHESIS_REGISTRY.items()) if h.family != "control"]
    states = {}
    for name in hyp_names:
        per = runner.collect(name, csv_map)
        report = agg.aggregate(name, sorted(csv_map),
                               [o for outs in per.values() for o in outs], cost_model=cost)
        states[name] = evaluate_pre_bh(report, per, win_name, win_rrs, win_exp, qcfg, cost)

    bh_inputs = {n: st.p_value for n, st in states.items() if st.passed_1_to_6}
    bh_survivors = benjamini_hochberg(bh_inputs, qcfg.significance_alpha)

    finals = {n: finalize(st, bh_survivors, qcfg) for n, st in states.items()}

    report_doc = {
        "qualification_version": QUALIFICATION_VERSION,
        "permutation_method_version": PERMUTATION_METHOD_VERSION,
        "permutation_count": qcfg.n_permutations,   # method vs count, separated
        "bh_method_version": BH_METHOD_VERSION,
        **provenance_block(cfg.exit_model, cfg.round_trip_bps),
        "config_sha256": cfg.sha256(),
        "winning_control": win_name,
        "alpha": qcfg.significance_alpha,
        "hypotheses": {n: dataclasses.asdict(finals[n]) for n in sorted(finals)},
    }
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "qualification_report.json").write_text(
        json.dumps(report_doc, sort_keys=True, indent=2), encoding="utf-8")

    print(f"winning_control={win_name} (E[R]={win_exp:+.4f})  alpha={qcfg.significance_alpha}")
    for n in sorted(finals):
        r = finals[n]
        nearest = r.reject_reasons[0] if r.reject_reasons else ""
        print(f"  [{r.verdict:11s}] {n:20s} n={r.n:6d} PF={r.profit_factor:7.3f} "
              f"E={r.expectancy_rr:+.4f} p={r.p_value:.4f} {nearest}")
    promoted = [n for n in finals if finals[n].verdict == "PROMOTE"]
    print(f"\nPROMOTE: {promoted or 'none'}  -> {out_dir / 'qualification_report.json'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="research", description="Edge Discovery research harness")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="run a hypothesis (or ALL) across the universe")
    run_p.add_argument("--hypothesis", default="ALL",
                       help="hypothesis name or ALL (default: ALL registered)")
    run_p.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    run_p.add_argument("--out", default="results/research")
    run_p.add_argument("--controls", action="store_true",
                       help="include falsification controls when --hypothesis ALL")
    run_p.set_defaults(func=cmd_run)

    q_p = sub.add_parser("qualify", help="M4: run the 7-gate QualificationGate over all hypotheses")
    q_p.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    q_p.add_argument("--out", default="results/research/qualification")
    q_p.set_defaults(func=cmd_qualify)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
