# Plan — Close out Track-1 Epic-1 "Repair the Spine" (STORY-1.4/1.5/1.6)

## Context

"Continue" resumes **Track-1 Epic-1 ("Repair the Spine")** — the multi-LLM build queue's first
epic, which clears the failing tests that undermine trust in the spine. STORY-1.1 (LLM fail-open
contract) landed last session. The build-queue's remaining order (1.2 dual-gate → 1.3 rr-fusion →
1.4 …) is **stale**: a live `pytest` run shows **STORY-1.2 and STORY-1.3 already pass**. The genuine
remaining reds are STORY-1.4, 1.5, 1.6.

Each was classified per CLAUDE.md §6.2 (drift discipline) before deciding the fix — they are *not*
uniform "fix the code" cases:

| Story | Failure | Classification | Fix owner |
|---|---|---|---|
| 1.4 gaussian | `test_engine_runner_ml_impl` sets `GAUSSIAN_IMPL=ml`, code ignores it | **stale test** — env var deliberately removed per Config-First §6.5 ("config is single source of truth"); `test_engine_runner_config_override` already covers the live config path | test (+ doc) |
| 1.5 replay | `KeyError: 'zone_id'` → outer fail-open wipes all records | **CODE_DRIFT** — real `models/zone_registry.json` zones key on `id`; code reads `zone_id` at `replay_memory_engine.py:416,425` | src code |
| 1.6 feature schema | unregistered version → `False`; test wants `True` | **TruthConflict** — `fail_closed=True` is a deliberate safety default. **User decision: keep fail-closed, fix the test, AND wire the (currently dormant) check into a live caller** | test + src wiring |

**Spine-safety (verified):** active config `engine_runner.gaussian_impl = heuristic`, so
`MLGaussianEngine` is **off the live spine**; ReplayMemory is sidecar-only (F-012);
`check_compatibility` has no current live caller. All three changes are therefore **spine-neutral on
the active config** — provable byte-identical via the golden-ledger gate.

Intended outcome: Epic-1 reds → 0 (modulo the pre-existing, unrelated `test_agents_path_alignment`),
spine byte-identical, and the schema-corruption guard promoted from dormant → live on the ML path.

## STORY-1.4 — Gaussian impl switch (test-drift + doc-drift)

**Intent (confirmed):** two real engines —
`HeuristicGaussianEngine` (default; deterministic EMA/momentum kernel, `gaussian_mu`/`gaussian_sigma`,
no model) and `MLGaussianEngine` (trained `GaussianNBModel` from the registry →
`predict_expected_rr` → sigmoid → score; fail-open 0.5). `shadow_ml` = heuristic is the production
score, ml runs as a logged shadow. Switching is **config-driven** via `config["gaussian_impl"]`
(`EngineRunner._get_gaussian_engine`, `engine_runner.py:288`); the `GAUSSIAN_IMPL` env var was
removed under §6.5.

**Changes (test + doc only):**
- `tests/test_gaussian_impl_switch.py`: rewrite the two env-var tests to the config path (mirror the
  passing `test_engine_runner_config_override`):
  - `test_engine_runner_ml_impl` → `EngineRunner._get_gaussian_engine({"gaussian_impl": "ml"})` →
    `MLGaussianEngine`.
  - `test_engine_runner_heuristic_explicit` → `{"gaussian_impl": "heuristic"}` → `HeuristicGaussianEngine`.
  - Drop the `os.environ["GAUSSIAN_IMPL"]` set/teardown from both.
- §6.2 doc sync: `src/engines/ml_gaussian_engine.py:6-8` docstring still advertises the removed env
  var — update to "Selected via `config['gaussian_impl']` (config-first, §6.5)".

## STORY-1.5 — Replay zone-registry key drift (CODE_DRIFT)

Root cause: real registry zones use `id` (keys: `id, mu, sigma, weights, threshold, meta, weight`),
but the loader hard-requires `zone_id`. Line 425 (`{int(z["zone_id"]): …}`) runs outside the
per-record guard → raises → outer `_load` fail-open empties `_records`/`_cluster_stats`.

**Changes (`src/replay/replay_memory_engine.py`):**
- Line 425: `zones = {int(z.get("zone_id", z.get("id", 0))): z for z in zone_reg.get("zones", [])}`
- Line 416: `best_id = int(zone.get("zone_id", zone.get("id", 0)))`

