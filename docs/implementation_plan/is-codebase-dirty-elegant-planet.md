# Commit Plan — snapshot working tree onto a new branch (no switch, Grok untouched)

## Context

`feature/truth-registry-v2` is 23 commits ahead of origin with **122 modified + 212 untracked**
paths (real content: +7,568 / −2,081 ignoring whitespace; `core.autocrlf=true` is *not* what's
inflating it). Nothing is staged.

This is the F-071 failure mode re-accumulating: 19 untracked modules under `src/` means the
committed repository is again not the running system. Several closed findings (F-074…F-084) cite
files that exist only on disk — `src/features/smc/`, `src/research/visual_crt/`,
`tools/tv_forensic/`, `src/config_layer/parent_crt.py`. Their evidence is unresolvable from a
clean checkout today.

**Two hard constraints from the user:**

1. A **Grok session is running in parallel** — do not touch its changes.
2. Commit to a **new branch without switching to it** — 12 other Claude worktrees share this
   `.git`, and this working tree is live.

Intended outcome: every non-Grok, non-junk change lands as a dependency-ordered commit series on a
new branch ref, while the working tree and `HEAD` remain **bit-for-bit unchanged**.

---

## Mechanism — commit without switching

`git checkout -b` / `git switch -c` move `HEAD` and are rejected here. Use plumbing against a
**temporary index file**, which never touches `.git/index`, `HEAD`, or a single file on disk:

```bash
export TMPIDX="$SCRATCH/commitplan.idx"
export GIT_INDEX_FILE="$TMPIDX"
PARENT=$(git rev-parse HEAD)          # 84fff51

# --- repeat per commit N ---
rm -f "$TMPIDX"
git read-tree "$PARENT"               # seed temp index from the parent commit's tree
git add -- <paths for commit N>       # honors GIT_INDEX_FILE, recurses dirs, respects .gitignore
TREE=$(git write-tree)
PARENT=$(git commit-tree "$TREE" -p "$PARENT" -F <msgfile>)
# --- end repeat ---

git branch snapshot/tree-restore-2026-08-19 "$PARENT"   # create ref; does NOT switch
unset GIT_INDEX_FILE
```

Safety properties:

- `HEAD` stays at `84fff51` on `feature/truth-registry-v2`; `git status` in the main tree is
  identical before and after.
- Other worktrees keep their own `.git/worktrees/<name>/index` — untouched.
- Object writes are concurrency-safe; `git branch` creates one new ref.
- `git add` applies the same `core.autocrlf` clean filter as a normal `git add`, so blobs are
  byte-identical to what a normal commit would produce.

**Hook caveat (must be handled manually).** `core.hooksPath=D:\Tradelatest\hooks`, and
`commit-tree` bypasses `pre-commit` / `commit-msg`. Run both gates by hand instead:

```bash
python scripts/maintenance/check_governance_invariants.py
```

and satisfy the §6 commit-linkage rule (`scripts/maintenance/check_session_log_commit.py`) — every
commit touching `src/**` or `configs/production/**` needs a same-day SESSION LOG entry in
`assistant_project.md`, which is already modified in this tree and lands in commit 15.

**Not doing:** no push, no `--force`, no rewriting `feature/truth-registry-v2`, no deletions, no
`git add -A`.

---

## Exclusion set 1 — Grok (DO NOT TOUCH)

Verified as a self-contained workspace, last written 2026-08-18 16:31:

```
.grok/                                                    # incl. rules/GROK.md, PENDING.md, run_mc_crt_sb*.py
GROK.md
grokclosure.txt
groksessionauto.txt
tests/Grok/
tests/test_grok_intent_workbook.py
docs/analysis/grok_test_intent.xlsx
docs/implementation_plan/analyse-last-grok-code-humming-leaf.md
docs/implementation_plan/topic-ladder-and-grok-test-intent-excel.md
configs/research/research_config_mc_crt_sb_xauusd.json    # referenced ONLY from .grok/run_mc_crt_sb*.py
```

## Exclusion set 2 — test-intent workbook effort (user decision: exclude entirely)

Both twins plus the shared generator, since the generator was written one minute before Grok's
workbook and may still be in flight:

