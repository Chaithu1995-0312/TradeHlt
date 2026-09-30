# Repository Analysis Coverage Audit — Phase 4 (Master Directive)

**Status:** IN PROGRESS (Steps 1-2 complete + first prioritized-queue batch; full-repository symbol-level
completion is a multi-session program) · **Date:** 2026-08-12 · **Authority:** research/governance
navigation only — grants no production/promotion authority, does not certify any finding, does not
reopen or close any surface in `docs/governance/closure_authority_index.json`.

**Purpose (per the master directive):** answer *"how much of this repository has been meaningfully
understood by the available LLM/navigation system?"* — not *"how much documentation exists?"*. Those
are different numbers and this audit keeps them separate rather than collapsing them into one
completion percentage.

**Baseline this audit measures against:** commit `84fff5176f5753eb7a12a0e74f8cb857f86ff877` (frozen
baseline commit — see `docs/implementation_plan/master-directive-vast-crane.md` Phase 1.5). The
working tree is **not** physically clean on top of that baseline; 19 post-baseline paths exist
(6 modified-tracked files, 1 uncommitted `assistant_project.md` append, 12 untracked paths) and are
inventoried separately in §2 rather than silently folded into or excluded from the coverage
denominator.

---

## §1. Master Analysis Universe

Reused existing repository denominators rather than inventing a competing census (per the
directive's rule 7 / CLAUDE.md §6.2 rule 1). Each row below is a **live-measured count**, not an
estimate, taken this session.

| Denominator | Source (existing asset, reused not replaced) | Inclusion rule | Exclusion rule | Count |
|---|---|---|---|---|
| Python source files, `src/` | filesystem walk | `*.py` under `src/`, incl. `__init__.py` | `__pycache__/` | **479** |
| Python scripts, `scripts/` | filesystem walk | `*.py` under `scripts/` | `__pycache__/` | **357** |
| Python tests, `tests/` | filesystem walk | `*.py` under `tests/` | `__pycache__/` | **419** |
| Config files, `configs/` | filesystem walk | all file types | — | **66** |
| Model artifacts, `models/` | filesystem walk | all file types | — | **57** |
| All git-tracked files (repo-wide) | `git ls-files` | everything HEAD tracks | — | **2,955** |
| Registered scripts (governed script universe) | `scripts/analysis/script_census.py` (SITS denominator) | every script the SITS registry classifies | test-only/vendor scripts excluded by the tool's own rule | **378** total — by category: RESEARCH_RUNNER 135, DIAGNOSTIC 115, GOVERNANCE 44, DATA 22, ORPHAN 24, PROBE 13, TRAINING 13, MAINTENANCE 12; **323 have `__main__`**, 32 flagged `hygiene_env_access` (report-only) |
| Feature-DAG nodes (governed feature universe) | `scripts/analysis/feature_dag_layers.py` (fresh probe run this session → `docs/governance/feature_dag_layers-2026-08-12.json`) | every node in the topological feature DAG | — | **49 nodes**, `is_dag=True`, canonical coverage **39/39**, 0 undefined_deps, 0 monotonicity_violations |
| Semantic OS FileIdentity entries | `docs/governance/semantic_os/file_identities.yaml` | every file with a registered semantic identity | — | **98 entries** (2,901 YAML lines ÷ ~30 lines/entry) — i.e. only **98 of 479** `src/` files (~20.5%) have *any* FileIdentity, before asking whether that identity was source-verified (§3 shows two of the seven spine entries admit they weren't) |
| Encyclopedia rows | `docs/book/encyclopedia/encyclopedia_rows.jsonl` | one row per file the Book/Encyclopedia describes | — | **813 rows** |
| Closure & Authority Index surfaces | `docs/governance/closure_authority_index.json` | named architectural surfaces with a closure ruling | — | **11 surfaces** (generated_at_utc `2026-07-11` — over a month stale relative to today; not contradicted, just unrefreshed) |
| Meaningful symbols, `src/` (AST-measured, this session) | `ast.walk` over all 479 `src/` files, 0 parse errors | every `ClassDef`/`FunctionDef`/`AsyncFunctionDef` node, incl. nested/private | none — this is a raw upper bound, not filtered for triviality | **587 classes**, **3,573 functions/methods** |
| Generated/boilerplate `src/` files | `__init__.py` count | `__init__.py` under `src/`, <5 lines | — | **58 total `__init__.py`, 22 near-empty (<5 lines)** — a defensible "generated/non-executable" floor |
| Post-baseline asset count | this session's git status + Phase 2 investigation | the 19 paths in §2 | — | **19** (0 `BASELINE`, 7 `POST_BASELINE_WORK`, 12 asset-classified) |
| Navigation-asset count (assets that describe other assets) | Semantic OS package + Encyclopedia + census tooling themselves | `docs/governance/semantic_os/*.yaml` (5 files), `docs/book/encyclopedia/*` (README + 6 group files + JSONL), `scripts/analysis/{script_census,feature_dag_layers,behavior_census}.py`, `scripts/governance/{construction_protocol,feature_surface_query}.py` | — | **~16 first-class navigation-asset files** |

**Reading this table honestly:** 98/479 `src/` files (20.5%) have a FileIdentity; 813 Encyclopedia
rows exist against 2,955 tracked files (27.5%) — but row/entry *existence* only proves `INDEXED` or
`DOCUMENTED` (§3's dimension set), never `SOURCE-INSPECTED` on its own. That gap is exactly what §3
measures for the one place this session went deep enough to check it.

---

## §2. Post-baseline path classification

Every path is git-verified present/absent and unmodified by this session (no deletes, moves,
commits, or `.gitignore` edits performed). Labels use the required taxonomy; one label per path,
with the deciding evidence.

| Path | Git state | Label | Evidence |
|---|---|---|---|
| `assistant_project.md` (SESSION LOG append) | Modified (+14/-0 at EOF) | `POST_BASELINE_WORK` | Narrates 84fff51 as already-done history → written after the commit, real governance content, not yet folded in |
| `docs/governance/SEMANTIC_OS_CONTRACT.md` | Modified (+17/-0 net) | `POST_BASELINE_WORK` | Undeclared by any of the 5 landed `impact.json`s; separate thread |
| `docs/governance/SEMANTIC_OS_V1_DESIGN.md` | Modified (+11/-0 net) | `POST_BASELINE_WORK` | Same — undeclared, separate thread |
| `docs/governance/model_paths_literal_debt.json` | Modified (+14/-0 net) | `POST_BASELINE_WORK` | Tied to the `bitnet_registry.py`/`live_engine.py` ModelPaths-hardening pair below |
| `docs/implementation_plan/yes-i-traced-the-floofy-forest.md` | Modified (365 lines touched, net -115) | `STALE` | Prior-session finding: proposes registering `FM-071` for absolute ATR, but the actual shipped fix registered `FM-074` instead (commit `a4773c9`) — tracked-baseline content is superseded; the uncommitted diff is mid-repair, not yet landed |
| `src/bitnet/bitnet_registry.py` | Modified | `POST_BASELINE_WORK` | Confirmed via diff: removes a silent `try/except` fallback around `ModelPaths` import, hardening only |
| `src/engines/live_engine.py` | Modified | `POST_BASELINE_WORK` | Same hardening pattern, same undeclared-by-manifest status |
| `.cbmignore` (repo root) | Untracked | `RESEARCH_ASSET` | Byte-identical to `oss_lab/adapters/codebase_memory/lab.cbmignore` (LF vs CRLF only); `INSTALL_ISOLATION.md` explicitly instructs this root copy — deliberate config for the OSS-lab Codebase-Memory tool, not clutter |
| `agent-tools/798de814-….txt` | Untracked | `RESEARCH_ASSET` | 2,211-line real hypothesis-framework result (`H-SECONDLOW-006`), independently referenced from `docs/analysis/session-log-archive/session-log-2026-07-02_to_2026-07-07.md` — the *content* is legitimate prior research output; the *directory* itself is unreferenced anywhere (orphaned filing location, not orphaned content) |
| `bundles/who_how_what_bundle.zip` | Untracked | `DUPLICATE` | 17-file snapshot of already-committed core files, all older/smaller than current versions (e.g. `CLAUDE.md` 73.5KB vs current 113KB) |
| `docs (2).zip` | Untracked | `STALE` | Partial `docs/analysis/`+`docs/topics/` export, newest entry 2026-06-06, vs today's full `docs/` (963 files, Aug-12) |
| `docs (3).zip` | Untracked | `STALE` | Same pattern, newest entry 2026-06-15 |
| `docs/implementation_plan/master-directive-vast-crane.md` | Untracked | `NAVIGATION_ASSET` | This session's own plan-mode artifact — documents the process, not the codebase |
| `mt5_analytics/evaluate_bar_features_outcome.py` | Untracked | `RESEARCH_ASSET` | 519-line finished, well-structured predictor-screening script (argparse CLI, clean docstrings) — cited as a contributing factor in `CH-phase2a-magnitude-states.completion.json`'s disclosed geometry-census residual, i.e. it's real and already referenced by a landed manifest, just never itself committed |
| `scripts (2).zip` | Untracked | `STALE` | Full `scripts/` snapshot incl. `.pyc` cache, newest mtime Aug-6, vs current 357-file `scripts/` tree |
| `terminals/` | Untracked | `ORPHAN` | A captured shell-session record (pid 5144, 2026-07-06) with zero repo references pointing to the directory |
| `tools/oss_lab/` | Untracked | `RESEARCH_ASSET` | Exactly matches `INSTALL_ISOLATION.md`'s designated isolated-binary-install path for the pinned Codebase-Memory tool — deliberate, not a duplicate of the committed `oss_lab/` |
| `ui_kits/` (`control_plane/` + `crt_dashboard/`) | Untracked | `DORMANT` | Real, functional-looking React/JSX control-plane prototype (`README.md` self-describes it as a mock-backed recreation) — but zero repo references anywhere, unwired from `src/control_plane/` |
| `xauusd_backtest_run/` | Untracked | `DUPLICATE` | One 9MB run directory (`run_20260714_130606_XAUUSD/`), structurally identical to the committed `results/{instrument}/backtests/run_*` pattern but sitting outside `results/` |

**Tally:** 0 `BASELINE` (none of the 19 qualify by definition — they're all post-baseline by
construction) · 7 `POST_BASELINE_WORK` · 1 `STALE` (plan doc) · 2 `STALE` (zip exports) · 2
`DUPLICATE` · 1 `ORPHAN` · 3 `RESEARCH_ASSET` · 1 `DORMANT` · 1 `NAVIGATION_ASSET`. Zero `UNKNOWN` —
every path had enough evidence this session to classify concretely. Zero deletions, moves, commits,
or gitignore edits were performed on any of them.

---

## §3. Analysis Coverage Matrix — first proven instance (7 spine modules)

Dimensions are kept separate per the directive — a module can be high on one and zero on another.
`ACCESSIBLE`/`INDEXED` are trivially true for anything in a git-tracked repo an LLM can open, so
they're folded into one column here; the dimensions that actually differentiate modules are
`DOCUMENTED`, `SOURCE-INSPECTED`, `SYMBOL-UNDERSTOOD`, `OUTPUT-TRACED`, `CONSUMER-TRACED`,
`SEMANTICALLY-UNDERSTOOD`, `EVIDENCE-VALIDATED`. All seven were fully read this session (source of
truth: 3 parallel Explore-agent passes, each required file:line citations).

| Module | Lines | `DOCUMENTED` (Semantic OS entry exists) | `SOURCE-INSPECTED` this session | `SYMBOL-UNDERSTOOD` | `OUTPUT-TRACED` | `CONSUMER-TRACED` | `SEMANTICALLY-UNDERSTOOD` | `EVIDENCE-VALIDATED` verdict |
|---|---|---|---|---|---|---|---|---|
| `src/core/engine_runner.py` | 1,167 | yes (`decision.multi_engine_orchestrator`) | yes | yes — `EngineRunner.run()` 8-step pipeline, `detect_regime`/`breakout_engine`/`trap_engine` module fns | yes — REJECT dict or `DecisionResult.to_dict()` + routing metadata, JSONL telemetry, `Collector.log()` | yes — 7 distinct callers found (`live_engine_hook.py`, `backtest_v2.py`, `backtest_bitnet.py`, `forward_tester.py`, `copilot_mode.py`, 2 research adapters) | yes — matches its own "6-step" self-description (code actually has finer sub-steps, noted as coarse-grain not contradiction) | **VERIFIED** |
| `src/core/decision_engine.py` | 240 | yes (`decision.central_authority`) | yes | yes — `DecisionEngine.evaluate/decide_batch/reject`, `DecisionResult` | yes — dict via `to_dict()`, `DynamicThreshold` state mutation | yes — 2 callers (`engine_runner.py`, research decision adapter) | yes — F-048 RR-removal claim confirmed by absence of any RR read in source | **VERIFIED** |
| `src/core/fusion_engine.py` | 768 | yes (`decision.fusion_geometry`) | yes | yes — `FusionEngine.compute/evaluate/fuse_strategy_results`, `ScoreNormalizer`, `EngineHealthTracker` | yes — dict (compute) or `FusionResult` dataclass (evaluate), `FUSION_UNKNOWN_REGIME` integrity event | yes — 6 distinct callers incl. `engine_runner.py`, `copilot_mode.py`, `trade_logger.py` (type-only) | yes — F-038 double-weighting-fix claim matches the 4-engine weighted-average code | **VERIFIED** |
| `src/config_layer/execution_planner.py` | 514 | yes (`execution.planner_intent_classifier`) | yes | yes — `ExecutionPlannerV1_2.plan()` + 4 private helpers | yes — dict with `execution_id` (deterministic md5), intent, entry, gate result, TTL | yes — 4 callers (`live_engine_hook.py`, research adapter, forward tester, copilot mode) | yes — "not SL/TP/RR" claim confirmed by absence + self-test assertion at L470 | **VERIFIED** |
| `src/core/ultron_risk_gate.py` | 495 | yes (`risk.capital_gate`) | yes | yes — `UltronRiskGate.evaluate/reset_kill_switch` | yes — approve/reject dict + persisted `logs/kill_switch_state.json` | yes — 3 callers (`live_engine_hook.py`, its own wrapper, `copilot_mode.py`) | yes — distinctness from `regime_governor.py` and `crt_engine_v2::UltronRiskEngine` confirmed in the file's own header | **VERIFIED** |
| `src/config_layer/config_validator.py` | 611 | yes, but **thin** (`config_layer.config_validator`) | yes | yes — `ConfigValidator.validate/validate_production` + 9 private helpers | yes — `ValidationReport` dict, stdout progress, optional JSON file write, backtest artifacts | yes — 2 production callers (`promotion_manager.py`, `pipeline_mode.py`) + 2 maintenance scripts | **partially — Semantic OS entry itself admits it wasn't source-verified** | **STALE (entry, not code)** — yaml `summary_50` literally says "role... not independently source-verified," `evidence: []`; this session's read confirms the boundary claim is correct but the entry hasn't been upgraded to reflect it |
| `src/governance/promotion_manager.py` | 730 | yes, but **thin** (`governance.promotion_manager`, Tier 2/MEDIUM) | yes | yes — `PromotionManager.promote_from_report/promote_from_tuner_checkpoint/promote_direct/list_versions/load_version` + 7 private helpers | yes — writes `configs/production/{version}.json`, `ACTIVE_VERSION` pointer, `configs/promotion_log.jsonl` events | **weak** — no dedicated `test_promotion_manager*.py`; only indirect grep hits, one real production caller (`pipeline_mode.py`) confirmed, one doc-referenced consumer (`multi_strategy_validator.py`) not import-confirmed | **partially — same self-admitted-unverified pattern** | **STALE (entry, not code)** — yaml explicitly says "accepted at boundary-membership level, not independently source-read," `evidence: []`, despite a fully readable, well-documented module |

**The concrete finding this batch produced:** 5 of 7 spine modules had Semantic OS entries that
were already accurate (`VERIFIED`) — the identity layer correctly described real code. **2 of 7**
(`config_validator.py`, `promotion_manager.py`) had entries that **self-disclose** they were never
source-verified (Tier 2, `evidence: []`) — this is the exact `INDEXED`≠`SOURCE-INSPECTED` gap the
directive asked this audit to find, not a documentation-quality complaint. This session's read now
supplies the missing evidence for both; upgrading the two yaml entries to Tier 1 with `evidence`
pointing at the class/method lines identified above is a small, safe, high-value follow-up
(governance-hygiene only, no behavior change) — not performed in this pass, since it wasn't
explicitly authorized and belongs to the Semantic OS's own edit surface.

---

## §4. What this batch does NOT claim

- **No claim of prior-session analysis.** Every `SOURCE-INSPECTED` mark above is backed by this
  session's own reads (3 parallel Explore-agent passes with file:line citations), not inferred from
  a FileIdentity entry's existence. Where the entry itself admitted it hadn't been source-verified
  (`config_validator.py`, `promotion_manager.py`), that admission is preserved, not overwritten.
- **No completion percentage.** Per the directive's explicit instruction, `ACCESSIBLE`/`INDEXED`/
  `DOCUMENTED`/`SOURCE-INSPECTED`/etc. are kept as separate columns. 7 of 479 `src/` files (1.5%)
  have full-dimension coverage from this session; the remaining 472 are `ACCESSIBLE` (any LLM can
  open them) but not yet source-inspected under this audit — that gap is stated plainly, not
  rounded away.
- **No closure claim.** Nothing in `docs/governance/closure_authority_index.json` is touched,
  reopened, or newly closed by this audit.

---

## §5. Next-session starting point (prioritized queue, denominator stays whole-repository)

The 7 spine modules are the *first* batch in processing-order, not the audit's boundary. Natural
next-priority tiers, by architectural importance (call-graph fan-in / runtime-critical-path
membership / output-producing surfaces), reusing the consumer-trace evidence already gathered in §3:

1. **Direct spine dependencies surfaced in §3's callee lists but not yet themselves analysed:**
   `src/core/gate_intelligence.py` (GateIntelligence — approval authority both `execution_planner.py`
   and indirectly the spine delegate to), `src/core/dynamic_threshold.py`, `src/core/regime_governor.py`
   (`UltronGovernor`/`RegimeGovernor`), `src/core/signal_audit.py`, `src/core/collector.py`,
   `src/core/acceptance_controller.py`, `src/core/convergence_controller.py`,
   `src/core/ultron_risk_gate_wrapper.py`, `src/config_layer/production_config.py`,
   `src/config_layer/model_resolver.py`.
2. **The 4 scoring engines** `src/engines/{crt_engine_v2,heuristic_gaussian_engine,
   ml_gaussian_engine,zone_gate_engine,rr_engine}.py` + `trap_validator_engine.py` — everything
   `engine_runner.py` calls unconditionally.
3. **The two thin-identity modules' upgrade** (`config_validator.py`, `promotion_manager.py` Semantic
   OS entries) as a standalone, low-risk governance-hygiene follow-up.
4. **Runtime entry points**: `src/runtime/{live_engine_hook,backtest_v2,backtest_bitnet}.py` — the
   files that actually instantiate and drive the spine in each execution mode.

This file itself is a `NAVIGATION_ASSET` — the next session should read §1-§3 before re-deriving any
of these counts, and extend §3's table rather than starting a new one.
