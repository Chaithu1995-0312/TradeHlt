# Plan — Single-paragraph semantic market description from the current feature/state inventory

## Context

The request is a **semantic-description exercise**, not a code change: produce one coherent
natural-language paragraph that describes a single market episode using only the feature and state
vocabulary the repository already establishes, walking observable candle values → feature states →
structural states → CRT/HTF context → decision state → execution intent. Nothing is to be built,
measured, promoted, or claimed. The value is in demonstrating that the repository's separate
vocabularies (canonical vector slots, FM identities, feature states, CRT states, HTF posture,
objective status, direction, reject reasons, trade intent, intent/termination) can narrate one
episode without collapsing into each other — which is exactly the `different registers stay
distinct` discipline of CLAUDE.md §6.6 / §6.8.

Deliverable = the paragraph, emitted in the response. No repository file changes.

## Vocabulary sources consulted (read-only, verified this session)

- `src/features/feature_schema.py` — `CANONICAL_FEATURES`, schema v5.0, `CANONICAL_FEATURE_DIM = 48`
  (v5.0 added the 9 SMC slots at indices 39–47).
- `configs/formulas/market_ontology.yaml` — FM identities and their declared `states:` blocks
  (FM-054…FM-061 structural states, FM-050 `volatility_regime`, FM-068 `rsi_state`,
  FM-069 `displacement_flag`, FM-063 `volume_spike`, FM-051/052 temporal, FM-020/021/027/028,
  FM-041 `atr` vs FM-074 `atr_absolute`, FM-064/065).
- `configs/formulas/market_crt_states.yaml` — the `feature_states:` roster and the CRT-state
  predicates/`valid_transitions`.
- `src/config_layer/state_identity.py` — `CRTState` (12 members: 9 execution-timeframe +
  3 disjoint parent-timeframe), `Direction`, `RejectReason`, `VALID_TRANSITIONS`.
- `src/config_layer/htf_state.py` — `HTFState`, `ObjectiveStatus`, `Objective`.
- `src/config_layer/crt_engine_v2.py:2301` — `_derive_trade_intent` → `liq_sweep` / `pullback` /
  `breakout` / `reversal`.
- `src/execution/execution_intent_v1_0.py` — `IntentState`, `TerminationReason`.
- Active config: `configs/production/ACTIVE_VERSION` = `v2_htfcrt_2026_08` (parent-CRT armed, F-075).

## Semantic consistency constraints honored in the draft

- The SWEEP predicate requires `displacement_flag: NoDisplacement`, so the sweep bar and the
  body-dominated displacement bar are described as **successive** bars, not one bar holding both.
- `SellSideSweep` pairs with `LowerLow` and a LONG consequence per FM-058's own declared semantics.
- Only legal edges are named: `RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION →
  RESOLUTION`, with `SHADOW_PENDING` and `EXPIRED` mentioned as the legal branches they are.
- Parent-timeframe `RANGE_C1 → MANIPULATION_C2 → DISTRIBUTION_C3` is kept as a **separate track**,
  never interleaved with the 9 execution states (state_identity.py disjoint sub-graph).
- `HTFState.DISTRIBUTION` is kept distinct from `CRTState.DISTRIBUTION_C3` (F-077).
- `rsi_state: NeutralMomentum` + `session: LONDON` + directional `trend_bias` are chosen so the
  EXECUTION predicate is coherent rather than contradicted.
- No formulas, no transitions, no meanings invented; no decision-relevance inferred from vector
  membership; no authority or profitability claimed.

## The paragraph (deliverable)

