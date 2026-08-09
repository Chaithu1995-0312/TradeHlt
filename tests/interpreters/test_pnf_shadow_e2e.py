"""
test_pnf_shadow_e2e.py — PNF-v1 shadow chain proof on REAL data (Plan 5).

Proves the first REAL interpreter runs through the unchanged chain
(InterpreterHypothesis → HypothesisRunner → forward_walk → QualificationGate) and is
measured honestly. PROMOTE is NOT expected (PNF-v1 was REJECTed vs random controls);
the assertions check the chain RUNS, returns a verdict, and is sha256-deterministic.

Skips if the real data file is absent.

Run: python -m pytest tests/interpreters/test_pnf_shadow_e2e.py -q
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_DATA = _ROOT / "data" / "BNBUSDT_M15.csv"
_CFG = _ROOT / "configs" / "research" / "research_config.json"
pytestmark = pytest.mark.skipif(
    not (_DATA.exists() and _CFG.exists()),
    reason="real BNBUSDT_M15.csv / research_config.json not present",
)

import research.controls           # noqa: F401,E402  — register controls for the gate
from research.config import ResearchConfig                              # noqa: E402
from research.costs import CostModel                                    # noqa: E402
from research.measurement.metrics import EdgeAggregator                 # noqa: E402
from research.qualification import (                                    # noqa: E402
    QualConfig, _net_rrs, benjamini_hochberg, evaluate_pre_bh, finalize,
)
from research.registry import HYPOTHESIS_REGISTRY, register_hypothesis  # noqa: E402
from research.runner import HypothesisRunner, run_result_to_dict        # noqa: E402

from interpreters.adapter import InterpreterHypothesis                  # noqa: E402
from interpreters.point_and_figure import PointAndFigureInterpreter     # noqa: E402

_INST = "BNBUSDT"


def _candidate():
    name = "interp:pnf"
    if name in HYPOTHESIS_REGISTRY:
        return HYPOTHESIS_REGISTRY[name]
    cand = InterpreterHypothesis(PointAndFigureInterpreter())
    register_hypothesis(cand)
    return cand


def _cfg() -> ResearchConfig:
    return dataclasses.replace(ResearchConfig.from_file(str(_CFG)), apply_signal_defaults=False)


def test_pnf_chain_runs_on_real_data():
    cand = _candidate()
    rr = HypothesisRunner(_cfg()).run(cand.name, {_INST: str(_DATA)})
    rep = rr.pooled
    assert rep.n > 0
    for v in (rep.win_rate, rep.expectancy_rr, rep.max_drawdown_rr):
        assert math.isfinite(v)


def test_pnf_qualification_returns_verdict_not_promote():
    cand = _candidate()
    cfg = _cfg()
    runner = HypothesisRunner(cfg)
    cost = CostModel(cfg.round_trip_bps)
    agg = EdgeAggregator()
    qcfg = QualConfig.from_research_config(cfg)
    csv_map = {_INST: str(_DATA)}

    per = runner.collect(cand.name, csv_map)
    control_names = sorted(n for n, h in HYPOTHESIS_REGISTRY.items() if h.family == "control")
    win_name, win_rrs, win_exp = "none", [], float("-inf")
    for nm in control_names:
        cper = runner.collect(nm, csv_map)
        rrs = [r for outs in cper.values() for r in _net_rrs(outs, cost)]
        crep = agg.aggregate(nm, [_INST], [o for outs in cper.values() for o in outs], cost_model=cost)
        if crep.expectancy_rr > win_exp:
            win_name, win_rrs, win_exp = nm, rrs, crep.expectancy_rr

    report = agg.aggregate(cand.name, [_INST],
                           [o for outs in per.values() for o in outs], cost_model=cost)
    state = evaluate_pre_bh(report, per, win_name, win_rrs, win_exp, qcfg, cost)
    bh = benjamini_hochberg({cand.name: state.p_value} if state.passed_1_to_6 else {},
                            qcfg.significance_alpha)
    final = finalize(state, bh, qcfg)
    assert final.verdict in {"PROMOTE", "REJECT", "INSUFFICIENT", "HUMAN_REVIEW"}
    assert final.verdict != "PROMOTE"              # PNF-v1 is falsified, not an edge


def test_pnf_chain_deterministic_by_hash():
    cand = _candidate()
    runner = HypothesisRunner(_cfg())
    csv_map = {_INST: str(_DATA)}

    def _h() -> str:
        rr = runner.run(cand.name, csv_map)
        return hashlib.sha256(
            json.dumps(run_result_to_dict(rr), sort_keys=True).encode("utf-8")).hexdigest()

    assert _h() == _h()
