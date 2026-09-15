# Concatenated implementation plans — part 8 of 10

Source directory: `docs/implementation_plan/`
Files in this part: 16

## Contents

1. `semantic-layer-certification-audit-proud-mccarthy.md` (28585 bytes)
2. `study-sujantrader-docs-composed-snowflake.md` (10019 bytes)
3. `task-build-a-vision-assisted-silly-scone.md` (12041 bytes)
4. `task-enforce-strict-historical-splendid-gizmo.md` (11298 bytes)
5. `task-independent-formula-majestic-wolf.md` (2156 bytes)
6. `the-biggest-ambiguity-is-virtual-manatee.md` (6578 bytes)
7. `the-biggest-assumption-in-tender-lollipop.md` (9557 bytes)
8. `the-biggest-assumption-to-ticklish-forest.md` (5022 bytes)
9. `the-biggest-assumption-you-zippy-parnas.md` (9421 bytes)
10. `the-biggest-risk-you-rustling-rain.md` (6368 bytes)
11. `the-biggest-risk-you-spicy-quilt.md` (6812 bytes)
12. `the-biggest-weakness-i-deep-alpaca.md` (16204 bytes)
13. `the-image-you-shared-luminous-peach.md` (13825 bytes)
14. `the-key-unanswered-question-functional-corbato.md` (8752 bytes)
15. `the-largest-risk-mossy-graham.md` (4884 bytes)
16. `the-largest-risk-you-indexed-puddle.md` (11921 bytes)


================================================================================
SOURCE_FILE: docs/implementation_plan/semantic-layer-certification-audit-proud-mccarthy.md
SOURCE_BYTES: 28585
PART: 8/10 FILE 1/16
================================================================================

# Semantic Layer Certification Audit (OHLCV only) — findings + remediation plan

## Context

The semantic layer is about to be trusted as **evidence** by an LLM research system. That raises the
bar past "the code runs": every feature must be mathematically correct, semantically named for what
it actually measures, causally clean, reachable, and consistently declared across ontology →
registry → pipeline → runtime → canonical vector.

I audited the layer read-only against the active config (`configs/production/ACTIVE_VERSION` =
`v2_multi_2026_04`, `feature_pipeline.normalization_basis = "atr_relative"`) and ran four
read-only probes against the real pipeline (synthetic edge cases + `data/mt5/XAUUSD_M15.csv`,
n=19,922). No repository file was modified.

**Verdict: Semantic Layer NOT CERTIFIED. Confidence 88%.**

The layer is unusually well-governed — the ontology, registries, parity batteries, lint and census
are better than most production systems. It fails certification on a small number of *specific,
measured* defects, three of which are blocking for LLM evidence use: a stale dependency spine that
reports `CLOSED` while three shipping vector slots are uncertified; two active feature identities
that are not scale-invariant and saturate their consumers on 99.7–99.99% of real bars; and two
canonical slots whose names do not match the quantity they emit.

---

## Existing strengths (verified, not assumed)

| Area | Evidence |
|---|---|
| Anti-`eval` execution | Formulas are name→callable dispatch (`src/features/registry/`), never `eval`'d; `fm_resolve.resolve_fm` rejects ids containing expression characters. |
| Causal swing publication (FC1-A) | `feature_pipeline.py:660-695` — centered pivot over `w=2k+1` is `.shift(k)` before production binding, so bar `t` uses data ≤ `t`; structure refs take a second `.shift(1)`. Mathematically causal. |
| ATR-normalized family is scale-invariant | Probe: ×100 price leaves `disp_strength`, `volatility_ratio`, `retest_depth`, `liquidity_distance`, `body_ratio`, `atr` **exactly** unchanged (ratio 1.000). |
| Fail-closed config | `_require_fp_cfg` has no soft defaults; unknown `normalization_basis` raises rather than falling through (`feature_pipeline.py:151-157`). |
| Anti-copy-paste guards | `swing_high`/`swing_low` and `higher_high`/`lower_low` identity assertions (`:666-670`, `:713-717`). |
| Warmup is derived, not a literal | `required_warmup_rows()` = 78 on active config; probe on clean data drops exactly 78. |
| Geometry census sees what a name-lint cannot | `geometry_census.py` NAME/EXPRESSION/SINK triangulation found 102 EXPRESSION_ONLY sites a name-based lint would miss. |
| Registry validators are behavioral | `validate_registry` / `validate_semantic_registry` check structure, vocabulary, referential integrity and epistemic-block discipline. |

---

## Critical defects (blocking)

### C1 — Dependency spine is stale against schema v4.0; `CLOSED` is a false claim
`scripts/analysis/feature_dag_layers.py:79,102` still declares v3.0 names (`wick_size`,
`macd_hist`). Schema v4.0 renamed slot 28 to `candle_range` and split `macd_hist` into
`macd_hist_raw` (18) + `macd_hist_z` (19).

Recomputing `build_dag()` today yields `missing_canonical = ['candle_range','macd_hist_raw','macd_hist_z']`
(artifact `feature_dag_layers.LATEST.json`, dated 2026-07-14, still claims `[]`).

Consequences, all live:
- Those three slots have **no DAG node**, therefore **no certification-ledger row** — the frontier
  prints `{PROMOTED_PRODUCTION: 46, SUPERSEDED: 2}` and reads fully closed while three shipping
  dims are uncertified.
- `feature_surface_query --summary` reports `closure: {CLOSED: 36, None: 3}` and still prints
  `surface_status: CLOSED`.
- `feature_dag_layers.main()` returns exit 2; `tests/test_feature_dag_layers.py:43` asserts the
  literal `38` and fails.

**Why it blocks:** an LLM asking "is the feature surface closed?" gets `CLOSED`. That answer is
wrong for 3 of 39 dims. Category 4 (reachability) and 11 (internal consistency) both fail here.

### C2 — Two active identities are not scale-invariant and saturate their consumers
`ema_spread` (FM-022, idx 9) and `momentum_score` (FM-023, idx 12) divide an absolute-price
numerator by the **close-relative** `atr` (`atr_14_raw/close`), so `legacy ≡ corrected × close`.

Measured, not cited:
- ×100 price ⇒ std ratio **exactly 100.000** for both; **1.000** for every other normalized dim.
- Real XAUUSD (n=19,922): `momentum_score ∈ [−13,516, +16,595]`, `ema_spread ∈ [−6,658, +5,857]`.
- `|tanh(momentum_score)| > 0.999` on **99.70%** of bars (the `heuristic_gaussian_engine` input).
- `|ema_spread| > 0.15` (the `engine_runner.dual_engine` trend threshold) on **99.99%** of bars.

This extends F-061 (measured on crypto) to XAUUSD. The corrected identities FM-030/FM-031 exist,
are parity-proven and config-reachable, but `active: false`. The certification ledger already
records FM-022/FM-023 as **SUPERSEDED** — while the active config still emits them. Nothing flags
this at runtime.

### C3 — Two canonical slots emit a different quantity than their name
- **idx 35 `candles_since_retest`** measures bars since the last **sweep**, not since the retest
  (`feature_pipeline.py:988-997`; the local variable is literally `bars_since_sweep`). The CRT
  engine computes a *different* quantity under the *same* name
  (`current_candle_index - retest_candle_index`). Ontology registration as FM-065 was **attempted
  and withdrawn** because it turned the ownership lint red — the collision is documented at
  `market_ontology.yaml:1474-1497` and left open.
- **idx 11 `trend_strength`** (FM-064) is likewise unregistered: no formula, no lineage, no PIT
  class. Emitted value is a rolling-50 z-score of `SMA10(diff(SMA20(close)))`.

These are the **only two** of 39 slots with no ontology identity, and both are semantic concepts an
LLM will reason about by name.

---

## High-severity defects

### H1 — Interior row deletion breaks the timestamp→row-index map
A run of ≥ `atr_period` bars with zero true range drives `atr → 0`, which NaNs
`disp_strength`/`ema_spread`/`momentum_score`, and `finalize()` drops those rows then
`reset_index(drop=True)`.

