# Topic: Feature Schema, Pipeline & Drift

> **Topic-visibility unit.** The canonical feature contract every engine consumes, the pipeline that
> builds it candle-by-candle, and the drift monitor that watches it. (Promoted from a stub row.)
>
> Created: 2026-06-05 · Updated: 2026-09-05 · Status: living

## In plain language
Every engine scores the same fixed, ordered list of numbers per candle — the **canonical feature
vector**. Its order is frozen and hashed so a model trained on one ordering can never be silently fed
another. The schema is currently **48-dimensional** (schema v5.0: 39 pre-existing features — the
35 v2.0 features, 3 v3.0 liquidity/volume features, and the v4.0 MACD-split/domain features — plus
9 v5.0 SMC primitives: order block, FVG, breaker, mitigation, PDH/PDL, EQH/EQL, CHoCH). A pipeline turns raw OHLCV into that vector with no lookahead; a monitor
watches a few features for distribution **drift** and logs it — but (per F-008) drift is **logged,
not acted on** (it doesn't yet gate or size down).

### Why `stream()` is more than CSV parsing
`CandleLoader.stream()` ([`backtest_v2.py:704`](../../src/runtime/backtest_v2.py)) is not a file
reader — it is the **truth-enforcement boundary** between raw price files and any code that reasons
about prices. Think of it as **double-entry bookkeeping for market data**: just as an accounting
ledger refuses to record transactions that violate its invariants, `stream()` refuses to emit a
candle unless it is real, complete, uniquely-timed, and in chronological order. Only then does the
engine get permission to reason about prices. The economic stake is a chain reaction —
`bad candle → bad ATR → bad SL distance → bad R → fake expectancy → false edge` — so **fail-fast is
cheaper than discovering corruption six months after deploying on a fake edge.**

**No-lookahead is a *composition* of layers, not a single gate** (F-039). Each is an independent
defense; the guarantee is their conjunction:

- **L1 — schema correctness:** unique headers, the six required columns, parseable timestamps.
- **L2 — temporal integrity:** strictly-increasing timestamps (no duplicate, no out-of-order bar)
  + per-row value sanity (`high ≥ low/open/close`, `volume ≥ 0`, no NaN/inf). An "impossible candle"
  (high below open) is treated like a violated foreign-key: immediate stop, not silent repair.
- **L3 — dataset intelligence:** gap analysis, session-calendar expectations, cross-file checks
  (`dataset_integrity.validate_dataset`). **Path-specific** — see below.
- **RT — generator semantics:** `for candle in stream(): engine.process(candle)` makes future-bar
  access *structurally impossible* — the engine cannot touch candle N+1 until N is consumed. This is
  a **causal constraint**, not (primarily) a memory optimization.

**L3 is not universal (F-039).** Only `backtest_v2` runs the L3 pre-flight. The entire `src/research/`
qualification pipeline, the analytics/governance tools, and the replay harnesses stream with only
the **always-on inline L1/L2 backstop + RT generator** as their integrity net. That makes the inline
backstop load-bearing: if `stream()` were ever made "user-friendly" (silent row-skips, auto-sorting
timestamps, inferring missing fields), those paths would lose their *only* safety net and could
quietly produce optimistic, corrupted backtests. The fail-fast, no-silent-skip design is the point.

**Why `volume` is required** flows from the contract direction `feature schema → required columns`
(`REQUIRED_OHLCV_COLUMNS`, [`ohlcv_schema.py:46`](../../src/data_ingestion/ohlcv_schema.py)), **not**
`loader → volume must exist`. The loader is downstream of the canonical feature contract; if the
schema ever dropped its volume-derived features, the requirement would follow from the contract, not
from a hard-coded loader assumption.

## Code covered
- [`src/features/feature_schema.py:46`](../../src/features/feature_schema.py) — `CANONICAL_FEATURES` — the frozen ordered tuple (48 entries; v2.0 0–34, v3.0 35–37, v4.0 38, v5.0 SMC 39–47).
- [`src/features/feature_schema.py:141`](../../src/features/feature_schema.py) — `CANONICAL_FEATURE_DIM` — `48` (asserted == len(CANONICAL_FEATURES)); `SCHEMA_V2_FEATURE_DIM` `35` / `SCHEMA_V4_FEATURE_DIM` `39` are the back-compat sentinels.
- [`src/features/feature_schema.py:223`](../../src/features/feature_schema.py) — `FEATURE_ORDER_HASH` — SHA-256[:16] of the order; the load-bearing schema hash.
- [`src/features/feature_pipeline.py:429`](../../src/features/feature_pipeline.py) — `FeaturePipeline` — raw OHLCV → enriched df + `(N,48)` vectors; `run()` at :1437; SMC step `compute_smc_features()` at :1206.
- [`src/features/feature_monitor.py:63`](../../src/features/feature_monitor.py) — `FeatureMonitor` — rolling-window drift detector, config-driven since (`window_size`/`soft_threshold`/`hard_threshold` at `:75-77`, sourced from `feature_monitor.window_size`/`soft_drift_z`/`hard_drift_z`; defaults equal the historical 500/2.5/3.0 literals).
- [`src/features/dataset_validator.py:1`](../../src/features/dataset_validator.py) — pre-training dataset gate (schema completeness, pairing, min-samples).
- [`src/features/feature_schema.py:349`](../../src/features/feature_schema.py) — `FeatureSchemaRegistry.check_compatibility` — `fail_closed=True` safety default (unknown version → reject). **2026-06-16 (STORY-1.6):** now has a live caller — `MLGaussianEngine` registers its model's stored `feature_order_hash` at load and calls `check_compatibility` in `compute()`; on equal-length/order-mismatch it returns the 0.5 fallback rather than scoring on misaligned features (the silent-corruption case the registry exists to catch). Was previously dormant (only `trainer.py` registered).

- **Spine inventory (2026-09-03 citation pass — path existence on the GCMC spine join; not a behavior claim, not G001, not a file:line citation. Source still wins.:**
- [`src/core/feature_store.py`](../../src/core/feature_store.py)
- [`src/data_ingestion/__init__.py`](../../src/data_ingestion/__init__.py)
- [`src/data_ingestion/clock_detector.py`](../../src/data_ingestion/clock_detector.py)
- [`src/data_ingestion/clock_registry.py`](../../src/data_ingestion/clock_registry.py)
- [`src/data_ingestion/session_autoderive.py`](../../src/data_ingestion/session_autoderive.py)
- [`src/data_ingestion/xauusd_phase1_candidate.py`](../../src/data_ingestion/xauusd_phase1_candidate.py)
- [`src/features/__init__.py`](../../src/features/__init__.py)
- [`src/features/broker_clock.py`](../../src/features/broker_clock.py)
- [`src/features/calendar_periods.py`](../../src/features/calendar_periods.py)
- [`src/features/dataset_builder.py`](../../src/features/dataset_builder.py)
- [`src/features/feature_builder.py`](../../src/features/feature_builder.py)
- [`src/features/feature_identity.py`](../../src/features/feature_identity.py)
- [`src/features/fm_resolve.py`](../../src/features/fm_resolve.py)
- [`src/features/gaussian_schema_contract.py`](../../src/features/gaussian_schema_contract.py)
- [`src/features/magnitude_states.py`](../../src/features/magnitude_states.py)
- [`src/features/market_context.py`](../../src/features/market_context.py)
- [`src/features/market_reality_contract.py`](../../src/features/market_reality_contract.py)
- [`src/features/market_shape.py`](../../src/features/market_shape.py)
- [`src/features/model_evidence.py`](../../src/features/model_evidence.py)
- [`src/features/parent_candle.py`](../../src/features/parent_candle.py)
- [`src/features/registry/__init__.py`](../../src/features/registry/__init__.py)
- [`src/features/registry/_loader.py`](../../src/features/registry/_loader.py)
- [`src/features/registry/composition_registry.py`](../../src/features/registry/composition_registry.py)
- [`src/features/registry/derived_registry.py`](../../src/features/registry/derived_registry.py)
- [`src/features/registry/predicate_registry.py`](../../src/features/registry/predicate_registry.py)
- [`src/features/registry/primitive_registry.py`](../../src/features/registry/primitive_registry.py)
- [`src/features/schema_validator.py`](../../src/features/schema_validator.py)

## Ins / Outs
- **Ins:** raw OHLCV DataFrame (timestamp/open/high/low/close; volume optional → 0.0 for FX). Drift monitor consumes `retest_depth`, `body_ratio`, `disp_strength` per opened trade.
- **Outs:** a 48-float vector in canonical order + enriched df (`FeaturePipeline.run`); `build_features(row)` → 48-key dict; drift severity (`"hard"|"soft"|"none"`) attached to backtest output (`BacktestMetrics.distribution["feature_drift"]`).

## Entry points & validations
- **Reached via:** `FeaturePipeline` is built inside `runtime.backtest_v2.BacktestRunner` (and the live hook). The monitor is wired in `BacktestRunner.__init__` (`backtest_v2.py:1932`), updated on `TRADE_OPENED` (`:2411`), logged at `:2816-2822`.
- **Validated by:** `FEATURE_ORDER_HASH` (any reorder invalidates the baseline → requires `baseline_capture.py`); the import-time `assert len == CANONICAL_FEATURE_DIM`; `dataset_validator` before training; no-lookahead streaming contract.

## Tests
- [`tests/test_feature_pipeline.py`](../../tests/test_feature_pipeline.py) — schema completeness, vector shape, no-NaN, determinism, zero-volume FX fallback.
- [`tests/test_schema_contracts.py`](../../tests/test_schema_contracts.py) — `FEATURE_ORDER_HASH` stability + v2.0→v3.0 back-compat slicing.
- [`tests/features/test_feature_schema_registry.py`](../../tests/features/test_feature_schema_registry.py) — registry/version + model feature-dim matching.
- [`tests/test_smc_primitives.py`](../../tests/test_smc_primitives.py) — the 9 v5.0 SMC primitive geometries directly.
- [`tests/test_feature_layer_freeze.py`](../../tests/test_feature_layer_freeze.py) — freeze-pin (vector SHA / schema hash) regression.

## Fits in architecture
The ingestion stage feeding every engine ([`signal-flow.md`](../architecture/signal-flow.md) Step 2 →
[`scoring-engines.md`](scoring-engines.md)). The schema hash is the seam between training and runtime;
the drift monitor is the (currently advisory) early-warning sensor — see F-008.

## Discussion (filled in-session)
- **Ambiguities:** 2026-06-05 — **dimension drift in the docs:** code is 38-dim (`CANONICAL_FEATURE_DIM=38`), but CLAUDE.md / `schemas.md` say "35-dim", and the source's own line-45 comment still says "= 32". Authoritative = `:76`. CLAUDE.md/schemas.md should be corrected to 38 (v2.0 was 35).
  - **RESOLVED 2026-06-11:** CLAUDE.md, `schemas.md` (§4.1, incl. the full 38-name tuple), and `architecture.md` corrected to 38-dim (Truth Maintenance pass, F-016 session). Remaining: the source's stale `:45` inline comment `= 32` is a *code* comment (out of scope for the doc-only pass) — a future code-touch should fix it.
  - **FULLY CLOSED 2026-06-25:** the deferred code comment is fixed (`feature_schema.py:45` `= 32` → `= 38`), and two living docs the 2026-06-11 pass missed are now corrected to 38-dim: `conventions.md:44` and `signal-flow.md` Step 2 (which also cited a non-existent `FeaturePipeline.transform(candle, history)` → corrected to `FeaturePipeline.run()`, batch enrich). `testing.md:107` label updated too. Historical/point-in-time docs (`docs/analysis/`, `docs/plans/`, archives, `human-language-analysis/`) deliberately left at "35-dim" per §6.2 rule 4 (preserve history). Note: many remaining "35-dim" hits are *correct* — they refer to the v2.0 model dim (`SCHEMA_V2_FEATURE_DIM=35`), not the current canonical schema.
- **Risks:** 2026-06-05 — F-008: drift is detected but not acted on (no gate/size-down); a regime shift can degrade silently.
- **Blockers:** 2026-06-05 — any schema change is load-bearing: it invalidates the baseline and all trained models keyed to `FEATURE_ORDER_HASH`.
- **Wiring note:** 2026-06-16 (STORY-1.6) — `check_compatibility` kept its `fail_closed=True` safety default (a TruthConflict resolved toward safety, not the test's old fail-open expectation; test updated to `test_unregistered_fail_closed`). Live caller is `MLGaussianEngine` only; **spine-neutral on the active config** (`gaussian_impl=heuristic`, so the ML path is not exercised by the governing backtest — golden ledgers byte-identical, 180 passed).
- **Findings (F-076, CH-htfcrt-parent-candle-smc-v1):** 2026-08-15 — schema extended 39→48 (v4.0→v5.0): 9 new SMC primitives (order block, FVG, breaker, mitigation, PDH/PDL distance, EQH/EQL distance, `change_of_character`) registered as ontology `derived_metrics`/`structural_states` (FM-075..FM-083) and emitted by a new `FeaturePipeline.compute_smc_features()` step. This doc's line citations and dim counts were also found stale at **38** (pre-dating even the v4.0 39-dim bump — a pre-existing drift not caused this session) and are corrected above to the current 48-dim/v5.0 state, matching the citations exactly (verified by grep, not carried forward from memory). Consequence accepted by the user: freeze-pin regenerated (new vector SHA), all 6 model families (zone_gate/rr/rr_fusion/gaussian/bitnet/tradenet) are now stale on the old ≤39-dim schema — `zone_registry.json`'s fail-closed `feature_order` load guard means those gates stay exactly as inert/degraded as before, not worse; retraining is separate, not-yet-authorized follow-up work. See [`docs/current-findings.md`](../current-findings.md) F-076.
- **Feature states as the TV/trader landing zone (2026-09-03):** The encoder (`src/features/feature_states.py`) is the declared-value→declared-state interpreter ("Features measure. States interpret."). Resolver occupancy consumes those states; the live engine does not. A trader saying "stop hunt" is describing FM-058 `liquidity_sweep` (`BuySideSweep`/`SellSideSweep`/`NoSweep`), not the word SWEEP. Comparison above this layer (English ↔ CRT enum) is the TV report's vocabulary artifact. Encoder remains shadow/resolver-path, not spine-consumed. P-FLOW-03 CURRENT pin; P-FLOW-17 is the missing per-bar evidence join on the construction trace.
- **Parquet vs formula fidelity (2026-08-27):** XAUUSD `clean_labels` 38 overlapping columns are bit-identical to HEAD `FeaturePipeline` and match `candle_math` / `derived_math` identities on stored OHLC. Schema hash still differs (38 vs 48). F-061/F-066 remain formula-identity defects, not save errors. Snapshot: [`docs/analysis/parquet-formula-parity-2026-08-27.md`](../analysis/parquet-formula-parity-2026-08-27.md).
- **2026-09-03 — spine citation pass:** named 27 previously unreferenced spine paths under Code covered (path existence on the GCMC spine join; not a behavior claim, not G001, not a file:line citation. Source still wins.).
- **2026-09-05 — the 48-slot lineage surface is queryable, and the v5.0 SMC slots got their first PIT class.** Two things that had been true-but-invisible since the F-076 bump:
  - `scripts/analysis/feature_38_lineage_census.py` **fails closed** when its hand-curated `LINEAGE` table does not cover every canonical name, so from 2026-08-15 (v5.0) it could not run at all and the shipped artifact silently stayed at 39 rows. `feature_surface_query --summary` reported this honestly as `pit: {…, None: 9}` / `closure: {CLOSED: 39, None: 9}`. The 9 SMC entries were added to the census **source** (never to the generated artifact) and the census regenerated: **48/48 rows, no `None` PIT bucket**, smoke PASS on the full XAUUSD corpus (47,197 rows, 48/48 canonical columns). PIT classes assigned from the existing vocabulary after reading all 577 lines of `src/features/smc/`: six are `STRUCTURE_WITH_CAUSAL_SWING` (they reach geometry only through `_geometry.detect_causal_swings`, confirmed at lag `k`), and **three join `CAUSAL_DELAYED_PUBLICATION`** — `fvg_distance` (zone stamped at the middle candle, undetectable until `bars[i+1]` closes) and `pdh_distance`/`pdl_distance` (reference the last *closed* D1 parent). **Closure was deliberately NOT moved** — that is a separate authorized certification act, so those 9 still read `NOT_IN_CLOSURE_AUDIT`.
  - `feature_surface_query` gained `--lineage` plus two per-slot blocks derived from the **live** authorities: `SEMANTIC_STATE` (from `FeatureStateEncoder`) and `RESOLVER_BINDING` (from `CRTStateResolver.required_when_features`). These exist to keep three questions apart that an external design doc collapsed into one: **13** vector slots declare L2 states · **13** features are named in a `when:` clause, but that is **10 canonical + 3 non-vector**, not the same 13 · and **48** canonical names are *supplied* to the resolver by `resolver_supply` regardless. `volatility_regime`, `volume_spike` and `change_of_character` are stateful and read by **no** predicate — the source-level answer to "why is CHoCH ignored?". Also corrected: the encoder's non-vector stateful vocabulary is **six** names, not the three `crt_state_resolver.py`'s own comment listed (the three FM-071/072/073 magnitude states were missing); `resolver_supply.py`'s docstring had already flagged this. Pinned by 8 new tests in `tests/test_feature_surface_query.py`. Query surface only — no behavior change, no authority (§6.5).
