# Ladder research clones vs v2_htfcrt_2026_08

Files: `configs/research/ladder_h1.json`, `configs/research/ladder_h4.json`.
The `params` block and `config_hash` are unchanged. `configs/production` is not edited.
No D1 clone: one month cannot support a D1 ladder, and D1 is Step 4.

## H1

| Knob | Active | Ladder | Changed |
|---|---|---|---|
| `setup.entry_semantics` | `approval_bar_legacy` | `resting_order` | yes |
| `setup.trade_ttl_candles` | `None` | `240` | yes |
| `crt_engine.max_expansion_age_hours` | `124` | `0` | yes |
| `backtest.gap_reset_minutes` | `120` | `180` | yes |
| `backtest.htf_clock_basis` | `count` | `calendar` | yes |
| `backtest.engine_gate_enabled` | `True` | `False` | yes |
| `backtest.timeframe` | `M15` | `H1` | yes |
| `parent_crt.timeframe` | `H4` | `H4` | no |
| `engine_runner.allowed_sessions` | `['london', 'new_york', 'overlap']` | `['london', 'new_york', 'overlap']` | no |

## H4

| Knob | Active | Ladder | Changed |
|---|---|---|---|
| `setup.entry_semantics` | `approval_bar_legacy` | `resting_order` | yes |
| `setup.trade_ttl_candles` | `None` | `60` | yes |
| `crt_engine.max_expansion_age_hours` | `124` | `0` | yes |
| `backtest.gap_reset_minutes` | `120` | `600` | yes |
| `backtest.htf_clock_basis` | `count` | `calendar` | yes |
| `backtest.engine_gate_enabled` | `True` | `False` | yes |
| `backtest.timeframe` | `M15` | `H4` | yes |
| `parent_crt.timeframe` | `H4` | `D1` | yes |
| `engine_runner.allowed_sessions` | `['london', 'new_york', 'overlap']` | `['london', 'new_york', 'overlap', 'asia', 'off_session']` | yes |

Stop floor 1.5×ATR is not an engine key. It is applied in `research.timeframe_ladder.stop_floor`.
