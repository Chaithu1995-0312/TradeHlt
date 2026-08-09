# Feature Layer — Working Tracker (opened 2026-07-19)

> ### FREEZE (2026-07-20) — queue closed for free-form work
>
> **`FEATURE_LAYER_MUTATION_FREEZE = ACTIVE`**  
> Policy: [`docs/governance/feature-layer-mutation-freeze-2026-07-20.md`](../governance/feature-layer-mutation-freeze-2026-07-20.md)  
> Pin + vector regression: [`docs/governance/feature-layer-freeze-pin-2026-07-20.json`](../governance/feature-layer-freeze-pin-2026-07-20.json)  
> Floor: `tests/test_feature_layer_freeze.py`  
> **Engineering focus shifted to:**
> [`backtest-runtime-roadmap-2026-07-20.md`](backtest-runtime-roadmap-2026-07-20.md)
>
> Do **not** start a parallel feature tracker. Residual items proceed only as
> **accepted future programs** listed in the freeze pin (M16 consumer phase, T-5/T-6,
> T-11 feeder handshake, T-17/18/19, stateful-6, superseded-vector migration with plan).

**Purpose:** one list, worked one item at a time, no drift. Opened at user request after the
2026-07-18/19 feature-governance session. Update this file as items close; do not start a new
tracker.

**Scope note:** this file is a *working queue*. It does not grant authority. Economic/activation
claims still require the CLAUDE.md Section 6.5 Authority Ladder. **As of 2026-07-20 the queue
is FROZEN** except accepted future programs — see banner above.

---

## 0. CORRECTION FIRST — two things I reported earlier were wrong

### C-1. "MACD is deferred to a named B2/B3 review" — WRONG, based on a stale comment

`configs/formulas/market_ontology.yaml:442` says *"Full FM-id registration + parity wiring is a
separate architectural review (deferred, B2/B3)."* **That comment is stale.** MACD was
certified and promoted by the *successor* programme without ever going through B2/B3:
`docs/governance/feature_completion_alignment_census-2026-07-14.json:45-47` lists `macd_line`,
`macd_signal`, `macd_hist` as `PROMOTED_PRODUCTION`, `D2_FORMULA: PASS`,
`D9_PRODUCTION_BINDING: BOUND_CANONICAL_VECTOR` (indices 16/17/18).

What actually remains for MACD is **only ontology registration debt** — tracked as
`M16-WU-ONTOLOGY-REGISTRATION` (Priority 7), `BLOCKS_ACTIVATION: false`. Not a review, not a
gate. **Fixing the stale ontology comment is itself a tracked item (T-9 below).**

### C-2. The "B0/B1/B2A/B2B/B3" ladder was ABANDONED mid-way, not paused

| Phase | Real status | Evidence |
|---|---|---|
| B0/B1 | **COMPLETE** — identity governance only, `PRODUCTION_BEHAVIOR_CHANGED=NO` | ontology v1.2, `tests/test_b0b1_feature_semantic_migration.py` 14 green |
| B2A | **COMPLETE — verdict PROMOTE** (eligibility only; *"activation authority NONE"*) | F-053; `docs/governance/b2a_feature_candidate_certification-2026-07-12.{json,md}` |
| B2B | **FROZEN / KILLED** — superseded | `docs/current-findings.md:765-768`: *"bottom-up certification replaces the B2B-first direction"* (F-054) |
| B2 activation | **NOT STARTED** — reframed as **"L6 ACTIVATION"** | `docs/current-findings.md:763` |
| B3 | **Never run as B3.** Its ATR/RSI boundary-freeze half executed inside F-054 (freeze lifted, FM-040..046); its volume/session/liquidity half absorbed into L1–L4 DAG certification | |

So: **do not plan work in B-phase terms.** The live programme is the L0–L6 DAG certification
(F-054) and its remediation frontier (below). Phase letters are used inconsistently across docs
— "B2" and "B2B" are interchanged in places, and B0 is never defined separately from B1.

---

## 1. The authoritative frontier ALREADY EXISTS — do not invent a parallel list

`docs/governance/feature_completion_alignment_census-2026-07-14.json:3127-3348` defines **8
prioritized work units** (`M16-WU-*`). Identity certification is **exhausted** (48 DAG nodes:
46 PROMOTED_PRODUCTION, 2 SUPERSEDED, 0 READY, 0 BLOCKED):

```
FEATURE_IDENTITY_FRONTIER_EXHAUSTED:   YES
FEATURE_COMPLETION_FRONTIER_EXHAUSTED: NO
FEATURE_PROGRAM_CLOSED:                NO
NEXT_AUTHORIZED_ACTION:                STOP     <- pending user adjudication
```

| P | Work unit | Blocks activation? |
|---|---|---|
| 1 | `M16-WU-SESSION-ENCODING` — canonical session int8 0/1/2 permuted vs `SESSION_MAP`/dashboard | **yes** |
| 2 | `M16-WU-TREND-STRENGTH-COLLISION` — `dual_engine` local `trend_strength = abs(ema_spread)` != canonical | **yes** |
| 3 | `M16-WU-VOLREGIME-S05` — `s05_grid` reads string `TRENDING`, canonical is int8 tercile | **yes** |
| 4 | `M16-WU-SUPERSEDED-VECTOR-MIGRATION` — FM-030/031 certified but UNBOUND; vector still emits superseded legacy dims | **yes** |
| 5 | `M16-WU-FM025-PROVENANCE` — FM-025 certified with empty SHA | **yes** |
| 6 | `M16-WU-EMPTY-SHA-FAMILY` — 26 features with empty/placeholder SHA | no |
| 7 | `M16-WU-ONTOLOGY-REGISTRATION` — MACD family + L3/L4 FM registration (see C-1) | no |
| 8 | `M16-WU-L6-PREP` — activation readiness | **yes** |

**Note P1/P2/P3 are consumer-alignment defects** — the canonical feature and its *consumer*
disagree on encoding. These are live correctness issues, higher priority than any registration
work.

---

## 2. This session's items, merged in

| ID | Item | State |
|---|---|---|
| **T-1** | Config-driven indicator periods (11 keys) + Section 6.5 scoped exception | **DONE** — parity-proven byte-identical |
| **T-2** | `feature_pipeline.py` docstrings 32 -> 38 (4 sites) | **DONE** |
| **T-3** | `ma_200` restore + `ma_periods: [20,50,200]` | **DONE 2026-07-19** — verified drop still 78, vector unchanged |
| **T-4** | `lookback` / `config_key` duplicate source-of-truth (grew 4 -> 9 entries) | **DONE 2026-07-19** — enforced by `tests/test_ontology_config_parity.py`; see section 16 |
| **T-5** | `_warmup_budget = 300` over-sized vs measured 78 | **OPEN** (deferred by user) — see SF-006. Note its original arithmetic was never load-bearing (ma_200 is not canonical) |
| **T-6** | `finalize()` survivorship guard is advisory-only (logs, never raises) | **OPEN** (deferred by user) — SF-006 |
| **T-7** | `causal_structure.py` `_DOUBLE_SWEEP_WINDOW_DEFAULT = 5` was an independent copy of the batch `window` (while `SWING_WINDOW` IS shared by import) | **DONE 2026-07-19** — added `feature_pipeline.resolve_double_sweep_window()` as the single source; both public `causal_structure` fns default to `None`-means-config (explicit arg still wins); the literal default is deleted. Divergence proof: batch == live at windows {3,5,8}, and the value FLIPS 0->1 at 8 (knob is live, not inert). Sub-gap found+fixed: `FeatureStore._liquidity_sweep_history` was `maxlen=10`, which would have truncated any window >10 — now `max(10, window)`, byte-identical today |
| **T-8** | `feature_builder.py:45-46` `config.get("ema_fast_period", 9)` / `("ema_slow_period", 21)` — same values as T-1 under different key names with soft defaults | **DONE 2026-07-20** — dead attrs removed; period authority = `feature_pipeline.ema_*_span` only |
| **T-9** | Stale ontology comment `market_ontology.yaml` indicator_identities ("deferred, B2/B3") — see C-1 | **DONE 2026-07-20** — SUPERSEDED comment + MACD FM-047/048/049 registration status recorded |
| **T-10** | `behavior_census` could not see the feature layer (dir excluded AND function-body constants never collected) | **DONE 2026-07-19** — both gaps closed additively; see section 18 |
| **T-11** | Live ingress substituted silent defaults for missing feeder fields | **DONE 2026-07-19 (fallbacks)** — all silent defaults removed, fail-closed; see section 19. **Period-symmetry vs the external feeder remains OPEN** (needs the version handshake) |
| **T-12** | XAUUSD 2-month backtest | **RAN 2026-07-19** — see §13 (`run_20260719_021925_XAUUSD`, 0 trades: all candidates off-session). Original blocker (L2 gate rejects `results/` location) resolved by exporting to `data/`. Closable on review. (This cell previously read "never ran / PAUSED" — reconciled 2026-07-19 per §6.2 against the §13 run record and the `:1121` status line.) |

Detail for T-4..T-11 lives in
`docs/analysis/session-findings-2026-07-18-xauusd-window-and-feature-governance.md` (SF-001..007).

---

## 3. User decisions recorded (do not re-litigate)

- **Stateful detection (6 features)** — `double_sweep`, `sweep_detected`, `liquidity_sweep`,
  `break_of_structure`, `higher_high`, `lower_low`: **EXCLUDED for now**, revisit in a future
  phase once the feature pipeline is stable. (Consistent with the ontology's own standing
  boundary: *"Stateful detection state-machines (BOS/CHOCH/pivot) remain out of this layer"* —
  these were certified LEDGER-ONLY with no ontology/registry edit.)
