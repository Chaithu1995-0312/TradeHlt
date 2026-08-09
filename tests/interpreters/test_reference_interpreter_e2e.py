"""
test_reference_interpreter_e2e.py — the END-TO-END chain proof on REAL data (Plan 4).

Proves: interpreter → InterpreterHypothesis → HypothesisRunner → forward_walk →
EdgeReport → QualificationGate, on a real M15 file, deterministically. The point is
that the chain RUNS and produces honest evidence — NOT that MA-cross has an edge
(verdict is expected to be REJECT/INSUFFICIENT, never PROMOTE).

Skips if the real data file is absent (CI without data still passes).

Run: python -m pytest tests/interpreters/test_reference_interpreter_e2e.py -q
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
    QualConfig, benjamini_hochberg, evaluate_pre_bh, finalize,
)
from research.registry import HYPOTHESIS_REGISTRY, register_hypothesis  # noqa: E402
from research.runner import HypothesisRunner, run_result_to_dict        # noqa: E402

from interpreters.adapter import InterpreterHypothesis                  # noqa: E402
from interpreters.reference import MovingAverageCrossInterpreter        # noqa: E402

_INST = "BNBUSDT"


def _candidate():
    """Register (once) the adapted MA-cross interpreter; reuse if already present."""
    name = "interp:ma_cross_10_30"
    if name in HYPOTHESIS_REGISTRY:
        return HYPOTHESIS_REGISTRY[name]
    cand = InterpreterHypothesis(MovingAverageCrossInterpreter(fast_period=10, slow_period=30))
    register_hypothesis(cand)
    return cand


def _cfg() -> ResearchConfig:
    # apply_signal_defaults=False → exercise the interpreter's own SL/TP geometry.
    return dataclasses.replace(ResearchConfig.from_file(str(_CFG)), apply_signal_defaults=False)


def test_chain_runs_and_produces_edgereport():
    cand = _candidate()
    runner = HypothesisRunner(_cfg())
    rr = runner.run(cand.name, {_INST: str(_DATA)})
    rep = rr.pooled
    assert rep.n > 0                                   # the chain produced measured trades
    # every headline field finite (no NaN/inf leaked through the chain)
    for v in (rep.win_rate, rep.expectancy_rr, rep.max_drawdown_rr):
        assert math.isfinite(v)


def test_qualification_returns_a_verdict_not_promote():
    cand = _candidate()
    cfg = _cfg()
    runner = HypothesisRunner(cfg)
    cost = CostModel(cfg.round_trip_bps)
    agg = EdgeAggregator()
    qcfg = QualConfig.from_research_config(cfg)
    csv_map = {_INST: str(_DATA)}

    control_names = sorted(n for n, h in HYPOTHESIS_REGISTRY.items() if h.family == "control")
    per = runner.collect(cand.name, csv_map)
    # winning control over the single instrument
    win_name, win_rrs, win_exp = "none", [], float("-inf")
    from research.qualification import _net_rrs
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
    assert final.verdict != "PROMOTE"              # a weak reference must not qualify


def test_chain_is_deterministic_by_hash():
    cand = _candidate()
    runner = HypothesisRunner(_cfg())
    csv_map = {_INST: str(_DATA)}

    def _hash() -> str:
        rr = runner.run(cand.name, csv_map)
        return hashlib.sha256(
            json.dumps(run_result_to_dict(rr), sort_keys=True).encode("utf-8")
        ).hexdigest()

    assert _hash() == _hash()                       # byte-identical serialized result
