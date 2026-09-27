# market_language_schema — canonical Run/Trace vocabulary

> **Status:** `DRAFT_DETERMINETIC_FIRST` (v1). Deterministic findings are final; cross-lane
> semantic alignments are explicitly listed under *LLM-PENDING* and are **not** filled in here.
> Machine binding: [`market_language_schema.json`](market_language_schema.json). Source of every
> row: [`market_language_census_report.json`](market_language_census_report.json) (S1–S8).

## 1. Principle

Run/Trace identity fields are named **from the existing authority vocabulary** — never invented,
never normalised away. This artifact is the reconciliation contract that feeds the Run/Trace
engine's `trace_id` / `can_join` naming.

## 2. Four distinct state vocabularies (kept separate)

| vocabulary | kind | count | canonical terms |
|---|---|---|---|
| `crt_machine` | deterministic state machine | 12 | `RANGE RANGE_C1 EXPANSION DISTRIBUTION_C3 MANIPULATION_C2 DISPLACEMENT RETEST SWEEP RESOLUTION EXECUTION EXPIRED SHADOW_PENDING` |
| `feature_enum` | feature gate enums | 36 | `trend_bias higher_high lower_low break_of_structure liquidity_sweep sweep_detected double_sweep retest_flag rsi_state displacement_flag body_commitment atr_magnitude momentum_magnitude change_of_character` |
| `smc_choch` | signed combination (NOT a machine) | 1 | `change_of_character` (−1/0/+1) |
| `trade_execution` | journal + geometry + intent | 31 | intents `BREAKOUT PULLBACK LIQ_SWEEP REVERSAL CONTINUATION UNKNOWN` |

`smc_choch` is deliberately **not** a state machine (market_ontology.yaml:32 excludes BOS/CHOCH
detection machines); it is a pure signed op over registered features. It is listed as a fourth
vocabulary precisely so it is never conflated with the first two.

## 3. The one place the vocabularies formally meet: CRT ↔ feature-enum gating edge

Every `crt_machine` state's `activation_condition` is a conjunction of **feature_enum gates**
(each expecting an enum value, e.g. `NoSweep` / `NoBreak` / `NoHigherHigh`). The gate key set is
the canonical join surface:

`liquidity_sweep break_of_structure sweep_detected displacement_flag double_sweep higher_high
lower_low retest_flag swing_high swing_low` (10 gates)

Example (`RANGE`): `{liquidity_sweep:[NoSweep], break_of_structure:[NoBreak], …}`.

## 4. Overlaps — surfaced, never normalised

- **Exact-name collision (S6, n=1):** `DISPLACEMENT` in `state/crt_machine` ∩ `state/feature_enum`.
  Resolution: **prefix-disambiguate**, do not merge — `crt::DISPLACEMENT` (state) **vs**
  `feature_enum::displacement_flag` (enum gate).
- **Concept-token overlap `sweep` (S6):** spans **6** vocabularies
  (`feature/rolling_indicators feature/structural_states shape/shape_layer state/crt_machine
  state/feature_enum trade/intent`), 13 member words — surfaced, **not** collapsed.

## 5. Run/Trace field vocabulary (proposal)

| field | purpose | value domain | grounded in |
|---|---|---|---|
| `trace_id` | contiguous CRT-machine residence episode | `crt_machine` canonical state + gating predicate fingerprint | `crt_machine`, `feature_enum` |
| `can_join` | predicate-level joinability: do observed gates satisfy the target state? | predicate over the 10 gate keys | `feature_enum`, §3 edge |

Both are `PROPOSAL_AWAITING_ENGINE_CONSUMER` — the engine implementation is a separate change.

---

## 6. LLM-lane brief (Step 4) — for the semantic cross-check lane

These determinations are **semantic, not census-derivable**, and are deliberately left open.

1. **S7 orphans → gap vs scalar.** The census lists 47 `features_with_no_state` (e.g. `atr`,
   `volume_ratio`, `body_ratio`, `candles_since_sweep`). Decide, with a provenance citation each:
   which are genuine API gaps that need a `feature_enum` state parent, vs legitimate scalar
   measurements that correctly have no state? (Recommend a `gap` / `scalar` / `unclear` tag per
   feature.)
2. **Shape-layer alias check.** Are the shape-layer members of the concept families
   (`DoubleSweepTrap`, `BuySideSweep`, `SellSideSweep`, `BuySideLiquidityGrab`, …) aliases of one
   geometric intent, or distinct shapes? Cross-check `ic-003-shape-narratives.md`.
3. **Sweep un-collapse confirmation.** Confirm the 6-way `sweep` overlap stays un-collapsed
   (same market concept, distinct computational vocabularies) so the S6 statement stands.

**Expected return:** a JSON of alignments keyed by the fields above; merge result updates §5/§6 of
this schema and flips `status` to `RECONCILED`.