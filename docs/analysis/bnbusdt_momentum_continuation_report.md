# BNBUSDT M15 — Momentum Continuation Research

> **Generated:** 2026-06-13 03:28 UTC
> **Data:** `data/BNBUSDT_M15.csv` (70,080 candles, 2024-05-22 to 2026-05-21)
> **Purpose:** Measure whether momentum continuation can be exploited on BNBUSDT
> **Methodology:** No optimization. No curve-fitting. Pure measurement from historical data.

## Overview — All Entry Definitions

| Entry Definition | Trades | Win Rate (90m) | Avg Return 60m | Med MFE | Med MAE | Med Peak (m) |
|---|---|---|---|---|---|---|
| Above_EMA20 | 36783 | 50.0% | +0.0043% | 1.6000 | 1.6800 | 45m |
| EMA_Slope_Pos | 36783 | 50.0% | +0.0043% | 1.6000 | 1.6800 | 45m |
| Close_Up | 35177 | 50.0% | -0.0020% | 1.6300 | 1.7500 | 45m |
| Momentum_Threshold | 15004 | 50.1% | +0.0018% | 1.6600 | 1.7800 | 45m |
| Momentum_Top20pct | 13712 | 50.8% | +0.0046% | 1.7300 | 1.8000 | 45m |
| Volume_Expansion | 9837 | 50.9% | +0.0087% | 2.0400 | 2.1200 | 45m |
| Combined_Strong | 4816 | 48.4% | +0.0101% | 1.8900 | 2.0000 | 45m |

---

## Detailed Results Per Entry Definition

### Above_EMA20

- **Total trades:** 36783
- **Win rate (90m):** 50.0%

#### Trade Frequency
- Per day: 50.39
- Per week: 352.71
- Per month: 1533.8
- Per year: 18392

#### MFE & MAE (60m horizon)
- Average MFE: 2.588264
- Median MFE: 1.600000
- Average MAE: 2.601272
- Median MAE: 1.680000
- MFE/MAE ratio: 0.99x

#### Time Analysis
- Median time to peak: 45 minutes
- Median time to bottom: 45 minutes

#### Returns at Fixed Horizons

| Horizon | Avg Return (%) | Prob Positive (%) |
|---|---|---|
| 15m | +0.0007% | 48.6% |
| 30m | +0.0016% | 48.9% |
| 45m | +0.0027% | 49.3% |
| 60m | +0.0043% | 49.6% |
| 90m | +0.0056% | 50.0% |

#### Continuation Survival Table

| Time | % Trades Still Positive |
|---|---|
| 15m | 48.6% |
| 30m | 48.9% |
| 45m | 49.3% |
| 60m | 49.6% |
| 90m | 50.0% |

> **Edge decay point:** Probability drops below 50% at `15m`

### EMA_Slope_Pos

- **Total trades:** 36783
- **Win rate (90m):** 50.0%

#### Trade Frequency
- Per day: 50.39
- Per week: 352.71
- Per month: 1533.8
- Per year: 18392

#### MFE & MAE (60m horizon)
- Average MFE: 2.588264
- Median MFE: 1.600000
- Average MAE: 2.601272
- Median MAE: 1.680000
- MFE/MAE ratio: 0.99x

#### Time Analysis
- Median time to peak: 45 minutes
- Median time to bottom: 45 minutes

#### Returns at Fixed Horizons

| Horizon | Avg Return (%) | Prob Positive (%) |
|---|---|---|
| 15m | +0.0007% | 48.6% |
| 30m | +0.0016% | 48.9% |
| 45m | +0.0027% | 49.3% |
| 60m | +0.0043% | 49.6% |
| 90m | +0.0056% | 50.0% |

#### Continuation Survival Table

| Time | % Trades Still Positive |
|---|---|
| 15m | 48.6% |
| 30m | 48.9% |
| 45m | 49.3% |
| 60m | 49.6% |
| 90m | 50.0% |

> **Edge decay point:** Probability drops below 50% at `15m`

### Close_Up

- **Total trades:** 35177
- **Win rate (90m):** 50.0%

#### Trade Frequency
- Per day: 48.19
- Per week: 337.31
- Per month: 1466.8
- Per year: 17588

#### MFE & MAE (60m horizon)
- Average MFE: 2.618736
- Median MFE: 1.630000
- Average MAE: 2.739611
- Median MAE: 1.750000
- MFE/MAE ratio: 0.96x

#### Time Analysis
- Median time to peak: 45 minutes
- Median time to bottom: 45 minutes

#### Returns at Fixed Horizons

| Horizon | Avg Return (%) | Prob Positive (%) |
|---|---|---|
| 15m | -0.0012% | 48.9% |
| 30m | -0.0029% | 49.1% |
| 45m | -0.0045% | 49.2% |
| 60m | -0.0020% | 50.1% |
| 90m | -0.0018% | 50.0% |