```
tests/Claude/                                             # untracked
tests/test_claude_intent_workbook.py                      # untracked
docs/analysis/claude_test_intent.xlsx                     # untracked
docs/analysis/feature-identity-state-inventory-2026-08-19.xlsx   # untracked, Excel lock file present
docs/analysis/~$feature-identity-state-inventory-2026-08-19.xlsx # Excel lock — never commit
claudeclosure.txt                                         # untracked, pairs with grokclosure.txt
scripts/analysis/test_functionality_excel.py              # MODIFIED — leave dirty
docs/analysis/tests_functionality_inventory.xlsx          # MODIFIED — leave dirty
scripts_business_functionality.xlsx                       # MODIFIED — leave dirty
```

## Exclusion set 3 — bulk / junk (gitignored in commit 1, never committed)

```
tools/oss_lab/            283 MB  vendored third-party Codebase-Memory repo
tools/tv_forensic/shots/   12 MB  TV screenshots
xauusd_backtest_run/        9 MB  run output (same class as the already-ignored results/)
ui_kits/crt_dashboard/    4.5 MB
docs (2).zip, docs (3).zip, scripts (2).zip   6.3 MB stale archives
bundles/who_how_what_bundle.zip
agent-tools/<uuid>.txt    session scratch
```

`__pycache__/` is already covered by `.gitignore:1`, so `git add` skips it automatically.

> **One assumption to confirm at execution time:** the user wrote "oos_lab" — read as
> `tools/oss_lab/` (the 283 MB vendored tree). Repo-root **`oss_lab/`** is different: it is already
> tracked, contains real governance work, and **is** committed (commit 13). Gitignoring a tracked
> path has no effect on tracked files but would hide the 5 legitimate untracked files under it.

---

## Commit sequence

Dependency-ordered (F-071 lesson: each commit must import cleanly on its own). Paths are prefixes
— `git add` recurses.

