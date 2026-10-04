# Bind feature NAMES to ontology identity — Step 1 cleanup, clean base, then Steps 2–3

## Context

Program FEATURE-NAME-IDENTITY-BINDING (user-approved 2026-09-16): the ontology becomes the single source of
feature names, production code references features by FM id (`F.FM_021`), and the 22 agreed v7 renames become
an ontology edit.

**Step 1 is DONE (uncommitted):** `source_inputs` FM-085..089, `CANONICAL_FEATURES` generated from the ontology,
`F`/`feature_name()` namespace, `feature_math_lint` regression fixed. Parity proven (hashes unchanged, value-level
freeze regression green). Completion manifest honestly BLOCKED on the shared uncommitted tree.

A review of Step 1 and the v7 list raised cleanup items, rename-list decisions and a working-tree blocker. Each
claim was checked against source; results and user decisions are folded in below.

### Review claims — verified at source

| # | Review claim | Verdict |
|---|---|---|
| 1.1 | `impl: feature_pipeline.FeaturePipeline` is the only class-level ref | **Partly.** Precedent exists (`features.magnitude_states.MagnitudeStateEncoder` ×3). Real ingestion check is `FeaturePipeline._validate_input` (`feature_pipeline.py:470`) → `require_ohlcv_columns` |
| 1.2 | Ontology version still 1.4 | **Confirmed** (`market_ontology.yaml:55`) |
| 1.3 / 1.4 | `consumed_by: [UNKNOWN]` note; `base_inputs` vs `source_inputs` twin lists | **Confirmed** |
| 2.2 | Bare `atr` in formula text is ambiguous | **Confirmed, and wider.** FM-022/023 `atr` = FM-041 close-relative (that is the F-061 defect, `derived_math.py:76-91`). FM-075..082 SMC text says `/ atr` but code divides by **absolute** ATR (`feature_pipeline.py:1260`, `atr_abs = atr*close`) — a DOC_DRIFT in registered formula text today |
| 2.5 | `crt_engine_v2.py:2330-2334/:2349-2354` bridge FM-027→FM-021 | **Corrected.** Those are pre-CH-002 cache keys that held **FM-027/FM-028** values (F-050), not FM-021/FM-020. Migrating them to `F.FM_021` would make them read `retest_ema_fast_distance_atr` after Step 3, so historical caches silently fall back to 0.0 — the exact F-079 class the review warns about. Same for `:2167/:2239` (legacy BitNet input names) |
| 3.2 | Alias stack depth | **Confirmed, sharper:** `SCHEMA_V5_ALIASES` has **zero consumers**; only V3 is read (`gaussian_schema_contract.py:55`, `research/model_runners/schema_resolver.py:277`). v4→v5 was additive (F-076), so no v4 map is needed |
| 4.1 | 33 unattributed files | **Attributed:** one foreign change set. 24 configs add an OBSERVATION_ONLY `layer_trace` section (hash-neutral, non-`params`), plus `layer_trace.py`, `run_id_last_ran.py`, `cross_family_join.py` + tests — a continuation of commit `5db2d03` |

### User decisions (this turn)

- Slot 33 keeps **`body_size_atr`**. Suffix rule: `_atr` = divided by absolute ATR, `_atr_rel` = by close-relative ATR.
- Non-vector siblings **renamed in Step 3**: FM-031 `momentum_score_atr` → `close_change_atr`, FM-068 `rsi_state` →
  `rsi_sma_state`, FM-074 `atr_absolute` → `atr_sma_abs`. FM-030 `ema_spread_atr` already fits the rule.
  `volatility_regime_{global_batch,expanding_causal,rolling_causal}` are pipeline research columns, not identities —
  **explicitly deferred**.
- Clean base: **commit the foreign `layer_trace` change set too**, with a declared attribution note.

## Phase A — Step 1 cleanup (added to the Step 1 change set; value-neutral)

