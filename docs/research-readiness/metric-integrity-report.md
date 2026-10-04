# Metric Integrity Report (2026-06-12)

> **Purpose (Phase 4):** trace every headline metric from source and cross-check it against an
> **independent oracle**. Extends [`backtest-trust-audit-2026-06-10.md`](../analysis/backtest-trust-audit-2026-06-10.md)
> (the original Backtest Trust Layer) to the two metrics it did not cover: **Sharpe** and **Recovery**.

## Method
Production headline metrics live in `runtime/backtest_v2.py` (`BacktestMetrics` + `MetricsEngine`,
[backtest_v2.py:1001](../../src/runtime/backtest_v2.py:1001)). The independent
`analytics/metrics_oracle.py` recomputes them from the published trade ledger using *different code*
(enforced: it may not import `MetricsEngine`/`BacktestMetrics`/`CapitalCurve`/`backtest_v2` —
`test_metrics_oracle_parity.py` step 4). Three test layers: **golden** fixtures (exact to 1e-12),
**invariants** (algebra over 25 ledgers), **parity** (oracle vs production on a real BNBUSDT run).

## Per-metric verdict

| Metric | Production formula (source) | Independently verified? | Notes |
|---|---|---|---|
| **PnL (R)** | `Σ pnl_rr_net` ([:1119](../../src/runtime/backtest_v2.py:1119)) | ✅ parity + golden | net of slippage+spread |
| **Profit Factor** | `gross_win / |gross_loss|`, inf-sentinel 999 ([:1144](../../src/runtime/backtest_v2.py:1144)) | ✅ parity + invariant | identity test |
| **Win rate** | `wins/(wins+losses)`, win:=r>0 ([:1037](../../src/runtime/backtest_v2.py:1037)) | ✅ parity + invariant | 0R counts as loss |
| **Expectancy** | mean R = `total/(w+l)` ([:1042](../../src/runtime/backtest_v2.py:1042)) | ✅ parity + invariant | mean≡classical (F4 closed) |
| **Max Drawdown** | R-walk ([:1159](../../src/runtime/backtest_v2.py:1159)) + %-equity ([:360](../../src/runtime/backtest_v2.py:360)) | ✅ parity + invariant | both forms |
| **MAR / return-to-DD** | `total_return_pct / max_dd_pct` ([:1150](../../src/runtime/backtest_v2.py:1150)) | ✅ parity | %-space recovery analog |
| **CAGR** | span-aware `(1+ret)^(1/yrs)−1` ([:1153](../../src/runtime/backtest_v2.py:1153)) | ✅ parity | M15→years |
| **Sharpe** | per-trade `mean/√var` **population variance** ([portfolio_validation.py:129](../../src/governance/portfolio_validation.py:129)) | ✅ **NEW** cross-module parity | see gap ↓ |
| **Recovery Factor** | *not computed by that name* | ⚠️ **gap (documented, not invented)** | MAR is the %-space analog (verified) |

## Findings

**A-3a — Sharpe was uncovered + lives only in a sidecar.** `BacktestMetrics` (the headline path)
does **not** compute Sharpe. It exists only in `governance/portfolio_validation.py` as a *per-trade*
ratio using **population** standard deviation (÷N, not ÷(N−1)) and **not annualized**. It was never
oracle-verified.
- **Fix (this session, additive):** independent `metrics_oracle.sharpe()` mirroring that exact
  convention, wired into `OracleResult`/`recompute`, with a **cross-module parity test** that runs
  the real production `PortfolioAnalytics.aggregate()` on a shared ledger and reconciles to 5e-4
  (production rounds to 4dp). Plus invariants (sign tracks mean; zero-variance→0).

**A-3b — Recovery Factor has no production counterpart.** No metric named "recovery factor" exists.
The classical form (net profit / max DD) maps to the implemented **MAR** (`return_to_max_dd`, %-space),
which IS oracle-verified. Per the no-invent-metrics constraint, production was **not** changed; an
R-space `metrics_oracle.recovery_factor()` + invariant was added for completeness/coverage only.

**Sharpe convention caveat (for researchers):** the production Sharpe is *per-trade, population-σ,
non-annualized*. It is **not** comparable to a standard annualized Sharpe and must not be cited as
one. This is a reporting-semantics caveat, not a correctness defect.

## Result
All 8 mission metrics now have an independent verification path (Sharpe/Recovery added this session);
176 analytics tests green. The headline P&L/PF/WR/expectancy/DD/MAR/CAGR figures a researcher reads
are mathematically certified against independent code. **Confidence: high.**