#### Continuation Survival Table

| Time | % Trades Still Positive |
|---|---|
| 15m | 48.9% |
| 30m | 49.1% |
| 45m | 49.2% |
| 60m | 50.1% |
| 90m | 50.0% |

> **Edge decay point:** Probability drops below 50% at `15m`

### Momentum_Threshold

- **Total trades:** 15004
- **Win rate (90m):** 50.1%

#### Trade Frequency
- Per day: 20.55
- Per week: 143.87
- Per month: 625.6
- Per year: 7502

#### MFE & MAE (60m horizon)
- Average MFE: 2.705628
- Median MFE: 1.660000
- Average MAE: 2.758307
- Median MAE: 1.780000
- MFE/MAE ratio: 0.98x

#### Time Analysis
- Median time to peak: 45 minutes
- Median time to bottom: 45 minutes

#### Returns at Fixed Horizons

| Horizon | Avg Return (%) | Prob Positive (%) |
|---|---|---|
| 15m | +0.0005% | 48.1% |
| 30m | -0.0021% | 48.4% |
| 45m | -0.0043% | 48.6% |
| 60m | +0.0018% | 50.1% |
| 90m | +0.0047% | 50.1% |

#### Continuation Survival Table

| Time | % Trades Still Positive |
|---|---|
| 15m | 48.1% |
| 30m | 48.4% |
| 45m | 48.6% |
| 60m | 50.1% |
| 90m | 50.1% |

> **Edge decay point:** Probability drops below 50% at `15m`

### Momentum_Top20pct

- **Total trades:** 13712
- **Win rate (90m):** 50.8%

#### Trade Frequency
- Per day: 18.78
- Per week: 131.48
- Per month: 571.8
- Per year: 6856

#### MFE & MAE (60m horizon)
- Average MFE: 2.818644
- Median MFE: 1.730000
- Average MAE: 2.878891
- Median MAE: 1.800000
- MFE/MAE ratio: 0.98x

#### Time Analysis
- Median time to peak: 45 minutes
- Median time to bottom: 45 minutes

#### Returns at Fixed Horizons

| Horizon | Avg Return (%) | Prob Positive (%) |
|---|---|---|
| 15m | +0.0024% | 48.7% |
| 30m | +0.0010% | 49.0% |
| 45m | -0.0014% | 49.2% |
| 60m | +0.0046% | 50.8% |
| 90m | +0.0082% | 50.8% |

#### Continuation Survival Table

| Time | % Trades Still Positive |
|---|---|
| 15m | 48.7% |
| 30m | 49.0% |
| 45m | 49.2% |
| 60m | 50.8% |
| 90m | 50.8% |

> **Edge decay point:** Probability drops below 50% at `15m`

### Volume_Expansion

- **Total trades:** 9837
- **Win rate (90m):** 50.9%

#### Trade Frequency
- Per day: 13.48
- Per week: 94.33
- Per month: 410.2
- Per year: 4918

#### MFE & MAE (60m horizon)
- Average MFE: 3.272398
- Median MFE: 2.040000
- Average MAE: 3.594506
- Median MAE: 2.120000
- MFE/MAE ratio: 0.91x

#### Time Analysis
- Median time to peak: 45 minutes
- Median time to bottom: 45 minutes

#### Returns at Fixed Horizons

| Horizon | Avg Return (%) | Prob Positive (%) |
|---|---|---|
| 15m | -0.0032% | 49.1% |
| 30m | -0.0014% | 49.7% |
| 45m | +0.0038% | 50.3% |
| 60m | +0.0087% | 50.8% |
| 90m | +0.0087% | 50.9% |

#### Continuation Survival Table

| Time | % Trades Still Positive |
|---|---|
| 15m | 49.1% |
| 30m | 49.7% |
| 45m | 50.3% |
| 60m | 50.8% |
| 90m | 50.9% |

> **Edge decay point:** Probability drops below 50% at `15m`

### Combined_Strong

- **Total trades:** 4816
- **Win rate (90m):** 48.4%

#### Trade Frequency
- Per day: 6.60
- Per week: 46.18
- Per month: 200.8
- Per year: 2408

#### MFE & MAE (60m horizon)
- Average MFE: 3.157479
- Median MFE: 1.890000
- Average MAE: 3.058000
- Median MAE: 2.000000
- MFE/MAE ratio: 1.03x

#### Time Analysis
- Median time to peak: 45 minutes
- Median time to bottom: 45 minutes

#### Returns at Fixed Horizons

| Horizon | Avg Return (%) | Prob Positive (%) |
|---|---|---|
| 15m | -0.0025% | 46.2% |
| 30m | -0.0026% | 46.4% |
| 45m | -0.0002% | 47.2% |
| 60m | +0.0101% | 48.5% |
| 90m | +0.0067% | 48.4% |

