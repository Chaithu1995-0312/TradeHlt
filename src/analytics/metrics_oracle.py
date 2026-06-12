"""
Independent backtest-metric recompute oracle — Backtest Trust Layer (2026-06-10).

PURPOSE
    Recompute the headline backtest metrics (PF, expectancy, win-rate, drawdown,
    total-return, CAGR, MAR) *from the trade ledger alone*, using mathematics that
    are written independently of the production path in `runtime/backtest_v2.py`.

NON-NEGOTIABLE INVARIANT
    This module MUST NOT import `MetricsEngine`, `BacktestMetrics`, `CapitalCurve`,
    or any other canonical formula helper. Same mathematics, *different code* — so a
    bug in the production metrics path cannot certify itself green via the parity
    test. (Enforced by `tests/analytics/test_metrics_oracle_parity.py` step 4.)

CONVENTIONS (mirrored from the canonical path so parity is meaningful)
    - A trade is a WIN iff `pnl_rr_net > 0`; otherwise (including exactly 0R) a LOSS.
      (`backtest_v2.py:1069-1070`.)
    - Profit factor uses gross win / |gross loss| in R; when there are no losses, the
      inf-sentinel is returned (`backtest_v2.py:1096-1101`).
    - Equity curve is `[initial_capital, *capital_after_each_trade]`; max-DD walks it
      with `dd = (peak - eq) / peak` (`backtest_v2.py:347-356`).

See: docs/analysis/backtest-trust-audit-2026-06-10.md
"""
from __future__ import annotations

from dataclasses import dataclass

# Mirror of `_ROI_DEFAULTS["profit_factor_inf_sentinel"]` (a config default value,
# not a formula). Kept local so this module imports nothing from the runtime path.
PF_INF_SENTINEL = 999.0
_BAR_MINUTES_M15 = 15
_MINUTES_PER_YEAR = 365 * 24 * 60


# ── R-multiple metrics (need only the per-trade pnl_rr_net list) ──────────────

def win_rate(rr: list[float]) -> float:
    """wins / total, win := r > 0. Empty ledger → 0.0."""
    n = len(rr)
    if n == 0:
        return 0.0
    wins = sum(1 for r in rr if r > 0)
    return wins / n


def profit_factor(rr: list[float], inf_sentinel: float = PF_INF_SENTINEL) -> float:
    """gross_win / |gross_loss| in R. No losses → inf_sentinel. Empty → 0.0."""
    if not rr:
        return 0.0
    gross_win = sum(r for r in rr if r > 0)
    gross_loss = sum(r for r in rr if r <= 0)   # ≤ 0, so this is negative-or-zero
    if gross_loss < 0:
        return gross_win / abs(gross_loss)
    return inf_sentinel


def expectancy_mean(rr: list[float]) -> float:
    """Mean R per trade = Σr / N. Empty → 0.0. (Canonical `avg_rr_net` form.)"""
    n = len(rr)
    return sum(rr) / n if n else 0.0


def expectancy_classical(rr: list[float]) -> float:
    """
    Classical form: WR·avg_win − (1−WR)·avg_loss, with loss magnitude positive and
    the loss partition = {r ≤ 0} (mirrors the win/loss convention). Algebraically
    identical to `expectancy_mean` — the two are cross-checked in WS3.6 invariants.
    """
    n = len(rr)
    if n == 0:
        return 0.0
    wins = [r for r in rr if r > 0]
    losses = [r for r in rr if r <= 0]          # magnitudes are -r
    wr = len(wins) / n
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss_mag = (sum(-r for r in losses) / len(losses)) if losses else 0.0
    return wr * avg_win - (1.0 - wr) * avg_loss_mag


def max_drawdown_rr(rr: list[float]) -> float:
    """Peak-to-trough on the cumulative-R equity walk (absolute R, ≥ 0)."""
    eq = peak = dd = 0.0
    for r in rr:
        eq += r
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return dd


# ── Capital (%) metrics (need the equity curve / initial capital) ────────────

def max_drawdown_pct(equity_curve: list[float]) -> float:
    """Peak-to-trough on a capital equity curve: max((peak - eq) / peak)."""
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for eq in equity_curve:
        peak = max(peak, eq)
        dd = (peak - eq) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    return max_dd


def total_return_pct(final_capital: float, initial_capital: float) -> float:
    """(final − initial) / initial."""
    return (final_capital - initial_capital) / initial_capital if initial_capital else 0.0


