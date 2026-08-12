# Market Reality — Repository-Wide Missing-Observable Search (WP3)

**Date:** 2026-07-12
**Scope:** Repository-local search for semantic equivalents of candidate market observables.
No production behavior changed. Returns evidence for ChatGPT's SET A/B/C classification — no A/B/C closure here.

---

## 1. Search methodology

Search was by **semantic behavior, not exact name**. For each candidate I (a) grepped `src/` (plus
`configs/`, `docs/` where relevant) for the concept and its synonyms, (b) inspected the producing code
and its call sites to distinguish *implemented and reachable* from *research-only* / *dead*, and (c)
where nothing adequate exists, asked whether the observable is **derivable from the history of the 38
canonical features** — noting that the 38-vector **includes raw `open/high/low/close/volume`**, so pure
OHLC-pattern observables are derivable, whereas observables needing a retained **non-canonical price
level** (e.g. `last_swing_high_price`) or **cross-engine state** are **not**.

**Classification tokens:** `FOUND_CANONICAL` (in the 38-vector) · `FOUND_NONCANONICAL` (computed in the
pipeline/engine but not in the vector) · `FOUND_RESEARCH_ONLY` (`src/research` or `src/interpreters`,
isolated from the spine) · `FOUND_STALE_OR_DEAD` (0 call sites / legacy) · `DERIVABLE_FROM_38_HISTORY` ·
`GENUINELY_ABSENT`.

**Correction #8 — three distinct derivability outcomes are kept separate:**
- **(a) directly present** → one of the FOUND_* tokens;
- **(b) causally derivable from history of the 38 canonical features** (incl. raw OHLC) → `DERIVABLE_FROM_38_HISTORY`;
- **(c) derivable only if hidden/non-canonical state or extra retained structure is kept** (e.g. a swing
  *price level*, or engine evidence outputs) → **NOT** labeled `DERIVABLE_FROM_38_HISTORY`; called out as
  `REQUIRES_NONCANONICAL_STATE` (a sub-note on the row).

## 2. Exact search commands

```
# concept clusters (ripgrep via Grep tool, case-insensitive, over src/)
price_position|upper_wick|lower_wick|rejection_wick|efficiency|kaufman|\ber\b|chop|overlap
atr_slope|acceleration|compression|expansion|contract|run_length|streak|persistence|premium|discount
fvg|fair_value|imbalance|\bgap\b|htf|multi_timeframe|mtf|divergence|uncertainty|conflict|market_quality|noise|acceptance|false_breakout|bars_since
fair_value_gap|\bfvg\b|price_position|premium|discount|efficiency_ratio|kaufman|\bchop\b|bars_since_swing|structure_age|breakout_persist|retest_hold|retest_outcome|price_volume|pv_diverg
# negative-confirmation (count mode -> 0 total):
fair_value_gap|\bfvg\b|efficiency_ratio|kaufman|retest_hold|retest_outcome|breakout_persistence|false_breakout|momentum_divergence|volume_slope|run_length|rotational   -> 0 occurrences
# targeted reads
src/research/candle_state/encoder.py (CandleState), src/research/candle_state/mtf_conjunction.py (MultiTFConjunctionBuilder)
```

## 3. Candidate observable table

