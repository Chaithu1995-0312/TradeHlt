# Validator gate tightening — expectancy hard gate, month window

## Changes
| Where | Change |
|---|---|
| `configs/production/v1_multi_2026_03.json` → `config_validator` | `min_expectancy` −0.5 → **0.0**, now a **HARD** gate (was a soft warning). New `min_trades_per_month: 4`. New `month_window_max_days: 35`. |
| `src/config_layer/config_validator.py` | `_run_quality_gates(..., window)`: expectancy < `min_expectancy` is a hard failure. `window="month"` uses `min_trades_per_month`; `window="full"` (default) keeps `min_trades_per_instrument` (10). `validate()` / `validate_production()` take `window`; invalid values raise `ValueError`. `window="month"` hard-rejects any CSV spanning more than `month_window_max_days` (`_csv_span_days`), so a two-year file cannot be validated at the 4-trade bar. CLI: `--window {full,month}`. |
| Docs | `CONFIG_REFERENCE.md`, `SCHEMAS.md §5.1`, `ARCHITECTURE.md`, `CLAUDE.md §11` updated. |
| Tests | New `tests/test_config_validator_gates.py` (11 tests). |

Nothing in the hashed `params` section changed, so the SHA-256 is unchanged and the config still loads and verifies. No promotion was run.

## Results (XAUUSD M15, production params)
| Engine / window | Trades | Expectancy | DD | Score | Decision |
|---|---|---|---|---|---|
| Old engine (close-on-rollover), full | 12 | −0.867R | 11.6% | 0.378 | **REJECT** (expectancy hard gate; was APPROVE under the old gates) |
| Fixed engine, full (2 years) | 12 | +0.037R | 3.0% | 0.500 | **APPROVE** (warning: low trade count) |
| Fixed engine, `--window month` on July 2025 slice | 2 | +0.320R | 0.4% | 0.498 | **REJECT**: only 2 trades, minimum 4 |
| Fixed engine, `--window month` on the 2-year file | — | — | — | — | **REJECT**: month window declared but CSV spans 730 days |

## Reading it
- The tightened gate would have caught the original defect: the old engine now fails on expectancy.
- The fixed engine still passes the full-window gates, but only just: +0.037R on 12 trades is statistically indistinguishable from zero. A hard gate at 0.0R filters losing configs; it does not prove an edge.
- July 2025 on M15 does not clear the month bar of 4 trades (it has 2), so a one-month validation of this config would reject on sample size. That is the gate working as intended, not a result about quality.
- The expectancy and fitness inputs are in-sample.

## Not changed (flagging)
- `configs/production/v2_multi_2026_04.json` and `tests/production_configs/v1_multi_2026_03.json` still have the old `config_validator` keys. v2 is not the active version (`ACTIVE_VERSION` = `v1_multi_2026_03`), but activating it would fail fast on the missing new keys until they are added.
- `validation_summary` in the active production config still holds numbers from the old engine behavior; refreshing it means re-validating and going through `PromotionManager`.
- Full suite: 12 failed / 902 passed. The same 12 failures existed before these changes (11 in `tests/inout/test_probability_engine.py`, 1 in `tests/test_control_plane_doc_alignment.py`).