- **`ma_200`** — restored (T-3), not left deleted.
- **Warmup guard** (T-5/T-6) — deferred, recorded as findings, not implemented.
- **Other instruments** (DOGE/XRP data-precision observation) — out of scope; data may be stale.
- **MT5 integration** — parked for future paper-trade / automation phases.
- **Consumer-alignment defects (M16 P1/P2/P3)** — `M16-WU-SESSION-ENCODING`,
  `M16-WU-TREND-STRENGTH-COLLISION`, `M16-WU-VOLREGIME-S05`: **DEFERRED to the future phase that
  works on `live_engine_hook`** (user decision 2026-07-19). They remain live correctness bugs and
  all three still carry `BLOCKS_ACTIVATION: true` — deferring them defers activation, which is
  the accepted trade.

---

## 4. Answer to the standing question: does "16/38 mapped" gate configurability?

**No — these are two different axes, and conflating them would misdirect the work.**

| Layer | Artifact | Executable? | What it governs |
|---|---|---|---|
| **WHAT** | `configs/formulas/market_ontology.yaml` | **NO** — `formula:` strings are documentation, explicitly *never* `eval`'d ("CONFIG-DECLARED, CODE-EXECUTED") | *meaning* / identity (FM-0NN) |
| **HOW** | `configs/production/*.json` | values only | *parameters* (periods, thresholds) |
| **CODE** | `feature_pipeline.py` etc. | yes — sole computation authority | the actual math |

So you **cannot** "import the YAML into the pipeline" to execute formulas — that is not what the
ontology is, and the registry deliberately holds only 15 scalar callables (rolling indicators
have *no* scalar form by design).

**Configurability comes from the HOW layer, and does not require a WHAT-layer FM id.** Today's
migration proves it empirically: of the 11 periods made configurable, only **4** correspond to
features with an FM id (rsi_14/atr/ema_fast/ema_slow). MA periods, Bollinger, MACD periods and
`trend_strength_window` were made configurable **despite those features having no FM id at all**.

Practical reading: registration (16/38) and configurability are independent. Register for
*meaning and lineage*; externalize to config for *tunability*. Neither blocks the other.

---

## 5. Suggested order of work

Consumer-alignment defects first — they are live correctness issues, cheap, and unblock the
rest:

1. **T-9** (stale comment) + **T-4** (parity test) — minutes each, closes debt this session created.
2. **M16-WU-SESSION-ENCODING** (P1) — canonical vs consumer disagreement, blocks activation.
3. **M16-WU-TREND-STRENGTH-COLLISION** (P2) and **M16-WU-VOLREGIME-S05** (P3) — same class.
4. **T-10** (`behavior_census` scan dirs) — makes the remaining ~35-constant backlog *measurable*
   before deciding whether to extend the Section 6.5 exception further.
5. **T-11** (live-path period verification) — highest consequence, needs a design decision.
6. **T-7 / T-8** — small, contained.
7. **T-5 / T-6** — deferred by user; revisit when the pipeline is stable.
8. **M16-WU-SUPERSEDED-VECTOR-MIGRATION** (P4) — the FM-030/031 binding gap. Large: touches
   `CANONICAL_FEATURES`, pipeline emission order, and model retrain/rebind. Explicit stop
   boundary: *"No silent dim swap; requires migration plan + retrain gates."*

**Standing caveat carried from the census:** the F-019..F-025 entry-information null bounds the
expected downstream *economic* value of this entire programme. The work is justified as
correctness/governance hygiene, not as an expected-edge improvement.

---

## 6. Why "only ontology registration debt" understates the cost (discussion, 2026-07-19)

Registration is not bookkeeping — **registration is what turns enforcement on.**

`scripts/analysis/feature_math_lint.py` is the tool that prevents a governed quantity from being
re-derived elsewhere. Its watch-list comes from `_registered_names()` (`:204-206`), whose
docstring is explicit: *"The governed feature set (ontology names) plus code/column aliases"* —
built by `load_ontology()` (`:51`). **A feature with no FM id is therefore un-flaggable by
construction**, regardless of how many divergent copies of its math exist.

Consequence for the 14 PROMOTED-but-unregistered features (MACD family, `session`,
`trend_strength`, `volatility_regime`, `hour_of_day`, `candles_since_retest`, and the 6 structure
features): any module may reimplement their math and **no check in this repo will notice**.
Contrast `body_ratio` (FM-010, registered) — the GD-001..GD-010 ledger exists *because* those
quantities had FM ids for the lint to key on.

Two live instances of exactly this failure mode already exist, both on unregistered features:
- **T-7** — `causal_structure.py` `_DOUBLE_SWEEP_WINDOW_DEFAULT = 5` independently copied the batch
  `window`. `double_sweep` is unregistered -> invisible to the lint. **Resolved 2026-07-19** (single
  source via `resolve_double_sweep_window()`), but resolved *by hand* — the lint still could not
  have caught it, so this remains a valid illustration of the registration-debt mechanism.
- **M16 P2** — `dual_engine` computes its own `trend_strength = abs(ema_spread)`, colliding with
  the canonical `trend_strength`. Also unregistered -> invisible to the lint.

So the census's `BLOCKS_ACTIVATION: false` is true in the narrow sense (it does not gate L6) but
misleading as a priority signal: registration debt is the *mechanism* by which the deferred
consumer-collision bugs became possible, and by which further ones can appear silently.

Mitigating: the work is `ESTIMATED_COMPLEXITY: M`, hash-neutral when descriptive, with a hard
stop boundary — *"No formula change; registration must match certified identities."*

---

## 7. `ma_200` — corrections to the record (2026-07-19)

- **`ma_300` does not exist** anywhere in `src/`, `configs/`, or `scripts/`. The moving averages
  are `ma_20`, `ma_50`, `ma_200` only. (Checked in response to a recollection of "ma200 ma300".)
- **`ma_200` is classified `IMPLEMENTATION_INTERMEDIATE`** by
  `scripts/analysis/phase1_run15a_quantity_role_adjudication.py:621`, grouped with `ma_20`,
  `ma_50`, `bb_*`, `prev_close`, `upper_wick`, `lower_wick`, `direction`, with consumers recorded
  as *"downstream pipeline features within same module."*
  **That classification is accurate for its siblings but NOT for `ma_200`:** `ma_20` really does
  feed `price_vs_ma20`/`ma_slope_20`->`trend_strength`; `ma_50` feeds `price_vs_ma50`; `ma_200`
  feeds **nothing**. It was bucketed by pattern, not by tracing actual consumers. Small
  documented-vs-actual mismatch — **new tracker item T-13**.
- **PROOF that `ma_200` never affected warmup** (measured, `head(400)` of the XAUUSD corpus):
  rows 78..198 have `ma_200 == NaN` and are **KEPT**; only rows 0..77 are dropped. Total drop 78
  vs `ma_200` NaN count 199 — the two numbers are unrelated because
  `dropna(subset=CANONICAL_FEATURES)` only inspects the 38 canonical columns and `ma_200` is not
  one of them. The old comment's arithmetic (`ma_200(200) + z-score(50) + swing(4) ~= 300`) summed
  a term that never participated. **True both before the deletion and after the restore** — which
  is why the restore did not, and could not, fix T-5.

| ID | Item | State |
|---|---|---|
| **T-13** | `phase1_run15a_quantity_role_adjudication.py:621` records `ma_200` as an intermediate "consumed downstream in same module" — it has zero consumers | **DONE 2026-07-20** — split from generic intermediate bucket; `consumers=[]` + accurate note |
| **T-14** | Ontology registration, partial: `macd_line` FM-047, `macd_signal` FM-048, `macd_hist` FM-049, `volatility_regime` FM-050 | **DONE 2026-07-19** |
| **T-15** | **PRE-EXISTING (not caused by this session):** `tests/test_feature_math_lint.py` is RED — 3 failures | **DONE 2026-07-20** — see section 20 |
| **T-16** | `feature_math_lint._registered_names()` excluded `rolling_indicators` -> all 11 windowed identities (FM-040..050) were UNPOLICED | **DONE 2026-07-19** — see section 11 |
| **T-20** | CRT `state.atr` vs canonical FM-041 `atr` | **DONE 2026-07-19** — DIAGNOSIS CORRECTED: not duplicate implementations of one quantity but a NAME COLLISION between two different quantities (absolute vs close-relative). Resolved by renaming `EngineState.atr` -> `atr_abs`. See section 17 |
| **T-21** | The lint's enforcement model assumes a scalar registry callable exists ("route through the registry"), which is **false by design** for `rolling_indicators`. Policing them therefore has no legal remedy path for legitimate producers | **OPEN** — design gap, surfaced by T-16 |
| **T-17** | FM-049 `macd_hist` — emitted value is z-scored by `compute_normalization`, not the raw difference | **FUTURE PHASE** (user-flagged to revisit) |
| **T-18** | FM-050 `volatility_regime` — window 200 + tercile cuts 0.33/0.66 still hardcoded, outside the Section 6.5 exception; sibling `_global_batch`/`_expanding_causal` identities unregistered | **FUTURE PHASE** (user-flagged to revisit) |
| **T-19** | `candles_since_retest` is **misnamed** — it counts bars since the last **liquidity_sweep**, not since a retest | **OPEN** — semantic finding, see below |

---

## 8. Ontology registration pass — result (2026-07-19)