In `configs/formulas/market_ontology.yaml`:
1. `version: 1.4` → `1.5`, with a dated one-line entry for `source_inputs` (2026-09-16).
2. `source_inputs` header comment: (a) `impl` names the ingestion class, per the `MagnitudeStateEncoder` precedent,
   and the entry point is `FeaturePipeline._validate_input`; (b) `consumed_by: [UNKNOWN]` means not yet
   censused, not "no consumers"; (c) `base_inputs` (DAG roots) and `source_inputs` (identities) must list the same names.
3. FM-075..082 formula text: `/ atr` → `/ (atr * close)`. Text only, matches code; FM-020's style.

Guard in `tests/test_feature_lineage.py`: `set(base_inputs) == set(source_inputs)`, so the twin lists can't drift.

Then: refresh the freeze-pin SHA for the ontology, and amend the Step 1 impact/completion manifests, topic doc and
SESSION LOG entry. Re-run the ontology floors and the freeze test.

## Phase B — clean base: 4 commits by explicit path (never `git add -A`)

Preflight: no live `git.exe`/`.git/index.lock`; check `git config core.hooksPath`. Re-check the mtimes and diffs of
the foreign files right before staging. If they changed since this plan, **stop and report**.

Before each commit, read every staged diff in full and scan it for secrets. Shared files carrying several change sets
(`market_ontology.yaml`, freeze pin, `assistant_project.md`, `CLAUDE.md`, `current-findings.md`,
`research_family_registry.json`, topic/architecture docs) are split **by hunk**. Build a filtered patch from
`git diff`, stage it with `git apply --cached`, and verify with `git diff --cached`. A hunk mixing two sets goes to
the later commit, with a note.

- **C1 — foreign `layer_trace` / run-id / cross-family set** (the 33 files). First inspect the 4 configs whose diff
  isn't +10 lines (`regime_map.json`, `v2_dispkill_shadow`, `v2_htfcrt_2026_08`, `v2_htfcrt_objgate_shadow`) and
  confirm `config_hash` is unchanged. Message states: written by a concurrent session, continuation of `5db2d03`,
  committed at user direction 2026-09-16, no manifest of its own seen.
- **C2 — CH-cost-model-identity-stamp** (`backtest_v2.py`, `tests/test_cost_model_stamped.py`, its impact
  manifest). Also foreign; included because Step 2 edits `backtest_v2.py`. Same attribution note.
- **C3 — CH-intent-schema-alignment / F-108** + SCR-472 shadow probe + the trade-intent census doc + FM-027/028
  hunks + the foreign CH-derive-declare-windows ontology hunks (declared in the waiver log).
- **C4 — Step 1 + Phase A cleanup.**

If the pre-commit hook blocks on the recorded baseline reds (12 names), **stop and ask** — no `--no-verify` without
explicit approval. After C4, re-run `validate-completion` for Step 1 and CH-intent-schema-alignment. Expect them to
clear or leave only the recorded pre-existing reds.

## Phase C — Step 2: move production reads onto identity (value-neutral, one change set)

1. **Census** `scripts/analysis/feature_name_literal_census.py` (SITS: stub append → seed → matrix). AST scan of `src/`
   excluding `src/research/`. Classifies each canonical-name literal as CANONICAL-READ / CANONICAL-WRITE / HOMONYM /
   CONFIG-KEY / LOG-DOC. Also scans the 3 sibling names (`momentum_score_atr` 0 sites, `rsi_state` 3, `atr_absolute` 4).
   **Pre-seeded HOMONYMs (pinned literal, never migrated):** `crt_engine_v2.py` `_derive_trade_intent` fallbacks
   `retest_depth` / `disp_strength` / `disp_str` (FM-027/028 legacy cache keys), and its reads of
   `sweep_detected` / `double_sweep` / `momentum_score` / `candles_since_sweep` / `body_ratio` (CRT cache, not the
   canonical row — trade-intent census CONTRACT GAP). Also `_bn_in["retest_depth"]` at `:2167/:2239` (BitNet
   input names), the `double_sweep` CRT cache key, the `Candle.body_ratio` property, and `atr` engine locals.
