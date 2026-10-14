# MKT-E04 `crt_displacement` — forensic specimen (documentation-only)

No src/config/authority edits. Every claim carries path:line. MKT-E04 only;
the six neighbours stay distinct throughout.

## 1. Contract

`configs/formulas/concept_contracts.yaml:448-463` — `MKT-E04 crt_displacement`,
`MARKET EVENT`, `ACCEPTED`, `version: 2 # R1-A`. Definition: "A directional
impulse away from the side of a specific prior sweep." Identity `{reference:
MKT-E01, timeframe: bar, clock: bar_close, availability_rule: bar_close}`.
Inputs `[MKT-E01, GP-06]`. Rule: "GP-06 with bias = the sweep's implied bias
and sweep_price = MKT-E01 sweep_extreme (R1-A). Magnitude gates are caller
parameters, not part of the primitive." Absence: "No prior sweep -> undefined."
Authority: `[src/structure/predicates.py, src/config_layer/crt_engine_v2.py]`,
lineage `[SP-002, F-074]`. Divergences: `[]`.

Grounding (`query_semantic_os.py --ground --kind CONCEPT --token MKT-E04`):
`GROUNDED`, `representations: []`, `consumers: []` (HEURISTIC).

Dependents citing MKT-E04: `TRS-01` birth (D2-1), `MKT-P01.DISPLACED`
(`lifecycle.entry_events: [MKT-E04]`, concept_contracts.yaml:838), `MKT-L02`
(inputs), `MKT-E11` move (sweep_extreme -> MKT-E04 close, R1-A), `MKT-E09`
downstream.

## 2. Representation: ABSENT

Mechanical scan of all six `configs/formulas/representation_registry/*.yaml`:
**zero rows with `concept_id: MKT-E04`**. Only mention is
`crt_engine.yaml:160` as a `DEX-07` field note ("open of the founding MKT-E04
candle") — a reference to the concept, not a representation of it.

## 3. GP-06 / sweep_extreme lineage

- GP-06: `src/semantics/geometry.py:57-59 directional_impulse` ->
  `src/structure/predicates.py:94-120` (SP-002/F-074). LONG: `close > open
  AND close > sweep_price`. Bias inherited, never re-derived.
- sweep_extreme: `src/semantics/market/events.py:56-72 sweep()` — `extreme =
  high/low`; "The ONE canonical displacement reference price (R1-A)".
- Thesis: `src/semantics/trading/thesis.py:48-80 form_thesis` — `sweep()`
  must fire, then `gp.directional_impulse(displacement_bar, event.extreme,
  event.implied_bias)` else `None`. Move = extreme -> displacement close.
- C3 witness: `src/semantics/integration/checks.py:201-230
  check_displacements` — `(MKT-E04, AGREE/UNEXPLAINED)` from GP-06 vs
  `sweep_event.price`, plus `(TRS-01, ...)` from `form_thesis`. Tests green
  (29 passed: integration + thesis + r1_normalisation).

## 4. Engine comparison

`src/config_layer/crt_engine_v2.py:1175-1500 try_sweep_to_displacement`.
Guards: direction present; `close > open` LONG / `close < open` SHORT;
**away: `close > sweep_event.price` LONG / `close < sweep.price` SHORT**
(`:1276-1323`, `G_SWEEP_DISP_AWAY_LONG/SHORT`); `move >=
atr_min_displacement * atr_abs`; `max_sweep_age_candles`; `body_ratio >=
body_ratio_min` (FM-010); `wick_size >= atr_multiplier_min * atr` (absolute
ATR). Success: `state.displacement_candle = candle` (`:1495`) +
`_transition(state, CRTState.DISPLACEMENT)` (`:1496-1500`).

Sweep construction `:960-1015 detect_sweep`: `SweepEvent(direction,
price=candle.high/low, candle, candle_index)`, strict GP-04. Engine imports
`swept_high/swept_low` (`:59`) but **no `directional_impulse`, no
`semantics.*`, no `form_thesis`, no `MarketEvent`** on this path — GP-06 is
re-stated inline against `sweep_event.price` and bundled with caller
magnitude gates. Downstream: `displacement_candle` feeds
`try_displacement_to_expansion` (`disp_close`), `stop_price`/`build_trade`
(`:2491-2637`; legacy `displacement` vs `sweep_extreme` K23 F3),
`Trade.displacement_origin` (`:2712-2715`, DEX-07). `Trade.direction` is set
at SWEEP (`:1124-1134`; RECORDED TRS-01 divergence, D2-1).

Event-vs-transition test: engine evaluates the GP-06 predicate inline and
transitions state, but stores **no MKT-E04 identity** (no concept_id,
parameterization_id, bar/extreme/bias record). The only MKT-E04-shaped object
is built off-spine by `form_thesis` in the C3 path.

## 5. Consumers re-check (anti-false-negative)

`consumers_by_concept()['MKT-E04']` = None; grounder `consumers: []`. Direct
grep over `src tests`: hits are `src/semantics/**`, `parent_crt.py:51,169`
(parent-track impulse, not MKT-E04), `research/sujan_crt + visual_crt`,
engine SL-anchor strings (anchor ≠ event), `bar_structure_snapshot`
(`crt_displacement_candle_index` analytics), tests. Zero hits in
`src/runtime`, `src/core`, `src/strategies`, engine semantic imports,
`src/features/` slots. `TRS-01: [crt_engine_v2.py, backtest_v2.py]` is a
homonym candidate (Trade.direction); engine never imports Thesis.
Zero-consumer is **not** a heuristic artefact.

## 6. Neighbour separation

`displacement_flag` (FM-069) = MKT-E05-family energy input (no sweep ref).
`disp_strength` (FM-020) = magnitude measurement. `CRTState.DISPLACEMENT` /
`MKT-P01.DISPLACED` = stage entered *by* the event (`entry_events:
[MKT-E04]`). `MKT-E05` = explicitly sweep-less. None is the representation.

## 7. Classification: C (COMPARATOR-ONLY) with B-shaped follow-up

Not A: TRS-01 birth, DISPLACED entry, TRS-03/MKT-E11 move all cite MKT-E04;
retiring orphans accepted slice-2/3 semantics. Not B-today: no spine reader
needs the event record; binding the engine transition as REP would
misrepresent a gated transition as the bare primitive (I-2 violation).
C: MKT-E04 lives as **verification scope** — C3 + `form_thesis` + R1-A
discipline — off the decision spine. Zero-consumer is expected **provided**
the scope is recorded.

Follow-up (only on scope change): `SEMANTIC_REGISTRY_CHANGE` to (a) record
C-scope on MKT-E04, or (b) bind a representation if a spine consumer needs
the identity (candidates: narrowed engine record or promoted `form_thesis`
output — design discussion first). No code change in this forensic.
