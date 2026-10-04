"""qualify_matrix.py — shared scope-loop helpers for the QUALIFY family of research drivers.

Research-framework consolidation Phase 2 (2026-09-14). The `scripts/research/qualify_*.py`
drivers (Programs 1/3/3A/5/6/6b/7/8/…) each build the same two primitives before running the M4
gate (`research.qualification`): a `{instrument: csv_path}` map filtered to the requested
instruments, and "which control wins this scope by pooled net expectancy" (== the CLI's own
`cli.cmd_qualify` semantics). Both were copy-pasted byte-for-byte (AST-normalized) across 6–10
drivers each. This module names them once; each duplicate was replaced in place by a same-named
import (`from research.qualify_matrix import csv_map`), so call sites are unchanged.

Adds NO statistics — `winning_control` only calls `research.qualification._net_rrs` and
`EdgeAggregator.aggregate`, exactly as every replaced copy did.

Originals: archive/research_framework_phase2*_2026-09-14/. Parity pinned by
tests/research/test_qualify_matrix.py against verbatim copies of every replaced variant.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from research.config import ResearchConfig
from research.costs import CostModel
from research.measurement.metrics import EdgeAggregator
from research.qualification import _net_rrs


def csv_map(cfg: ResearchConfig, instruments: Sequence[str]) -> dict[str, str]:
    """{instrument: csv_path} for every `cfg.pattern` match under `cfg.data_dir` whose
    underscore-split stem prefix is in `instruments` (e.g. `BNBUSDT_M15.csv` -> `BNBUSDT`)."""
    data_dir = Path(cfg.data_dir)
    keep = set(instruments)
    out: dict[str, str] = {}
    for p in sorted(data_dir.glob(cfg.pattern)):
        inst = p.stem.split("_")[0]
        if inst in keep:
            out[inst] = str(p)
    return out


def winning_control(
    per_by_hyp: dict[str, dict[str, list]],
    control_names: Sequence[str],
    scope_instruments: Sequence[str],
    agg: EdgeAggregator,
    cost: CostModel,
) -> tuple[str, list[float], float]:
    """Highest pooled NET-expectancy control over the scope (== cli.cmd_qualify semantics).

    Returns (name, net_rr_sequence, expectancy_rr); ("none", [], 0.0) if `control_names` is empty.
    """
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