**Registered 4** of the 14 `M16-WU-ONTOLOGY-REGISTRATION` targets, in `rolling_indicators`,
`lifecycle: registered`, no formula change:

| FM | feature | depends_on | notes |
|---|---|---|---|
| FM-047 | `macd_line` | `close` | `config_keys: [macd_fast, macd_slow]` |
| FM-048 | `macd_signal` | `macd_line` | `config_key: macd_signal` |
| FM-049 | `macd_hist` | `macd_line`, `macd_signal` | **emitted value is Z-SCORED** (compute_normalization overwrites in place) — recorded in the entry `note` so it can't be misread from the formula line |
| FM-050 | `volatility_regime` | `atr` (FM-041) | **no `config_key`** — window 200 + 0.33/0.66 cuts were deliberately NOT migrated; sibling `_global_batch`/`_expanding_causal` identities intentionally left unregistered |

**Verified:** `validate_registry() == []`; lineage edges resolve and `used_by` transposes
correctly (`atr` now shows `volatility_regime` among its 9 consumers);
`tests/test_feature_lineage.py` + `tests/test_formula_registry.py` **17 passed**; 38-dim vector
**unchanged** (3,871 rows, shape `(3871, 38)`, NaN-free) — registration is descriptive, as intended.

**The enforcement question that motivated this pass — MY CLAIM WAS WRONG. CORRECTED 2026-07-19
(E-001).**

I reported: *"registering these names puts them inside `feature_math_lint`'s watch-list. Result:
ZERO violations — no module re-derives them outside the registry. Clean."* **That result was
vacuous.** `feature_math_lint._registered_names()` iterates only:

```python
for section in ("primitives", "feature_compositions", "derived_metrics"):
```

**`rolling_indicators` is not scanned at all** (`grep rolling_indicators feature_math_lint.py` ->
no matches). Measured directly:

```
macd_line   policed_by_lint=False      body_ratio  policed_by_lint=True
macd_signal policed_by_lint=False      upper_wick  policed_by_lint=True
macd_hist   policed_by_lint=False
volatility_regime policed_by_lint=False
atr / rsi_14 / ema_fast  policed_by_lint=False
```

Zero violations because **the lint never looked**, not because the code is clean.

**What this registration pass actually delivered** (still real, just narrower than I claimed):
stable FM ids, DAG/lineage membership (`depends_on` + `used_by`), machine-readable identity, and
the documented z-scoring caveat on `macd_hist`. **It did NOT deliver lint enforcement.**

**Wider consequence — this is a pre-existing hole, not one I created.** All **11**
`rolling_indicators` names are unpoliced: `atr`, `rsi_14`, `ema_fast`, `ema_slow`, `true_range`,
`swing_high`, `swing_low` (FM-040..046, since 2026-07-12) plus my 4. So the F-054 promotion of
ATR/RSI/EMA to "first-class registered identities" also did not confer enforcement.

**Dry-run of closing it** (add `"rolling_indicators"` to that tuple — a one-line change): **8 new
violations surface, all `atr` re-derivations**:

```
analytics/sl_tp_comparator.py:358        config_layer/crt_engine_v2.py:2486
config_layer/crt_engine_v2.py:2562       core/feature_store.py:125
features/causal_structure.py:60          strategies/intent_builder.py:112
training/stage1_dataset_builder.py:334   research/secondlow_v1/detector.py:136
```

That is genuine signal — 8 sites re-deriving ATR outside the registry, currently invisible.
**New tracker item T-16.** Should be its own change with triage (pin as GD-0NN with evidence, or
route through the registry), not folded into a registration pass.

### Not registered, with reasons (do not retry blindly)

- `trend_strength` — **BLOCKED**: `depends_on: [ma_20]`, and `ma_20` is neither registered nor a
  base input, so `test_dependency_graph_acyclic_and_grounded` would fail. Unblock by registering
  `ma_20` first (precedented — `true_range` FM-040 is a registered non-canonical intermediate).
  Note its emitted value is **also z-scored**. Decide whether `ma_50`/`ma_200` follow for symmetry.
- `candles_since_retest` — **BLOCKED**: depends on `liquidity_sweep`, which is in the
  user-deferred stateful bucket.
- `session`, `hour_of_day` — **WRONG SHAPE**: pure timestamp derivations with no window;
  `computation_class` must be `rolling`/`rolling_stateful`, so declaring either would be false.
  Needs a placement decision — new section, or scalar registration in `derived_metrics` (which
  WOULD require real callables in `derived_math.py`, since that section's `impl` must resolve in
  `FORMULA_REGISTRY`).
- The 6 stateful-detection features — deferred by the user.

### T-15 — the lint floor was ALREADY red before this session

`tests/test_feature_math_lint.py`: `test_floor_is_green`, `test_pins_have_no_stale_durable_keys`,
`test_universe_reconciliation_with_census` all fail. **Established as pre-existing, not caused by
the registration:**
- The violations are exclusively `body_ratio`/`body_size`/`wick_size`/`upper_wick`/`lower_wick`
  (FM-001/002/003/004/010) — all registered long before this session. None of the 4 new names appear.
- `_durable_key` is computed from the **violation site's** `(file, qualname, target, kind,
  ast.dump(rhs))` — **nothing from the ontology** — so an ontology edit cannot stale a pin.
- Decisive: `src/config_layer/crt_sweep_taxonomy.py` is **unmodified in the worktree** (identical
  to HEAD) yet its GD-008/GD-009 pins are stale, i.e. the pins were already out of sync with
  *committed* code.
- The pytest floor scans a **wider universe** than the `--check` CLI (includes `scripts/` and
  `tests/`), which is why it reports more sites: `manual_backtest.py`, `strategy_backtest.py`,
  `s09_pattern_recog.py`, `test_feature_pipeline.py`, `crt_xauusd_runtime_trace.py`,
  `feature_math_drift_probe.py`, `live_path_replay.py`, `story_builder.py`.

Remediation is a separate work unit: re-adjudicate GD-006..GD-009 (retire via the manifest if
resolved, or re-pin the new sites) and triage the wider violation set. **Not attempted here** —
it is untouched pre-existing debt and mixing it into this pass would obscure both.

---

## 8b. Full-suite triage — 35 failed / 3284 passed (64 min, 2026-07-19)

Every failure below was tested for causality by **isolation** (temporarily removing my change and
re-running), not by inference.

### MINE — found and fixed (3)

| # | Failure / defect | Cause | Fix |
|---|---|---|---|
| 1 | **FM-050 declared `depends_on: [atr]` — a FALSE LINEAGE CLAIM.** No test caught this; found while triaging. | `compute_volatility_regime` reads `df["atr_14"]` (**absolute**, = SMA14 of true_range). FM-041 `atr` is `atr_14_raw / close` (**close-relative**, canonical idx 13). Different quantities. | `depends_on: [true_range]` (FM-040, the registered ancestor of the absolute chain) + explicit note. `true_range.used_by` now correctly `[atr, volatility_regime]` — **siblings**, not ancestor/descendant. |
| 2 | `test_feature_dag_layers::test_ontology_crosscheck_only_known_rollups` | My FM-050 added a 5th divergence to a 4-item `allowed` whitelist. **Isolation-proved mine** (passed with FM-050 removed). | Per user decision: tightened `_NODES["volatility_regime"]` from `["close","high","low"]` to `["true_range"]` + `"FM-050"`, so ontology and DAG agree exactly. **Alarm stays armed** — no whitelist suppression. M14B's conclusion unchanged; only edge granularity. |
| 3 | `test_config_reachability::test_no_dead_config_keys` | I added a `_comment_ema` key to `crt_engine` (a *scanned* section) -> flagged DEAD. Renaming to `_comment` did **not** help: the checker scans `crt_engine` but does not scan the brand-new `feature_pipeline` section at all, which is why `feature_pipeline._comment` passes. | Removed the key entirely. The EMA-collision disambiguation already lives in 3 places: `feature_pipeline._comment`, the `compute_canonical_ema_features` docstring, and the CLAUDE.md Section 6.5 exception. |

### PRE-EXISTING — isolation-verified, logged, NOT touched

| Failure(s) | Isolation evidence |
|---|---|
| `test_feature_dag_invalidation::test_transitive_downstream_of_atr` | Still fails with FM-050 removed. **User decision: log only, don't touch.** It asserts `volatility_regime` is downstream of `atr` — which contradicts both the code (`df["atr_14"]`, absolute) and the M14B analysis. Likely a stale expectation, but correcting a governance floor deserves its own change. |
| `test_reachability_golden` ×2 | Removing my entire `feature_pipeline` config section -> **identical** failures. Comparison artifact `config-reachability-report.json` was already modified in the worktree before this session. |
| `test_three_authority_surplus_census::test_freshness_summary_matches_live_scan` | Same isolation run -> **identical** `frozen=39 live=41`. Note `change_contracts.json` already referenced `feature_pipeline` twice, in a file I never touched. |
| `test_feature_math_lint` ×3 | `_durable_key` derives from the violation SITE's `(file, qualname, target, kind, ast.dump(rhs))` — **nothing from the ontology**. Decisive: `crt_sweep_taxonomy.py` is byte-identical to HEAD yet its GD-008/009 pins are already stale. |
| `test_geometry_census` ×2 | `geometry_census.jsonl` / `_summary.json` were both already modified in the worktree pre-session. |
| ~26 others | Not individually triaged. Includes several known-red floors (e.g. `test_agents_path_alignment`). |

**Net: of 35 failures, 2 were mine — both fixed.** The third fix (FM-050 lineage) was a real
correctness defect that *no test caught*; it surfaced only because triaging the crosscheck failure
forced me to read the M14B comment. Post-fix: `test_config_reachability`, `test_feature_dag_layers`,
`test_feature_lineage`, `test_formula_registry`, `test_feature_pipeline`, `test_candle_math` =
**63 passed**. 38-dim vector re-verified **unchanged** (3,871 rows, `(3871, 38)`, NaN-free).

---

## 9. `candles_since_retest` — context for the blocked dependency

The blocker is not incidental; it reflects what the feature actually measures.

```python
# feature_pipeline.compute_canonical_temporal_features
if "liquidity_sweep" in df.columns:
    sweep_groups = (df["liquidity_sweep"] != 0).astype(int).cumsum()
