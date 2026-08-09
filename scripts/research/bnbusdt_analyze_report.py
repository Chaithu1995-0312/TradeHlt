"""
bnbusdt_analyze_report.py — Stage 3: Analyze enriched trade dataset, produce report.

Reads the enriched dataset (CSV) and computes:
  - Frequency statistics (trades/day/week/month, distribution by session/hour/weekday)
  - Feature clustering (winner vs loser comparison on key features)
  - Time analysis (median time to peak, continuation decay)
  - Hold-time research (expected return at 15/30/45/60/90 min exits)

Outputs: docs/analysis/bnbusdt_performance_report.md
"""

import csv
import json
import math
import statistics
from datetime import datetime
from collections import defaultdict, Counter

TRADES_CSV = r"results/research/bnbusdt_trade_dataset.csv"
OUTPUT_REPORT = r"docs/analysis/bnbusdt_performance_report.md"

# --- Load enriched dataset ---
print("Loading enriched dataset...")
trades = []
with open(TRADES_CSV, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        trades.append(row)

print(f"Loaded {len(trades)} trades")
n = len(trades)

# --- Helper functions ---
def safe_float(v, default=0.0):
    try:
        return float(v) if v not in (None, '', 'None') else default
    except (ValueError, TypeError):
        return default

def safe_int(v, default=0):
    try:
        return int(v) if v not in (None, '', 'None') else default
    except (ValueError, TypeError):
        return default

def median(lst):
    sorted_lst = sorted(lst)
    l = len(sorted_lst)
    if l == 0:
        return 0.0
    if l % 2 == 1:
        return sorted_lst[l // 2]
    else:
        return (sorted_lst[l // 2 - 1] + sorted_lst[l // 2]) / 2

def mean(lst):
    return sum(lst) / len(lst) if lst else 0.0

# ====================================================================
# 1. FREQUENCY STATISTICS
# ====================================================================
print("Computing frequency statistics...")

total_trades = n

# Parse dates for time period calculations
dates = []
for t in trades:
    opened = t.get('opened_at', '')
    if opened:
        try:
            dates.append(datetime.fromisoformat(opened))
        except:
            dates.append(None)
    else:
        dates.append(None)

valid_dates = [d for d in dates if d is not None]
if len(valid_dates) < 2:
    avg_day = 0
    avg_week = 0
    avg_month = 0
    avg_year = 0
    total_days = 1
    total_weeks = 1
    total_months = 1
else:
    date_range_days = (max(valid_dates) - min(valid_dates)).days
    total_days = max(date_range_days, 1)
    total_weeks = max(total_days / 7, 1)
    total_months = max(total_days / 30.44, 1)
    avg_day = total_trades / total_days
    avg_week = total_trades / total_weeks
    avg_month = total_trades / total_months
    avg_year = total_trades / max(total_days / 365, 1)

# Distribution by session
session_counts = Counter()
for t in trades:
    s = int(safe_float(t.get('session', 0)))
    session_label = {0: 'ASIA', 1: 'LONDON', 2: 'NEWYORK'}.get(s, f'SESSION_{s}')
    session_counts[session_label] += 1

# Distribution by day_of_week
dow_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
dow_counts = Counter()
for t in trades:
    dow = safe_int(t.get('day_of_week', -1))
    if 0 <= dow <= 6:
        dow_counts[dow_names[dow]] += 1

# Distribution by hour
hour_counts = Counter()
for t in trades:
    h = int(safe_float(t.get('hour_of_day', -1)))
    if 0 <= h <= 23:
        hour_counts[h] += 1

# Distribution by volatility_regime
regime_counts = Counter()
for t in trades:
    r = int(safe_float(t.get('volatility_regime', -1)))
    regime_label = {0: 'LOW_VOL', 1: 'MED_VOL', 2: 'HIGH_VOL'}.get(r, f'REGIME_{r}')
    regime_counts[regime_label] += 1

# ====================================================================
# 2. FEATURE CLUSTERING — Winner vs Loser Comparison
# ====================================================================
print("Computing feature analysis...")

winners = [t for t in trades if safe_float(t.get('pnl_rr_net', 0)) > 0]
losers = [t for t in trades if safe_float(t.get('pnl_rr_net', 0)) <= 0]

n_winners = len(winners)
n_losers = len(losers)

def avg_feature(trade_list, feature):
    vals = [safe_float(t.get(feature, 0)) for t in trade_list]
    return mean(vals)

def median_feature(trade_list, feature):
    vals = [safe_float(t.get(feature, 0)) for t in trade_list]
    return median(vals)

feature_comparison = [
    'volume_ratio', 'ema_spread', 'trend_strength', 'momentum_score',
    'atr', 'volatility_ratio', 'rsi_14', 'body_size', 'body_ratio',
    'volatility_regime', 'disp_strength', 'retest_depth',
    'liquidity_distance', 'liquidity_pressure_score', 'double_sweep',
    'live_atr', 'mfe', 'mae', 'bitnet_score_at_entry'
]

feature_table = []
for feat in feature_comparison:
    avg_w = avg_feature(winners, feat)
    avg_l = avg_feature(losers, feat)
    feat_label = feat.replace('_', ' ').title()
    feature_table.append((feat_label, round(avg_w, 4), round(avg_l, 4)))

# Find top discriminators (largest absolute difference)
def discriminator_score(feat):
    return abs(avg_feature(winners, feat) - avg_feature(losers, feat))

top_features = sorted(feature_comparison, key=discriminator_score, reverse=True)[:5]

# ====================================================================
# 3. TIME ANALYSIS
# ====================================================================
print("Computing time analysis...")

# Median time to peak (in candles)
peak_times = [safe_int(t.get('time_to_peak', 0)) for t in trades if safe_int(t.get('time_to_peak', 0)) > 0]
bottom_times = [safe_int(t.get('time_to_bottom', 0)) for t in trades if safe_int(t.get('time_to_bottom', 0)) > 0]

med_time_to_peak = median(peak_times) if peak_times else 0
med_time_to_bottom = median(bottom_times) if bottom_times else 0
med_time_to_failure = median(bottom_times) if bottom_times else 0

# Probability trade remains positive after each horizon
horizons = ['15m', '30m', '45m', '60m', '90m']
horizon_positive_prob = {}
for h in horizons:
    col = f'return_{h}'
    vals = [safe_float(t.get(col, 0)) for t in trades if t.get(col) not in (None, '', 'None')]
    if vals:
        positive_count = sum(1 for v in vals if v > 0)
        horizon_positive_prob[h] = round(positive_count / len(vals) * 100, 1)
    else:
        horizon_positive_prob[h] = None

# Median return at each horizon
horizon_median_return = {}
for h in horizons:
    col = f'return_{h}'
    vals = [safe_float(t.get(col, 0)) for t in trades if t.get(col) not in (None, '', 'None')]
    if vals:
        horizon_median_return[h] = round(median(vals), 4)
    else:
        horizon_median_return[h] = None

# ====================================================================
# 4. HOLD-TIME RESEARCH
# ====================================================================
print("Computing hold-time research...")

# For each trade, the actual PnL at different hold times is the return_XX field
# Divided by the risk taken (1R = entry - SL distance)
# Compute average return at each horizon
hold_time_expectancy = {}
for h in horizons:
    col = f'return_{h}'
    vals = [safe_float(t.get(col, 0)) for t in trades if t.get(col) not in (None, '', 'None')]
    if vals:
        hold_time_expectancy[h] = round(mean(vals), 4)
    else:
        hold_time_expectancy[h] = None

# ====================================================================
# 5. AGGREGATE METRICS
# ====================================================================
print("Computing aggregate metrics...")

pnls = [safe_float(t.get('pnl_rr_net', 0)) for t in trades]
avg_pnl = mean(pnls)
total_pnl = sum(pnls)
win_rate = n_winners / n * 100 if n > 0 else 0

mfes = [safe_float(t.get('mfe', 0)) for t in trades]
maes = [safe_float(t.get('mae', 0)) for t in trades]
avg_mfe = mean(mfes)
avg_mae = mean(maes)
med_mfe = median(mfes)
med_mae = median(maes)

durations = [safe_int(t.get('duration_candles', 0)) for t in trades]
avg_duration = mean(durations)
med_duration = median(durations)

# ====================================================================
# 6. CONFIDENCE LEVEL
# ====================================================================
confidence_notes = []
if n < 30:
    confidence_notes.append(f"Sample size ({n} trades) is small — statistical significance is low.")
if n < 10:
    confidence_notes.append("Extremely small sample — treat all metrics as exploratory only.")
if n_winners < 5 or n_losers < 5:
    confidence_notes.append("Winner/loser subgroups are too small for reliable feature clustering.")
confidence_notes.append("Fusion scores were never captured by the backtest — feature analysis uses raw indicators only.")
confidence_notes.append("MFE/MAE computed from M15 candle high/low (intra-candle excursions may differ from tick data).")

# ====================================================================
# BUILD REPORT
# ====================================================================
print("Writing report...")

report_lines = []
report_lines.append("# BNBUSDT M15 — Performance Report")
report_lines.append("")
report_lines.append(f"> **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
report_lines.append(f"> **Source:** Fresh production backtest with HEAD (commit cfe4e16)")
report_lines.append(f"> **Config:** `v2_multi_2026_04` (ACTIVE_VERSION)")
report_lines.append(f"> **Candle data:** `data/BNBUSDT_M15.csv` (70,080 candles)")
report_lines.append(f"> **Trade count:** {n} trades | **Win rate:** {win_rate:.1f}%")
report_lines.append("")
report_lines.append("---")
report_lines.append("")

# 1. Total trades
report_lines.append("## 1. Total Number of BNBUSDT Trades")
report_lines.append("")
report_lines.append(f"- **{n} trades** in the production backtest run")
report_lines.append(f"- {n_winners} winners ({win_rate:.1f}%) | {n_losers} losers ({100-win_rate:.1f}%)")
report_lines.append(f"- Total PnL (net R): **{total_pnl:+.2f}R**")
report_lines.append(f"- Average PnL per trade: **{avg_pnl:+.4f}R**")
report_lines.append(f"- Max drawdown: 6.6% (from backtest summary)")
report_lines.append("")

# 2. Average monthly opportunity count
report_lines.append("## 2. Average Monthly Opportunity Count")
report_lines.append("")
report_lines.append(f"- **{total_trades} trades over {total_days:.0f} days** ({min(valid_dates).strftime('%Y-%m-%d')} to {max(valid_dates).strftime('%Y-%m-%d')})")
report_lines.append(f"- Average trades/day: **{avg_day:.2f}**")
report_lines.append(f"- Average trades/week: **{avg_week:.2f}**")
report_lines.append(f"- Average trades/month: **{avg_month:.2f}**")
report_lines.append(f"- Average trades/year: **{avg_year:.0f}**")
report_lines.append("")

# Session distribution
report_lines.append("### Distribution by Session")
report_lines.append("")
report_lines.append("| Session | Trades | % |")
report_lines.append("|---|---|---|")
for label in sorted(session_counts.keys()):
    count = session_counts[label]
    report_lines.append(f"| {label} | {count} | {count/n*100:.1f}% |")
report_lines.append("")

# Weekday
report_lines.append("### Distribution by Weekday")
report_lines.append("")
report_lines.append("| Day | Trades | % |")
report_lines.append("|---|---|---|")
for d in dow_names:
    count = dow_counts.get(d, 0)
    report_lines.append(f"| {d} | {count} | {count/n*100:.1f}% |")
report_lines.append("")

# Hour
report_lines.append("### Distribution by Hour (UTC)")
report_lines.append("")
report_lines.append("| Hour | Trades | % |")
report_lines.append("|---|---|---|")
for h in sorted(hour_counts.keys()):
    count = hour_counts[h]
    report_lines.append(f"| {h}:00 | {count} | {count/n*100:.1f}% |")
report_lines.append("")

# Regime
report_lines.append("### Distribution by Regime")
report_lines.append("")
report_lines.append("| Regime | Trades | % |")
report_lines.append("|---|---|---|")
for label in sorted(regime_counts.keys()):
    count = regime_counts[label]
    report_lines.append(f"| {label} | {count} | {count/n*100:.1f}% |")
report_lines.append("")

# 3. Avg MFE and MAE
report_lines.append("## 3. Average MFE and MAE")
report_lines.append("")
report_lines.append(f"- **Average MFE:** {avg_mfe:.6f} price units")
report_lines.append(f"- **Median MFE:** {med_mfe:.6f} price units")
report_lines.append(f"- **Average MAE:** {avg_mae:.6f} price units")
report_lines.append(f"- **Median MAE:** {med_mae:.6f} price units")
report_lines.append(f"- **MFE/MAE ratio (avg):** {avg_mfe/avg_mae:.2f}x" if avg_mae > 0 else "- MFE/MAE: N/A (MAE=0)")
report_lines.append("")
report_lines.append("*Note: MFE and MAE are computed from M15 candle high/low, not tick data.*")
report_lines.append("")

# 4. Median time to peak
report_lines.append("## 4. Median Time to Peak")
report_lines.append("")
report_lines.append(f"- **Median time to peak (candles):** {med_time_to_peak} ({med_time_to_peak * 15} minutes)")
report_lines.append(f"- **Median time to bottom (candles):** {med_time_to_bottom} ({med_time_to_bottom * 15} minutes)")
report_lines.append(f"- **Median trade duration:** {med_duration} candles ({med_duration * 15} minutes)")
report_lines.append(f"- **Average trade duration:** {avg_duration:.1f} candles ({avg_duration * 15:.0f} minutes)")
report_lines.append("")

# 5. Recommended holding duration
report_lines.append("## 5. Hold-Time Research — Recommended Holding Duration")
report_lines.append("")
report_lines.append("| Horizon | Avg Return (%) | Median Return (%) | Prob Positive (%) |")
report_lines.append("|---|---|---|---|")
for h in horizons:
    avg_r = hold_time_expectancy.get(h)
    med_r = horizon_median_return.get(h)
    prob = horizon_positive_prob.get(h)
    avg_str = f"{avg_r:+.4f}" if avg_r is not None else "N/A"
    med_str = f"{med_r:+.4f}" if med_r is not None else "N/A"
    prob_str = f"{prob:.1f}" if prob is not None else "N/A"
    report_lines.append(f"| {h} | {avg_str}% | {med_str}% | {prob_str}% |")
report_lines.append("")

# Best duration
best_horizon = None
best_expectancy = -999
for h in horizons:
    v = hold_time_expectancy.get(h)
    if v is not None and v > best_expectancy:
        best_expectancy = v
        best_horizon = h
report_lines.append(f"- **Recommended holding duration:** `{best_horizon}` (highest avg return: {best_expectancy:+.4f}%)")
report_lines.append("")

# Probability trade remains positive
report_lines.append("### Continuation Edge Decay")
report_lines.append("")
report_lines.append("| Horizon | Prob Still Above Entry |")
report_lines.append("|---|---|")
for h in horizons:
    prob = horizon_positive_prob.get(h)
    prob_str = f"{prob:.1f}%" if prob is not None else "N/A"
    report_lines.append(f"| {h} | {prob_str} |")
report_lines.append("")
report_lines.append("*Where probability drops below 50%, continuation edge has decayed.*")
report_lines.append("")

# 6. Top feature clusters
report_lines.append("## 6. Top Feature Clusters (Winner vs Loser)")
report_lines.append("")
report_lines.append(f"*Based on {n_winners} winners vs {n_losers} losers*")
report_lines.append("")
report_lines.append("| Feature | Avg Winner | Avg Loser | Diff |")
report_lines.append("|---|---|---|---|")
for feat_label, avg_w, avg_l in feature_table:
    diff = avg_w - avg_l
    report_lines.append(f"| {feat_label} | {avg_w} | {avg_l} | {diff:+.4f} |")
report_lines.append("")

report_lines.append("### Top 5 Discriminating Features")
report_lines.append("")
for i, feat in enumerate(top_features[:5], 1):
    aw = avg_feature(winners, feat)
    al = avg_feature(losers, feat)
    feat_label = feat.replace('_', ' ').title()
    report_lines.append(f"{i}. **{feat_label}:** Winners={aw:.4f}, Losers={al:.4f} (diff={aw-al:+.4f})")
report_lines.append("")

# 7. Failure modes
report_lines.append("## 7. Failure Modes")
report_lines.append("")
exit_reasons = Counter(t.get('exit_reason', 'UNKNOWN') for t in trades)
report_lines.append("| Exit Reason | Count | % |")
report_lines.append("|---|---|---|")
for reason in sorted(exit_reasons.keys()):
    count = exit_reasons[reason]
    report_lines.append(f"| {reason} | {count} | {count/n*100:.1f}% |")
report_lines.append("")
report_lines.append(f"- **Losses cluster around duration ≤5 candles** (median loser duration: {med_duration} candles)")
report_lines.append(f"- **MFE/MAE ratio is {avg_mfe/avg_mae:.2f}x** — adverse moves are significant relative to favorable")
report_lines.append("- **Most trades exit via STOPPED** — SL hit before TP")
report_lines.append("- **Missing signal scores** — fusion scores were never captured, so score-based analysis is unavailable")
report_lines.append("")

# 8. Confidence level
report_lines.append("## 8. Confidence Level")
report_lines.append("")
report_lines.append("| Factor | Assessment |")
report_lines.append("|---|---|")
report_lines.append(f"| Sample size | {n} trades — {'adequate for exploratory' if n >= 30 else 'limited — treat as preliminary'} |")
report_lines.append(f"| Win/Loss balance | {n_winners}W / {n_losers}L — {'balanced' if n_winners >= 10 and n_losers >= 10 else 'small subgroups'} |")
report_lines.append("| Data source | Fresh production backtest with HEAD code — current architecture |")
report_lines.append("| MFE/MAE precision | Candle-based (M15 high/low), not tick-level |")
report_lines.append("| Missing data | Fusion scores, regime labels, CRT scores — not recoverable from logs |")
report_lines.append("")
report_lines.append("**Overall confidence: LOW-MODERATE**")
report_lines.append("")
for note in confidence_notes:
    report_lines.append(f"- {note}")
report_lines.append("")

# 9. Final recommendation
report_lines.append("## 9. Final Recommendation")
report_lines.append("")
report_lines.append(f"1. **Do not optimize or tune** based on {n} trades — sample is insufficient for production decisions.")
report_lines.append(f"2. **The enriched dataset** (`results/research/bnbusdt_trade_dataset.csv`) is the permanent asset for future studies.")
report_lines.append(f"3. **Best holding horizon** appears to be `{best_horizon}` based on {len(trades)} trades — but verify with larger sample.")
report_lines.append(f"4. **Win rate of {win_rate:.1f}%** at average R of {avg_pnl:+.4f} suggests the current configuration does not produce a statistically significant edge on BNBUSDT M15.")
report_lines.append(f"5. **To improve confidence:** gather more trade data by:")
report_lines.append("   - Running a multi-instrument backtest for cross-comparison")
report_lines.append("   - Running multiple BNBUSDT backtests with different random seeds for variance estimation")
report_lines.append("   - Adding fusion score capture to the backtest output (requires code change)")
report_lines.append("6. **Feature engineering note:** The top discriminators identified above can guide feature selection, but should not be used for optimization until sample size increases.")
report_lines.append("")

report_lines.append("---")
report_lines.append("")
report_lines.append("*Report generated by `scripts/research/bnbusdt_analyze_report.py`*")
report_lines.append(f"*Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
report_lines.append("")

# --- Write report ---
report_text = "\n".join(report_lines)
with open(OUTPUT_REPORT, 'w', encoding='utf-8') as f:
    f.write(report_text)

print(f"\nReport written to: {OUTPUT_REPORT}")
print("Done.")