| Candidate observable | Classification | Evidence (file · symbol) |
|---|---|---|
| close location value / close position in bar | **FOUND_NONCANONICAL** + DERIVABLE_FROM_38_HISTORY | `feature_pipeline.py:522` `price_position = (close-low)/wick_size` — computed, **not** in the 38-vector. Also research `encoder.py` `body_pct`. Trivially derivable per-bar from o/h/l/c (in 38). |
| upper wick ratio | FOUND_RESEARCH_ONLY + DERIVABLE_FROM_38_HISTORY | `research/candle_state/encoder.py:57` `upper_wick_pct=(high-max(o,c))/(high-low)`. Raw magnitude `upper_wick` at `feature_pipeline.py:187` (noncanonical). Derivable per-bar from OHLC in 38. |
| lower wick ratio | FOUND_RESEARCH_ONLY + DERIVABLE_FROM_38_HISTORY | `encoder.py:58` `lower_wick_pct`; raw `lower_wick` `feature_pipeline.py:188`. |
| directional rejection | DERIVABLE_FROM_38_HISTORY | No named feature. = asymmetry of upper vs lower wick, derivable per-bar from OHLC in 38. Research proxy: `encoder.py` wick_pct fields. |
| price-path efficiency / Kaufman ER / trend efficiency | **GENUINELY_ABSENT** (as implemented) → DERIVABLE_FROM_38_HISTORY | Negative search: `kaufman`, `efficiency_ratio` → **0 occurrences**. Derivable from `close` history (in 38): net move / summed abs moves over N. No producer. |
| bar overlap / range overlap / rotational congestion / chop | **GENUINELY_ABSENT** → DERIVABLE_FROM_38_HISTORY | `chop`, `rotational` → 0 occurrences. Overlap derivable from consecutive high/low history (in 38). Related but distinct: `displacement_flag` (`feature_pipeline.py:588`, noncanonical) and research inside/outside tokens. |
| ATR slope / volatility slope / acceleration / shock | FOUND_RESEARCH_ONLY + DERIVABLE_FROM_38_HISTORY | `atr_slope` → 0 direct; research `encoder.py:60` `atr_ratio=TR/trailing ATR`; `research/candle_state` COMPRESSION/EXPANSION. Derivable from `atr` history (in 38). **This is the WP1 §10 gap.** |
| range compression | FOUND_RESEARCH_ONLY + DERIVABLE_FROM_38_HISTORY | `research/hypotheses/compression_breakout.py`, `compression_box_straddle.py`; `encoder.py` VOL_COMPRESSION. Derivable from `atr`/range history in 38. |
| directional persistence / run length / sign persistence | **GENUINELY_ABSENT** → DERIVABLE_FROM_38_HISTORY | `run_length`, `streak` → 0. Sign of `(close-open)` derivable per-bar from OHLC in 38; run length = count over history. No producer. |
| structure age / bars since swing | FOUND_NONCANONICAL + DERIVABLE_FROM_38_HISTORY | `crt_engine_v2.py:2912` engine-internal `structure_age`/`_struct_age` (dict, not a feature). Bars-since-swing derivable from `swing_high`/`swing_low` event history (both in 38). |
| bars since BOS | DERIVABLE_FROM_38_HISTORY | Derivable from `break_of_structure` event history (in 38). No dedicated feature. |
| BOS direction / breakout direction | **FOUND_CANONICAL** | `break_of_structure ∈ {−1,0,+1}` (`feature_pipeline.py:468`, vector index 22). Signed. |
| breakout persistence / acceptance beyond level / time beyond boundary | **REQUIRES_NONCANONICAL_STATE** (not derivable from 38 alone) | `acceptance`/`breakout_persist` → no feature. Needs the **swept/broken price level** (`last_swing_*_price`, `bos_level`) which are **not** in the 38 → category (c). |
| breakout failure / false breakout | REQUIRES_NONCANONICAL_STATE / partial FOUND_CANONICAL | `false_breakout` → 0. `liquidity_sweep` (`:473`, in 38) encodes the *poke-and-reject* pattern = a false-breakout proxy at the moment; but "failure **after** acceptance" needs the level + forward tracking → category (c). |
| retest hold / retest failure / retest outcome | **REQUIRES_NONCANONICAL_STATE** | `retest_hold`,`retest_outcome` → 0. `retest_flag`/`retest_depth` (in 38) mark EMA9 proximity after a sweep, **not** the hold/fail outcome; outcome needs forward price-vs-level tracking → category (c). |
| momentum slope / acceleration | DERIVABLE_FROM_38_HISTORY | Derivable from `momentum_score`/`macd_hist` history (in 38). Related canonical: `macd_hist`. |
| momentum divergence | **GENUINELY_ABSENT** → DERIVABLE_FROM_38_HISTORY | `momentum_divergence` → 0. Derivable from `close` vs `rsi_14`/`macd_line` history (all in 38). No producer. |
| volume slope / volume trend | **GENUINELY_ABSENT** → DERIVABLE_FROM_38_HISTORY | `volume_slope` → 0. Research `encoder.py:59` `volume_z`. Derivable from `volume` history (in 38). |
| price-volume divergence | DERIVABLE_FROM_38_HISTORY | Derivable from `close` + `volume` history (both in 38). No producer. |
| impulse / displacement persistence | FOUND_NONCANONICAL + DERIVABLE_FROM_38_HISTORY | `displacement_flag` (`feature_pipeline.py:588`, noncanonical), `disp_strength` (in 38). Persistence derivable from `disp_strength`/`body_ratio` history. |
| range location / premium / discount / distance to boundary | FOUND_NONCANONICAL + DERIVABLE_FROM_38_HISTORY | `bb_position` (`:283`), `range_size` (`:538`) — noncanonical. `crt_engine_v2.py:2802-2809` "discount/premium zone" (engine-internal filter, not a feature). Derivable from rolling high/low of OHLC history (in 38). |
| fair value gap / FVG / imbalance / gap lifecycle | **GENUINELY_ABSENT** → DERIVABLE_FROM_38_HISTORY | `fvg`,`fair_value_gap` → **0 occurrences**. FVG is a pure 3-bar OHLC pattern → derivable from OHLC history (in 38). **No producer anywhere.** |
| HTF trend / HTF structure / multi-timeframe alignment | **FOUND_RESEARCH_ONLY** | `research/candle_state/mtf_conjunction.py` `MultiTFConjunctionBuilder` ({M15,H1,H4} via `resample.py`). Isolated from the spine (F-040 program). No canonical HTF feature. |
| evidence conflict / state conflict / market quality / market noise / uncertainty score | **GENUINELY_ABSENT** (feature layer) | `uncertainty`,`market_quality` → no feature-layer producer (hits are engine/LLM narrative text). A cross-evidence disagreement measure needs **engine/fusion outputs**, not the 38 → not derivable from the feature history alone → category (c)/absent for a feature surface. |

