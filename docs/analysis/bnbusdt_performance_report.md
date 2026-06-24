# BNBUSDT M15 — Performance Report

> **Date:** 2026-06-13 02:56
> **Source:** Fresh production backtest with HEAD (commit cfe4e16)
> **Config:** `v2_multi_2026_04` (ACTIVE_VERSION)
> **Candle data:** `data/BNBUSDT_M15.csv` (70,080 candles)
> **Trade count:** 13 trades | **Win rate:** 30.8%

---

## 1. Total Number of BNBUSDT Trades

- **13 trades** in the production backtest run
- 4 winners (30.8%) | 9 losers (69.2%)
- Total PnL (net R): **-4.65R**
- Average PnL per trade: **-0.3574R**
- Max drawdown: 6.6% (from backtest summary)

## 2. Average Monthly Opportunity Count

- **13 trades over 663 days** (2024-05-24 to 2026-03-18)
- Average trades/day: **0.02**
- Average trades/week: **0.14**
- Average trades/month: **0.60**
- Average trades/year: **7**

### Distribution by Session

| Session | Trades | % |
|---|---|---|
| ASIA | 2 | 15.4% |
| LONDON | 11 | 84.6% |

### Distribution by Weekday

| Day | Trades | % |
|---|---|---|
| Monday | 3 | 23.1% |
| Tuesday | 1 | 7.7% |
| Wednesday | 1 | 7.7% |
| Thursday | 2 | 15.4% |
| Friday | 1 | 7.7% |
| Saturday | 3 | 23.1% |
| Sunday | 2 | 15.4% |

### Distribution by Hour (UTC)

| Hour | Trades | % |
|---|---|---|
| 7:00 | 2 | 15.4% |
| 8:00 | 1 | 7.7% |
| 9:00 | 4 | 30.8% |
| 13:00 | 3 | 23.1% |
| 14:00 | 2 | 15.4% |
| 15:00 | 1 | 7.7% |

### Distribution by Regime

| Regime | Trades | % |
|---|---|---|
| HIGH_VOL | 5 | 38.5% |
| LOW_VOL | 4 | 30.8% |
| MED_VOL | 4 | 30.8% |

## 3. Average MFE and MAE

- **Average MFE:** 2.388462 price units
- **Median MFE:** 2.450000 price units
- **Average MAE:** 3.371538 price units
- **Median MAE:** 2.800000 price units
- **MFE/MAE ratio (avg):** 0.71x

*Note: MFE and MAE are computed from M15 candle high/low, not tick data.*

## 4. Median Time to Peak

- **Median time to peak (candles):** 2.0 (30.0 minutes)
- **Median time to bottom (candles):** 1 (15 minutes)
- **Median trade duration:** 2 candles (30 minutes)
- **Average trade duration:** 3.4 candles (51 minutes)

## 5. Hold-Time Research — Recommended Holding Duration

| Horizon | Avg Return (%) | Median Return (%) | Prob Positive (%) |
|---|---|---|---|
| 15m | +0.0180% | -0.1190% | 46.2% |
| 30m | -0.0467% | +0.1234% | 61.5% |
| 45m | -0.1166% | -0.1330% | 46.2% |
| 60m | -0.0891% | +0.2467% | 61.5% |
| 90m | -0.0199% | +0.0844% | 53.8% |

- **Recommended holding duration:** `15m` (highest avg return: +0.0180%)

### Continuation Edge Decay

| Horizon | Prob Still Above Entry |
|---|---|
| 15m | 46.2% |
| 30m | 61.5% |
| 45m | 46.2% |
| 60m | 61.5% |
| 90m | 53.8% |

*Where probability drops below 50%, continuation edge has decayed.*

## 6. Top Feature Clusters (Winner vs Loser)

*Based on 4 winners vs 9 losers*

