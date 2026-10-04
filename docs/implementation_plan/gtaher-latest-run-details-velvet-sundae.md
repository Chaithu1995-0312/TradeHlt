# Latest XAUUSD corpus run — gathered details (read-only, no code change)

## Context
User asked to gather the latest run details on the XAUUSD corpus. Pure read-only lookup; no implementation planned.

## Latest run
`results/run_20260923_072728_XAUUSD__20240522..20260521_v2_htfcrt_2026_08_7de09f62/` (artifacts written 2026-09-23 12:58 local)

- Config `v2_htfcrt_2026_08`, hash `7de09f62…d613`; dataset hash `4d73f5ce…6ba56`; identity VERIFIED
- Corpus `data/mt5/XAUUSD_M15.csv`, 47,275 rows, 2024-05-22 01:00 → 2026-05-21 23:45; 121 session-gap resets
- Cost model `backtest_g1g2_v2`; risk denominator `entry_fill_to_sl__v1`; HTF clock basis `count`, 16 candles/range
- 3 setups / 3 approved / 0 rejected; win rate 33.3%; PF 0.27
- PnL raw −0.32R, net −1.69R (cost drag 1.37R); avg RR net −0.56R; max DD 2.31R (2.3%); return −1.7%
- Trades: CRT-0001 LONG 2024-11-12 STOPPED −1.05R; CRT-0002 LONG 2024-11-15 STOPPED −1.25R; CRT-0003 LONG 2025-02-25 TP2 +0.61R
- State funnel: RANGE 22185, SWEEP 15566, DISPLACEMENT 778, EXPANSION 8632, RETEST 26, EXECUTION 4, SHADOW_PENDING 6
- G001 goal report: FAIL (trades/month 0.19 vs ≥20; avg RR, win rate, expectancy all short)
- Byte-identical headline numbers to prior run `run_20260922_044800_…` (same config/dataset hash)

## Downstream artifacts (2026-09-23)
- `results/research/bar_matrix/XAUUSD_M15/` (bar_matrix + features parquet/csv)
- `results/research/oracle_labels/XAUUSD_M15/labels.csv` (~378k units)
- `results/layer_trace/XAUUSD_layer_trace.jsonl` 900 MB, last touched 2026-09-24 14:21 (shared append file, not a fresh run)

## Caveats
- Session log 2026-09-24 records F1–F4 K23 changes as code-only, flags OFF; no post-fix run exists yet.
- Working tree dirty (32+ src files), so "latest run" reflects pre-fix code.

## Verification
Figures read directly from run_manifest.json, XAUUSD_summary.json, XAUUSD_report.txt, XAUUSD_trades.csv.
