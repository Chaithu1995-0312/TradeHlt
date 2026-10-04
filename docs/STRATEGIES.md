# STRATEGIES.md

> Living document describing the 10 strategy modules and their orchestrator.
> **Last updated:** 2026-06-07 12:55 UTC+5:30
> This describes the codebase as it currently exists. For decisions about changes, consult the user or a coding agent.

---

## StrategyOrchestrator

**Module:** `src/strategies/strategy_orchestrator.py`

Runs all 10 strategies per candle. Produces a consensus score injected into EngineRunner context as `strategy_consensus_score`.

| Component | Detail |
|-----------|--------|
| Completeness gate | `min_signal_strategies=2` |
| Consensus gate | `min_agreement_ratio=0.60` |
| Weighted aggregation | Config-driven weights per strategy |
| Exception handling | `fail_open=True` per strategy — one failing strategy does not crash the run |

**Config section:** `strategy_engine.s01..s10` in `configs/production/*.json`

---

## Strategy By Index

### S1 — CRT Wrapper (`src/strategies/s01_crt_wrapper.py`)
- Adapter over `engines.crt_engine.compute()` — zero CRT code changes
- Passes CRT scores into StrategyOrchestrator format
- **Config:** `strategy_engine.s01_crt`

### S2 — Mean Reversion (`src/strategies/s02_mean_reversion.py`)
- RSI + Bollinger Bands: `rsi_14 < 30` + price at BB lower → BUY; `rsi_14 > 70` + price at BB upper → SELL
- **Config:** `strategy_engine.s02_mean_reversion`

### S3 — Breakout (`src/strategies/s03_breakout.py`)
- Break of structure (BOS) + swing level + `volume_ratio >= 1.3` → breakout signal
- SL anchored at the broken swing level
- **Config:** `strategy_engine.s03_breakout`

### S4 — Statistical Arbitrage (`src/strategies/s04_stat_arb.py`)
- EMA-spread Z-score: `z > 1.5` → revert
- `trend_filter` blocks trades during strong trends
- **Config:** `strategy_engine.s04_stat_arb`

### S5 — Grid (`src/strategies/s05_grid.py`)
- ATR-grid on swing range
- Lower-half levels → BUY, upper-half → SELL
- Blocked in TRENDING regime
- **Config:** `strategy_engine.s05_grid`

### S6 — Scalping (`src/strategies/s06_scalping.py`)
- MACD-histogram + momentum + session filter (07:00–17:00)
- 2-bar cross detection
- **Config:** `strategy_engine.s06_scalping`

### S7 — News Sentiment (`src/strategies/s07_news_sentiment.py`)
- Layer 1: `volatility_ratio >= 2.0` or spread > 0.05% → NO_TRADE
- Layer 2: zone + trend follow
- **Config:** `strategy_engine.s07_news_sentiment`

### S8 — ML Ensemble (`src/strategies/s08_ml_ensemble.py`)
- Optional BitNet blend + weighted feature scorer
- 4-indicator majority vote for direction
- **Config:** `strategy_engine.s08_ml_ensemble`

### S9 — Pattern Recognition (`src/strategies/s09_pattern_recog.py`)
- Detects: Hammer, Shooting Star, Bullish Engulf, Bearish Engulf, Marubozu
- 3-candle state buffer
- **Config:** `strategy_engine.s09_pattern_recog`

### S10 — Trap Strategy (`src/strategies/s10_trap_strategy.py`)
- Bull Trap → SELL, Bear Trap → BUY
- LIQ_SWEEP intent variant
- Confidence ladder: +0.15 liquidity sweep, +0.10 disp strength, +0.10 double sweep, +0.10 volume ratio > 1.5
- **Config:** `strategy_engine.s10_trap`

---

## Known Notes

- EngineRunner uses the strategy consensus score only if it is `>= 0.0` — the consensus is **advisory, not gating**
- Whether `StrategyOrchestrator.compute()` is invoked in the active execution path determines whether individual strategy thresholds are enforced
- All 10 strategies were created during Sprints 2–3 (2026-04-30)