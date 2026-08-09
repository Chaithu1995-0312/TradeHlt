# Envelope Shadow Weight-0 — ENV_SHADOW_W0_V1

| Field | Value |
|-------|--------|
| created | 2026-07-21T23:01:08.555531+00:00 |
| status | **SHADOW_COMPLETE** |
| calibration_ok | True |
| n_ok | 139942 |
| n_err | 0 |
| weight_violations | 0 |
| decision_weight | **0.0** (hard) |
| spine_consumed | **false** |

## Calibration vs clean actuals (diagnostic)

| Head | Spearman IC | pred_mean | actual_mean |
|------|-------------|-----------|-------------|
| `mfe_r` | 0.2157 | 4.255213 | 3.879448 |
| `mae_r_heat` | 0.2178 | 4.219125 | 3.879448 |
| `holding_bars` | 0.3443 | 6.431142 | 6.520916 |
| `time_to_mfe` | 0.2158 | 4.640761 | 4.598813 |

## Non-claims

- Zero decision / fusion / planner influence
- Not ENV-P, not production KEEP
- Not a TradeNet reopen
