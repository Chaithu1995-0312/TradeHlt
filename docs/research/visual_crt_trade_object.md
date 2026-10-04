# Visual CRT Trade Object — specification (SEM-012)

**Status:** Lane 1 (semantic certification) · `knowledge_status: CHARACTERIZED` · **frozen before measurement**
**Date:** 2026-08-17 · **Change:** `CH-visual-crt-trade-object`
**Code:** `src/research/visual_crt/` · **Floor:** `tests/research/test_visual_crt_trade_object.py`

---

## 1. Why this object exists

The question "how many profitable trades are in the TradingView screenshots" has no answer
today, because no trade object is defined for the picture. Measured on the captured shots:
19 marked engine events, exactly **one** trade-shaped (`ENTRY` 2026-07-30 07:00 LONG @
4058.87 → `SL` @ 4044.47, MFE 0.09R), and it is `SUPERSEDED` under F-074. The engine's own
month ledger records `84 SWEEP → 2 BEGIN_SOFT_CONF → 2 FILTER_REJECTED → 0 TRADE_OPENED`.

So the population is one loser. This spec defines the object that *could* have a
population: the trade a trader reading the chart would have taken.

## 2. What makes it a NEW ontology (and not a re-run of F-019…F-042)

The engine sweeps `M15StructuralLiquidityRange` (SEM-011) — a trailing 14-bar (first-seed
16-bar) count-window envelope. That is a *local extreme*, not a level anyone marked in
advance. The monthly TV↔production comparison measured how rarely the two coincide: of 84
M15-SLR pierces, **4/84** sat on a prior closed H4 high/low or PDH/PDL at spread tolerance,
and **51/84** touched no SMC level at all.

This object founds on **pre-existing, chart-visible pools** instead. That is a genuinely
different founding structure, which is the only legitimate basis for reopening the
directional class (F-028: reopen via a new ontology, never via a sweep of the old one).

**`P-CRT-LIQ-01` is not violated.** That policy forbids a second named CRT *liquidity
object*. This lives in `src/research/`, imports no spine module at runtime, touches neither
`detect_sweep` nor `M15-SLR`, and is wired into no engine. It is a research interpreter.
The floor test enforces the isolation with an AST import-walk.

## 3. The object — every field mechanical

### 3.1 Pool

A price level already drawable when the sweep bar printed. V1 vocabulary is closed:

| Kind | Source | Side |
|---|---|---|
| `PRIOR_H4_HIGH` / `PRIOR_H4_LOW` | most recent **closed** calendar H4 (`ParentCandleBuilder(rule="H4")`) | HIGH / LOW |
| `PDH` / `PDL` | most recent **closed** calendar D1 | HIGH / LOW |

No-lookahead is structural: `ParentCandleBuilder.parent_history` never exposes an
in-progress period, and `detect_pool_sweep` additionally ignores any pool whose
`formed_at_index >= bar.index`.

**Excluded from V1 on purpose:** session-so-far extremes. F-066 established that
MT5-sourced session labels on this exact XAUUSD corpus derive from broker-server time
mislabelled UTC (53.36% of bars wrong), so a session pool would inherit a known clock
defect. Adding it is a separate authorized change, not an oversight.

### 3.2 Sweep

Boundary-cross-then-close-back-inside, the same semantic as
`crt_engine_v2.RangeDetector.detect_sweep`, re-expressed against a pool:

- HIGH pool: `bar.high > pool.price and bar.close < pool.price` → **short**
- LOW pool: `bar.low < pool.price and bar.close > pool.price` → **long**

