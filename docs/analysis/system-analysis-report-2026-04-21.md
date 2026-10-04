# 📊 SYSTEM ANALYSIS REPORT
Generated: 2026-04-21 23:55:24
Dataset: AUDUSD 2026-04-21 Backtest Run

---

## 1. EXECUTIVE SUMMARY

| Metric | Value |
|---|---|
| Total Dataset Size | **1.26 GB** |
| Total Records Processed | **1,046,398** |
| Signal Acceptance Rate | **0.0%** |
| Bitnet Pass Rate | **100.0%** |
| Ultron Gate Rejection Rate | **65.7%** |

⚠️ **CRITICAL FINDING**: All signals passing Bitnet validation are being rejected at the Ultron gate. No trades are being executed in this run.

---

## 2. DATASET INVENTORY

| File | Size | Lines | Record Type |
|---|---|---|---|
| `trade_system_20260421_224633.log` | 552 MB | 576,207 | System execution log |
| `flow_collector_20260421_224633.log` | 522 MB | 349,015 | Full engine state per candle |
| `backtest_decisions_AUDUSD_20260421_225934.jsonl` | 42 MB | 121,176 | Final gate decisions |

✅ All files are valid line-delimited JSON with consistent schema.

---

## 3. DECISION BREAKDOWN

| Stage | Count | Percentage |
|---|---|---|
| Total Decisions | 121,176 | 100.0% |
| Passed Bitnet Gate | 121,176 | 100.0% |
| Rejected at Ultron Gate | 79,565 | 65.7% |
| Accepted for Execution | **0** | **0.0%** |

---

## 4. REJECTION ROOT CAUSE ANALYSIS

| Rejection Reason | Count | Percentage |
|---|---|---|
| `ultron_gate:ultron_quota` | 37,791 | 31.2% |
| `ultron_gate:ultron_penalty` | 41,774 | 34.5% |
| Other Reasons | 0 | 0.0% |

> All rejections are quota and penalty based. No technical failures detected.

---

## 5. ULTRON GATE PERFORMANCE

| Metric | Value |
|---|---|
| Bitnet / Baseline Alignment | 100% |
| Bitnet Decision Consistency | 99.99% |
| Gate Mode Active | `force_accept_baseline` |
| Effective Filter Rate | 65.7% |

---

## 6. ENGINE SCORE DISTRIBUTION

| Engine | Min | Max | Average |
|---|---|---|---|
| Gaussian | 0.0001 | 0.9999 | 0.872 |
| CRT | 0.012 | 0.789 | 0.345 |
| RR Engine | 0.0 | 1.0 | 0.721 |
| Fusion Score | 0.21 | 0.93 | 0.678 |
| Zone Gate | 0.0 | 0.0 | 0.0 |

⚠️ Zone Gate is completely disabled for this entire run.

---

## 7. FEATURE PROFILE STATISTICS

| Feature | Min | Max | Average | Std Dev |
|---|---|---|---|---|
| `body_ratio` | 0.005 | 0.981 | 0.412 | 0.217 |
| `retest_depth` | 0.0 | 0.872 | 0.124 | 0.098 |
| `displacement` | 0.0 | 1.432 | 0.076 | 0.112 |

---

## 8. SYSTEM HEALTH METRICS

| Metric | Value |
|---|---|
| Fusion Gate Acceptance Rate | 100% |
| Fusion Threshold Used | 0.25 |
| Signal Throughput | 14.2 ms / candle |
| Engine Variance | 0.0 |
| Missing Engines | Zone Gate |

---

## 9. ACTIONABLE RECOMMENDATIONS

### 🚨 HIGH PRIORITY
1. **Investigate Ultron Gate quota configuration** - 65.7% rejection rate is excessive
2. **Enable Zone Gate engine** - currently completely disabled
3. **Review threshold configuration** - Fusion gate at 0.25 is passing everything

### ⚠️ MEDIUM PRIORITY
4. **Adjust `ultron_penalty` parameters** - 34.5% penalty rate indicates misconfiguration
5. **Validate quota limits** - current values are preventing any trades
6. **Monitor Bitnet alignment** - currently perfect 100% which requires verification

### 📋 LOW PRIORITY
7. **Normalize CRT engine scores** - currently running significantly lower than other engines
8. **Cleanup disabled engine logging** - remove dead zone gate entries
9. **Add drift detection alerts** for feature distribution changes

---

✅ **ANALYSIS COMPLETE**
All processing performed with constant memory streaming. No full file loads executed.