Tolerant of both schema variants (minimal, defensive — sidecar path). This unblocks
`test_cluster_stats_built` (records load → cluster 0 populated) and `test_decay_weighting`
(records present → decay-weighted winrate < 0.5).

## STORY-1.6 — Keep fail-closed + wire check into a live caller

**Decision:** keep `check_compatibility(..., fail_closed=True)` default (safety); fix the test to
expect `False`; **promote the check from dormant → live** in the ML inference path (the exact site
its own docstring names, `feature_schema.py:235-238`).

**Changes:**
1. `tests/features/test_feature_schema_registry.py`: rename/rewrite `test_unregistered_fail_open` →
   `test_unregistered_fail_closed`, assert `check_compatibility("_never_registered_xyz_") is False`,
   and assert the WARNING is logged. (Optionally add a one-liner asserting explicit
   `fail_closed=False` still returns `True` to pin the legacy opt-in.)
2. `src/engines/ml_gaussian_engine.py` — register at load, check at inference:
   - In `_load_model` (after `load_gaussian_model` returns `_meta`): if
     `_meta.get("feature_order_hash")`, call
     `FeatureSchemaRegistry.register(active_version, _meta["feature_order_hash"])`. This populates the
     in-memory registry so the inference check has something to compare (the registry is otherwise
     empty at live inference — registration only happens in `trainer.py` at train time).
   - In `compute` (before scaling, where the model is loaded): call
     `compatible = FeatureSchemaRegistry.check_compatibility(self._model_version)`. When **not**
     compatible **and** `len(vec) == self._model.n_features` (equal length but registry reports
     order-mismatch / unknown) → return the `_fallback` 0.5 + WARNING. This is the genuine
     silent-corruption case the registry exists to catch (length-equal, order-different); the
     existing `len(vec) > n_features` truncation path is unchanged for the differing-length case.
   - Keep fail-open doctrine intact: any exception still returns 0.5.

**Why spine-neutral:** active `gaussian_impl=heuristic` → this code path is not exercised by the
governing backtest; golden ledgers must stay byte-identical.

## Critical files

- `tests/test_gaussian_impl_switch.py` (1.4 test)
- `src/engines/ml_gaussian_engine.py` (1.4 docstring, 1.6 wiring)
- `src/replay/replay_memory_engine.py:416,425` (1.5 fix)
- `tests/features/test_feature_schema_registry.py` (1.6 test)
- `src/features/feature_schema.py:248` (unchanged — `check_compatibility` default stays `fail_closed=True`)

## Reuse (no new patterns)

- `EngineRunner._get_gaussian_engine` config switch + the passing `test_engine_runner_config_override` (1.4 template).
- `FeatureSchemaRegistry.register/check_compatibility` already exist (1.6 just calls them); registration mirrors `trainer.py:469,792`.
- `_meta["feature_order_hash"]` produced by `trainer.py:399`.

## Verification

1. **Targeted tests green:**
   `python -m pytest tests/test_engine_runner_dual_gate.py tests/test_engine_runner_rr_fusion.py tests/test_gaussian_impl_switch.py tests/features/test_feature_schema_registry.py tests/replay/test_replay_memory_engine.py -q`
   → 0 failed (was 4).
2. **Spine byte-identical (the §6.5 parity gate):** golden-ledger + metrics-oracle-parity + invariants
   for BNBUSDT + SOLUSDT — confirm unchanged (changes touch only the inactive ml path, the replay
   sidecar, dormant schema check, and tests). Run the project's golden/oracle test set
   (`tests/.../test_*golden*`, `*metrics_oracle*`, `*invariant*`).
3. **No new reds:** full suite delta vs the known Epic-1 baseline — expect the 4 fixed reds gone and
   no new failures introduced.
4. **§6.2 sync:** check `docs/architecture/citation-map.generated.md` + `docs/topics/` for gaussian /
   replay / feature-schema citations touching the edited lines; `python -m pytest
   tests/test_doc_citations.py tests/test_topic_docs.py -q`.

## Close-out (per CLAUDE.md mandates)

- `multi_llm/build_queue.jsonl`: STORY-1.4/1.5/1.6 `status` → `done`.
- `HANDOFF.md`: update `current_story`/`completed`/`next_actor`.
- SESSION LOG entry appended to `assistant_project.md` (§6 — codebase log; governed src changed).
- No findings flip (these are test-trust repairs, no economic finding); no rehash (no `params`-block edit).