## 4. Existing canonical matches (in the 38-vector)

- `break_of_structure` (signed BOS direction) · `liquidity_sweep` (signed) · `swing_high`/`swing_low` ·
  `higher_high`/`lower_low` · `double_sweep` · `sweep_detected` (unsigned) · `retest_depth`/
  `candles_since_retest` · `volatility_regime` (ATR-level tercile) · `atr`/`volatility_ratio` ·
  `momentum_score`/`macd_line`/`macd_signal`/`macd_hist`/`rsi_14` · `disp_strength` ·
  `liquidity_distance`/`liquidity_pressure_score` · `body_ratio`/`wick_size`/`body_size` ·
  `session`/`hour_of_day` · raw `open/high/low/close/volume`/`volume_ratio`/`volume_spike`.

## 5. Existing noncanonical matches (computed, not in the vector)

- `price_position` (close-in-bar location) · `upper_wick`/`lower_wick` (raw magnitudes) · `range_size`
  (20-bar range/close) · `bb_position` (Bollinger location) · `displacement_flag` ·
  `volume_range_proxy`/`volume_range_proxy_ratio` · `volatility_regime_expanding_causal` /
  `volatility_regime_global_batch` (sibling vol-rank identities) · `ma_slope_20`/`trend_strength` (slope
  intermediates) · engine-internal `structure_age`/`_struct_age`, `premium`/`discount` zone flags
  (`crt_engine_v2.py`). These exist in code but are **not** part of the 38-feature observation surface.

## 6. Research-only matches (isolated from the spine)

- `research/candle_state/encoder.py` `CandleState`: `body_pct`, `upper_wick_pct`, `lower_wick_pct`,
  `volume_z`, `atr_ratio`; token axes direction {BULL/BEAR/DOJI}, vol {COMPRESSION/NORMAL/EXPANSION},
  structure {INSIDE/OUTSIDE/NORMAL}, trend {UP/DOWN/FLAT}.
