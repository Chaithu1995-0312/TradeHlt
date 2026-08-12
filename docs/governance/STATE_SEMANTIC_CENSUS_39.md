# STATE Semantic Census — 39 Canonical Features

**Status:** COMPLETE (census) · **Implementation:** none (C = 0)  
**Date:** 2026-08-12  
**Authority:** research/docs only · `PRODUCTION_BEHAVIOR_CHANGED=NO`  
**Layer owner:** `src/features/feature_states.py` (+ `magnitude_states.py` for FM-071/072/073)  
**Schema authority:** `src/features/feature_schema.py` · `CANONICAL_FEATURES` (39, schema v4.0)  
**Ontology authority:** `configs/formulas/market_ontology.yaml`  
**Does not reopen:** L4 CONTEXT · L7 TESTIMONY · AGR-v0 AGREEMENT fold · O6/O7/O18 magnitude bands  

---

## 0. First principle (locked)

> **No discrete state ≠ no semantics.**  
> The goal is not 39/39 states. The goal is an explicitly justified semantic status for every canonical slot.

Classification vocabulary (exactly one primary class per feature):

| Code | Name | Meaning |
|---|---|---|
| **A** | `STATE_COVERED` | Authoritative semantic state already exists (vector-bound or certified magnitude/twin) |
| **B** | `VALUE_SEMANTIC` | Primitive/value meaning is sufficient; no Layer-2 band required |
| **C** | `STATE_REQUIRED_EXISTING_VALUE` | Authoritative value exists; defensible state interpretation still missing |
| **D** | `NEW_MEASUREMENT_REQUIRED` | Cannot form a state without new measurement/math or schema promotion |
| **E** | `IMPLEMENTATION_INTERMEDIATE` | Computational surface; must not be promoted to a market semantic state |
| **F** | `INTENTIONALLY_UNBANDED` | Architecture / ontology leaves it continuous for a stated reason |
| **G** | `UNKNOWN` | Sources do not establish enough information |

---

## 1. Encoder inventory (source-verified)

```text
FeatureStateEncoder.stateful_features     = 18 identities
  vector-bound (12):  double_sweep, trend_bias, sweep_detected, liquidity_sweep,
                      break_of_structure, swing_high, swing_low, higher_high,
                      lower_low, volatility_regime, session, volume_spike
  non-vector (6):     body_commitment, atr_magnitude, momentum_magnitude,
                      rsi_state, displacement_flag, retest_flag

FeatureStateEncoder.continuous_features  = 27 / 39   ← census remainder, NOT an implementation backlog
CANONICAL_FEATURE_DIM                    = 39
```

Phase-2A magnitude twins (shadow; not vector slots):

| Twin | FM | Source value | Transform | States |
|---|---|---|---|---|
| `body_commitment` | FM-071 | `body_ratio` | identity bins | Low/Medium/High Commitment |
| `atr_magnitude` | FM-072 | `atr` | series percentile | Low/Medium/High ATR Magnitude |
| `momentum_magnitude` | FM-073 | `\|momentum_score\|` | abs series percentile | Low/Medium/High Momentum Magnitude |

---

## 2. Full census table (39/39)