2. **Edit** CANONICAL-READ/WRITE sites to `F.FM_0NN`: pipeline writers, `core/feature_store.py`,
   `runtime/live_engine_hook.py`, `core/gate_intelligence.py`, `config_layer/execution_planner.py`, strategies,
   and `runtime/backtest_v2.py` index lookups.
3. **Ratchet test** (pattern of `tests/test_model_paths_literals.py`): no new canonical-name literal in `src/` outside
   `src/research/`; HOMONYM sites pinned by exact list. **Deferred scope, stated in the test docstring:** `scripts/`,
   `tests/` and `src/research/` keep literals and will go stale against v7 over time.

**Parity, measured in isolation:** two `git worktree`s — A at C4, B at the Step 2 commit. The gitignored
`data/mt5/XAUUSD_M15.csv` and `models/` are passed by absolute path from the main tree. Compare the XAUUSD 48-dim
vector bit-identical by position, and the XAUUSD backtest ledger byte-identical modulo `run_id`. Planner, gate and
comparator floors stay green. Foreign WIP can't reach the measurement.

## Phase D — Step 3: apply renames as an ontology edit (schema v7.0, one change set)

1. Rename the 22 `vector_key`s (list `schema_v7_rename_list.md`, slot 33 = `body_size_atr`). Rename the 3 sibling
   identities, including FM-031's second block at `market_ontology.yaml:3053`. Edit their 7 `src/` literal sites directly.
2. **Formula/intent text names identities explicitly:** FM-022/023 `atr` → `atr_sma_rel`. `(atr * close)` stays
   as written. FM-026 `liquidity_distance` → `structure_level_distance_atr`. FM-043/044/054 intents: `ema_spread` →
   `ema_spread_atr_rel`.
3. **Aliases:** add `SCHEMA_V6_ALIASES` (v6 → v7, 22 + 3 entries). Add one `resolve_historical_name(name)` in
   `feature_schema.py` that composes V3 → V5 → V6 in version order and fails on cycles or collisions. Route both
   existing consumers through it, so `SCHEMA_V5_ALIASES` stops being dead.
4. Regenerate `tests/fixtures/test_vectors.json` through the pipeline. Remap model `feature_order` lists across all
   4 registries (the `scripts/governance/remap_registries_v6.py` pattern). Bump `SCHEMA_VERSION` to 7.0 and run
   `src/runtime/baseline_capture.py`.
5. **Training freeze window:** from Step 3's first edit until its commit, no model is trained or registered. Any model
   trained after the commit uses v7-native names. Pre-v7 artifacts read v7 data only through the remap. Recorded in
   the freeze-pin waiver.
6. Explicit deferrals, recorded in the manifest: the `volatility_regime_*` research columns; literals in
   `scripts/`/`tests/`/`src/research/`.

**Parity:** by-position vector identity; ledger byte-identical modulo `run_id` (worktree method as in Phase C).

## Governance (every phase)

Freeze-pin waiver before the first edit of each step (`FEATURE-NAME-IDENTITY-BINDING`) → impact manifest →
`validate-impact` → implement → parity proof → `validate-completion` → sync findings (F-107 successor for v7),
topics, citations and `docs/reference/schemas.md` → SESSION LOG. Record each review item's disposition in the
Step 1 completion manifest.

## Verification

- Phase A: `validate_registry()`/`validate_semantic_registry()` == `[]`; `test_feature_lineage.py` (incl. new twin-list
  guard), `test_feature_spec_schema.py`, `test_formula_registry.py`, `test_semantic_registry.py`,
  `test_feature_layer_freeze.py`; hashes unchanged.
- Phase B: `git status` shows only intended residue; each commit's `git show --stat` matches its declared list;
  `config_hash` unchanged; `validate-completion` re-run.
- Phases C–D: worktree parity (vector by position + ledger); new ratchet test green;
  `check_governance_invariants.py --all` at the recorded baseline, same failing names.