#### Continuation Survival Table

| Time | % Trades Still Positive |
|---|---|
| 15m | 46.2% |
| 30m | 46.4% |
| 45m | 47.2% |
| 60m | 48.5% |
| 90m | 48.4% |

> **Edge decay point:** Probability drops below 50% at `15m`

---

## Feature Discovery — Winners vs Losers

### Above_EMA20 — Feature Comparison

| Feature | Winner Mean | Loser Mean | Diff | p-value | Significant? |
|---|---|---|---|---|---|
| rsi_14 | 61.8057 | 62.6501 | -0.8444 | 0.0 | ✅ |
| hour | 11.5174 | 11.3397 | +0.1776 | 0.01593 | ✅ |
| trend_strength | 0.9997 | 1.065 | -0.0653 | 0.0 | ✅ |
| dow | 2.9519 | 2.9859 | -0.0340 | 0.101853 | ❌ |
| volume_ratio | 0.9506 | 0.9694 | -0.0189 | 0.003841 | ✅ |
| ema20_slope | 0.2757 | 0.2931 | -0.0174 | 1e-06 | ✅ |
| regime | 1.02 | 1.0348 | -0.0148 | 0.091167 | ❌ |
| session | 0.9974 | 0.984 | +0.0134 | 0.119803 | ❌ |
| mom_change_pct | 0.0703 | 0.0783 | -0.0081 | 0.002488 | ✅ |
| atr_pct | 0.3549 | 0.3525 | +0.0024 | 0.255266 | ❌ |
| body_pct | 0.1761 | 0.1761 | -0.0000 | 0.982919 | ❌ |

#### Top Feature Clusters (2D centroids)

| Rank | Features | Distance | Winner Centroid | Loser Centroid |
|---|---|---|---|---|
| 1 | rsi_14 + trend_strength | 0.8469 | (np.float64(61.8057), np.float64(0.9997)) | (np.float64(62.6501), np.float64(1.065)) |
| 2 | ema20_slope + rsi_14 | 0.8446 | (np.float64(0.2757), np.float64(61.8057)) | (np.float64(0.2931), np.float64(62.6501)) |
| 3 | volume_ratio + rsi_14 | 0.8446 | (np.float64(0.9506), np.float64(61.8057)) | (np.float64(0.9694), np.float64(62.6501)) |
| 4 | mom_change_pct + rsi_14 | 0.8444 | (np.float64(0.0703), np.float64(61.8057)) | (np.float64(0.0783), np.float64(62.6501)) |
| 5 | atr_pct + rsi_14 | 0.8444 | (np.float64(0.3549), np.float64(61.8057)) | (np.float64(0.3525), np.float64(62.6501)) |
| 6 | body_pct + rsi_14 | 0.8444 | (np.float64(0.1761), np.float64(61.8057)) | (np.float64(0.1761), np.float64(62.6501)) |
| 7 | volume_ratio + trend_strength | 0.0679 | (np.float64(0.9506), np.float64(0.9997)) | (np.float64(0.9694), np.float64(1.065)) |
| 8 | ema20_slope + trend_strength | 0.0676 | (np.float64(0.2757), np.float64(0.9997)) | (np.float64(0.2931), np.float64(1.065)) |
| 9 | mom_change_pct + trend_strength | 0.0658 | (np.float64(0.0703), np.float64(0.9997)) | (np.float64(0.0783), np.float64(1.065)) |
| 10 | atr_pct + trend_strength | 0.0653 | (np.float64(0.3549), np.float64(0.9997)) | (np.float64(0.3525), np.float64(1.065)) |

### EMA_Slope_Pos — Feature Comparison

| Feature | Winner Mean | Loser Mean | Diff | p-value | Significant? |
|---|---|---|---|---|---|
| rsi_14 | 61.8057 | 62.6501 | -0.8444 | 0.0 | ✅ |
| hour | 11.5174 | 11.3397 | +0.1776 | 0.01593 | ✅ |
| trend_strength | 0.9997 | 1.065 | -0.0653 | 0.0 | ✅ |
| dow | 2.9519 | 2.9859 | -0.0340 | 0.101853 | ❌ |
| volume_ratio | 0.9506 | 0.9694 | -0.0189 | 0.003841 | ✅ |
| ema20_slope | 0.2757 | 0.2931 | -0.0174 | 1e-06 | ✅ |
| regime | 1.02 | 1.0348 | -0.0148 | 0.091167 | ❌ |
| session | 0.9974 | 0.984 | +0.0134 | 0.119803 | ❌ |
| mom_change_pct | 0.0703 | 0.0783 | -0.0081 | 0.002488 | ✅ |
| atr_pct | 0.3549 | 0.3525 | +0.0024 | 0.255266 | ❌ |
| body_pct | 0.1761 | 0.1761 | -0.0000 | 0.982919 | ❌ |

