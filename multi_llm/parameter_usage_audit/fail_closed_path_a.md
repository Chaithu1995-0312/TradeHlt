# Fail-closed Path A — change log

Applied on D:\Tradelatest 2026-09-19 after P2.5 Path A (prod fallbacks dormant).

## Primary
- src/features/crt_state_resolver.py — thr[] for retest_depth_max, body_ratio_min, atr_multiplier_min, expansion_atr_min_distance
- src/config_layer/state_identity.py — CRTConfig four fields required
- scripts/backtest/manual_backtest.py — authority constants
- scripts/research/retest_divergence_probe.py — thr[] for retest_depth_max
- tests/helpers/crt_config.py — crt_config_for_test(**overrides)
- tests + msip + some scripts — CRTConfig() → crt_config_for_test()

## Unchanged
- FOREX/CRYPTO Overrides
- Prod declare numbers
