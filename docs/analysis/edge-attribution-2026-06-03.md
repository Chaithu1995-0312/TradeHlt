# Edge Attribution + Survivability Study

> Point-in-time, generated 2026-06-02T19:55:01.721125+00:00 (seed 1337). PURE MEASUREMENT — no production/config/spine change. Depth set: `data\master_crypto_training.jsonl` (N=203,588, ETH). Cross-instrument: BNBUSDT, BTCUSDT, ETHUSDT, SOLUSDT. Full multivariate model: R²(rr)=0.0042, AUC(win)=0.5149.

## Headline

- **Full multivariate model is at/near chance:** AUC(win)=0.5149, R²(rr)=0.0042. Individual features → outcome carry almost no signal at the per-candle level; **drop-column marginal ΔR² is ~0 for every feature except the top one(s)**.
- **Where any edge lives (empirical):** **selection-process (not static features)**. Top durable features by Edge Score: candles_since_retest(0.48), volatility_ratio(0.10), hour_of_day(0.00).
- **Roadmap implication:** (3) **No durable static feature-edge at the per-candle level.** The full multivariate model is at chance (AUC=0.5149, R²=0.0042); drop-column marginal contribution is ~0 for all but 1 feature(s). The edge is NOT a static feature→outcome map — it lives in the **selection process** (CRT state machine + session + score selectivity) and **throughput policy**, which this unfiltered-opportunity dataset deliberately does not apply. This is a valuable, engineering-saving negative result for the cluster-space / probability-surface thesis.
- **Durable tier:** 5 / 38 cleared the meaningful-effect coverage gate (a decile expectancy departing ≥0.05R from baseline, with edge-support N ≥ 500, and activation ≥ 0.05). The other 33 never move binned expectancy ≥0.05R (tiny-effect) or fire too rarely (tiny-coverage) — reported, never elevated.

### Interpretation (read before acting)

- **This is measured on per-candle scanner *opportunities* (every candle → a long/short setup), NOT executed trades.** The production system filters these via the CRT state machine + session gate + score threshold down to ~15–35 trades (BNB v4 backtest PF≈2.5). So near-chance feature→outcome here is *expected* and does **not** mean the live system has no edge — it means the edge is created by **selectivity** (which candles are allowed to trade), not by a static map from features to outcome.
- **Consequence for the roadmap:** a static feature-cluster predictor (Probability Surface / cluster-space / a TradeNet that scores raw setups) is unlikely to add edge on this evidence — the demonstrated lever remains **throughput/selection policy** (the session change that moved BNB +4.91%→+20.59%). Invest there before more feature-cluster intelligence.
- The only features with any unique, broadly-supported, stable effect are **candles_since_retest** (retest timing) and **volatility_ratio** — and even these are modest (marginal ΔR² ≤ 0.0024). Interactions (Phase 2) are at best 'regime-conditional' with best-cell PF≈1.25 — positive but not a strong, standalone edge.

## Phase 1 — Edge Attribution Table (durable tier, sorted by Edge Score)

| Feature | Family | Importance | Marginal(ΔR²) | PF-spread | Exp-spread | Temporal | X-Inst | Coverage(act%/edgeN) | Edge Score |
|---|---|---|---|---|---|---|---|---|---|---|
| candles_since_retest | geometry | 1.000 | 0.0024 | 0.39 | 0.144 | 0.89 | 0.54 | 82% / 26,412 | **0.4787** |
| volatility_ratio | state | 0.743 | 0.0004 | 0.28 | 0.095 | 0.88 | 0.97 | 100% / 20,360 | **0.1005** |
| hour_of_day | state | 0.373 | 0.0000 | 0.45 | 0.146 | 0.39 | 0.57 | 95% / 34,972 | **0.0009** |
| volume_ratio | state | 0.540 | 0.0000 | 0.29 | 0.096 | 0.93 | 0.97 | 100% / 20,360 | **0.0000** |
| atr | state | 0.763 | 0.0000 | 0.26 | 0.090 | 0.95 | 0.95 | 100% / 20,356 | **0.0000** |

### MIRAGE / low-coverage (demoted — not durable)