#### Top Feature Clusters (2D centroids)

| Rank | Features | Distance | Winner Centroid | Loser Centroid |
|---|---|---|---|---|
| 1 | rsi_14 + trend_strength | 0.8469 | (np.float64(61.8057), np.float64(0.9997)) | (np.float64(62.6501), np.float64(1.065)) |
| 2 | ema20_slope + rsi_14 | 0.8446 | (np.float64(0.2757), np.float64(61.8057)) | (np.float64(0.2931), np.float64(62.6501)) |
| 3 | volume_ratio + rsi_14 | 0.8446 | (np.float64(0.9506), np.float64(61.8057)) | (np.float64(0.9694), np.float64(62.6501)) |
| 4 | mom_change_pct + rsi_14 | 0.8444 | (np.float64(0.0703), np.float64(61.8057)) | (np.float64(0.0783), np.float64(62.6501)) |
| 5 | atr_pct + rsi_14 | 0.8444 | (np.float64(0.3549), np.float64(61.8057)) | (np.float64(0.3525), np.float64(62.6501)) |
| 6 | body_pct + rsi_14 | 0.8444 | (np.float64(0.1761), np.float64(61.8057)) | (np.float64(0.1761), np.float64(62.6501)) |
| 7 | volume_ratio + trend_strength | 0.0679 | (np.float64(0.9506), np.float64(0.9997)) | (np.float64(0.9694), np.float64(1.065)) |
| 8 | ema20_slope + trend_strength | 0.0676 | (np.float64(0.2757), np.float64(0.9997)) | (np.float64(0.2931), np.float64(1.065)) |
| 9 | mom_change_pct + trend_strength | 0.0658 | (np.float64(0.0703), np.float64(0.9997)) | (np.float64(0.0783), np.float64(1.065)) |
| 10 | atr_pct + trend_strength | 0.0653 | (np.float64(0.3549), np.float64(0.9997)) | (np.float64(0.3525), np.float64(1.065)) |

### Close_Up — Feature Comparison

| Feature | Winner Mean | Loser Mean | Diff | p-value | Significant? |
|---|---|---|---|---|---|
| rsi_14 | 55.8289 | 56.9282 | -1.0993 | 0.0 | ✅ |
| hour | 11.6457 | 11.4176 | +0.2281 | 0.002035 | ✅ |
| dow | 2.9604 | 3.0132 | -0.0528 | 0.012901 | ✅ |
| trend_strength | 1.0011 | 1.0491 | -0.0480 | 0.0 | ✅ |
| ema20_slope | 0.0979 | 0.1277 | -0.0298 | 0.0 | ✅ |
| session | 1.018 | 0.9914 | +0.0266 | 0.002288 | ✅ |
| volume_ratio | 0.9473 | 0.9636 | -0.0164 | 0.014977 | ✅ |
| atr_pct | 0.3748 | 0.3685 | +0.0063 | 0.011115 | ✅ |
| regime | 1.0624 | 1.0584 | +0.0040 | 0.656387 | ❌ |
| mom_change_pct | 0.1929 | 0.1898 | +0.0031 | 0.196454 | ❌ |
| body_pct | 0.1912 | 0.1882 | +0.0030 | 0.203429 | ❌ |

#### Top Feature Clusters (2D centroids)

| Rank | Features | Distance | Winner Centroid | Loser Centroid |
|---|---|---|---|---|
| 1 | rsi_14 + trend_strength | 1.1003 | (np.float64(55.8289), np.float64(1.0011)) | (np.float64(56.9282), np.float64(1.0491)) |
| 2 | ema20_slope + rsi_14 | 1.0997 | (np.float64(0.0979), np.float64(55.8289)) | (np.float64(0.1277), np.float64(56.9282)) |
| 3 | volume_ratio + rsi_14 | 1.0994 | (np.float64(0.9473), np.float64(55.8289)) | (np.float64(0.9636), np.float64(56.9282)) |
| 4 | mom_change_pct + rsi_14 | 1.0993 | (np.float64(0.1929), np.float64(55.8289)) | (np.float64(0.1898), np.float64(56.9282)) |
| 5 | atr_pct + rsi_14 | 1.0993 | (np.float64(0.3748), np.float64(55.8289)) | (np.float64(0.3685), np.float64(56.9282)) |
| 6 | body_pct + rsi_14 | 1.0993 | (np.float64(0.1912), np.float64(55.8289)) | (np.float64(0.1882), np.float64(56.9282)) |
| 7 | ema20_slope + trend_strength | 0.0565 | (np.float64(0.0979), np.float64(1.0011)) | (np.float64(0.1277), np.float64(1.0491)) |
| 8 | volume_ratio + trend_strength | 0.0507 | (np.float64(0.9473), np.float64(1.0011)) | (np.float64(0.9636), np.float64(1.0491)) |
| 9 | atr_pct + trend_strength | 0.0484 | (np.float64(0.3748), np.float64(1.0011)) | (np.float64(0.3685), np.float64(1.0491)) |
| 10 | mom_change_pct + trend_strength | 0.0481 | (np.float64(0.1929), np.float64(1.0011)) | (np.float64(0.1898), np.float64(1.0491)) |

