# XAUUSD Identity Certification (2-year shadow)

> L5 close/outcome writer authorized 2026-08-23 (`CH-identity-l5-outcome-writer`). Frozen L5 PK is L4 PK + `walk_kernel` + `cost_model_id` + `fill_model_id` — not `trade_id`. 4/4 engine closes recovered via IdentityQuery. Production approved remains false.
>
> **Executed-close freeze (user 2026-08-23, `CH-identity-l5-executed-record-freeze`):** these 4 PRESERVED L5 rows are the complete historical record of CRTEngine closes on this corpus and basis. They are not the market's structural trade set. F-086 remains the definitive answer on whether the declared M15 vocabulary marks a profitable entry bar. No 100% window scan. No TradeLib. Not production.

**Gate:** `XAUUSD_IDENTITY_CERTIFICATION`
**Status:** **PASS**
**Production approved:** False
**Corpus:** `data/mt5/XAUUSD_M15.csv`
**corpus_sha256:** `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56`
**Rows:** 47275

| Check | Required | Result |
|---|---|---|
| L0 identities written | Count | 47275 |
| L1 identities written | Count | 47197 |
| L2 identities written | Count | 613561 |
| L3 occupancies written | Count | 47275 |
| L3 events written | Count | 4871 |
| RESET events present | YES/NO | YES |
| L4 geometries written | Count | 4 |
| L5 outcomes written | Count | 4 |
| UNIDENTIFIED records | Count | 0 |
| IDENTITY_INCOMPLETE records | Count | 0 |
| IDENTITY_MISMATCH records | Count | 0 |
| CRT process_candle errors (isolated) | Count | 0 |
| Query PRESERVED L0 | Count | 47275 |
| Query PRESERVED L1 | Count | 47197 |
| Query PRESERVED L2 | Count | 613561 |
| Query PRESERVED L3 occupancy | Count | 47275 |
| Query PRESERVED L3 events | Count | 4871 |
| Query PRESERVED L4 | Count | 4 |
| Query PRESERVED L5 | Count | 4 |

## Gate (not production)

```text
L0–L5 recoverable via IdentityQuery  (of what was written)
No recompute path on QUERY
No HEAD dependency on QUERY
No identity mismatch
```

**Certification:** PASS
**Production Approved:** NO (gate requires this report; promotion is a separate authorization).

## Errors

- none

CRTConfig: version=`v2_htfcrt_2026_08` mode=`PRODUCTION_MERGED` instrument=`XAUUSD`

L3 occupancy state histogram:
- RANGE: 20786
- SWEEP: 14432
- EXPANSION: 11228
- DISPLACEMENT: 760
- RETEST: 29
- EXPIRED: 28
- EXECUTION: 6
- SHADOW_PENDING: 6

Engine event_log kinds (raw, before identity write):
- BEGIN_SOFT_CONF: 27
- CONFIRMATION_FAILED: 1
- FILTER_REJECTED: 21
- RESET: 2595
- STATE_TRANSITION: 2276
- SWEEP: 1673
- TRADE_OPENED: 4
- TRADE_STOPPED: 3
- TRADE_TP1: 1
- TRADE_TP2: 1

## Executed CRT closes (frozen identity record)

Scope: instrument `XAUUSD` · timeframe `M15` · corpus `data/mt5/XAUUSD_M15.csv` (`4d73f5ce…`) · producer CRTEngine · `geometry_kind=engine_trade` · `geometry_schema=dual_tp_partial` · `walk_kernel=backtest_ledger` · `cost_model_id=none_gross` · `fill_model_id=engine_intrabar`.

This is the executed CRT close book for that basis. It is not an every-bar oracle and does not reopen F-086.

| bar_open_ts | direction | entry_px | sl_px | exit_reason | y_R_gross | mfe | mae | duration_bars |
|---|---|---|---|---|---|---|---|---|
| 2024-11-12T15:30:00 | long | 2614.46 | 2610.04757143 | TRADE_STOPPED | −1.0 | 0.0884 | 2.0193 | 2 |
| 2024-11-15T07:45:00 | long | 2565.48 | 2564.55985714 | TRADE_STOPPED | −1.0 | 0.0000 | 10.3245 | 2 |
| 2025-02-25T15:45:00 | long | 2934.39 | 2933.20985714 | TRADE_TP2 | +1.75 | 7.1856 | 1.1185 | 3 |
| 2026-03-03T15:15:00 | long | 5163.98 | 5131.76071429 | TRADE_STOPPED | −1.0 | 0.6915 | 1.1304 | 3 |

On-disk store (gitignored): `results/identity_cert/xauusd_m15_2y_l5`. The table above is the tracked copy.

## Notes

- WRITE used FeaturePipeline / FeatureStateEncoder / CRTEngine as producers.
- QUERY used IdentityQuery / Identity Check only.
- L5 written on engine close (STOPPED/TP2/STOPPED_STRUCTURAL/ABORTED) under named backtest_ledger + none_gross + engine_intrabar. Missing cost/fill is not defaulted.
- 2-year mt5 corpus run.
- L3 WRITE uses ACTIVE_VERSION CRTConfig + HTFBuilder clock + initialise_range (BacktestRunner path). Isolated process_candle(htf_id='') stays RANGE.
- Executed-close freeze 2026-08-23: 4-of-4 L5 is the complete CRTEngine close record for this corpus/basis. F-086 remains definitive on M15 structural tradeability.
- Not production. Not live-spine. Grants no G001.
