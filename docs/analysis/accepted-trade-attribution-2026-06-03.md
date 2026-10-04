# Accepted-Trade Attribution Study (Study 1)

> Point-in-time, 2026-06-03T06:48:46.533468+00:00 (seed 1337). PURE MEASUREMENT — no production change. Pooled CRT-accepted/executed trades from `results/**/*_trades.csv`. N=439 unique valid (win-rate 0.4966, mean rr +0.1025). By instrument: {'BNBUSDT': 99, 'ETHUSDT': 68, 'SOLUSDT': 56, 'BTCUSDT': 49, 'BNBUSDT_M15': 39, 'XAUUSD': 26, 'EURCAD': 24, 'GBPUSD': 21, 'EURUSD': 19, 'AUDUSD': 18, 'USDJPY': 18, 'XRPUSDT': 2}.

## Headline — does feature edge EMERGE after selection?

- **Selection already produces positive expectancy:** accepted trades = mean rr **+0.1025R** at **49.7%** win-rate (the per-candle opportunity pool is ~0). The edge is demonstrably in the selection. The question is whether *features* add anything on top.
- **Accepted-trade multivariate model:** AUC(win)=**0.5979**, R²(rr)=**-0.2495**  vs per-candle baseline AUC=0.5149, R²=0.0042  (ΔAUC = **+0.0830**).
- **Verdict:** **Weak / suggestive — INCONCLUSIVE.** Direction-only AUC lifted 0.5149→0.5979 (Δ+0.083), so features carry *a little* more signal among accepted trades than among all candles. BUT R²(rr)=-0.2495 is **negative** (magnitude is unpredictable — the model generalizes worse than the mean), the marginal-ΔR² column is computed off that negative-R² model so it is **not reliable**, and N=439 across heterogeneous configs is too small to trust. This does **not** justify building a feature/cluster predictor yet — it justifies getting more clean accepted-trade samples (fix feedback-loop Break 2) and looking at Study 2.
- **Recurring (weak) candidates:** the only features with any signal are volatility-context — `atr`/`volatility_ratio`/`rsi_14` top importance — consistent with *volatility regime* mattering at entry, but marginal is unreliable at this N.
- **Durable features (coverage-gated):** 25/38 — NOTE: at N=439 the decile expectancy spreads are large from noise, so the coverage gate is weakly discriminating here; trust the Edge Score / marginal collapse, not the count.

## Attribution table (durable tier, by Edge Score)

| Feature | Family | Importance | Marginal(ΔR²) | PF-spread | Exp-spread | Temporal | X-Inst | act% / edgeN | Edge Score |
|---|---|---|---|---|---|---|---|---|---|---|
| atr | state | 1.000 | 0.0343 | 1.96 | 0.874 | 0.98 | 0.78 | 99% / 395 | **0.4831** |
| ema_spread | state | 0.283 | 0.0094 | 1.61 | 0.748 | 0.77 | 0.32 | 99% / 395 | **0.0122** |
| liquidity_pressure_score | geometry | 0.302 | 0.0058 | 1.06 | 0.540 | 0.69 | 0.27 | 70% / 350 | **0.0059** |
| disp_strength | geometry | 0.213 | 0.0043 | 1.91 | 0.811 | 0.29 | 0.68 | 99% / 220 | **0.0033** |
| open | price | 0.193 | 0.0000 | 1.05 | 0.509 | 0.72 | 0.22 | 99% / 351 | **0.0000** |
| high | price | 0.193 | 0.0000 | 1.05 | 0.509 | 0.72 | 0.27 | 99% / 351 | **0.0000** |
| low | price | 0.190 | 0.0000 | 1.05 | 0.509 | 0.75 | 0.38 | 99% / 395 | **0.0000** |
| close | price | 0.194 | 0.0000 | 1.05 | 0.509 | 0.75 | 0.27 | 99% / 395 | **0.0000** |
| volume | price | 0.097 | 0.0000 | 0.78 | 0.407 | 0.75 | 0.32 | 73% / 439 | **0.0000** |
| volume_ratio | state | 0.194 | 0.0000 | 1.75 | 1.162 | 0.19 | 0.14 | 73% / 350 | **0.0000** |
| ema_fast | state | 0.193 | 0.0000 | 1.07 | 0.529 | 0.71 | 0.32 | 99% / 395 | **0.0000** |
| ema_slow | state | 0.207 | 0.0000 | 1.07 | 0.530 | 0.68 | 0.32 | 99% / 395 | **0.0000** |
| trend_strength | state | 0.303 | 0.0000 | 1.19 | 0.555 | 0.94 | 0.24 | 99% / 439 | **0.0000** |
| momentum_score | state | 0.274 | 0.0000 | 1.46 | 0.556 | 0.45 | 0.16 | 99% / 395 | **0.0000** |
| volatility_ratio | state | 0.724 | 0.0000 | 1.83 | 0.644 | 0.66 | 0.08 | 99% / 352 | **0.0000** |
| rsi_14 | state | 0.521 | 0.0000 | 1.37 | 0.668 | 0.68 | 0.27 | 99% / 395 | **0.0000** |
| macd_line | state | 0.338 | 0.0000 | 1.53 | 0.726 | 0.54 | 0.57 | 99% / 351 | **0.0000** |
| macd_signal | state | 0.258 | 0.0000 | 1.44 | 0.646 | 0.17 | 0.51 | 99% / 351 | **0.0000** |
| macd_hist | state | 0.180 | 0.0000 | 2.02 | 0.773 | 0.86 | 0.49 | 99% / 395 | **0.0000** |
| body_size | geometry | 0.195 | 0.0000 | 0.94 | 0.463 | 0.25 | 0.51 | 98% / 395 | **0.0000** |
| wick_size | geometry | 0.142 | 0.0000 | 1.38 | 0.591 | 0.62 | 0.68 | 99% / 309 | **0.0000** |
| body_ratio | geometry | 0.258 | 0.0000 | 1.98 | 1.004 | 0.45 | 0.46 | 99% / 439 | **0.0000** |
| hour_of_day | state | 0.487 | 0.0000 | 1.26 | 0.636 | 0.87 | 0.24 | 85% / 439 | **0.0000** |
| candles_since_retest | geometry | 0.092 | 0.0000 | 1.14 | 0.471 | 0.35 | 0.62 | 91% / 224 | **0.0000** |
| liquidity_distance | geometry | 0.246 | 0.0000 | 0.96 | 0.502 | 0.99 | 0.19 | 70% / 351 | **0.0000** |

## Caveats

- **Config/period heterogeneity (dominant):** the 731 runs span many param configs and date ranges; pooled attribution mixes regimes. Per-instrument N is small.
- **Survivorship:** only executed trades; no rejected-candidate counterfactual here (that is Study 2).
- **Missing features in trade CSVs:** none (excluded if absent).
- Low N inflates importance variance; treat single-feature spikes with suspicion. correlation ≠ causation.
