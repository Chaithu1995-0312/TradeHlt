# Fix the full-suite reds after EPIC-84 / MC-D0a / schema v6.0 / mode-C / entry-chain

## Context
Full run 2026-10-01 (`pytest --ignore=tests/test_execution_planner_replay.py`, log `pytest_full_results.log`):
**216 failed + 27 errors in 97 files**, plus 1 collection error in the excluded file = **98 files**.
The user has reviewed the recent changes as per design. So the default fix is to bring tests, fixtures
and generated artifacts up to the new design, not to revert code. Exception: a test that encodes an
invariant (no lookahead, kernel never imports research, fail-closed config, freeze pins). If that kind
of test fails, it is investigated as a possible real defect and never weakened (CLAUDE.md §6.8: no
silent remediation).

The root causes, read from the `--tb=line` output and confirmed against source/git:
- **EPIC-84 fail-closed config** (2d7dde0, 326b95b, a0cabbd, 466be7d): strict `_require` keys. Test
  fixture configs lack the keys that are now required.
- **MC-D0a engine relabel** (f125339): `rr_engine.py` → `candle_commitment.py`, zone_gate →
  `feature_cluster_similarity`, gaussian → `ema_momentum_kernel`. Tests, Semantic OS yaml and registries
  still carry the old names (`file_identities.yaml:1245` → missing `src/engines/rr_engine.py`). Some
  test edits were sed-renamed to symbols that don't exist (`engine_runner.run_feature_cluster_similarity`).
- **Schema v6.0 / 48-dim (F-107)**: tests pin `5.0`, 39 or 38 dims, or the old names `trend_strength`,
  `candles_since_retest` and `wick_size`.
- **Mode-C** (bc3d408): `CRTEngine.process_candle(..., *, bar_features)` is now required
  (`crt_engine_v2.py:3589`).
- **Entry-chain / A3b**: `_derive_trade_intent` reads `inputs["sweep_detected"]` strictly
  (`crt_engine_v2.py:2549`). The fixtures in `test_execution_contract_v1` lack the key.
- **Generated artifacts are stale**: flow graphs, cli-matrix, findings export, FM matrix, censuses,
  goldens, registries.

## Approach: four buckets, each worked as small batches (fix → targeted pytest → next)

**Bucket A: test/fixture drift to the new design (~95 tests, mechanical)**
- EPIC-84 required keys go into the test fixtures (not into code defaults):
  `test_strict_fetch_gate`(8), `test_session_autoderive`, `test_dataset_integrity`
  (`dataset_integrity.session_calendar.*`), `test_shadow_promotion_gate`(8, `governance.shadow_data_csv`),
  `test_correlation_engine_rolling`(7, `correlation`), `cognitive/test_cognitive_bus`(5),
  `research/test_controls` (`bar_context.instrument`).
- Mode-C `bar_features=` goes into `test_mode_c_resolver_founding`(7); `parent_state` into the spy in
  `test_feature_warmup_coupling`.
- The `sweep_detected`/`double_sweep`/… intent inputs go into the `test_execution_contract_v1`(10) fixtures.
- MC-D0a: `test_engine_runner_dual_gate`(4) patches the real seam (`_compute_soft_zone_score` /
  `get_zone_gate`). `test_feature_layer_freeze`, `test_model_runners_*` and
  `test_reasoning_capabilities` get the new labels.
- v6.0: `test_K_smc_identity`, `test_schema_v4_artifact_reconciliation`, `test_liquidity_distance`,
  `episodes/test_candidate_features`, `test_crt_baseline_trace`, `test_story_ontology`,
  `test_story_library_golden`, `test_feature_dag_layers`, `test_vector_fixture_freshness` (regenerate
  the fixture with its generator).
- Retrieval API: `test_retrieval_pipeline`(9, `Document(domain=)`), `test_retrieval_lexical_parquet`
  (7, `_FixtureConfig.candidate_n`). First confirm the API change is intended (git log on
  `src/retrieval/`).
- `test_execution_planner_replay` loader: register `sys.modules[name] = mod` before `exec_module`
  (Py3.12 dataclass needs it).

**Bucket B: regenerate generated artifacts with their documented generators (never hand-edit)**
- `scripts/analysis/gen_flow_graphs.py` (7), `generate_cli_matrix.py` (2),
  `scripts/governance/export_findings.py`, FM ownership / G001 builders (3), reachability goldens (2),
  three-authority census, layer-audit manifest, SITS chain for `test_script_registry`, model-paths and
  module-attribution ledgers, the `codebase-state-map.md` §1 rows, and `schema_version_registry`
  (register `BRIDGE_SCHEMA_VERSION`).
- Semantic OS source yaml (`file_identities.yaml` etc.) is a SOURCE, not generated. Update its paths and
  slugs for the MC-D0a renames, then re-seed (`test_semantic_os`/`_identity`/`_objects`/`_workbooks`, 12).
- `test_research_family_registry`: bind F-096…F-110. `test_research_dag_provenance`: recount.

**Bucket C: per-item investigation, possible real defects (~20 tests). Report before changing any test.**
`test_runtime_boundary` (kernel imports research), `test_crt_state_resolver_sweep_geometry`
(SWEEP≠DISPLACEMENT), `test_live_rail_replay_cert` (0 bars reach process), `test_live_hook_crt_config_plumbing`,
`test_parent_crt_pivotality`, `test_interpreter_contract`, `test_anti_hallucination`,
`replay/test_assign_cluster` (38-dim artifacts vs 48), `test_gaussian_nb_schema_contract`(6, the alias
map lacks the v6.0 names), `test_replay_determinism`(4, `feature_pipeline.smc_max_window` missing),
`model_runners` `fusion_engine.weight_ema_momentum_kernel` missing in prod config, `test_fm030_031`
(shadow config drifted), `test_crt_threshold_authority_census`(6), the `test_feature_math_lint` /
`test_geometry_census` / `test_gate5` trio, `test_corpus_read_lint`, `test_feature_certification_ledger`,
and the remaining 1-off asserts. Each one is classified as `DOC_DRIFT`, `CODE_DRIFT` or `AMBIGUOUS`
(§6.2). `CODE_DRIFT` gets a minimal src fix only where the design intent is unambiguous; `AMBIGUOUS`
goes to the user.

**Bucket D: authority-gated. Not fixed by Claude; kept red and reported.**
- Clock provenance `user_reviewed=false` for BNB/EURUSD
  (`configs/data_provenance/ohlcv_clock_registry.json`): a human declares this.
- XAUUSD corpus freeze drift (`data/XAUUSD_M15.csv` hash 486cf36→478b075). This may be the
  2026-09-27 restore; needs an authority decision.
- Stale findings past Revalidate-by (F-016…): needs real re-verification, not a date bump.
- Session log cap (368 entries): the known `rotate_session_log.py` fusing hazard.
- Missing gitignored `results/` evidence (cost calibration manifest, RB1 benchmark): it can only be
  recovered by re-running the measurement.

## Execution rules
- Preflight each batch: `git status --porcelain` and a check for another live session (concurrent
  sessions). Stage named files only, never `-A`.
- After each batch: `venv/Scripts/python.exe -m pytest <touched test files> -q`.
- Commit per bucket. Commits touching `src/` carry `[nolog]` or a same-day SESSION LOG entry.

## Verification
1. Targeted pytest per batch: every file in the batch is green.
2. `python scripts/maintenance/check_governance_invariants.py --all` (the authoritative floor) before
   and after.
3. Full suite in the background → log, compared to today's 216F/27E. The expected residue is Bucket D
   plus any Bucket C item the user parks.