| Idx | Feature | Ontology / FM | Existing State | Class | Reason (authority) | New State? | New Meas.? | Ctx | Shape | CRT |
|---:|---|---|---|---|---|---|---|---|---|---|
| 0 | `open` | base_input leaf | — | **B** | Raw OHLCV primitive; no ontology discrete identity | No | No | — | — | — |
| 1 | `high` | base_input leaf | — | **B** | Raw OHLCV primitive | No | No | — | — | — |
| 2 | `low` | base_input leaf | — | **B** | Raw OHLCV primitive | No | No | — | — | — |
| 3 | `close` | base_input leaf | — | **B** | Raw OHLCV primitive | No | No | — | — | — |
| 4 | `volume` | base_input leaf | — | **B** | Raw participation level; not cross-bar comparable alone | No | No | — | — | — |
| 5 | `volume_ratio` | FM-062 | — (states:[]) | **F** | Self-normalized continuous participation; discrete state is `volume_spike` | No | No | Vol opt | — | — |
| 6 | `double_sweep` | FM-060 | NoDoubleSweep / DoubleSweep | **A** | Vector-bound structural state | No | No | Liq | yes | yes |
| 7 | `ema_fast` | FM-043 | — | **E** | Trend *reference* for spread/bias; not a market condition vocabulary | No | No | — | — | soft-conf |
| 8 | `ema_slow` | FM-044 | — | **E** | Longer trend reference; intermediate for `ema_spread`/`trend_bias` | No | No | — | — | — |
| 9 | `ema_spread` | FM-022 | — (states:[]) | **F** | Explicitly BLOCKED for fixed bands (F-061 dimensional mix); sign covered by `trend_bias`; FM-030 inactive | No | No* | — | — | regime |
| 10 | `trend_bias` | FM-054 | Bearish / Neutral / Bullish | **A** | Declared structural state = sign(ema_fast−ema_slow) | No | No | Trend | yes | yes |
| 11 | `trend_strength` | FM-064 | — (states:[]) | **F** | Already z-scored continuous slope statistic; no declared categorical identity | No | No | — | — | — |
| 12 | `momentum_score` | FM-023 | via **momentum_magnitude** FM-073 | **A** | Phase-2A O18 certified 10/10; abs series percentile (F-061-safe) | No | No | Mom mag | — | — |
| 13 | `atr` | FM-041 | via **atr_magnitude** FM-072 | **A** | Phase-2A O7 certified 10/10; series percentile of relative ATR | No | No | Vol mag | — | geom |
| 14 | `volatility_ratio` | FM-024 | — (states:[]) | **F** | Continuous bar-range / ATR; regime covered by FM-050 | No | No | — | — | — |
| 15 | `rsi_14` | FM-042 | via **rsi_state** FM-068 | **A** | Pipeline+ontology ternary Oversold/Neutral/Overbought; non-vector twin | No | No | Mom opt | — | — |
| 16 | `macd_line` | FM-047 | — | **E** | Intermediate for MACD hist; not a discrete market state | No | No | — | — | — |
| 17 | `macd_signal` | FM-048 | — | **E** | Intermediate for MACD hist | No | No | — | — | — |
| 18 | `macd_hist_raw` | FM-049 | — (states:[]) | **F** | Declared raw difference identity; continuous by design | No | No | — | — | — |
| 19 | `macd_hist_z` | FM-053 | — (states:[]) | **F** | Already z-scored continuous; no declared bands | No | No | — | — | — |
| 20 | `sweep_detected` | FM-059 | NoSweep / SweepDetected | **A** | Vector-bound liquidity state | No | No | Liq | yes | yes |
| 21 | `liquidity_sweep` | FM-058 | SellSide / No / BuySide | **A** | Vector-bound directional sweep | No | No | Liq | yes | yes |
| 22 | `break_of_structure` | FM-057 | BearishBreak / No / Bullish | **A** | Vector-bound structure state | No | No | Struct | yes | yes |
| 23 | `swing_high` | FM-045 | NoSwingHigh / Confirmed | **A** | Vector-bound structure state | No | No | Struct | yes | yes |
| 24 | `swing_low` | FM-046 | NoSwingLow / Confirmed | **A** | Vector-bound structure state | No | No | Struct | yes | yes |
| 25 | `higher_high` | FM-055 | NoHigherHigh / HigherHigh | **A** | Vector-bound structure state | No | No | Struct | yes | yes |
| 26 | `lower_low` | FM-056 | NoLowerLow / LowerLow | **A** | Vector-bound structure state | No | No | Struct | yes | yes |
| 27 | `body_size` | FM-001 | — (states:[]) | **B** | Geometry primitive; ratio/state live on body_ratio / body_commitment | No | No | — | — | — |
| 28 | `candle_range` | FM-002 | — (states:[]) | **B** | Geometry primitive (high−low); **not** wick magnitude (misnomer retired) | No | No | — | — | — |
| 29 | `body_ratio` | FM-010 | via **body_commitment** FM-071 | **A** | Phase-2A O6 certified 10/10; identity bins, CRT-coherent high edge | No | No | Geom mag | — | gate |
| 30 | `volatility_regime` | FM-050 | Low / Normal / High Vol | **A** | Vector-bound regime state (absolute atr_14 terciles) | No | No | Vol | yes | — |
| 31 | `session` | FM-052 | ASIA/LONDON/NEWYORK/OVERLAP/CLOSED | **A** | Nominal session state; Time dimension owner | No | No | Time | — | filter |
| 32 | `hour_of_day` | FM-051 | — (states:[]) | **F** | Cyclic continuous clock; semantic session band is FM-052 | No | No | — | — | — |
| 33 | `disp_strength` | FM-020 | — continuous; sibling **displacement_flag** FM-069 | **F** | Continuous ATR-norm body strength; boolean twin is separate identity; CRT owns lifecycle | No | No | opt | — | CRT |
| 34 | `retest_depth` | FM-021 | — continuous; sibling **retest_flag** FM-061 | **F** | Continuous depth gated by flag; discrete retest presence is FM-061 | No | No | opt | — | CRT |
| 35 | `candles_since_retest` | FM-065 | — (states:[]) | **F** | Bar-count clock since sweep; no categorical identity declared | No | No | — | — | — |
| 36 | `liquidity_distance` | FM-025 | — (states:[]) | **F** | Continuous ATR-normalized distance; interpretation is magnitude, not declared bands | No | No | — | — | — |
| 37 | `liquidity_pressure_score` | FM-026 | — | **E** | Monotone transform of `liquidity_distance` (audit: exact bijection class) | No | No | — | — | — |
| 38 | `volume_spike` | FM-063 | NoSpike / VolumeSpike | **A** | Vector-bound participation *intensity* state (adaptive percentile) | No | No | Volume | — | — |