Probe: a 20-bar flat run deleted **interior** positions 213–219 (85 dropped total vs 78 warmup);
clean control dropped exactly 78, all prefix. This contradicts the module's own stated invariant
(`required_warmup_rows` docstring: the count and first-valid index coincide "only because the drop
is a prefix") and silently misaligns the map `backtest_v2.py:1500-1530` depends on. Trigger is real:
halted/illiquid sessions, stale broker feeds, synthetic instruments.

### H2 — `formula_hash` contains no fingerprint of the executing code
`feature_dag_certify.py:78-85` hashes `{formula_id, intended-quantity prose, sorted deps}`. Editing
a formula body (e.g. `<=` → `<` in `sweep_high`, `feature_pipeline.py:724`) leaves the hash
identical, so **no STALE cascade fires**. The ledger has **zero** `INVALIDATED_STALE` events — the
cascade has never run against real data. Certification therefore attests to a declaration, not to
the code that ships.

Compounding: the witness strings hold stale line numbers, and the `session` witness still describes
the **v3.0 3-value hour partition** that FM-052 replaced on 2026-07-22 — re-certifying `session`
today would change its hash purely from prose.

### H3 — Scalar↔pipeline parity is only valid at default config values
`derived_math.disp_strength` hardcodes `clip(0,3)`, `retest_depth` hardcodes `clip(0,1)`,
`liquidity_pressure_score` hardcodes `-0.5` / sentinel `10.0`. The pipeline reads all of these from
`feature_pipeline.*` config keys. Changing any knob silently diverges the scalar authority from the
vectorized authority while the parity battery still passes at defaults.

### H4 — Same-bar two-sided sweeps lose their bearish leg
`feature_pipeline.py:727-730`: `np.where(sweep_high, 1, np.where(sweep_low, -1, 0))`. A bar that
sweeps both extremes and closes back inside — the most informative liquidity bar there is — is
recorded as `+1` only. `double_sweep` (FM-060) then cannot detect it, because it looks for
opposite-signed values across a 5-bar window. `break_of_structure` has the same undeclared
bullish-priority tie-break (`:719-722`).

### H5 — Trained artifacts remain bound to pre-causal (leaking) swings
`feature_surface_query --summary`: `rr_pit: PIT_UNCLEAN_CENTERED_SWINGS`,
`zone_pit: PIT_UNCLEAN_CENTERED_SWINGS`. The pipeline's production columns are causal-delayed, but
`rr_model.json` and `zone_registry.json` were fit on centered (future-leaking) swings. ZoneGate is
the only live HARD gate (F-041). Temporal correctness passes for the *pipeline* and fails for the
*artifacts* consuming it.

### H6 — Journal emission re-opens the FM-027/FM-021 and FM-028/FM-020 name collisions
`crt_engine_v2.py:3215-3228` reads `cf.get("displacement_retrace", cf.get("retest_depth", 0.0))`
and re-emits both under `cached_retest_depth` / `cached_disp_strength`. A journal row cannot
distinguish "no displacement" from "cache absent", and a downstream reader gets FM-027 under
FM-021's name — the exact collision CH-002 closed on the cache.

---

## Medium-severity defects

- **M1 — Absolute-valued epsilons in scale-sensitive denominators.** `rs = gain/(loss + 1e-9)`
  (`:494`), z-score `/(std + 1e-9)` (`:752`), `bb_position` `+1e-9` (`:521`),
  `body_to_total_wick_ratio` `tw > 1e-8` (`candle_math.py:64-74`), and
  `crt_sweep_taxonomy.py:122` `full_range = max(high-low, 0.001)`. None is scale-invariant; on a
  low-priced instrument the epsilon becomes a material term.
- **M2 — Guard asymmetry for one identity.** FM-013 computed via `compute_composition` uses
  `den > 0`; via `candle_math.body_to_total_wick_ratio` it uses `tw > 1e-8`. Same FM id, two
  behaviours on `0 < tw ≤ 1e-8`.
- **M3 — Missing-data and real observations are indistinguishable.** `liquidity_pressure_score`
  maps a NaN distance to sentinel 10.0 ⇒ `exp(-5)=0.0062`; probe shows genuine distances reaching
  10.18, so the sentinel overlaps real data. `retest_depth = 0.0` means "perfect retest" *or* "no
  retest" (zero_rate 37–42%). `body_ratio = 0.0` on a zero-range bar means "maximum indecision" for
  a bar carrying no information. No feature marks degenerate bars.
- **M4 — Participation is broker-conditional and fails silently.** Probe: an all-zero-volume
  instrument yields `volume_ratio ≡ 1.0` and `volume_spike ≡ 0` — two constant dims, no warning.
  Common on FX/CFD feeds.
- **M5 — Warmup ignores EMA initialization bias.** `required_warmup_rows()` sums only
  `ma_periods[0]`, `trend_strength_window`, `zscore_window`. `ewm(adjust=False)` is non-NaN from
  row 0 and therefore never dropped; at defaults `3×macd_slow = 78` happens to coincide with the
  warmup. Raising `macd_slow` or `ema_slow_span` silently leaks biased rows.
- **M6 — `volatility_regime` biases to "high vol" during warmup.** `np.select(..., default=2)`
  (`:572-577`) sends a NaN percentile to regime 2, and `min_periods=1` on the rolling rank means
  the first valid ATR ranks against a population of 1 ⇒ `pct=1.0` ⇒ regime 2.
- **M7 — Ordinal codes fed as continuous magnitudes.** `session` {0..4}, `hour_of_day` {0..23},
  `volatility_regime` {0,1,2} enter the float vector consumed by distance/density models.
  `|OVERLAP − ASIA|` is meaningless, and `hour_of_day` is cyclic but encoded linearly (23 and 0 are
  maximally distant).
- **M8 — Declaration drift.** FM-028's `depends_on: [candle_range, atr]` names FM-041
  (close-relative), but the runtime passes `state.atr_abs` (absolute) — and the guard trace labels
  that absolute value `formula_id: "FM-041"`. FM-050 had exactly this bug and was corrected
  2026-07-19; FM-028 was not. Also: `TRADENET_SCHEMA`/`GAUSSIAN_SCHEMA` carry `version="3.0"` with
  `n_features=39` while `SCHEMA_VERSION="4.0"`; `derived_math.py` docstrings cite pre-2026-07-24
  line numbers throughout; `run()`/`build_feature_vector`/`live_engine_hook.py:373` docstrings say
  38 / 35 dims.
- **M9 — A degenerate but legal frame crashes with a misleading diagnosis.** A fully flat frame
  raises `AssertionError: swing_high and swing_low are bit-for-bit identical — column reference bug
  detected` (`:666-670`). That is a data-quality condition reported as a code bug.
- **M10 — `FEATURE_SCHEMA` is a second, contradictory schema.** A legacy 24-key dict in
  `feature_schema.py:17-42` containing 8 names that exist nowhere in the ontology
  (`bb_upper`, `bb_lower`, `zone_strength`, `pattern_score`, `tp_ratio`, `sl_distance`,
  `spread_pct`, `day_of_week`). Two hash functions coexist with different semantics:
  `FEATURE_ORDER_HASH` is order-sensitive, `SchemaObject.checksum` is order-insensitive;
  `SCHEMA_HASH` concatenates names without a separator.

---

## Formula corrections

| Id | Current | Corrected | Note |
|---|---|---|---|
| FM-022 | `(ema_fast − ema_slow) / atr` | `(ema_fast − ema_slow) / (atr · close)` | Already registered as FM-030, parity-proven, `active:false`. Behavior change — requires retrain + threshold recalibration. |
| FM-023 | `close_delta / atr` | `close_delta / (atr · close)` | Already registered as FM-031. Same gating. |
| FM-058 | `where(sweep_high, +1, where(sweep_low, −1, 0))` | emit both legs: keep `liquidity_sweep` ternary for compatibility **and** add `sweep_up`/`sweep_dn` booleans; `double_sweep` should OR in same-bar two-sided sweeps | H4 |
| FM-026 | NaN distance → sentinel 10.0 → 0.0062 | emit `NaN` (or a companion `liquidity_valid` flag) instead of a value colliding with real observations | M3 |
| FM-021 | 0.0 both for "perfect retest" and "no retest" | pair with the already-computed `retest_flag` in the vector, or emit NaN-with-flag | M3 |
| FM-028 | `depends_on: [candle_range, atr]` | `depends_on: [candle_range, true_range]` (absolute ATR), mirroring the FM-050 correction | M8, declaration-only |
| `derived_math` clips | hardcoded `(0,3)`, `(0,1)`, `-0.5`, `10.0` | read the same config keys the pipeline reads | H3 |
| RSI / z-score / bb epsilons | absolute `1e-9`, `1e-8`, `0.001` | scale-relative guards (e.g. `eps · close` or a strict `> 0` branch) | M1 |

---

## Missing semantic concepts (OHLCV-derivable only)

Each adds information not recoverable from the existing 39 dims.

1. **Close position in range** — `(close − low) / (high − low)`. Already computed at
   `feature_pipeline.py:794-798` as `price_position` and then **discarded**. `body_ratio` is
   sign-free magnitude; close *location* is the actual rejection/absorption signal. Cheapest real
   gain in the layer.
2. **Directional body / bar polarity** — `sign(close − open)`. `trend_bias` is EMA polarity, not
   candle polarity; the vector currently has no signed single-bar direction.
3. **Gap** — `open − prev_close` (ATR-normalized). Absorbed into `true_range` but never exposed;
   load-bearing at session boundaries and weekend rolls.
4. **Effort vs result** — `candle_range / volume` (or `|close−open| / volume`). Volume is present
   only as `volume_ratio` and `volume_spike`; neither expresses participation *efficiency*.
5. **Acceleration / deceleration** — second difference of close, and ATR slope (vol-of-vol). Repo
   grep: zero occurrences of `acceleration`, `atr_slope`, `vol_of_vol`. Momentum is first-order only.
6. **Multi-bar compression** — short-window range ÷ long-window range (NR7-style). `volatility_ratio`
   is single-bar; compression-before-expansion is a multi-bar state and is currently absent from the
   canonical vector (it exists only in `src/research/candle_state/`).
7. **Cyclic time encoding** — `sin/cos(2π·hour/24)`. Grep: no `sin(`/`cos(` anywhere in the feature
   layer. Fixes M7's linear-hour artifact.
8. **Exhaustion** — `upper_wick_ratio` / `lower_wick_ratio` (FM-011/FM-012) already exist as
   registered research nodes, `active:false`, no vector slot. Directional rejection is currently
   unrepresented; only the sign-free `body_ratio` ships.
9. **Degenerate-bar indicator** — an explicit flag for `candle_range == 0` / zero volume, so
   imputed values stop being indistinguishable from observations (M3, M4).

---

## Redundancy report (measured on XAUUSD, n=19,922)

**Exact functional identities — 100.0% of rows:**

| Redundant slot | Is exactly | Incremental information |
|---|---|---|
| 20 `sweep_detected` | `liquidity_sweep != 0` | zero |
| 10 `trend_bias` | `sign(ema_spread)` | zero |
| 18 `macd_hist_raw` | `macd_line − macd_signal` | zero |
| 37 `liquidity_pressure_score` | `exp(−0.5 · liquidity_distance)` (monotone bijection) | zero |
| 29 `body_ratio` | `body_size / candle_range` | zero given 27+28 |

**Near-collinear price-level block — `|r| ≥ 0.9997`:** `open`, `high`, `low`, `close`, `ema_fast`,
`ema_slow` (15 pairs above 0.97). Six of 39 dims are near-duplicate copies of the price level, and
they are non-stationary. For the consumers that use a distance metric — ZoneGate's similarity kernel
(the only live HARD gate), Gaussian NB density, RR Mahalanobis — these dominate the metric. This is
a mechanical explanation consistent with F-044 (in-sample `d_sq` never below 2.4 against `E[d_sq]=27`),
F-041B (0/8 zones clear honest E>0) and F-060 (Gaussian degenerates to a near-constant).

Recommendation: keep the raw OHLC dims only if a consumer genuinely needs levels; otherwise replace
the block with returns/ATR-normalized forms, and drop or explicitly flag the 5 zero-information
slots. **This is a schema-v5 change and invalidates every trained artifact** — it is not a free win.

---

## Reachability report

- **Unregistered but shipping:** idx 11 `trend_strength` (FM-064), idx 35 `candles_since_retest`
  (FM-065). Registration attempted and withdrawn.
- **Uncertified but shipping:** idx 18 `macd_hist_raw`, idx 19 `macd_hist_z`, idx 28 `candle_range`
  — no DAG node, no ledger row, no PIT class (C1).
- **Registered but unreachable:** FM-011 `upper_wick_ratio`, FM-012 `lower_wick_ratio` (research,
  `active:false`, no vector slot, no consumer); FM-030/FM-031 (reachable only via a non-promoted
  shadow config); FM-013 `body_to_total_wick_ratio` (emitted on the live path under its own name
  only).
- **Computed then discarded:** `price_position`, `range_size`, `bb_position`, `rsi_state`,
  `displacement_flag`, `ma_200` — all computed every run, none canonical.
- **Duplicate ids across sections:** FM-030/FM-031 appear in both `derived_metrics` and
  `migration_candidates`; the semantic contract requires ids unique across all sections, and
  `migration_candidates` is not in `_ITERATED_SECTIONS` so no validator sees the duplication.
- **Superseded but live:** `indicator_identities` IND-001/IND-002 duplicate FM-041/FM-042.
- **`consumed_by: [UNKNOWN]`** on ~30 nodes — the consumer half of the lineage graph is, by
  declaration, not established.
- **L5/L6 DAG layers are declared and empty** — no node carries layer 5 or 6.

---

## Dependency integrity report

- DAG is acyclic and grounded: `is_dag: true`, no undefined deps, no ungrounded nodes, layer
  monotonicity clean — but computed over a node set that no longer matches the shipping schema (C1).
- **Schema-dependent branch:** `if "liquidity_sweep" in df.columns` (`:988`) silently switches
  `candles_since_retest` between two different quantities. The ledger records the fallback as
  "NON-AUTHORITATIVE / unreachable in production", but it is a live conditional, not a guard.
- **Environment-dependent branches:** `TRUST_VOLREGIME_CAUSAL`, `TRUST_SWING_CAUSAL` — both are
  correctly confined to dual-emitting research views and cannot mutate production columns. Verified.
- **Ontology crosscheck drift:** 9 entries today vs 4 in the 2026-07-14 artifact, including
  `higher_high`, `lower_low`, `break_of_structure`, `liquidity_sweep`, `momentum_score_atr`.
- **102 EXPRESSION_ONLY geometry sites** — geometry recomputed without using a governed name, plus
  **24 distinct zero-range policies** and 7 `NON_EQUIVALENT_SAME_NAME` rows across the corpus.

---

## Normalization report

Eight coexisting bases in one 39-dim vector:

| Basis | Dims |
|---|---|
| Absolute price | 0–3 open/high/low/close, 7 ema_fast, 8 ema_slow, 16 macd_line, 17 macd_signal, 18 macd_hist_raw, 27 body_size, 28 candle_range |
| Close-relative | 13 atr |
| **Price-scaled (defective)** | **9 ema_spread, 12 momentum_score** |
| Dimensionless ATR-normalized | 14 volatility_ratio, 33 disp_strength, 34 retest_depth, 36 liquidity_distance |
| Bounded [0,1] | 29 body_ratio, 37 liquidity_pressure_score |
| Rolling z-score | 11 trend_strength, 19 macd_hist_z |
| Ordinal / categorical | 30 volatility_regime, 31 session, 32 hour_of_day |
| Binary / ternary | 5 volume_ratio (ratio), 6, 10, 20–26, 38 |
| Unbounded count | 35 candles_since_retest |

Two problems, in priority order: **(a)** dims 9 and 12 should share the ATR-absolute basis used by
14/33/34/36 and do not (C2 — the only inconsistency that is also a measured decision-surface
defect); **(b)** 9 raw absolute-price dims are non-stationary and instrument-scale-dependent, which
is defensible only if every consumer standardizes — and the distance-based consumers do not.

---

## Edge case report (probed, not inferred)

| Case | Behaviour | Deterministic? |
|---|---|---|
| Zero-range candle | `body_ratio=0`, `volatility_ratio=0`, `disp_strength=0`, `price_position=0.5` — indistinguishable from genuine low values | yes, but semantically ambiguous |
| ≥14 consecutive zero-TR bars | `atr→0` ⇒ NaN ⇒ **interior rows deleted**, index re-based | **no — breaks row alignment (H1)** |
| Fully flat frame | `AssertionError: column reference bug detected` | crashes with wrong diagnosis (M9) |
| Zero volume (single bars) | `volume_ratio=0`, `volume_spike=0`, rows survive | yes |
| Zero volume (whole instrument) | `volume_ratio ≡ 1.0`, `volume_spike ≡ 0` — two constant dims, silent | yes, silently degenerate (M4) |
| NaN propagation | `finalize()` replaces ±inf with NaN then drops; `build_feature_vector` raises on any residual NaN | yes — no imputation |
| First N bars | 78 rows dropped on active config; matches `required_warmup_rows()` exactly on clean data | yes (M5 caveat) |
| Warmup volatility regime | NaN percentile → regime 2 via `np.select(default=2)`; `min_periods=1` ranks against n=1 | yes, biased (M6) |
| Extreme volatility | `disp_strength`/`retest_depth` clip; `volatility_ratio` unbounded (13.3 observed) | yes |
| Gaps / session boundaries | absorbed into `true_range`; no explicit gap feature | yes |
| RSI with zero loss | `gain/1e-9` → RSI → 100, hard-clipped | yes; epsilon is dimensional (M1) |

---

## Remediation plan

Three tiers, deliberately separated because they carry very different authority under
`CLAUDE.md §6.5`. **Tier 1 is what I propose to implement now; Tiers 2 and 3 need an explicit
decision.**

### Tier 1 — declaration/consistency repair (hash-neutral, zero behaviour change)
No emitted value changes; every fix is provable byte-identical on the XAUUSD freeze corpus.

1. **Re-sync the DAG spine to v4.0** — `scripts/analysis/feature_dag_layers.py:79,102`: rename
   `wick_size`→`candle_range`, split `macd_hist`→`macd_hist_raw`+`macd_hist_z` with correct deps
   and layers. Regenerate `feature_dag_layers.LATEST.json`.
2. **Seed and certify the three orphaned slots** through the existing ledger
   (`scripts/governance/feature_dag_certify.py`) so `closure` has no `None` rows, and make
   `feature_surface_query` refuse to print `surface_status: CLOSED` while any row is unclosed.
3. **De-literalize the dim count** — replace `38` in `tests/test_feature_dag_layers.py:43`,
   `feature_dag_layers.py:271,324` with `len(CANONICAL_FEATURES)`.
4. **Register FM-064 `trend_strength` and FM-065 `candles_since_retest`** as canonical nodes,
   recording the CRT-vs-pipeline collision explicitly (the lint went red for a real reason — the
   right resolution is two distinct registered identities, not a withheld registration).
5. **Fix FM-028's declared dependency** to the absolute ATR, mirroring the FM-050 correction, and
   correct the `formula_id: "FM-041"` label on `state.atr_abs` in the guard trace.
6. **Make `derived_math` read the same config keys as the pipeline** (H3) so parity holds off-default.
7. **Close the journal collision** — `crt_engine_v2.py:3215-3228`: drop the cross-collision `.get`
   fallbacks; emit explicit `None`/absent rather than `0.0`.
8. **Docstring/citation sync** — `derived_math.py` line cites, 38/35-dim docstrings,
   `TRADENET_SCHEMA`/`GAUSSIAN_SCHEMA` version, the stale `session` certification witness.

### Tier 2 — semantic hardening (behaviour-changing, additive, config-gated)
Each ships behind a config flag defaulting to current behaviour, with a byte-identity parity proof
on the default arm.

9. **Strengthen `formula_hash`** to include an AST fingerprint of the executing pipeline function
   (H2), so a numeric edit actually fires the STALE cascade. Then run the cascade once deliberately
   to prove it works.
10. **Fail loudly on non-prefix drops** (H1) — `finalize()` asserts the drop is a prefix, or the
    pipeline carries an explicit source-position column so alignment survives interior deletion.
11. **Two-sided sweep preservation** (H4) — additive `sweep_up`/`sweep_dn`; `double_sweep` ORs the
    same-bar case.
12. **Degenerate-bar and missing-data flags** (M3, M4) — stop letting sentinels collide with
    observations; warn when a dim becomes constant.
13. **Scale-relative epsilons** (M1, M2) — unify the guards; single policy for zero-range.
14. **`price_position` promotion** (missing concept 1) — it is already computed; promoting it is
    the cheapest genuine information gain, but it is a vector change (see Tier 3 note).

### Tier 3 — needs your decision, not my judgement
15. **Activate FM-030/FM-031** (C2). The math is correct and proven; activation requires retraining
    `rr_model`/`gaussian` artifacts and recalibrating `engine_runner.dual_engine` thresholds tuned
    to the legacy magnitudes. Under §6.5 this needs demonstrated G001 improvement, and the ledger
    already marks the legacy pair SUPERSEDED. Leaving it is a knowingly-defective active identity;
    changing it is a promotion-gated behaviour change.
16. **Schema v5 vector surgery** — drop/replace the 5 zero-information dims and the 6 collinear
    price-level dims. Highest expected value for the distance-based consumers, but invalidates every
    trained artifact and every PIT/closure record.
17. **Re-fit `rr_model` / `zone_registry` on causal swings** (H5). ZoneGate is the only live HARD
    gate and is currently `PIT_UNCLEAN`.

---

## Verification

Tier 1 acceptance (all must pass before I report completion):

```bash
venv/Scripts/python.exe scripts/analysis/feature_dag_layers.py
```
```bash
venv/Scripts/python.exe scripts/governance/feature_surface_query.py --summary
```
```bash
venv/Scripts/python.exe -m pytest tests/test_feature_dag_layers.py tests/test_semantic_registry.py tests/test_derived_math.py teststy/test_candle_math.py tests/test_feature_lineage.py -q
```

- `feature_dag_layers.py` exits 0 with `missing_canonical == []` and `n_canonical_covered == 39`.
- `feature_surface_query --summary` shows `closure: {CLOSED: 39}` and no `None` PIT rows.
- `validate_registry()` and `validate_semantic_registry()` both return `[]`.
- `feature_math_lint` floor stays green (NEW violations = 0).
- **Byte-identity gate:** XAUUSD freeze-pin vector SHA unchanged, and the 39-dim matrix from
  `FeaturePipeline(...).run()` is bit-identical before/after on `data/mt5/XAUUSD_M15.csv`.
- Config hash unchanged (Tier 1 touches no `params` block).

Then the full **post-implementation revalidation checklist** (sections A–L) is re-run as a fresh
read-only audit against the modified tree — not from memory of this pass — with per-item evidence,
and the certification verdict re-issued.

---

## Governance notes

- Findings F-070+ to register: the C1 false-`CLOSED` claim, the C3 name/quantity mismatches, and
  the C2 XAUUSD extension of F-061.
- Doc-drift decisions required per §6.2 for every Tier 1 item touching a citation or a doc claim.
- No Tier 1 item downgrades an existing finding; Tier 3 item 15 would reverse the "representational
  only" framing that F-061 already partially retracted.


================================================================================
SOURCE_FILE: docs/implementation_plan/study-sujantrader-docs-composed-snowflake.md
SOURCE_BYTES: 10019
PART: 8/10 FILE 2/16
================================================================================

# Close out `v2_htfcrt_2026_08` verification + correct Sujan provenance + add the HTF-state/objective dimension

## Context

The `CH-htfcrt-parent-candle-smc-v1` program has **already shipped** (Phases 0–6): calendar-true
parent candles, a 3-candle parent-CRT state machine (`CRTState` 9→12), 9 SMC primitives as canonical
features (schema 39→48, v4.0→v5.0), and a promoted active version `v2_htfcrt_2026_08`. Findings
**F-075** and **F-076** are registered.

Three things are now outstanding, from two separate causes.

**(a) Verification is not fully closed.** The parity evidence landed and is good — background job
`bc4bqjaj8` returned `46997/47197`, exactly the figure already recorded in F-076, with both failures
being a stale pre-existing pin (`# measured 99.96% at settle time`), so **no new CRT-parity
regression**. But the full-suite tally was lost (job piped through `tail`, which buffers to EOF →
0 bytes), determinism was never run twice, and the `post_htfcrt` baseline successor to Phase 0's
`pre_htfcrt` was never captured.

**(b) A provenance overclaim I introduced, found by review and confirmed against source.** A review
challenged whether `C1=Range / C2=Manipulation / C3=Distribution` is Sujan vocabulary. Checked
against the primary docs — it is not, and more sharply, it *conflicts*:

| Token | Occurrences across both SujanTrader docs |
|---|---|
| `manipulation` | **0** |
| `C1` / `C2` / `C3` / "first candle" | **0** |
| `objective` | **51** |
| `accumulation` | 20 |
| `distribution` | 5 |

`SujanTraderCrtExpPart2.txt:869-872` defines a **four-state** model — *"State 1 – Expansion · State 2
– Accumulation · **State 3 – Distribution (look for reversal evidence)** · State 4 – Reversal"*. So
Sujan's *Distribution* is a **reversal-warning** state, while the shipped `DISTRIBUTION_C3` is a
**directional impulse** — near-inverted. Sujan's own 3-candle profile (`SujanTraderCRTExp.txt:787-791`)
is *expansion → small accumulation/base → recovery* (move→**pause**→move), not range→**sweep**→impulse.

The labels came from the **user's own directive** and are standard ICT/CRT vocabulary — they are not
invented, and the shipped state definitions carry no Sujan attribution. But two artifacts *do* borrow
Sujan's authority and must be corrected (E-001):
- [`src/config_layer/parent_crt.py:97-99`](D:/Tradelatest/src/config_layer/parent_crt.py) — *"mirrors the **source framework's** own 'has this CRT completed its objective?' discipline"*
- `docs/governance/build_manifests/CH-htfcrt-parent-candle-smc-v1.impact.json:4` — juxtaposes the three labels with `"Source: SujanTrader…txt study"`

**(c) The genuinely missing Sujan layer.** Objective is Sujan's dominant concept (51 hits, per-TF
`Monthly Objective` headers, checklist item *"☐ Has the 6M objective been reached?"*) and Accumulation
is his preferred trade location (`Accumulation ⭐⭐⭐⭐⭐ (Best place to prepare)` vs `Expansion ⭐⭐
(Usually avoid chasing)`). Neither exists in the build.

**User decisions taken:** keep the C1/C2/C3 names and fix attribution with a *stronger provenance
boundary* — "Sujan is evidence for the parent-candle philosophy and the four-state HTF model; it is
**not** authority for the C1/C2/C3 state-machine design" — modelling profile and HTF-state as **two
explicit dimensions**; and build the missing layer **wired into the spine**.

---

## Stage 1 — Close verification (do first; no new code)

1. **Full suite, unbuffered.** `python -m pytest tests/ -q > <scratch>/full.txt 2>&1` — redirect to a
   file, never pipe through `tail` (that's what lost the last run). Triage against the known
   pre-existing baseline (7 failures at Phase-4 close + the 2 stale-pin parity + 2
   `test_reachability_golden` + `test_agents_path_alignment` + 4 script-registry grandfather, all
   already attributed).
2. **Determinism.** Run the XAUUSD backtest twice; assert byte-identical vector + trade ledger.
3. **Baseline successor.** `python src/runtime/baseline_capture.py --label post_htfcrt`, then diff
   against Phase 0's `pre_htfcrt` manifest. Every delta must map to a named mechanism (schema
   39→48, `SCHEMA_HASH`, `ACTIVE_VERSION`) — an unexplained delta is a defect.
4. Record the resulting tallies in the completion manifest's `checks_result`, replacing the current
   prose estimate with measured numbers.

**Do not** regenerate `test_reachability_golden`'s golden — `active_models.yaml` is being edited by
concurrent sessions, so an isolated regeneration would capture unrelated in-progress state.

## Stage 2 — Provenance correction (E-001, same turn as Stage 1)

Cheap, no config/closure churn. Nothing is renamed.

- **`parent_crt.py:97-99`** — drop the "source framework" appeal; state the mechanical rationale
  directly (*a swept range is not a confirmed narrative until the impulse away from it confirms*).
- **`state_identity.py:59-61`** — add a short block comment: these are **profile-position** labels for
  the three parent candles, **not** Sujan's four HTF state labels; `DISTRIBUTION_C3` does **not**
  inherit Sujan's *Distribution*.
- **Impact manifest** — split `Source:` into `Trigger:` (the SujanTrader study prompted the work) vs
  the actual provenance of the labels (user directive + standard CRT vocabulary).
- **New finding F-077** (`RF-CRT-STRUCTURE`, `Contract: UNKNOWN`, Certain) recording the semantic
  divergence with the occurrence counts and the `Part2:869-872` citation, so it cannot silently
  re-propagate. Add the row to CLAUDE.md's Repository Truths Index; re-run
  `scripts/governance/export_findings.py`.
- Cross-reference from F-075's Note.

## Stage 3 — The second dimension: HTF state + objective + activation

Two orthogonal axes, per the agreed model:

```
                 PARENT CRT
          ┌──────────┴──────────┐
   CANDLE PROFILE            HTF STATE
    C1 → C2 → C3      Expansion/Accumulation/Distribution/Reversal
          └──────────┬──────────┘
                 OBJECTIVE → OBJECTIVE STATUS
                          ↓
                    LOWER-TF CRT → ACTIVATION → EXECUTION
```

**Design constraints (each is a real, verified hazard):**
- **New `HTFState` enum — do NOT extend `CRTState` again.** It is a separate dimension; extending
  `CRTState` would reopen the state topology a second time and conflate the axes.
- **Do not add a 4th expansion/compression implementation.** Three already exist:
  `CandleStateEncoder` (`src/research/candle_state/encoder.py:35-37`), `RegimeLabeler`
  (`src/interpreters/regime_observer.py:41`), and `volatility_regime`
  (`market_ontology.yaml:1748`). Production must not import `src/research/` (backwards layering) —
  follow the sanctioned `weekly_sweep`/`parent_crt` **reimplement-locally** precedent, with
  thresholds read from config via strict `_require()`, no silent defaults (§6.5).
- **Name clash:** `weekly_range.py:24` `ACCUMULATION_WEEKDAYS` means Mon/Tue, *not* Wyckoff
  accumulation. Namespace the new states on the enum; never a bare module constant.
- **Ontology first (§6.6):** register `HTFState` + `Objective` as canonical nodes in
  `market_ontology.yaml` **non-frozen sibling sections** before production use — the frozen runtime
  keys stay flat + additive. `market_story_ontology.yaml:149` already reserves
  `wyckoff (status: planned, "accumulation/distribution: spring, upthrust")` as the descriptive seam.
- **Activation ≠ bias veto.** `DISTRIBUTION_C3` must not become trade permission — structure validity
  is not execution validity. Objective-status gates *activation*; the parent-bias gate stays a veto.

**Sequencing (each step verifiable on its own):**
1. `HTFState` enum + a pure classifier over closed parent candles, config-driven thresholds. Unit-test
   against synthetic candles like `weekly_sweep` does.
2. Typed `Objective` / `ObjectiveStatus` (exists / achieved / invalidated) derived from HTF state +
   parent range levels. Distinct from `GoalSpec` (`goal_schema.py:78`), which is the **economic** G001
   objective — different concept, must not be conflated.
3. Ontology registration + `validate_registry()` green.
4. **Wire it — behind a config gate, default OFF, and prove byte-identical ledgers first.** This also
   closes F-075's open gap that *nothing currently threads `parent_state`*, so the shipped gate is
   unreachable. Flipping the gate ON is a **separate, explicitly-verified step** with its own before/
   after ledger diff — that ordering is what keeps §6.5 intact (wiring grants reachability;
   only measured ΔG001 grants authority).
5. New impact manifest for the wiring (it is a `RUNTIME_DECISION_PATH_CHANGE` on an already-promoted
   config), findings, topic sync, session log.

**Explicitly out of scope:** 3M/6M tiers (Sujan's checklist starts at 6M, but the 2-year corpus gives
only 24 monthly candles — deferred by earlier decision); retraining the 6 stale model families;
renaming any shipped state.

---

## Verification

- **Stage 1** is itself the verification gate — Stage 2/3 should not start until the full-suite tally,
  determinism, and `post_htfcrt` diff are recorded.
- **Stage 2:** `pytest tests/test_current_findings.py tests/test_findings_export.py
  tests/test_doc_citations.py tests/test_topic_docs.py` + confirm zero remaining Sujan-attribution
  claims (`grep -rn "source framework\|Sujan" src/ configs/`).
- **Stage 3:** classifier unit tests; `validate_registry() == []`; **byte-identical XAUUSD ledger with
  the new gate OFF** (the hard gate — a diff here means a wrong config default); then a separately
  attributed diff with it ON.
- Close with `construction_protocol.py validate-completion <manifest>` and the §6 SESSION LOG.
- **No economic claim** is admissible from any of this: E rung stays OPEN (0 sealed `MC-*`), F rung is
  PARTIAL until the 9 SMC slots carry `CLOSURE_STATUS` rows.


================================================================================
SOURCE_FILE: docs/implementation_plan/task-build-a-vision-assisted-silly-scone.md
SOURCE_BYTES: 12041
PART: 8/10 FILE 3/16
================================================================================

# CRTStateResolver vs BacktestRunner — Economic Comparison (XAUUSD M15)

## Context

