# Topic: Feature Schema, Pipeline & Drift

> **Topic-visibility unit.** The canonical feature contract every engine consumes, the pipeline that
> builds it candle-by-candle, and the drift monitor that watches it. (Promoted from a stub row.)
>
> Created: 2026-06-05 · Updated: 2026-06-26 (added "Why `stream()` is more than CSV parsing"; F-039 L3-coverage) · Status: living

## In plain language
Every engine scores the same fixed, ordered list of numbers per candle — the **canonical feature
vector**. Its order is frozen and hashed so a model trained on one ordering can never be silently fed
another. The schema is currently **38-dimensional** (schema v3.0: the 35 v2.0 features plus three
liquidity/volume features). A pipeline turns raw OHLCV into that vector with no lookahead; a monitor
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
- [`src/features/feature_schema.py:46`](../../src/features/feature_schema.py) — `CANONICAL_FEATURES` — the frozen ordered tuple (38 entries; v2.0 indices 0–34 + v3.0 indices 35–37).
- [`src/features/feature_schema.py:76`](../../src/features/feature_schema.py) — `CANONICAL_FEATURE_DIM` — `38` (asserted == len(CANONICAL_FEATURES)); `SCHEMA_V2_FEATURE_DIM` `35` is the back-compat sentinel.
- [`src/features/feature_schema.py:122`](../../src/features/feature_schema.py) — `FEATURE_ORDER_HASH` — SHA-256[:16] of the order; the load-bearing schema hash.
- [`src/features/feature_pipeline.py:135`](../../src/features/feature_pipeline.py) — `FeaturePipeline` — raw OHLCV → enriched df + `(N,38)` vectors; `run()` at :775.
- [`src/features/feature_monitor.py:63`](../../src/features/feature_monitor.py) — `FeatureMonitor` — rolling-window drift detector (window 500; hard Z>3.0, soft Z>2.5 at :30–33).
- [`src/features/dataset_validator.py:1`](../../src/features/dataset_validator.py) — pre-training dataset gate (schema completeness, pairing, min-samples).
- [`src/features/feature_schema.py:247`](../../src/features/feature_schema.py) — `FeatureSchemaRegistry.check_compatibility` — `fail_closed=True` safety default (unknown version → reject). **2026-06-16 (STORY-1.6):** now has a live caller — `MLGaussianEngine` registers its model's stored `feature_order_hash` at load and calls `check_compatibility` in `compute()`; on equal-length/order-mismatch it returns the 0.5 fallback rather than scoring on misaligned features (the silent-corruption case the registry exists to catch). Was previously dormant (only `trainer.py` registered).

## Ins / Outs
- **Ins:** raw OHLCV DataFrame (timestamp/open/high/low/close; volume optional → 0.0 for FX). Drift monitor consumes `retest_depth`, `body_ratio`, `disp_strength` per opened trade.
- **Outs:** a 38-float vector in canonical order + enriched df (`FeaturePipeline.run`); `build_features(row)` → 38-key dict; drift severity (`"hard"|"soft"|"none"`) attached to backtest output (`BacktestMetrics.distribution["feature_drift"]`).

## Entry points & validations
- **Reached via:** `FeaturePipeline` is built inside `runtime.backtest_v2.BacktestRunner` (and the live hook). The monitor is wired in `BacktestRunner.__init__` (`backtest_v2.py:1451`), updated on `TRADE_OPENED` (`:1759`), logged at `:1857`.
- **Validated by:** `FEATURE_ORDER_HASH` (any reorder invalidates the baseline → requires `baseline_capture.py`); the import-time `assert len == CANONICAL_FEATURE_DIM`; `dataset_validator` before training; no-lookahead streaming contract.

## Tests
- [`tests/test_feature_pipeline.py`](../../tests/test_feature_pipeline.py) — schema completeness, vector shape, no-NaN, determinism, zero-volume FX fallback.
- [`tests/test_schema_contracts.py`](../../tests/test_schema_contracts.py) — `FEATURE_ORDER_HASH` stability + v2.0→v3.0 back-compat slicing.
- [`tests/features/test_feature_schema_registry.py`](../../tests/features/test_feature_schema_registry.py) — registry/version + model feature-dim matching.

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