else:
    sweep_groups = df["retest_flag"].eq(1).cumsum()      # fallback
bars_since_sweep = df.groupby(sweep_groups).cumcount()
df["candles_since_retest"] = np.where(sweep_groups > 0, bars_since_sweep, 0)
```

**Despite its name, it counts bars since the last SWEEP, not since a retest.** The in-code comment
records this as a deliberate fix: grouping by `retest_flag` made `cumcount()==0` at every retest
candle (the retest candle *is* the first of its own group), producing zero variance in training
data. Grouping by sweep events yields N=2..5 at a typical retest candle — real signal.

Three consequences:
1. **Registration is genuinely blocked** — its true dependency is `liquidity_sweep`, which sits in
   the user-deferred stateful-detection bucket. Declaring `depends_on: [retest_flag]` to dodge the
   grounding test would be a false lineage claim. Correct to wait.
2. **The name is misleading** (T-19). Anyone reading `candles_since_retest` in a model or finding
   will reasonably assume retest-relative timing. Renaming is a canonical-schema change (index 34)
   — not cheap; may be better handled as an ontology `note` + alias when it is registered.
3. **There is a silent fallback path** — on a DataFrame lacking `liquidity_sweep` (minimal test
   frames, partial runs) the feature switches to the degenerate `retest_flag` grouping *without
   warning*, producing the zero-variance behaviour the fix was meant to eliminate. Worth a log line.

---

## 10. `session` / `hour_of_day` — placement design

**Constraint discovered while designing:** enforcement lives only in `primitives`,
`feature_compositions`, `derived_metrics` (T-16). So placement determines whether registration is
documentation-only or actually policed. This matters here more than anywhere else, because
`session` **already has a known 3-way collision**: pipeline hour buckets (`<8`/`<16`), the
`dataset_integrity` tradability calendar, and `inout.scanner.s06_scalping.session_hours_start/end`
(**7/17** — different values, different module). `M16-WU-SESSION-ENCODING` (P1, blocks activation)
is a *fourth* variant. This is exactly the class the lint exists to catch.

**Blocking prerequisite for any option:** `timestamp` is **not** a base input — the ontology's
`base_inputs` are `open/high/low/close/volume/close_delta/ref_high/ref_low/bos_level/disp_open/
disp_close/retest_close`. Any entry declaring `depends_on: [timestamp]` fails the grounding test.
Precedent exists for adding it: `ref_high`/`ref_low`/`bos_level` are declared leaves with the
comment *"structural — out of scope, a leaf."*

### Options

| Option | Mechanism | Enforcement? | Cost / risk |
|---|---|---|---|
| **A — `derived_metrics` + scalar callables** | add `timestamp` to `base_inputs`; write `hour_of_day(ts)` / `session(hour)` in `derived_math.py`; register in `DERIVED` | **YES** | **Type conflict**: `derived_math.py`'s charter is explicitly *"All functions are scalar (float -> float)"* for ATR/price-relative math. A datetime-in/int-out calendar projection violates both its stated contract and its documented purpose. Would need the module's charter widened. |
| **B — new `temporal_context` section** | new ontology section; extend `_ITERATED_SECTIONS`, `validate_registry` branch, `test_feature_lineage._entries()`, and the lint's section tuple | **YES** (if added to the lint tuple) | Honest semantics — these genuinely are neither scalar market math nor windowed indicators. Touches registry + tests + lint. Medium. |
| **C — `rolling_indicators`** | reuse existing section | **NO** (T-16) | Cheapest, but `computation_class` must be `rolling`/`rolling_stateful` — false for a per-bar calendar projection. Rejected: dishonest AND unenforced. |
| **D — leave unregistered** | document only | **NO** | Zero cost, but leaves the one feature with a known live 4-way collision completely ungoverned. |

### Recommendation

**B, sequenced after T-16.** Reasoning: (1) it is the only option that is both semantically honest
and enforceable; (2) `session`'s collision history is the strongest existing evidence that
enforcement is needed for exactly this feature; (3) doing T-16 first means the new section can be
added to a lint that is already section-aware, rather than building a second unpoliced tier.
Sequence: **T-16 (close the rolling_indicators hole + triage the 8 atr sites) -> add `timestamp`
to `base_inputs` -> create `temporal_context` with `session` + `hour_of_day` -> add the section to
both the registry iterator and the lint.**

Do **not** do B before T-16 — that would repeat this pass's mistake of registering into a tier
that looks governed but isn't.

---

## 11. ITEM 1 / T-16 — lint coverage for `rolling_indicators` (DONE 2026-07-19)

**Change (2 parts, `scripts/analysis/feature_math_lint.py`):**
1. `_registered_names()` section tuple += `"rolling_indicators"` — the actual coverage fix.
2. Two classifier corrections, because coverage surfaced 2 false positives:
   - `_COERCION_CALLS` += `asarray/array/astype/asfarray` — numpy dtype coercion carries its
     argument's class, exactly like `float()`. `np.asarray(atr, dtype=float)` on a *parameter* is
     transport. `np.asarray(high * low)` still recurses to a BinOp -> derivation.
   - `ast.BoolOp` moved out of the blanket-derivation branch and classified like `IfExp` /
     `_BOUND_CALLS`: derivation only if an operand computes. `x or 0.0` is null-coalescing
     defaulting, not arithmetic. `a > b or c > d` still resolves via its `Compare` operands.

**Method — violation-SET diff, not exit code** (the floor was already red, so pass/fail proves
nothing):

| Stage | Violations |
|---|---|
| Baseline (before any change) | **4** (`upper_wick`/`lower_wick` x2 files) |
| After adding `rolling_indicators` | **8** (+4 `atr`) |
| After classifier fixes | **6** (+2 `atr`, genuine) |

**SAFETY GATE PASSED:** `comm -23 baseline final` is **empty** — not one previously-detected
violation was masked by the classifier change. The only removals are the 2 confirmed false
positives. `tests/test_feature_math_lint.py` still fails on **exactly** the same 3 pre-existing
tests (`test_floor_is_green`, `test_pins_have_no_stale_durable_keys`,
`test_universe_reconciliation_with_census`) — **no new test breakage**.

**Triage of the 4 surfaced sites:**

| Site | RHS | Verdict |
|---|---|---|
| `config_layer/crt_engine_v2.py:2486` (`CRTEngine.initialise_range`, key `a44121317317d14d`) | `self.detector.compute_atr(candles, cfg.atr_period)` | **GENUINE** — second ATR implementation |
| `config_layer/crt_engine_v2.py:2562` (`CRTEngine.process_candle`, key `af495620f5557850`) | same | **GENUINE** — same |
| `core/feature_store.py:125` | `float(d.get("atr", 0.0) or 0.0)` | FALSE POSITIVE — fixed by the `BoolOp` change |
| `features/causal_structure.py:60` | `np.asarray(atr, dtype=float)` | FALSE POSITIVE — fixed by the coercion change |

Note the earlier dry-run predicted **8** new sites; the CLI surfaced **4**, because
`_SCAN_DIRS = ("features","core","config_layer","engines","runtime")` excludes the `analytics/`,
`strategies/`, `training/`, `research/` sites the ad-hoc dry-run had included. The pytest floor
scans a wider universe and may still report those.

### The blocker this exposed (T-20 / T-21)

The 2 genuine sites **cannot be resolved by either sanctioned mechanism**:
- **Cannot pin.** `test_grandfather_set_monotonic` asserts `CURRENT ∪ RETIRED == BASELINE` where
  BASELINE is exactly `GD-001..010`. A `GD-011` fails `current <= baseline` ("foreign pin ids").
  The ratchet is a deliberate one-way design — grandfathering was a one-time amnesty, and the
  test docstring explicitly names the workaround it blocks ("retire 2, add 2 back").
- **Cannot route.** The lint's remedy text says "route through candle_math/derived_math/registry",
  but `rolling_indicators` are **exempt from `FORMULA_REGISTRY` by design** — the registry holds
  no scalar ATR callable, because none exists for a windowed indicator. There is nothing to route
  to.

So the enforcement model has a structural gap for windowed identities (**T-21**), and the real
remedy for these 2 sites is architectural: make the CRT engine **consume** the pipeline's ATR
rather than compute its own from its own buffer with its own `crt_engine.atr_period` (**T-20**) —
a behaviour-affecting change requiring a parity proof, deliberately not attempted here.

**Net position:** the 2 duplicate ATR implementations are now **visible** instead of invisible,
which was the entire point of T-16. The floor stays red — but it was red before, and no
previously-green test was broken.

---

## 12. ITEM 2 — `session` / `hour_of_day` registration (DONE 2026-07-19)

**New ontology section `temporal_context`** — a THIRD computation class, chosen because both
existing sections would have required a false declaration:
- not `rolling_indicators` (`computation_class` must be `rolling`/`rolling_stateful`; a per-bar
  calendar projection has no window),
- not `derived_metrics` (its `impl` must resolve in `FORMULA_REGISTRY`, and `derived_math.py`'s
  charter is explicitly *"scalar float -> float"* ATR/price-relative math — a datetime-in/int-out
  projection violates both contract and purpose).

Entries: **FM-051 `hour_of_day`** (`depends_on: [timestamp]`), **FM-052 `session`**
(`depends_on: [hour_of_day]` — what the code actually does). `session` carries a `note`
documenting the 4-way collision.

**Prerequisite:** `timestamp` added to ontology `base_inputs` as a declared leaf — same rule as
`ref_high`/`ref_low`/`bos_level`, and it was **already** a raw input in
`feature_dag_layers._RAW_INPUTS`, so this aligned the ontology to the DAG rather than inventing a
concept.

**Wired into all 5 places** (missing any one leaves it half-governed):
| # | File | Change |
|---|---|---|
| a | `src/features/registry/__init__.py` | `_ITERATED_SECTIONS` += `temporal_context` |
| b | `src/features/registry/__init__.py` | `validate_registry()` branch — requires `formula` + `impl` + `computation_class == "calendar"`; CALENDAR-impl exemption from FORMULA_REGISTRY |
| c | `tests/test_feature_lineage.py` | `_entries()` + skip in `test_registered_plus_resolve_impl` |
| d | `scripts/analysis/feature_math_lint.py` | `_registered_names()` += `temporal_context` — **the enforcement point** |
| e | `scripts/analysis/feature_dag_layers.py` | FM ids added; `session` edge tightened `["timestamp"] -> ["hour_of_day"]` to match the ontology exactly (crosscheck divergence-free, same approach as FM-050) |

**Verified:** `validate_registry() == []`; `session`/`hour_of_day` `policed=True`; lineage grounded
(`session -> hour_of_day -> timestamp`, `timestamp ∈ base_inputs`); ontology<->DAG crosscheck clean.

### The payoff — a FIFTH session definition, found because registration turned the lint on

Violation-set diff surfaced 2 new `session` sites (nothing masked):

**1. `runtime/backtest_v2.py:1932` — GENUINE name collision, now FIXED.**
`session = self._session(candle.timestamp)` returns a **string** session name resolved from
`crt_cfg.session_windows` (config-driven), defaulting to `"OFF_SESSION"`. Canonical FM-052 is an
**int8 {0,1,2}** from hardcoded 8/16 cutoffs. Same bare name, **different type, different source,
different concept** — `semantic_class: name_collision_distinct`, the GD-006/007 category.
Since the ratchet forbids new pins, resolved the way those pins' own `review_trigger` recommends:
**renamed the local to `session_label`** (used on exactly 2 adjacent lines; behaviour-neutral) with
a comment stating it is the CRT-engine session LABEL, not the canonical feature. Violation cleared.

So the count of `session` definitions in this repo is now documented at **five**: pipeline int8
(8/16), scanner `s06_scalping` 7/17, `dataset_integrity` tradability calendar,
`M16-WU-SESSION-ENCODING`'s canonical-vs-`SESSION_MAP` permutation, and this CRT string label.

**2. `features/crt_feature_builder.py:144` — left open, deliberately.**
`str(raw_session ...).strip().lower()` is string NORMALIZATION of an already-supplied session, not
a re-derivation of the bucket — a false positive of the `.strip()`/`.lower()` family. **The module
is dead (0 callers, documented in `candle_math.py:14` and the gate2b adjudication rows).** Not
worth expanding classifier surface for a 0-caller file; logged rather than fixed.

**Final lint state: 7 violations** = 4 pre-existing (`upper_wick`/`lower_wick`) + 2 `atr` (T-20,
structurally unresolvable here) + 1 dead-module `session`. **Nothing masked at any step.**

---

## 13. ITEM 4 — XAUUSD 2-month backtest (RAN 2026-07-19)

**Run dir (for reuse — do not re-run):**
`results/XAUUSD/backtests/run_20260719_021925_XAUUSD/`
Artifacts: `XAUUSD_summary.json`, `XAUUSD_events.jsonl` (1,561 records),
`XAUUSD_crt_telemetry.jsonl` (1,245), `XAUUSD_report.txt`.
Input: `data/XAUUSD_W2026-03-23-to-2026-05-21.csv` (3,949 rows, parent sha `4d73f5ce…`).

**The blocker is cleared.** L2 gate returns **WARN**, not REJECT (`hard_failures: []`;
41 intra-session gaps, **0 missing candles**, largest 12 — within thresholds). Guard passthrough
confirmed: the path is returned unchanged, not rewritten.

**Dataset identity confirmed — the guard-substitution risk is definitively falsified:**
```
FeaturePipeline | finalize | rows_before=3949 rows_after=3871 drop=78 drop_pct=1.98%
```
3,949 in / 3,871 out — the 2-month window, **not** the 47,275-row corpus. This also confirms the
78-row / 1.98% warmup figure in a real run (the earlier "254 rows / 6.4%" was my error).

**Result: 0 trades.** Reported plainly; **no edge claim in either direction** (Section 6.5).

### The CRT state trace (the in/out-of-state data)

**Correction to my own plan:** I said transitions land in `XAUUSD_crt_telemetry.jsonl`. They do
**not** — that file holds aggregate counters (`kind: TRANSITION_COUNTER`, `RESET_ATTRIBUTED`,
`CANDIDATE_LIFECYCLE`, `DECISION_DISTANCE`, …) with no `event` field. The per-event transitions are
in **`XAUUSD_events.jsonl`** (327 `STATE_TRANSITION` records).

| Transition | Count |
|---|---|
| `RANGE -> SWEEP` | 285 |
| `SWEEP -> DISPLACEMENT` | 24 |
| `RANGE -> SHADOW_PENDING` | 5 |
| `SHADOW_PENDING -> SWEEP` | 5 |
| `SWEEP -> EXPANSION` | 5 |
| `EXPANSION -> RETEST` | 3 |
| `RETEST -> EXECUTION` | **0** |

State entry counts (`TRANSITION_COUNTER`): RANGE 943, SWEEP 290, DISPLACEMENT 24,
SHADOW_PENDING 5, EXPANSION 5, RETEST 3. `SHADOW_LEAK: 0` (clean).

### Why 0 trades — the SESSION filter, not the scorer

All 3 retests were **APPROVED** by the CRT scorer (`DECISION_DISTANCE`: scores 0.311 / 0.330 /
0.477 vs threshold 0.30, `accepted: true`, `rejection_reason: "APPROVED"`). Every one was then
killed by `FILTER_REJECTED`:

| Timestamp | Reason |
|---|---|
| 2026-05-07 10:45 | `off_session:OFF_SESSION` |
| 2026-05-15 05:45 | `off_session:OFF_SESSION` |
| 2026-05-20 02:15 | `off_session:ASIA` |

**HYPOTHESIS REFUTED (mine).** I predicted this would be F-048's mechanism — the DecisionEngine
`rr` gate firing `low_rr` because RREngine emits a polarity in [0.5,1] against `rr_threshold=1.5`,
making `run()` structurally unable to execute. **It was not.** The candidates never reached that
gate; the CRT session filter rejected them first. Checked before claiming: zero `low_rr` /
`_engine_vetoed` / engine-rejection entries anywhere in the run log. F-048 is neither confirmed
nor contradicted by this run.

Two things worth noting:
1. **`off_session:ASIA`** — ASIA is a *named* session yet was still filtered, so the allowed-session
   set excludes it. Consistent with F-017 (session policy is not a promotable lever) and directly
   relevant to the session-collision work in Item 2.
2. The very feature registered as **FM-052 `session`** in Item 2 — the one with the documented
   4-way (now five-way) collision — is what gated 100% of this run's trade candidates.

**Run configuration:** `BACKTEST_ENGINE_GATE=1` (**gate ON**, logged explicitly), production config
`v2_multi_2026_04`, `gaussian_impl=heuristic`, ZoneGate 8 zones from `models/zone_registry.json`.
Note this differs from F-037's documented research-spine setting (`.env` = 0, CRT-only) — this run
had the full fusion stack wired in, though no candidate survived far enough to exercise it.

**Statistical standing: INSUFFICIENT.** 3 candidates, 0 trades, over ~2 months. Nothing here
supports or refutes any economic hypothesis.

---

## 14. Table-B migration, PHASE A — 24 literals -> config (DONE 2026-07-19)

**Three-tier classification** (user directive: *"actually tunable policy, not identity — if
tunable then it needs to be in config"*). The prior two-tier split forced a false choice.

| Tier | Rule | Code comment template |
|---|---|---|
| **STRUCTURAL** | no meaningful alternative value; changing it breaks the definition or the arithmetic | `STRUCTURAL — defines the identity of <feature>; do not move to config per §6.5.` |
| **TUNABLE STRUCTURAL** (new) | shapes a REGISTERED identity *and* has legitimate alternatives -> goes to config, but carries two extra obligations | `TUNABLE STRUCTURAL — config-driven, but changing it redefines <FM-0NN>; requires ontology formula sync + artifact re-certification.` |
| **BEHAVIORAL** | tunable, target feature has no FM id | plain config reference |

**Migrated: 24 keys** (12 Tier 3 + 12 Tier 2). Left in code: enum encodings, RSI definitional
constants, `ddof=1`, degenerate sentinels, epsilons, and `finalize()` 300/0.02 (T-5/T-6 deferred).

### The obligation Tier 2 created — 6 ontology formulas were about to become FALSE

Migrating a literal that is *written into* an ontology `formula:` string makes that string a false
claim about runtime the moment config diverges. Synced (formula now names the config key, current
value shown as default) + `config_key(s)` added:

| FM | Was | Now |
|---|---|---|
| FM-020 `disp_strength` | `clip(…, 0.0, 3.0)` | `clip(…, <…clip_low>, <…clip_high>)  # defaults 0.0, 3.0` |
| FM-021 `retest_depth` | `clip(…, 0.0, 1.0)` | `clip(…, <…clip_low>, <…clip_high>)  # defaults 0.0, 1.0` |
| FM-026 `liquidity_pressure_score` | `exp(-0.5 * …); nan -> 10.0` | `exp(<…decay_coeff> * …); nan -> <…nan_sentinel>` |
| FM-049 `macd_hist` | `rolling(50) z-scored` | `rolling(<…zscore_window>) z-scored  # default 50` |
| FM-050 `volatility_regime` | `rolling(200)…cuts at 0.33/0.66` | config-key form; **note also corrected** — it had asserted the window/cuts "remain hardcoded", now false |
| FM-052 `session` | `< 8 … < 16` | `< <…asia_end_hour> … < <…london_end_hour>` |