### Momentum_Threshold — Feature Comparison

| Feature | Winner Mean | Loser Mean | Diff | p-value | Significant? |
|---|---|---|---|---|---|
| rsi_14 | 59.2715 | 60.5838 | -1.3123 | 0.0 | ✅ |
| hour | 11.3187 | 11.1713 | +0.1474 | 0.192774 | ❌ |
| trend_strength | 1.1101 | 1.1747 | -0.0646 | 2e-06 | ✅ |
| ema20_slope | 0.1758 | 0.2136 | -0.0378 | 1e-06 | ✅ |
| volume_ratio | 1.12 | 1.1531 | -0.0331 | 0.007299 | ✅ |
| dow | 3.0144 | 3.0473 | -0.0329 | 0.314911 | ❌ |
| session | 0.9775 | 0.9611 | +0.0164 | 0.212869 | ❌ |
| regime | 1.048 | 1.0552 | -0.0072 | 0.602456 | ❌ |
| atr_pct | 0.3744 | 0.3693 | +0.0051 | 0.173999 | ❌ |
| mom_change_pct | 0.3276 | 0.3241 | +0.0035 | 0.438713 | ❌ |
| body_pct | 0.3247 | 0.3216 | +0.0032 | 0.475464 | ❌ |

#### Top Feature Clusters (2D centroids)

| Rank | Features | Distance | Winner Centroid | Loser Centroid |
|---|---|---|---|---|
| 1 | rsi_14 + trend_strength | 1.3139 | (np.float64(59.2715), np.float64(1.1101)) | (np.float64(60.5838), np.float64(1.1747)) |
| 2 | ema20_slope + rsi_14 | 1.3129 | (np.float64(0.1758), np.float64(59.2715)) | (np.float64(0.2136), np.float64(60.5838)) |
| 3 | volume_ratio + rsi_14 | 1.3127 | (np.float64(1.12), np.float64(59.2715)) | (np.float64(1.1531), np.float64(60.5838)) |
| 4 | mom_change_pct + rsi_14 | 1.3123 | (np.float64(0.3276), np.float64(59.2715)) | (np.float64(0.3241), np.float64(60.5838)) |
| 5 | atr_pct + rsi_14 | 1.3123 | (np.float64(0.3744), np.float64(59.2715)) | (np.float64(0.3693), np.float64(60.5838)) |
| 6 | body_pct + rsi_14 | 1.3123 | (np.float64(0.3247), np.float64(59.2715)) | (np.float64(0.3216), np.float64(60.5838)) |
| 7 | ema20_slope + trend_strength | 0.0749 | (np.float64(0.1758), np.float64(1.1101)) | (np.float64(0.2136), np.float64(1.1747)) |
| 8 | volume_ratio + trend_strength | 0.0726 | (np.float64(1.12), np.float64(1.1101)) | (np.float64(1.1531), np.float64(1.1747)) |
| 9 | atr_pct + trend_strength | 0.0648 | (np.float64(0.3744), np.float64(1.1101)) | (np.float64(0.3693), np.float64(1.1747)) |
| 10 | mom_change_pct + trend_strength | 0.0647 | (np.float64(0.3276), np.float64(1.1101)) | (np.float64(0.3241), np.float64(1.1747)) |

### Momentum_Top20pct — Feature Comparison

| Feature | Winner Mean | Loser Mean | Diff | p-value | Significant? |
|---|---|---|---|---|---|
| rsi_14 | 56.1617 | 57.6649 | -1.5031 | 0.0 | ✅ |
| hour | 11.3864 | 11.1487 | +0.2377 | 0.041622 | ✅ |
| trend_strength | 1.0837 | 1.1418 | -0.0581 | 4.3e-05 | ✅ |
| volume_ratio | 1.1383 | 1.1784 | -0.0400 | 0.002521 | ✅ |
| ema20_slope | 0.09 | 0.1285 | -0.0385 | 3e-05 | ✅ |
| session | 0.9861 | 0.957 | +0.0291 | 0.031779 | ✅ |
| dow | 2.9971 | 3.021 | -0.0239 | 0.485934 | ❌ |
| regime | 1.0981 | 1.0829 | +0.0152 | 0.2899 | ❌ |
| atr_pct | 0.3964 | 0.387 | +0.0094 | 0.03258 | ✅ |
| mom_change_pct | 0.3341 | 0.3322 | +0.0019 | 0.694235 | ❌ |
| body_pct | 0.3311 | 0.3295 | +0.0015 | 0.749286 | ❌ |