F-069 (previous program, complete and committed as `03c3dbf`) established that `CRTStateResolver`
cannot semantically reproduce `BacktestRunner` through configuration alone (88.16% agreement,
structurally config-unreachable EXPANSION-entry gap). The user now asks the natural follow-up:
**"which one is giving better results — run the latest report on MT5 XAUUSD and share it."**

Clarified with the user: "better results" can't mean trading performance for the resolver as-is,
because `CRTStateResolver` has no execution authority at all — it is a research-shadow classifier,
never a trading model (§6.5 Authority Ladder, CLAUDE.md). Confirmed deductively, not just
empirically: `_continuous_gates_pass`'s EXECUTION branch (`src/features/crt_state_resolver.py`)
requires a `score`/`risk_score`/`crt_score` feature absent from `CANONICAL_FEATURES`
(`src/features/feature_schema.py`) — resolver EXECUTION count is 0 in every measurement taken this
session (baseline, all 33 F-069 sweep candidates, Stage B). So a strict "same trigger rule"
comparison is a foregone conclusion before any code runs.

The user chose to proceed anyway with a **relaxed-trigger simulation**: trade the resolver's
**EXPANSION-entry** transitions (its most-populated non-trivial state) instead of EXECUTION,
explicitly as a *different* rule from the engine's own — not a replay of the same strategy — and
compare the resulting economics (win rate, PF, expectancy, drawdown) against the engine's real
trades on the same corpus. The goal is an honest, decisive answer the user can act on, not a
technically-correct-but-hollow "0 vs 1" restatement of the structural fact.

**Verified this session, foundational to the design:**
- Both existing `BacktestRunner` runs on this corpus (`results/run_20260805_105350_XAUUSD/` and
  `results/run_20260724_104845_XAUUSD/`) produce **exactly 1 real trade each** (`wc -l` = 2
  including header). The newer run's engine code/config predate its own run timestamp
  (`crt_engine_v2.py` 10:34:48 < run 10:53:50; `v2_multi_2026_04.json` Aug 2, well before) — it is
  current, trustworthy ground truth; **no fresh BacktestRunner run is needed.**
- A concurrent session's descriptive doc, `reports/crt_state_resolver_vs_backtest_runner_report.md`
  (correctly cites F-069's semantic-parity numbers), contains a **fabricated worked example**
  (entry=2352.10, sl=2350.21) that does **not** match the real trade row
  (`entry_raw=2318.21, sl=2317.4565714285714, direction=LONG, pnl_rr_net=-0.0383`, confirmed by
  reading the CSV directly). The new report must read the CSV directly and must not cite that doc's
  numbers.
- My original assumption that `BacktestRunner` uses `ExecutionPlannerV1_2`/`UltronRiskGate` was
  **wrong** — verified by direct grep: both classes are used only by the separate live-trading path
  (`src/runtime/live_engine_hook.py`) and are never imported by `backtest_v2.py`.
  `ExecutionPlannerV1_2` explicitly disclaims SL/TP in its own docstring and a self-test assertion.
  The real trade builder is `ExecutionEngine.build_trade()` in `src/config_layer/crt_engine_v2.py`.
- `CRTStateMemory.displacement_direction` (`crt_state_resolver.py:125`, set at DISPLACEMENT/SWEEP
  entry, carried into EXPANSION) is the principled, already-tracked direction source for the
  resolver arm — no new direction-inference rule needs to be invented.

## Design

### New script: `scripts/research/crt_resolver_economic_comparison.py`

Follows the established F-069 probe convention exactly (READ-ONLY docstring stating the trigger-rule
divergence up front, `_ROOT`/`sys.path` shim, `CERT_VERSION`, prediction-before-results discipline).

**Engine-side ledger** — `resolve_engine_ledger()`: reads
`results/run_20260805_105350_XAUUSD/XAUUSD_trades.csv` directly (default; `--force-fresh-run` escape
hatch re-runs `BacktestRunner` via the `detection_sweep.py:71-79` idiom
`ConfigBuilder.build("XAUUSD")` → `BacktestConfig.from_prod_config(...)` → `CandleLoader` →
`BacktestRunner(...).run(...)` if ever needed). No metric reinvention — the CSV's `pnl_rr_net` is
the engine's own already-costed truth.

**Resolver-side EXPANSION-entry adapter** — `CRTStateExpansionSignalSource`, following
`src/research/adapters/shape_signal_source.py`'s `_compute()` pattern (the closest existing
precedent for turning a bar-by-bar classifier into a signal source). Reuses
`scripts/research/crt_state_confusion_matrix.py::build_resolver_timeline`/`compute_enriched_frame`
for the resolver drive rather than reimplementing it, but must capture `resolver.memory` snapshots
per bar (needed for `displacement_direction` + `displacement_candle_index`), which
`build_resolver_timeline` doesn't expose — a short, locally-scoped per-bar loop mirroring it, with a
comment citing why. Detects **entry transitions** (`states[i]=="EXPANSION" and states[i-1]!=
"EXPANSION"`), not occupancy. SL mirrors the engine's shape — `disp_low - sl_atr_buffer*atr` (LONG)
— reading `sl_atr_buffer`/`tp1_atr_multiplier` from `ConfigBuilder.build("XAUUSD")` at runtime, never
hardcoded, so a future config change can't silently desync this script from the engine. TP is a
**single flat TP1 multiplier only** (no per-intent classification, no TP1-partial/breakeven-trail/TP2
two-leg structure) — an explicit, stated simplification, not an attempt at a byte-exact replay. Bars
with `displacement_direction == 0` (undetermined) or an inverted SL are **skipped and counted**, never
defaulted to a guessed direction.

