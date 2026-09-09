# Plan — Register absolute ATR as a first-class ontology identity, fix F-072's 2 live sites

## Context

Previous phase of this session (fully executed, committed on `feature/truth-registry-v2`,
commits `788d499`…`2d9df3e`): restored 1,838 uncommitted files to git (half of `src/`, the
entire Semantic OS, CI, the pre-commit hook), and registered findings F-071/F-072/F-073
correcting and extending an earlier 27-hole architecture map. See that history in
`docs/current-findings.md`.

This phase addresses **F-072**: `compute_crt_levels` (`src/core/gate_intelligence.py:24-84`)
requires price-unit ATR, but the canonical `atr` feature is close-relative
(`atr_14_raw/close`). Three call sites feed the ratio into price-unit SL/TP arithmetic.

**Why now, and why this scope.** Verification (this session) found the root cause is not
three independent bugs — it's a **missing ontology node**. Absolute ATR (the quantity these
sites actually need) has no registered FM identity; it exists under three different names
(`atr_14_raw`, `atr_14`, `state.atr_abs`) with no single source of truth. The ontology
already documents this gap in its own words at `market_ontology.yaml:932`: *"No first-class
FM id exists for the bare absolute-ATR intermediate."* The same missing-node class has
already produced this exact defect **twice before** it hit F-072: the FM-050 runtime-metadata
mislabel (2026-07-19, 4 sites) and the FM-028 `depends_on` correction (2026-07-31). Patching
the 3 call sites without registering the node would be the fourth recurrence of the same root
cause — and would also violate CLAUDE.md §3.3b/§6.6 (new/renamed quantities are registered
through the ontology → registry chain first; "never local formula math").

**Reachability, verified this session (changes urgency, not scope):**

| Site | Status |
|---|---|
| `live_engine_hook.py:916` | Dead — `HookedLiveEngine` is never instantiated (F-073, parked) |
| `research/model_runners/adapters/execution_plan.py:279` | Registered in the model-runner registry, never actually run (no output under `results/model_runners/`) |
| `config_layer/execution_planner.py:390,403,406` | **Actually exercised** — `scripts/research/live_path_replay.py` ran it (BNB/BTC/ETH/SOL, `results/live_path_replay/`), but its own conclusion (0/35 trades reach execution — 3 unrelated upstream blockers) doesn't depend on entry-price geometry, and no registered finding cites this artifact. So: no contaminated conclusion today, but a live landmine the moment upstream blockers are fixed. |

**F-073 (no live rail) is explicitly parked** — scoped this session (repair = fix one bad
import + implement a `simulate_one` method that was speced but never built, for a
`write=False` diagnostic tool; the underlying `HookedLiveEngine` class already passes 36/36
tests) but deliberately not decided. This plan's work is valid and complete under either
future outcome of that fork.

## What to build

### 1. Register the ontology node

In `configs/formulas/market_ontology.yaml`, add a new `rolling_indicators` entry for
absolute ATR (proposed `FM-071` — next free id; confirm against the live registry at
execution time in case another id landed since). Model it on the existing `FM-041` (`atr`,
close-relative) entry immediately above it (`market_ontology.yaml:1065-1096`):

- `formula`: `SMA(<feature_pipeline.atr_period>) of true_range` (no `/close`)
- `depends_on: [true_range]` (FM-040)
- `units: price_absolute` (matching FM-040's convention, not FM-041's `dimensionless`)
- `source_of_truth`: both real producers — `feature_pipeline.py` (`atr_14_raw`, the pre-division
  intermediate inside `compute_canonical_volatility_features`) and `crt_engine_v2.py`
  (`state.atr_abs`, `compute_atr` at `:869-882`) — note in `semantics.description` that these
  are the same quantity computed twice on two independent code paths (not yet unified;
  unifying the *implementation* is out of scope here, only the *identity* is being registered).
- Cross-link: update FM-041's own note to point at the new node instead of only describing
  the gap in prose.

### 2. Re-point the two existing gap acknowledgments