#### Top Feature Clusters (2D centroids)

| Rank | Features | Distance | Winner Centroid | Loser Centroid |
|---|---|---|---|---|
| 1 | rsi_14 + trend_strength | 1.5043 | (np.float64(56.1617), np.float64(1.0837)) | (np.float64(57.6649), np.float64(1.1418)) |
| 2 | volume_ratio + rsi_14 | 1.5037 | (np.float64(1.1383), np.float64(56.1617)) | (np.float64(1.1784), np.float64(57.6649)) |
| 3 | ema20_slope + rsi_14 | 1.5036 | (np.float64(0.09), np.float64(56.1617)) | (np.float64(0.1285), np.float64(57.6649)) |
| 4 | atr_pct + rsi_14 | 1.5032 | (np.float64(0.3964), np.float64(56.1617)) | (np.float64(0.387), np.float64(57.6649)) |
| 5 | mom_change_pct + rsi_14 | 1.5031 | (np.float64(0.3341), np.float64(56.1617)) | (np.float64(0.3322), np.float64(57.6649)) |
| 6 | body_pct + rsi_14 | 1.5031 | (np.float64(0.3311), np.float64(56.1617)) | (np.float64(0.3295), np.float64(57.6649)) |
| 7 | volume_ratio + trend_strength | 0.0705 | (np.float64(1.1383), np.float64(1.0837)) | (np.float64(1.1784), np.float64(1.1418)) |
| 8 | ema20_slope + trend_strength | 0.0697 | (np.float64(0.09), np.float64(1.0837)) | (np.float64(0.1285), np.float64(1.1418)) |
| 9 | atr_pct + trend_strength | 0.0588 | (np.float64(0.3964), np.float64(1.0837)) | (np.float64(0.387), np.float64(1.1418)) |
| 10 | mom_change_pct + trend_strength | 0.0581 | (np.float64(0.3341), np.float64(1.0837)) | (np.float64(0.3322), np.float64(1.1418)) |

### Volume_Expansion — Feature Comparison

| Feature | Winner Mean | Loser Mean | Diff | p-value | Significant? |
|---|---|---|---|---|---|
| rsi_14 | 48.3758 | 51.232 | -2.8562 | 0.0 | ✅ |
| hour | 10.5271 | 10.319 | +0.2081 | 0.114485 | ❌ |
| ema20_slope | -0.0918 | 0.0083 | -0.1001 | 0.0 | ✅ |
| mom_change_pct | -0.055 | -0.0085 | -0.0465 | 2.1e-05 | ✅ |
| trend_strength | 1.5932 | 1.6294 | -0.0361 | 0.063746 | ❌ |
| body_pct | 0.3631 | 0.3409 | +0.0222 | 0.008479 | ✅ |
| atr_pct | 0.4133 | 0.3913 | +0.0220 | 7.1e-05 | ✅ |
| session | 0.8645 | 0.8428 | +0.0217 | 0.148662 | ❌ |
| regime | 1.1045 | 1.091 | +0.0135 | 0.421541 | ❌ |
| dow | 2.9778 | 2.9907 | -0.0129 | 0.753453 | ❌ |
| volume_ratio | 2.2102 | 2.2066 | +0.0037 | 0.818669 | ❌ |

#### Top Feature Clusters (2D centroids)

| Rank | Features | Distance | Winner Centroid | Loser Centroid |
|---|---|---|---|---|
| 1 | ema20_slope + rsi_14 | 2.8580 | (np.float64(-0.0918), np.float64(48.3758)) | (np.float64(0.0083), np.float64(51.232)) |
| 2 | mom_change_pct + rsi_14 | 2.8566 | (np.float64(-0.055), np.float64(48.3758)) | (np.float64(-0.0085), np.float64(51.232)) |
| 3 | rsi_14 + trend_strength | 2.8565 | (np.float64(48.3758), np.float64(1.5932)) | (np.float64(51.232), np.float64(1.6294)) |
| 4 | atr_pct + rsi_14 | 2.8563 | (np.float64(0.4133), np.float64(48.3758)) | (np.float64(0.3913), np.float64(51.232)) |
| 5 | body_pct + rsi_14 | 2.8563 | (np.float64(0.3631), np.float64(48.3758)) | (np.float64(0.3409), np.float64(51.232)) |
| 6 | volume_ratio + rsi_14 | 2.8562 | (np.float64(2.2102), np.float64(48.3758)) | (np.float64(2.2066), np.float64(51.232)) |
| 7 | ema20_slope + mom_change_pct | 0.1103 | (np.float64(-0.0918), np.float64(-0.055)) | (np.float64(0.0083), np.float64(-0.0085)) |
| 8 | ema20_slope + trend_strength | 0.1064 | (np.float64(-0.0918), np.float64(1.5932)) | (np.float64(0.0083), np.float64(1.6294)) |
| 9 | ema20_slope + atr_pct | 0.1025 | (np.float64(-0.0918), np.float64(0.4133)) | (np.float64(0.0083), np.float64(0.3913)) |
| 10 | ema20_slope + body_pct | 0.1025 | (np.float64(-0.0918), np.float64(0.3631)) | (np.float64(0.0083), np.float64(0.3409)) |