| # | Message (subject) | Paths |
|---|---|---|
| 1 | `chore(gitignore): exclude vendored OSS, TV shots, run output, stale archives` | `.gitignore` (edit), `.cbmignore` |
| 2 | `feat(features): SMC primitives + canonical schema v4.0→v5.0 (F-076)` | `src/features/smc/`, `src/features/feature_schema.py`, `feature_pipeline.py`, `crt_feature_builder.py`, `tests/test_smc_primitives.py`, `docs/governance/feature-layer-freeze-pin-2026-07-20.json`, `configs/market_reality/market_reality_v1.yaml` |
| 3 | `feat(crt): directional displacement contract (F-074)` | `src/config_layer/crt_engine_v2.py`, `state_identity.py`, `configs/formulas/market_crt_states.yaml`, `tests/test_directional_displacement.py`, `test_retrace_reset_direction.py`, `test_crt_states_yaml_transition_parity.py`, `docs/governance/build_manifests/CH-directional-displacement-contract.*` |
| 4 | `feat(htf): parent CRT + HTFState/ObjectiveStatus (F-075, F-078)` | `src/config_layer/parent_crt.py`, `htf_state.py`, `src/features/parent_candle.py`, `src/runtime/parent_crt_feed.py`, `configs/production/v2_htfcrt_2026_08.json`, `v2_htfcrt_objgate_shadow_2026_08.json`, `tests/test_parent_*`, `tests/test_htf_*`, `scripts/research/htf_*`, manifests `CH-htf*`, `CH-parent-crt-caller-wire.*` |
| 5 | `feat(structure): M15 structural range + structure predicate registry` | `src/config_layer/m15_structural_range.py`, `src/structure/`, `src/features/registry/predicate_registry.py`, `src/features/registry/__init__.py`, `derived_registry.py`, `configs/formulas/structure_profiles.yaml`, `tests/test_m15_structural_range.py`, `test_structur*`, `test_predicate_definition_binding.py`, manifests `CH-PSTRUCT-*`, `CH-p-struct-*`, `CH-m15-structural-liquidity-range.impact.json`, `CH-structure-dimension-inventory.impact.json` |
| 6 | `feat(governance): Semantic OS grounding + adversarial review protocol (§6.7/§6.8, F-079)` | `src/governance/semantic_grounding.py`, `semantic_os.py`, `docs/governance/semantic_os/`, `SEMANTIC_OS_CONTRACT.md`, `SEMANTIC_OS_V1_DESIGN.md`, `SEMANTIC_REVIEW_PROTOCOL.md`, `scripts/governance/query_semantic_os.py`, `src/agent/modes/truth_mode.py`, `plan_compiler.py`, `tests/test_semantic_grounding.py`, `test_semantic_query.py`, `tests/governance/test_semantic_review_protocol.py`, manifests `CH-closed-semantic-environment.*` |
| 7 | `feat(ingestion): OHLCV clock detection + provenance registry (F-066 follow-on)` | `src/data_ingestion/clock_detector.py`, `clock_registry.py`, `ohlcv_schema.py`, `dataset_integrity.py`, `historical_fetcher.py`, `src/features/calendar_periods.py`, `configs/data_provenance/`, `docs/governance/clock_evidence/`, `scripts/governance/review_ohlcv_clocks.py`, `tests/test_ohlcv_clock_provenance.py`, `test_calendar_periods.py` |
| 8 | `feat(research): measured broker cost model + adverse stop fill (F-082)` | `src/research/costs.py`, `config.py`, `provenance.py`, `measurement/forward_walk.py`, `measurement/metrics.py`, `configs/research/measurement_contracts/metals_mt5.v1.json`, `src/core/ultron_risk_gate.py`, `tests/test_component_cost_model.py`, `test_cost_model_parity.py`, `test_forward_walk_adverse_fill.py`, `test_measurement_profile_calibration.py`, `test_measurement_contract.py`, manifest `CH-cost-model-broker-truth.*` |
| 9 | `feat(research): Visual CRT trade object + MC-VCRT V2 remeasure (F-081, F-083, F-084)` | `src/research/visual_crt/`, `configs/research/measurement_contracts/instances/`, `scripts/research/vcrt_remeasure_v2.py`, `visual_state_*.py`, `tests/research/test_vcrt_v2_contract.py`, `test_visual_crt_trade_object.py`, `tests/test_visual_state_harness.py`, `docs/research/visual-crt-*`, `visual_crt_trade_object.md`, `reports/xauusd_visual_*`, manifests `CH-vcrt-remeasure-v2.*`, `CH-visual-crt-*` |
| 10 | `feat(tools): TradingView forensic capture + H4 grid reconciliation (F-080)` | `tools/tv_forensic/` **excluding `shots/`**, `scripts/research/tv_engine_odds.py`, `tests/test_tv_forensic_smoke.py`, `reports/monthly_tv_vs_*`, `reports/xauusd_month_tv_engine_odds.md`, manifests `CH-monthly-tv-coverage-h4-recon.*`, `CH-xauusd-tv-odds.impact.json` |
| 11 | `feat(live): live rail scaffolding — feeder, orchestrator, order manager (F-072/F-073)` | `src/inout/live_rail/`, `src/runtime/live_rail_feeder.py`, `live_rail_orchestrator.py`, `live_engine_hook.py`, `src/live/order_manager.py`, `src/core/ultron_live_adapter.py`, `src/agent/modes/pipeline_mode.py`, `src/engines/live_engine.py`, `configs/experimental/spec/live_rail_tickdb_paper.json`, `tests/test_live_rail_*`, `tests/fixtures/ticks/`, `docs/implementation_plan/live-rail-repair-path.md`, manifests `CH-live-rail-pr*` |
| 12 | `docs(governance): CRT object-relations closure CT-009` | `docs/governance/crt_object_relations.yaml`, `crt_object_relations_closure.md`, `crt_closure_report.md`, `crt_executable_state_graph.json`, `tests/test_crt_object_relations.py`, `tests/test_crt_*` (closure/adversarial/baseline/resolver), manifests `CH-crt-object-relations*` |
| 13 | `feat(oss_lab): RI-SOS compatibility runner + QA milestone verdict` | `oss_lab/` (all, tracked + untracked), `tests/test_oss_lab.py` |
| 14 | `chore(registry): feature-math lint, script registry, generated architecture artifacts` | `scripts/analysis/feature_math_lint.py`, `feature_dag_layers.py`, `scripts/governance/seed_script_registry.py`, `scripts/maintenance/check_governance_invariants.py`, `scripts/analysis/CRT_TRACE_WORKFLOW.md`, `crt_episode_number_trace.py`, `run_crt_trace_workflow.py`, `session_filter_funnel_probe.py`, `xauusd_excel_feature_state_trace.py`, `scripts/research/{p_struct_01_displacement_evidence,smc_feature_month_extract,smc_visual_verification,crt_range_rebuild_probe}.py`, `docs/governance/script_registry_*`, `docs/reference/script-matrix.md`, `cli-matrix.md`, `docs/architecture/*.generated.md`, `graph.dot`, `docs/research-readiness/feature-math-lint-report.*`, `src/control_plane/registry.py`, remaining `src/**` + `tests/**` singletons (`bitnet_registry.py`, `sl_tp_comparator.py`, `timing_reconstructor.py`, `resample.py`, `weekly_range.py`, `clean_labels/builder.py`, `model_runners/schema_resolver.py`, `logging_config.py`, `crt_state_resolver.py`, `tests/conftest.py`, …) |
| 15 | `docs: findings F-074…F-084, closure index, topics, memory, session log` | `CLAUDE.md`, `AGENTS.md`, `active_models.yaml`, `assistant_project.md`, `docs/current-findings.md`, `docs/governance/closure_authority_index.json`, `change_contracts.json`, `research_family_registry.json`, `model_paths_literal_debt.json`, `feature_dag_layers*.json/.md`, `ANALYSIS_COVERAGE_AUDIT.md`, `docs/reference/{agent-reference,config-reference,schemas}.md`, `docs/topics/`, `docs/memory/`, `docs/book/A1-testing.md`, `docs/analysis/readme.md`, `docs/analysis/session-log-archive/`, `docs/implementation_plan/` (minus the 2 Grok docs), `docs/research/p_struct_01_*`, `structure-dimension-inventory-displacement.md`, `reports/p_struct_01_*`, `reports/semantic_and_screenshot_layer_review.md`, `tests/test_p_struct_01_*`, `test_fm058_boundary_is_not_sp001.py`, `mt5_analytics/evaluate_bar_features_outcome.py`, `multi_llm/research_lane/prompts/`, `terminals/`, `ui_kits/control_plane/`, `configs/formulas/market_ontology.yaml` |
| 16 | `gov(runtime): ACTIVE_VERSION v2_multi_2026_04 → v2_htfcrt_2026_08` | `configs/production/ACTIVE_VERSION`, `configs/production/v2_multi_2026_04.json`, `configs/promotion_log.jsonl` |

