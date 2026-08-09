"""Unit tests for Program 5 — cross-sectional relative-value (dispersion).

Covers the load-bearing properties: panel-alignment fail-fast, the no-lookahead invariant
(scores/forward-spread at bar t are invariant to data appended after the bars they read),
control sanity (market-neutral weights sum to 0; reversed == −interpreter at zero cost;
market basket weights sum to 1; random L/S neutral), cost monotonicity, the verdict ladder
(incl. REDUNDANT), and end-to-end determinism. Pure — no spine, no data files.
"""
from __future__ import annotations

import json
import random

import pytest

from research.cross_sectional import (
    Interpreter, XSQualConfig, _evaluate, _finalize, build_panel, long_only_weights,
    long_short_weights, market_weights, net_series, qualify, random_ls_weights,
    rebalance_grid, scores,
)

_SYMS = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]


def _make_panel(n=600, seed=7):
    rng = random.Random(seed)
    closes = {}
    for s in _SYMS:
        price, series = 100.0, []
        for _ in range(n):
            price *= 1.0 + rng.uniform(-0.01, 0.01)
            series.append(price)
        closes[s] = series
    return build_panel(_SYMS, list(range(n)), closes)


# ── alignment fail-fast ───────────────────────────────────────────────────────
def test_build_panel_rejects_misaligned_lengths():
    with pytest.raises(ValueError):
        build_panel(["A", "B"], [0, 1, 2], {"A": [1.0, 2.0, 3.0], "B": [1.0, 2.0]})


# ── no-lookahead ──────────────────────────────────────────────────────────────
def test_scores_are_invariant_to_future_data():
    base = _make_panel(300, seed=3)
    t, L = 200, 96
    rng = random.Random(99)
    mut = {s: list(base.closes[s]) for s in base.symbols}
    for s in base.symbols:                      # scramble everything strictly after t
        for i in range(t + 1, 300):
            mut[s][i] *= rng.uniform(0.5, 1.5)
    mpanel = build_panel(base.symbols, base.timestamps, mut)
    for kind in ("momentum", "reversal", "vol"):
        assert scores(base, t, kind, L) == scores(mpanel, t, kind, L)


def test_forward_spread_invariant_to_data_after_exit():
    base = _make_panel(300, seed=4)
    t, L, H = 180, 64, 16
    rng = random.Random(11)
    mut = {s: list(base.closes[s]) for s in base.symbols}
    for s in base.symbols:                      # mutate only strictly after the exit bar t+H
        for i in range(t + H + 1, 300):
            mut[s][i] *= rng.uniform(0.5, 1.5)
    mpanel = build_panel(base.symbols, base.timestamps, mut)

    def wf(panel):
        return lambda tt: long_short_weights(scores(panel, tt, "momentum", L), 2)

    a = net_series(base, [t], wf(base), H, 0.0)
    b = net_series(mpanel, [t], wf(mpanel), H, 0.0)
    assert a == b


# ── control / weight sanity ───────────────────────────────────────────────────
def test_weight_constructions():
    p = _make_panel(200, seed=5)
    sc = scores(p, 150, "momentum", 96)
    assert abs(sum(long_short_weights(sc, 2).values())) < 1e-12           # market-neutral
    assert abs(sum(market_weights(p.symbols).values()) - 1.0) < 1e-12     # full basket
    assert abs(sum(long_only_weights(sc, 2).values()) - 1.0) < 1e-12
    rng = random.Random(1)
    assert abs(sum(random_ls_weights(p.symbols, 2, rng).values())) < 1e-12


def test_reversed_is_negative_interpreter_at_zero_cost():
    p = _make_panel(600, seed=6)
    L, H = 96, 16
    grid = rebalance_grid(L, H, len(p))
    si = net_series(p, grid, lambda t: long_short_weights(scores(p, t, "momentum", L), 2), H, 0.0)
    sr = net_series(p, grid,
                    lambda t: long_short_weights({s: -v for s, v in scores(p, t, "momentum", L).items()}, 2),
                    H, 0.0)
    assert si and all(abs(a + b) < 1e-12 for a, b in zip(si, sr))


# ── cost monotonicity ─────────────────────────────────────────────────────────
def test_higher_cost_lowers_net_expectancy():
    p = _make_panel(600, seed=8)
    L, H = 96, 16
    grid = rebalance_grid(L, H, len(p))
    wf = lambda t: long_short_weights(scores(p, t, "momentum", L), 2)   # noqa: E731
    e0 = sum(net_series(p, grid, wf, H, 0.0)) / len(grid)
    e50 = sum(net_series(p, grid, wf, H, 50.0)) / len(grid)
    assert e50 < e0


# ── verdict ladder ────────────────────────────────────────────────────────────
def _rec(**over):
    base = dict(name="x", kind="momentum", L=8, H=8, n=99, expectancy=0.1,
                profit_factor=1.4, win_rate=0.5, is_mean=0.1, oos_mean=0.1,
                oos_retention=1.0, winning_control="random_ls", winning_control_mean=0.0,
                baseline_delta=0.1, market_mean=0.0, beats_market=True,
                control_means={}, p_value=0.01, reject_reasons=[],
                _passed_1_to_6=True, _insufficient=False)
    base.update(over)
    return base


def test_verdict_ladder():
    assert _finalize(_rec(beats_market=False), set(), 0.05)["verdict"] == "REDUNDANT"
    assert _finalize(_rec(beats_market=True), set(), 0.05)["verdict"] == "REJECT"        # gate7 BH
    assert _finalize(_rec(beats_market=True), {"x"}, 0.05)["verdict"] == "PROMOTE"
    assert _finalize(_rec(_insufficient=True, reject_reasons=["FAILED_gate1"]),
                     set(), 0.05)["verdict"] == "INSUFFICIENT"
    assert _finalize(_rec(_passed_1_to_6=False, reject_reasons=["FAILED_gate2"]),
                     set(), 0.05)["verdict"] == "REJECT"


def test_finalize_strips_private_keys():
    out = _finalize(_rec(), {"x"}, 0.05)
    assert not any(k.startswith("_") for k in out)
    assert out["verdict"] == "PROMOTE"


# ── determinism (end-to-end) ──────────────────────────────────────────────────
def test_qualify_is_deterministic():
    p = _make_panel(800, seed=5)
    itps = [Interpreter("xs_mom_96_16", "momentum", 96, 16),
            Interpreter("xs_rev_8_8", "reversal", 8, 8)]
    qc = XSQualConfig(k=2, min_samples=10, expectancy_min=0.0, pf_min=1.0, oos_split=0.3,
                      oos_retention_min=0.5, n_permutations=500, significance_alpha=0.05)
    r1 = qualify(p, itps, qc)
    r2 = qualify(p, itps, qc)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)
    assert set(r1["interpreters"]) == {"xs_mom_96_16", "xs_rev_8_8"}
    for r in r1["interpreters"].values():
        assert r["verdict"] in {"PROMOTE", "REJECT", "INSUFFICIENT", "REDUNDANT"}