> On this M15 bar the candle reports its `open`, `high`, `low`, `close` and `volume`, and the shape
> those four prices make is what everything downstream reads first: `body_size` against
> `candle_range` (FM-002) gives `body_ratio` (FM-010), while `atr` (FM-041, close-relative) and its
> absolute form `atr_absolute` (FM-074) say how large that range is for this instrument, so
> `volatility_ratio` and the tercile bucket `volatility_regime` (FM-050) can call the bar
> `HighVolatility` rather than `NormalVolatility` or `LowVolatility`; `ema_fast` sits above
> `ema_slow`, so `ema_spread` and `trend_strength` (FM-064) carry a `Bullish` `trend_bias` (FM-054)
> instead of `Neutral` or `Bearish`, `rsi_14` (FM-042) stays inside its configured band so
> `rsi_state` (FM-068) reads `NeutralMomentum` and not `Overbought` or `Oversold`, and
> `momentum_score` with the split `macd_line`, `macd_signal`, `macd_hist_raw` and `macd_hist_z`
> describes the same push in its own units, while `volume_ratio` lifts `volume_spike` (FM-063) from
> `NoSpike` to `VolumeSpike`; structurally this bar traded through the prior swing reference and
> closed back inside it, so `liquidity_sweep` (FM-058) resolves to `SellSideSweep` with
> `sweep_detected` (FM-059) at `SweepDetected` and `double_sweep` (FM-060) still `NoDoubleSweep`,
> `break_of_structure` (FM-057) holds at `NoBreak` even as `lower_low` reads `LowerLow` against the
> carried `swing_low` (FM-067) while `higher_high` stays `NoHigherHigh`, `swing_high` remains
> `NoSwingHigh`, and `displacement_flag` (FM-069) is still `NoDisplacement` on this bar — the
> liquidity picture around it being given by `liquidity_distance`, `liquidity_pressure_score`,
> `pdl_distance`, `pdh_distance`, `eql_distance`, `eqh_distance`, `order_block_distance`,
> `fvg_distance`, `breaker_distance` and `mitigation_block_distance`, with `change_of_character`
> summarising `break_of_structure` against `trend_bias`; on the next bar the body dominates its
> range and `displacement_flag` turns `Displacement`, `disp_strength` (FM-020) and
> `displacement_atr_ratio` (FM-028) sizing that impulse away from the side just swept, after which
> price returns toward the fast-EMA reference so `retest_flag` (FM-061) becomes `RetestActive`,
> `retest_depth` (FM-021) and `displacement_retrace` (FM-027) become meaningful rather than zero,
> and `candles_since_retest` (FM-065) begins counting; read as the execution-timeframe state
> machine, that same sequence carries the engine out of `RANGE` into `SWEEP`, on into
> `DISPLACEMENT` and then `EXPANSION` — where a window flip could instead have left it in
> `SHADOW_PENDING`, or a TTL could have moved it through `EXPIRED` back to `RANGE` — and here it
> advances to `RETEST`; on the parent timeframe a separate three-candle track reads
> `RANGE_C1`, then `MANIPULATION_C2`, then `DISTRIBUTION_C3`, and that parent carries its own
> posture `HTFState.EXPANSION` (as opposed to `ACCUMULATION`, `DISTRIBUTION`, `REVERSAL` or
> `UNKNOWN`) together with an `ObjectiveStatus` of `EXISTS` rather than `NONE`, `ACHIEVED` or
> `INVALIDATED`, oriented `Direction.LONG`; at the decision surface the bar's `session` (FM-052) is
> `LONDON` at its `hour_of_day` (FM-051), so the signal is not turned away as `OUTSIDE_SESSION`,
> nor as `LOW_SCORE`, `NO_DOUBLE_SWEEP`, `NEWS_FILTER`, `HIGH_SPREAD` or `INVALID_STATE`, leaving
> `RETEST → EXECUTION` and then `RESOLUTION` as the remaining legal path; the setup that results is
> classified as the `liq_sweep` intent rather than `pullback`, `breakout` or `reversal` because the
> sweep flags are the ones that are set, and the execution intent for it opens as `PROPOSED` and
> ends either `EXECUTED` or `TERMINATED` under `REJECTED`, `EXPIRED`, `REPLACED` or `CANCELLED`.

## Execution steps

1. Emit the paragraph above as the response body — single paragraph, no list, no table, no
   repository explanation.
2. Append the `📝 SESSION LOG ENTRY` block to `assistant_project.md` per CLAUDE.md §6/§7.4
   (this is the only file write; it is the standing logging mandate, not a change to the system
   being described).

## Verification

- Every name used traces to one of the read-only sources listed above; nothing is introduced that
  those files do not declare.
- Registers stay separate: `HTFState.DISTRIBUTION` ≠ `CRTState.DISTRIBUTION_C3`; the parent
  three-candle track is never spliced into the 9-state execution graph; `Direction`, `RejectReason`,
  trade intent (`liq_sweep`…), and `IntentState`/`TerminationReason` are used only in their own
  layers.
- No transition is named that is absent from `VALID_TRANSITIONS`, and no state combination is
  asserted that `market_crt_states.yaml` predicates contradict.
- No economic, authority, or profitability claim appears (CLAUDE.md §6.5 Authority Ladder); the
  paragraph is descriptive only and grants nothing.
