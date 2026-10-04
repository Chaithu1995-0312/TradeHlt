# Concatenated implementation plans — part 3 of 10

Source directory: `docs/implementation_plan/`
Files in this part: 16

## Contents

1. `continue-exactly-here-peaceful-rabin.md` (3385 bytes)
2. `continue-last-session-some-modular-hummingbird.md` (8699 bytes)
3. `continue-refactored-hamster.md` (8251 bytes)
4. `create-new-branch-from-sequential-bachman.md` (3745 bytes)
5. `crtstateresolver-backtestrunner-how-each-shimmering-toast.md` (1797 bytes)
6. `d-tradelatest-active-models-yaml-d-trad-async-tulip.md` (4190 bytes)
7. `d-tradelatest-crtclaude-pdf-go-through-iterative-otter.md` (5508 bytes)
8. `d-tradelatest-docs-analysis-feature-ide-foamy-sutherland.md` (12137 bytes)
9. `d-tradelatest-docs-analysis-feature-ide-iterative-codd.md` (12616 bytes)
10. `d-tradelatest-docs-governance-finding-d-staged-widget.md` (7082 bytes)
11. `d-tradelatest-docs-governance-tradenet-parsed-shannon.md` (4703 bytes)
12. `d-tradelatest-docs-implementation-plan-ethereal-crystal.md` (9275 bytes)
13. `d-tradelatest-reports-monthly-tv-vs-act-iterative-bengio.md` (13680 bytes)
14. `d-tradelatest-reports-ohlcv-lineage-for-glistening-wilkinson.md` (13270 bytes)
15. `d-tradelatest-results-feature-trace-sem-goofy-hanrahan.md` (3802 bytes)
16. `dataset-navigation-use-the-snug-sparrow.md` (6839 bytes)


================================================================================
SOURCE_FILE: docs/implementation_plan/continue-exactly-here-peaceful-rabin.md
SOURCE_BYTES: 3385
PART: 3/10 FILE 1/16
================================================================================

# Resume IC-003B (H-IC003B-001) from on-disk checkpoints

## Context

IC-003B is the sequence-geometry **shape library** research program (representation
redesign after IC-003 v1 was archived `LIBRARY_FAIL`). It was **safely paused** on
2026-07-16 before a system restart, mid-run. All worker PIDs were killed intentionally;
state survives only via disk checkpoints. This session must **finish the run** — not
re-plan, not restart from scratch.

Verified state (read-only checks this session):
- `checkpoint.json` → `"status": "PAUSED"`, `completed_units: [S_N4, T_N4]`.
- On disk & intact: `arm_S_N4/{shapes.json,assignment.jsonl}`, `arm_T_N4/{shapes.json,assignment.jsonl}`.
- Pending: `C_N4, S_N16, T_N16, C_N16, S_N8, T_N8, C_N8`.
- `scripts/research/ic003b_build.py` exposes `--resume` (default), `--fresh`, `--mark-paused`.

The long pole is **Arm T N=16** — pure-Python banded DTW over ~4.5M upper-triangle
pairs (subsample 3000), GIL-bound to ~1 core, ~2.5–3.5h. Total remaining ~3–4h.

## Plan

**Step 1 — P0 resume (the mandatory action).** Run:
```powershell
cd D:\Tradelatest
$env:PYTHONPATH='src'
python scripts/research/ic003b_build.py --resume
```
Run it **in the background** (3–4h job) so the session is notified on completion rather
than blocking. Confirm the log shows `SKIP Arm S N=4` / `SKIP Arm T N=4` (checkpoint hit)
early — if it recomputes N=4 instead of skipping, stop and investigate (do **not** let it
silently overwrite the N=4 checkpoints).

**Step 2 — On completion, record the verdict.** Expected outputs:
`REPORT.md`, `report.json`, `SHAPE_LIBRARY.md`, and `checkpoint.json → "RUN_COMPLETE"`.
Read `REPORT.md`; record `program_verdict` ∈ {`IC003B_LIBRARY_OK`, `IC003B_PARTIAL`,
`IC003B_FAIL`}. **Accept `FAIL` as-is** — do not touch G1.

**Step 3 (optional, only if asked) — P1 DTW profile.** Per
`docs/research-readiness/erp-geometry-compute-doctrine.md` Stage 1: profile Arm T to
measure the % wall in `dtw_euclidean`/`pairwise_dtw` vs assign vs JSON. No algorithm
swap, no `DistanceEngine` build, no GPU unless the user explicitly asks and Stage-1
evidence supports it.

## Hard constraints (from the handoff — must obey)

1. **RESEARCH_ONLY** — no production config change from IC-003B.
2. **G1 = 0.85** for Arm S — never amend gates to force `LIBRARY_OK`.
3. **No `--fresh`** unless the user explicitly accepts losing the N=4 checkpoints.
4. **No GPU rental** this week without Stage-1 profile evidence.
5. **`LIBRARY_OK ≠ expectancy / production authority`** (§6.5).
6. Append the §6 SESSION LOG block to `assistant_project.md` on completion.

## Files

- Driver: `scripts/research/ic003b_build.py`
- Orchestrator/checkpoint: `src/research/ic003b_sequence_geometry/build_all.py`
- DTW wall: `src/research/ic003b_sequence_geometry/dtw.py`, `cluster_dtw.py`
- Gates/schema (G1=0.85): `src/research/ic003b_sequence_geometry/schema.py`
- Prereg (frozen): `docs/research-readiness/h-ic003b-sequence-geometry-preregistration.md`

## Verification

- Early: resume log shows `SKIP` for both N=4 arms (checkpoint honored).
- End: `checkpoint.json` `status == "RUN_COMPLETE"` and `REPORT.md` + `report.json` +
  `SHAPE_LIBRARY.md` exist with a `program_verdict`.
- If a mid-run pause is needed: `python scripts/research/ic003b_build.py --mark-paused`
  (per-arm artifacts already flush after each finished S/T/C unit).


================================================================================
SOURCE_FILE: docs/implementation_plan/continue-last-session-some-modular-hummingbird.md
SOURCE_BYTES: 8699
PART: 3/10 FILE 2/16
================================================================================

# Resolve F-048 — RR ownership: DecisionEngine becomes semantic-approval only

## Context

**What prompted this.** The user articulated a clean separation of concerns and asked to "rewind
F-048" → *resolve the ownership call now*:

```
DecisionEngine  →  "Is this a valid market opportunity?"   (semantic evidence)
                   NOT "Will this make money?"             (economics)
```

DecisionEngine must never know fees / taxes / slippage / brokerage / portfolio / capital / RR.
The economic reward:risk question is owned downstream by UltronRiskGate; concrete SL/TP + sizing
by ExecutionPlanner.

**The current state is a half-measure.** F-048 (the RR gate consuming candle polarity ∈[0.5,1]
against `rr_threshold=1.5`, so `run()` executed 0/70,002) was patched in the working tree with a
*shim*: `_economic_rr_from_fusion` ([decision_engine.py:76](src/core/decision_engine.py:76)) that
teaches DecisionEngine to *recognize polarity and skip*. But DecisionEngine still holds
`rr_threshold` and still enforces an economic RR floor whenever `true_rr` is supplied. That is
DecisionEngine still knowing about economics — the exact mixing the user wants gone. The shim is
uncommitted and F-048's finding record still describes the pre-shim mechanism (a §6.2 drift).

**Intended outcome.** DecisionEngine's inputs become exactly {score, p_win, zone validity,
weak_component}. All RR — polarity (contract A, feeds FusionEngine averaging) and economic
(contract D, SL/TP-derived) — lives outside it. Economic RR is enforced solely by
`UltronRiskGate` Check 2 ([ultron_risk_gate.py:228](src/core/ultron_risk_gate.py:228),
`min_rr_ratio`, already cost-taxed by spread+slippage).

**Why this is safe (parity).** No production or backtest path supplies an economic RR to
DecisionEngine: `engine_runner` omits `true_rr` ([engine_runner.py:1035](src/core/engine_runner.py:1035))
and marks polarity; nothing else writes it. So the economic gate is already **dead-by-absence** on
every real path — removing it is *definitional, not behavioral*. On the sole XAUUSD candidate in
47,275 bars, the reject fires at `zone_gate_invalid` (evaluate line 159), three gates **before** the
RR gate (line 183), so the ledger cannot change. Behavior differs only in unit-test injectors that
feed economic RR directly.

**Governance note.** This is the one governance action being un-paused, because the user explicitly
asked to resolve F-048. Broader governance (State Consolidation, other findings) stays paused.

---

## Current state (verified this session, read-only)

| Fact | Evidence |
|---|---|
| Shim = skip-if-polarity, still enforces economic floor | [decision_engine.py:76-102,181-185](src/core/decision_engine.py:76) |
| `rr_threshold` is in the `decision_engine` section, **not** `params` | config grep → hash-neutral to remove |
| `decide_batch` routes through `evaluate()` — one gate site | [decision_engine.py:218](src/core/decision_engine.py:218) |
| Gate order: zone → score → p_win → **rr** | evaluate lines 159/164/169/183 |
| Only reader of `decision_engine.rr_threshold` is DecisionEngine | grep (live_engine_hook:474 is a comment; analytics/clustering `rr_threshold` is its own unrelated knob) |
| `low_rr` reject has a second, independent meaning | `analytics/clustering.py` post-hoc loss-cluster label — untouched |
| Economic RR already owned + reachable | UltronRiskGate Check 2, after ExecutionPlanner builds SL/TP |
| Only one test file has real dependencies | `tests/test_rr_contract_wiring.py` (imports the helper; asserts `low_rr`). `test_crt_fixes.py` injects `rr:2.0` > threshold → green either way |

---

## Changes

### 1. `src/core/decision_engine.py` — strip the economic RR gate (core change)

- Delete `_economic_rr_from_fusion` (lines 76-102).
- Delete `self.rr_threshold = _require_decision_cfg(config, "rr_threshold")` in `__init__` (line 119).
- Delete the local `rr_threshold` read (line 147) and the economic-RR gate block (lines 173-185).
- Result: `evaluate()` gates on zone validity → dynamic score → p_win → weak_component. No RR term.
- Update the module/class docstrings to state the ownership boundary explicitly (DecisionEngine =
  semantic approval; economic RR owned by UltronRiskGate).

### 2. `src/core/engine_runner.py` — drop the now-dead shim keys from `fusion_ctx`