### Combined_Strong — Feature Comparison

| Feature | Winner Mean | Loser Mean | Diff | p-value | Significant? |
|---|---|---|---|---|---|
| rsi_14 | 69.2378 | 70.6347 | -1.3969 | 4e-06 | ✅ |
| hour | 10.4873 | 10.0165 | +0.4708 | 0.012951 | ✅ |
| trend_strength | 1.5901 | 1.707 | -0.1169 | 1.7e-05 | ✅ |
| dow | 2.9347 | 2.9895 | -0.0548 | 0.348594 | ❌ |
| regime | 1.0073 | 1.0587 | -0.0514 | 0.033574 | ✅ |
| session | 0.8583 | 0.813 | +0.0453 | 0.035009 | ✅ |
| ema20_slope | 0.4699 | 0.5066 | -0.0367 | 0.015686 | ✅ |
| mom_change_pct | 0.2187 | 0.2398 | -0.0211 | 0.070637 | ❌ |
| body_pct | 0.3085 | 0.3159 | -0.0074 | 0.448082 | ❌ |
| volume_ratio | 2.1833 | 2.19 | -0.0067 | 0.76744 | ❌ |
| atr_pct | 0.37 | 0.3691 | +0.0008 | 0.891004 | ❌ |

#### Top Feature Clusters (2D centroids)

| Rank | Features | Distance | Winner Centroid | Loser Centroid |
|---|---|---|---|---|
| 1 | rsi_14 + trend_strength | 1.4017 | (np.float64(69.2378), np.float64(1.5901)) | (np.float64(70.6347), np.float64(1.707)) |
| 2 | ema20_slope + rsi_14 | 1.3973 | (np.float64(0.4699), np.float64(69.2378)) | (np.float64(0.5066), np.float64(70.6347)) |
| 3 | mom_change_pct + rsi_14 | 1.3970 | (np.float64(0.2187), np.float64(69.2378)) | (np.float64(0.2398), np.float64(70.6347)) |
| 4 | volume_ratio + rsi_14 | 1.3969 | (np.float64(2.1833), np.float64(69.2378)) | (np.float64(2.19), np.float64(70.6347)) |
| 5 | atr_pct + rsi_14 | 1.3969 | (np.float64(0.37), np.float64(69.2378)) | (np.float64(0.3691), np.float64(70.6347)) |
| 6 | body_pct + rsi_14 | 1.3969 | (np.float64(0.3085), np.float64(69.2378)) | (np.float64(0.3159), np.float64(70.6347)) |
| 7 | ema20_slope + trend_strength | 0.1225 | (np.float64(0.4699), np.float64(1.5901)) | (np.float64(0.5066), np.float64(1.707)) |
| 8 | mom_change_pct + trend_strength | 0.1188 | (np.float64(0.2187), np.float64(1.5901)) | (np.float64(0.2398), np.float64(1.707)) |
| 9 | volume_ratio + trend_strength | 0.1171 | (np.float64(2.1833), np.float64(1.5901)) | (np.float64(2.19), np.float64(1.707)) |
| 10 | body_pct + trend_strength | 0.1171 | (np.float64(0.3085), np.float64(1.5901)) | (np.float64(0.3159), np.float64(1.707)) |

---

## Recommended Holding Time

- **Above_EMA20:** `90m` (avg return +0.0056%)
- **EMA_Slope_Pos:** `90m` (avg return +0.0056%)
- **Close_Up:** `15m` (avg return -0.0012%)
- **Momentum_Threshold:** `90m` (avg return +0.0047%)
- **Momentum_Top20pct:** `90m` (avg return +0.0082%)
- **Volume_Expansion:** `60m` (avg return +0.0087%)
- **Combined_Strong:** `60m` (avg return +0.0101%)

## Fixed-Time Exits vs TP/SL

This research uses **fixed-time exits** exclusively (no TP/SL). The data shows:

- **Above_EMA20:** MFE 2.5883 vs MAE 2.6013 (ratio 0.99x)
  - Avg return at best horizon: 0.0043%
- **EMA_Slope_Pos:** MFE 2.5883 vs MAE 2.6013 (ratio 0.99x)
  - Avg return at best horizon: 0.0043%