def cagr(total_return: float, total_candles: int, bar_minutes: int = _BAR_MINUTES_M15) -> float:
    """Span-aware CAGR: (1+ret)^(1/years) − 1, years from candle span."""
    years = (total_candles * bar_minutes) / _MINUTES_PER_YEAR if total_candles > 0 else 0.0
    if years > 0 and (1.0 + total_return) > 0:
        return (1.0 + total_return) ** (1.0 / years) - 1.0
    return 0.0


def return_to_max_dd(total_return: float, max_dd_pct: float) -> float:
    """MAR-style ratio: total_return_pct / max_dd_pct. Zero DD → 0.0."""
    return total_return / max_dd_pct if max_dd_pct > 0 else 0.0


# ── Sharpe & Recovery (research-readiness audit 2026-06-12) ───────────────────
# These two headline metrics were NOT covered by the original Backtest Trust Layer
# because the canonical production metrics dataclass does not compute them:
#   - Sharpe IS computed, but only in the sidecar governance path
#     (`governance/portfolio_validation.py:125-131`) as a PER-TRADE ratio using the
#     POPULATION standard deviation (÷N, not ÷(N-1)) and NOT annualized. The oracle
#     mirrors that exact convention so the cross-module parity test is meaningful.
#   - Recovery Factor has no production counterpart by that name; the implemented
#     `return_to_max_dd` (MAR) is its %-space analog (already oracle-verified). The
#     R-space form below is provided for completeness / invariant coverage only —
#     it is deliberately NOT added to the production metrics path.

def sharpe(rr: list[float]) -> float:
    """Per-trade Sharpe = mean(R) / population_stdev(R). <2 trades or zero variance → 0.0.

    Mirrors governance/portfolio_validation.py:125-131 (population variance, ÷N, not
    annualized) so the two independent implementations can be reconciled. Independent
    code path — imports nothing from the production metrics modules."""
    n = len(rr)
    if n < 2:
        return 0.0
    mean = sum(rr) / n
    var = sum((r - mean) ** 2 for r in rr) / n
    return mean / (var ** 0.5) if var > 0 else 0.0


def recovery_factor(rr: list[float]) -> float:
    """R-space recovery factor = ΣR / max_drawdown_rr. Zero DD → 0.0.

    The classical recovery factor (net profit / max drawdown). The production path
    exposes only the %-space MAR form (`return_to_max_dd`); this R-space form has no
    production counterpart and exists for invariant coverage. Net-negative R over zero
    DD is impossible (a losing run always draws down), so DD>0 whenever ΣR<0."""
    dd = max_drawdown_rr(rr)
    return (sum(rr) / dd) if dd > 0 else 0.0


# ── Bundled recompute ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OracleResult:
    trades: int
    win_rate: float
    profit_factor: float
    expectancy_mean: float
    expectancy_classical: float
    max_drawdown_rr: float
    max_drawdown_pct: float
    total_return_pct: float
    cagr: float
    return_to_max_dd: float
    sharpe: float
    recovery_factor: float


def recompute(
    rr: list[float],
    *,
    equity_curve: list[float] | None = None,
    initial_capital: float | None = None,
    final_capital: float | None = None,
    total_candles: int = 0,
    bar_minutes: int = _BAR_MINUTES_M15,
    inf_sentinel: float = PF_INF_SENTINEL,
) -> OracleResult:
    """Recompute every headline metric from the ledger. Capital (%) metrics are
    computed only when `equity_curve` / `initial_capital` / `final_capital` are
    supplied; otherwise they default to 0.0."""
    mdd_pct = max_drawdown_pct(equity_curve) if equity_curve else 0.0
    tr = (
        total_return_pct(final_capital, initial_capital)
        if (final_capital is not None and initial_capital is not None)
        else 0.0
    )
    return OracleResult(
        trades=len(rr),
        win_rate=win_rate(rr),
        profit_factor=profit_factor(rr, inf_sentinel),
        expectancy_mean=expectancy_mean(rr),
        expectancy_classical=expectancy_classical(rr),
        max_drawdown_rr=max_drawdown_rr(rr),
        max_drawdown_pct=mdd_pct,
        total_return_pct=tr,
        cagr=cagr(tr, total_candles, bar_minutes),
        return_to_max_dd=return_to_max_dd(tr, mdd_pct),
        sharpe=sharpe(rr),
        recovery_factor=recovery_factor(rr),
    )