\* `ema_spread`: corrected identity FM-030 exists but is **inactive** (`normalization_basis` default); activating it is a separate gated program, not a STATE-band addition.

**Non-vector stateful twins already in encoder (not 39 slots, recorded for completeness):**

| Identity | FM | Class role |
|---|---|---|
| `body_commitment` | FM-071 | A twin for idx 29 |
| `atr_magnitude` | FM-072 | A twin for idx 13 |
| `momentum_magnitude` | FM-073 | A twin for idx 12 |
| `rsi_state` | FM-068 | A twin for idx 15 |
| `displacement_flag` | FM-069 | Discrete conviction marker (distinct from FM-020 continuous) |
| `retest_flag` | FM-061 | Discrete retest presence (gates FM-021) |

---

## 3. Summary counts (must sum to 39)

| Class | Count | Features |
|---|---:|---|
| **A** STATE_COVERED | **16** | 6,10,12,13,15,20,21,22,23,24,25,26,29,30,31,38 |
| **B** VALUE_SEMANTIC | **7** | 0,1,2,3,4,27,28 |
| **C** STATE_REQUIRED_EXISTING_VALUE | **0** | — |
| **D** NEW_MEASUREMENT_REQUIRED | **0** | — *(O15 is residual observation, not a 39-slot class)* |
| **E** IMPLEMENTATION_INTERMEDIATE | **5** | 7,8,16,17,37 |
| **F** INTENTIONALLY_UNBANDED | **11** | 5,9,11,14,18,19,32,33,34,35,36 |
| **G** UNKNOWN | **0** | — |
| **Σ** | **39** | |

```text
16 + 7 + 0 + 0 + 5 + 11 + 0 = 39  ✓
```

---

## 4. O5 — Participation (deep dive)

**Census observation (10 episodes):** O5 = PARTIAL 5 / COVERED 5 (recurring PARTIAL).

**Authoritative chain (source):**

| Quantity | FM | Role | States |
|---|---|---|---|
| `volume` | base_input | raw count | none (B) |
| `volume_ratio` | FM-062 | volume / SMA(volume) — self-normalized participation | `states: []` (F) |
| `volume_spike` | FM-063 | adaptive percentile spike on volume_ratio | **NoSpike / VolumeSpike** (A) |

