# ROI Baseline — BNBUSDT M15 (2026-05-29)

> **Point-in-time snapshot, not a living doc.** Captures the first measured ROI baseline
> after the "ROI Step" made account-equity return a first-class, additive telemetry metric.
> Profit remains subordinate to correctness per `docs/architecture/goal.md` — these numbers
> are *measured*, not *gated*. For current truth, re-run the backtest.

## What this is

The ROI Step surfaced six additive returns metrics (`total_return_pct`, `annualized_return_pct`,
`profit_factor`, `return_to_max_dd`, `gross_win_rr`, `gross_loss_rr`) into `BacktestMetrics`
and the governance `ValidationReport`. No gate, fitness weight, or behavior changed — only
measurement was added (telemetry-additive invariant). This file records the resulting baseline.

## Run

- **Instrument / TF:** BNBUSDT M15
- **Data:** `data/BNBUSDT_M15.csv` — 70,080 candles ≈ **2.0 years** (70,080 × 15 min ÷ 525,600 min/yr)
- **Config:** active `v2_multi_2026_04 - deepdeektry` (`initial_capital=100,000`, `use_compounding=true`, slippage + spread on)
- **Command:** `python src/runtime/backtest_v2.py --csv data/BNBUSDT_M15.csv --instrument BNBUSDT --output results/roi_baseline`
- **Artifact:** `results/roi_baseline/run_20260529_161443_BNBUSDT/`

## Baseline ROI metrics

| Metric | Value | Note |
|---|---|---|
| **Total return (ROI)** | **+4.91%** | final capital 104,913.44 from 100,000 |
| **Annualized return (CAGR)** | **+2.43%** | `(1.0491)^(1/2.0) − 1` over the 2-year span |
| **Profit factor** | **1.79** | gross win 11.13R ÷ gross loss 6.21R |
| **Return / max drawdown (MAR-like)** | **2.38** | 4.91% ÷ 2.07% |
| Gross win / loss | +11.13R / −6.21R | |

## Context metrics (pre-existing, for reference)

| Metric | Value |
|---|---|
| Trades (approved / rejected) | 15 / 0 (approval rate 100%) |
| Win rate | 60.0% |
| Avg RR net | +0.328R |
| Total PnL net | +4.92R (raw +5.91R; cost drag −0.99R) |
| Max drawdown | 2.07% equity (2.08R) |
| Win / loss streak | 2 / 2 |
| Best / worst session | NEWYORK 71% WR, +2.99R / LONDON 50% WR, +1.93R |

Trade-level figures (15 trades, 60% WR, +0.328R, 2.08R DD) match the
[[project_phase4b_findings]] memory entry — confirming the additive change preserved
deterministic replay (invariant #1).

## Observations

- **ROI is modest and DD-light.** +4.91% over two years with only 2.07% max drawdown → a high
  return-to-DD ratio (2.38) but a low absolute return, driven by very low trade frequency (15
  trades / 2 yr) and the conservative selectivity established through Phases 1–4.
- **CAGR ≪ total return** because the span is 2 years; annualization roughly halves the headline.
- **Profit factor 1.79** is healthy for the sample but rests on N=15 — not yet statistically robust
  (matches the soft "low trade count" caution in `ConfigValidator`).
- **Cost drag is real:** raw +5.91R → net +4.92R (−0.99R, ~17% of gross).

## Status of the ROI Step

This baseline closes the *measure* phase. Whether to **gate on ROI** (promotion floor) or
**optimize for ROI** (objective shift — would require an explicit deviation flag per
`goal.md`) is a separate, later decision and is **out of scope** here.
