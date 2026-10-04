# Envelope Offline Train — ENV_OFFLINE_TRAIN_V1

| Field | Value |
|-------|--------|
| created | 2026-07-28T06:24:09.843588+00:00 |
| instrument | XAUUSD |
| protocol | TN_ENV_CLEAN_L2 |
| protocol_hash | `1808c5a9faa63cab49d7d9b8d3f33f44c7ba5979a0e87420e94d60b58e47cf84` |
| n_rows | 94332 |
| status | **TRAIN_COMPLETE** |
| signal_rollup | **SIGNAL_RETAINED** |
| authority | research offline only |

## Test metrics (primary = Spearman IC)

| Head | test IC | val IC | gap | RMSE | R² | long IC | short IC | Tag |
|------|---------|--------|-----|------|----|---------|----------|-----|
| `mfe_r` | 0.1837 | 0.2584 | 0.0747 | 3.8779 | 0.0229 | 0.1426 | 0.2224 | **SIGNAL_RETAINED** |
| `mae_r_heat` | 0.1458 | 0.2367 | 0.091 | 3.9309 | -0.004 | 0.2073 | 0.0823 | **SIGNAL_RETAINED** |
| `holding_bars` | 0.3562 | 0.3953 | 0.0392 | 6.7733 | 0.1067 | 0.3405 | 0.3739 | **SIGNAL_RETAINED** |
| `time_to_mfe` | 0.2324 | 0.2591 | 0.0267 | 5.6596 | 0.0808 | 0.2375 | 0.2387 | **SIGNAL_RETAINED** |

IC retain floor: 0.1

## Explicit non-claims

- No production KEEP
- No Fusion / planner / neural_fn
- No TradeNet outcome training
- PIT unclean features inherited — GATE-P forbidden

Artifacts under run directory; dataset_sha256=`be97b7519045753b…`