**Why PARTIAL is not a missing STATE:**

`scripts/research/xauusd_episode_coverage_census.py` marks PARTIAL when:

```text
volume_spike == NoSpike  AND  expansion-scale morphology is present
```

That is a **participation STATE ↔ expansion CONTEXT** relationship question, not the absence of a participation state. `NoSpike` is a real declared state; inventing a Spike merely because expansion is convenient would fabricate semantics.

**Decision:**

- Do **not** add Low/Med/High participation bands on `volume_ratio` in this task.
- Keep `volume_spike` as the discrete participation intensity state.
- Keep the expansion relationship at CONTEXT/episode layer (already CLOSED for L4 structure).
- O5 residual remains an **episode-coherence observation**, not a C-class state gap.

---

## 5. O15 — Wick / absorption (deep dive)

**Census observation:** O15 = UNREPRESENTED 10/10 (recurring).

**Measurements that exist:**

| Identity | FM | Lifecycle | Vector slot | States |
|---|---|---|---|---|
| `upper_wick` | FM-003 | parity_verified | **no** | [] |
| `lower_wick` | FM-004 | parity_verified | **no** | [] |
| `total_wick` | FM-005 | parity_verified | **no** | [] |
| `upper_wick_ratio` | FM-011 | research, `active:false` | **no** | [] |
| `lower_wick_ratio` | FM-012 | research, `active:false` | **no** | [] |
| `body_to_total_wick_ratio` | FM-013 | registered, inactive | **no** | [] |
| `body_ratio` → `body_commitment` | FM-010 / FM-071 | certified | body_ratio yes / twin no | LowCommitment ≈ wick-dominated *unsigned* |
| `price_position` | *(none)* | computed in `feature_pipeline` then **discarded** | no | no FM |

**Verification vs “NEW_MEASUREMENT_REQUIRED if pursued”:**

1. **Directional wick ratios (FM-011/012)** exist as research formulas but are **not production-authoritative** (`active:false`, not in CANONICAL_FEATURES, `states: []`). Promoting them + declaring state vocabulary is a **measurement-surface activation + ontology state program**, not a pure C interpret-existing-vector-value.
2. **`price_position`** (close location in range — the audit’s preferred absorption signal) is **computed and discarded**, with **no FM identity** — classic **D**.
3. **`body_commitment` LowCommitment** covers *unsigned* wick-dominated bars only; it does **not** express upper vs lower rejection / absorption.
4. None of the **39** slots *is* a directional absorption feature (`candle_range` is high−low, not wick).

**Decision for this task:**

```text
O15 pursuit class = D  NEW_MEASUREMENT_REQUIRED
  (register/activate absorption measurement + declare state vocabulary;
   do NOT invent formula / vector slot / state names in this pass)

Among the 39: no C-class row maps to O15.
STOP for O15 implementation.
```

---

## 6. Continuous remainder (27/39) — why not C

The encoder’s `continuous_features` list is a **descriptive census**, not a mandate to band.

| Bucket | Count | Disposition |
|---|---:|---|
| Continuous but **A via magnitude/twin** | 4 | body_ratio, atr, momentum_score, rsi_14 |
| Continuous **B** primitives | 7 | OHLC, volume, body_size, candle_range |
| Continuous **E** intermediates | 5 | emas, macd line/signal, liq pressure |
| Continuous **F** intentional | 11 | volume_ratio, ema_spread, …, liq distance |
| **C** | 0 | none with affirmative “state required” evidence |

No continuous feature met the C gate (existing authoritative value **and** defensible missing state interpretation **and** safe normalization **without** new measurement).

---

## 7. Implementation

```text
C = 0  →  no code changes
          no ontology state additions
          no FeatureStateEncoder / MagnitudeStateEncoder edits
          no Context / Shape / CRT / Testimony / Agreement edits
```

**Regression (this session):**