The `fusion_ctx` built at [engine_runner.py:1031](src/core/engine_runner.py:1031) fed only the
deleted gate. Remove `"rr"` and `"rr_semantic"` (they were the shim's markers); keep
`"candle_polarity"` only if the collector audit record still wants it (harmless, non-decision).
Update the F-048 comment block to record the resolution. Parity-neutral — these keys were consumed
only by `DecisionEngine.evaluate`, which no longer reads them.

### 3. `configs/production/v2_multi_2026_04.json` — retire `decision_engine.rr_threshold`

Remove the orphaned key (line 133). **Hash-neutral** (not in `params`). A key that now gates
nothing is a config illusion (the F-056 class). This is an active-config edit → gated; approval is
via ExitPlanMode. Archived configs + baseline manifests keep their historical `rr_threshold: 1.5` —
do **not** touch those (they are point-in-time records).

### 4. `tests/test_rr_contract_wiring.py` — flip the C-contract tests

- Remove the `_economic_rr_from_fusion` import and `test_economic_rr_helper_skips_polarity_semantic`
  (helper deleted).
- `test_decision_engine_enforces_true_rr` → **invert**: assert DecisionEngine does **not** reject on
  `true_rr=1.0` (economics is not its job) → decision `execute`.
- `test_decision_engine_skips_polarity_rr_gate` → keep (polarity still yields `execute`), reframe
  comment (now trivially true — no RR gate exists).
- `test_true_rr_from_sl_tp_geometry_matches_tp1_mult` (contract D) + `test_active_config_rr_fusion_
  remains_disabled` (contract B) → keep unchanged.
- Add a test asserting `DecisionEngine` has no `rr_threshold` attribute (ownership guard), and a
  test that `UltronRiskGate` is the economic-RR owner (rr below `min_rr_ratio` → `rr_too_low_after_costs`).

### 5. Same-turn doc mandates (§6.2 / §6.3 / §6.4 Findings + Citation + Topic Sync)

- `docs/current-findings.md`: flip **F-048 → RESOLVED**, fill `Reversal:` (shim→full ownership
  separation; economic RR gate removed, not skipped), and update the **Repository Truths Index**
  row. Note the F-048 note that GD-001/002 body_ratio remediation was "BLOCKED behind this" — record
  that it is now unblocked (do not act on it here).
- `docs/topics/fusion-decision.md:23`: remove `rr_threshold` from the `decision_engine` key list.
- `docs/reference/config-reference.md:113`: retire the `rr_threshold` row.
- `src/runtime/live_engine_hook.py:474`: update the stale F-048 comment (mechanism resolved).
- SESSION LOG (`assistant_project.md`) + a Documentation Drift Protocol audit entry.

---

## Explicitly NOT in scope

- No TradeEconomicsEngine (layer 10) — the two unrelated cost models (`research/costs.py` 12bps vs
  UltronRiskGate spread+slippage) stay as-is; consolidating them is a separate future stage.
- No re-enabling `rr_fusion` (contract B stays `enabled:false`, §6.5 / F-038).
- No change to UltronRiskGate logic — it already owns economic RR; we only stop duplicating it.
- No State Consolidation, no other findings (governance stays paused beyond F-048).

---

## Verification

1. **Unit** — RR contract + decision surface:
```bash
python -m pytest tests/test_rr_contract_wiring.py tests/test_crt_fixes.py -q
```
2. **Config loads without the key** + validator passes:
```bash
python -c "import sys; sys.path.insert(0,'src'); from config_layer.production_config import get_prod_config; c=get_prod_config(); assert 'rr_threshold' not in c['decision_engine']; print('ok')"
```
3. **No remaining reader**:
```bash
python scripts/analysis/... # grep: no src/ reference to decision_engine.rr_threshold outside comments
```
4. **Ledger parity (the real proof)** — gate-ON XAUUSD backtest, before vs after, identical
   `total_setups` + `rejection_reasons` (expect 1 setup, reject `zone_gate_invalid`):
```bash
BACKTEST_ENGINE_GATE=1 python scripts/analysis/model_evidence_survey.py --csv data/mt5/XAUUSD_M15.csv --instrument XAUUSD
```
5. **Feature parity untouched** (no feature change — should be trivially identical):
   XAUUSD vector SHA `37f43f449af0720f…`.

**Completion criterion:** DecisionEngine has no RR/economic surface; `rr_threshold` gone from the
active config (hash unchanged); economic RR enforced only by UltronRiskGate; XAUUSD gate-ON ledger
byte-identical; F-048 recorded RESOLVED with the doc set synchronized; affected floors green.


================================================================================
SOURCE_FILE: docs/implementation_plan/continue-refactored-hamster.md
SOURCE_BYTES: 8251
PART: 3/10 FILE 3/16
================================================================================

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


================================================================================
SOURCE_FILE: docs/implementation_plan/create-new-branch-from-sequential-bachman.md
SOURCE_BYTES: 3745
PART: 3/10 FILE 4/16
================================================================================

# New branch from `patch` + resolve the deferred push

## Context

On 2026-07-02 a live Groq key in `.env` (commits 278d993/eb64269) blocked `git push` via GitHub push-protection. The history was scrubbed via an isolated clone + `filter-branch`, and the **scrubbed line was already pushed** that day (`origin/patch` fast-forwarded `5897209..05d4ad0..e0e7971`). A later session deferred pushing with the note "pushing this branch is a separate, weightier decision given its scrubbed history" — but that caution is now stale: **verified** `origin/patch` and `origin/main` contain zero `.env` history (`git log origin/{patch,main} -- .env` empty; `ls-remote` shows only clean `main`+`patch` on the remote). The only unpushed commit on `patch` is 0c378a9 (docs, truth-layer registry v2.0) — a routine fast-forward.

The old secret survives only in two **local** refs — `backup/pre-env-scrub-20260702` and `claude/elegant-dubinsky-a2b441` (stale `.claude/worktrees/` checkout). **User decision: keep both for now** (key rotation pending; no publication risk since they're local-only).

The working tree holds ~95 modified + 1 deleted tracked files (+1931/−497): F-042/F-043 finding rows, `flow_context/*.json`, `ui_kits/control_plane/*`, broad `src/` edits, doc syncs. User decisions:

- New branch **`feature/truth-registry-v2`** from `patch` @ 0c378a9, checked out.
- **Commit the WIP onto the new branch** (patch stays clean at 0c378a9).
- **Push both**: `patch` (fast-forward to 0c378a9) and the new branch.
- Do **not** delete the secret-bearing local refs.

## Steps

1. **Pre-flight (read-only).** Confirm `patch` @ 0c378a9, `git stash list` untouched, and re-check `git status` for any *untracked* files (first status pass was truncated) — we will commit tracked changes only.
2. **Create + switch:** `git switch -c feature/truth-registry-v2` (from `patch`).
3. **Stage tracked changes only:** `git add -u` — picks up the ~95 modifications + the `.claude/scheduled_tasks.lock` deletion, and cannot add untracked files (`.env` is gitignored+untracked; double-check with `git status --short` that nothing staged is a secret).
4. **Session log (§6 mandate):** append the SESSION LOG ENTRY block to `assistant_project.md` before committing (the pre-commit hook / `test_session_log.py` targets this file), stage it too.
5. **Commit** with a descriptive message (WIP consolidation: F-042/F-043 doc sync, flow_context, control-plane UI kit, src edits) + `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. Let the pre-commit hook run (~71 tests); if it fails, investigate — never `--no-verify`.
6. **Push:** `git push origin patch feature/truth-registry-v2 -u` — both are plain fast-forwards / new-ref pushes; **no force push anywhere**. LFS size warnings are known-benign.

## Verification

- `git log --oneline -2 feature/truth-registry-v2` shows the WIP commit atop 0c378a9; `git status` clean (apart from intentionally-kept untracked files).
- `git ls-remote origin refs/heads/patch refs/heads/feature/truth-registry-v2` → patch=0c378a9, new branch=new SHA.
- `git show --stat HEAD | grep -i "\.env"` → empty (no secret in the new commit).
- Secret-bearing local refs untouched: `git branch --contains 278d993` still lists only the two kept refs.

## Notes / flags

- The WIP includes edits to `configs/production/v1_multi_2026_03.json` and an archived v2 config — these are the user's own working-tree changes being committed verbatim, not config edits I author; `ACTIVE_VERSION` is untouched (no §6.2 approval gate triggered beyond this user-approved plan).
- Groq key rotation remains the user's out-of-band action; the kept local refs should be deleted once rotated (standing open question in the session log).


================================================================================
SOURCE_FILE: docs/implementation_plan/crtstateresolver-backtestrunner-how-each-shimmering-toast.md
SOURCE_BYTES: 1797
PART: 3/10 FILE 5/16
================================================================================

# Plan: CRTStateResolver vs BacktestRunner — Consolidated OHLCV→States Report

## Context

User wants a **consolidated comparison report** showing:
1. How **CRTStateResolver** transforms OHLCV → features → CRT states
2. How **BacktestRunner** performs the same transformation
3. The **latest MT5/XAUUSD run report** (probably in `results/` or `reports/`)

This is exploratory/documentation work. No code changes expected — the goal is **visibility into the two parallel paths**.

## Phase 1: Exploration (in progress)
- [ ] Locate CRTStateResolver (class definition, entry point, API)
- [ ] Locate BacktestRunner (class definition, entry point, feature injection)
- [ ] Map feature pipeline: OHLCV → FeaturePipeline.run() → 38-dim vector
- [ ] Identify state emission: where CRTState objects are created/emitted in each path
- [ ] Find latest MT5/XAUUSD run artifacts (results dir, report files, timestamps)

## Phase 2: Report Structure (pending)
Will create a consolidated markdown report covering:
- **Data Flow Diagram** (text/ASCII or reference to `.dot` graph)
- **CRTStateResolver path** (signature, input, output, state transitions)
- **BacktestRunner path** (signature, input, output, state transitions)
- **Feature pipeline bridge** (where they diverge/converge)
- **State lifecycle** (how states are updated per candle)
- **Latest MT5/XAUUSD metrics** (attached from run report)

## Phase 3: Output Delivery (pending)
- Consolidated markdown report
- Link to latest run artifacts
- Visual comparison table (if relevant)

## Critical Files (to be confirmed by agent)
- TBD: CRTStateResolver location
- TBD: BacktestRunner location
- TBD: FeaturePipeline location
- TBD: Latest run report path

---

**Status:** Awaiting Explore agent completion to populate critical files.


================================================================================
SOURCE_FILE: docs/implementation_plan/d-tradelatest-active-models-yaml-d-trad-async-tulip.md
SOURCE_BYTES: 4190
PART: 3/10 FILE 6/16
================================================================================

# Add flags + key-existence checks linking active_models.yaml ↔ ACTIVE_VERSION config

## Context
"Link both files" evolved (via a multi-LLM design pass) into a model coverage registry. The
decisive finding: **that registry already exists** — `active_models.yaml` is schema **v2.1** with
per-model `reachability`/`optimization` blocks, and `tests/test_active_models_registry.py` already
links it to the config named by `configs/production/ACTIVE_VERSION` **by pointer resolution, not
value equality**, with a §6.5 guard that already forbids `threshold|min_delta|promotion` keys in
`optimization` (the exact "don't assert yaml==config" failure the chain warned about).

(E-001 note: my first read this session showed v2.0 — a stale working-tree snapshot; the file is now
committed at v2.1. Verified via `git show HEAD:` + clean `git status --porcelain`.)

The one genuine gap, which the user pre-approved: the config link is at **section** granularity
today (`crt_engine`, `params` exist as top-level keys). It does not yet assert (1) binary runtime
**flags** match the live values, nor (2) individual **config_key existence**. This plan adds both —
additive, hash-neutral, grants no authority.

## Change 1 — one additive yaml field (make rr_fusion machine-readable)
`rr_model.runtime` states "rr_fusion disabled" only in prose (`notes` + status comment). Add a
structured twin so the flag test can compare directly:
```yaml
rr_model:
  runtime:
    rr_fusion_active: false   # machine-readable twin of the F-038 prose; config engine_runner.rr_fusion.enabled
```
(yaml is not hashed — only the config `params` block feeds `config_hash` — so this is hash-neutral.)

## Change 2 — semantic-flag consistency test (high-confidence, green on arrival)
Add `test_runtime_flags_match_active_config` to `tests/test_active_models_registry.py`. Resolve the
active config via the existing `test_config_sections_are_active_config_keys` loader (ACTIVE_VERSION →
JSON). Assert this fixed flag map (FLAGS ONLY — never thresholds; yaml documents code defaults,
config holds tuned overrides like retest_depth_max 0.25 vs 0.15):

| yaml path | config path (ACTIVE_VERSION) |
|---|---|
| `bitnet.runtime.enabled` | `crt_engine.use_bitnet` |
| `zone_gate.runtime.zone_mode` | `engine_runner.zone_mode` |
| `zone_gate.runtime.registry_file` | `engine_runner.zone_registry_path` |
| `gaussian.runtime.engine` via `{HeuristicGaussianEngine: "heuristic"}` | `engine_runner.gaussian_impl` |
| `rr_model.runtime.rr_fusion_active` (Change 1) | `engine_runner.rr_fusion.enabled` |

## Change 3 — individual config_key existence test (verify-first, then pin)
Add `test_yaml_config_keys_exist_in_schema`. Build the key set from the CRT `detection.*.config_keys`
+ `thresholds` block; assert each resolves into `{f.name for f in dataclasses.fields(CRTConfig)}` ∪
the `params`/`crt_engine` section keys. Reuse the `CRTConfig` import pattern from
`scripts/analysis/config_reachability.py:57`.

**Discipline (§6.5 — don't pin a biased instrument):** run it first as a report (print unresolved
keys) to confirm 0 *benign* naming mismatches (e.g. `session_windows`, `sizing_bands`). If any
surface, classify each as real drift (fix yaml/code + doc decision per §6.2) vs. a naming-convention
gap (adjust the comparison) BEFORE turning it into a hard assertion. Do not ship it red.

## Critical files
- `active_models.yaml` — Change 1 (one field).
- `tests/test_active_models_registry.py` — Changes 2 & 3 (two functions; reuses its own config loader
  + `CRTConfig` via `dataclasses.fields`).
- Do NOT touch `tests/test_crt_state_invariants.py` (semantic YAML↔code invariant stays there).

## Out of scope (parked per §6.5 — separate axis / premature)
MT5 signal→position evidence bridge; coverage-% dashboards; a new CLAUDE.md governance section.

## Verification
`python -m pytest tests/test_active_models_registry.py tests/test_crt_state_invariants.py` green.
Red-check: flip `use_bitnet` or `rr_fusion.enabled` in a scratch config copy → flag test red;
rename a yaml `config_key` → existence test red. Then §6/§6.2 SESSION LOG + doc-impact entry
(governed-config-adjacent turn).


================================================================================
SOURCE_FILE: docs/implementation_plan/d-tradelatest-crtclaude-pdf-go-through-iterative-otter.md
SOURCE_BYTES: 5508
PART: 3/10 FILE 7/16
================================================================================

# Plan: Formalize manual CRT analysis checklist as a docs/topics/ entry

## Context
Following the CRTClaude.pdf note-taking pass (see below), the user wants the repeatable input
template (reference timeframe / entry timeframe / pre-marked key levels) and the probability/
quality scorecard that emerged ad hoc in that chat **formalized into a standing checklist**, and
linked to Tradelatest's actual "ins/outs" rather than living as a one-off chat artifact.

Explore agent findings: there is **no existing discretionary/manual-chart-analysis concept** in
the repo.
- `src/inout/` is pure market-data plumbing (candle fetchers: Hummingbot, AlphaVantage, MT5,
  perp-funding) — not a manual-input layer.
- `manual_tools/trade_generator.py` is a DEMO-only MT5 *test-trade fixture generator* for broker-
  semantics validation — unrelated to discretionary chart reading.
- `docs/topics/` (the concept↔code↔tests index, [readme.md](docs/topics/readme.md)) has 26 topics
  covering the **automated** spine (CRT engine → Fusion → Decision → ExecutionPlanner →
  UltronRiskGate) but nothing for a human discretionary workflow.

So per CLAUDE.md §6.2 rule 1 (existing-doc-first) there is genuinely no doc that owns this topic —
a new one is the correct (not the lazy) choice, structured per the `_template.md` pattern so it's
governed the same way every other topic is (Topic Sync Mandate, §6.4).

The "link with Tradelatest in and outs" instruction is interpreted as: cross-reference the doc to
the real automated **Ins/Outs** of the spine (per `_template.md`'s own "Ins / Outs" section) so the
manual SOP explicitly states where it *feeds* the automated system (or explicitly that it
currently doesn't) — not as literal code under `src/inout/`.

## What will be created
**New file:** `docs/topics/manual-crt-checklist.md`, filled from `_template.md`'s skeleton:

- **In plain language:** discretionary CRT (romeoopt model) chart-reading SOP — human applies it
  manually in TradingView; not executed by any Tradelatest engine. Exists to make repeatable what
  was previously re-derived turn-by-turn in chat.
- **Code covered:** none (by design) — note explicitly: *"no Tradelatest module implements this;
  it is a human-side companion to the automated CRT spine, not a code path."* Cross-link
  `docs/topics/crt-spine.md` only as the conceptual cousin (range/AMD ideas the automated
  `crt_engine_v2.py` formalizes differently), not as a shared implementation.
- **Ins / Outs** (the actual checklist):
  - **Ins (inputs the user must supply each time):**
    1. Reference CRT timeframe (Monthly/Weekly/Daily/4H) — which candle defines CRT High/Low.
    2. Entry/execution timeframe (1H/15m) — where the LTF confirmation (CSD) is sought.
    3. Pre-marked key levels already on the chart (PMH/PML, PWH/PWL, rejection/order
       blocks, FVGs) — Claude must not invent these from a raw screenshot.
  - **Outs (what the checklist produces):**
    1. CRT High / CRT Low for each timeframe in the top-down stack.
    2. Purge status per level: not-yet-purged / wick-only / closed-back-inside (Turtle Soup
       confirmed).
    3. Directional bias + target level.
    4. **Probability/quality scorecard** (the BTCUSD rubric, generalized):
       - Setup Quality score (/10): + inside bars within CRT, + CSD confirmation present, +
         clean single-wick purge, + timeframe coupling honored (HTF key levels referenced).
       - Probability band (e.g. 65-70%) with explicit **factors-for** / **factors-against** table.
       - Invalidation condition (level that kills the setup) + confirmation triggers (levels that
         must be reclaimed) — always stated, never omitted.
- **Entry points & validations:** "Reached via: manual chat/session walkthrough with Claude, not a
  CLI or control-plane route." "Validated by: none (discretionary, no backtest/replay gate) — this
  is explicitly **outside** the §6.5 Authority Ladder; it earns no production authority no matter
  how good a scorecard looks."
- **Tests:** none — explicitly state why (manual/discretionary, not governed code).
- **Fits in architecture:** one link to `docs/architecture/signal-flow.md` noting this sits
  *outside* the spine entirely — a human pre-trade research aid, parallel to but not feeding the
  automated candle→order path.
- **Discussion:** seed with one dated entry noting the origin (CRTClaude.pdf chat, 2026-06-26) and
  the open question: *should this ever become a real `Interpreter` (per
  `docs/topics/interpreter-contract.md`) so it's measurable against G001?* — flag as a future
  option, not a commitment (Authority Ladder: information ≠ authority).

**Edit:** `docs/topics/readme.md` — add one row to the Topic index table:
`| Manual CRT checklist (discretionary) | manual/research | _none (human SOP)_ | manual chat
session | _none_ | stub | [manual-crt-checklist.md](manual-crt-checklist.md) |`

## Why "stub" status, not "living"
Per the status legend, `stub` = row only / doc exists but isn't tied to maintained code. This is
honest: there's no code to drift against yet. If/when this becomes an `Interpreter` per the
Interpreter Contract layer, promote to `living` then.

## Verification
Doc-only change — no tests to run. Sanity check: confirm the new file follows `_template.md`'s
section headers exactly (so `Sync`/`Audit` tooling that scans `docs/topics/*.md` doesn't choke),
and confirm the new readme.md row matches the existing table's column count/order.


================================================================================
SOURCE_FILE: docs/implementation_plan/d-tradelatest-docs-analysis-feature-ide-foamy-sutherland.md
SOURCE_BYTES: 12137
PART: 3/10 FILE 8/16
================================================================================

# Visual CRT Re-measurement — MC-VCRT-XAUUSD-M15-V2

**Prior phase (complete):** F-082 shipped the corrected cost model (SEM-015) + honest stop fills (SEM-016), config-gated and parity-proved. User has since agreed UNK-COST-02 (broker decomposition supersedes the volatility proxy) and authorised this re-measurement.

**Lane:** research measurement. **Authority:** diagnostic only — no G001, no promotion, no `ACTIVE_VERSION` change, `economic_claims_allowed` stays false.

---

## Context

### Why now

F-081 measured the Visual CRT trade object and returned 0 PROMOTE on both arms. Its net figures were **cost-dominated by a constant we have since proved wrong for XAUUSD by ~11x**. With the ruler fixed, the question "is this null information-driven or cost-artifact-driven?" is finally answerable.

### What the sealed contract requires

`MC-VCRT-XAUUSD-M15-V1.json` `metrics.kill_criteria` names this explicitly:

> Changing ANY frozen dimension after seeing outcomes (… **cost model, exit model** …) requires a NEW `MC-*` id, a new hypothesis and a new pre-registration (V2) — never an edit to this instance.

So a new instance is the *sanctioned* path, not a workaround. V1 stays sealed and registered.

### The second problem, found while reading V1

V1's contract declares two things its run never produced:

| Declared in the sealed contract | Actually executed |
|---|---|
| `splits.scheme: single_holdout_chronologic`, embargo 96 bars, purge overlapping horizons, seed 20260817, "exact dates locked in `split_manifest` at run time" | **No split at all.** No `split_manifest` artifact exists. |
| `metrics.success_gate`: "…AND beats the pre-registered controls (`random_entry`, `long_only`)" | **No controls run.** |

`src/research/visual_crt/driver.py` contains **zero** occurrences of `control`, `random_entry`, `long_only`, `oos`, `holdout`, `embargo`, `purge`, or `split`; the ledger rows carry no split or control fields.

**This does not undermine F-081's verdict.** Controls and OOS are gates a *positive* result must clear; an arm rejected at the absolute-expectancy stage never reaches them. The gap matters precisely when something comes back positive — which is exactly the case this re-run could produce. So V2 implements them.

### A third find, load-bearing for the implementation

`driver.py:140-150` has its own `_net_r` with a hardcoded `ROUND_TRIP_BPS = 12.0`. It **never imports `research.costs`**. F-082's `cost_model` selector therefore does not reach this driver at all — a fourth independent cost site. Fixing this is what makes the re-run possible.

### Intended outcome

A complete, contract-faithful V2 measurement that isolates the effect of the corrected measurement basis, with V1 preserved and byte-reproducible.

---

## Pre-registration (write and seal BEFORE running anything)

V1 earned its credibility by sealing the contract before the detector existed. V2 keeps that discipline: the contract, the predicted outcome, and the decision rules below are committed **before** the controls/OOS code is written and before any V2 number is produced.

### Predicted outcome

Both arms **still REJECT**. Net expectancy moves from decisively negative to mildly negative; gross stays indistinguishable from zero.

| Arm | V1 gross | V1 net | V2 predicted gross | V2 predicted net |
|---|---|---|---|---|
| A (displacement close) | +0.0080R | −0.5559R | ≈ 0.000 … +0.007R | **≈ −0.03 … −0.08R** |
| B (retest close) | −0.0835R | −1.2617R | ≈ −0.09 … −0.12R | **≈ −0.15 … −0.30R** |

Reasoning: cost in R falls ~10x (Arm B benefits most — its median risk is 0.78 ATR vs Arm A's 2.64, so it was far more cost-sensitive); the adverse fill pushes *gross* slightly **more** negative (Arm A 42% stop rate, Arm B 71%). The two corrections partially offset, which is why they must never be described as one "costs were too high" fix.

### Decision rules (fixed in advance)

1. **Prediction confirmed (both REJECT)** → register as confirmatory. The null is information-driven, not a cost artifact. This is the expected result and grants nothing.
2. **Either arm turns positive** → **investigate in the same turn** (user decision). Treat as a defect hypothesis first, in this order: cost-model sign/leg error → adverse-fill sign error → V1-reproduction drift → look-ahead in the new split/control code. Report the diagnosis with the numbers. A positive that survives investigation is **still not registrable as an edge**: it would require a fresh pre-registered test on unseen data, because a second look at the same corpus under a better ruler cannot license an economic claim.
3. **Controls not beaten** → the arm fails the success gate regardless of expectancy sign.
4. **OOS retention below IS** → report; do not retune. Retuning any frozen dimension after seeing V2 outcomes requires a V3.

### Multiplicity

V2 is a **measurement-basis replication** of V1's two pre-registered arms, not two new hypotheses. It inherits V1's Bonferroni α=0.025 and spends no new alpha. It cannot "rescue" V1: a null that stays null is confirmatory.

---

## Approach

### Step 1 — Governance pre-flight

- BUILD_IMPACT_MANIFEST `CH-vcrt-remeasure-v2` against `docs/governance/change_contracts.json`; classes `SCRIPT_LIFECYCLE_CHANGE` (new runner) + `DOCUMENTATION_ONLY`, carrying **UNK-COST-01** forward as a non-blocking unknown (still no registered class for the research measurement harness).
- Ground every new noun via `scripts/governance/query_semantic_os.py --ground` (§6.7).

### Step 2 — Seal `MC-VCRT-XAUUSD-M15-V2.json`

New file in `configs/research/measurement_contracts/instances/`. Copy V1 and change **exactly two** frozen dimensions:

| Surface | V1 | V2 |
|---|---|---|
| `costs.cost_model_id` | `CM-XAUUSD-LEGACY-12BPS-UNCALIBRATED` | `CM-XAUUSD-COMPONENT-MEASURED-V1` (SEM-015, sourced from the manifest sha256 `6ce4abf5…`, per-leg, `entry_slippage_basis=PROXY_FROM_STOP`) |
| `exits.exit_model_id` | `EX-VCRT-INTRABAR-V1` | `EX-VCRT-INTRABAR-ADVERSE-V2` (SEM-016 `AdverseFill(stop_slippage=0.09, model_gaps=True)`) |

**Byte-frozen from V1:** `population` (same corpus, same sha256 `4d73f5ce…`, 47,275 bars), `features`, `labels`, all geometry constants, horizon 40, duplicate rule, both arm definitions, multiplicity.

Also carried forward verbatim: `authority.economic_admissible: false`, `trust_status.economic_claims_allowed: false`, every `prohibited_substitutions` entry, and the `kill_criteria`. Add a `supersedes_note` recording that V2 exists because V1's cost and exit models are superseded — and that V1's *verdict* is not.

Add to `trust_status.open_risks_non_blocking`: stop slippage rests on n=7 demo fills; entry slippage is a declared proxy; V1 did not execute its declared splits/controls.

### Step 3 — Make the driver contract-bindable (V1 stays byte-reproducible)

`src/research/visual_crt/driver.py`:

- Replace the hardcoded `_net_r` with an injected cost function. Default = today's exact 12bps arithmetic, so **V1 reproduces byte-identically**.
- Thread an `adverse_fill` parameter into the `forward_walk` call at `:279`; default `None` = V1 behaviour.
- Add `contract_id` as a parameter rather than the module constant, so the ledger stamps the right id.
- Extend `LedgerRow` additively with `split` (`"is"`/`"oos"`), `cost_model_id`, `fill_model_id`. V1 re-runs must still produce byte-identical rows — so write the V1 ledger through a compatibility path that omits the new fields, or regenerate V1's expected artifact and diff against the committed one explicitly.

**Reuse, do not reimplement:** `research.costs.ComponentCostModel` (+ `.from_manifest`, `.cost_r(exit_kind=…)`), `research.measurement.forward_walk.AdverseFill`, `research.provenance.provenance_block(cost_model=…, fill_model=…)`.

### Step 4 — Implement the declared splits and controls

New module `src/research/visual_crt/controls.py` (keeps `driver.py` focused, mirrors the package's existing one-concern-per-file layout):

- **`single_holdout_chronologic`** — per arm, sort entries by `entry_ts`, last 20% = OOS; drop IS entries whose 40-bar exit horizon overlaps the OOS start (purge); enforce the 96-bar (24h) embargo. Emit `split_manifest.json` with the exact locked dates, as the contract requires.
- **`random_entry` control** — same n, same direction mix, same SL/TP geometry, entry bars drawn uniformly from the corpus. Seeded; declare the seed in the contract.
- **`long_only` control** — same entry bars and geometry as the arm, direction forced long. This is the control that matters most here: gold trended up across 2024-2026, so an arm must beat passive long exposure, not just zero.

Both controls resolve through the **same** `forward_walk` + cost model as the arm — otherwise the comparison is rigged.

### Step 5 — Runner script (SITS-registered)

`scripts/research/vcrt_remeasure_v2.py` — thin `argparse` wrapper (no business logic per §3.3), taking `--contract` and `--out-dir`. Register the same turn: `script_census.py --write-stubs` → `seed_script_registry.py` → `generate_script_matrix.py`.

Outputs to `results/visual_crt/mc_vcrt_xauusd_m15_v2/`: `ledger_arm_{A,B}.jsonl`, `controls_{random_entry,long_only}_{A,B}.jsonl`, `split_manifest.json`, `metrics.json`, `summary.json` — each carrying the full provenance block.

### Step 6 — Findings

Two findings, different types, registered per the E-001 six-question ritual:

- **F-083 (GOVERNANCE)** — V1 declared an OOS split and two controls in its sealed contract and executed neither; V2 closes the gap. Explicitly state that F-081's REJECT is unaffected (a null never reaches those gates) and why the gap still mattered.
- **F-084 (ECONOMIC)** — the V2 re-measurement result under the corrected basis, scoped to whatever actually comes back.

Both rows added to `docs/current-findings.md` **and** the CLAUDE.md Truths Index (the test enforces both). Add a forward pointer on F-081; never edit its verdict.

---

## Verification

**Gate 1 — V1 reproduction (must pass before any V2 number is trusted).** Re-run the driver under V1 bindings and diff against the committed artifacts:

```bash
venv/Scripts/python.exe -m pytest tests/research/test_visual_crt_trade_object.py -q
```

Then byte-diff regenerated `ledger_arm_A.jsonl` / `ledger_arm_B.jsonl` against `results/visual_crt/mc_vcrt_xauusd_m15_v1/`. A refactor that cannot reproduce V1 invalidates V2 — stop and fix.

**Gate 2 — the V2 run.**

```bash
venv/Scripts/python.exe scripts/research/vcrt_remeasure_v2.py --contract MC-VCRT-XAUUSD-M15-V2
```

Check against the pre-registered prediction table above, then apply the decision rules — including the same-turn investigation if either arm turns positive.

**Gate 3 — floors and governance.**

```bash
venv/Scripts/python.exe -m pytest tests/research/test_visual_crt_trade_object.py tests/test_component_cost_model.py tests/test_forward_walk_adverse_fill.py tests/test_measurement_contract.py tests/test_current_findings.py tests/test_topic_docs.py tests/test_script_registry.py -q
```

Plus a new floor `tests/research/test_vcrt_v2_contract.py`: V2 differs from V1 in exactly the two declared surfaces; controls run through the same cost model as the arms; the OOS split respects embargo and purge; `economic_claims_allowed` is false.

**Known-failing, out of scope:** the 9 pre-existing GREEN_FLOOR failures recorded under F-071, and `test_session_log.py` entry-count (81 vs cap 30 — rotation rewrites a file other sessions append to concurrently, so it stays flagged for the user, not run unilaterally).

---

## Explicitly not doing

- **No edit to `MC-VCRT-XAUUSD-M15-V1.json`** or to F-081's verdict.
- **No retuning of any frozen dimension** after seeing V2 outcomes — that requires a V3.
- **No economic claim** whatever V2 returns; `mt00`/`mt01` remain UNRUN, 0/27 probes.
- **No production activation** — `ACTIVE_VERSION` (`v2_htfcrt_2026_08`) untouched, UltronRiskGate cost tax still declared-but-inert.
- **No re-measurement of any other finding** — this turn is Visual CRT only.


================================================================================
SOURCE_FILE: docs/implementation_plan/d-tradelatest-docs-analysis-feature-ide-iterative-codd.md
SOURCE_BYTES: 12616
PART: 3/10 FILE 9/16
================================================================================

# Exit Geometry & Dynamic Stop Modifications — a decomposition

Backtest-only. Decompose **why** the oracle program's information never crosses zero, and measure
the one class of exit behaviour the repository has never built: causal dynamic stop policies on the
production two-target object.

---

## Context

The profitable-entry oracle program (2026-08-21) ended on a split result. Conjunctions of declared
states beat the base rate at a **6.2–7.6× excess over a measured block-permutation null** — real
information, not a multiple-comparisons artifact — while **0 of 84 state cells cleared zero** on the
net basis across all 8 arm×direction combinations. It left a narrow question:

> not *is there structure* (there is), but *why the structure will not cross zero* — exit geometry,
> cost, or the size of the information itself.

This program answers that by accounting, not by another search. Three things make it tractable now
and make it different from a re-run of F-025:

1. **Every exit analysis in this repo was measured on the wrong exit object.** `research/exit_grid.py`
   (F-025) and `research/forensics.py` both drive `forward_walk`, which models one TP, no partial and
   no trail. Production realises 50% at TP1, moves the stop to a **half-way trail**, and runs the
   remainder to TP2. `multi_tp_walk` now exists and is triangulated, so the real object is measurable
   for the first time.
2. **The cost basis changed.** `exit_grid.ceilings` computes `min_achievable_cost` from flat 12 bps.
   On XAUUSD that is ~11× the measured broker cost (F-082: 0.5394R vs 0.0477R). Every ceiling in the
   F-025 lineage inherits that. SEM-015 `ComponentCostModel` replaces it here.
3. **Production has exactly one dynamic stop** — the half-way trail at TP1 — and whether it helps has
   never been measured. The whole class (ratchet, breakeven-at-R, time-decay, chandelier) is absent
   for the two-target object.

**Scope note, not a correction.** F-025 was crypto-scoped, single-TP, flat-bps. This is XAUUSD,
two-target, measured-cost. Different object, different cost basis, different instrument — it neither
confirms nor overturns F-025, and will not cite it as support (§6.2).

**Authority.** Descriptive decomposition. `economic_claims_allowed: false`, no promotion, no fusion
weight, no G001, no `ACTIVE_VERSION` change. The 236-bar holdout **stays sealed** — mining happens on
TRAIN only and no cell is claimed as a forward result.

---

## Two constraints that govern the whole design

### 1. Intrabar path ambiguity — stops update on bar CLOSE only

A ratcheting stop **cannot be faithfully simulated from OHLC**. If the stop moves using bar *i*'s
high and bar *i*'s low also reaches the new level, the within-bar order is unknowable, and resolving
it favourably is silent optimism that compounds over every bar of every trade. Program 10
(`research/path/ambiguity_census.py`) already established this failure class for the *fixed*-stop
tie-break (population P1); for a ratchet it is strictly worse, because the ambiguity recurs on every
bar rather than only on spanning bars.

**Rule:** the stop level applied to bar *i* is a function of bars **≤ i−1** only. Enforced by test —
a policy that reads the current bar's high/low must fail. The same-bar-update variant is measured
once as a declared **optimism bound** so the size of the assumption is reported rather than hidden;
it is never the primary basis.

### 2. R is comparable across stop widths — but only under a stated assumption

`ComponentCostModel.cost_r` is `cost_price / risk_distance`. Under fixed-fractional sizing (position
size = risk budget ÷ risk distance), 1R is the same currency for every geometry, and that ratio is
exactly the fixed-fractional-correct cost. So E[R] **is** comparable across stop widths — this is the
assumption that licenses comparing a 0.5×ATR stop against a 3×ATR one at all, and it gets stated in
the report rather than assumed. Its limits get stated too: it ignores margin/capital constraints and
the differing absolute exposure a wider stop implies.

---

## Reuse (existing, verified — do not rebuild)

| Need | Existing | Note |
|---|---|---|
| Exit-agnostic MFE/MAE ceiling | `forward_walk.horizon_excursion` | tie-break immune by construction |
| Ceiling arithmetic + regime label | `exit_grid.ceilings`, `min_achievable_cost` | swap flat `CostModel` → `ComponentCostModel` |
| Capture ratio, loss-mechanism ranking | `forensics._opp_bundle`, `_loss_mechanisms`, `_classify` | `capture_ratio = realised / mfe_r` already implemented |
| Two-target production kernel | `research/oracle/multi_tp_walk.py` | triangulated; extend additively |
| Ratchet reference implementations | `forward_walk` `exit_model="trailing"`, `replay/timing_reconstructor.py` | two independent priors to cross-check a new ratchet against |
| Block bootstrap / permutation / partition | `research/oracle/scan.py` | `block_bootstrap_mean_ci`, `l3_permutation_null`, `partition`, `effective_n` |
| Labelling driver | `research/oracle/labeler.py` | `label_corpus` already takes geometry as parameters |
| Corpus | `results/research/bar_matrix/XAUUSD_M15/` (47,197×124), `oracle_labels/`, `oracle_scan/scan_report_train.json` | all on disk |

---

## Stages

### Stage A — Ceilings first (this is a gate, not a preamble)

Bound what *any* exit could achieve before searching the space. Reuse `horizon_excursion` over the
full oracle universe (every bar × both directions) with SEM-015 cost.

| Ceiling | Definition | Attainable? |
|---|---|---|
| perfect-foresight | `E[MFE_r] − min_cost` | No — requires knowing the path |
| **causal** | best E[R] over the policy grid, using only past bars | Yes, but mined (optimistic) |
| incumbent | production geometry's actual E | This is what runs today |

Plus the `capture_ratio` distribution (realised ÷ MFE) via `forensics._opp_bundle`, and the
loss-mechanism ranking, both stratified by exit reason.

**Gate:** if the perfect-foresight ceiling is ≤ 0 net of measured cost, then no exit policy of any
kind can help, the exit axis closes with a decisive answer, and Stages B–D are not run. F-025
measured `reality_gap` +4.16R on a different basis, so this probably won't fire — but computing it
first is what prevents a pointless search, and it is cheap.

### Stage B — Dynamic stop policy class (register **SEM-019** first, §6.6)

New `src/research/oracle/stop_policy.py`. A `StopPolicy` is a pure function
`(trade_state, bars_so_far) → new_stop`, causal by construction. `multi_tp_walk` gains one optional
`stop_policy=None` parameter; `None` reproduces today's behaviour byte-identically.

| Policy | Params | Why it's in the grid |
|---|---|---|
| `fixed` | — | **The control.** Measures whether *any* dynamic stop helps. |
| `production` | — | Today's half-way trail at TP1. The audit baseline. |
| `breakeven_at_r` | x ∈ {0.5, 1.0, 1.5} | The thing the config key `partial_tp_breakeven_enabled` claims to do but doesn't |
| `ratchet_r` | k ∈ {0.5, 1.0, 1.5} | Trail k×R behind the running extreme |
| `ratchet_atr` | k ∈ {1, 2, 3} | Chandelier; scale-invariant counterpart |
| `time_decay` | n ∈ {6, 18} | Targets F-024's asymmetry: losers resolve ~immediately, winners mature over ~90 min |

Invariants, each a test: a stop never moves **away** from price (widening risk is not a stop);
`production` + `fixed` reproduce existing labels exactly; a policy peeking at the current bar fails.

### Stage C — Geometry × policy sweep, with the controls that bind

Grid: `sl_geom{2} × tp1_mult × tp2_mult × partial_fraction{0, 0.25, 0.5, 0.75} × horizon{20,40,96} × policy`.
Compute is not the constraint (377k labels took 10.6s), so **multiplicity discipline matters more,
not less**: block bootstrap on every interval, block-permutation null on the sweep, primary arm
declared up front.

**Pre-declared, and load-bearing:** an *unconditionally* profitable cell is a **bug signal, not a
discovery**. Every-bar-both-directions expectancy should sit near −cost; a positive one is
investigated as a defect before it is reported. XAUUSD rose across the corpus, so passive
same-direction exposure (`long_only`) is the binding control, not zero — the oracle scan's 65 → 8
collapse under exactly this control is the precedent.

### Stage D — The interaction test (the payoff)

Take the oracle scan's informative cells (`l2_states_*.csv`, `l3_conjunctions_*.csv`, already on
disk) and compute E_net for each under every exit configuration. Two shapes, pre-declared:

- **LEVEL** — exit shifts base and cells alike; `Δ(cell − base)` is flat across configs ⇒ exit does
  not unlock the information, and the binding constraint is information size.
- **INTERACTION** — `Δ(cell − base)` varies with exit ⇒ a joint entry×exit configuration exists.

Statistic: variance of `(cell − base)` across exit configs, against the same quantity under
block-permuted labels. This is what separates "exit is a flat level shift" from "exit and entry
information interact" — and it is the question the oracle determination actually left open.

### Stage E — Report

`docs/analysis/exit-geometry-decomposition-2026-08-2X.md`, point-in-time. Descriptive. No F-id
registered without explicit sign-off. Assert the holdout was never read.

---

## Files

**New** — `src/research/oracle/stop_policy.py` · `scripts/research/exit_geometry_scan.py` ·
`tests/research/test_stop_policy.py` · `tests/research/test_exit_ceilings.py`

**Modified** — `src/research/oracle/multi_tp_walk.py` (one additive `stop_policy` param, default
`None`) · `configs/formulas/market_ontology.yaml` (**SEM-019** `DYNAMIC_STOP_POLICY`, **SEM-020**
`EXIT_CAPTURE_DECOMPOSITION`, in the non-frozen `execution_behaviours` section; SEM-018 is currently
the highest id) · SITS registration for the new runnable.

**Never touched** — `src/config_layer/crt_engine_v2.py`, `src/runtime/backtest_v2.py`, `src/core/*`,
`configs/production/*`, `ACTIVE_VERSION`, `research/exit_grid.py`, `forward_walk.py`.

---

## Verification

| Check | Pass condition |
|---|---|
| **Parity** | `stop_policy=None` reproduces the existing 377,256 labels byte-identically |
| **Causality** | a policy reading the current bar's high/low to set that bar's stop **fails** an explicit test |
| **Monotonicity** | no policy ever moves a stop away from price |
| **Ratchet cross-check** | new `ratchet_r` agrees with `forward_walk(exit_model="trailing")` under a degenerate single-TP config |
| **Ceiling sanity** | `E[MFE_r] ≥ E[R_gross]` in every cell — a violation is a bug, not a finding |
| **Drift control** | every cell reported against `long_only`, never against zero alone |
| **Null** | block-permutation null on both the sweep and the Stage-D interaction statistic |
| **Holdout** | asserted unread on the artifact, not left to discipline |
| **Ontology** | SEM-019/020 mutation-tested (missing field / bad `knowledge_status` / duplicate id all caught) |
| **Freeze pin** | `test_xauusd_window_vector_regression` + `test_schema_pins_match` still pass — this program must be vector-inert |

Run:
```bash
python scripts/research/exit_geometry_scan.py --instrument XAUUSD --stage ceilings
```
then `--stage sweep`, then `--stage interaction`. Floor:
`pytest tests/research/test_stop_policy.py tests/research/test_exit_ceilings.py tests/research/test_multi_tp_walk_parity.py tests/research/test_oracle_labeler.py`

---

## Risks

1. **Intrabar ambiguity favours ratchets** — the single largest way this program could manufacture a
   false result. Contained by the close-only update rule, with the same-bar variant measured as a
   declared bound.
2. **Mining an exit grid on outcome-labelled data** — hundreds of cells over overlapping labels.
   Contained by block bootstrap + permutation null + the bug-signal rule for unconditional positives.
3. **Drift masquerading as exit skill** — a wide stop and a long horizon on a rising instrument is
   beta. `long_only` is the binding control throughout.
4. **Ceiling optimism** — the perfect-foresight bound is not attainable and must never be quoted as
   headroom. Three ceilings are reported precisely so the attainable one is separable.
5. **Horizon confound** — a longer horizon changes cost (more swap nights) and outcome mix
   simultaneously. Both carried per cell; gross and net always reported side by side.
6. **A LEVEL result is the likely outcome**, and it is a real answer, not a failure — it would close
   the exit axis and localise the constraint to information size.


================================================================================
SOURCE_FILE: docs/implementation_plan/d-tradelatest-docs-governance-finding-d-staged-widget.md
SOURCE_BYTES: 7082
PART: 3/10 FILE 10/16
================================================================================

# Plan — Continue Finding Dependency Audit (F-038 correction + Phase B Economic Truth Audit)

## Context

`docs/governance/finding_dependency_audit.md` completed **Phase A** (static reachability of all 12
R1 findings): 11 PASS, 1 FLAG. "Continue" means closing out Phase A's open item and executing the
audit's documented next stage, **Phase B — Economic Truth Audit** (B1/F-023, B2/F-019, B3/F-021).

While verifying Phase A's single actionable item I found it is **wrong**: the audit's F-038 FLAG
(line 94 / Phase-A summary) claims `v2_multi_2026_04.json:50` overrides `rr_fusion.enabled` to
`true` ("fix NOT deployed"). I read the active config directly:

- `configs/production/ACTIVE_VERSION` = `v2_multi_2026_04`
- Runtime resolves it via `production_config.py:116` → `f"{version}.json"` → `v2_multi_2026_04.json`
  (the `v2_multi_2026_04 - deepdeektry.json` sibling, name contains a space, is **never** loaded)
- `v2_multi_2026_04.json:34` → `"enabled": false` (rr_fusion). Line 50 is `"ultron_gate_enabled": false`.

So the F-038 fix **IS** deployed in the active config; the FLAG is a misread (DOC_DRIFT per §6.2
rule 2 — code wins, fix the doc). The deepdeektry sibling carrying `enabled: true` is a separate,
non-loaded artifact (latent TruthConflict, noted but out of scope here).

Goal of this change: (1) correct the audit doc so its only "actionable" item reflects reality, and
(2) run the three Phase-B economic replays to answer the audit's central question — *is Epoch-3
(post-stabilization) merely cleanup (E2 findings survive) or a new economic universe?* (F-019 is the
detector.)

---

## Part 1 — Correct the F-038 DOC_DRIFT (doc-only, this turn)

Edit `docs/governance/finding_dependency_audit.md` (per §6.2 rule 4: mark `CORRECTED`, never
silent-delete):

1. **F-038 row (≈line 91-94)** — change `⚠ FLAG` → `✅ PASS (CORRECTED 2026-06-27)`. Replace the
   "Fix NOT deployed" detail with: active config `v2_multi_2026_04.json:34` has
   `rr_fusion.enabled: false` (verified via `ACTIVE_VERSION` → `production_config.py:116` filename
   resolution). The earlier claim cited line 50 (`ultron_gate_enabled`) and/or the non-loaded
   `… - deepdeektry.json` sibling. Note the sibling divergence as a latent TruthConflict.
2. **Phase A Summary table (≈line 121)** + **R1 table (≈line 163)** — F-038 `⚠ FLAG` → `✅ PASS`.
3. **"One actionable finding from Phase A" (≈line 125-127)** — replace: Phase A is now **12/12 PASS**;
   the F-038 fix is already deployed; no config flip required. Optionally add a one-line follow-up to
   reconcile/retire the `… - deepdeektry.json` sibling.
4. **Audit Log (≈line 226)** — change `11/12 PASS; 1 FLAG (F-038)` → `12/12 PASS (F-038 FLAG
   corrected — fix already deployed)`.

No code/config change. F-038 in `current-findings.md` already states "FIX SHIPPED" — consistent, no
finding edit needed. Add a SESSION LOG entry (§6) recording the E-001 correction (mandatory phrase:
"Caught me overclaiming; I owe you a correction" — applied to the prior audit's misread).

---

## Part 2 — Phase B Economic Truth Audit (execution; scope per user answer)

All three are **read-only re-measurements** that write to *new* output paths (existing baselines are
never overwritten). Each carries a pre-registered success criterion (= finding survives) and failure
mode (= Epoch-3 is a new economic universe). Run `ORIENT_RUNTIME` first (confirm `ACTIVE_VERSION`).

### B2 / F-019 — Epoch-3 detector (headline; run first)
```
python scripts/research/qualify_majors.py --out results/research/qualification_2026_06_27
```
- Driver `scripts/research/qualify_majors.py`; M4 gate `src/research/qualification.py`; cost
  `src/research/costs.py` (12 bps). Data: `data/{BNB,ETH,BTC,SOL}USDT_M15.csv` (all present, 70,080
  rows). Deterministic body; ~10 min.
- **Success:** still 0 PROMOTE; toy arm byte-identical to frozen baseline
  `results/research/qualification/qualify_majors.json` (no toy code changed). **Failure:** any
  hypothesis clears M4 → E3 = new economic universe.
- Note: backtests run CRT-only (`BACKTEST_ENGINE_GATE=0`, F-037), so the F-038 rr_fusion change is
  expected **not** to move the spine arm — a useful cross-check. Compare new vs frozen `qualify_majors.json`.

### B1 / F-023 — re-cluster on governing intrabar_fixed labels (P0 mandatory)
```
python scripts/analysis/bnbusdt_trade_anatomy.py --instrument BNBUSDT \
  --opportunities logs/BNBUSDT/20260530_011521/opportunities.jsonl \
  --candles data/BNBUSDT_M15.csv --out-dir results/research/bnbusdt_trade_anatomy_2026_06_27
```
- Driver already labels via `forward_walk(exit_model="intrabar_fixed")`
  (`src/research/measurement/forward_walk.py`) — does **not** trust the F-022-unreliable
  `opportunities.jsonl` outcome/rr fields. KMeans k=4 on 9 standardized morphology features.
- Output ~122 MB CSV + `anatomy_summary.json` (`morphology_clusters`). **Success:** all 4 clusters
  WR ≈ 0.34±0.01, mean_R ≈ 0.000±0.023. **Failure:** any cluster WR >0.40 or <0.28 → new universe.

### B3 / F-021 — reject-reason decomposition (SESSION/ZONE/SCORE)
```
python scripts/research/phase_s_selection_effect.py \
  --config configs/research/research_config_phase_s.json --out results/research/phase_s_2026_06_27
```
- Driver `scripts/research/phase_s_selection_effect.py`; runs spine backtests inline +
  `forward_walk(intrabar_fixed)` + 12 bps; folds reasons via `src/research/selection_effect.py`.
- **Success:** SESSION dominates (≥95%), ZONE 0 rejects, SCORE <5 (F-021 holds:
  SELECTION_IS_SESSION_ONLY). **Failure:** SCORE/ZONE materially binding → selection skill may exist.

### Post-run governance (every replay)
- **If all survive:** record E3 = stabilized E2; mark Phase B rows DONE in the audit's Audit Log +
  the R2 table; in `current-findings.md` set `Validated: 2026-06-27` / refresh `Revalidate-by` for
  F-019/F-021/F-023 (Findings Mandate, §6.2). No reversal.
- **If any breaks:** run the E-001 6-question pre-registration ritual *before* registering; surface
  as a finding flip with `Reversal:` + evidence (file:line / artifact); this is a major epoch event —
  pause and report to user before propagating.
- SESSION LOG entry each turn (§6). No new findings invented; replays only confirm/flip existing F-ids.

---

## Verification

- **Part 1:** `pytest tests/test_doc_citations.py tests/test_current_findings.py` (citation +
  findings-index consistency). Visual diff of the audit doc.
- **Part 2:** byte-compare new `qualify_majors.json` toy arm vs frozen baseline (determinism gate);
  confirm each replay's success criterion; outputs land in dated dirs (baselines untouched).
- Spot-check `results/research/*_2026_06_27/` artifacts exist and parse.

## Out of scope (flag, don't fix here)
- Reconciling/retiring `configs/production/v2_multi_2026_04 - deepdeektry.json` (latent TruthConflict
  — divergent `rr_fusion.enabled`, not loaded). Worth a separate cleanup.
- Phase C / R3 ontology replays (F-040, Programs 4/5/6) — only on new ontology/market.


================================================================================
SOURCE_FILE: docs/implementation_plan/d-tradelatest-docs-governance-tradenet-parsed-shannon.md
SOURCE_BYTES: 4703
PART: 3/10 FILE 11/16
================================================================================

# Plan — Phase 1: align authoritative facts (RR 35→38) + defer federation

## Context

Scope reduced on the governing principle: **don't optimize governance faster than you can validate
models.** The federation refactor is governance optimization; the bottleneck is trustworthy models.
So: execute Phase 1 now, record the federation as a deferred proposal, and leave Phases 2–3 for
later decisions.

## What Phase 1 changes

**One verifiable misalignment exists.** The dim cross-check across all families found exactly one
registry-vs-artifact contradiction:

| Family | YAML | Registry | Artifact | Action |
|---|---|---|---|---|
| gaussian ETH / BNB | 35 / 38 | 35 / 38 | 35 / 38 | consistent — no change |
| zone_gate | 38 | *(no dim field)* | 38 | consistent — no change |
| **rr_model** | **35** | **35** | **38** | **fix registry, mirror follows** |
| tradenet | 35 | *(no dim field)* | binary `.pth` | **unverifiable — leave untouched** |
| bitnet | n/a | `{}` | — | n/a |

Four independent confirmations that 38 is correct: the artifact (`n_features: 38`,
`feature_schema: "canonical_38"`, `scale_mu`/`ridge_w` both length 38, `zero_indices` 11 → rank 27);
the trainer constant `rr_pattern_miner.py:22` `N_FEATURES = CANONICAL_FEATURE_DIM` = **38**; the
pipeline; and sibling entry `202605_v1`, which already declares 38.

### Edits

1. **`models/rr_registry.json`** — active entry `202605_bnb_v2_bnbusdt`: `n_features: 35 → 38`.
   No hash field on entries ⇒ no rehash. **Artifact untouched.**
2. **`active_models.yaml`** — mirror follows *because the registry changed*:
   `rr_model.identity.selection.feature_schema_dim` and
   `runtime_binding.compatibility.feature_schema_dim`, both `35 → 38`.
3. **`docs/governance/build_manifests/CH-rr-registry-dim-38.impact.json`** (+ `.completion.json`)
   — matching the existing manifest shape (`change_id`, `objective`, `change_classes`,
   `affected_files`). Class: `MODEL_ARTIFACT_CHANGE`, which claims `"models/ registry manifests"`
   as its surface; guard `tests/test_active_models_registry.py`.
4. **`docs/governance/model_lineage_rollup.md`** — §4.3a marked RESOLVED (finding text preserved,
   resolution appended per §6.2 rule 4); §10.7 candidate (c) marked DONE.

### Deliberately left alone

- Six other RR entries also declare 35; four are dangling and unverifiable against any artifact.
  Changing unverifiable metadata would be inventing data.
- The same entry's `n_samples: 0` vs `metrics.n_train: 49000` — `0` is certainly wrong, but the
  true total is unknown and will not be guessed. Recorded as an open item.
- TradeNet's declared 35 — binary `.pth`, no registry dim field, unverifiable without torch.

### Behavioural impact: none on the decision path

The only runtime reader is `src/control_plane/dashboard_api.py:492` (`entry.get("n_features", 35)`)
— a *display* consumer. `rr_fusion.enabled=false`, so no inference path reads it either way. The
edit corrects what the dashboard shows.

## Federation — recorded as deferred, not built

A short block appended to `model_lineage_rollup.md` §10.7 (the existing home for recorded,
unauthorized candidates — no new file, §6.2 rule 5):

```text
MRF_V1 — Model Registry Federation
Status:  Proposed
State:   Not Implemented
Reason:  Deferred until research stabilization
```

With three lines of why it was deferred and the load-bearing constraint discovered while scoping it
(`active_models.yaml` is a runtime input — `state_contract_loader.py:38` hardcodes the root path,
parses `state_contracts`, and enumerates top-level keys as the model-ID set; 27 coupled files,
22 registry tests), so a future decision starts from evidence rather than re-deriving it.

## Files

| File | Change |
|---|---|
| `models/rr_registry.json` | active entry `n_features: 35 → 38` |
| `active_models.yaml` | mirror: two `feature_schema_dim` 35 → 38 |
| `docs/governance/build_manifests/CH-rr-registry-dim-38.*.json` | NEW manifest pair |
| `docs/governance/model_lineage_rollup.md` | §4.3a RESOLVED · §10.7 (c) DONE · MRF_V1 deferred note |
| `assistant_project.md` | §6 SESSION LOG |

Not touched: any model artifact, loader, config, or runtime wiring. No new YAML authorities.

## Verification

```
venv/Scripts/python.exe -m pytest tests/test_active_models_registry.py tests/test_state_contracts.py tests/test_doc_citations.py tests/test_session_log.py -q
```

Explicit checks: registry `n_features` == artifact `n_features` (38); artifact sha256 **unchanged**
at `6ed92d26…` (proves metadata-only); `active_models.yaml` mirrors the updated registry (R1 green);
`test_state_contracts.py` green (the index's runtime contract untouched).


================================================================================
SOURCE_FILE: docs/implementation_plan/d-tradelatest-docs-implementation-plan-ethereal-crystal.md
SOURCE_BYTES: 9275
PART: 3/10 FILE 12/16
================================================================================

# Plan: Multi-LLM Coordination Layer (Track 3) → driving the Domain-First Refactor (Track 1)

## Context

You run four LLMs by hand — DeepSeek (planner), Gemini (navigator), ChatGPT (interpreter), Claude
(executor) — and the real, felt pain is **context drift**: each model accumulates private
assumptions until you have "4 independent realities" and contradictory architectures. The ChatGPT
"Project OS" thread proposes a large fix (context compiler, portable mind, role files, handoff
protocol, documentation compiler, cognitive domains, session manager).

**Decision (yours):** build the multi-LLM layer **first** (Track 3), then execute the
`FULL_BUILD_SPECIFICATION.md` domain-first refactor (Track 1) **driven through** that multi-LLM
workflow.

**Key finding that shapes this plan:** an Explore pass confirmed ~90% of the proposed "Project OS"
**already exists** in this repo under other names. So this plan builds **only the genuinely-absent
~10%** and wires it to the abundant existing substrate — it does **not** rebuild what's there.
This respects CLAUDE.md §6.2 (existing-doc-first, minimize doc count, zero silent truth divergence)
and §6.1's "no premature framework" guardrail.

### Already exists — DO NOT rebuild (derive from / point to these)
| Capability | Existing source of truth |
|---|---|
| Canonical memory / context | `CLAUDE.md`, `MEMORY.md`, `assistant_project.md`, `docs/knowledge-map.md` |
| Findings registry | `docs/current-findings.md` + CLAUDE.md Repository Truths Index (`tests/test_current_findings.py`) |
| Impact-driven doc compiler | `gen_citation_map.py`, `gen_code_map.py` + `tests/test_doc_citations.py`, `tests/test_topic_docs.py` |
| Session manager | `assistant_project.md` SESSION LOG + `tests/test_session_log.py` + rotation + commit-hook |
| Cognitive domains | `docs/intent/` (7), `docs/topics/` (26), `docs/architecture/` (22) |
| Dependency/intent map | `docs/architecture/code-map.generated.md`, `docs/intent/*`, `module-roles.generated.md` |
| Active runtime truth | `configs/production/ACTIVE_VERSION` + §4.0 precedence |

### Genuinely absent — what we build
1. **Role files** (frozen, hand-authored): what each model owns.
2. **Handoff protocol** (one doc): the mandatory response structure + authority hierarchy.
3. **Context compiler** (one script): regenerates a small set of *portable context files* **from**
   the canonical sources above — the "Portable Mind" you upload to any model.
4. **Live handoff state + build queue**: `HANDOFF.md` (current actor / next actor) and a
   machine-readable story queue seeded from `FULL_BUILD_SPECIFICATION.md` — the bridge to Track 1.

---

## Track 3 (build now)

### Phase A1 — Static authored docs (no code)
Create `multi_llm/` at repo root (discoverable; these are meant to be grabbed and uploaded):

- `multi_llm/MULTI_LLM_PROTOCOL.md` — the mandate. Mandatory response block for **every** model
  (`CURRENT_TASK`, `NEXT_10_STEPS`, `CONTEXT_DELTA`, `FOR_NEXT_MODEL`, `PROMPT_FOR_NEXT_MODEL`,
  `CONFIRMATION`); the flow `DeepSeek→Gemini→ChatGPT→Claude→Tests/Findings→Gemini`; the **Authority
  Hierarchy** (`Reality > Tests > Findings > Repository > Shared Context > LLMs`) — tied to CLAUDE.md
  §6.5 Authority Ladder so it doesn't become a competing doctrine.
- `multi_llm/roles/ROLE_DEEPSEEK.md`, `ROLE_GEMINI.md`, `ROLE_CHATGPT.md`, `ROLE_CLAUDE.md` — frozen
  responsibilities (Planner / Navigator / Interpreter+ParameterExpansion / Executor). `ROLE_CLAUDE.md`
  must restate the non-negotiables it already lives under: §6 SESSION LOG, write-authority/path-guard,
  promotion gate, no silent config defaults (§6.5).
- `multi_llm/README.md` — index + "how to run a cycle" + explicit "these files are the *protocol*;
  the *truth* lives in the repo" statement.

### Phase A2 — Context compiler (code, mirrors `gen_citation_map.py`)
- `scripts/context/build_context.py` — **stdlib-only, deterministic, `--check` mode**, every output
  stamped `GENERATED — do not edit · regenerate with python scripts/context/build_context.py`. It
  reads canonical sources and writes portable files to `context/`:
  - `context/01_GLOBAL_CONTEXT.md` ← CLAUDE.md §1/§4/§6.x doctrines + `docs/architecture/goal.md`
  - `context/02_CURRENT_STATE.md` ← `configs/production/ACTIVE_VERSION` + current branch + latest N
    SESSION LOG entries + `NEXT_10_STEPS` (from the build queue, A3)
  - `context/03_FINDINGS.md` ← `docs/current-findings.md` non-terminal findings + Repository Truths Index
  - `context/04_DEPENDENCY_AND_INTENT.md` ← `code-map.generated.md` summary + `docs/intent/*` titles
  - `context/05_HANDOFF.md` ← role-file summaries + protocol summary + current `HANDOFF.md` state
- `tests/test_context_compiler.py` — mirrors `tests/test_doc_citations.py`: (a) compiler runs and all
  source paths resolve, (b) outputs non-empty, (c) **determinism** (run twice → byte-identical), (d)
  **no hand-edit drift** (regenerate and diff against committed `context/*.md`, like the citation-map
  freshness check), (e) header stamp present on every generated file.

### Phase A3 — Live handoff state + build queue (the bridge to Track 1)
- `HANDOFF.md` (repo root) — small hand/compiler-merged state: `current_actor`, `current_story`,
  `completed`, `blocked`, `next_actor`, `next_prompt`. This is the working-memory file passed between models.
- `data/build_queue.jsonl` — append-only story queue **seeded from `FULL_BUILD_SPECIFICATION.md`**
  (one line per story: `id`, `epic`, `title`, `status`, `confidence`, `files`, `depends_on`). Matches
  the repo's JSONL convention. Feeds `NEXT_10_STEPS` in `context/02_CURRENT_STATE.md`.
  - `scripts/context/seed_build_queue.py` — one-time parser of the spec's epic/story tables → JSONL.

### Phase A4 — Minimal CLAUDE.md wiring (one entry, not a new doctrine)
- Add a single short section (e.g. CLAUDE.md §13 "Multi-LLM Layer") + a `Compile` trigger to §12
  Trigger Vocabulary pointing at `multi_llm/` and `scripts/context/build_context.py`. Keep it thin —
  the detail lives in `multi_llm/`, per minimize-doc-count.

---

## Track 1 (after Track 3, executed *through* the multi-LLM workflow)

Once A1–A4 exist, the operating loop becomes: compile `context/*.md` → hand to DeepSeek/Gemini/ChatGPT
for the next story's plan/gaps/explanation → **Claude executes** the story → tests+findings decide →
regenerate context → advance the queue. The first stories to run are `FULL_BUILD_SPECIFICATION.md`
**Epic 1 (repair the spine — fix the 23 failing tests)**, because nothing downstream is trustworthy
on a broken foundation (F-010/trust-layer discipline). **Not planned in detail here** — each epic
gets planned as it surfaces in the queue. The F-001 / Program-1 tension (don't over-invest in
tooling vs. the real binding constraint) is carried as an explicit gate before Epics 4–10.

---

## File inventory
```
NEW  multi_llm/MULTI_LLM_PROTOCOL.md
NEW  multi_llm/README.md
NEW  multi_llm/roles/ROLE_DEEPSEEK.md
NEW  multi_llm/roles/ROLE_GEMINI.md
NEW  multi_llm/roles/ROLE_CHATGPT.md
NEW  multi_llm/roles/ROLE_CLAUDE.md
NEW  scripts/context/build_context.py        (mirrors scripts/analysis/gen_citation_map.py)
NEW  scripts/context/seed_build_queue.py
NEW  tests/test_context_compiler.py          (mirrors tests/test_doc_citations.py)
NEW  HANDOFF.md
NEW  data/build_queue.jsonl                   (generated by seed_build_queue.py)
NEW  context/01_GLOBAL_CONTEXT.md ... 05_HANDOFF.md   (generated by build_context.py)
MOD  CLAUDE.md                                (+§13 + one Compile trigger; thin)
```

## Conventions to follow (reuse, don't invent)
- Context compiler = stdlib-only + deterministic + `--check` + GENERATED header — copy
  `scripts/analysis/gen_citation_map.py` structure exactly.
- Generated-file freshness test = copy `tests/test_doc_citations.py` regenerate-and-diff approach.
- JSONL append-only for `build_queue.jsonl` — same discipline as `promotion_log.jsonl`.
- Windows console output through `src/utils/console_safe.py` if the scripts print non-ASCII.
- Append the §6 SESSION LOG entry on every implementation turn (the layer must obey, not bypass, it).

## Verification
1. `python scripts/context/seed_build_queue.py` → inspect `data/build_queue.jsonl` (44 stories present).
2. `python scripts/context/build_context.py` then `--check` again → byte-identical (determinism).
3. `pytest tests/test_context_compiler.py -v` → all green (resolve, non-empty, determinism, no-drift, header).
4. `pytest` full suite → no new reds introduced (purely additive layer).
5. Manual: open `context/*.md` — confirm each is a faithful *derived view* of its source, not a fork,
   and small enough to paste into an external model.

## Out of scope / deferred
- The 44-story refactor itself (Track 1) — planned per-epic as the queue advances; Epic 1 first.
- ChatGPT's "impact-driven documentation compiler" and "cognitive-domain context bundles" — already
  covered by existing citation/topic/code-map machinery; not rebuilt.
- Any n8n / Claude-API gate (Epics 6–7 of the spec) — far downstream, behind the F-001 gate.
- Automating LLM-to-LLM calls — the human stays the bridge for now (matches the proposal).


================================================================================
SOURCE_FILE: docs/implementation_plan/d-tradelatest-reports-monthly-tv-vs-act-iterative-bengio.md
SOURCE_BYTES: 13680
PART: 3/10 FILE 13/16
================================================================================

# Close-M15 Semantic Equivalence Gate (vs TradingView), before any HTF predictive/qualification role

## Context

`reports/monthly_tv_vs_active_production_semantic_comparison.md` row 1 records **MATCH (1,430/1,455 = 98.3%)** for candle/OHLC identity. That verdict is an **L1 sum over all four O/H/L/C fields against a single scalar `MATCH_TOLERANCE = 3.0`** (`tools/tv_forensic/engine_data.py:24, :317-322`). It therefore says nothing directly about the one field every CRT and HTF semantic decision actually reads: the **close**.

The exposure is structural, not hypothetical:

- `src/features/parent_candle.py:56` — the H4 parent's `close = children[-1].close`. **The H4 close IS an M15 close.** Any M15 close divergence propagates into the parent undamped.
- Every HTF decision is a strict close inequality:
  - `src/config_layer/parent_crt.py:154-155` — sweep: `close < h_ref` / `close > l_ref`
  - `src/config_layer/parent_crt.py:169-171` — F-074 impulse: `close > open AND close > sweep.price` (and the SHORT mirror)
  - `src/config_layer/htf_state.py:97-100` — classify: `curr.close > prev.high`, `curr.close < prev.low`, `prev.close > prev.open`
  - `src/config_layer/htf_state.py:126-137` — objective: `last_close >= target` / `< invalidate_at`
  - `src/config_layer/crt_engine_v2.py:3020-3021` — parent-bias veto: `candle.close` vs `_htf_mid`
- The M15 engine's own funnel is close-gated at the same points (`crt_engine_v2.py:892-893, 1141, 1167, 1196, 1222, 1491, 1512`).

So the aggregate MATCH is not the evidence needed. Before HTF is assigned any predictive or qualification role, the close field must be isolated and its measured divergence propagated through the decisions that read it.

**Read-only reconnaissance already run (this is the starting point, not the deliverable):**

| Measurement (from existing sidecars, n=1,260 M15 compared bars) | Value |
|---|---|
| M15 bars with non-zero close delta | **98.17%** (1,237/1,260) |
| Close delta: mean / median | **+0.0499 / +0.0450** (TV above engine) |
| Close abs delta: p50 / p95 / p99 / max | 0.07 / **0.22** / 0.32 / **0.99** |
| Same-bias check across fields (mean Δ) | O +0.0437, H +0.0498, L +0.0497, C +0.0499 → **feed-level quote offset, not close-specific** |
| Close dispersion vs other fields (max abs) | C **0.99** vs O 8.38 / H 9.73 / L 6.37 → **close is the best-behaved field** |
| Bar-boundary equivalence (own-slot TV close strictly closest) | **96.39%** (1,201/1,246); all 45 exceptions have own-slot \|ΔC\| ≤ 0.34 (noise scale, not a 15-min misalignment) |
| **M15-resolution coverage** | **15 of 23 corpus trading days**, 1,260/2,116 bars (59.5%). Blind: Jul 16, 17, 21, 22, 23, 24, 27, 31 |
| Bars where TV close falls outside engine `[low, high]` | **20/1,260 (1.59%)** — matters for the substitution policy below |

Two things follow. (1) The close is *systematically offset and never exact*, so "MATCH" must not be read as "equivalent." (2) The report's "**23 of 23** trading days with TradingView capture" is true for *any* capture but is **15 of 23 at M15 resolution** — a distinction row 1's M15 claims do not currently carry.

**Intended outcome:** a pre-registered, verdict-bearing artifact that either licenses or blocks HTF on the close-equivalence axis, with the criterion fixed before any measurement runs.

## Decisions already taken (user, this session)

1. **Coverage** — use the existing 15/23 M15 days and declare the gap. No new TradingView capture; no network/Playwright.
2. **Gate form** — pre-registered gate + verdict artifact. No new Closure & Authority Index row.
3. **Pass bar** — PASS iff close-only substitution flips **no** parent-CRT state/bias/objective and **no** M15 funnel transition on **non-daily-open** bars. F-080's daily-open bars are reported separately as a *bar-definition* divergence, not a close divergence. Knife-edge count is reported but not blocking.

## Scope guards (non-negotiable)

- Descriptive only. No `configs/production/` write, no `ACTIVE_VERSION` change (stays `v2_htfcrt_2026_08`), no promotion, no model retrain, no `objective_gate` flip, no CRT re-closure. Grants no authority (§6.5) — a PASS clears **one precondition**, it does not confer predictive value on HTF.
- No `src/` edit. All engine/parent-CRT decisions are exercised through their real code paths; the census records **distances to boundaries the feed already exposes**, never a second copy of a predicate (§3.3b: no local formula math, no duplicate geometry).
- Tolerances are **inherited**, not invented: `engine_data.MATCH_TOLERANCE`/`DECISIVE_RATIO` and the measured close envelope (p95 = 0.22, max = 0.99) are the perturbation budgets. Not widened after seeing results.

## Work

### Step 0 — Pre-registration (must land before any arm runs)

Write `docs/governance/build_manifests/CH-close-m15-equivalence-gate.impact.json`, following the `CH-monthly-tv-coverage-h4-recon.impact.json` precedent (same directory, same shape). It declares:

- every path the change touches (two new scripts, one report + machine twin, SITS registry artifacts);
- the change class per `docs/governance/change_contracts.json`;
- **the gate criterion verbatim** (decision 3 above), plus the three verdict tokens the report may emit: `CLOSE_EQUIVALENT_FOR_HTF` · `CLOSE_EQUIVALENT_EXCEPT_DAILY_OPEN` · `CLOSE_NOT_EQUIVALENT`;
- **the substitution policy, fixed up front**: when the TV close falls outside the engine bar's `[low, high]` (measured: 20/1,260 = 1.59%), expand that bar's high/low minimally to admit it (primary cell) — and report the clamp-to-range variant as a robustness cell. Both are declared now so neither can be selected after seeing which one is cleaner;
- **the new-finding precondition**: register an F-id only if a decision flip is found on non-daily-open bars, or if the daily-open flip count materially extends F-080. A clean result registers nothing.

### Step 1 — Arm A: close-field isolation (`scripts/research/close_m15_equivalence.py`, part 1)

Read-only over `tools/tv_forensic/shots/*.json` (excluding `*_ANNOTATED` and `*_PRE_*`, exactly as `htf_parent_telemetry_extract.py:130-133` already filters). Emit, per shot and pooled:

- per-field Δ decomposition (mean/median/mean-abs/p95/max) so the shared +0.05 bias is separated from close-specific dispersion;
- the close abs-Δ distribution and the exceedance table at 0.05/0.1/0.25/0.5/1.0;
- the **bar-boundary test**: engine close vs TV close at t, t−15m, t+15m; report own-slot-closest rate and, for every exception, the own-slot error magnitude (the discriminator between noise and misalignment);
- **honest coverage**: M15-covered days (15) vs corpus days (23), named blind days, bars covered vs corpus bars.

### Step 2 — Arm B: knife-edge margin census, month-complete (`scripts/research/close_margin_census.py`)

Needs no TradingView bars, so it covers all 2,116 bars — this is the arm that is *not* coverage-limited.

- **M15 side**: replay `CRTEngine` with guard hooks exactly as `scripts/analysis/crt_predicate_failure_census_6m.py:88-92` does (`CRTBaselineTraceHooks()`, `hooks.enabled = True`, `engine.baseline_trace = hooks`). Guard records carry `operands[].runtime_value` for both PASS and FAIL results, so every close-driven guard's margin is harvestable without touching `src/`. Filter to guards whose operands include `feature_id == "close"`.
- **HTF side**: drive `ParentCRTFeed.from_prod_config()` per `htf_parent_telemetry_extract.py:84-121` (including the `bt.guard_xauusd_csv_path` identity patch and the `feed._builder.parent_candle` read-back) and, at each H4 close, record the distance from the parent close to the boundaries the feed already exposes — `feed.track.range.h_ref` / `.l_ref`, `feed.track.sweep.price`, the previous parent's high/low, the objective `target` / `invalidate_at`, and `_htf_mid`.
- Output: for each decision family, the margin distribution and the count of evaluations whose margin sits inside **0.22** (p95) and inside **0.99** (max) — the knife-edge census. Reported, not blocking.

### Step 3 — Arm C: three-cell substitution replay (`scripts/research/close_m15_equivalence.py`, part 2)

Cell-based A/B in the established repo style (`htf_objective_gate_shadow.py`, `bitnet_shadow_diagnostic` lineage). Restricted to the 15 M15-covered days; parents with incomplete TV child coverage are marked `NOT_TESTABLE`, never silently included.

| Cell | Stream fed to the engine + feed | Question |
|---|---|---|
| **A0** | engine bars, unmodified | **Parity gate.** Must reproduce `results/monthly_tv_semantic_report/htf_parent_telemetry.jsonl` exactly and the published funnel (84/19/6/2/0). Abort on any mismatch — reuse the `EXPECTED_DISTRIBUTION_C3_CLOSES = 15` non-vacuity check (`htf_parent_telemetry_extract.py:76`). |
| **A1** | engine O/H/L, **TV close only** | **The user's question.** Isolates the close field's contribution. |
| **A2** | full TV O/H/L/C | Context / upper bound — how much of any flip is close vs the other three fields. |

Diff A1 and A2 against A0 on: `track_state` / `bias` / `htf_state` / `objective_status` per H4 close, and the M15 funnel transition sequence. Classify every flip as daily-open (F-080 bar-definition) or ordinary-bar, and **never pool the two**.

### Step 4 — Verdict artifact

`reports/close_m15_semantic_equivalence.md` + `reports/close_m15_semantic_equivalence.json` (machine twin, mirroring the existing monthly report's md/json pairing). Contents: the pre-registration restated, all three arms, the verdict token, the coverage statement, and an explicit §6.8 closing tag. Add a cross-link from `reports/monthly_tv_vs_active_production_semantic_comparison.md` row 1 noting that its MATCH is a 4-field L1 aggregate and pointing at this report for the close-only decomposition and the 15-of-23 M15 figure (§6.2 rule 6 synchronize; the existing text is not deleted).

### Step 5 — Registration + close-out

- **SITS** (both new scripts, same turn — `docs/reference/conventions.md:122-126`):
  ```bash
  python scripts/analysis/script_census.py --write-stubs docs/governance/script_registry_stubs.jsonl
  ```
  then add the required Python overlays in `scripts/governance/seed_script_registry.py` (a stub alone leaves `purpose = GRANDFATHER_UNCLASSIFIED` and fails the coverage floor), then `seed_script_registry.py`, then `generate_script_matrix.py`.
- `python scripts/governance/construction_protocol.py validate-completion docs/governance/build_manifests/CH-close-m15-equivalence-gate.impact.json`
- Finding in `docs/current-findings.md` **only if** the Step-0 precondition fires; §6.7 ground any new noun before asserting it.
- `📝 SESSION LOG ENTRY` appended to `assistant_project.md` (§6 — codebase log; this is governed-code-adjacent research, not workflow).

## Critical files

**Read (authorities, do not modify):** `src/features/parent_candle.py` · `src/config_layer/parent_crt.py` · `src/config_layer/htf_state.py` · `src/config_layer/crt_engine_v2.py` · `tools/tv_forensic/engine_data.py`

**Reuse (harnesses, copy the pattern):** `scripts/research/htf_parent_telemetry_extract.py` (ParentCRTFeed replay + sidecar filtering + non-vacuity gate) · `scripts/analysis/crt_predicate_failure_census_6m.py` (guard-hook attach + operand harvest) · `scripts/research/htf_objective_gate_shadow.py` (multi-cell comparison structure) · `src/runtime/crt_baseline_trace.py` (`CRTBaselineTraceHooks`)

**Create:** `scripts/research/close_m15_equivalence.py` · `scripts/research/close_margin_census.py` · `reports/close_m15_semantic_equivalence.{md,json}` · `docs/governance/build_manifests/CH-close-m15-equivalence-gate.impact.json`

**Edit (surgical):** `scripts/governance/seed_script_registry.py` (2 overlays) · `docs/governance/script_registry_stubs.jsonl` (generated) · `reports/monthly_tv_vs_active_production_semantic_comparison.md` (row-1 cross-link) · `docs/current-findings.md` (conditional) · `assistant_project.md`

## Verification

1. **Parity gates are the acceptance criteria, not the report prose.** A0 must reproduce `htf_parent_telemetry.jsonl` byte-for-byte on `track_state`/`bias`/`htf_state`/`objective_status` and hit `DISTRIBUTION_C3 == 15`; the guard-hook replay must reproduce the published M15 funnel (84/19/6/2/0). Either failing = harness bug, abort, do not report downstream numbers.
2. **Non-vacuity**: the substitution must actually bite — assert ≥1 substituted bar differs from engine on every covered day, so a silently-identical stream cannot masquerade as a PASS (the D-1/F-079 failure class).
3. **Read-only proof**: `git status` shows no change under `configs/`, `src/`, `models/`, `data/`; `configs/production/ACTIVE_VERSION` still reads `v2_htfcrt_2026_08`.
4. **Regression floors**: `python -m pytest tests/test_tv_forensic_smoke.py tests/test_script_registry.py tests/test_script_matrix_sync.py tests/test_current_findings.py tests/test_session_log.py -q` (add `tests/test_closure_authority_index.py` — the index must be *unchanged*, per decision 2).
5. **Both substitution policies reported** (expand + clamp), so the 1.59% incoherent-bar handling is visible rather than chosen.

## What this deliberately does not do

- Does not take new TradingView captures; the 8 blind M15 days stay blind and are named in the report.
- Does not adjudicate F-077's Romeo/Sujan non-equivalence, and does not touch F-080's daily-open characterization beyond citing it.
- A PASS clears the close-equivalence precondition **only**. Assigning HTF a predictive or qualification role remains a separate, separately-authorized program requiring measured ΔG001 (§6.5 Authority Ladder).


================================================================================
SOURCE_FILE: docs/implementation_plan/d-tradelatest-reports-ohlcv-lineage-for-glistening-wilkinson.md
SOURCE_BYTES: 13270
PART: 3/10 FILE 14/16
================================================================================

# Model-Intent Forensics → Evidence-Driven, Gated Feature Expansion

## Context

Two forensic reports (`reports/OHLCV_LINEAGE_FORENSICS.md`, `reports/FEATURE_REACHABILITY_AUDIT.md`)
plus an external LLM critique asked: are the ~20 "ACTIVE_VIA_MODEL" canonical features dead weight, and
should every model consume all 38 features and be retrained? Directive: **no feature deletion; no forced
100% utilization; achieve 100% *understanding* of feature ownership and model intent first, then perform
evidence-driven expansion and retraining — measure-first, gate everything.**

### Reframed objective (binding)

Replace "make all 38 features 100% used" with three distinct targets:

```
100% feature UNDERSTANDING   — every feature's market meaning + current owner is known
100% justified OWNERSHIP     — every model's feature set is explained by intent (A) or evidence (B)
100% measurable CONTRIBUTION — every claim of value is backed by decision-flip / ΔG001 measurement
```

Keep two questions **separate** throughout — they are different problems:

- **Question A — intended information ownership:** what each model was *designed* to consume, and *why
  it deliberately ignores* the rest (different time horizon · independent vote · diversification against
  correlated failure · structural filter vs predictor). Specialization is often an advantage.
- **Question B — marginal information value:** which currently-ignored feature *measurably* improves
  predictive or decision quality, net of cost and **net of ensemble-correlation cost**.

A feature can be correctly owned (A) yet still not worth adding elsewhere (B), and vice-versa.

### Why this matters / intended outcome

Investigation (3 Explore agents + direct reads) suggests the binding ZoneGate defect is **label/exit
quality, not feature count** — but those claims are **hypotheses to independently verify (Phase 5), not
axioms**. The intended outcome is: a canonical **Model-Intent & Feature-Ownership Matrix** (the authority
all later work defers to), an empirical importance + decision-flip measurement, independent verification
of the ZoneGate/label/registry claims, and only then scoped, gated, advisory-first expansion/retraining
measured against G001/M4. Per CLAUDE.md §6.5, nothing earns production weight without demonstrated ΔG001.

## Doctrine guardrails (binding on every phase)

- **No deletions.** Features and config values are preserved; reclassification is documentation only.
- **Findings are not axioms.** The ZoneGate broken-label, registry split-brain, and model-internal claims
  below are flagged `[TO VERIFY]` and must be independently confirmed (Phase 5 / Phase 1 split-brain
  check) before they drive any architectural decision. Surface disagreements as §6.2 `TruthConflict`,
  never silently "fix".
- **Authority Ladder (§6.5):** information ≠ value ≠ authority ≠ architecture. Phases 1–4 earn
  research/docs authority only. Expansion/retrain (6) is advisory-first; **no production promotion**
  unless it clears ΔG001 under governed gates (Phase 8, separate).
- **Specialization is a feature, not a bug.** Forcing all models onto the same 38-vector risks
  `identical latent reps → correlated errors → weaker ensemble`. Expansion must be shown not to increase
  inter-model score correlation / correlated failure — this is a measured gate, not a preference.
- **Falsification backdrop:** F-019…F-040 falsified the *entry-information* edge across all axes tested;
  standing conclusion "binding constraint = EXECUTION MODEL, not predictability." The untested,
  high-ROI angle here is **label quality**, never isolated by that program — frame to reach a clean
  conclusion, not to manufacture an edge.
- **Research isolation:** all measurement/retrain runs in `src/research/` + `scripts/research/` via
  `forward_walk(exit_model="intrabar_fixed")` + the M4 `QualificationGate`; production spine and
  `configs/production/*` untouched until a separate governed promotion.

---

## Phase 1 — Model-Intent Reconstruction (DOCS · no code) — answers Question A

Consolidate verified per-model intent (already established from agent reads, with file:line). For each
model state: primary purpose · market phenomenon · features consumed · **why it deliberately ignores the
rest** (horizon / independent-vote / diversification / structural-filter).
- **CRT** (`crt_engine_v2.py`): structural state machine; raw Candle + internal EMA(2,5) + internal
  ATR(14); ignores canonical momentum/volatility *by design* → KEEP SPECIALIZED.
- **Gaussian** (`heuristic_gaussian_engine.py:305`): momentum Gaussian on 3/38 → expansion *candidate*.
- **RR** (`rr_engine.py:45`): candle-polarity on close/high/low (3/38); `min_rr` dead-but-kept →
  KEEP SPECIALIZED.
- **ZoneGate** (`zone_gate_engine.py` + `live_engine.py:202`): full-38 weighted-Gaussian; fail-open to
  0.5/pass on registry error.
- **BitNet** (`bitnet_inference.py:317`): 6-feature hard-reject gate (off by default) → candidate.
- **Regime/Breakout/Trap** (`engine_runner.py:144-213`): 3 features each → candidate.
- **Fusion** (`fusion_engine.py`): regime-weighted blend of 4 engine scores; not feature-driven.

**Split-brain check (here, not later):** `[TO VERIFY]` `models/zone_gate_registry.json` (referenced by
`model_registry.py:877`) appears empty (0 zones) while `models/zone_registry.json` (loaded by live
`BitNetZoneGate`) holds 8 zones — confirm which the active config (`v2_multi_2026_04`, branch `patch`)
actually scores through. If runtime loads the empty one, ZoneGate is silently fail-open in production →
`TruthConflict`.

---

## Phase 2 — Feature-Ownership Matrix (DOCS · the canonical authority)

The **deliverable everything else defers to.** Existing-doc-first: extend `docs/topics/feature-schema.md`,
or promote `docs/topics/model-intent-and-feature-ownership.md` from `_template.md`. Build the
**Model × 38-Feature matrix**, each cell ∈ {REQUIRED, BENEFICIAL, OPTIONAL, KEEP-SPECIALIZED, UNKNOWN}
with a WHY tagged as **(A) intent** or **(B) evidence-pending**. Built on verified consumption maps —
*not* the reports' biased "VECTOR_ONLY ≈ low value." No deletions; no expansion decided yet. Register a
finding (F-04x) capturing the matrix. **Finalize this before any retraining/architectural change.**

---

## Phase 3 — Static Weights + Permutation Importance (MEASURE) — begins Question B

Replace the report's biased **zero-ablation** with distribution-preserving measurement:
1. **Static weight read (cheapest, no model run).** New `scripts/research/zone_weight_introspection.py`:
   load `zone_registry.json`, emit per-zone + aggregate per-feature weights and `zero_indices` — read
   directly which of the 38 each zone uses.
2. **Predictive importance (reuse existing).** Run `scripts/research/edge_attribution_study.py`
   (`sklearn.permutation_importance` + mutual-info + drop-column LOO + survival/coverage gates) on the
   canonical set. **Do not build a new ablation script.**
Outputs → `docs/analysis/feature-importance-<date>.md` (point-in-time). Research authority only.

---

## Phase 4 — Decision-Flip Importance Through the Full Spine (MEASURE) — sharpest Question B

The question that actually matters: does perturbing a feature change a *trade decision*? Small new harness
reusing the spine-as-hypothesis adapter + `forward_walk`: **permute (not zero)** each feature column,
re-run the fusion decision path, count decision flips per feature → the **Decision Influence Matrix**
(ΔZone, ΔFusion, % trade-flips). Consistency check: a feature zeroed in every zone must show ~0 flips.

**Ensemble-correlation measurement (new, per review):** compute pairwise correlation of the 4 engine
scores at baseline, and (in Phase 6) re-compute after any expansion — expansion that raises inter-engine
correlation / correlated-failure is penalized regardless of marginal predictive gain. Record as a finding.

---

## Phase 5 — ZoneGate Label-Quality Verification (independent confirmation)

`[TO VERIFY]` Direct reads show 6/8 zones with negative mean_RR and ~96–98.65% SL-hit training labels
(zone_0: TP 1.3% / SL 98.65% / mean_RR −0.029, n=20,708) — consistent with F-038/F-025 but **not yet an
architectural assumption.** Independently confirm: (a) the metadata reflects the labels the zones were
actually fit on (not stale meta); (b) regenerate a sample of those labels via
`src/research/measurement/forward_walk.py` (`intrabar_fixed`) + `CostModel(cfg.round_trip_bps)` and
compare to stored outcomes; (c) confirm the registry that runtime loads is the one carrying these labels
(ties to Phase 1 split-brain). Output: a finding that either confirms "label-quality is the dominant
ZoneGate defect" or refutes it. **Go/No-Go gate for Phase 6** lives here: expand/retrain only if Phase 4
shows a currently-ignored feature with material decision-flip influence (B), **or** Phase 5 confirms the
label defect.

---

## Phase 6 — Scoped, Evidence-Driven Expansion / Retrain (advisory-first · ONLY if Go)

Sequenced; CRT/RR untouched (Question A says specialized by design).
- **Stage 6a — ZoneGate label/exit fix (root cause):** regenerate honest labels (forward_walk
  intrabar_fixed + `cfg.round_trip_bps`), locate the zone-registry builder (BitNetSearchEngine / the
  script that produced `zone_registry.json`), retrain a *candidate* registry to a **research path (NOT
  `models/`)**.
- **Stage 6b — feature-ownership expansion (gated on 6a + Phase 4):** expand Gaussian/Regime/BitNet to
  their *relevant* features only; retrain candidates in research paths.
Each stage measures: decision-flip vs baseline, **inter-engine correlation delta**, `metrics_oracle`
parity, M4 `QualificationGate`, `GoalValidator.evaluate()` vs G001. Register PROMOTE/REJECT findings.

**Cost configurability (user ask):** reuse the **existing** knob `ResearchConfig.round_trip_bps`
(`configs/research/research_config.json` → `costs.round_trip_bps`; `src/research/costs.py` already
config-driven). Thread `cfg.round_trip_bps` through all new label/retrain code; **never hardcode 12**;
replace literal "12bps" *display* strings in new code with config-derived values (follow the existing
`provenance_block(...)` pattern). Production-side cost knob out of scope unless separately requested.

---

## Phase 7 — G001 / M4 Validation (MEASURE · decides authority)

Run candidates through the frozen rails: M4 `QualificationGate` (7 gates, intrabar_fixed + configurable
bps), `metrics_oracle` 2-instrument determinism parity, `GoalValidator` report vs the G001 spec. A
candidate earns *research* authority on PROMOTE; it earns nothing toward production unless ΔG001 is
demonstrated **and** ensemble-correlation did not worsen.

## Phase 8 — Production-Promotion Discussion (NOT in this plan)

No `ModelRegistry.promote()` / `models/` write / `configs/production/*` change here. Promotion is a
separate, governed decision contingent on Phase 7 ΔG001 — explicitly deferred per §6.5.

---

## Files

**Create:** `scripts/research/zone_weight_introspection.py` · decision-flip + correlation harness
(`scripts/research/`) · `docs/analysis/feature-importance-<date>.md` · Stage 6a/6b retrain drivers
(only if Go).
**Modify (additive):** `docs/topics/feature-schema.md` *or* new `model-intent-and-feature-ownership.md`
(the Matrix) · `docs/current-findings.md` + §6.2 Truths Index in `CLAUDE.md` (F-04x: matrix; importance;
correlation; label verdict; expansion result) · `MEMORY.md` + `memory/project_model_intent_feature_ownership.md`.
**Reuse (do not rebuild):** `scripts/research/edge_attribution_study.py` · `src/research/measurement/forward_walk.py`
· `src/research/costs.py` · `src/research/qualification.py` · `src/analytics/metrics_oracle.py` ·
`src/config_layer/goal_validator.py`.

## Verification

- **Phases 1–2:** Matrix complete (every model×feature cell tagged A/B with WHY); split-brain documented.
- **Phases 3–4:** static weights + `edge_attribution_study.py` + decision-flip harness run clean and
  reconcile (zeroed-everywhere feature ⇒ ~0 flips); baseline inter-engine correlation recorded.
- **Phase 5:** label regeneration reproduces (or refutes) stored zone outcomes; verdict registered.
- **Phases 6–7:** `pytest` green per `docs/reference/testing.md`; `metrics_oracle` parity on candidate
  ledgers; M4 + GoalValidator attached; **no diff under `models/` or `configs/production/`**; expansion
  shows correlation not worsened.
- **Cost knob:** flip `costs.round_trip_bps`; confirm labels/net-RR move; grep new code for literal `12`
  cost constants (must be none).
- Every phase ends with a §6 SESSION LOG entry; findings flipped same-turn (Findings Mandate).

## Risks / most-likely failure mode

- **Forcing all models onto all 38 features** → eliminates intentional specialization, raises correlated
  error, adds complexity with no ΔG001. Guarded by Question-A/B separation + the correlation gate.
- **Treating unverified ZoneGate/label claims as fact** → mitigated by the `[TO VERIFY]` Phase 5 gate.
- **Most likely empirical outcome is another null** (F-019…F-040) — acceptable, high-knowledge-ROI *iff*
  the label-quality question is cleanly answered.


================================================================================
SOURCE_FILE: docs/implementation_plan/d-tradelatest-results-feature-trace-sem-goofy-hanrahan.md
SOURCE_BYTES: 3802
PART: 3/10 FILE 15/16
================================================================================

# Analysis-only task — no code/repo changes

## Context
User pasted a broken Python snippet (tries `json.load()` on a file named
`semantic_layer_validation_7day_bars.csv`, which fails — CSV isn't JSON) plus a
hand-typed fallback reconstruction of "contradiction" percentages, followed by a
draft markdown report titled "Unexplained Semantic Mismatches in Market Behavior."
The ask: given the repo has three related files (csv / md / json) under
`results/feature_trace/`, determine which one actually suits the requirement, and
evaluate the correctness/completeness of the pasted script + report against it.

User confirmed: deliver the analysis only, no files to be created or edited.

## Findings (to report to user, no implementation needed)

1. **Three files, one lineage** — all in `results/feature_trace/`, produced by
   `scripts/analysis/semantic_layer_validation.py`:
   - `semantic_layer_validation_7day_stats.json` — the **source of truth**. Full
     machine-readable stats: geometry_verification, feature_statistics,
     non_canonical_evidence_statistics, and `contradiction_scan` (7 predicates
     with occurrences/pct/examples).
   - `semantic_layer_validation_7day.md` — human-readable narrative report,
     explicitly derived from the json ("Every statistic below is drawn from
     results/feature_trace/semantic_layer_validation_7day_stats.json"). Already
     contains a complete Part 3 contradiction table (all 7 predicates) plus
     co-occurrence stats, missing-semantics, redundancy analysis, and a final
     assessment.
   - `semantic_layer_validation_7day_bars.csv` — raw per-bar feature dump (635
     lines incl. header, one row per of the 634 finalized bars) — the "excel"
     file. This is tabular per-row data, not aggregated stats; it is NOT valid
     JSON (hence the pasted script's `JSONDecodeError`).

2. **Which file suits the requirement** — the pasted script wants
   `contradiction_scan["semantic_mismatch_predicates"]`, which only exists in the
   **`_stats.json`** file. The script's bug is simply pointing at the `.csv`
   filename while calling `json.load()`. Correct fix (if ever needed): open
   `semantic_layer_validation_7day_stats.json` instead.

3. **The pasted "manual fallback" numbers are correct but INCOMPLETE** — the 4
   hand-typed predicates (10/1.58%, 1/0.16%, 5/0.79%, 18/2.84%) match the real
   json exactly. But the json's `contradiction_scan.semantic_mismatch_predicates`
   has **7** predicates, not 4. Missing from the pasted report:
   - `trend_bias==Bearish while break_of_structure==BullishBreak` — **25
     occurrences, 3.94%** (the single largest predicate in the whole scan —
     bigger than the one the draft report emphasizes).
   - Doji (`body_ratio`<0.1) carrying `break_of_structure`≠0 — 14, 2.21%.
   - `liquidity_sweep`≠0 AND `break_of_structure`≠0 same bar — 2, 0.32%.
   - The repo's own `.md` explicitly combines predicates 4+5 into "43 bars
     (6.78%) — the most frequent recurring inconsistency in the study," which
     the draft report never states.

4. **Verdict to give the user**: use `semantic_layer_validation_7day_stats.json`
   as the data source (not the `.csv`, which isn't JSON, and not a re-typed
   subset). The repo's existing `semantic_layer_validation_7day.md` is already a
   complete, correct, cited analysis of that json — the pasted draft report is a
   partial re-derivation that undercounts contradictions and misses the largest
   one. Point the user at the existing `.md` rather than have them extend the
   partial draft.

## Verification
N/A — no code changes. Answer is delivered as plain-text analysis in the next
turn, citing `results/feature_trace/semantic_layer_validation_7day.md` and
`_stats.json` line numbers already read this session.


================================================================================
SOURCE_FILE: docs/implementation_plan/dataset-navigation-use-the-snug-sparrow.md
SOURCE_BYTES: 6839
PART: 3/10 FILE 16/16
================================================================================

# Plan: Configurable Mother-Range / Inside-Close Detector (XAUUSD M15)

## Context

New OHLCV-derived market-structure concept, generalized from the user's 4-hour formulation to
an **arbitrary configurable block size `x`**:

1. Group M15 bars into blocks of `x` bars (`x=16` → 4-hour, `x=96` → "1 day", any `x`).
2. Block 1 is the **mother range**: `H₁ = max(high)`, `L₁ = min(low)`, `R₁ = H₁ − L₁`.
3. Block 2's **last close** `C₂` is tested: `inside = L₁ ≤ C₂ ≤ H₁`.
4. **`InsideScore = (C₂ − L₁) / (H₁ − L₁)`** — 0.0 = closed at mother low, 1.0 = at mother high.
5. Optional **big-mother filter** so only genuine expansions qualify: `R₁ > k·ATR` or
   `R₁ > P₉₀(trailing R)`.

Thesis: a large expansion followed by a close back *inside* it means the expansion was not
accepted — absorption / failed continuation / balance returning after imbalance.

Fully causal: every quantity uses only bars at or before `C₂`'s own bar.

### Pre-verified — the concept fires (measured on the real 47,275-bar dataset)

| Blocking | Blocks | Inside-close (all) | Inside-close (**big mother only**) |
|---|---|---|---|
| positional `x=16` | 2,954 | 51.8% | **67.9%** (n=321) |
| calendar 4H | 3,095 | 51.7% | **71.8%** (n=351) |
| positional `x=96` | 492 | 50.3% | **68.1%** (n=69) |
| calendar 24H | 516 | 50.9% | **56.8%** (n=74) |

Baseline is a coin-flip (~51%); **the big-mother filter lifts it to 68–72%** — a ~16–20pp
lift. The hypothesis is real and worth instrumenting. `InsideScore` median ≈ 0.53–0.60 when
inside (closes cluster mid-range, not at the edges).

### Data-truth correction the spec needs (verified)

**This dataset's trading day is 92 bars, not 96.** Measured: `bars/day` median **92** (496 of
516 days); the **00:00–00:45 UTC hour is absent** (75-minute daily gap, 394 occurrences;
weekend gaps 2,955 min). A day runs 01:00 → 23:45 UTC.

Consequences, which the implementation must handle rather than paper over:
- `x=96` is **not** "1 day" here. Positional 96-bar blocks absorb 4 bars of the next day and
  the phase **drifts 4 bars per day, compounding**.
- `92 mod 16 = 12`, so positional 16-bar blocks also do not stay aligned to wall-clock 4-hour
  boundaries across days.

### Design decision taken (no user round-trip needed)

Rather than force a choice, **both blocking modes are implemented on one code path** and
reported side by side, because the divergence is itself a finding (positional `x=96` 68.1% vs
calendar 24H 56.8% — 11pp apart on the headline number):

- **`positional`** — every `x` consecutive rows. Always exactly `x` bars. Drifts vs wall-clock.
  This is what the `x` parameter literally means.
- **`calendar`** — anchored to real UTC boundaries derived from `x` (`x=16` → 4H boundaries,
  `x=96` → daily). Matches what a trader sees on a chart. Bar counts vary (3–16 observed) at
  the daily gap and weekend edges.

## Approach

Single new read-only script: **`scripts/analysis/mother_range_inside_close.py`**.
No `src/` module, no config change, no ontology registration — this is a research-stage
descriptive measurement, following the precedent of the two scripts already built this session
([semantic_layer_validation.py](scripts/analysis/semantic_layer_validation.py),
[mature_semantic_audit.py](scripts/analysis/mature_semantic_audit.py)).

### CLI

```
--csv          data/mt5/XAUUSD_M15.csv
--block-bars   x (repeatable; default: 16 96) -- the configurable block size
--blocking     both | positional | calendar   (default both)
--big-rule     percentile | atr_mult | none   (default percentile)
--big-pct      90        (P90 of trailing block ranges)
--big-k        1.5       (for atr_mult: R1 > k*ATR)
--lookback     100       (trailing window for the big-mother threshold)
--output-dir   results/mother_range
```

### Traceability (the explicit requirement)

Every block pair emits a fully hand-verifiable record — CSV + JSONL:

`x` · `blocking_mode` · `pair_id` · block-1 `[row_start, row_end]` + `[ts_start, ts_end]` +
`n_bars` · **`H1` with the row index & timestamp of the bar that set it (argmax)** ·
**`L1` with the argmin bar's index & timestamp** · `R1` · block-2 `[row_start, row_end]` ·
`C2` with its row index & timestamp · `inside` · `InsideScore` · `big_threshold_value` ·
`big_rule_used` · `big_pass` · `max_source_row_index` (the causality proof: must be ≤ `C2`'s
row index).

Anyone can take a `pair_id`, open the CSV at the cited row range, and re-derive `H1`/`L1`/`C2`
by hand.

### Causality discipline

The big-mother threshold is computed from **prior blocks only** (`.shift(1)` on the trailing
rolling quantile / ATR), never including the block being judged — unambiguously causal, no
self-referential threshold. Asserted in-script.

### Outputs

- `results/mother_range/mother_range_x{X}_{mode}_blocks.csv` — the per-block trace
- `results/mother_range/mother_range_stats.json` — statistics across every `x` × mode
- `results/mother_range/mother_range_report.md` — the readable comparison: inside-close rate
  (all vs big-filtered), lift over baseline, `InsideScore` distribution, block-count and
  bars-per-block sanity, the positional-vs-calendar divergence, and worked hand-verifiable
  examples (largest mother range; deepest inside close; a clean failure/outside case).

### Critical files

- `scripts/analysis/mother_range_inside_close.py` — the only new file
- [data/mt5/XAUUSD_M15.csv](data/mt5/XAUUSD_M15.csv) — source (gitignored; 47,275 bars)
- [scripts/analysis/semantic_layer_validation.py](scripts/analysis/semantic_layer_validation.py) — structural precedent (arg parsing, `_native()` JSON coercion, SHA-256 provenance header, rule-selected examples)

## Verification

- **Determinism**: two runs → byte-identical outputs excluding the timestamp header.
- **Block integrity**: positional blocks assert exactly `x` bars each; calendar blocks report
  their true bar counts and never silently pad.
- **Causality assertion**: for every record, `max_source_row_index ≤ C2_row_index` — fails
  loudly otherwise. Plus an explicit check that the big-threshold at block *i* is computed
  only from blocks `< i`.
- **Hand re-derivation**: pick 3 records at random, independently recompute `H1`/`L1`/`C2`
  straight from the raw CSV rows at the cited indices, and confirm exact match.
- **Reproduce the pre-verified numbers**: positional `x=16` must yield 2,954 blocks / 51.8%
  baseline / 67.9% big-filtered; calendar 4H → 3,095 / 51.7% / 71.8%. A deviation means the
  implementation drifted from the probe and must be explained, not accepted.
- **Boundary cases**: `x` larger than a day, `x=1`, and `x` not dividing the dataset evenly —
  confirm the trailing partial block is dropped, never silently truncated into a short block.