- **Close_Up:** MFE 2.6187 vs MAE 2.7396 (ratio 0.96x)
  - Avg return at best horizon: -0.002%
- **Momentum_Threshold:** MFE 2.7056 vs MAE 2.7583 (ratio 0.98x)
  - Avg return at best horizon: 0.0018%
- **Momentum_Top20pct:** MFE 2.8186 vs MAE 2.8789 (ratio 0.98x)
  - Avg return at best horizon: 0.0046%
- **Volume_Expansion:** MFE 3.2724 vs MAE 3.5945 (ratio 0.91x)
  - Avg return at best horizon: 0.0087%
- **Combined_Strong:** MFE 3.1575 vs MAE 3.0580 (ratio 1.03x)
  - Avg return at best horizon: 0.0101%

**Finding:** Fixed-time exits reveal whether momentum has a natural decay horizon that outperforms discretionary exit. If avg returns are positive at some horizons but negative at others, fixed-time exits can be calibrated to capture the edge before decay.

## Top Feature Clusters (All Definitions)

| Rank | Strategy | Features | Separation Distance |
|---|---|---|---|
| 1 | Volume_Expansion | ema20_slope + rsi_14 | 2.8580 |
| 2 | Volume_Expansion | mom_change_pct + rsi_14 | 2.8566 |
| 3 | Volume_Expansion | rsi_14 + trend_strength | 2.8565 |
| 4 | Volume_Expansion | atr_pct + rsi_14 | 2.8563 |
| 5 | Volume_Expansion | body_pct + rsi_14 | 2.8563 |
| 6 | Volume_Expansion | volume_ratio + rsi_14 | 2.8562 |
| 7 | Momentum_Top20pct | rsi_14 + trend_strength | 1.5043 |
| 8 | Momentum_Top20pct | volume_ratio + rsi_14 | 1.5037 |
| 9 | Momentum_Top20pct | ema20_slope + rsi_14 | 1.5036 |
| 10 | Momentum_Top20pct | atr_pct + rsi_14 | 1.5032 |
| 11 | Momentum_Top20pct | mom_change_pct + rsi_14 | 1.5031 |
| 12 | Momentum_Top20pct | body_pct + rsi_14 | 1.5031 |
| 13 | Combined_Strong | rsi_14 + trend_strength | 1.4017 |
| 14 | Combined_Strong | ema20_slope + rsi_14 | 1.3973 |
| 15 | Combined_Strong | mom_change_pct + rsi_14 | 1.3970 |

## Confidence Level

| Factor | Assessment |
|---|---|
| Total signals across all definitions | 152112 |
| Data period | 2 years (70,080 M15 candles) |
| Multiple definitions tested | 7 |
| Statistical tests | Welch t-test on feature differences |
| Lookahead bias | None — only past data used for indicators, only forward data for outcomes |
| Survivorship bias | None — Binance live data |
| Precision | M15 OHLCV (intra-candle moves not captured) |

> **Overall confidence: HIGH.** Large sample size across multiple definitions.

## Failure Modes

1. **Fake breakouts:** Price spikes above EMA/previous close but immediately reverses
2. **Mean reversion:** Strong moves attract counter-traders, reversing gains
3. **Low volatility chop:** In low-vol regimes, momentum signals produce many false starts
4. **Session dependency:** Momentum may work in one session but fail in another
5. **Large spread events:** News/release events create gaps that invalidate entries
6. **M15 limitation:** Intra-candle momentum cannot be captured at this resolution
7. **Volume reliability:** Volume on low-vol candles may be misleading

## Final Conclusion

### Summary

1. **Total trades analyzed:** 152112 across 7 entry definitions
2. **Average trades per month:** varies by definition (see per-definition tables)
3. **Average MFE/MAE:** varies by definition — see MFE/MAE tables above
4. **Median time to peak:** 45 minutes (best definition)
5. **Recommended holding time:** see per-definition analysis above
6. **Fixed-time exits vs TP/SL:** see analysis above
7. **Top feature clusters:** see cluster tables above
8. **Confidence level:** see confidence assessment above
9. **Failure modes:** listed above

### Verdict: NO EDGE DETECTED

No entry definition produced a statistically significant edge. Momentum continuation on BNBUSDT M15 appears to be random or negative expectancy over this period.

### Key Recommendations

1. **Do not optimize** — this is purely exploratory
2. **Test on other instruments** — momentum may work differently on BTC/ETH/SOL
3. **Test on tick data** — M15 OHLCV misses intra-candle momentum dynamics
4. **Test different timeframes** — momentum may work on H1/H4 but not M15
5. **Forward test** — run the best definition on live data to verify

---

*Report generated by `scripts/research/momentum_continuation_bnbusdt.py`*
*2026-06-13 03:28 UTC*