- `research/candle_state/mtf_conjunction.py` `MultiTFConjunctionBuilder` (M15∧H1∧H4).
- `research/hypotheses/compression_breakout.py`, `expansion_breakout.py`, `compression_box_straddle.py`,
  `weekly_sweep_reversal.py`.
- `interpreters/point_and_figure.py` (P&F double-top/bottom), `interpreters/regime_observer.py`
  (`MarkovRegimeForecaster`), `research/regime_conditioning.py`.
- These carry **research authority only** (§6.5); none feeds the 38-vector or the decision spine.

## 7. Stale / dead matches

- `src/features/crt_feature_builder.py` — **0 call sites** (its own docstring flags it dead; stale at 35
  keys). It passes structure quantities into a legacy CRT vector; not a live producer.
- `feature_schema.py:17-42` `FEATURE_SCHEMA` (24-key legacy dict: `rejection_wick`, `volatility_flag`,
  `is_inside_bar`, `pattern_score`, `spread_pct`, `sl_distance`, `tp_ratio`) — **separate** from
  `CANONICAL_FEATURES`; several keys (`rejection_wick`, `is_inside_bar`, `pattern_score`) have no
  canonical vector counterpart. Legacy/observational.

## 8. Observables derivable from 38-feature history (correction #8, category b only)

The 38-vector includes raw OHLCV, so these need **only** the retained 38-feature history (+ raw OHLC that
is already part of the 38) — no extra hidden state:

| Observable | Required source features (⊂ 38) | Min causal history | Derivation sketch | Extra raw OHLCV? |
|---|---|---|---|---|
| close location value | `open,high,low,close` | 1 bar | `(close-low)/(high-low)` | in 38 |
| upper/lower wick ratio | `open,high,low,close` | 1 bar | `(high-max(o,c))/(high-low)`, symmetric | in 38 |
| Kaufman efficiency ratio | `close` | N bars | `|c_t-c_{t-N}| / Σ|Δc|` | no |
| bar/range overlap, chop | `high,low` | 2..N bars | overlap of `[low,high]` intervals | no |
| ATR slope / acceleration / shock | `atr` | N bars | `atr_t - atr_{t-N}`, 2nd diff, z-score | no |
| range compression | `atr` or `high,low` | N bars | trailing range trend | no |
| directional run length | `open,close` | N bars | count consecutive `sign(close-open)` | no |
| bars since swing | `swing_high,swing_low` | since last event | `cumcount` on event history | no |
| bars since BOS | `break_of_structure` | since last event | `cumcount` on `≠0` history | no |
| momentum slope / acceleration | `momentum_score,macd_hist` | N bars | diff of momentum history | no |
| momentum / PV divergence | `close,rsi_14,macd_line,volume` | N bars | sign-disagreement of trends | no |
| volume slope / trend | `volume` | N bars | trailing volume regression | no |
| range location / premium-discount | `high,low,close` | N bars | `(close - rolling_low)/(rolling_high - rolling_low)` | no |
| fair value gap (FVG) | `high,low` | 3 bars | `low_t > high_{t-2}` (bull) / `high_t < low_{t-2}` (bear) | no |

## 9. Genuinely absent observables

**Absent as any implemented producer** (0 occurrences) AND **not** cleanly derivable from the 38-feature
history alone:

- **evidence conflict / state conflict / market quality / market noise / uncertainty score** — a
  cross-evidence/cross-engine disagreement measure. Requires **engine/fusion outputs** (CRT/Gaussian/
  ZoneGate/RR scores), which are downstream of the feature surface — **not** in the 38 and not derivable
  from feature history. Category (c) at the engine layer; **absent** for a feature-layer observable.

**Absent as an implemented producer but DERIVABLE (category b)** — listed in §8, not here: Kaufman ER,
chop/overlap, run length, momentum/PV divergence, volume slope, FVG. These are *missing implementations*,
not *missing observability*.

## 10. Category (c) — require non-canonical state or extra retained structure (NOT `DERIVABLE_FROM_38_HISTORY`)

- **breakout persistence / acceptance beyond level / time beyond boundary** — needs the broken **price
  level** (`last_swing_*_price`/`bos_level`, noncanonical) retained across bars.
