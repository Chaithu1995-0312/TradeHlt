# -*- coding: utf-8 -*-
"""qualify_xauusd.py — thin, NON-PROMOTABLE M4 research pass on the certified XAUUSD corpus (ERP T1).

XAUUSD is deliberately excluded from qualify_fx_metals.py, so this runs it directly through the
isolated research stack over the ONLY approved load target — the Phase-1 frozen candidate
`data/mt5/XAUUSD_M15.csv` (resolved via guard_xauusd_csv_path). Two families, mirroring qualify_fx_metals:

  * toy   — expansion_breakout / mean_reversion  (research_config_fx_metals.json; apply_signal_defaults=true)
  * spine — the production decision spine v2_multi_2026_04 as the `spine` hypothesis
            (research_config_spine_xauusd.json; apply_signal_defaults=false; read by ProductionSpineSource)

Reuses the VERBATIM M4 gate math (research.qualification) + HypothesisRunner + forward_walk(intrabar_fixed).

TRUST: the corpus is FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION (NOT economically admissible). Output is
UNTRUSTED_RAW and NON-PROMOTABLE. NO edge claim; verdicts (REJECT/INSUFFICIENT expected, cf. F-035/F-029)
recorded as-is. The spine lens depends on `.env BACKTEST_ENGINE_GATE` (F-037: 0 => CRT-only) — recorded,
never misstated. Measure-only: no optimization, no promotion, no config/spine/ACTIVE_VERSION edits.

Usage:
  python scripts/research/qualify_xauusd.py                         # toy + spine
  python scripts/research/qualify_xauusd.py --family toy            # toy only
  python scripts/research/qualify_xauusd.py --family spine          # spine only (full backtest, slow)
  python scripts/research/qualify_xauusd.py --permutations 300
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

import research.controls    # noqa: F401,E402  (register controls)
import research.hypotheses  # noqa: F401,E402  (register hypotheses, incl. spine)
from data_ingestion.xauusd_phase1_candidate import (  # noqa: E402
    PHASE1_STATUS, authority_status_note, guard_xauusd_csv_path,
)
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
from utils.run_manifest import build_manifest, write_run         # noqa: E402

INSTRUMENT = "XAUUSD"
TOY_CONFIG = "configs/research/research_config_fx_metals.json"
SPINE_CONFIG = "configs/research/research_config_spine_xauusd.json"
TOY_CANDIDATES = ["expansion_breakout", "mean_reversion"]
SPINE_CANDIDATES = ["spine"]
PROD_VERSION = "v2_multi_2026_04"
RUNS_DIR = _ROOT / "results" / "test_runs"


def _guarded_csv_map() -> dict[str, str]:
    """The ONLY approved XAUUSD load — the frozen candidate (NOT the root/glob)."""
    return {INSTRUMENT: guard_xauusd_csv_path("data/XAUUSD_M15.csv", INSTRUMENT)}


def _winning_control(per_by_hyp, control_names, agg, cost):
    win_name, win_rrs, win_exp = "none", [], float("-inf")
    for name in sorted(control_names):
        outs = per_by_hyp[name].get(INSTRUMENT, [])
        rrs = _net_rrs(outs, cost)
        rep = agg.aggregate(name, [INSTRUMENT], outs, cost_model=cost)
        if rep.expectancy_rr > win_exp:
            win_name, win_rrs, win_exp = name, rrs, rep.expectancy_rr
    if win_exp == float("-inf"):
        win_name, win_rrs, win_exp = "none", [], 0.0
    return win_name, win_rrs, win_exp


def _run_family(candidates, permutations, csv_map, *, is_spine: bool) -> tuple[ResearchConfig, dict]:
    cfg_path = SPINE_CONFIG if is_spine else TOY_CONFIG
    if is_spine:
        # ProductionSpineSource reads spine.prod_version/universe from THIS config; pin it. The spine
        # source loads via its own _resolve_csv -> CandleLoader guard -> the SAME frozen candidate, and
        # indexes entries against the FULL corpus, so the spine family always uses the full guarded map
        # (never a truncated slice) to keep index alignment.
        os.environ["RESEARCH_SPINE_CONFIG"] = SPINE_CONFIG
        csv_map = _guarded_csv_map()
    else:
        csv_map = csv_map or _guarded_csv_map()

    cfg = ResearchConfig.from_file(cfg_path)
    runner = HypothesisRunner(cfg)
    cost = CostModel(cfg.round_trip_bps)
    agg = EdgeAggregator()
    qcfg = QualConfig.from_research_config(cfg)
    if permutations is not None:
        qcfg = dataclasses.replace(qcfg, n_permutations=permutations)

    control_names = sorted(n for n, h in HYPOTHESIS_REGISTRY.items() if h.family == "control")
    per_by_hyp = {name: runner.collect(name, csv_map) for name in candidates + control_names}
    win_name, win_rrs, win_exp = _winning_control(per_by_hyp, control_names, agg, cost)

    states = {}
    for name in candidates:
        outs = per_by_hyp[name].get(INSTRUMENT, [])
        report = agg.aggregate(name, [INSTRUMENT], outs, cost_model=cost)
        states[name] = evaluate_pre_bh(report, {INSTRUMENT: outs},
                                       win_name, win_rrs, win_exp, qcfg, cost)
    bh_inputs = {n: st.p_value for n, st in states.items() if st.passed_1_to_6}
    bh_survivors = benjamini_hochberg(bh_inputs, qcfg.significance_alpha)
    finals = {n: dataclasses.asdict(finalize(st, bh_survivors, qcfg)) for n, st in states.items()}

    family = {
        "config_path": cfg_path,
        "config_sha256": cfg.sha256(),
        "permutation_count": qcfg.n_permutations,
        "winning_control": win_name,
        "winning_control_exp": round(win_exp, 6),
        "hypotheses": {n: finals[n] for n in sorted(finals)},
    }
    if is_spine:
        family["prod_version"] = PROD_VERSION
    return cfg, family


def run(permutations: int | None = None, csv_map: dict[str, str] | None = None,
        family: str = "both") -> dict:
    """Run the XAUUSD toy and/or spine family M4 pass. Returns the deterministic report doc.

    `csv_map` (toy only) may be a truncated slice of the guarded corpus for a fast plumbing SMOKE; the
    spine family ALWAYS uses the full guarded corpus (index alignment with ProductionSpineSource).
    """
    families: dict[str, dict] = {}
    base_cfg: ResearchConfig | None = None
    if family in ("toy", "both"):
        base_cfg, families["toy"] = _run_family(TOY_CANDIDATES, permutations, csv_map, is_spine=False)
    if family in ("spine", "both"):
        cfg, families["spine"] = _run_family(SPINE_CANDIDATES, permutations, None, is_spine=True)
        base_cfg = base_cfg or cfg

    gate = os.environ.get("BACKTEST_ENGINE_GATE")
    lens = ("crt_only_gate_off" if gate == "0"
            else "fusion_gate_on" if gate in ("1", "true", "True")
            else f"gate_{gate}")
    return {
        "qualification_version": QUALIFICATION_VERSION,
        "permutation_method_version": PERMUTATION_METHOD_VERSION,
        "bh_method_version": BH_METHOD_VERSION,
        "alpha": QualConfig.from_research_config(base_cfg).significance_alpha,
        "universe": [INSTRUMENT],
        "corpus_path": _guarded_csv_map()[INSTRUMENT].replace("\\", "/"),
        "corpus_status": PHASE1_STATUS,
        "non_promotable": True,
        "validation_lens": lens,
        "backtest_engine_gate": gate,
        "authority_note": authority_status_note(),
        **provenance_block(base_cfg.exit_model, base_cfg.round_trip_bps),
        "families": families,
    }


def _print_table(doc: dict) -> None:
    safe_print(f"\nQUALIFY-XAUUSD (NON-PROMOTABLE; {doc['corpus_status']}; lens={doc['validation_lens']}) "
               f"— intrabar_fixed, {doc.get('round_trip_bps', '?')}bps; alpha={doc['alpha']}\n")
    safe_print(f"| {'Family':6s} | {'Hypothesis':18s} | {'n':>7s} | {'PF':>8s} | {'E(net)':>9s} | {'p':>8s} | {'Verdict':12s} |")
    promoted = []
    for fam in ("toy", "spine"):
        if fam not in doc["families"]:
            continue
        for name, r in doc["families"][fam]["hypotheses"].items():
            safe_print(f"| {fam:6s} | {name:18s} | {r['n']:7d} | {r['profit_factor']:8.3f} | "
                       f"{r['expectancy_rr']:+9.4f} | {r['p_value']:8.4f} | {r['verdict']:12s} |")
            if r["verdict"] == "PROMOTE":
                promoted.append(f"{fam}:{name}")
    safe_print(f"\nPROMOTE: {promoted or 'none'}   (research-only; no edge claim)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="qualify_xauusd",
                                 description="Non-promotable M4 research pass on the XAUUSD frozen candidate")
    ap.add_argument("--family", choices=["toy", "spine", "both"], default="both")
    ap.add_argument("--permutations", type=int, default=None, help="override permutation budget")
    ap.add_argument("--out", default="results/research/qualification_xauusd")
    args = ap.parse_args(argv)

    doc = run(permutations=args.permutations, family=args.family)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "qualify_xauusd.json").write_text(json.dumps(doc, sort_keys=True, indent=2), encoding="utf-8")

    verdicts = {fam: {n: r["verdict"] for n, r in doc["families"][fam]["hypotheses"].items()}
                for fam in doc["families"]}
    assertions = {
        "non_promotable": True,
        "corpus_status": doc["corpus_status"],
        "validation_lens": doc["validation_lens"],
        "backtest_engine_gate": doc["backtest_engine_gate"],
        "prod_version": PROD_VERSION if "spine" in doc["families"] else None,
        "verdicts": verdicts,
        "note": "UNTRUSTED_RAW research pass on a FROZEN_CANDIDATE corpus; no edge/economic claim (D-04, §6.5)",
    }
    manifest = build_manifest(
        command="python scripts/research/qualify_xauusd.py",
        argv=sys.argv,
        validation_lens=doc["validation_lens"],
        exit_model="intrabar_fixed",
        cost_model_bps=int(doc.get("round_trip_bps", 12)),
        label_source="forward_walk_intrabar_fixed",
        instruments=[INSTRUMENT],
        timeframe="M15",
        data_source="local_csv_mt5",
        network="none",
        dry_run=True,
        intended_work_item_id="WI-004",
    )
    run_dir = RUNS_DIR / manifest["run_id"]
    write_run(run_dir, manifest, assertions)

    _print_table(doc)
    safe_print(f"\n-> {out_dir / 'qualify_xauusd.json'}  | manifest -> {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
