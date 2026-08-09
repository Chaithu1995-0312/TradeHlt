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
