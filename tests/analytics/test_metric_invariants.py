"""
WS3.6 metric invariants — assert the *mathematical relationships* that must hold for
ANY ledger (not specific values). Complements the golden fixtures: golden fixtures
pin known points, invariants pin the algebra across the whole input space.

See docs/analysis/backtest-trust-audit-2026-06-10.md.
"""
from __future__ import annotations

import random

import pytest

from analytics import metrics_oracle as mo


def _ledgers():
    """A spread of deterministic ledgers (seeded), incl. edge shapes."""
    rng = random.Random(42)
    fixed = [
        [1.0, -1.0, 2.0],
        [-1.0, -0.5, -1.0],
        [2.0],
        [1.0, -1.0, 1.0, -1.0, 1.0],
        [0.0, 1.0, -2.0, 0.0, 3.0],   # includes 0R (counts as loss)
    ]
    rand = [[round(rng.uniform(-2.0, 3.0), 4) for _ in range(rng.randint(2, 40))]
            for _ in range(20)]
    return fixed + rand


@pytest.mark.parametrize("rr", _ledgers())
def test_profit_factor_identity(rr):
    """PF ≡ gross_profit / |gross_loss| (independently recomputed)."""
    gp = sum(r for r in rr if r > 0)
    gl = sum(-r for r in rr if r <= 0)
    expected = (gp / gl) if gl > 0 else mo.PF_INF_SENTINEL
    assert mo.profit_factor(rr) == pytest.approx(expected)


@pytest.mark.parametrize("rr", _ledgers())
def test_expectancy_two_forms_agree(rr):
    """mean(R) ≡ WR·avg_win − (1−WR)·avg_loss. Directly exercises the F4 expectancy
    divergence: the simple-mean form and the classical form must coincide."""
    assert mo.expectancy_mean(rr) == pytest.approx(mo.expectancy_classical(rr), abs=1e-12)


@pytest.mark.parametrize("rr", _ledgers())
def test_win_rate_identity(rr):
    expected = (sum(1 for r in rr if r > 0) / len(rr)) if rr else 0.0
    assert mo.win_rate(rr) == pytest.approx(expected)


@pytest.mark.parametrize("rr", _ledgers())
def test_max_drawdown_rr_matches_independent_walk(rr):
    """max-DD(R) ≡ max(peak − equity) over the cumulative-R walk."""
    eq = 0.0
    peak = 0.0
    expected = 0.0
    for r in rr:
        eq += r
        peak = max(peak, eq)
        expected = max(expected, peak - eq)
    assert mo.max_drawdown_rr(rr) == pytest.approx(expected)


def test_monotonic_up_has_zero_drawdown():
    rr = [0.1, 0.2, 0.3, 0.4]
    assert mo.max_drawdown_rr(rr) == pytest.approx(0.0)


@pytest.mark.parametrize("deltas", [
    [5.0, -3.0, 10.0, -2.0],
    [-1.0, -1.0, -1.0],
    [100.0],
])
def test_equity_conservation(deltas):
    """final_equity − initial ≡ Σ trade dollar-PnL, and total_return reflects it."""
    init = 1000.0
    equity = [init]
    for d in deltas:
        equity.append(equity[-1] + d)
    final = equity[-1]
    assert final - init == pytest.approx(sum(deltas))
    assert mo.total_return_pct(final, init) == pytest.approx(sum(deltas) / init)


def test_drawdown_pct_bounded_unit_interval():
    """max-DD% ∈ [0, 1] for any positive equity curve."""
    rng = random.Random(7)
    for _ in range(50):
        eq = [1000.0]
        for _ in range(rng.randint(1, 30)):
            eq.append(max(1.0, eq[-1] + rng.uniform(-200, 200)))
        dd = mo.max_drawdown_pct(eq)
        assert 0.0 <= dd <= 1.0


# ── Sharpe & Recovery invariants (research-readiness audit 2026-06-12) ────────

@pytest.mark.parametrize("rr", _ledgers())
def test_sharpe_sign_tracks_mean(rr):
    """Sharpe sign ≡ sign(mean R): the denominator (stdev) is always ≥ 0."""
    s = mo.sharpe(rr)
    mean = mo.expectancy_mean(rr)
    if len(rr) >= 2 and len(set(rr)) > 1:           # needs variance to be defined
        assert (s > 0) == (mean > 0)
        assert (s < 0) == (mean < 0)


def test_sharpe_zero_variance_is_zero():
    assert mo.sharpe([1.0, 1.0, 1.0]) == 0.0
    assert mo.sharpe([2.0]) == 0.0
    assert mo.sharpe([]) == 0.0


@pytest.mark.parametrize("rr", _ledgers())
def test_recovery_factor_identity(rr):
    """recovery_factor ≡ ΣR / max_drawdown_rr (0 when no drawdown)."""
    dd = mo.max_drawdown_rr(rr)
    expected = (sum(rr) / dd) if dd > 0 else 0.0
    assert mo.recovery_factor(rr) == pytest.approx(expected)


def test_recovery_factor_zero_when_monotonic_up():
    assert mo.recovery_factor([0.1, 0.2, 0.3]) == pytest.approx(0.0)


def test_sharpe_parity_with_production_portfolio_validation():
    """Cross-module parity: the oracle's independent Sharpe must reconcile with the
    ONLY production Sharpe (governance/portfolio_validation PortfolioAnalytics) on a
    shared ledger. This is the Sharpe analogue of the metrics-oracle parity gate —
    the production path is verified against independent code, not against itself."""
    from governance.portfolio_validation import PortfolioAnalytics

    class _StubTrade:                       # minimal shape PortfolioAnalytics reads
        def __init__(self, r):
            self.pnl_rr_net = r
            self.is_winner = r > 0
            self.duration_candles = 1
            self.gaussian_score = 0.0
            self.instrument = "TEST"

    rng = random.Random(11)
    for _ in range(15):
        rr = [round(rng.uniform(-2.0, 3.0), 4) for _ in range(rng.randint(3, 40))]
        prod = PortfolioAnalytics([_StubTrade(r) for r in rr]).aggregate()
        # production rounds sharpe_per_trade to 4dp (portfolio_validation.py:149);
        # residual is pure serialization rounding, not formula divergence.
        assert mo.sharpe(rr) == pytest.approx(prod["sharpe_per_trade"], abs=5e-4)
