# feature_schema.bridge.md

> **GENERATED — do not edit by hand.** Regenerate with `python scripts/analysis/gen_bridge_layer.py`.

The FM-ID ↔ concept ↔ vector-index ↔ authority bridge. Every row is read from `src/features/feature_schema.py` and `configs/formulas/market_ontology.yaml` at generation time.

Schema dimension **48** · `SCHEMA_HASH` `d40e7c7d5b624ef6d27670255ad95a35` · `FEATURE_ORDER_HASH` `7901bb0d34f3d0af`

## Vector index ↔ identity ↔ concept

| Idx | Canonical name | FM-ID | Ontology section | Category | Concept(s) |
|---:|---|---|---|---|---|
| 0 | `open` | `FM-085` | source_inputs | Price | OHLCV |
| 1 | `high` | `FM-086` | source_inputs | Price | OHLCV |
| 2 | `low` | `FM-087` | source_inputs | Price | OHLCV |
| 3 | `close` | `FM-088` | source_inputs | Price | OHLCV |
| 4 | `volume` | `FM-089` | source_inputs | Volume | OHLCV |
| 5 | `volume_ratio` | `FM-062` | rolling_indicators | Volume | — |
| 6 | `double_sweep` | `FM-060` | structural_states | Liquidity | Liquidity, Sweep |
| 7 | `ema_fast` | `FM-043` | rolling_indicators | Trend | — |
| 8 | `ema_slow` | `FM-044` | rolling_indicators | Trend | — |
| 9 | `ema_spread` | `FM-022` | derived_metrics | Trend | — |
| 10 | `trend_bias` | `FM-054` | structural_states | Trend | CHoCH (Change of Character) |
| 11 | `trend_strength_z` | `FM-064` | rolling_indicators | Trend | — |
| 12 | `momentum_score` | `FM-023` | derived_metrics | Momentum | — |
| 13 | `atr` | `FM-041` | rolling_indicators | Volatility | — |
| 14 | `volatility_ratio` | `FM-024` | derived_metrics | Volatility | — |
| 15 | `rsi_14` | `FM-042` | rolling_indicators | Momentum | — |
| 16 | `macd_line` | `FM-047` | rolling_indicators | Momentum | — |
| 17 | `macd_signal` | `FM-048` | rolling_indicators | Momentum | — |
| 18 | `macd_hist_raw` | `FM-049` | rolling_indicators | Momentum | — |
| 19 | `macd_hist_z` | `FM-053` | rolling_indicators | Momentum | — |
| 20 | `sweep_detected` | `FM-059` | structural_states | Liquidity | Liquidity, Sweep |
| 21 | `liquidity_sweep` | `FM-058` | structural_states | Liquidity | Liquidity, Sweep |
| 22 | `break_of_structure` | `FM-057` | structural_states | MarketStructure | CHoCH (Change of Character) |
| 23 | `swing_high` | `FM-045` | rolling_indicators | MarketStructure | — |
| 24 | `swing_low` | `FM-046` | rolling_indicators | MarketStructure | — |
| 25 | `higher_high` | `FM-055` | structural_states | MarketStructure | — |
| 26 | `lower_low` | `FM-056` | structural_states | MarketStructure | — |
| 27 | `body_size` | `FM-001` | primitives | CandleGeometry | — |
| 28 | `candle_range` | `FM-002` | primitives | CandleGeometry | — |
| 29 | `body_ratio` | `FM-010` | feature_compositions | CandleGeometry | Displacement |
| 30 | `volatility_regime` | `FM-050` | rolling_indicators | Volatility | — |
| 31 | `session` | `FM-052` | temporal_context | Time | — |
| 32 | `hour_of_day` | `FM-051` | temporal_context | Time | — |
| 33 | `disp_strength` | `FM-020` | derived_metrics | Volatility | Displacement |
| 34 | `retest_depth` | `FM-021` | derived_metrics | Retest | — |
| 35 | `candles_since_sweep` | `FM-065` | rolling_indicators | Retest | — |
| 36 | `liquidity_distance` | `FM-025` | derived_metrics | Liquidity | Liquidity |
| 37 | `liquidity_pressure_score` | `FM-026` | derived_metrics | Liquidity | Liquidity |
| 38 | `volume_spike` | `FM-063` | rolling_indicators | Volume | — |
| 39 | `order_block_distance` | `FM-075` | derived_metrics | MarketStructure | Order Block |
| 40 | `fvg_distance` | `FM-076` | derived_metrics | MarketStructure | FVG (Fair Value Gap) |
| 41 | `breaker_distance` | `FM-077` | derived_metrics | MarketStructure | Breaker Block |
| 42 | `mitigation_block_distance` | `FM-078` | derived_metrics | MarketStructure | Mitigation Block |
| 43 | `pdh_distance` | `FM-079` | derived_metrics | Liquidity | PDH (Previous-Day High) |
| 44 | `pdl_distance` | `FM-080` | derived_metrics | Liquidity | PDL (Previous-Day Low) |
| 45 | `eqh_distance` | `FM-081` | derived_metrics | Liquidity | EQH (Equal Highs) |
| 46 | `eql_distance` | `FM-082` | derived_metrics | Liquidity | EQL (Equal Lows) |
| 47 | `change_of_character` | `FM-083` | structural_states | MarketStructure | CHoCH (Change of Character) |

## Declared but NOT vector-bound (no canonical slot)

These identities are real, measured, and governed — but `lineage.vector_key` is empty, so they are NOT part of the 48-dim vector. A bridge that listed only vector rows would silently drop them.

| FM-ID | Ontology name | Section | Category | Concept |
|---|---|---|---|---|
| `FM-028` | `displacement_atr_ratio` | derived_metrics | Volatility | Displacement |
| `FM-029` | `disp_strength_atr_rescale` | derived_metrics | Volatility | Displacement |
| `FM-069` | `displacement_flag` | structural_states | Volatility | Displacement |

## Coverage

- Canonical features: **48**
- Named by at least one concept: **23**
- Not named by any concept: 25

Features with no concept mapping (measured, not yet bridged to vocabulary):

- `atr` (FM-041) — rolling_indicators
- `body_size` (FM-001) — primitives
- `candle_range` (FM-002) — primitives
- `candles_since_sweep` (FM-065) — rolling_indicators
- `ema_fast` (FM-043) — rolling_indicators
- `ema_slow` (FM-044) — rolling_indicators
- `ema_spread` (FM-022) — derived_metrics
- `higher_high` (FM-055) — structural_states
- `hour_of_day` (FM-051) — temporal_context
- `lower_low` (FM-056) — structural_states
- `macd_hist_raw` (FM-049) — rolling_indicators
- `macd_hist_z` (FM-053) — rolling_indicators
- `macd_line` (FM-047) — rolling_indicators
- `macd_signal` (FM-048) — rolling_indicators
- `momentum_score` (FM-023) — derived_metrics
- `retest_depth` (FM-021) — derived_metrics
- `rsi_14` (FM-042) — rolling_indicators
- `session` (FM-052) — temporal_context
- `swing_high` (FM-045) — rolling_indicators
- `swing_low` (FM-046) — rolling_indicators
- `trend_strength_z` (FM-064) — rolling_indicators
- `volatility_ratio` (FM-024) — derived_metrics
- `volatility_regime` (FM-050) — rolling_indicators
- `volume_ratio` (FM-062) — rolling_indicators
- `volume_spike` (FM-063) — rolling_indicators