Verified: **0** stale literal assertions remain (`grep` of the old patterns returns 0);
`validate_registry() == []`; 12 entries now carry `config_key`/`config_keys`.

### `causal_structure` — parameter added, but NOT yet single-source

`_DOUBLE_SWEEP_WINDOW` (module global, read at two sites) -> `_DOUBLE_SWEEP_WINDOW_DEFAULT`, with
an explicit `double_sweep_window` keyword on **both** `causal_structure_series` and
`causal_structure_at_bar`.

**Correction to my own comment during implementation:** I first wrote that the config value "is
threaded into causal_structure so the two can no longer drift". **False** — `feature_pipeline`
**never calls** `causal_structure`; the only production caller is `core/feature_store.py:141`
(live path), which still resolves the signature default. So the two are no longer *hardcoded
copies*, but they are not one source either. **T-7 stays OPEN** until FeatureStore threads config.

**T-7 CLOSED 2026-07-19** (supersedes the paragraph above; kept per §6.2 rule 4). The signature
default was removed entirely rather than threaded at the call site: both public `causal_structure`
functions now take `double_sweep_window: int | None = None`, and `None` resolves through the new
`feature_pipeline.resolve_double_sweep_window()` — the same `None`-means-config contract Phase B
gave `k`/`swing_window`. Putting the resolution in `causal_structure` (not in `FeatureStore`) means
a future second live caller cannot reintroduce the divergence. `FeatureStore` therefore needed no
call-site change; it needed a *different* fix — its `_liquidity_sweep_history` ring was
`maxlen=10`, which caps the history handed to `causal_structure_at_bar` and would have silently
truncated any window >10. Now `max(10, window)`; byte-identical at today's value of 5.