- **breakout failure after acceptance** — same level + forward tracking.
- **retest hold / failure / outcome** — needs the swept level + forward price-vs-level tracking.
- **structure age as decayed distance-from-level** — bars-since is derivable (b), but distance-from-level
  needs the level (c).

These are the observables where the Market Reality `MarketRealityHistoryBuffer` would need to retain more
than the 38 features (either the noncanonical swing/BOS *price levels* or a purpose-built event ledger).

## 11. Identity collision risks

- **`retest_depth` collision:** pipeline FM-021 `retest_depth` = EMA9 distance (`feature_pipeline.py:643`)
  **vs** `crt_engine_v2` `displacement_retrace` (FM-027) historically emitted under the same name
  (`derived_math.py:107-121`). Downstream code reading "retest_depth" may read different quantities per
  engine path. A Market Reality `pullback_retest` dimension must bind to a *specific* identity/ID.
- **`disp_strength` collision:** canonical FM-020 `body/(atr*close)` **vs** `displacement_atr_ratio`
  FM-028 (`candle_range/atr`) **vs** `disp_strength_atr_rescale` FM-029 (`scoring_engine.py`). Only FM-020
  is in the vector.
- **`volatility_regime` siblings:** production `_rolling_causal` vs `_global_batch` (leaky) vs
  `_expanding_causal`. Only `_rolling_causal` is canonical; the others are non-PIT/long-memory variants.
- **`wick_size` misnomer:** name says "wick" but value is full range (`high-low`). A `direction`/
  `exhaustion` dimension referencing "wick" must use the raw `upper_wick`/`lower_wick` (noncanonical), not
  `wick_size`.
- **`session` semantics:** naive-hour cutoffs {8,16} with **no timezone contract** (WP1 §15). A
  `temporal_session` dimension inherits this ambiguity until a tz contract exists.
- **`volume`/`volume_range_proxy`:** on dead-volume (FX) instruments `volume_ratio≡1.0`; a `participation`
  dimension must decide whether to consume source volume or the range proxy.

## 12. Questions requiring ChatGPT SET A/B/C classification

1. **ema_spread / momentum_score dimensional defect** (WP1 §6): SET B (repair to divide by absolute ATR)
   vs SET A (accept per-instrument scaling as intended)? Repairing changes model input distributions.
2. **RSI/ATR "Wilder" docstring vs SMA implementation** (WP1 §7-8): SET B (align semantics/comment) — but
   which is canonical, Wilder or SMA? Repository has trained models on the SMA version.
3. **`sweep_detected` direction loss:** SET C (a signed liquidity-rejection observable) or SET A
   (`liquidity_sweep` already carries the sign)?
4. **volatility_dynamics** (WP1 §10 / §8 here): SET C new observable (ATR slope/compression) or
   DERIVABLE-and-therefore-SET-A? It is derivable from `atr` history but has **no producer**.
5. **breakout/retest outcome family** (§10): SET C, but requires retaining a non-canonical level — is that
   in-scope for MarketRealityHistoryBuffer, or does it force a new canonical `*_level` feature?
6. **FVG / imbalance:** SET C observable, DERIVABLE from OHLC — build as a Market Reality derivation or a
   new canonical feature?
7. **evidence conflict / quality / uncertainty** (§9): feature-layer SET C is impossible (needs engine
   outputs) — is this a Market Reality dimension fed by *engine evidence*, outside the 38-source contract?
8. **`retest_depth` / `disp_strength` identity collisions** (§11): which ID does each Market Reality
   dimension bind to?

## 13. No-production-behavior-change proof

- Search-only work package. No file under `src/`, `configs/production/`, `tests/`, or any engine module
  was modified. No feature was added. Greps and reads are read-only.
- Deliverables: this report + `market-reality-fresh-probes-2026-07-12.md` +
  `configs/market_reality/market_reality_v1.yaml` + the mandated SESSION LOG append to
  `assistant_project.md`. `git diff -- src configs/production tests` from this task = **empty**.