| Feature | Family | Importance | Edge Score | activation% | edge-N | why |
|---|---|---|---|---|---|---|
| swing_low | geometry | 0.496 | 0.1706 | 15% | 0 | edgeN<floor |
| volatility_regime | state | 0.297 | 0.0609 | 64% | 0 | edgeN<floor |
| macd_line | state | 0.354 | 0.0502 | 100% | 0 | edgeN<floor |
| swing_high | geometry | 0.296 | 0.0092 | 15% | 0 | edgeN<floor |
| trend_strength | state | 0.346 | 0.0032 | 100% | 0 | edgeN<floor |
| wick_size | geometry | 0.322 | 0.0014 | 100% | 0 | edgeN<floor |
| open | price | 0.297 | 0.0000 | 100% | 0 | edgeN<floor |
| high | price | 0.309 | 0.0000 | 100% | 0 | edgeN<floor |
| low | price | 0.325 | 0.0000 | 100% | 0 | edgeN<floor |
| close | price | 0.337 | 0.0000 | 100% | 0 | edgeN<floor |
| volume | price | 0.348 | 0.0000 | 100% | 0 | edgeN<floor |
| double_sweep | state | 0.053 | 0.0000 | 5% | 0 | activation<floor, edgeN<floor |
| ema_fast | state | 0.314 | 0.0000 | 100% | 0 | edgeN<floor |
| ema_slow | state | 0.322 | 0.0000 | 100% | 0 | edgeN<floor |
| ema_spread | state | 0.306 | 0.0000 | 100% | 0 | edgeN<floor |
| trend_bias | state | 0.122 | 0.0000 | 49% | 0 | edgeN<floor |
| momentum_score | state | 0.358 | 0.0000 | 100% | 0 | edgeN<floor |
| rsi_14 | state | 0.279 | 0.0000 | 100% | 0 | edgeN<floor |
| macd_signal | state | 0.331 | 0.0000 | 100% | 0 | edgeN<floor |
| macd_hist | state | 0.264 | 0.0000 | 100% | 0 | edgeN<floor |
| sweep_detected | geometry | 0.076 | 0.0000 | 18% | 0 | edgeN<floor |
| liquidity_sweep | geometry | 0.088 | 0.0000 | 18% | 0 | edgeN<floor |
| break_of_structure | geometry | 0.061 | 0.0000 | 13% | 0 | edgeN<floor |
| higher_high | geometry | 0.072 | 0.0000 | 16% | 0 | edgeN<floor |
| lower_low | geometry | 0.247 | 0.0000 | 15% | 0 | edgeN<floor |
| body_size | geometry | 0.301 | 0.0000 | 100% | 0 | edgeN<floor |
| body_ratio | geometry | 0.293 | 0.0000 | 100% | 0 | edgeN<floor |
| session | state | 0.131 | 0.0000 | 64% | 0 | edgeN<floor |
| disp_strength | geometry | 0.391 | 0.0000 | 100% | 0 | edgeN<floor |
| retest_depth | geometry | 0.533 | 0.0000 | 100% | 0 | edgeN<floor |
| liquidity_distance | geometry | 0.286 | 0.0000 | 100% | 0 | edgeN<floor |
| liquidity_pressure_score | geometry | 0.287 | 0.0000 | 100% | 0 | edgeN<floor |
| volume_spike | state | 0.245 | 0.0000 | 22% | 0 | edgeN<floor |

## Phase 2 — Interaction Survivability (Top-10 pairs; cells require N≥500)

| Pair | best cell (A-tercile,B-tercile) | cell-N | exp | PF | interaction-lift | temporal-stable | verdict |
|---|---|---|---|---|---|---|---|
| candles_since_retest x hour_of_day | (2,1) | 21,440 | 0.093 | 1.27 | 0.067 | True | regime-conditional |
| candles_since_retest x volume_ratio | (2,2) | 20,668 | 0.087 | 1.25 | 0.066 | True | regime-conditional |
| candles_since_retest x volatility_ratio | (2,2) | 19,828 | 0.088 | 1.26 | 0.066 | True | regime-conditional |
| candles_since_retest x atr | (2,0) | 24,112 | 0.079 | 1.23 | 0.066 | True | regime-conditional |
| hour_of_day x atr | (1,0) | 24,528 | 0.083 | 1.25 | 0.064 | True | regime-conditional |
| volume_ratio x atr | (2,0) | 24,108 | 0.074 | 1.22 | 0.058 | True | regime-conditional |
| hour_of_day x volume_ratio | (1,2) | 28,136 | 0.082 | 1.25 | 0.058 | True | regime-conditional |
| volatility_ratio x atr | (2,0) | 24,456 | 0.077 | 1.23 | 0.056 | True | regime-conditional |
| volatility_ratio x hour_of_day | (2,1) | 26,736 | 0.088 | 1.27 | 0.049 | True | regime-conditional |
| volatility_ratio x volume_ratio | (2,2) | 44,100 | 0.057 | 1.17 | 0.034 | True | none |

## Caveats (non-negotiable)

- **Collinearity/leakage:** univariate importance overstates correlated features; the drop-column **Marginal(ΔR²)** column is the antidote — a high-importance/low-marginal feature is a passenger.
- **Outcome definition:** `rr_achieved` uses the scanner's SL/TP + 0.5R trail; a different exit definition could move ranks.
- **Depth vs breadth:** importance/temporal from ETH depth set; cross-instrument from 4 instruments' opportunities (per-candle, NOT executed trades — session/score filters not applied here).
- **correlation ≠ causation; importance ≠ tradeable edge** until placed in the gate/throughput context.
- Price-level features (open/high/low/close) are non-stationary; treat any 'importance' there as suspect.
