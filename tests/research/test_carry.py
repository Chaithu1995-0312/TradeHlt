"""Unit tests for Program 6 — carry/basis as a signal on cross-sectional spot dispersion.

Covers the new load-bearing properties on top of the Program-5 kernel: funding forward-fill
(no-lookahead, last settlement <= t), basis contemporaneous alignment, carry/basis score signs,
`Panel` backward-compatibility (Program-5 close-only construction unchanged), fail-fast on a missing
perp corpus, and end-to-end determinism through the (unchanged) `qualify` gate. Offline — synthetic
CSVs in tmp_path + in-memory panels; no network, no committed fixtures.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import random

import pytest

from research.cross_sectional import (
    Interpreter, XSQualConfig, build_panel, load_panel, qualify, scores,
)

_M15 = dt.timedelta(minutes=15)
_8H_BARS = 32   # 8h / 15min


# ── synthetic CSV writers ─────────────────────────────────────────────────────
def _ts_list(n: int, start: str = "2024-05-22 00:00:00") -> list[str]:
    base = dt.datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
    return [(base + i * _M15).strftime("%Y-%m-%d %H:%M:%S") for i in range(n)]


def _write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _make_corpus(tmp_path, n=40):
    """2 symbols, n M15 bars; funding settles at bar 0 and bar 32 (00:00 / 08:00)."""
    ts = _ts_list(n)
    perp = tmp_path / "perp"
    perp.mkdir()
    csv_map = {}
    for sym, base in (("AAA", 100.0), ("BBB", 200.0)):
        sp = tmp_path / f"{sym}_M15.csv"
        _write_csv(sp, ["timestamp", "open", "high", "low", "close", "volume"],
                   [[t, base + i, base + i, base + i, base + i, 1.0] for i, t in enumerate(ts)])
        csv_map[sym] = str(sp)
        _write_csv(perp / f"{sym}_FUNDING_8H.csv", ["timestamp", "funding_rate"],
                   [[ts[0], 0.001], [ts[_8H_BARS], 0.002]])
        _write_csv(perp / f"{sym}_BASIS_M15.csv", ["timestamp", "premium_index"],
                   [[ts[i], i * 1e-4] for i in range(n)])
    return csv_map, str(perp), ts, n


# ── funding forward-fill + basis alignment (integration, offline) ─────────────
def test_load_panel_ffill_and_basis(tmp_path):
    csv_map, perp_dir, ts, n = _make_corpus(tmp_path)
    panel = load_panel(csv_map, perp_dir=perp_dir)

    assert len(panel.funding["AAA"]) == len(panel.basis["AAA"]) == len(panel.timestamps) == n
    # forward-fill: bars before the 08:00 settlement carry the 00:00 rate; the boundary flips at 32.
    assert panel.funding["AAA"][0] == 0.001
    assert panel.funding["AAA"][_8H_BARS - 1] == 0.001        # 07:45 — must NOT see the 08:00 rate
    assert panel.funding["AAA"][_8H_BARS] == 0.002            # 08:00 — sees its own settlement
    # basis is contemporaneous (native M15, no fill).
    assert panel.basis["AAA"][5] == pytest.approx(5e-4)


def test_load_panel_missing_perp_raises(tmp_path):
    csv_map, _perp, ts, n = _make_corpus(tmp_path)
    with pytest.raises(FileNotFoundError):
        load_panel(csv_map, perp_dir=str(tmp_path / "does_not_exist"))


# ── carry/basis score signs ───────────────────────────────────────────────────
def test_carry_basis_score_signs():
    syms = ["AAA", "BBB", "CCC"]
    n, L, t = 6, 4, 5
    closes = {s: [100.0] * n for s in syms}
    funding = {"AAA": [0.001] * n, "BBB": [0.003] * n, "CCC": [0.002] * n}
    basis = {"AAA": [0.0005] * n, "BBB": [0.0015] * n, "CCC": [0.0010] * n}
    p = build_panel(syms, list(range(n)), closes, funding, basis)

    sc = scores(p, t, "carry", L)                 # -mean(funding): lowest funding -> highest score
    assert sc["AAA"] > sc["CCC"] > sc["BBB"]
    assert sc["AAA"] == pytest.approx(-0.001)

    inv = scores(p, t, "carry_inv", L)            # +mean: exact sign flip
    assert all(inv[s] == pytest.approx(-sc[s]) for s in syms)
    assert inv["BBB"] > inv["CCC"] > inv["AAA"]

    b = scores(p, t, "basis", L)                  # -mean(basis): lowest basis -> highest score
    assert b["AAA"] > b["CCC"] > b["BBB"]


def test_carry_basis_scores_no_lookahead():
    syms = ["AAA", "BBB"]
    n, L, t = 10, 4, 5
    closes = {s: [100.0 + i for i in range(n)] for s in syms}
    funding = {"AAA": [0.001 * i for i in range(n)], "BBB": [0.002 * i for i in range(n)]}
    basis = {s: [0.0001 * i for i in range(n)] for s in syms}
    p = build_panel(syms, list(range(n)), closes, funding, basis)

    fm = {s: list(funding[s]) for s in syms}
    bm = {s: list(basis[s]) for s in syms}
    for s in syms:                                # scramble everything strictly after t
        for i in range(t + 1, n):
            fm[s][i] += 999.0
            bm[s][i] += 999.0
    pm = build_panel(syms, list(range(n)), closes, fm, bm)

    assert scores(p, t, "carry", L) == scores(pm, t, "carry", L)
    assert scores(p, t, "basis", L) == scores(pm, t, "basis", L)


# ── Panel backward-compatibility (Program-5 path untouched) ───────────────────
def test_panel_backward_compat():
    p = build_panel(["A", "B"], [0, 1, 2], {"A": [1.0, 2.0, 3.0], "B": [4.0, 5.0, 6.0]})
    assert p.funding == {} and p.basis == {}
    assert scores(p, 2, "momentum", 1)            # close-only kinds still resolve


# ── determinism through the unchanged gate ────────────────────────────────────
def test_qualify_carry_is_deterministic():
    syms = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]
    n = 800
    rng = random.Random(3)
    closes, funding, basis = {}, {}, {}
    for s in syms:
        price, cs, fs, bs = 100.0, [], [], []
        for _ in range(n):
            price *= 1.0 + rng.uniform(-0.01, 0.01)
            cs.append(price)
            fs.append(rng.uniform(-1e-3, 1e-3))
            bs.append(rng.uniform(-2e-3, 2e-3))
        closes[s], funding[s], basis[s] = cs, fs, bs
    p = build_panel(syms, list(range(n)), closes, funding, basis)

    itps = [Interpreter("carry_lo_96_16", "carry", 96, 16),
            Interpreter("basis_hi_32_16", "basis_inv", 32, 16)]
    qc = XSQualConfig(k=2, min_samples=10, expectancy_min=0.0, pf_min=1.0, oos_split=0.3,
                      oos_retention_min=0.5, n_permutations=500, significance_alpha=0.05)
    r1 = qualify(p, itps, qc)
    r2 = qualify(p, itps, qc)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)
    assert set(r1["interpreters"]) == {"carry_lo_96_16", "basis_hi_32_16"}
    for r in r1["interpreters"].values():
        assert r["verdict"] in {"PROMOTE", "REJECT", "INSUFFICIENT", "REDUNDANT"}