| Feature | Avg Winner | Avg Loser | Diff |
|---|---|---|---|
| Volume Ratio | 1.0912 | 1.2048 | -0.1136 |
| Ema Spread | -42.7833 | -514.2027 | +471.4194 |
| Trend Strength | -0.7523 | -0.6367 | -0.1156 |
| Momentum Score | -291.0742 | -170.4077 | -120.6665 |
| Atr | 0.0034 | 0.0041 | -0.0007 |
| Volatility Ratio | 1.6106 | 1.042 | +0.5686 |
| Rsi 14 | 41.5655 | 37.0782 | +4.4873 |
| Body Size | 2.39 | 1.6611 | +0.7289 |
| Body Ratio | 0.7247 | 0.4066 | +0.3181 |
| Volatility Regime | 0.5 | 1.3333 | -0.8333 |
| Disp Strength | 1.1454 | 0.4628 | +0.6826 |
| Retest Depth | 0.5625 | 0.1507 | +0.4118 |
| Liquidity Distance | 0.7949 | 1.0652 | -0.2703 |
| Liquidity Pressure Score | 0.7061 | 0.6851 | +0.0210 |
| Double Sweep | 0.0 | 0.0 | +0.0000 |
| Live Atr | 2.0141 | 3.0723 | -1.0582 |
| Mfe | 4.645 | 1.3856 | +3.2594 |
| Mae | 0.7 | 4.5589 | -3.8589 |
| Bitnet Score At Entry | 0.0 | 0.0 | +0.0000 |

### Top 5 Discriminating Features

1. **Ema Spread:** Winners=-42.7833, Losers=-514.2027 (diff=+471.4194)
2. **Momentum Score:** Winners=-291.0742, Losers=-170.4077 (diff=-120.6666)
3. **Rsi 14:** Winners=41.5655, Losers=37.0782 (diff=+4.4874)
4. **Mae:** Winners=0.7000, Losers=4.5589 (diff=-3.8589)
5. **Mfe:** Winners=4.6450, Losers=1.3856 (diff=+3.2594)

## 7. Failure Modes

| Exit Reason | Count | % |
|---|---|---|
| STOPPED | 11 | 84.6% |
| TP2 | 2 | 15.4% |

- **Losses cluster around duration ≤5 candles** (median loser duration: 2 candles)
- **MFE/MAE ratio is 0.71x** — adverse moves are significant relative to favorable
- **Most trades exit via STOPPED** — SL hit before TP
- **Missing signal scores** — fusion scores were never captured, so score-based analysis is unavailable

## 8. Confidence Level

| Factor | Assessment |
|---|---|
| Sample size | 13 trades — limited — treat as preliminary |
| Win/Loss balance | 4W / 9L — small subgroups |
| Data source | Fresh production backtest with HEAD code — current architecture |
| MFE/MAE precision | Candle-based (M15 high/low), not tick-level |
| Missing data | Fusion scores, regime labels, CRT scores — not recoverable from logs |

**Overall confidence: LOW-MODERATE**

- Sample size (13 trades) is small — statistical significance is low.
- Winner/loser subgroups are too small for reliable feature clustering.
- Fusion scores were never captured by the backtest — feature analysis uses raw indicators only.
- MFE/MAE computed from M15 candle high/low (intra-candle excursions may differ from tick data).

## 9. Final Recommendation

1. **Do not optimize or tune** based on 13 trades — sample is insufficient for production decisions.
2. **The enriched dataset** (`results/research/bnbusdt_trade_dataset.csv`) is the permanent asset for future studies.
3. **Best holding horizon** appears to be `15m` based on 13 trades — but verify with larger sample.
4. **Win rate of 30.8%** at average R of -0.3574 suggests the current configuration does not produce a statistically significant edge on BNBUSDT M15.
5. **To improve confidence:** gather more trade data by:
   - Running a multi-instrument backtest for cross-comparison
   - Running multiple BNBUSDT backtests with different random seeds for variance estimation
   - Adding fusion score capture to the backtest output (requires code change)
6. **Feature engineering note:** The top discriminators identified above can guide feature selection, but should not be used for optimization until sample size increases.

---

*Report generated by `scripts/research/bnbusdt_analyze_report.py`*
*Date: 2026-06-13 02:56*