### Why commit 16 is last and alone

`ACTIVE_VERSION` is §4.0 **Tier 0** — the only runtime truth — and §6.2 requires explicit user
approval for edits to it. It has already flipped on disk to `v2_htfcrt_2026_08`, backed by a
matching `PROMOTED` line in `promotion_log.jsonl` (2026-08-15, hash
`7de09f62…`), so this is a governed promotion rather than a stray edit. It nonetheless
**supersedes F-016** ("active config is `v2_multi_2026_04`") on this branch. Isolated so it can be
dropped or deferred with `git branch <name> <commit-15-sha>` without disturbing commits 1–15.

---

## Verification

Run after the branch ref exists — all read-only with respect to the working tree.

1. **Working tree provably untouched** (the load-bearing check):
   ```bash
   git status --porcelain | md5sum
   ```
   Capture before and after; the digests must match. `git rev-parse HEAD` must still be `84fff51`.

2. **Grok surface provably absent from the branch:**
   ```bash
   git diff --name-only 84fff51 snapshot/tree-restore-2026-08-19 | grep -Ei '(^|/)\.?grok|GROK\.md|tests/Grok/|_test_intent|test_functionality_excel'
   ```
   Must return nothing.

3. **Import-resolvability from a clean checkout** (the F-071 gate that caught the last divergence):
   ```bash
   git worktree add --detach ../Tradelatest-commitplan-verify snapshot/tree-restore-2026-08-19
   ```
   Then from that worktree, compile-check every committed module and confirm 0 unresolvable
   imports. Remove the worktree afterward.

4. **Governance floor** (replaces the bypassed `pre-commit` hook):
   ```bash
   python scripts/maintenance/check_governance_invariants.py
   ```
   Expect the 9 pre-existing GREEN_FLOOR failures recorded under F-071 and no new ones.

5. **No bulk blobs leaked in:**
   ```bash
   git diff --name-only 84fff51 snapshot/tree-restore-2026-08-19 | grep -E 'oss_lab/codebase-memory|tv_forensic/shots|xauusd_backtest_run|\.zip$|~\$'
   ```
   Must return nothing.

6. **Residual dirt is only the intended exclusions** — after the run, `git status --porcelain`
   should show exactly the Grok set, the workbook set, and the newly-gitignored bulk paths.

## Rollback

Single command, no history rewrite, working tree unaffected:

```bash
git branch -D snapshot/tree-restore-2026-08-19
```

Orphaned objects are reclaimed by `git gc` on its own schedule.