```text
pytest tests/test_feature_states.py
      tests/test_magnitude_states.py
      tests/test_market_context.py
      tests/test_model_evidence.py
      tests/test_episode_agreement.py
      tests/test_episode_propositions.py
→ 116 passed
```

**Invariants held:**

| Invariant | Status |
|---|---|
| Canonical 39-vector | UNCHANGED |
| Feature values | UNCHANGED |
| Production spine path | UNCHANGED |
| O6/O7/O18 magnitude states | UNCHANGED |
| L4 CONTEXT | CLOSED — unchanged |
| L7 TESTIMONY | CLOSED — unchanged |
| AGR-v0 AGREEMENT | UNCHANGED |
| O11 conflicts preserved | (not touched) |
| O12 ORTHOGONAL | (not touched) |
| `PRODUCTION_BEHAVIOR_CHANGED` | **NO** |

---

## 8. Whole-chain status (post-census; no C implementation)

Same 10-episode certification corpus (`results/research/xauusd_episode_semantic_reconstruction/`):

| Layer | Status | Notes |
|---|---|---|
| VALUE | OK 10/10 | unchanged |
| STATE | OK 10/10 | 2A + discrete vector states; census classifies remainder honestly |
| CONTEXT | **CLOSED** OK 10/10 | not reopened |
| SHAPE | ~9/10 | residual partial elsewhere; not this task |
| CRT | OK 10/10 | not reopened |
| TESTIMONY | **CLOSED** OK 10/10 | not reopened |
| AGREEMENT | BREAK 5 / PARTIAL 4 / OK 1 | AGR-v0 **unchanged** |

Residual **observations** (not incomplete 39-classifications):

- O5 PARTIAL — participation state present; expansion *relationship* is context/episode
- O15 UNREPRESENTED — **D** if pursued (measurement promotion required)
- O11 CONFLICT — preserved real conflicts (not a state gap)

---

## 9. Final decision block

```text
STATE CENSUS:
    39/39 classified = YES

STATE_COVERED:                 16
VALUE_SEMANTIC:                 7
STATE_REQUIRED_EXISTING_VALUE:  0
NEW_MEASUREMENT_REQUIRED:       0   (among the 39; O15 residual = D if pursued)
IMPLEMENTATION_INTERMEDIATE:    5
INTENTIONALLY_UNBANDED:        11
UNKNOWN:                        0

NEW STATES IMPLEMENTED:         []
NEW MEASUREMENTS:               NONE
  (O15 blocker if pursued: activate/register directional wick or price_position
   + declare state vocabulary — separate authorized program)

CONTEXT:                        CLOSED — unchanged
TESTIMONY:                      CLOSED — unchanged
AGREEMENT:                      UNCHANGED
CANONICAL VECTOR:               UNCHANGED
PRODUCTION_BEHAVIOR_CHANGED:    NO

STATE_CLOSURE:                  CLOSED
```

**Meaning of CLOSED here:** every canonical feature has an evidence-backed A–G status; zero C-class work remains; residual episode observations (O5 relationship, O15 measurement gap) are **classified**, not papered over with invented states.

---

## 10. Authority trail

| Claim | Source |
|---|---|
| 39-slot order / dim | `src/features/feature_schema.py` · `CANONICAL_FEATURES` |
| State encoder continuous=27 | `FeatureStateEncoder.continuous_features` |
| Declared states | `configs/formulas/market_ontology.yaml` `states` blocks |
| Magnitude twins O6/O7/O18 | `magnitude_states.py` · FM-071/072/073 · Phase 2A cert |
| O5 PARTIAL rule | `scripts/research/xauusd_episode_coverage_census.py` |
| O15 gap + price_position discard | reconstruction script · `feature_pipeline.compute_canonical_candle_features` · FM-011/012 |
| F-061 band block on ema_spread/momentum | ontology `known_issue` + `feature_states.py` module docstring |
| Liquidity pressure = f(distance) | semantic-layer certification audit redundancy report |

---

*Honest UNKNOWN / D / F is a successful result. Invented states are not.*
