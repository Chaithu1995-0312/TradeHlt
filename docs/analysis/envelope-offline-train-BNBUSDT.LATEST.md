# Envelope Offline Train — ENV_OFFLINE_TRAIN_V1

| Field | Value |
|-------|--------|
| created | 2026-07-21T22:41:28.312108+00:00 |
| instrument | BNBUSDT |
| protocol | TN_ENV_CLEAN_L2 |
| protocol_hash | `09beb48635248dd077a7fc9b96b8ec30b9b7e10b67ac9c7b051de8799f1a0ec8` |
| n_rows | 139942 |
| status | **TRAIN_COMPLETE** |
| signal_rollup | **SIGNAL_RETAINED** |
| authority | research offline only |

## Test metrics (primary = Spearman IC)

| Head | test IC | val IC | gap | RMSE | R² | long IC | short IC | Tag |
|------|---------|--------|-----|------|----|---------|----------|-----|
| `mfe_r` | 0.1864 | 0.1884 | 0.002 | 4.2916 | -0.1239 | 0.2015 | 0.1719 | **SIGNAL_RETAINED** |
| `mae_r_heat` | 0.1835 | 0.1923 | 0.0088 | 4.1778 | -0.0651 | 0.1721 | 0.1954 | **SIGNAL_RETAINED** |
| `holding_bars` | 0.3062 | 0.2753 | -0.0309 | 6.9481 | 0.0821 | 0.3058 | 0.2893 | **SIGNAL_RETAINED** |
| `time_to_mfe` | 0.2027 | 0.1741 | -0.0287 | 5.5814 | 0.0473 | 0.2065 | 0.1982 | **SIGNAL_RETAINED** |

IC retain floor: 0.1

## Explicit non-claims

- No production KEEP
- No Fusion / planner / neural_fn
- No TradeNet outcome training
- PIT unclean features inherited — GATE-P forbidden

Artifacts under run directory; dataset_sha256=`0ad3d5502bbe256a…`
