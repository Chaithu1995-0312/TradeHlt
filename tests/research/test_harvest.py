"""Unit tests for Program 6b — carry HARVEST (funding cashflow + price/basis).

Covers: discrete funding-settlement marking (load_panel), funding accrual over (t, t+H] with the
no-lookahead boundary (a settlement at t is NOT accrued), the structurally-positive funding income of
the long-low/short-high basket, the full = funding-only + price/basis decomposition identity, the
`cash` zero control, the DIAGNOSTIC-only verdict authority for funding-only specs (never PROMOTE,
never in the promotion surface), and determinism. Offline — synthetic CSVs + in-memory panels.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import random

import pytest

from research.cross_sectional import (
    DIAGNOSTIC_NEGATIVE, DIAGNOSTIC_POSITIVE, HarvestSpec, XSQualConfig, build_panel,
    harvest_net_series, load_panel, long_short_weights, qualify_harvest, rebalance_grid, scores,
)

_M15 = dt.timedelta(minutes=15)
_8H_BARS = 32


# ── discrete settlement marking via load_panel ────────────────────────────────
def _ts_list(n: int) -> list[str]:
    base = dt.datetime.strptime("2024-05-22 00:00:00", "%Y-%m-%d %H:%M:%S")
    return [(base + i * _M15).strftime("%Y-%m-%d %H:%M:%S") for i in range(n)]


def _write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def test_load_panel_funding_settle_is_discrete(tmp_path):
    n = 40
    ts = _ts_list(n)
    perp = tmp_path / "perp"
    perp.mkdir()
    csv_map = {}
    for sym, base in (("AAA", 100.0), ("BBB", 200.0)):
        sp = tmp_path / f"{sym}_M15.csv"
        _write_csv(sp, ["timestamp", "open", "high", "low", "close", "volume"],
                   [[t, base, base, base, base, 1.0] for t in ts])
        csv_map[sym] = str(sp)
        _write_csv(perp / f"{sym}_FUNDING_8H.csv", ["timestamp", "funding_rate"],
                   [[ts[0], 0.001], [ts[_8H_BARS], 0.002]])
        _write_csv(perp / f"{sym}_BASIS_M15.csv", ["timestamp", "premium_index"],
                   [[ts[i], 0.0] for i in range(n)])
    panel = load_panel(csv_map, perp_dir=str(perp))
    fs = panel.funding_settle["AAA"]
    assert fs[0] == 0.001 and fs[_8H_BARS] == 0.002       # only on settlement bars
    assert sum(1 for x in fs if x != 0.0) == 2            # exactly two non-zero
    assert all(fs[i] == 0.0 for i in range(1, _8H_BARS))  # zero between settlements


# ── accrual over (t, t+H] + no-lookahead boundary ─────────────────────────────
def test_funding_accrual_excludes_entry_bar_settlement():
    syms = ["AAA", "BBB"]
    n = 10
    closes = {s: [100.0] * n for s in syms}
    basis = {s: [0.0] * n for s in syms}
    settle = {"AAA": [0.0] * n, "BBB": [0.0] * n}
    settle["AAA"][2] = 0.05    # AT entry bar t=2 -> must NOT be accrued
    settle["AAA"][3] = 0.01    # inside (2, 6]
    settle["AAA"][7] = 0.02    # outside (2, 6]
    p = build_panel(syms, list(range(n)), closes, basis=basis, funding_settle=settle)

    w = lambda t: {"AAA": 1.0, "BBB": 0.0}          # noqa: E731  long AAA only
    r = harvest_net_series(p, [2], w, H=4, round_trip_bps=0.0, include_price=False)
    # only the bar-3 settlement (0.01) is in (2,6]; long pays funding -> -0.01
    assert r[0] == pytest.approx(-0.01)


# ── long-low/short-high basket has positive funding income ────────────────────
def test_long_low_short_high_income_is_positive():
    syms = ["AAA", "BBB", "CCC", "DDD"]      # monotone funding low->high
    n = 12
    rate = {"AAA": 0.0001, "BBB": 0.0003, "CCC": 0.0006, "DDD": 0.0009}
    closes = {s: [100.0] * n for s in syms}
    basis = {s: [0.0] * n for s in syms}
    funding = {s: [rate[s]] * n for s in syms}                 # ffilled (for the carry ranking)
    settle = {s: [rate[s] if i in (4, 8) else 0.0 for i in range(n)] for s in syms}
    p = build_panel(syms, list(range(n)), closes, funding=funding, basis=basis, funding_settle=settle)

    grid = rebalance_grid(1, 4, n)
    wfn = lambda t: long_short_weights(scores(p, t, "carry", 1), 2)   # noqa: E731 long low funding
    # funding-only return = income - cost(0); income = -Σ w·accrued; long-low/short-high => > 0
    series = harvest_net_series(p, grid, wfn, H=4, round_trip_bps=0.0, include_price=False)
    assert series and sum(series) / len(series) > 0


# ── decomposition identity: full = funding_only + price/basis ─────────────────
def test_full_minus_funding_only_is_price_basis_term():
    syms = ["AAA", "BBB", "CCC", "DDD"]
    n = 16
    rng = random.Random(5)
    closes = {s: [100.0 + rng.uniform(-5, 5) for _ in range(n)] for s in syms}
    basis = {s: [rng.uniform(-1e-3, 1e-3) for _ in range(n)] for s in syms}
    funding = {s: [rng.uniform(-1e-3, 1e-3) for _ in range(n)] for s in syms}
    settle = {s: [funding[s][i] if i % 4 == 0 else 0.0 for i in range(n)] for s in syms}
    p = build_panel(syms, list(range(n)), closes, funding=funding, basis=basis, funding_settle=settle)

    grid = rebalance_grid(1, 4, n)
    wfn = lambda t: long_short_weights(scores(p, t, "carry", 1), 2)   # noqa: E731
    full = harvest_net_series(p, grid, wfn, 4, 0.0, include_price=True)
    fund = harvest_net_series(p, grid, wfn, 4, 0.0, include_price=False)
    for t, f_full, f_fund in zip(grid, full, fund):
        w = wfn(t)
        price = sum(w[s] * ((p.closes[s][t + 4] / p.closes[s][t] - 1.0)
                            + (p.basis[s][t + 4] - p.basis[s][t])) for s in w)
        assert (f_full - f_fund) == pytest.approx(price, abs=1e-12)


# ── qualify_harvest: authority separation + verdict ladder + determinism ──────
def _synthetic_harvest_panel(n=900, seed=4):
    syms = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]
    rng = random.Random(seed)
    closes, funding, basis, settle = {}, {}, {}, {}
    for s in syms:
        price, cs, fs, bs, st = 100.0, [], [], [], []
        for i in range(n):
            price *= 1.0 + rng.uniform(-0.01, 0.01)
            cs.append(price)
            rate = rng.uniform(-1e-3, 1e-3)
            fs.append(rate)
            bs.append(rng.uniform(-2e-3, 2e-3))
            st.append(rate if i % _8H_BARS == 0 else 0.0)   # settle every 8h
        closes[s], funding[s], basis[s], settle[s] = cs, fs, bs, st
    return build_panel(syms, list(range(n)), closes, funding=funding, basis=basis, funding_settle=settle)


_SPECS = [
    HarvestSpec("harvest_full_cur_96", 1, 96, True),
    HarvestSpec("harvest_full_1d_96", 96, 96, True),
    HarvestSpec("harvest_fund_cur_96", 1, 96, False),
    HarvestSpec("harvest_fund_1d_96", 96, 96, False),
]
_QC = XSQualConfig(k=2, min_samples=10, expectancy_min=0.0, pf_min=1.0, oos_split=0.3,
                   oos_retention_min=0.5, n_permutations=300, significance_alpha=0.05)


def test_funding_only_specs_are_diagnostic_only():
    p = _synthetic_harvest_panel()
    rep = qualify_harvest(p, _SPECS, _QC)
    # tradeable (harvest_full) live in `interpreters`; funding-only in `diagnostics` — disjoint.
    assert set(rep["interpreters"]) == {"harvest_full_cur_96", "harvest_full_1d_96"}
    assert set(rep["diagnostics"]) == {"harvest_fund_cur_96", "harvest_fund_1d_96"}
    for r in rep["diagnostics"].values():
        assert r["verdict"] in {DIAGNOSTIC_POSITIVE, DIAGNOSTIC_NEGATIVE}
        assert "funding_income" in r
    for r in rep["interpreters"].values():
        assert r["verdict"] in {"PROMOTE", "REJECT", "REDUNDANT", "INSUFFICIENT"}
    # no funding-only name can ever reach the promotion surface
    assert all(not n.startswith("harvest_fund") for n in rep["promoted"])


def test_cash_control_present_and_zero():
    p = _synthetic_harvest_panel()
    rep = qualify_harvest(p, _SPECS, _QC)
    assert "cash" in rep["controls"]
    for r in rep["interpreters"].values():
        assert r["control_means"]["cash"] == 0.0     # doing nothing earns nothing


def test_qualify_harvest_is_deterministic():
    p = _synthetic_harvest_panel()
    r1 = qualify_harvest(p, _SPECS, _QC)
    r2 = qualify_harvest(p, _SPECS, _QC)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)