**Measurement** — reuses existing, tested machinery, no reinvention:
- `src/research/measurement/forward_walk.py::forward_walk(signal, future, exit_model=
  "intrabar_fixed")` for the resolver arm, using the `atr=1.0` raw-price-distance trick already
  established by `src/research/adapters/spine_signal_source.py` (set `sl_atr_mult`/`tp_atr_mult` to
  the actual price distances, `atr=1.0`, so `Signal`'s ATR-multiple contract carries exact prices).
- `src/research/measurement/metrics.py::EdgeAggregator.aggregate(...)` for both arms — same
  win/PF/expectancy formulas as the engine's own (`net_rr > 0` convention matches), applied
  identically so the comparison table is apples-to-apples on the *math*, with cost-model choice
  stated explicitly (native engine cost vs. flat 12bps `DEFAULT_COST_MODEL` — report both, don't
  silently blend).
- `src/research/measurement/bootstrap.py::bootstrap_ci(...)` per arm on the mean net-R, deterministic
  seed shared across both arms. `n==1` (engine side) returns `(v, v)` by the module's own design —
  marked `"ci_degenerate": True"` in the report, not hidden.
- **Explicitly skip `src/research/qualification.py`'s full M4 gate** — its `min_samples`/OOS-split/
  permutation/BH-FDR machinery is built for multi-hypothesis discovery search, not a two-arm
  structural comparison, and would fail outright at n=1 in a way that misrepresents "no gate passed"
  as "rejected" rather than the true "insufficient data to gate at all."

### Report (`reports/crt_resolver_economic_comparison.md`)

Methodology-before-results structure (the pre-registration discipline, satisfied inline since the
script's logic is fixed code run once, not tuned after seeing numbers):
1. **Trigger rule stated for each arm** — engine = native EXECUTION branch (the real production
   rule); resolver = EXPANSION-entry, explicitly flagged as a *different, relaxed* rule, with the
   F-069 citation for why EXECUTION-triggered resolver trades are structurally impossible.
2. **SL/TP construction + simplifications stated** for each arm.
3. **Cost model choice stated** — both native and flat-12bps columns, not blended.
4. **Provenance** — which run directory was used and why, corpus path, resolver config state
   (current committed `market_crt_states.yaml`, untouched for this comparison).
5. **Comparison table**: n, wins, losses, win rate, PF, expectancy, max drawdown, bootstrap 95% CI,
   skip/reject counters.
6. **Epistemic Integrity caveat (Program E-001)** — explicit "INSUFFICIENT, no economic conclusion
   derivable at this sample size" framing for both arms (`MIN_CELL_N` precedent), stating plainly
   that the only decisive, non-statistical finding is structural: the engine can trade under its own
   rule and the resolver's native rule cannot, full stop — anything beyond that is illustrative, not
   a finding either direction.
7. **A note correcting the record** on the concurrent doc's fabricated worked-example numbers, so a
   future reader doesn't cite them as real.
8. **Authority footer** — grants no authority to modify resolver/engine/config regardless of outcome.

### Tests (`tests/research/test_crt_resolver_economic_comparison.py`)

Same `importlib.util.spec_from_file_location` + `sys.modules[name]=mod`-before-`exec_module` pattern
used throughout F-069's test files (proven working this session). Assertions on concrete values, not
just "no exception" (E-001 discipline):
- Entry-transition detector fires on transitions, not occupancy (synthetic state list).
- Direction inference is deterministic and correctly skips `displacement_direction==0`.
- SL construction matches the engine's formula byte-for-byte on a hand-built synthetic bar.
- Inverted-SL bars are rejected and counted, never silently kept.
- The real trades CSV parses to the expected concrete row (skip-if-absent fixture).
- `n=1` bootstrap CI returns a degenerate `(v, v)` and is marked as such in the output.
- Report generation places the methodology section before the comparison table.

### SITS registration (same turn)

`script_census.py --write-stubs` → overlay in `scripts/governance/seed_script_registry.py`
(category `RESEARCH_RUNNER`, `ttl_days=90`, `task_refs=["F-069","SITS"]`, purpose citing the
relaxed-trigger caveat) → `seed_script_registry.py` → `generate_script_matrix.py` →
`query_scripts.py --validate`.

### Explicitly out of scope (agreed)

No per-intent TP classification for the resolver arm (no `cached_features` equivalent in resolver
memory). No TP1-partial/breakeven-trail/TP2 replication. No M4 QualificationGate routing. No
modification to `CRTStateResolver` (re-derive displacement candle OHLC via raw row lookup instead).
No fresh `BacktestRunner` run unless the existing one proves stale (it doesn't). No promotion or
production-config change of any kind, regardless of the result.

## Verification

1. `pytest tests/research/test_crt_resolver_economic_comparison.py` — all pass, including the
   byte-for-byte SL formula check and the transition-vs-occupancy check.
2. Run `python scripts/research/crt_resolver_economic_comparison.py` — confirm it completes, emits
   both `results/analysis/crt_resolver_economic_comparison.LATEST.json` and
   `reports/crt_resolver_economic_comparison.md`, and the resolver arm's skip/reject counters plus
   engine arm's n=1 are visible and explained, not hidden.
2b. Sanity-check the resolver arm's trade count is in a plausible range given ~1,500-4,600 EXPANSION
    bars but far fewer *entry transitions* (sticky-dwell collapses many bars into one entry) —
    flag if it comes out at 0 or absurdly high before trusting the comparison table.
3. `python scripts/governance/query_scripts.py --validate` exits clean after SITS registration.
4. Read the generated report end-to-end for internal consistency (methodology matches what the code
   actually did; no leftover reference to the concurrent doc's fabricated numbers).
5. `SendUserFile` the finished `reports/crt_resolver_economic_comparison.md` to the user, with a
   short chat summary stating the headline structural fact first (engine can trade, resolver's
   native rule cannot) before the illustrative relaxed-trigger numbers.

## Out of scope

No changes to `src/features/crt_state_resolver.py`, `src/config_layer/crt_engine_v2.py`, or any
production config. No commit unless the user asks, matching this session's established convention.


================================================================================
SOURCE_FILE: docs/implementation_plan/task-enforce-strict-historical-splendid-gizmo.md
SOURCE_BYTES: 11298
PART: 8/10 FILE 4/16
================================================================================

# Enforce Strict Historical Data Schema (No Defaults)

## Context

Historical OHLCV ingestion across the codebase silently papers over missing data:
`CandleLoader` treats `volume` as optional, `FeaturePipeline` injects `volume = 0.0`
when the column is absent ("Forex safe fallback"), `historical_fetcher`/`sl_tp_comparator`
cascade `.get("open", .get("Open", 0))`, and the governance/runtime row-readers default
every field to `0.0`. The result: a malformed dataset (missing a whole column) produces
silent zero-filled candles instead of a hard failure, corrupting backtests, training data,
and live decisions without any signal that the source was broken.

**Goal:** any historical dataset missing one of the six mandatory columns must fail
immediately and loudly. No defaults, no auto-generation, no column substitution, no
zero/one-fill for `timestamp, open, high, low, close, volume`.

## Decisions (locked with user)

1. **Volume rule = column presence.** The `volume` column must physically exist or load
   fatal-errors. Remove only the silent *inject-when-absent* fallback. **Keep** the
   existing `compute_volume_features()` high-low proxy for files that genuinely carry an
   all-zero volume column (Forex). Real zero values in a present column are valid data.
2. **Scope = everything**: historical DataFrame loaders + CSV/dict row loaders + live
   intake (`live_engine_hook`) + strategy plugins `s01–s10`.
3. **Only the six OHLCV fields are governed.** Derived/auxiliary feature defaults
   (`ema_fast`, `atr`, `body_ratio`, `volume_ratio`, the 30 non-OHLCV canonical features,
   etc.) are **out of scope** and left untouched. Touch a `.get(field, default)` only when
   `field ∈ {timestamp, open, high, low, close, volume}`.
4. **Header aliasing is permitted normalization, not substitution.** Mapping `Open→open`,
   `o→open`, `tick_volume→volume`, `datetime→timestamp`, or merging real `date`+`time`
   columns is allowed (the column exists, just differently named). What is forbidden is
   inventing a column that has no alias present, or sourcing `timestamp` from the row index.

## New shared helper

**Create `src/data_ingestion/ohlcv_schema.py`** — single source of truth for the contract:

```python
REQUIRED_OHLCV_COLUMNS = frozenset({"timestamp", "open", "high", "low", "close", "volume"})

def require_ohlcv_columns(columns, *, source: str = "Historical dataset") -> None:
    missing = REQUIRED_OHLCV_COLUMNS - set(columns)
    if missing:
        raise ValueError(
            f"{source} missing required columns: " + ", ".join(sorted(missing))
        )
```

Error text matches the task spec exactly (e.g. `Historical dataset missing required columns: close, volume`).
No logging, no warning — raise. All loaders below import this constant/function rather
than re-declaring the set.

## Tier A — DataFrame loaders (call `require_ohlcv_columns` after header normalization)

- **`src/features/feature_pipeline.py:161-172` (`_validate_input`)** — replace the
  current 5-column `required` list + the `if "volume" not in ...: self.df["volume"] = 0.0`
  block with a single `require_ohlcv_columns(self.df.columns, source="FeaturePipeline")`.
  Keep the numeric coercion loop. **Keep `compute_volume_features()` (lines 200-214)
  unchanged** — the high-low proxy stays for genuine zero-volume files.
- **`src/runtime/backtest_v2.py:1346-1358`** — after header lowercasing and the
  real `date`+`time` merge (lines 1350-1356, preserved — that is reconstruction from real
  columns, not index synthesis), call `require_ohlcv_columns(raw_df.columns)` before
  constructing `FeaturePipeline`. This gives a clear top-level error before the pipeline.
- **`src/governance/strategy_backtest.py:146-196`** — after `pd.read_csv(...)` /
  `FeaturePipeline(df).run()`, call `require_ohlcv_columns(df.columns)`; then change the
  six-field reads at lines 192-196 from `float(row.get("open", 0.0))` etc. to
  `float(row["open"])` … `float(row["volume"])`. Leave the `CANONICAL_FEATURES`
  comprehension at line 189 as-is (covers the 30 non-OHLCV features).
- **`src/config_layer/rr/rr_dataset_builder.py`** — flows through `FeaturePipeline`
  (`_build_canonical_features_df`, line 87), so column presence is enforced transitively.
  No direct change unless it reads a raw CSV before the pipeline (verify during impl).

## Tier B — CSV / dict row loaders (validate headers, then strict access)

- **`src/runtime/backtest_v2.py:651-680` (`CandleLoader.stream`)** — after `_detect_column`
  for all fields, build the set of canonical fields that resolved to a header (treat
  `date`+`time` as satisfying `timestamp`) and call `require_ohlcv_columns(resolved)`.
  This makes **volume mandatory**: replace line 675
  `vol = float(row[v_col]) if v_col is not None else 0.0` with strict `vol = float(row[v_col])`,
  and the OHLC-only `ValueError` at 665-666 is superseded by the unified check. Keep
  `COLUMN_ALIASES` (header aliasing) and the per-row `(ValueError, IndexError) → continue`
  guard for malformed *values* (distinct from missing *columns*).
- **`src/data_ingestion/historical_fetcher.py:505-520` (`_load_from_csv`)** — validate
  `reader.fieldnames` (case-normalized, allowing `tick_volume`/`Volume` aliases) against
  the six via `require_ohlcv_columns`; then drop the `.get(field, .get(Field, 0))` cascades
  at 515-519 in favor of strict resolved-key access. DB path (`_load_from_db`, explicit
  SELECT) and MT5 path already strict — leave them.
- **`src/analytics/sl_tp_comparator.py:480-502` (`load_candles_from_csv`)** — validate
  `DictReader` headers, then replace `float(row.get("open") or row.get("Open", 0))` (and
  high/low/close, timestamp at 493) with strict resolved access. This loader reads OHLC
  only; still enforce all six columns *present* in the file (dataset contract), reading the
  subset it needs without defaults.
- **`src/replay/timing_reconstructor.py:167-199` (`load_candles`)** — validate the CSV
  header row against the six, then strict index access for high/low/close (already
  index-based; just add the presence check + remove any silent skips that mask a missing
  column).

## Tier C — Live intake + strategy plugins (six fields only, strict access)

- **`src/runtime/live_engine_hook.py`** — for the six OHLCV fields only, convert
  `_safe_float(trade_data.get(field), default)` to strict required access (raise
  `ValueError`/`KeyError` with the standard message if absent). Affected lines:
  `_build_engine_input` 282-285 + 299 (close/open/high/low/volume cascade and `volume→1.0`);
  `_build_ohlcv_and_auxiliary` 329-333 (same cascade + `volume→1.0`); the engine-input
  echo at 617-620 (`get("open",0.0)`…); `844` (`get("close",0.0)`); and the timestamp
  default at `531` (`get("timestamp", candle_idx)` — must not fall back to the index).
  **Leave** all auxiliary defaults (`ema_fast→close`, `atr→0.0`, `volume_ratio→1.0`,
  `disp_strength`, `session`, etc.) untouched — not governed.
  > Risk note: live feeds must now deliver full OHLCV per tick; single-price ticks that
  > previously reconstructed O/H/L from close will now raise. This is the user-chosen
  > strict behavior.
- **Strategy plugins `src/strategies/s01_*.py … s10_*.py`** — replace
  `float(candle.get("close", 0.0))` / `get("open"|"high"|"low", 0.0)` with strict
  `float(candle["close"])` etc. Representative hits: `s09_pattern_recog.py:121,196-199,234-237`,
  `s10_trap_strategy.py:113`, and the `close` reads in `s01`–`s08`. Leave `volume_ratio`
  defaults (`s09:103`, `s10:109`) — derived, not raw volume.
- **`src/runtime/backtest_v2.py:2470`** — `float(row.get("volume", 0.0))` → `float(row["volume"])`
  (rows come from the now-strict enriched_df). Leave the mixed `CANONICAL_FEATURES`
  comprehension at 2456 (30 non-OHLCV features legitimately default; the six are guaranteed
  present upstream).
- **`src/core/engine_runner.py:557-558,858`**, **`src/engines/zone_gate_engine.py:71`**,
  **`src/core/feature_store.py`**, **`src/features/crt_feature_builder.py:46-50`** — these
  read engine-input dicts already built by the strict paths above. Convert the six-field
  `.get(field, default)` to strict access for consistency; preserve the `close→price`
  cascade only if `price` is a legitimate alias (verify), otherwise make strict.

## Out of scope / explicitly preserved

- `compute_volume_features()` high-low proxy (forex zero-volume) — **kept**.
- `date`+`time` → `timestamp` merge from real columns — **kept** (not index synthesis).
- All non-OHLCV feature defaults (ema/atr/session/volume_ratio/30 canonical features).
- NaN-guard `np.nan` finalize-drop logic in `feature_pipeline.py` (rows dropped during
  warmup; not a column-level fallback).

## Tests

- **New `tests/data_ingestion/test_ohlcv_schema.py`** — table-driven: for each of the six
  columns, build a DataFrame/CSV omitting exactly that column and assert
  `require_ohlcv_columns` / each loader raises `ValueError` with the exact message
  (`...missing required columns: <name>`); plus a multi-missing case (`close, volume`) and
  a happy-path no-raise case. Covers self-review items 1-6.
- **`CandleLoader`** — new test: CSV without a volume column now raises (was silently 0.0).
- **`FeaturePipeline`** — update existing tests: a frame without `volume` now raises
  (previously auto-added). Add a test that a frame *with* an all-zero volume column still
  runs and triggers the proxy (forex compatibility preserved).
- **Migration cost (flagged):** existing test fixtures / inline CSVs that omit `volume`
  will now fail and must be updated to include the column. Grep `tests/` for `pd.read_csv`
  mocks and inline candle CSVs during impl (e.g. `tests/test_backtest_payload_integrity.py`
  already includes volume; others may not).
- Re-run the full suite per `docs/TESTING.md`; fix any fixture that relied on a synthesized
  column by adding real OHLCV values (never by re-introducing a default).

## Verification

1. `python -m pytest tests/data_ingestion/test_ohlcv_schema.py -v` — all six missing-column
   cases + multi-missing + happy path pass.
2. `python -m pytest tests/ -q` — full regression green (fixtures migrated, not defaults
   restored).
3. Manual: feed a CSV missing `volume` to `CandleLoader.stream()` and to
   `FeaturePipeline` → both raise `ValueError: ... missing required columns: volume`.
   Feed a forex CSV with an all-zero `volume` column → loads, proxy engages.
4. Determinism/replay check (`tests/runtime/test_replay_determinism.py`) still byte-identical
   on a complete dataset — strict enforcement must not alter valid-data behavior.

## Residual assumptions & known remaining fallbacks (to confirm during impl)

- Header aliasing (`tick_volume`, `vol`, `Open`, `datetime`, etc.) is retained as
  normalization — if the user wants *exact* lowercase names only, the alias maps must also
  be stripped (not assumed).
- The `close → price` alias in `engine_runner`/`zone_gate_engine` is verified before
  deciding strict-vs-alias.
- Non-OHLCV canonical-feature `0.0` defaults (e.g. `backtest_v2.py:2456`,
  `strategy_backtest.py:189`) remain by design (decision #3); call out if any of the six
  ever slips through one of those comprehensions.


================================================================================
SOURCE_FILE: docs/implementation_plan/task-independent-formula-majestic-wolf.md
SOURCE_BYTES: 2156
PART: 8/10 FILE 5/16
================================================================================

# Plan — Market Reality: Independent Formula Probes + Config Contract

## Context

We are moving `OHLCFeatureMap` toward a layered Market Reality architecture (Raw OHLCV → verified
canonical feature math → 38-feature observation surface → `MarketRealityHistoryBuffer` → configured
causal temporal derivations → configured Market Reality dimensions → `MarketRealitySnapshot` →
evidence consumers). The Market Reality layer must launch **observe-only, zero decision authority**.

This task is **evidence-gathering + a config contract only**. It produces three deliverables and
changes **no production code or behavior**. Per the governing contamination rule, every prior verdict
(CLOSED / PASS / PIT_CERTIFIED / finding conclusions / config comments / test pass counts) is treated
as *potentially contaminated* and must be independently reconstructed from current implementation and
fresh execution probes. ChatGPT is separately doing the SET A/B/C static classification; **this task
returns evidence to support/reject provisional classifications, not final A/B/C closure.**

## Deliverables (the ONLY files created)

1. `reports/analysis/market-reality-fresh-probes-2026-07-12.md` (Report 1 — WP1 + WP2)
2. `reports/analysis/market-reality-repository-search-2026-07-12.md` (Report 2 — WP3)
3. `configs/market_reality/market_reality_v1.yaml` (WP4 — config contract, no formulas)

Temp probe scripts go in the scratchpad (not committed) unless repo policy requires committed
reproducibility; exact commands + inline probe code are recorded in Report 1.

## Hard constraints (from the task)

- Do NOT modify production formulas, CRT, EngineRunner, Fusion, DecisionEngine, ExecutionPlanner,
  risk controls. Do NOT retrain models. Do NOT add canonical features. Do NOT implement the Market
  Reality runtime. Do NOT claim SET A/B/C closure.
- YAML must NOT contain executable formulas / Python expressions / hidden fallbacks / decision authority.
- Config must fail closed: `enabled: false`, `mode: observe_only`, all `authority.*: false`.

<!-- Exploration findings and detailed work-package steps appended below after agent results. -->


================================================================================
SOURCE_FILE: docs/implementation_plan/the-biggest-ambiguity-is-virtual-manatee.md
SOURCE_BYTES: 6578
PART: 8/10 FILE 6/16
================================================================================

# Plan: Restructure & correct `active_models.yaml` into a 3-truth-layer registry

## Context

You asked (of three possible deliverables) for **(1) a CRT state-truth table** — State → Detection
function → Config keys → Default thresholds → OHLCV inputs — and **(2) a machine-readable model
registry handoff** so Claude gets active-model truth without documentation hunting.

Investigation shows **both already exist** in [`active_models.yaml`](../../active_models.yaml) — the
file CLAUDE.md declares is "loaded first in every Claude session." So this is not a build. But the
file has **drifted from the code** and, more importantly, **conflates three distinct kinds of truth**
into single fields — the flaw you identified. The fix is not "intent OR runtime" but a schema that
keeps them as separate layers, mapping onto the doctrine the repo already runs (§4.0 Runtime Truth
Precedence: Tier-0 runtime ≠ findings/research ≠ history/architecture).

**Intended outcome:** every model entry becomes self-documenting across three truth layers, so future
corrections are *additive, not destructive* — no architectural intent is lost, and no session
inherits a false "this is live / this is proven" belief.

## Backward-compat: SAFE (verified this session)

`grep active_models` over the repo → **zero `.py` matches**; only CLAUDE.md (a read reference) and
this plan cite it. **No loader, no test asserts on the YAML shape** — the structural refactor breaks
nothing. This resolves the "downstream tools assume the schema" risk.

## Target schema (per your recommendation)

Every model/engine entry is refactored to four layers:

```yaml
<model>:
  intent:    # Layer 1 — Architectural truth: what it was DESIGNED to answer (preserve, never delete)
  runtime:   # Layer 2 — Runtime truth: what actually EXECUTES today (engine, features, file:line, active)
  evidence:  # Layer 3 — Research truth: what SURVIVES evidence (findings, validated:true/false)
  status:    # rollup: e.g. active | orphaned | experimental | dormant
```

## Ground truth established this session (Layer-2/3 source)

- CRT = **9 states** (`RANGE, SHADOW_PENDING, SWEEP, DISPLACEMENT, EXPANSION, EXPIRED, RETEST,
  EXECUTION, RESOLUTION`); `VALID_TRANSITIONS` [`crt_engine_v2.py:1073`](../../src/config_layer/crt_engine_v2.py#L1073), enum :63. No `CANCELLED`.
- Live Gaussian = `HeuristicGaussianEngine.compute`, **3 features** — `src/engines/heuristic_gaussian_engine.py:305`. `v4_mirrored` (38-dim NB, 242k, corr 0.2066) is **experimental, not wired**.
- ZoneGate = full **38-vector** contract, fail-open 0.5 — `src/engines/zone_gate_engine.py:163`.
- RR = candle-polarity index on close/high/low, `min_rr` unused — `src/engines/rr_engine.py:45`.
- S1–S10 exist ([`strategy_orchestrator.py`](../../src/strategies/strategy_orchestrator.py)) but are
  **orphaned** — feed dormant `FusionEngine.fuse_strategy_results()`, not the spine.
- 4-engine fusion gate is **OFF in backtests** (`BACKTEST_ENGINE_GATE=0`, F-037); live runs it.

## Corrections (all 8 approved; refined per your review)

| # | Item | Correction under the layered schema |
|---|---|---|
| D1 | CRT state count | `states: 10` → **9** (matches `state_list` + code). |
| D2 | CRT detection | Split into **`detection` states** (range/sweep/displacement/expansion/retest/expired) — each gets `file_line`, `config_keys`, `defaults`, `ohlcv_inputs` verified vs code — **and `lifecycle` states**: `shadow_pending: {type: lifecycle_state}`, `execution: {type: terminal_execution_state}`, `resolution: {type: post_trade_state}`. **No invented detection rules** for lifecycle states. |
| D3 | Gaussian | Split into `runtime:` (`HeuristicGaussianEngine`, 3 feats, `file: …:305`, `active: true`) and `trained_registry:` (`v4_mirrored: {status: experimental, active: false, samples 242000, correlation 0.2066}`). **Both truths preserved.** |
| D4 | ZoneGate | `runtime.inputs` → full 38-canonical-vector + `fail_open: 0.5`; `evidence` → F-041 registry TruthConflict + label caveat. |
| D5 | RR | `runtime` → `type: geometric_filter`, `learning: false`, `min_rr: retained_but_unused`, inputs `[close, high, low]`; `evidence` → F-038. |
| D6 | Strategies S1–S10 | Add `status: orphaned`, `wiring: sidecar`, `participates_in_live_spine: false` (dormant `fuse_strategy_results`). |
| D7 | engine_runner / philosophy | **Keep** the intent questions; add `authority: {level: architectural_intent, validated: false, findings: [F-019, F-037, F-040, …]}`. Add F-037 note that fusion gate is OFF in backtests / ON live. **Philosophy preserved, annotated — not deleted.** |
| D8 | header | Refresh `Last verified against`; add cross-link to [`model-intent-and-feature-ownership.md`](../../docs/topics/model-intent-and-feature-ownership.md); document the 4-layer schema convention inline at the top so future edits stay additive. |

All are `DOC_DRIFT` (code is authority); no finding is reversed and this is **not** `ACTIVE_VERSION`
config → within §6.2 auto-fix calibration. D3 (Gaussian split) is the most consequential and is now
non-destructive by construction (both truths retained).

## Files

- **Edit:** [`active_models.yaml`](../../active_models.yaml) — full refactor to the 4-layer schema + all corrections.
- **Read to verify (no edit):** `crt_engine_v2.py` (per-state config keys/defaults/`file:line`),
  `heuristic_gaussian_engine.py`, `zone_gate_engine.py`, `rr_engine.py`,
  `docs/topics/model-intent-and-feature-ownership.md` (already-verified engine truth).
- **No new doc** (§6.2 existing-doc-first): topic doc owns feature-ownership; `active_models.yaml`
  owns the machine-readable registry.

## Out of scope (per your deliverable selection)

- Intent-vs-demonstrated-edge matrix (Model → target → labels → edge → F-id) — not chosen.
- Deep per-strategy S1–S10 documentation — only the layered status flag is added.

## Verification

1. `python -c "import yaml,sys; yaml.safe_load(open('active_models.yaml')); print('ok')"` — parses.
2. Every `runtime.file`/`file_line` resolves to the cited symbol (grep each).
3. `crt.states` (9) == `len(crt.state_list)` == `len(VALID_TRANSITIONS)` in code.
4. Confirm no code depends on the shape: re-run `grep -r active_models --include=*.py` → still 0.
   `pytest -k "active_models or model_registry" -q` (expected: no tests target this file).
5. §7.4 SESSION LOG entry to `assistant_project.md` + dated Discussion entry to the model-intent
   topic doc (§6.4), recording the drift + schema decision (§6.2 audit-trail).


================================================================================
SOURCE_FILE: docs/implementation_plan/the-biggest-assumption-in-tender-lollipop.md
SOURCE_BYTES: 9557
PART: 8/10 FILE 7/16
================================================================================

# Gap Audit — MT5 Reality-Feedback Loop: Built vs. Missing

## Context

You pasted a long multi-model strategic analysis of Tradelatest's automation posture. Across all
three "solutions" it converges on a single recommendation: **"Finish the MT5 position-intelligence
and feedback system so every real trade becomes a reusable learning artifact"** / *"complete the
MT5 analytics feedback loop."* You asked (via the intent question) for a **gap audit vs. what's
already built — before any building.**

This document is that audit. It maps the target loop the analysis describes against the actual
code, verified by direct file reads (not just subagent report), and then states the *real* binding
constraint — which is **not** the one the analysis names.

**Target loop (from the analysis):**
`MT5 deals → position reconstruction → MFE/MAE → duration → session → regime → expectancy →
evidence report → finding → research update → paper validation → production approval`

---

## Headline Conclusion

The **measurement half** of the loop is built, test-gated, and mature (~90%). The **feedback half**
(reality-vs-forecast comparison → finding writeback → scheduler) is unbuilt. **But the top gap is
neither of those** — it is that **the only MT5 deals in existence are synthetic** (trade_generator
kernel-validation orders on an IC Markets demo). There is no edge-bearing, strategy-driven trade
flow. Layered on top: the spine is research-null (F-019…F-043, no validated directional edge).

So "close the loop" as literally stated would (a) have no real fuel, and (b) if fueled, mostly
re-confirm the existing null. The genuinely high-value, **edge-independent** work is different from
what the analysis ranks #1 — see *Recommended Sequencing*.

---

## What Is BUILT (verified)

### A. MT5 → PositionEpisode → FeatureRecord → InsightReport  (mt5_analytics/) — MATURE
| Stage | Module | Status |
|---|---|---|
| Read-only MT5 ingestion (deals/orders/positions/candles, UTC-normalized) | `mt5_analytics/core/mt5_adapter.py` | BUILT |
| Two ingestion paths: incremental daemon (30s poll) + explicit batch rebuild | `core/daemon.py`, `core/rebuild.py`, shared via `core/shared_pipeline.py` | BUILT; byte-parity test `tests/mt5_analytics/test_pipeline_parity.py` |
| Deal → `PositionEpisode` (VWAP entry/exit, net/gross/commission/swap, duration, volume-balance completion guard; handles pyramiding/partial/INOUT/reopen) | `engines/position_reconstructor.py`, schema `schemas/position_episode_v1_0.py` | BUILT (Phase 2a) |
| Episode → `FeatureRecord`: MFE/MAE in trade-R, RR, duration, **session** (LON/NY/ASIA/OVERLAP/OFF), **regime** (C/N/E/None/UNKNOWN) | `engines/features/*` | BUILT; purity guard forbids aggregate keys at feature layer |
| Read-only `InsightReport`: expectancy, win-rate, PF, Sharpe, recovery, exit-efficiency (capture ratio), **cost-drag** (commission/swap fraction of gross), attribution by session/regime/duration, Herfindahl `effective_n` | `analytics/insight_report.py` (imports only `analytics.metrics_oracle`) | BUILT (v0.6.0) |
| **Sufficiency gating** (min_n=30): underpowered buckets return `None`, make no claim | `analytics/insight_report.py` | BUILT (E-001 / F-019 discipline) |

### B. Execution telemetry (exec_telemetry/) — BUILT but capture is demo/manual only
| Stage | Module | Status |
|---|---|---|
| `ExecutionEvent` schema: requested vs filled price, signed slippage, send→fill latency, retcode/name, filling mode | `exec_telemetry/schemas/execution_event_v1.py` | BUILT (frozen v1.0) |
| Operational report: fill-rate, retcode histogram, adverse-slippage & latency distributions (sufficiency-gated); **operational-only, no PnL/expectancy by design** | `exec_telemetry/report.py` | BUILT |
| Capture path: `manual_tools/trade_generator.py --exec-log` → `runtime/exec_telemetry/<broker>/orders.jsonl` | producer | BUILT — **but requires live/demo order_send; runs only from trade_generator, not the live spine** |

### C. Reusable-but-unwired pieces (exist in main, corrected from subagent claims)
- `scripts/research/ingest_live_outcomes.py` — **EXISTS and is wired** into `src/engines/live_engine.py`
  + `scripts/training/phase5_calibration.py`. But it pairs `logs/live_alerts.jsonl` with a
  **hand-entered outcomes CSV** (`alert_id,pnl_rr_net,exit_reason,win`) and feeds the **Gaussian
  calibration** path — it is *not* a findings-writeback and *not* auto-fed from MT5 deals.
- `src/journal/trade_logger.py` — **EXISTS in main** (subagent wrongly said worktree-only); writes
  `logs/trade_journal.jsonl` from the alert/backtest lineage.
- `scripts/research/live_path_replay.py` — replays **backtest** trades through the live gate
  (ExecutionPlanner + UltronRiskGate); measure-only, writes to `results/live_path_replay/`. It is
  backtest-vs-backtest-gated, **not** live-vs-research.
- `src/research/qualification.py` (QualificationGate) + `src/research/measurement/forward_walk.py`
  — mature, but consume **backtest candles only**; no input contract for real executed outcomes.

---

## The Structural Gaps (verified MISSING)

1. **Two disjoint trade-truth lineages that never meet.**
   - *Python alert lineage*: `live_engine` → alert → (human places order) → manual
     `ingest_live_outcomes` / `trade_logger` → `logs/*.jsonl`, keyed by `alert_id`.
   - *MT5-deal lineage*: `mt5_analytics` daemon/rebuild → `PositionEpisode` (the "MT5 owns financial
     truth" doctrine), keyed by deal tickets.
   - **No join key or module bridges them.** An alert's forecast is never reconciled to the MT5
     episode that realized it.

2. **exec_telemetry ↔ mt5_analytics disconnect.** `src/live/` has **zero** references to
   exec_telemetry / insight_report / findings (grep-verified). Slippage/latency/fill-quality
   (execution reality) is never joined to realized expectancy (outcome reality) — so *"are costs /
   slippage dominating returns?"* cannot be answered end-to-end.

3. **InsightReport → Finding writeback: entirely MISSING.** `mt5_analytics` never touches
   `docs/current-findings.md` / `data/findings.jsonl`; insight is read-only + dashboard-only. (This
   is *partly intentional* — §6.5 "information, not authority"; findings are human-authored by
   design.)

4. **Reality-vs-forecast comparison: MISSING.** Nothing compares a live `InsightReport` (expectancy,
   capture ratio, cost fraction) against the backtest forecast that motivated the trade. Note: the
   "reality_gap +4.16R" in **F-025 is a backtest-internal ceiling** (`src/research/exit_grid.py`
   `ceilings()`: `mfe_capture − structural`), **not** a live-vs-research measurement.

5. **No scheduler.** No `.github/workflows`, cron, or Task-Scheduler entry runs the daemon,
   regenerates insights, or refreshes findings (grep-verified). Everything is human-initiated.

6. **No real trade fuel (the decisive gap).** Confirmed by you: only synthetic trade_generator demo
   deals exist. The loop's *input* — real strategy/alert-driven executed trades — does not yet exist.

---

## Recommended Sequencing (edge-independent first; NOT yet authorized — audit only)

The analysis ranks "build the writeback/feedback plumbing" as #1. Given synthetic-only fuel + a
null spine, that ordering wastes effort on plumbing with nothing true to carry. Sharper order:

- **Tier 0 — Generate real fuel (human-in-loop).** Start placing a small number of *actual*
  alert-driven demo trades (from `live_engine` alerts) so real `PositionEpisode`s exist. Without
  this, every downstream module measures noise. Cheapest, highest-leverage, edge-independent.
- **Tier 1 — exec_telemetry ↔ analytics join (edge-independent).** Wire `src/live/mt5_bridge.send_order`
  to emit `ExecutionEvent`s, and build the one missing bridge that answers *"is cost/slippage
  dominating?"* by joining execution reality to `InsightReport` outcomes. This is valuable **even on
  a null spine** — it tells you whether costs alone would kill any future edge (extends F-025/F-034).
- **Tier 2 — Reality-vs-forecast comparison.** A `reality_gap_audit` that reconciles the alert
  forecast (Python lineage) to the realized MT5 episode (MT5 lineage) via a shared join key — the
  actual "does live match research?" question.
- **Tier 3 — Finding writeback + scheduler.** Only after Tiers 0–2 produce trustworthy signal.
  Keep the human-authored-finding governance boundary (§6.5); automate the *evidence packet*, not
  the verdict.

## Verification (how to confirm this audit before/while building)

- Confirm no live wiring: `grep -rn "exec_telemetry\|insight_report" src/live src/runtime/live_engine_hook.py` → expect none.
- Confirm findings are hand-authored: `grep -rn "current-findings\|findings.jsonl" mt5_analytics/` → expect none.
- Confirm the measurement pipeline runs: `pytest tests/mt5_analytics tests/exec_telemetry -q` (should be green).
- Inspect real fuel state: list `runtime/mt5_analytics/**/episodes*.jsonl` and check whether any
  episode came from a non-`trade_generator` source.

## Scope / Doctrine notes
- This is an **audit deliverable**, not an implementation. No code is changed by this plan.
- Read-only per plan mode. If you approve, the natural next step is Tier 0/Tier 1 as a *separate*
  scoped task, under the normal §6 SESSION LOG + Authority-Ladder gates.
- Governed-doc impact: none registered here; if any gap above is later contested against a finding,
  it goes through the Documentation Drift Protocol, not a silent edit.


================================================================================
SOURCE_FILE: docs/implementation_plan/the-biggest-assumption-to-ticklish-forest.md
SOURCE_BYTES: 5022
PART: 8/10 FILE 8/16
================================================================================

# 20-Day Purge + Delayed Entry — Standalone Detection Script

## Context

The goal is **not** a research program. It's a small, standalone read-only script:

> Read an OHLCV file → mark where a 20-day high/low purge happened → flag whether an entry
> exists N hours (default 2h) later → write the annotated rows + a summary of setups.

Whether the rule *predicts* anything is a separate question, explicitly out of scope here. This
just **mechanically identifies the setups**.

### The one correctness trap to avoid

The proposed `df["High"].rolling(20)` treats each row as a day. But the data on disk is
**intraday** (verified: `data/*_M15.csv` = 15-min bars, `data/binance/*_H1.csv` = 1-hour bars,
`timestamp,open,high,low,close,volume`). On M15, `rolling(20)` is a **5-hour** window, not 20 days.
So the script **resamples to daily** to compute the 20-day level, then detects the purge on the
intraday bars. `.shift(1)` on the daily level excludes the current forming day (no lookahead).

Environment confirmed: `pandas 3.0.2` + `openpyxl` present → `.csv` and `.xlsx` both readable.

## Design — one file

**New:** `scripts/analysis/purge_delay_scan.py` (read-only; `scripts/analysis/` is the repo's
home for standalone analysis tools). No changes anywhere else. No spine/research/config wiring.

### Logic

1. **Load** OHLCV from a `--file` path (CSV or XLSX via pandas; auto-picks engine by extension).
   Parse `timestamp` to datetime, sort, set as index. Tolerate the repo's canonical header.
2. **Infer bar interval** from the median timestamp delta → `bar_minutes` (M15→15, H1→60).
   `delay_bars = round(delay_hours * 60 / bar_minutes)` (default `--delay-hours 2` → 8 on M15,
   2 on H1). Overridable with `--delay-bars`.
3. **Daily 20-day level** (no lookahead):
   ```python
   daily = df.resample("1D").agg(High="max", Low="min")   # calendar-day HH/LL
   daily["HH20"] = daily["High"].rolling(20).max().shift(1)  # prior 20 COMPLETED days
   daily["LL20"] = daily["Low"].rolling(20).min().shift(1)
   ```
   Broadcast `HH20`/`LL20` back onto the intraday index by forward-filling each day's level.
4. **Purge flags** on intraday bars:
   `higher_purge = high > HH20`, `lower_purge = low < LL20`.
   Optional `--min-penetration-atr` guard (default 0.0) to suppress micro-breaks, using a simple
   ATR (rolling true-range mean) — off by default so the base rule is exactly as specified.
   Debounce: collapse a run of consecutive purges of the same side into the **first** bar
   (`purge & ~purge.shift(1)`), so one purge = one event, not every bar price stays beyond.
5. **Delayed entry:** `entry_buy = lower_purge_event.shift(delay_bars)`,
   `entry_sell = higher_purge_event.shift(delay_bars)` (LOWER purge → BUY, HIGHER → SELL,
   mean-reversion as specified). Entry row carries the entry timestamp + entry price (that bar's
   open/close).
6. **Output:**
   - `--out <path.csv>`: the full frame annotated with `HH20, LL20, higher_purge, lower_purge,
     entry_buy, entry_sell` (default: alongside input, `<name>_purge_scan.csv`).
   - Console: a compact table of detected setups — `purge_time, purge_type, purge_price,
     level, entry_time, signal, entry_price` — plus counts. Windows-safe printing via
     `src/utils/console_safe.py` if non-ASCII sneaks in (defensive; likely unneeded).

### CLI
```
python scripts/analysis/purge_delay_scan.py --file data/EURUSD_M15.csv
python scripts/analysis/purge_delay_scan.py --file data/BNBUSDT_M15_2year.xlsx --delay-hours 2 --lookback-days 20
```
Args: `--file` (req), `--lookback-days` (20), `--delay-hours` (2) / `--delay-bars` (override),
`--min-penetration-atr` (0.0), `--out` (optional).

## Critical files
- New: `scripts/analysis/purge_delay_scan.py`.
- Reference only: `data/*_M15.csv` / `data/*.xlsx` (inputs), `src/utils/console_safe.py`
  (safe printing). Nothing else touched.

## Verification
1. Run on `data/EURUSD_M15.csv` → confirm it prints a setup table and writes the annotated CSV.
2. Spot-check one setup by hand: pick a printed `purge_time`, confirm that bar's high/low really
   breaks the printed HH20/LL20, and that `entry_time` is exactly `delay_bars` bars later.
3. **No-lookahead check:** confirm the level a bar is tested against uses only *prior* completed
   days — verify `HH20` at the first bar of day D equals the max of days D-20…D-1 (not including D).
4. Run once on an M15 file and once on `data/binance/BTCUSDT_H1.csv` → confirm `delay_bars`
   auto-resolves to 8 and 2 respectively for `--delay-hours 2`.
5. Sanity: total higher+lower purge events is small relative to row count (a 20-day extreme is
   rarely breached); if it's firing every bar, the debounce or `.shift(1)` is wrong.

## Notes / deferred
- This is mechanical detection only — **no** backtest, PnL, cost model, or statistical test.
- If you later want significance / OOS / multi-delay sweep / promotion, that's the heavier
  research-framework path (previously drafted) — kept out of scope by your direction.


================================================================================
SOURCE_FILE: docs/implementation_plan/the-biggest-assumption-you-zippy-parnas.md
SOURCE_BYTES: 9421
PART: 8/10 FILE 9/16
================================================================================

# Plan — Candle-State Edge Discovery: Non-Directional Transition Frontier (Program 4b)

## Context

The user proposed a "candle-state edge discovery engine" (state encoding × multi-timeframe ×
RR × holding period sweep) hunting a ≥70% win-rate edge, with a strong falsification-discipline
checklist. Reconnaissance (3 Explore agents) established three things that reshape the build:

1. **The discipline is already built.** The proposed `hypothesis_runner.py` / `walk_forward.py` /
   `monte_carlo.py` / `permutation_test.py` / `report_generator.py` map 1:1 onto existing,
   battle-tested modules: `HypothesisRunner` ([runner.py](src/research/runner.py)), `forward_walk()`
   with hard no-lookahead asserts ([forward_walk.py](src/research/measurement/forward_walk.py)),
   `EdgeAggregator` ([metrics.py](src/research/measurement/metrics.py)), and a 7-gate
   `QualificationGate` ([qualification.py](src/research/qualification.py)) that already enforces
   NET-of-cost expectancy, PF, beats-control, OOS retention, permutation p≤α, and Benjamini-Hochberg
   FDR. Rebuilding them violates the repo's "never reinvent existing patterns" rule.

2. **Most of the proposal is already falsified.** Program 1 is formally **KILLED**
   ([program-1-closure-2026-06-13.md](docs/analysis/program-1-closure-2026-06-13.md)). 7 of 10
   proposed hypotheses are already answered: directional next-bar candle prediction (F-019/020/021/
   025/027/035, crypto **and** FX), morphology clustering (F-023, all clusters win≈34%/mean_R≈0),
   continuation-after-sweep (F-026). Re-running these is named-forbidden "archaeology."

3. **Data reality:** M15-only on disk, 2yr, 12 symbols; resampler goes **upward only** (M15→H1/H4).
   No M5 → the M5-based proposed hypotheses cannot run without a fresh MT5 fetch.

**User mandate (confirmed):** NEW FRONTIER ONLY · M15-base only · expectancy-first gate with
WR/streak/rolling-10 as reporting-only · reuse the kernel, build only the missing pieces.

**Intended outcome:** a small additive layer that tests the *genuinely-untested, reopen-legal*
frontier — **multi-timeframe state conjunction (M15∧H1∧H4)** and **compression→expansion
TRANSITION forecasting (non-directional targets)** — pre-registered per the Epistemic Integrity
ritual, run through the unchanged qualification machinery. Likely high-knowledge-ROI outcome:
Stage-1 information may exist while Stage-2 economic consumption fails (consistent with F-030);
that null is a valid, valuable result, not a failure of the build.

---

## Architecture: two-stage gate (respects the §6.5 Authority Ladder)

Non-directional forecasts (predict vol/range expansion) are **Authority-Ladder Level 1
(information)**, not Level 2 (economic). They cannot flow directly through the trade-outcome
QualificationGate. So:

- **Stage 1 — Information gate (non-directional).** Does a candle-state conjunction / compression
  state carry predictive information about *forward* volatility/range expansion? Measured with
  mutual information + permutation, reusing
  [process_diagnostics.py](src/research/process_diagnostics.py) (`mutual_information`,
  `direction_conditional_entropy`) and
  [conditional_entropy_grid.py](src/research/conditional_entropy_grid.py)
  (`partition_stat`, `permutation_pvalue`, `candidate_cells`). Authority: **research/docs only.**
- **Stage 2 — Economic gate (only for Stage-1 survivors).** Convert a surviving conjunction into a
  *tradeable* Hypothesis (a compression→expansion **breakout** construction — enter the first range
  break after a predicted-expansion compression) and run it through the **unchanged**
  `HypothesisRunner` + `QualificationGate` (intrabar_fixed exit, 12bps). Promotion is
  expectancy-first; WR is reported, never promotes alone.

**No-lookahead** is automatic: the multi-TF state is computed inside `detect()` from the M15
`window` (past+current only); `resample()` drops the in-progress HTF bucket so only *closed* H1/H4
candles are ever visible.

---

## Files to create (all additive; the runner/gate/forward_walk are NOT modified)

New subpackage `src/research/candle_state/`:

- `__init__.py`
- `encoder.py` — **`CandleStateEncoder`**: pure fn, candle list → discrete state label
  (BULL_STRONG/BULL_WEAK/BEAR_STRONG/BEAR_WEAK/DOJI/EXPANSION/COMPRESSION/INSIDE_BAR/OUTSIDE_BAR)
  + continuous features (body%, upper/lower wick%, volume z-score, ATR ratio, range-expansion
  ratio). Reuses `bar.body_ratio`/`is_bullish` and [indicators.py](src/research/indicators.py)
  (`atr`, `sma`). No new feature registry — keep it local and pure.
- `mtf_conjunction.py` — **`MultiTFConjunctionBuilder`**: M15 window → resample to H1/H4 via
  [resample.py](src/research/resample.py) → encode each TF's last *closed* candle → conjunction key
  (e.g. `"M15=COMPRESSION|H1=UP|H4=BULL"`). Pure, no-lookahead.
- `transition_target.py` — non-directional **forward** target labelers: vol-expansion
  (`ATR_{t+1..t+k}/ATR_t > θ`), range-expansion, regime-transition flag. Used by Stage 1 only.
- `reporting.py` — additive reporting-only helpers consuming `list[Outcome]`:
  `streak_metrics` (max losing streak), `rolling_window_metrics(window=10)`, WR rollup.
  **Never** feeds the gate.

New hypothesis (Stage 2), registered into the **existing** `HYPOTHESIS_REGISTRY`:

- `src/research/hypotheses/compression_breakout.py` — the tradeable transition consumer.
  This *is* the user's "TransitionHypothesisRegistry" realized via the existing
  `register_hypothesis()` plugin (no parallel registry — convention).

Drivers (thin CLI wrappers, business logic in modules):

- `scripts/research/transition_information.py` — Stage 1 information gate.
- `scripts/research/qualify_transitions.py` — Stage 2 economic gate (mirrors
  [qualify_majors.py](scripts/research/qualify_majors.py)).
- `scripts/research/candle_state_report.py` — consolidated evidence table incl. **failures**
  (the user's FULL_RESULTS.csv / EDGE_SUMMARY.md, written under `results/research/candle_state/`).

Governance / docs (per Epistemic Integrity ritual, written BEFORE running):

- `docs/research/preregistration-program-4b.md` — the 6-question pre-registration check
  (artifact, INSUFFICIENT-explanation, sign-noise, statistical-vs-economic, parent-vs-children,
  raw-counts) for each transition hypothesis. **Mandatory before any finding is registered.**
- On results: add **F-040** to [current-findings.md](docs/current-findings.md) + the §6.2
  Repository Truths Index in CLAUDE.md (same turn), plus a memory file.

Tests `tests/research/`:

- `test_candle_state_encoder.py` — vocabulary correctness + determinism + pure (no lookahead).
- `test_mtf_conjunction.py` — resample-causality (only closed HTF bars visible), determinism.
- `test_transition_information.py` — MI/permutation kernel wiring + seeded determinism.
- `test_compression_breakout.py` — Signal emission + no-lookahead (entry_index guard).
- `test_reporting_metrics.py` — streak/rolling-10 correctness; assert reporting never alters verdict.

---

## Scope guards (doctrine compliance)

- **NEW frontier only.** Only the compression→expansion transition + MTF conjunction (non-directional
  targets) are promotion candidates. No SL/TP grids, entropy partitions, session sweeps, or
  directional candle-pattern searches with tweaked thresholds.
- **Clean-room replication = documentation only, ~zero new code.** A single labeled section in the
  report re-runs the existing toy pool via the *existing* `qualify_majors.py` to document
  reproduction of the F-019 null — explicitly NON-PROMOTABLE.
- **M15-base only.** M15 native + H1/H4 derived. No synthetic M5; M5 research requires an explicit
  MT5 fetch + new on-disk corpus (out of scope here).
- **Expectancy-first.** Existing 7-gate `QualificationGate` is the sole promote authority
  (intrabar_fixed + 12bps, matching every prior falsification for comparability). WR≥70% /
  max-streak≤3 / rolling-10 are reported alongside, never gating.

---

## Verification

1. `pytest tests/research/ -q` — new tests green; run twice to confirm byte-identical artifacts
   (determinism). Confirm reporting-metric test proves verdict-invariance.
2. **No-lookahead proof:** unit test feeds a window and asserts the MTF builder never sees an
   HTF bar overlapping the current M15 bar; `forward_walk`'s existing index assert covers Stage 2.
3. **Stage 1 run:** `python scripts/research/transition_information.py` on crypto majors → MI +
   permutation p per conjunction; record which (if any) clear the floor.
4. **Stage 2 run (only Stage-1 survivors):** `python scripts/research/qualify_transitions.py` →
   per-instrument + pooled M4 verdict.
5. `python scripts/research/candle_state_report.py` → consolidated CSV/MD incl. all failures.
6. Pre-register (doc) BEFORE step 3; on results, file F-040 + Repository Truths Index + memory,
   same turn. Append the §6 SESSION LOG entry.

## Most likely result (set expectation)

Stage-1 information PLAUSIBLE (vol has memory: H_atr=0.885, F-030), Stage-2 economic PASS
UNLIKELY (F-030: vol predictable but non-consumable in spot long/short; F-025: bottleneck is entry
information). A Stage-1-PASS / Stage-2-FAIL outcome is the high-knowledge-ROI result and closes the
last reopen-legal directional-adjacent frontier cleanly — it is the expected, valuable deliverable,
not a failure.


================================================================================
SOURCE_FILE: docs/implementation_plan/the-biggest-risk-you-rustling-rain.md
SOURCE_BYTES: 6368
PART: 8/10 FILE 10/16
================================================================================

# Plan — Experiment-2A: Cross-Asset Lead-Lag (falsification-first)

## Context

The Experiment-1 arc exhaustively falsified **BNB → BNB** (own-series price action: aggregate,
conditional, opportunity — all indistinguishable from random under realistic execution). The
only **genuinely exogenous** information available in the current data (OHLCV M15 only; no
orderflow/news/macro on disk) is **cross-asset**: do BTC/ETH/SOL moves predict BNB? That
hypothesis family was **never attacked** by Experiment-1.

**Posture (confirmed): falsification-first, NOT strategy-building.** Build a small cross-asset
family + run it through the **existing, unchanged** machinery (M4 QualificationGate +
`always_long`/`random_uniform` controls + permutation + BH + the conditional-edge audit). The
deliverable is a **verdict** — most likely another `PROMOTE: none` ("cross-asset OHLCV is
insufficient"), which is a scientific success — exactly like Phase B.

**Universe:** `BNBUSDT` (target) + `BTCUSDT`, `ETHUSDT`, `SOLUSDT` (peers) — all already in
`data/`, all crypto-clean (24/7, ~70k M15 bars, same span; L2/L3 APPROVE).

**Dominant NEW risk = synchronization look-ahead leak.** Every failure so far was "no edge";
the cross-asset inverse risk is *manufacturing a fake edge* by letting `detect()` peek at a peer
bar dated after the decision. Two defenses, baked in: a strict `ts ≤ t` peer guard, and a
**peer-shuffle control** (run every hypothesis with peer series misaligned — any "edge" that
survives the shuffle is a leak/bug, not signal).

## Change 1 — Multi-symbol synchronized-context substrate (the only real new capability)

New `src/research/multi_symbol.py` — `PeerContext`:
- Loads each peer via `CandleLoader`; stores per peer a sorted timestamp array + bars.
- `peer_windows(t, window) -> {sym: [bars with ts ≤ t][-window:]}` via bisect. **Strict
  no-lookahead:** only peer bars with `timestamp ≤ t` (contemporaneous M15 close at `t` is
  allowed — both instruments close simultaneously and the prediction target is BNB `t+1…`;
  forward_walk already reads only BNB bars after `t`). Assert no peer bar with `ts > t` is ever
  returned.
- Injected into the existing `detect(window, features, ctx)` via `ctx["peers"]` — **contract
  unchanged**; the existing single-instrument hypotheses ignore `ctx["peers"]` (backward compatible).

Runner: extend `HypothesisRunner.collect`/`run_instrument` with an optional `PeerContext` so the
**target** (BNB) drives the bar loop and each bar gets its peer context. The target is what is
forward-walked / aggregated / qualified; controls run on the **same** target (apples-to-apples).
Config: additive `cross_asset` section in `configs/research/research_config.json` +
`ResearchConfig` (`target`, `peers`, `peer_window`) → in the provenance hash.

## Change 2 — Cross-asset probe hypotheses (`src/research/hypotheses/cross_asset.py`)

Deliberately simple, **3 distinct mechanisms** (NOT 50 — every added hypothesis widens the BH
universe; keep researcher-degrees-of-freedom minimal). Each declares `economic_rationale`, reads
`ctx["peers"]`, emits a BNB `Signal`, flows through identical measurement/qualification:
- **`xa_leader_momentum`** — BTC's last-k-bar return sign → BNB direction (leader carry: BTC
  leads, BNB follows).
- **`xa_relative_strength`** — basket (BTC/ETH/SOL) strong while BNB lags → long BNB (catch-up).
- **`xa_corr_breakdown`** — BNB return decouples from the basket (opposite sign) → fade BNB back
  toward the basket (correlation-reversion).

Fixed, sensible parameters — **no parameter search, no ATR/stop/exit tuning** (SL/TP inherit the
config defaults via `apply_signal_defaults`, identical to Experiment-1).

## Change 3 — Run through the EXISTING machinery (no new gates, no weakening)

1. `qualify` (M4) on the 3 hypotheses with the BNB `always_long`/`random_uniform` controls — the
   beats-winning-control gate compares cross-asset vs BNB random baseline; BH across the family.
2. **Peer-shuffle leakage control:** re-run with peer series time-shuffled; confirm any apparent
   signal collapses to the random baseline (proves no synchronization leak).
3. Conditional-edge / adversarial audit only **if** something clears M4 (don't pre-fish).

**Explicitly forbidden** (per the arc's lessons): parameter search · ATR/stop/target redesign ·
hypothesis stuffing · weakening M4 · low-power metrics (opportunity profile) · zero-baseline
comparisons · promotion.

## Tests (`tests/research/`)
- `PeerContext`: never returns a peer bar with `ts > t` (no-lookahead); correct window slicing
  with peer gaps/misalignment; bisect alignment correctness.
- Backward-compat: existing single-instrument hypotheses produce **byte-identical** edge_report
  with `ctx["peers"]` present-but-ignored (determinism invariant holds).
- One cross-asset hypothesis fires deterministically on a synthetic 2-instrument fixture.
- **Leakage test:** a fixture with a planted future-peer value must NOT change the signal (guard
  blocks `ts > t`).

## Verification (end-to-end)
1. `python -m pytest tests/research -q` — green incl. no-lookahead + backward-compat.
2. `python -m research.cli qualify` (cross-asset mode) → deterministic verdict; **then** the
   peer-shuffle control → signal must vanish.
3. Isolation lint: no `core.engine_runner`/`promotion_manager`/`config_validator` imports.
4. Deliverable `docs/analysis/cross-asset-experiment-2-2026-06-10.md`: hypotheses, universe,
   controls, M4 verdict, peer-shuffle result, (conditional/adversarial only if a survivor),
   **final verdict — cross-asset OHLCV: useful / useless.**

## Out of scope (hard)
No orderflow/news/macro/funding (no data). No strategy delivery — a verdict only. Governing
`intrabar_fixed`, qualification/M4/promotion, and the **production** config are untouched
(`cross_asset` is additive to the *research* config). A survivor is a PRE-REGISTERED OOS
CANDIDATE, never an edge; promotion still requires M4.5/M4.7 (unbuilt). Most likely outcome:
`PROMOTE: none` → cross-asset OHLCV insufficient → burden moves to data acquisition. That is a
successful Experiment-2.

## Governance / session-log
Append `📝 SESSION LOG ENTRY` per §6 at implementation. Isolated, measure-only research; no
live-spine/config-hash/promotion impact; determinism is a hard invariant.


================================================================================
SOURCE_FILE: docs/implementation_plan/the-biggest-risk-you-spicy-quilt.md
SOURCE_BYTES: 6812
PART: 8/10 FILE 11/16
================================================================================

# Review — Program E-001 (Epistemic Integrity Sweep) + Remediation

## Context

A multi-LLM session built Program E-001 to formalize the invariant *"no layer may possess
greater certainty than the layer beneath it"* after the F-030 incident (a `regime_conditioning`
rollup printed `REGIME_HARMFUL` from all-`INSUFFICIENT` cells). The user asked for a review of
the delivered changes. This file records what was verified, the gaps found, and a remediation
plan. **The headline gap is an irony: the invariant *tests* themselves partly instantiate the
very failure classes (E-001A overclaim, E-001F decorative wiring) the program was built to
catch.** Per the program's own ritual: *"Caught me overclaiming; I owe you a correction."*

## What is genuinely solid (verified)

- **Charter** [`docs/governance/EPISTEMIC_INTEGRITY.md`](docs/governance/EPISTEMIC_INTEGRITY.md) — defines all six failure classes, the invariant, the mandatory phrase, the 6-question ritual. Well structured.
- **The real fix is real.** [`src/research/regime_conditioning.py:324`](src/research/regime_conditioning.py) — the `all_insufficient` guard (line 327-328) correctly precedes the `n_harmful > n_beneficial` emission (line 331). The F-030 bug is genuinely closed in code.
- **F-031 registered** ([`docs/current-findings.md:410`](docs/current-findings.md)) with evidence links that resolve; F-030 documents the corrected case.
- **Evidence-link test is substantive and binds** — its header/field regexes (`### F-NNN`, `- Confidence:`, `- Evidence:`) match the real findings format, so it actually parses 30 findings and checks each Certain/Likely finding cites a resolvable file. Not vacuous.
- **Tests run as claimed:** `15 passed, 1 skipped`.
- **CLAUDE.md §6.2** carries the pre-registration ritual + mandatory phrase (wired).

## Gaps found (the corrections owed)

1. **E-001A / E-001E tests are substring-grep, not behavioral** ([`tests/governance/test_epistemic_invariants.py:124`](tests/governance/test_epistemic_invariants.py), `:178`). They assert `"all_insufficient" in code` and string-position ordering — they never construct an all-`INSUFFICIENT` population and assert the verdict is `REGIME_INSUFFICIENT`. Consequences: a correctness-preserving rename/refactor *fails* (false positive); logically-broken code that keeps the strings *passes* (false negative). The charter/summary claim "the F-030 bug pattern is now a test failure" is **stronger than the grep supports** → itself an E-001A overclaim.

2. **E-001B test cannot fail** (`:375`) — it `pytest.skip`s when it finds concerning lines, otherwise passes. Same for `test_possible_findings_can_be_artifact_or_explanation` (`:243`). A test that never enforces is **decorative wiring (E-001F)** by the program's own definition, yet the charter §6 table lists "Test asserts."

3. **Charter status drift (DOC_DRIFT).** §9 still reads *"Pending sweep results from Phases 2–3"* and §10 marks phases 2a–4 as ⬜ PENDING, contradicting the COMPLETE claim. The charter contradicts itself.

4. **Evidence-link checks existence only, not support.** `_resolve_evidence` (`:84`) verifies `src/foo.py` exists but ignores the `:line` and never checks the file mentions the claim. Crude E-001C guard sold as "resolves to a real artifact."

5. **Second rollup layer unguarded** (minor). `scope_verdict` ([`regime_conditioning.py:355`](src/research/regime_conditioning.py)) can surface `REGIME_HARMFUL` at scope level from one harmful consumer among insufficients. Deliberate cross-consumer precedence, but it's an undocumented exception to the stated invariant and outside test coverage.

## Remediation plan

**Goal:** make Track B (the tests) actually enforce the invariant, and remove the program's own
overclaim/decorative-wiring instances. Track A (governance docs) needs only the drift fix.

### R1 — Make E-001A/E-001E behavioral (the core fix)
- Refactor the verdict-decision block ([`regime_conditioning.py:324-334`](src/research/regime_conditioning.py)) into a pure helper, e.g. `_consumer_verdict(cells_out, all_insufficient, redundant, n_harmful, n_beneficial, has_exploitable) -> str`. The surrounding loop calls it with the same args — **byte-identical behavior**, no logic change (verify by running `tests/test_regime_conditioning.py`).
- Replace the grep tests with behavioral ones: call `_consumer_verdict` with a synthetic all-`INSUFFICIENT` cell set and assert the result is `REGIME_INSUFFICIENT` (and that a single-harmful-among-insufficient set is *not* `REGIME_HARMFUL`). This binds the *behavior*, surviving refactors.
- Note `regime_conditioning.py` is a research harness — refactoring its verdict block is inside scope (the charter's "do not touch" list is spine / `qualification.py` / prod configs, not this file).

### R2 — Stop the decorative tests from masquerading as enforcement
Pick one per the user's call (see question): either (a) turn E-001B + the possible-findings test into real asserts (fail on violation), or (b) relabel them honestly as advisory and correct the charter §6 table so it no longer claims "Test asserts" for non-enforcing rows.

### R3 — Fix charter status drift
Update [`EPISTEMIC_INTEGRITY.md`](docs/governance/EPISTEMIC_INTEGRITY.md) §9 (record the sweep result) and §10 (mark 2a–4 ✅ DONE). Append the scope_verdict precedence (gap 5) as an explicit, documented exception to the invariant.

### R4 (optional) — Strengthen the evidence-link guard
Extend `_resolve_evidence` to also assert the cited file is non-empty and, where a `:line` is given, that the line exists. Full content-supports-claim verification is out of scope (needs semantics).

### R5 — Apply the program's own ritual
Register the meta-correction: a one-line note on F-031 (or a SESSION LOG entry) recording that the E-001 *test suite* itself was found to overclaim and was corrected to behavioral enforcement — the mandatory phrase applies, and a pre-registration correction is governance succeeding.

## Verification
- `python -m pytest tests/governance/test_epistemic_invariants.py tests/test_regime_conditioning.py tests/test_current_findings.py -q` → all green.
- Prove R1 inert: `tests/test_regime_conditioning.py` (15) still passes byte-identically after the helper extraction.
- Confirm the new behavioral test *fails* if the `all_insufficient` guard is removed (deliberately break it locally, see red, restore) — the true test of "the bug is now a test failure."
- Per CLAUDE.md §6: append the SESSION LOG entry.

## Hard boundaries (unchanged from the original program)
No edits to the CRT spine (`crt_engine_v2.py`), the M4 gate (`qualification.py`), or production
configs. R1's refactor is confined to the research harness's presentation block and is proven
inert by the existing determinism test.


================================================================================
SOURCE_FILE: docs/implementation_plan/the-biggest-weakness-i-deep-alpaca.md
SOURCE_BYTES: 16204
PART: 8/10 FILE 12/16
================================================================================

# Forensic Verdict — Feature-Math WHAT Layer, Gate 1 / Gate 2, GD-001…GD-010

> **This is a forensic verdict, not a design proposal.** It answers the ten audit axes and the
> closing questions: what is proven, what is broken, what is unproven, which findings are material,
> whether Gate 1 is complete, whether Gate 2 can be closed, whether GD-001/GD-002 should proceed to
> remediation, and the single highest-leverage next action.
>
> Every claim below was verified by reading source (file:line), not by trusting agent summaries,
> grep, or call graphs. Where I could not verify without executing code, I say so and mark it a
> required verification step (plan mode is read-only).

---

## Context

F-047 declared the market ontology "AUTHORITATIVE + ENFORCED," pinned 10 pre-existing feature-math
divergences (GD-001…GD-010), and Gate-2 Step 7c reported "0 decision flips / 39,456 score-gated →
DECISION-INERT." The audit's thesis: the project may have manufactured the *appearance* of
mathematical trustworthiness without guaranteeing research→backtest→live-decision consistency. I
traced the causal chain OHLCV → ontology → registry → candle_math/derived_math → live-hook/pipeline →
CRT/engines → fusion/decision, and stress-tested each checkpoint.

---

## Verdict summary

| # | Axis | Verdict |
|---|---|---|
| 1 | What was built vs plan | **Mostly proven.** Artifacts exist and match the plan. One headline overclaim (7c "DECISION-INERT"). |
| 2 | WHAT layer genuinely authoritative | **Partially.** Registry is real, non-`eval`'d, single-source per FM-ID. But "authoritative for *all* feature math" is stronger than the enforcement supports (axis 3). |
| 3 | Enforcement bypassable | **BROKEN (by design gaps).** Material false-negative classes confirmed from source. |
| 4 | Grandfather pins durable & truthful | **Proven.** Set-based ratchet is sound; manifest empty ⇒ CURRENT=ORIGINAL, consistent. One reproducibility caveat (Python-version-coupled fingerprints). |
| 5 | Adjudication verdicts source-correct | **Proven** for the sites I traced (GD-001/002/003/004/005/010). |
| 6 | Semantic classifications correct | **Proven.** `disp_strength`/wick/range collisions are genuine name collisions (distinct quantities), not formula bugs. Rename is the right remedy. |
| 7 | Gate 2 measured what it claims (value/score) | **Proven for value & score drift.** Injection reaches the real score boundary (`engine_runner.py:654`). |
| 8 | Step 7c state isolation causally valid | **Proven.** `deepcopy`-per-candle B-vs-B control genuinely isolates the adaptive controllers. |
| 9 | "Decision flip" is the real final decision | **Proven it captures final EXECUTE/REJECT — but NULL-BY-CONSTRUCTION.** See broken finding below. |
| 10 | Over-engineered vs edge discovery | **Yes, past this point.** High ROI already realized; further enforcement build-out is optimization theater. |

---

## The single most important finding (BROKEN)

**Gate-2 Step 7c's "0 decision flips → DECISION-INERT" is null-by-construction and cannot close Gate 2.**

- `reports/feature-math-decision-flip-probe.json`: `approve_current_A = 0`, `approve_canonical_B = 0`
  across all 70,002 candles. **Zero candles executed in either branch.**
- A flip requires `apA != apB` (`feature_math_decision_flip_probe.py:199`). With both approval counts
  identically 0, `flips = 0` is a **mathematical identity, independent of `body_ratio`**. The
  divergence could be arbitrarily large and the probe would still report 0 flips.
- The 39,456 "score-gated" denominator is **entirely rejects** (`reasonB_histogram`: `low_score`
  39,418, `invalid_session:asia` 23,346, `low_rr` 6,918, `ultron_gate:*` 320). None are executes.
- **Decisive corroboration:** the real research spine executes BNBUSDT **~11 times gate-ON / ~13
  gate-OFF** (per prior findings/memory). This harness executes **0 times**. The probe therefore does
  **not** reproduce the only candles where a score shift could change a trade — the ~11–13 live
  setups. It measures body_ratio sensitivity at a boundary that never fires an approval.
- The 7b score-drift probe already proved `body_ratio` moves the **CRT score ~96.7%** and the
  live value differs on 97% of bars, `>1` on 46%. So the value is score-material; 7c was supposed to
  show whether that reaches decisions. **It did not answer the question — it showed the harness
  reaches no decision.**

The adjudication doc's own caveat concedes this (`docs/analysis/feature-math-divergence-adjudication.md:148-152`:
*"does NOT reproduce the ~13 CRT-state-gated live setups where run() actually executes; a definitive
live-setup flip rate would need the CRT-spine harness"*). **But the top-line F-047 conclusion and the
memory entry both assert "DECISION-INERT" without that qualifier in the headline** — an E-001-class
overclaim: the honest statement is *"decision-flip UNPROVEN at the execution margin; 0 flips observed
in an all-candle harness that produced 0 executions."*

> Caught the system overclaiming: "DECISION-INERT" is doing more work than the data supports. The
> data supports "inert within a harness that approves nothing," which is materially weaker.

---

## What is PROVEN

- **Registry is real and non-`eval`'d.** `FORMULA_REGISTRY = {**PRIMITIVES, **DERIVED}` is a static
  name→callable dict (`src/features/registry/__init__.py:26`); dispatch is by `inspect.signature`
  matching, YAML is `safe_load`'d, no `eval`/`exec` anywhere. Canonical math is single-sourced in
  `src/features/candle_math.py` and `src/features/derived_math.py`.
- **Canonical `body_ratio` is coherent; the live-hook one is the bug.** `candle_math.body_ratio =
  body_size / candle_range` bounded [0,1] (`:57-58`), the only definition the `body_ratio >= 0.70`
  gate is coherent against. The divergent site `live_engine_hook.py:360-362` computes
  `body_ratio = body_size / wick_size` where `wick_size = total_wick` — **unbounded, incoherent with
  the gate.** This is a genuine correctness defect, not a stylistic one.
- **Injected value reaches the real score boundary.** `engine_runner.py:654` consumes `input_data`
  directly into `crt_compute`; gaussian/RR likewise. No recompute-override. The probe's injection is
  faithful *at the scoring level*.
- **State isolation is sound.** `deepcopy(runner_ref)` per candle isolates `AcceptanceController`/
  `ConvergenceController`/`DecisionEngine` dynamic-threshold state; the zone bypass is a **class-level**
  monkeypatch specifically to preserve deepcopy isolation (`:98-122`). No `__deepcopy__`/lock/global
  defeats it. The B-vs-B control is a valid marginal counterfactual.
- **Grandfather ratchet is a true set invariant.** `test_grandfather_set_monotonic` enforces
  `CURRENT ∪ RETIRED == ORIGINAL_BASELINE` and `CURRENT ∩ RETIRED == ∅` — not a count cap.
  `durable_key = sha256(rel, qualname, target, kind, ast.dump(rhs))[:16]` is content- and
  scope-sensitive (proven by `test_durable_key_is_content_and_scope_sensitive`). Manifest is empty
  ⇒ CURRENT = all 10 = ORIGINAL. Consistent.
- **Semantic classifications hold.** `disp_strength` collisions (GD-004 `scoring_engine` = `move/atr`;
  GD-005 `crt_engine` = `wick/atr`) are distinct quantities sharing a name with the FM-020 feature
  (`body/(atr*close)`, the pipeline column). These are name collisions → **rename** is behavior-neutral
  and correct. GD-003 (`body_size`) and GD-010 (`candle_range`) are byte-identical duplicates.

## What is BROKEN

- **Gate-2 7c null-by-construction** (above) — the load-bearing defect.
- **Enforcement lint has material false-negative classes** (`feature_math_lint.py`, confirmed from
  source `:319-325`, `:363-378`). New feature-math escapes the lint when written as:
  1. **DataFrame column assignment** `df["body_ratio"] = high - low` — Subscript target, never yielded
     by `_target_names`. (This is the *dominant* form in a pandas feature pipeline.)
  2. **Attribute assignment** `self.body_ratio = ...` — Attribute target, never yielded.
  3. **Augmented / walrus** `body_ratio += ...` / `body_ratio := ...` — only `Assign`/`AnnAssign`
     inspected.
  4. **Re-derivation into a non-registered variable name** `_br = body / tw` (then consumed) — filtered
     out at `:376` (`canon not in registered`).
  5. **Anything outside 5 dirs** (`research/`, `strategies/`, `analytics/`, `scripts/`, `tests/` all
     exempt) — the research pipeline that produced F-019…F-042 is **not** lint-covered.
  6. **A helper whose leaf name collides with a registered feature** (`_call_is_registry` whitelists
     any call whose leaf is a registered name) → a rogue local `def body_ratio(...)` is classed OK.
  → "The WHAT layer is ENFORCED" is true only for `Name`-target assignments in 5 dirs. The strong
  reading ("all feature math is governed") is **not supported**.

## What is UNPROVEN

- **Whether canonicalizing GD-001/GD-002 changes any real live decision.** The only artifact that
  claims to answer this is null-by-construction. Genuinely open.
- **Exhaustiveness of the 10-site census.** Gate 1 enumerated 10 sites *of the form the lint can see*.
  Given the false-negative classes above (esp. DataFrame writes and the exempt `research/` tree),
  there may be re-derivations the census never surfaced. "10 divergences total" is **not proven** —
  "10 divergences of the scannable form" is.
- **Live-path fidelity.** The probe bypasses the zone gate (matching *backtest*, not live) and injects
  a `trend_bias`-signed direction rather than the real CRT-determined direction. GD-001/002 live in
  the **live** hook (F-010-unverified, F-037: backtests bypass it). So even a corrected 7c measures a
  backtest-configured proxy of a live-only divergence.

---

## Answers to the closing questions

**Is Gate 1 complete?** — **Substantially, with one qualifier.** Classification and source-tracing of
the 10 sites are correct and durable. But Gate 1's *completeness* is bounded by the census
instrument, which has the false-negative classes above. Gate 1 is complete **for the scanned surface**;
it is **not proven exhaustive** over all repo feature-math. Downgrade the "authoritative for all
feature math" language to "authoritative for the governed FM-IDs; enforced against Name-target
re-derivation in 5 dirs."

**Can Gate 2 be closed?** — **No, not on the current artifact.** The 7c result is arithmetically
forced (0/0 approvals). Gate 2 closes only after the decision-flip is measured at candles where the
system actually executes.

**Should GD-001/GD-002 proceed to remediation?** — **Yes — it is a real correctness fix (the live
value is the incoherent one) — but the PATH depends on the missing test.** Remediation is *not*
byte-identical: it swaps the live value from `body/total_wick` to the canonical `body/candle_range`
(≈97% of bars change). So:
- If the decisive flip test (below) shows **0 flips at the real executions** → remediate freely
  (correct formula, behavior-neutral). Hash-neutral, no promotion gate.
- If it shows **any flip** → the fix **changes live trade decisions** → must go through the promotion
  gate with a `ValidationReport`, per §6.5 Authority Ladder and §4.0.
- Do **not** ship it blind on the strength of the null-by-construction 7c.

**Which findings are material?** — GD-001/GD-002 (the only non-equivalent, decision-reachable formula
divergence) and GD-004/GD-005 (decision-reachable name collisions, one a HARD REJECT). GD-003/010 are
immaterial (byte-identical). GD-006/007 are diagnostic-unreachable. GD-008/009 are dead code.

**Is the project over-engineered relative to edge discovery?** — **Yes, from here on.** The apparatus'
highest ROI is *already banked*: it demonstrated the features are not contaminated, which
**re-validates the F-019…F-042 falsification sweep** rather than overturning it (a null with a clear
conclusion = high knowledge-ROI, §6.1). But the binding constraint is repeatedly established as the
*execution model / entry-information null* (F-001, F-025, F-040), not feature correctness. Building
more enforcement (fixing the lint's blind spots, more pins, more governance) is **optimization theater
on a WHAT layer whose consumers have no demonstrated edge.** YAGNI applies: close Gate 2, do the cheap
hygiene, freeze the layer, redirect.

---

## Single highest-leverage next action

**Run the one decisive experiment: a CRT-spine decision-flip test at the ~11–13 real BNBUSDT
executions.** Not a redesign — a ~1-file bounded read-only probe:

- Take the CRT-spine setups that actually reach `EXECUTION` (already enumerated by the existing spine
  adapter / prior findings — reuse, don't rebuild).
- For each, evaluate `EngineRunner.run()` twice — canonical vs `body/total_wick` `body_ratio` — with
  the **same deepcopy isolation 7c already implements** (that machinery is correct and reusable).
- Record final EXECUTE/REJECT flips **on the executing candles only** (denominator = the ~11–13, not
  70,002).

This is small, deterministic, and **decisively closes or opens Gate 2**. Outcome routing:
- **0 flips** → Gate 2 closes honestly; GD-001/002 remediation is behavior-neutral; ship it +
  GD-004/005 renames + GD-008/009 dead-code deletion as one hygiene pass; **freeze the feature-math
  program**; correct the F-047/memory "DECISION-INERT" headline to the qualified statement.
- **≥1 flip** → GD-001/002 is live-material; remediation goes through the promotion gate; re-scope the
  finding.

Everything else in this space is lower leverage. Do **not** spend effort hardening the lint's
false-negatives unless a real DataFrame-write re-derivation is actually observed.

---

## Verification (how to check this verdict end-to-end)

1. **Reproduce the null-by-construction claim:** `type reports/feature-math-decision-flip-probe.json`
   → confirm `approve_current_A == 0` and `approve_canonical_B == 0`. If both are 0, `flips=0` is
   forced.
2. **Confirm the spine executes >0:** re-run the spine adapter on BNBUSDT (gate-ON) and confirm ~11
   executions — the count the 7c harness fails to reproduce.
3. **Reproduce the durable_keys** under `venv/Scripts/python.exe` (PyYAML + the interpreter the pins
   were minted on — `ast.dump` is version-sensitive): `python scripts/analysis/feature_math_lint.py
   --check`. All 10 pins should be present, 0 stale, floor green.
4. **Demonstrate a lint false-negative** (read-only, in a scratch file): a module under `src/engines/`
   containing `df["body_ratio"] = high - low` passes `--check` clean — proving the Subscript blind spot.
5. **Run the tests behind the layer:** `python -m pytest tests/test_feature_math_lint.py
   tests/test_feature_lineage.py -q` → the ratchet/lineage floor is green (this verifies the *pins*,
   not exhaustiveness).

---

## SESSION LOG (to persist to assistant_project.md on execution — plan mode blocked the write)

```
📝 SESSION LOG ENTRY
Date: 2026-07-08
Topic: Forensic audit of feature-math WHAT layer / Gate 1 / Gate 2 / GD-001..010
Decision/Output: Verdict — registry/pins/isolation PROVEN; enforcement has material false-negative
  classes (Subscript/Attribute/AugAssign/non-registered-name/out-of-5-dirs); Gate-2 7c is
  NULL-BY-CONSTRUCTION (0/0 approvals across 70,002 candles → flips=0 forced; spine executes ~11,
  harness executes 0) → Gate 2 cannot close; F-047/memory "DECISION-INERT" is an E-001 overclaim.
Belief Update / ROI / Goal:
  Goal: guarantee research→backtest→live decision consistency of feature math.
  Belief: the feature-math correctness question is NOT yet answered for the cases that matter;
    the apparatus' real ROI (re-validating the F-019..F-042 null sweep as non-artifactual) is banked.
  Knowledge ROI: high (identified the one load-bearing gap + the one decisive cheap test).
  Action: run the CRT-spine flip test on the ~11-13 real executions; then freeze the layer.
Open Questions: Do GD-001/002 flip any real live decision? Is the 10-site census exhaustive given
  the DataFrame-write / research/ blind spots?
Next Step: CRT-spine decision-flip probe (executing candles only); route remediation on its result.
```


================================================================================
SOURCE_FILE: docs/implementation_plan/the-image-you-shared-luminous-peach.md
SOURCE_BYTES: 13825
PART: 8/10 FILE 13/16
================================================================================

# Program 4b — Forward Markov Regime-Transition Forecast (crypto majors)

## Context

Program 8 (weekly CRT sweep) is closed (F-042, 0 PROMOTE). You asked to move next to "Program
4b: Transition Forecast," which I initially recommended from the Funding Ledger without
verifying its true status. Investigation surfaced a real doc-staleness issue worth stating
plainly before planning the build:

- The Funding Ledger's **"Program 4b: ... Regime TRANSITION Forecast (forward Markov P^H) —
  RESEARCH (pre-registration pending)"** entry (`docs/current-findings.md`, dated 2026-06-17)
  describes a **literal Markov transition-probability forecast** —
  `docs/research-readiness/program-4b-transition-preregistration.md` — whose own §8 build
  checklist says "a future session — NOT done here."
- **F-040** (2026-06-26, "Program 4 CLOSED") tested a **different construction** — an MTF
  candle-state conjunction (`docs/research/preregistration-program-4bcd.md`,
  `compression_breakout.py`) — and closed a differently-scoped "4b/4c/4d" grouping.
- These are **not the same hypothesis**: one is a literal trailing Markov `P_t^H`
  transition-matrix projection; the other is a compression→expansion conjunction test. The
  Markov-P^H construction was genuinely never built. The stale ledger entry needs a doc fix
  regardless of which way this new run resolves (§6.2 DOC_DRIFT, unambiguous, auto-fixable).
- The pre-registration reserves finding number **"F-031"** for the result — but F-031 has
  since been consumed by an unrelated governance finding. The real result will be **F-043**
  (next free after this session's own F-042).
- **Pre-registered economic prior** (stated before running, per E-001): F-040 already
  established that a related transition channel is informative but economically
  non-consumable because *"the binding constraint is the EXECUTION MODEL (spot long/short
  cannot express a long-vol payoff), not predictability."* Program 4b targets the same
  category of thing (anticipating a volatility-regime change) in the same spot-directional
  architecture, so the reasonable prior is it hits the same wall — expect
  `REGIME_INFORMATIONAL` / `REGIME_HARMFUL` / `REGIME_INSUFFICIENT` at best, not
  `REGIME_EXPLOITABLE`. This is recorded now, not after seeing results.

The pre-registration's design is **frozen** (§5, "changing any after a null is forbidden
archaeology") — this plan implements it as specified, it does not redesign it.

## What already exists and will be reused verbatim

| Concern | File:line |
|---|---|
| `RegimeLabeler` (current-level S_t, trailing terciles) | `src/interpreters/regime_observer.py:40-91` — reused AS-IS for the current-level series (both the calibration input and the new within-tercile-shuffle's stratifying key) |
| `regime_conditioning.evaluate_scope` (3×3 cross-matrix, M4 gate, BH, verdict rollup) | `src/research/regime_conditioning.py:238-395` — reused verbatim for the core gate; extended ADDITIVELY (see below), never behavior-changed for existing callers |
| `RegimeConfig` | `src/research/regime_conditioning.py:51-76` — reused as-is; `lag_k=8` set via config, no code change needed |
| `characterize()` / `ProcessManifest.hurst_atr` / `thesis_flags.volatility_persistent` | `src/research/process_characterization.py:238-310` — reused verbatim for the calibration gate |
| Program 4's toy consumers | `expansion_breakout`, `mean_reversion` (registered hypotheses) — **reused, NOT `compression_breakout`** (that belongs to the separate, already-closed F-040/candle-state pipeline — using it here would silently retest F-040's question under Program 4b's name) |
| Program 4's spine family | `configs/research/research_config_spine_majors.json`, consumer `spine` — reused verbatim, same as Program 4's driver |
| Driver structure to mirror | `scripts/research/qualify_regime_conditioning.py` (full file) — copy structure, not modify |
| Config structure to mirror | `configs/research/research_config_regime.json` — copy `harness`/`forward_walk`/`signal`/`costs`/`qualification`/`universe`/`regime` blocks verbatim |
| Falsification controls, `HypothesisRunner`, `QualConfig`, `benjamini_hochberg` | unchanged, same imports as the existing driver |
| No-lookahead test pattern to extend | `tests/test_regime_observer.py:53-71` (`test_no_lookahead_truncation_stable`, `test_no_global_rank_leak`) |
| Determinism/verdict test pattern to extend | `tests/test_regime_conditioning.py:58-76` (`_QCFG`/`_RCFG` fixtures, `_edge_scenario`/`_noise_scenario` planted-edge pattern) |

## Implementation steps

### 1. `MarkovRegimeForecaster` — the only genuinely new statistical engine
New class in `src/interpreters/regime_observer.py` (additive; `RegimeLabeler` untouched):
- Constructor: `atr_period` (reuse `RegimeLabeler`'s, default 14), `tercile_window` (480),
  `w_markov` (trailing transition-count window, 480), `h` (forecast horizon, 8). No config
  reads — constructor args only, mirroring `RegimeLabeler`.
- `forecast_series(candles) -> list[str | None]`: for each bar `t`, build the trailing
  transition-count matrix over the last `w_markov` **completed** transitions `τ→τ+1` with
  `τ+1 ≤ t` (using `RegimeLabeler.label_series(candles)` internally for `S_t`, reused
  verbatim — never reimplemented), row-normalize (rows with zero occurrences → uniform
  `[1/3,1/3,1/3]`), raise to the `h`-th power (`numpy.linalg.matrix_power`), project the
  current one-hot state `v_t`, and take `argmax` as `Ŝ_{t+h}` (confidence = `max` of the
  projected vector, exposed via a companion `confidence_series()` for diagnostics — not
  required by the gate). Returns `None` wherever the underlying `S_t` series is `None`
  (warmup) or the trailing transition window isn't yet full.
- **Docstring must state explicitly:** `forecast_series[t]` is the prediction MADE AT bar
  `t` for `t+h`, using only data through `t` — never the realized regime at `t+h`. This is
  the load-bearing no-lookahead property; the output is a drop-in replacement for
  `RegimeLabeler.label_series()`'s shape/semantics, so it plugs into `evaluate_scope()`
  unchanged.
- Pure, deterministic (no RNG), same trailing-only discipline as `RegimeLabeler`.

### 2. Within-tercile-shuffle control (the pre-registration's "5th control")
Additive changes to `src/research/regime_conditioning.py`:
- New function `_within_tercile_relabeler(universe, current_level_series, tag)`: for each
  instrument, group `universe[inst]` positions by their **current-level** label at
  `entry_index` (looked up from `current_level_series`, i.e. `RegimeLabeler`'s S_t — NOT the
  predicted label), then seeded-shuffle the **predicted** labels within each current-level
  group (mirrors `_shuffled_relabeler`'s per-instrument seeded-shuffle pattern, stratified
  by the extra series). This destroys transition-forecast information while preserving the
  current vol level — isolating whether an apparent edge is really just the (already-closed,
  F-030) level signal reappearing.
- Extend `evaluate_scope()` and `_consumer_verdict()` with a **new optional parameter**
  (`current_level_series: dict | None = None`, default `None`). When `None` (every existing
  Program-4 call site), behavior is byte-identical to today — protected by a regression test
  (§4). When supplied (Program 4b only), compute `S_within_tercile` analogously to how
  `S_lagged` is computed today, and fold a `level_redundant` check into the SAME
  `REGIME_REDUNDANT` verdict bucket (the pre-registration reuses Program 4's exact 5-verdict
  vocabulary, §4 of the pre-reg — no 6th verdict class). Record `S_within_tercile` /
  `level_redundant` as new, purely additive fields in the per-consumer output dict (parallel
  to the existing `S_lagged`/`redundant` fields) for transparency.

### 3. Hard calibration gate (harder than Program 4's advisory-only check)
In the new driver (not touching `qualify_regime_conditioning.py`): reuse
`process_characterization.characterize()` verbatim, but **raise** (`SystemExit` or
`RuntimeError`) if BNBUSDT's `hurst_atr` falls outside `[0.855, 0.915]` or
`thesis_flags["volatility_persistent"]` is `False` — per the pre-registration's "the CLI
raises... no economic claim runs on an instrument whose vol-memory prior isn't reproduced."

### 4. New config
`configs/research/research_config_regime_transition.json` (new file): copy
`research_config_regime.json`'s `harness`/`forward_walk`/`signal`/`costs`/`qualification`/
`universe`/`regime` blocks verbatim, with `regime.lag_k` set to `8` (= H, per the
pre-registration's explicit hardening — "lag_k = forecast horizon H"). Add a new top-level
`markov` block (read directly by the driver, not by `RegimeConfig.from_dict`, same pattern as
the existing `regime` block): `{"w_markov": 480, "h": 8, "hurst_atr_center": 0.885,
"hurst_atr_tolerance": 0.03}`. `research_config_spine_majors.json` is reused unchanged for the
spine family (no new file needed there).

### 5. New driver
`scripts/research/qualify_regime_transition.py` (new file, mirrors
`qualify_regime_conditioning.py`'s structure exactly):
- Build the current-level series (`RegimeLabeler`, reused) once per instrument, AND the
  predicted series (`MarkovRegimeForecaster.forecast_series`, new) once per instrument.
- Run the hard calibration gate (step 3) before any economic evaluation; abort on failure.
- Run both families exactly like Program 4's driver (`toy`: `expansion_breakout`,
  `mean_reversion`; `spine`: `spine`), across the same `MAJORS` scope
  (`BNBUSDT, ETHUSDT, BTCUSDT, SOLUSDT` + `POOLED`), passing the **predicted** label series
  as `evaluate_scope()`'s `label_series` argument and the **current-level** series as the new
  `current_level_series` argument.
- Output: `results/research/regime_transition/qualify_regime_transition.json` (deterministic
  body, no wall-clock) + `_manifest.json` (git commit + timestamp) — same two-file convention.
- Print the calibration line + verdict table, mirroring `_print_table` in the existing driver.

### 6. Tests (new, plus one regression addition to the existing suite)
- `tests/test_markov_regime_forecaster.py`: determinism; no-lookahead truncation (`forecast_
  series[:k+1]` invariant to appended future bars — mirrors `test_no_lookahead_truncation_
  stable`/`test_no_global_rank_leak`); trailing-window-only transition counting (a completed
  transition landing after `t` must not be counted at `t`); uniform-1/3 fallback for
  zero-occurrence rows; H-step projection correctness against a small hand-computed 3-state
  matrix (verify against `numpy.linalg.matrix_power` directly, not just end-to-end).
- `tests/test_regime_conditioning.py` additions: (a) a planted LEVEL-only edge (rr depends on
  current level; the predicted label carries zero incremental information) must resolve to
  `REGIME_REDUNDANT` via the within-tercile check, not `REGIME_EXPLOITABLE` — the core
  behavioral proof that the 5th control does its job; (b) **regression test**: calling
  `evaluate_scope()` WITHOUT `current_level_series` (Program 4's original signature) produces
  byte-identical output to before this change — protects F-030's reproducibility; (c)
  determinism test extended to the new optional-parameter path.

### 7. Execution + doc fixes + findings registration
1. **Doc-drift fix (unambiguous, auto-fixable per §6.2 gate calibration):** update the stale
   Funding Ledger "Program 4b" entry (`docs/current-findings.md`, 2026-06-17) — correct the
   reserved-number reference from F-031 (superseded) and mark it as about to be resolved by
   this run.
2. Write/confirm the E-001 six-question check inline, recording the stated prior (§ above)
   BEFORE running.
3. Run `python scripts/research/qualify_regime_transition.py`; inspect the verdict JSON.
4. Register the result as **F-043** in `docs/current-findings.md`, citing the calibration
   result, per-consumer/per-scope verdicts, and the within-tercile-shuffle outcome
   specifically (whether `level_redundant` fired).
5. Finalize the Funding Ledger "Program 4b" entry with the real outcome (status +
   Reopen Conditions, same format as Program 4/6b/8's entries) and add a Scope Matrix row.
6. Add the F-043 row to `CLAUDE.md` §4 Repository Truths Index.
7. Run `tests/test_current_findings.py` + the full `tests/research/` and regime-specific
   suites to confirm no regression.

## Critical files
- `src/interpreters/regime_observer.py` (edit — additive `MarkovRegimeForecaster` class)
- `src/research/regime_conditioning.py` (edit — additive `_within_tercile_relabeler` +
  optional `current_level_series` parameter on `evaluate_scope`/`_consumer_verdict`)
- `configs/research/research_config_regime_transition.json` (new)
- `scripts/research/qualify_regime_transition.py` (new)
- `tests/test_markov_regime_forecaster.py` (new), `tests/test_regime_conditioning.py` (edit —
  additions + regression test)
- `docs/current-findings.md` (edit — new F-043 finding + Program 4b Funding Ledger fix +
  Scope Matrix row), `CLAUDE.md` §4 (edit — new F-043 row)

## Verification
1. `pytest tests/test_markov_regime_forecaster.py tests/test_regime_observer.py
   tests/test_regime_conditioning.py -v` — all green, including the new regression test
   proving Program 4's original `evaluate_scope()` behavior is unchanged.
2. `pytest tests/research/ tests/test_current_findings.py -q` — full suite unaffected.
3. `python scripts/research/qualify_regime_transition.py` — runs end-to-end (raises cleanly
   if the calibration gate fails), writes both JSON files, prints calibration + verdict
   tables, exits 0.
4. Run the driver twice; diff the two JSON bodies — must be byte-identical.
5. `pytest tests/test_current_findings.py -q` — passes after F-043 is registered.


================================================================================
SOURCE_FILE: docs/implementation_plan/the-key-unanswered-question-functional-corbato.md
SOURCE_BYTES: 8752
PART: 8/10 FILE 14/16
================================================================================

# Executor Assessment — External AI-Stack Proposal (Dify / LangChain / Hermes / n8n / DuckDB / LiteLLM / Qdrant / Ollama)

## Context

Another model in the multi-LLM loop (§13) produced a "recommended stack" memo proposing you
layer Dify + LangChain + Hermes-concepts + n8n + DuckDB + LiteLLM + Qdrant + Ollama + MCP on top
of the Tradelatest / mt5_analytics ecosystem. Per **§13.8** that memo is *input to Claude, not
authority* — it's a recommendation the evidence settles. You asked for an **Executor assessment
first** (verify claims → score against frozen doctrine → per-tool verdict), with **target use not
yet decided**. This file is that verdict, not a build plan. Nothing here is executed.

The memo's own headline reframing is correct and worth keeping: *"deterministic workflow >
autonomous exploration"* and *"use each tool for one responsibility only."* The problem is it
mis-states what already exists and recommends architecture ahead of a proven bottleneck — which
**§6.5 Authority Ladder** (information ≠ value ≠ authority ≠ **architecture**) and the §6.1
"no premature framework" guardrail explicitly forbid.

---

## 1. Fact-check — what the memo claims vs. repo reality

| Memo claim | Reality (evidence) | Verdict |
|---|---|---|
| "You already have MT5 → JSONL → **Parquet** → Dashboard" | Live artifact is **JSONL + `manifest.json` (sha256)** only. `mt5_analytics/storage/partition_writer.py:1-11` = *"idempotent, date-partitioned **JSONL** writer."* **Zero** `import duckdb` / `to_parquet` / `.parquet` anywhere in `mt5_analytics/` (grep empty). | **FALSE** — no Parquet/DuckDB pipeline exists |
| DuckDB/Parquet are net-new tools to add | Already **declared optional deps** (`pyproject.toml:18-26`, `mt5_analytics` extra: pyarrow, duckdb, streamlit) — for *"later phases (storage, dashboard, research)"* but **not wired**. | Declared-not-used |
| A dashboard exists | **TRUE** — `mt5_analytics/ui/streamlit_dashboard.py` (Streamlit, read-only, consumes JSONL via `dashboard_data`). Not the control plane, not over Parquet. | TRUE (Streamlit) |
| n8n is a "new suggested tool beyond your list" | **Already a pending backlog epic** — `multi_llm/build_queue.jsonl` Epic 6 "n8n Integration" (STORY-6.1…6.5 conf 70–90 + STORY-9.3 tests), scoped into `src/control_plane/` webhook receiver. | Not new — on roadmap |
| Add LangChain / Dify / LiteLLM / Qdrant / Ollama / Hermes | **Zero footprint** in code or deps (grep). All net-new, all long-running services. | Net-new heavy |
| "Existing deterministic Intent→Plan→Tools→Execution resembles an agent framework already" | **TRUE** — `src/agent/tool_registry.py` + `plan_compiler.py` `PLAN_REGISTRY` + `IntentRouter`; deterministic by design (CLAUDE.md §3.3: *"do not route planning through the LLM"*). | TRUE — argues *against* adding another orchestrator |

**Bottom line:** the memo recommends "adopting" DuckDB/Parquet (partly already sanctioned but
inert) while calling the pipeline "done," presents an already-planned tool (n8n) as novel, and
bolts on 6 net-new server-grade dependencies with no stated consumer.

---

## 2. Doctrine scorecard

| Doctrine | Bearing on the proposal |
|---|---|
| **§4 "No database / no broker / file-backed"** | Dify, n8n, Qdrant, Ollama, LiteLLM are **long-running services** (Docker/servers) → against the file-backed posture. **DuckDB is the one exception** — embedded, file-backed, queries JSONL/Parquet in-process; already a declared dep. Not a violation. |
| **§4 "control plane is stdlib-only, localhost, no auth"** | Adding Dify/n8n web layers conflicts with stdlib minimalism. n8n was accepted *only* as a webhook receiver bolted to the existing control plane (Epic 6), not as a replacement. |
| **§6.1 no-premature-framework + §6.5 Authority Ladder** | Adding a tool = **increasing architecture**, the top rung. Doctrine: architecture is justified only by a **demonstrated consumer with measured benefit** — not "it'd be nice." "Target use not decided" ⇒ by doctrine, **build nothing yet.** |
| **§13 multi-LLM is hand-operated by design** | User=Bridge copy-paste is intentional. The *one* genuine friction the memo names (copy-paste toil) is real — but the repo already chose **n8n**, not Dify/LangChain, to address it. |
| **§6.5 "CONFIG_DRIVEN grants tunability, never authority"** | Same logic: a capability existing (Streamlit, DuckDB dep) grants *usage*, never a mandate to expand the stack. |

---

## 3. Per-tool verdict (Executor recommendation)

| Tool | Memo said | Executor verdict | Why |
|---|---|---|---|
| **DuckDB** | (bundled) | **ADOPT-WHEN-NEEDED** — read-only query over existing JSONL | Only doctrine-clean item: embedded, file-backed, already a declared dep, zero new service. The natural "ask questions over trade history" substrate. |
| **Streamlit dashboard** | implied new | **ALREADY EXISTS — extend, don't re-import** | `streamlit_dashboard.py` is live and read-only. Any "dashboard" work extends this. |
| **n8n** | "new tool" | **DEFER to Epic 6** — do not re-scope | Already planned as a control-plane webhook receiver. Not a Claude decision to re-open now. |
| **Hermes *concepts*** (persistent memory / skill files) | adopt ideas | **ALREADY PRESENT** — `~/.claude/…/memory/` + `MEMORY.md` + findings registry + Portable Mind (`scripts/context/build_context.py`, `pack_story.py`) | You already have the learning-loop. Importing "Hermes" adds nothing; avoid its self-modifying autonomous loops (memo agrees). |
| **LangChain** | partial (RAG/tools) | **REJECT for orchestration; MAYBE thin RAG only** | Deterministic `PLAN_REGISTRY` already is the tool layer; a 2nd orchestrator = duplication (the memo's own stated #1 risk). If retrieval is ever needed, a ~100-line stdlib+DuckDB path beats the dependency. |
| **Dify** | YES (high) | **REJECT** | Heavy Docker platform; duplicates control-plane + agent layer; violates stdlib/file-backed posture. No consumer identified. |
| **LiteLLM** | suggested | **REJECT (now)** | A model gateway matters only at multi-provider scale you don't run. `llm_inference_client` + BitNet/Groq/llama.cpp already cover the tie-breaker path. Revisit only if provider-fanout becomes real. |
| **Qdrant** | suggested | **REJECT** | Server-grade vector DB for a corpus that fits in memory; DuckDB + brute-force cosine covers any near-term retrieval. |
| **Ollama** | suggested | **REJECT (now)** | Local model server; overlaps existing llama.cpp/BitNet GGUF integration. No gap. |
| **AutoGPT** | NO | **REJECT — agree with memo** | Unbounded autonomous loops are the antithesis of the governance/audit posture. |
| **MCP** | suggested | **NEUTRAL / already available** | This harness already speaks MCP; not a repo dependency to "adopt." |

---

## 4. The actual recommendation

**Adopt nothing net-new right now.** By §6.1/§6.5 and your own "target use not decided," the
correct Executor answer is to *not* buy architecture ahead of a proven bottleneck. The repo already
holds the minimal-viable answer to every real need the memo raises:

- **"Ask questions over trade/findings history"** → JSONL truth + **DuckDB (already a declared
  dep)** for read-only SQL + existing **Streamlit** dashboard. No Dify/LangChain/Qdrant required.
- **"Persistent memory / skills"** → already exists (`MEMORY.md`, findings registry, Portable Mind).
- **"Reduce multi-LLM copy-paste"** → already scoped as **n8n Epic 6**; don't fork it into Dify.

**If** you later want to act, the single smallest doctrine-clean step is a **read-only DuckDB query
helper over the existing `mt5_analytics` JSONL partitions** (activates a dep you already declared,
adds no service, no schema change, `dashboard_data`-style CI-tested loader). That is the only
candidate worth a build plan — and only once you name the question you want it to answer.

---

## 5. Verification (for whatever does get built later)

Any adoption must clear the same gates the memo bypassed:
- **No new long-running service** unless it passes §4 (file-backed / localhost / no-auth-surface).
- **Named consumer + measured benefit** before it earns architecture authority (§6.5 ladder).
- **`pytest` green** + the Streamlit-free data layer stays CI-tested (mirror `dashboard_data`).
- **SESSION LOG + doc-drift decision** per §6 / §6.2 for any code that lands.

## Open decision for the user
Pick the **one question you'd want to ask over your own trade history** (or confirm "none yet").
That single use-case is the only thing that would justify turning any of this into a build plan —
and if the answer is "none yet," the correct action is to ship nothing and revisit when a real
question strains the current JSONL+Streamlit path.


================================================================================
SOURCE_FILE: docs/implementation_plan/the-largest-risk-mossy-graham.md
SOURCE_BYTES: 4884
PART: 8/10 FILE 15/16
================================================================================

# IC-007 / PLAN-002 closure bookkeeping — wire F-052 into the truth index + log the closure

## Context

DeepSeek executed the PLAN-002 closure correction (remove the second engines-path CODE
authority — the `(0.35,0.25,0.20,0.20)` fallback tuple in `engines.crt_engine.compute`) while I
was away. Review of the actual repo state confirms the **implementation is correctly done**:

- `src/engines/crt_engine.py` — missing `context["score_component_weights"]` now `raise`s a
  `KeyError` *inside* the existing `try/except Exception`, so `compute()` returns
  `{"score": 0.0, "reason": "score_component_weights missing…"}` — **fail-closed, no silent CODE
  literal**. (The reviewer's wording concern is real and is **already pre-corrected** in F-052's
  Note: it does NOT propagate an exception externally.)
- All real callers pass the key explicitly: `engine_runner.py:678` (config-injected),
  `s01_crt_wrapper.py` (new `_load_score_component_weights()` from prod config, fail-closed),
  both probes (`feature_math_drift_probe.py`, `pit_swing_blast_radius.py`) pass explicit legacy
  vectors. Tests either monkeypatch `crt_compute` (dual-gate/rr-fusion) or assert the fail-closed
  path (`test_plan002_dual_weights_how.py`).
- **F-052 is recorded** in `docs/current-findings.md` (call-site census 18 matches / 0 legit
  implicit-default callers, files changed, 38/38 focused tests, Reversal, precise fail-closed
  Note) with Type=GOVERNANCE, Status=VALIDATED, Confidence=Certain.

**Two gaps remain — both governance bookkeeping, matching the reviewer's "What We Don't Know":**

1. **F-052 is absent from the CLAUDE.md Repository Truths Index**, so the enforcement floor
   `tests/test_current_findings.py::test_index_and_doc_agree_on_nonterminal_ids` is **RED**
   (`non-terminal findings absent from CLAUDE.md Repository Truths Index: ['F-052']`). This is
   the *only* failing check across the whole construction floor (121 passed / 1 failed).
2. **No §6 SESSION LOG entry** records this closure correction (DeepSeek wrote the finding but
   not a log entry).

**Broader-suite status (the reviewer's other "don't know") — resolved by read-only verification:**
the affected surface is **green**: `test_plan002_dual_weights_how` + engine_runner dual-gate +
rr-fusion + zone_gate + crt_fixes + crt_adversarial_closure + active_models + golden ledgers =
**102 passed / 8 skipped**; construction `check` = 121 passed, the single red being the F-052
index row. The two PLAN-002 manifests' `declared_files` are the dirty-tree union, so they already
cover the closure-correction files (`crt_engine.py`, `s01_crt_wrapper.py`, the probes) — no
manifest churn needed.

## Change (docs-only; zero code/config edits)

1. **Wire F-052 into the truth index.** Insert one row into the CLAUDE.md "Repository Truths
   Index" table immediately after the F-051 row (CLAUDE.md:360), matching the existing
   `| F-id | TYPE | conclusion | Conf |` format:
   `| F-052 | GOV | PLAN-002 closure — the 2nd engines-path CODE authority (the (0.35,0.25,0.20,0.20) fallback in engines.crt_engine.compute) removed: missing score_component_weights now FAIL-CLOSED (returns score 0.0 + reason, not a silent CODE literal, not a propagated exception); all real callers (EngineRunner, S01CRTWrapper, probes) inject the HOW key; conf_weights + risk_score_weights untouched; the two weight identities stay distinct | Certain |`
   This turns the RED floor green (index ↔ doc agree).

2. **Append a §6 SESSION LOG entry** to `assistant_project.md` recording: the closure-correction
   review verdict (implementation sound, F-052 already recorded, wording pre-corrected), the
   index-row wiring, the read-only broader-suite verification (102 passed on affected surface +
   121/1 construction), and the precise fail-closed behavior statement. Rotate first if the log
   is at the 30-entry cap (`rotate_session_log.py`, collision-check the archive name).

## Explicitly NOT doing (reviewer's guardrails)

- No IC-007 implementation changes; no touching `crt_engine.compute` logic, weight values,
  `conf_weights`, or merging the two identities.
- No new broad audit; no PLAN-003 (stays REVISED/not-started — heterogeneous); no surplus
  cleanup beyond this closure.
- Do not modify PLAN-001.

## Verification

- `venv/Scripts/python.exe -m pytest tests/test_current_findings.py -q` → all green (the index
  ↔ doc agreement test flips red→green).
- `venv/Scripts/python.exe scripts/governance/construction_protocol.py check` → **GREEN**
  (was 121 passed / 1 failed = the F-052 index row).
- `git diff --stat` shows only `CLAUDE.md` + `assistant_project.md` changed (docs-only; no
  `src/`, `configs/`, `models/` edits) — confirming pure bookkeeping.
- Stop after the floor is green for the user to select the next surplus-census candidate (do not
  auto-start the next implementation).


================================================================================
SOURCE_FILE: docs/implementation_plan/the-largest-risk-you-indexed-puddle.md
SOURCE_BYTES: 11921
PART: 8/10 FILE 16/16
================================================================================

# Plan: Freeze a Goal Layer (economic-objective layer) + close 2 data-governor gaps

## Context

**Why this change.** The user's architectural review argues for freezing a *Goal Architecture*
(`GOAL.md` / `goal_schema.py` / `goal_validator.py` + a hard Data Governor) **before** adding any
new interpreters (P&F, Wyckoff, Market Profile, Order Flow). The core insight is correct: the
system optimizes engines without an explicit, machine-checkable **business goal**, and bad data
silently manufactures fake edges.

**What exploration found (the reconciliation).** Most of the proposal already exists and is good —
so this plan is *additive and surgical*, not a greenfield build:

- **Data Governor — 8 of 10 checks already exist.** `src/data_ingestion/dataset_integrity.py` +
  `src/data_ingestion/ohlcv_schema.py` hard-check missing/duplicate/non-monotonic timestamps, NaN,
  invalid OHLC, negative volume, future timestamps, excessive gap ratio. It runs **before** any
  engine (data-validation-first, confirmed), is wired into both backtest entry points, and raises
  `DatasetIntegrityError`. It uses a **session-aware** `APPROVE/WARN/REJECT` model (crypto 24×7 vs
  FX weekend / 21:00 rollover) — a `test_fx_weekend_gaps_approve` test exists *specifically* so naive
  gap-rejection doesn't kill legitimate FX gaps. **Only 2 gaps remain:** resample completeness
  (4×M15 = 1×H1) and missing H1/H4 bars (`src/research/resample.py` is measure-only).
- **Metrics Layer — ~80% built.** `BacktestMetrics` (`src/runtime/backtest_v2.py`) computes
  profit_factor, expectancy (`avg_rr_net`), win_rate, avg_rr, max_drawdown_pct, return_to_max_dd,
  annualized_return, funnel_counts. **Missing:** trades-per-month / trade-frequency.
- **Acceptance Layer — exists.** `config_validator.py` enforces config-driven hard/soft promotion
  gates; the M4 `QualificationGate` (`src/research/qualification.py`) already forces research
  hypotheses to prove expectancy/PF/OOS/significance — the "prove Δexpectancy/Δfrequency/Δdrawdown"
  contract.
- **The genuine gap (the real insight):** the **Goal Layer is prose-only.**
  `docs/architecture/goal.md` defines invariants + a north-star but has **zero quantitative business
  targets** and no machine-readable artifact. Nothing ties config_validator thresholds + M4 + metrics
  back to one frozen economic objective.

**Framing.** `goal.md §1` declares "Profit is not the primary objective" with the priority order
*replay correctness > explainability > telemetry continuity > advisory-AI*. The business targets are
the **economic-objective dimension** that sits *alongside* (never above) those invariants, and the
advisory-first design respects that. This operationalizes CLAUDE.md §6.1 (ROI toward the user's
economic objective).

**Decisions locked with the user:**
1. **Authority:** telemetry now + a dormant `enforce` flag (default off) that can later flip the goal
   into a blocking promotion gate. Advisory-first because Program 1 is KILLED (F-019→F-027) — a
   blocking gate today rejects 100% of runs.
2. **Location:** a new top-level `goal` section in the production config JSON (reuses
   `get_prod_section`, honors the no-magic-numbers rule + branch-scoped ACTIVE_VERSION truth).
3. **Data:** extend the existing `dataset_integrity.py` (keep session-aware APPROVE/WARN/REJECT) —
   **do NOT** build a pure hard-reject module (would regress FX handling).
4. **Numbers:** freeze the user's example values as the starting canonical goal (editable later).

**Out of scope (explicitly deferred):** P&F / Wyckoff / Market Profile / Order Flow engines, and a
pre-fusion per-engine qualification contract beyond what M4 already provides. Those come *after* this
Goal Layer is frozen.

---

## Implementation

### 1. New `goal` config section (single source of truth for the economic objective)

Add a top-level `goal` key to the **active** config `configs/production/v2_multi_2026_04.json` **and**
the canonical `v1_multi_2026_03.json` / `v2_multi_2026_04.json` lineage. Starting values:

```jsonc
"goal": {
  "goal_id": "G001",
  "enforce": false,                       // dormant blocking flag (default OFF = advisory)
  "trades_per_month": {"min": 20, "target": 40, "max": 80},
  "avg_rr": {"min": 2.0},
  "win_rate": {"min": 0.35},
  "max_drawdown_pct": {"max": 0.10},
  "risk_per_trade": {"target": 0.005},
  "expectancy_r": {"min": 0.20},
  "timeframe": {"execution": "M15", "structure": "H1"},
  "instruments": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
  "constraints": {"reaction_only": true, "human_execution": true, "no_prediction": true}
}
```

Then **rehash**: `python scripts/maintenance/_compute_hash.py` (per config edit). Update each config's
`validation_summary` hash as the script dictates.

> **F-018 guard:** the active `patch` config lags HEAD code. `GoalSpec.from_prod_config` must
> **fail-soft when the `goal` section is absent** (return a disabled spec, advisory off) — never
> fail-fast — so older/lagging configs keep loading.

### 2. `src/config_layer/goal_schema.py` — `GoalSpec` dataclass

Copy the structure of `docs/reference/example-service.py` (`_require` strict accessor,
`from_prod_config` factory, named flow logger). Frozen `@dataclass`:

- Fields mirror the section above (nested ranges as small frozen value objects or simple
  `min/target/max` floats).
- `GoalSpec.from_prod_config(cfg: dict) -> "GoalSpec"`: read `cfg.get("goal")`; if absent →
  `GoalSpec.disabled()` (advisory off, all targets `None`). If present → `_require` each key,
  fail-fast on a malformed-but-present section.
- `enforce: bool` surfaced as a top-level field.

### 3. `src/config_layer/goal_validator.py` — `GoalValidator` + `GoalReport`

- `GoalReport` dataclass: per-criterion `{name, target, actual, pass: bool, gap}` rows + overall
  `decision: "PASS"|"FAIL"`, plus `enforced: bool`.
- `GoalValidator.evaluate(metrics) -> GoalReport`: pure, deterministic function of `BacktestMetrics`
  (so it cannot break replay/golden determinism). Compares trades_per_month, avg_rr, win_rate,
  max_drawdown_pct, expectancy_r against the `GoalSpec`. A disabled spec → `GoalReport` with all rows
  `None`/skipped and `decision="PASS"` (advisory no-op).
- Reuse existing metric fields; no recomputation of PnL.

### 4. Wire as additive telemetry (measure-only) — `src/runtime/backtest_v2.py`

After `MetricsEngine.compute()`, build the `GoalReport` and attach it to
`BacktestMetrics.distribution["goal_report"]` — the **same additive pattern** already used for
`_roi_block` and `feature_drift`. Never gates anything here. This is the F-006/telemetry-additive
convention (see [project_roi_metrics_layer], [project_phase6_roi_baseline]).

### 5. Add `trades_per_month` to metrics — `src/runtime/backtest_v2.py` (`MetricsEngine`)

Derive from the backtest span (first→last candle timestamp, already available) and
`approved_trades`: `trades_per_month = approved_trades / span_months`. Add as a computed property /
field on `BacktestMetrics` so `GoalValidator` can read it. Additive only.

### 6. Dormant flag-gated block — `src/governance/promotion_manager.py` (or `config_validator.py`)

When `GoalSpec.enforce == True`, fold `GoalReport` FAIL criteria into the promotion `hard_failures`
list so `ValidationReport.decision` becomes `REJECT`. **Default `enforce=false` → zero behavior
change today.** Place the check where `config_validator`'s hard gates already merge (keep one
acceptance authority; do not create a parallel gate).

### 7. Close the 2 data-governor gaps — `src/data_ingestion/dataset_integrity.py`

Add two checks, classified into the **existing** APPROVE/WARN/REJECT severity model with
**config-driven thresholds** under the existing `dataset_integrity` config section:

- **Resample completeness:** reuse `src/research/resample.py` to build H1/H4; for every emitted
  bucket whose window is fully tradable (session-aware, reuse `_is_tradable`), verify the expected
  child count (4×M15→H1, 4×H1→H4). Incomplete tradable buckets → severity per threshold.
- **Missing H1/H4 bars:** detect tradable H1/H4 slots with no emitted bar. Honor the session calendar
  so FX weekends / 21:00 rollover are **not** false-flagged (the whole reason to extend, not replace).

Keep `raise_on_fail` / skip-not-abort semantics identical. Bump the relevant validator version
constant if the report shape changes.

### 8. Docs + truth sync (same-turn, per §6.2 / §6.3 / §6.4)

- `docs/architecture/goal.md`: add a "Canonical economic targets (machine-readable)" subsection that
  **points at** the `goal` config section; keep the existing priority ordering and invariants intact.
- `docs/reference/config-reference.md`: document the new `goal` section keys + editing/rehash rule.
- `docs/reference/schemas.md`: add `GoalSpec` + `GoalReport` shapes (§ dataclasses) and the new
  `goal_report` distribution line.
- `docs/topics/`: promote/update **one** topic doc (`goal-layer.md`) from `_template.md` per the Topic
  Sync Mandate (only that file).
- **No finding flip:** this is new infrastructure, not the validation/overturning of a conclusion, so
  `docs/current-findings.md` is unchanged. Record the build as a memory entry + SESSION LOG.

---

## Critical files

| File | Change |
|---|---|
| `configs/production/v2_multi_2026_04.json` (+ v1/v2 lineage) | new `goal` section; rehash |
| `src/config_layer/goal_schema.py` | **new** — `GoalSpec` (fail-soft when absent) |
| `src/config_layer/goal_validator.py` | **new** — `GoalValidator` + `GoalReport` |
| `src/runtime/backtest_v2.py` | attach `goal_report` telemetry; add `trades_per_month` |
| `src/governance/promotion_manager.py` / `config_validator.py` | dormant `enforce` fold-in |
| `src/data_ingestion/dataset_integrity.py` | resample-completeness + missing-H1/H4 checks |
| docs: `goal.md`, `config-reference.md`, `schemas.md`, `topics/goal-layer.md` | sync |

## Reused existing code (do not reinvent)
- `docs/reference/example-service.py` — `_require` / `from_prod_config` / flow-logger template.
- `get_prod_section` (`src/config_layer/production_config.py`) — config access + ACTIVE_VERSION truth.
- `BacktestMetrics` ROI block / `feature_drift` — the additive-telemetry attach pattern.
- `dataset_integrity._is_tradable` + session calendar — session-aware gap logic to keep.
- `src/research/resample.py` — deterministic M15→H1/H4 aggregation for completeness checks.
- `config_validator` hard/soft gate merge point — the single acceptance authority.

---

## Verification

1. **Unit tests (new):**
   - `tests/test_goal_schema.py` — `from_prod_config` parses the section; **absent section →
     disabled spec, no exception**; malformed-but-present → fail-fast.
   - `tests/test_goal_validator.py` — PASS/FAIL per criterion + gap math; disabled spec = advisory
     no-op PASS; `enforce=True` folds FAIL into hard_failures, `enforce=False` does not.
   - `tests/test_dataset_integrity.py` (extend) — incomplete H1 bucket → REJECT/WARN; missing H1/H4
     bar detected; **`test_fx_weekend_gaps_approve` still APPROVES** (no regression).
   - metrics test — `trades_per_month` correct over a known span.
2. **Determinism / replay gates:** run the Backtest Trust Layer parity/replay/golden tests
   (`[project_backtest_trust_layer]`). Confirm `goal_report` is deterministic and golden artifacts
   updated intentionally (additive field).
3. **ORIENT_RUNTIME:** `get_active_version()` still loads `v2_multi_2026_04` after rehash; schema
   keys present (no `unknown override key` error).
4. **End-to-end:** run a BNBUSDT backtest; confirm `goal_report` appears in metrics telemetry,
   `enforce=false` changes no decision, and flipping `enforce=true` in a throwaway config turns a
   goal-missing run into a promotion REJECT.
5. **Full suite + Five Governance Questions** per `docs/reference/testing.md`; append SESSION LOG.