Sweeping buy-side liquidity implies a short; sell-side implies a long. When several pools
are pierced on one bar, the **deepest** wins (ties → caller's pool order, deterministic).

### 3.3 Displacement — the F-074 contract

The impulse must travel **away from the swept side**. Unsigned energy-only displacement is
not legal (`CH-directional-displacement-contract`, user-authorized 2026-08-13). Six gates,
applied in the engine's own order:

1. `bar.index - sweep.bar_index <= max_sweep_age_candles`
2. direction present
3. LONG requires `close > open`; SHORT requires `close < open`
4. LONG requires `close > sweep_price`; SHORT requires `close < sweep_price`
5. `body_ratio >= body_ratio_min` — canonical FM-010 via `features.candle_math`, never re-derived
6. `candle_range >= atr_multiplier_min * atr_abs` **and** `|close - open| >= atr_min_displacement * atr_abs`

`atr_abs` is ATR in **price units** (FM-074 `atr_absolute`), never the close-relative
canonical `atr` (FM-041). Passing the relative form silently shrinks every threshold — the
F-072 defect class.

### 3.4 Pre-registered thresholds

Mirroring the active config `v2_htfcrt_2026_08` so the object is *comparable* to the
engine rather than independently tuned. Frozen here before any outcome is computed.

| Parameter | Value | Source |
|---|---|---|
| `body_ratio_min` | 0.65 | active `params` |
| `atr_multiplier_min` | 1.0 | active `params` |
| `atr_min_displacement` | 1.2 | `CRTConfig` default |
| `max_sweep_age_candles` | 20 | `CRTConfig` default |
| `atr_period` | 14 | `CRTConfig` default |
| `n_prior_h4` | 1 | "the prior H4", the classic CRT read |

### 3.4b Retest (Arm B only) — and the substitution it rests on

Mirrors `crt_engine_v2.StateMachine.try_expansion_to_retest`:

```
depth_abs        = close - pool.price   (LONG)  |  pool.price - close  (SHORT)
adaptive_ceiling = max(retest_depth_max * impulse, retest_atr_depth_fraction * atr_abs)
min_depth        = retest_min_depth_atr_fraction * atr_abs
RETEST fires when  min_depth <= depth_abs <= adaptive_ceiling
```

`retest_depth_max = 0.15`, `retest_atr_depth_fraction = 0.3`,
`retest_min_depth_atr_fraction = 0.1`.

> **Declared modelling substitution (MC-VCRT-V1, Arm B).** The engine computes its static
> ceiling as `retest_depth_max * rng.size`. A pool is a **level**, not a range, so `rng.size`
> has no meaning here. `impulse = |displacement.close - sweep.sweep_price|` stands in for it.
> This is a substitution, not a discovery: it must never be restated as "the canonical CRT
> retest formula". A positive Arm B validates **this research object under this substitution**
> — it does not retroactively certify `try_expansion_to_retest`, and grants that engine path
> no authority.

### 3.4c Duplicates and supersession

Frozen in the contract, implemented by the driver — not driver-defined behaviour:

- **One shot per `(pool, direction)`** until a newer closed parent replaces that pool.
  Same guard shape as `weekly_sweep._first_sweep_this_week`.
- **At most one open trade at a time.** A signal arriving while a trade is open is dropped,
  not queued. This keeps labels non-overlapping, which the contract's own
  `splits.overlap_policy: forbid_overlapping_labels` requires.

### 3.5 Entry, Stop, Target, Cost

Expressed in ATR multiples so the object maps directly onto `research.contracts.Signal`
and resolves through the governing exit model.

**Two arms, pre-registered together** (`multiplicity.n_variants_preregistered = 2`,
Bonferroni). Choosing an arm after seeing outcomes is forbidden.

| Field | Rule |
|---|---|
| **Entry** | **Arm A**: close of the displacement bar. **Arm B**: close of the retest bar (§3.4b) |
| **Stop** | `sweep_price` ± `sl_atr_buffer × atr_abs` (beyond the swept extreme), `sl_atr_buffer = 0.2` |
| **Target** | `tp_atr_mult × atr_abs`, `tp_atr_mult = 2.0` (`tp2_atr_multiplier`) |
| **Exit model** | `forward_walk(exit_model="intrabar_fixed")` — the governing truth, SL-before-TP tie-break |
| **Timeout** | 40 bars, declared explicitly (never left to the `max_forward` default) |
| **Cost** | `CM-XAUUSD-LEGACY-12BPS-UNCALIBRATED`, declared in the sealed contract. 12bps is **not** a calibrated metals cost, so every net figure is DIAGNOSTIC |

### 3.6 Status

Every emitted trade carries `CURRENT` or `SUPERSEDED` (§6.2 rule 4). A definition change
supersedes rows in place; rows are never deleted.

## 4. What Lane 1 does NOT do

No ledger, no corpus run, no expectancy, no win count. The definition is frozen *before*
outcomes are computed — defining it afterwards would be look-ahead in the definition
itself. Counting happens in Lane 2, under sealed `MC-VCRT-XAUUSD-M15-V1`.

### 4b. The ceiling on what Lane 2 can return

`economic_claims_allowed` is **false** on that instance: `trust_status` requires `mt00: PASS`
and `mt01_matrix_coverage: COMPLETE`, and the repo is at 0/27 probes with
`MEASUREMENT_LAYER_STATUS = OPEN`. So Lane 2 answers *population and power*, reported as
DIAGNOSTIC — never an economic verdict.

| Outcome | Means |
|---|---|
| `n < 30` | `INSUFFICIENT` power — **not** "harmful", not evidence against the object |
| `n >= 30` | sufficiently populated for Lane-2 reporting |
| `n >= 30` **and** positive expectancy | **still not economically validated** |

30 is a pre-declared minimum for this lane, not a statistical threshold that confers validity.

### 4c. Kill criteria

Any result — `n=0`, `n<30`, negative diagnostic expectancy — is a **result to register**.
Changing pool tolerance, the retest predicate, the duplicate rule, or any other frozen
dimension after seeing outcomes requires a **new `MC-*` id, new hypothesis, new
pre-registration** (V2). The contract must not become a moving target.

## 5. Authority

This object **grants no** production, promotion, G001, or gate-flip **authority**
(CLAUDE.md §6.5 — evidence never grants authority). It changes no config, no model, and no
`ACTIVE_VERSION`. `knowledge_status` is `CHARACTERIZED`: a named, mechanically-specified
construction, **not** a claim that it is the correct or institutional reading of CRT.