**Residual (NOT closed, needs a decision):** `FeatureStore._compute_derived`'s fallback
double_sweep path — which fires only when `_apply_causal_structure` raises — scans the *entire*
deque and ignores `double_sweep_window` altogether. Making it window-aware would change behavior on
that degraded path today (10 -> 5), so it is deliberately left alone rather than silently
"fixed" (§6.2 rule 3). Filed for a user decision.

### Verification (all gates passed)

| Gate | Result |
|---|---|
| Parity, full XAUUSD corpus (47,197 rows) | **byte-identical** `np.array_equal`, shape `(47197, 38)` |
| Config actually READ (parity alone can't prove this) | 6 keys mutated one at a time -> output moved every time |
| Strictness | incomplete cfg raises `KeyError` |
| Lint violation-set diff | **7 -> 7**, nothing new, nothing masked |
| Live-path `causal_structure` | default ≡ explicit-5; param provably plumbed (25 differs) |
| Tests | **81 passed** across pipeline/candle_math/derived_math/lineage/registry/dag_layers/fc1a/reachability |

**Finding surfaced by the "is it read?" gate:** `rsi_overbought`/`rsi_oversold` move
`df['rsi_state']` but **not the 38-dim vector** — `rsi_state` is non-canonical. A repo-wide grep
finds **no consumer of `rsi_state` outside `feature_pipeline.py`**, so these two knobs are
currently inert w.r.t. every model and decision path. Config-driven, but tuning them changes
nothing downstream today. Worth an explicit dead-knob check before anyone sweeps them.

### Phase B (NOT started) — `swing_window`

Deliberately excluded and sequenced last: it is imported cross-module by
`causal_structure.py:21`, sets the **FC1-A PIT causal delay** (`available_at = t+k`) as well as
the pivot half-window, and defines `lookback: 2` on **two** registered identities (FM-045/046).
Own commit, own parity + live-path proof.

---

## 15. Table-B migration, PHASE B — `swing_window` (DONE 2026-07-19)

User chose **full migration** over keeping it STRUCTURAL. Executed with the provenance layer
included, because that was the actual risk.

### What made this different from Phase A

`SWING_WINDOW` was not a local constant — it was a **published interface with 9 module-level
importers**: `causal_structure.py` (live path), **6 governance/certification scripts**, and 2 test
modules. Six of those scripts write `"swing_window": SWING_WINDOW` into durable artifacts as a
**provenance fact**.

The naive approach (module default + config override used only inside `FeaturePipeline`) would
have produced **governance artifacts asserting a value the pipeline did not use** — strictly worse
than leaving it hardcoded, because it injects the drift into the provenance layer itself.

### Design: PEP 562 lazy module attribute

```python
def resolve_swing_window(cfg=None) -> int:   # THE single source of truth
def __getattr__(name):                        # PEP 562
    if name == "SWING_WINDOW": return resolve_swing_window()
```

Two properties that made this the right tool:
1. **All 9 `from features.feature_pipeline import SWING_WINDOW` statements keep working** — so the
   6 certification scripts became provenance-correct with **zero edits**; they now record the
   resolved config value automatically.
2. **No import-time config load.** A module-level assignment would create a
   `features -> config_layer` edge *at module execution*, the exact cycle risk the deferred
   imports elsewhere guard against (`config_layer.rr.rr_dataset_builder` and
   `config_layer.crt_engine_v2` import `features.*` in the other direction).

**`causal_structure.py`:** removed the module-level `from features.feature_pipeline import
SWING_WINDOW` (it would have forced a config load at *that* module's import). Both public
functions now take `k: int | None = None`, resolved at call time via `_resolve_k()` — explicit
arg wins, else config. Same resulting value, no import coupling.

**`feature_pipeline.compute_structure_liquidity`** now reads `self._fp_cfg["swing_window"]` — the
instance config, not the module attribute, so an injected `cfg` is honoured.

### Provenance fixes actually required: 2 (not 6)

Only `phase1_run1_feature_truth.py` had **hardcoded literals** rather than the import:
`parameters={"SWING_WINDOW": 2}` at `:481` and `:514`, plus a formula string
`"rolling(center=True,k=2) …"`. All three now resolve from the imported (config-derived) value.
Repo-wide grep for a hardcoded swing literal in `scripts/`: **none remain**.

### Ontology

FM-045/FM-046 formulas rewritten to name the config key (`k = <feature_pipeline.swing_window>`,
default shown), `config_key` added to both, and FM-045 carries a `note` recording that `k` sets
the FC1-A PIT contract and that changes require **re-certification, not a re-run**.

### Verification (all gates passed)

| Gate | Result |
|---|---|
| Parity, full XAUUSD corpus | **byte-identical**, `(47197, 38)` |
| `swing_window` actually read | `k=3` changes output |
| PEP 562 import path | `SWING_WINDOW` == resolver == 2; unknown attr still raises |
| `causal_structure` lazy `k` | auto ≡ explicit `k=2`; `k=4` differs (provably plumbed) |
| **Live-path call parity** | `feature_store.py:141`'s exact call signature ≡ explicit `(k=2, dsw=5)` |
| Lint violation-set diff | **7 -> 7**, nothing new, nothing masked |
| `validate_registry()` | `[]` |
| Tests | **78 passed** (incl. `test_fc1a_swing_causal`, `test_phase1_duplicate_formula_identity_closure`) |

### Honest debt note — T-4 exposure GREW

Entries carrying **both** `lookback` and `config_key` went from **4 -> 9** (`atr`, `rsi_14`,
`ema_fast`, `ema_slow`, `macd_line`, `macd_signal`, `volatility_regime`, `swing_high`,
`swing_low`). `lookback` is kept for human readability but **nothing enforces it matches the
resolved config value** — so all 9 can now silently lie if a config value is changed. T-4's parity
test (assert `lookback == resolved config value` for every entry declaring both) is no longer a
nice-to-have; it is the guard for the whole migration. **T-4 priority raised.**

Only `true_range` (lookback 1) still has a `lookback` with no `config_key` — correctly, since its
period derives from `atr_period`.

---

## 16. T-4 — ontology <-> config parity, ENFORCED (DONE 2026-07-19)

**Scope was larger than "add a test".** Inspection found **6 entries already lying**: they
declared `config_key` while their `formula:` still inlined the literal, because they predated the
`<feature_pipeline.X>` token convention introduced in Phase A — `atr` (SMA(14)), `rsi_14`
(SMA(14)), `ema_fast` (span=9), `ema_slow` (span=21), `macd_line` (span=12/26), `macd_signal`
(span=9). Change `rsi_period` to 21 and FM-042's formula would still have claimed 14.

**Part 1 — 6 formulas rewritten** to the token form
(`close.ewm(span=<feature_pipeline.ema_fast_span>, …)  # default 9`).

**Part 2 — schema disambiguation.** Two entries carried `lookback` alongside *plural*
`config_keys`, so "which key does the lookback mirror" was unassertable. Added
`lookback_config_key`: `macd_line -> feature_pipeline.macd_slow` (the longer span = effective
warmup), `volatility_regime -> feature_pipeline.volatility_percentile_window` (the tercile cuts
are thresholds, not lookbacks).

**Part 3 — `tests/test_ontology_config_parity.py`** (new; dedicated file rather than folding into
`test_feature_lineage.py`, which is a pure-ontology fixture with no config dependency):

| Rule | Asserts |
|---|---|
| **A** | every `config_key`/`config_keys`/`lookback_config_key` names a key that EXISTS in config |
| **B** | singular `config_key` + `lookback` -> must be EQUAL to the live config value |
| **C** | plural `config_keys` + `lookback` -> MUST declare `lookback_config_key`, and match it |
| **D** | every `<feature_pipeline.X>` token in any `formula`/`note` resolves |
| **E** | **regression guard** — declaring `config_key(s)` OBLIGES the formula to contain a token |
| sanity | the population is non-trivial (>=12 bound, >=8 with lookback) so an empty-set pass is impossible |

Rule E is what makes this durable: *if you say the value comes from config, the formula must say
where.* Structural, no numeric heuristics, no false positives — and it is exactly the rule whose
absence let the 6 entries in Part 1 rot.

### Verification — the guard was proven to FAIL, not just to pass

A test that cannot fail is not enforcement, so each rule was broken deliberately and restored:

| Deliberate break | Caught by | Message |
|---|---|---|
| config `rsi_period` 14 -> 21 | **B** | `rsi_14: lookback=14 but feature_pipeline.rsi_period=21` |
| strip the token from `ema_fast`'s formula | **E** | declares config binding but formula inlines the literal |
| rename `config_key` to a nonexistent key | **A** (+B) | `not present in config` |

Other gates: `test_ontology_config_parity` **6 passed**; combined governance run **29 passed**
(`+ test_feature_lineage`, `test_formula_registry`, `test_feature_dag_layers`);
`validate_registry() == []`; lint violation-set diff **7 -> 7** (nothing new, nothing masked);
feature vector **unchanged** `(47197, 38)` — this pass is metadata/doc only, zero runtime effect.

### Also closed this session: T-7

`causal_structure` now resolves BOTH `k` and `double_sweep_window` through config-backed
resolvers under the same `None`-means-config contract. Verified: the live-style call (passing
neither) equals the explicit config value, and an explicit override provably changes output. The
previous latent batch/live split — where FeatureStore silently ignored
`feature_pipeline.double_sweep_window` — is gone.

---

## 17. T-20 — CRT ATR (DONE 2026-07-19). **My diagnosis was wrong; the fix is a rename.**

### The correction

I had recorded T-20 as "2 genuine duplicate-ATR implementations" and recommended *"CRT consumes
the pipeline ATR"*. **That recommendation would have been a serious bug.** The two are
**different quantities sharing a bare name**:

| | CRT `EngineState.atr` | Canonical FM-041 `atr` |
|---|---|---|
| Value | **ABSOLUTE**, price units | `atr_14_raw / close` — **close-relative**, dimensionless |
| Evidence | `atr_min_displacement * atr` compared to price moves; `candle.wick_size < mult * atr`; `expansion_atr_min_distance * atr` | canonical vector index 13 |
| Config key | `crt_engine.atr_period` | `feature_pipeline.atr_period` |
| Warmup | partial-window mean (works with <14 bars) | `rolling(14)` -> NaN |

Feeding the relative value into CRT's absolute-price comparisons would be a ~1000x error on gold.
The code already knew: `crt_engine_v2.py:1102` tags it `"source_class": "CRT_LOCAL_DERIVED"`.

**This is the third time the bare name `atr` has misled in this repo** — FM-050's `depends_on`,
the `volatility_regime` DAG edge, and this diagnosis. The lint flagged it on TARGET NAME, which is
why it looked like a re-derivation.

### The fix

`EngineState.atr` -> `EngineState.atr_abs`, with the distinction documented at the field. **50
reference sites across 6 files** (crt_engine_v2 34, backtest_v2 7, crt_xauusd_runtime_trace 4,
crt_gaussian_scorer 2, 2 test modules).

### A regression I introduced and caught by byte-diffing

The mechanical rename **silently broke telemetry**. `crt_engine_v2.py:2529` used a *string-based*
`getattr(st, "atr", 0.0)` — invisible to an attribute-name regex — so `RETEST_REPLAY` records
started emitting `"atr": 0.0` instead of the real values (10.71 / 14.92 / 5.91).

**Nothing else would have caught it:** the run summary was identical ("0 trades"),
`events.jsonl` was byte-identical, and every test passed. Only the telemetry byte-diff exposed it.
Swept for the pattern and found two more (`crt_baseline_trace.py:206`,
`p3c1_build_trade_audit.py:105`, both defaulting to `None`); all three now use the real attribute,
and the site carries a comment explaining why the string-access form was dangerous.

### Verification

| Gate | Result |
|---|---|
| `XAUUSD_events.jsonl` (the ledger) | **byte-identical** |
| `XAUUSD_crt_telemetry.jsonl` | **byte-identical** (after the getattr fix; DIFFERED before it) |
| `XAUUSD_summary.json` | identical excl. run id |
| Lint violations | **7 -> 5** — both `atr` violations resolved; the `upper_wick`/`lower_wick` pair merely shifted line (:900->:905) from a comment insertion |
| GD stale-pin set | **unchanged** (durable_key is content-based, so the line shift staled nothing) |
| Tests | **87 passed** |

### T-21 partially dissolves

I had framed T-21 as *"the lint's remedy is impossible for rolling indicators"*. For **this**
instance that is moot — it was never a genuine re-derivation, just a name collision, and renaming
resolved it cleanly. The lint-model gap remains real in principle for a genuine second producer of
a windowed identity, but **these two sites were not evidence for it**. T-21 keeps no open example.

### Residual (documented, not fixed)

Two ATR implementations still exist with a real behavioural difference — CRT's partial-window mean
vs the pipeline's NaN warmup. Defensible: they run in different execution contexts (live candle
buffer vs batch DataFrame). Also unchanged: the BitNet feature map at `crt_engine_v2.py:1955/2024`
injects the ABSOLUTE atr under the canonical key `"atr"` — that is the known **F-055** finding
(`atr` fed raw/unnormalized), on a path inert while `use_bitnet: false`. Deliberately not touched.

---

## 18. T-10 — behavior_census can now see the feature layer (DONE 2026-07-19)

### The one-line fix would have produced a FALSE GREEN

`_SCAN_DIRS` excluded `features/`, so the obvious fix was to add it. But `_collect_constants`
only gathers **module/class-level** assignments (its own docstring: *"NOT function-body /
signature"*), and nearly every remaining `feature_pipeline` literal lives inside a `compute_*`
method body. Adding the directory alone would have scanned it and reported ~nothing — a green
result meaning *"we didn't look"*, which is worse than not running the tool.

**Two gaps, both closed:**
1. `_SCAN_DIRS` += `"features"`.
2. New `_collect_function_constants()` — walks `FunctionDef`/`AsyncFunctionDef` bodies.

### Reported ADDITIVELY, on purpose

Function-body constants land in new keys (`function_constants`, `function_behavioral`), **not**
merged into `behavioral`/`hardcoded`. Existing floors assert those lists are empty
(`test_crt_engine_no_genuine_hardcoded`, `test_dynamic_threshold_has_no_behavioral_constants`).
Merging would have broken them **not because anything regressed, but because the measurement
definition changed** — a misleading break. Additive keeps every existing assertion's meaning
intact while making the new layer visible. **All 7 existing floors still pass.**

### A second blind spot found while wiring it

`feature_pipeline.py` was STILL skipped after adding the directory. The skip test
(`if not consts: continue`) ran **before** function collection, and the module now has **zero**
module/class-level constants — `SWING_WINDOW` became a lazy `__getattr__` in Phase B. So the most
constant-dense module in the layer was being skipped outright and would have read as "clean".
Fixed by collecting function constants before the skip decision.

### What it now shows — the migration is confirmed thorough

`features/feature_pipeline.py`: module/class-level behavioral **0**, hardcoded **0**;
function-body constants **2**, of which **1 BEHAVIORAL** — `_warmup_budget = 300` (L1016), which
is precisely **T-5**, already deferred by decision. Seven `features/` modules are now visible
where zero were before.

**Honest scope limit:** the census collects `NAME = <numeric literal>` assignments. Literals
appearing INLINE inside expressions (e.g. the `0.02` in `max(300, int(n_before * 0.02))`, or the
`1e-9` guards) are still not collected — true for the pre-existing scanned packages too. This is
a real improvement in visibility, not total coverage.

### Verification

95 tests passed across census / ontology-parity / feature-pipeline / CRT / config-reachability;
lint violations unchanged at 5; feature vector unchanged `(3871, 38)`.

---

## 19. T-11 — no silent fallbacks on the live ingress (DONE 2026-07-19)

User rule, verbatim: **"No silent Fall Back. Hard rule."** Audited the source (not docs), fixed
every violation found in the live path AND in my own session code.

**Decisions:** fail closed on FeatureStore failure (no kill-switch flag — such a flag gets
switched on under pressure and left on); ALL consumed fields required (no tiering, no
"acceptable" default, no future adjudication about where the line sits).

### What was fixed, worst first

**1. The FeatureStore try/except — the biggest hole.** It caught every exception, logged a
WARNING, and continued with the un-validated `_safe_float` dict. Since
`FeatureStore._ensure_required()` is the ONLY enforcement of the canonical field contract,
**the validation failure was itself what disabled the validation** — a real decision then scored
on defaulted data. Now propagates: a validation failure REJECTS the tick.

**2. `ema_fast`/`ema_slow` defaulted to `close`** — a PRICE substituted for a moving average.
Cascaded: `ema_spread` -> 0, `trend_bias` -> 0, and `ema_spread`'s own fallback was
`ema_fast - ema_slow` = 0. Three canonical features became plausible, wrong, and mutually
consistent — undetectable by any range check.

**3. `atr` defaulted to `0.0`** — silently disabling every `if state.atr_abs > 0` CRT guard
(`crt_engine_v2.py:1193/1373/1892/1903/2712/2805`). The engine did not error; it quietly stopped
applying its own logic.

**4. `_derive_session` returned `"london"` when the feeder sent nothing** — fabricating a
specific trading session. Session gates trade admission: the 2026-07-19 XAUUSD run had **100%**
of its candidates rejected by the session filter. An invented "london" could admit or reject
trades on fiction. Also `_normalize_session(None) -> "london"`, and unknown values were passed
through raw; both now raise.

**5. `symbol` defaulted to `"EURUSD"` at two sites** — inventing a concrete instrument, so
orchestrator routing and logging would misattribute the decision to the wrong market.
(`"UNKNOWN"` elsewhere is at least honest; a real ticker is not.) New `_require_symbol()`.

**6. ~30 feature fields defaulting to `0.0`/`1.0`** — `0.0` is a LEGITIMATE value for most
structure flags, so a defaulted field was **indistinguishable from a real one**. All now
mandatory via the new `_require_feature_value()`, which mirrors the existing
`_require_ohlcv_value()` pattern already in the file.

**7. `context` re-read `candles_since_retest`/`sweep_detected`/`double_sweep` from raw
`trade_data` with defaults** while the same fields were strict in `engine_input` — the same value
could be real in one path and defaulted in the other. Now read from the validated frame.
(`double_sweep` especially: FeatureStore derives it from history, so the feeder's raw value was
the wrong source regardless.)

**8. My own session code — same sin, 7 sites.** `float(st.atr_abs or 0.0)`,
`getattr(state, "atr_abs", None)` x2, and 4x `float(self.state.atr_abs or 0.0)`. All dead
defaults on a non-optional dataclass field — but **exactly the pattern that had silently zeroed
telemetry an hour earlier**. Now direct attribute access, so a future rename fails loudly.

### Deliberately NOT fallbacks (kept, documented)

- `double_sweep: 0.0` in the auxiliary dict — a placeholder that `FeatureStore._compute_derived()
  overwrites with the history-correct value; never read as data.
- `disp_str` as an alias for `disp_strength` — a naming variant, not a default: if neither
  spelling is present the strict accessor still raises.
- The three `is_asia`/`is_london`/`is_newyork` `_safe_float(..., 0.0)` reads — these test WHICH
  flag is set, not substitute a value; if none is set, `_derive_session` raises.

### Verification

| Gate | Result |
|---|---|
| Positive — complete `trade_data` | builds identically (strict path changes no values, only rejects incomplete input) |
| Negative — delete each of `ema_fast`/`ema_slow`/`atr`/`body_ratio`/`retest_depth`/`session`/`symbol` | **each raises `ValueError` naming the field** (previously: silent `close`/`0.0`/`"london"`/`"EURUSD"`) |
| `_normalize_session(None)` | raises (was `"london"`) |
| Live-hook tests | **51 passed** — existing fixtures were already complete, so no test needed loosening |
| Batch path | backtest `events.jsonl` AND `crt_telemetry.jsonl` **byte-identical** |
| Broad regression | **127 passed**; lint violations unchanged at 5 |

### Still OPEN under T-11

The **versioned feed contract** (`feed_schema_version` handshake) and the **batch/live period
symmetry check** — asserting the feeder's EMA/ATR periods match `feature_pipeline.*`. Both need
the producer (external EA repo) to participate, so they are a coordinated change, not a
unilateral one. The asymmetry noted earlier stands: sweeping `ema_fast_span` still changes
batch/training with no live effect. What this pass removed is the *silent* part — a missing or
malformed field now fails loudly instead of resolving to a plausible lie.

---

## 20. Queue pass 2026-07-20 — T-8 / T-9 / T-13 / T-15 closed

Worked the remaining **actionable** queue items (not deferred/paused/external). User decisions
in §3 still hold: M16 P1/P2/P3 deferred to live_engine_hook phase; T-5/T-6 warmup deferred;
stateful 6 excluded; T-17/T-18 future phase.

### T-9 — stale MACD B2/B3 comment

`configs/formulas/market_ontology.yaml` `indicator_identities` header: the line claiming
*"Full FM-id registration + parity wiring is a separate architectural review (deferred, B2/B3)"*
is now marked SUPERSEDED with the C-1 truth (MACD PROMOTED as FM-047/048/049; residual is
registration-hygiene only, not a review gate).

### T-8 — dead EMA soft defaults

`src/features/feature_builder.py`: removed `ema_fast_period` / `ema_slow_period` soft-default
attributes (never read by `build()` or any caller). Period authority remains solely
`feature_pipeline.ema_fast_span` / `ema_slow_span` (T-1).

### T-13 — ma_200 consumer claim

`scripts/analysis/phase1_run15a_quantity_role_adjudication.py`: `ma_200` split out of the
generic intermediate bucket. Role stays `IMPLEMENTATION_INTERMEDIATE` but `consumers=[]` with
an explicit note that ma_20/ma_50 feed downstream columns while ma_200 feeds nothing. (ma_200
was not present in the 2026-07-10 frozen universe artifact — correction is in the adjudicator
source so a future re-run cannot re-lie.)

### T-15 — feature_math_lint floor GREEN

Three pre-existing failures closed:

| Failure | Fix |
|---|---|
| `test_floor_is_green` (4 wick re-derivations + 1 session) | Locals renamed: `upper_wick`/`lower_wick` → `sweep_uw_frac`/`sweep_lw_frac` in `detect_sweep` + `candle_geometry` (NOT `upper_wick_ratio` — that is itself FM-011/012 and re-trips the lint). Dead-module `session` local → `session_label`. |
| `test_pins_have_no_stale_durable_keys` (GD-006..009) | Pins **retired** via append-only `feature-math-grandfather-retirements.json` (same change that removed the sites). Remaining pin: GD-010 only. |
| `test_universe_reconciliation_with_census` (16 missing) | 16 Gate-2B adjudications appended to `geometry_semantic_adjudication.jsonl` for out-of-lint-universe registered-name derivations (scripts/tests/strategy/research). |

**Verified:** `tests/test_feature_math_lint.py` + `tests/test_btcusdt_crt_v3_handover.py` →
**23 passed, 7 skipped**. Lint report: `new_violations=0`, `stale_pins=0`, `current_pins=1`
(GD-010), `retired=9`. Behaviour-neutral renames only — no scoring/decision path change.

### Remaining OPEN on this tracker (do not invent work)

| ID | State | Why still open |
|---|---|---|
| **T-5 / T-6** | DEFERRED by user | warmup budget / finalize guard |
| **T-11 residual** | needs external feeder | `feed_schema_version` + batch/live period symmetry |
| **T-12** | PAUSED by user | (XAUUSD 2-month already ran — §13; item may be closable on review) |
| **T-17 / T-18** | FUTURE PHASE | macd_hist z-score semantics; volregime knobs |
| **T-19** | OPEN (semantic) | `candles_since_retest` misnamed — rename is schema-index-34 change |
| **T-21** | design gap, no live example | rolling_indicators remedy path; T-20 dissolved its only "evidence" |
| **M16 P1/P2/P3** | DEFERRED by user | consumer-alignment; still `BLOCKS_ACTIVATION: true` |
| **M16 P4+** | not started | superseded-vector migration etc. — large, own plan |

---

## 21. FREEZE + focus shift (2026-07-20)

| Artifact | Path |
|---|---|
| Freeze policy | `docs/governance/feature-layer-mutation-freeze-2026-07-20.md` |
| Freeze pin + benchmarks | `docs/governance/feature-layer-freeze-pin-2026-07-20.json` |
| Floor test | `tests/test_feature_layer_freeze.py` |
| Active engineering roadmap | `docs/implementation_plan/backtest-runtime-roadmap-2026-07-20.md` |
| Closure index surface | `FEATURE_LAYER_MUTATION_FREEZE` status **COMPLETE**, `frozen: true` |

**Freeze class:** `GOVERNANCE_FREEZE` — scientifically extensible via accepted programs /
waivers; not “never touch features again.”

**Feature regression pin (scope 2026-07-20b — XAUUSD only):**

| Corpus | Vector |
|---|---|
| `data/XAUUSD_W2026-03-23-to-2026-05-21.csv` | (3871, 38) float32 SHA `adad1a0b…` + coverage metadata |

**Removed from feature pin:** BNB head benchmark (belongs in runtime suite R-1/R-2).

**What freeze is not:** L6 activation, economic validation, full-path behavioral equivalence,
or clearance of M16 `BLOCKS_ACTIVATION` items. Coverage block on the pin lists paths
**not** exercised by the feature matrix hash.

**Default next work:** backtest/runtime roadmap R-1 / R-2 / R-3 (measurement honesty,
BNB gate ON/OFF *runtime* baselines, filter-stack map, F-048 intent decision).