- `market_ontology.yaml:932` (FM-028's note) — replace *"No first-class FM id exists…"* with
  a reference to the new node; change `depends_on` from `[candle_range, true_range]` to
  `[candle_range, <new-FM-id>]` if that's a closer match to what `displacement_atr_ratio`
  actually consumes (check `derived_math.displacement_atr_ratio`'s signature first).
- `market_ontology.yaml:1454-1456` (the `volatility_regime` node's note, FM-050 lineage) —
  same treatment: point `depends_on` at the new node instead of describing the workaround in
  prose.

### 3. Fix the 2 live (non-dead) call sites

- `src/config_layer/execution_planner.py:390,403,406` — `close` is already in local scope
  (`:389`). Change `atr = float(features["atr"])` to consume the absolute form:
  `atr_abs = float(features["atr"]) * close` (or read a newly-emitted absolute-ATR feature if
  one exists on this code path — check `features` dict contents at the call site first; if
  the feature pipeline doesn't emit an absolute form on this path, the multiply-by-close
  derivation is the correct fallback, matching the existing FM-030/031 `atr_absolute` arm
  precedent at `market_ontology.yaml:725,763`). Use `atr_abs` in the `0.1 * atr` LIQ_SWEEP
  branches.
- `src/research/model_runners/adapters/execution_plan.py:279-287` — same treatment;
  `close` availability needs a quick check at the call site (verify before assuming, unlike
  `execution_planner.py` where it's confirmed in scope).
- **Leave `live_engine_hook.py:916` alone** — F-073 is parked, so this site stays dead and
  unfixed; touching it now would be scope creep into the parked fork.

### 4. Extend `feature_math_lint.py` (the guard)

`scripts/analysis/feature_math_lint.py` currently enforces *who may derive a registered
name*. Add a second, narrower check: flag a call site where a name known to be
close-relative (`atr`, and by the same pattern `ema_spread`/`momentum_score` under the
default `normalization_basis`) is passed into a function/parameter whose docstring or
existing usage establishes it expects absolute/price-unit input, without an accompanying
`* close` (or equivalent) in the same expression. This is a narrower, more heuristic check
than the existing derivation lint — scope it conservatively (a few known dimensional pairs,
not a general unit-inference system) and expect it to need a `_KNOWN_DIVERGENCES`-style
allowlist for the FM-061-class consumers that read `atr` correctly today.

## Verification

1. `python scripts/governance/seed_semantic_os.py --check` and the ontology's own registry
   validator (`python -m features.registry` or whatever `validate_registry()` entry point
   `CLAUDE.md §6.6` names) — new node passes schema, no `UNKNOWN_*` dangling refs.
2. `pytest tests/test_formula_registry.py tests/test_feature_lineage.py tests/test_candle_math.py tests/test_derived_math.py` — the existing ontology floor stays green (these are in
   `GREEN_FLOOR`).
3. Byte-identity check on the canonical feature vector for at least one instrument (XAUUSD
   freeze-pin, per the FM-030/031 precedent) — registering a node and fixing 2 non-canonical
   call sites must not change any of the 39 vector values. `tests/test_feature_layer_freeze.py`.
4. `pytest tests/test_execution_planner.py tests/test_model_runners_execution_plan.py` — the
   two fixed call sites' existing test suites must still pass; add a new assertion that the
   LIQ_SWEEP entry-price offset is now `~0.1 * atr_abs` (price-unit magnitude), not
   `~0.1 * atr_ratio`.
5. Re-run `scripts/research/live_path_replay.py` for at least BNBUSDT and diff its
   `results/live_path_replay/` output before/after — since its own conclusion doesn't depend
   on entry-price geometry (verified above), the diff should be null or extremely narrow; if
   it changes trade counts, that's a signal something else was silently depending on the bug.
6. `python scripts/analysis/feature_math_lint.py --check` — 0 new violations after the guard
   extension (only pre-existing pinned divergences).
7. Update `docs/current-findings.md` F-072: flip `Status: OPEN` → `RESOLVED` (or partially —
   note explicitly that `live_engine_hook.py:916` remains unfixed pending F-073), per the
   §6.2 Findings Mandate, same turn as the code change.
