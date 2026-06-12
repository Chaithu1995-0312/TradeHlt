# Test Coverage Gap Report (2026-06-12)

> **Purpose (Phase 7):** classify modules PROVEN / PARTIALLY_TESTED / UNTESTED with risk; triage the
> 66 failures + 5 errors from the full-suite run; correct stale `testing.md` counts.

## Suite facts (empirical)
- **Full run:** `1509 passed, 66 failed, 5 errors, 18 skipped, 2 xfailed` in 525 s.
- **Actual layout: 116 test files across 15 dirs** — `testing.md` claims *51 files / 10 domains*
  (DOC_DRIFT, A-6; correct it). 210 src modules; only `src/llm_research` has zero test reference.
- **Trust layer GREEN:** `metrics_oracle_parity`, `golden_ledgers`, `metric_invariants`,
  `replay_determinism` all pass.

## Failure triage (none in the core spine or trust layer)

| Bucket | Count | Files | Classification | Research-blocking? |
|---|---|---|---|---|
| **Config-section split-brain** | ~28 → **0** | `test_dataset_integrity` (21), `uat`(5 err), `live_integration` (2) | ✅ **RESOLVED by R1 (2026-06-12)** — sections added to the active config, behavior-neutral; 75 tests green | was YES — now closed |
| **Branch-scoped (post-TP3)** | ~16 | `test_roi_gaps` (10), `test_promotion_engine_overrides` (4), `_FREQ_BOOST`/`tp3_enabled` | invalid on `patch` (F-016) | no, but pollutes signal (A-5) |
| **Dormant sidecars** | 11 | `replay/test_assign_cluster` (8), `test_replay_memory_engine` (2), `test_timing_reconstructor` (1) | F-012 sidecar; RME fix wired to v1 config only | no |
| **External-dep** | 11 | `test_llm_connectivity` | LLM fail-open tie-breaker; env (no llama/Groq) | no |
| **Real telemetry gap** | 3 | `test_execution_planner_replay` | `TelemetryCollector.on_retest_replay` missing (A-7) | partial |
| **Doc-drift** | 2 | `test_codebase_structure_doc`, `test_control_plane_doc_alignment` | `src/research` row missing; AGENTS.md | no |

## Module classification (subpackage granularity)

| Subpackage | Status | Risk | Basis |
|---|---|---|---|
| `core` (engine_runner, fusion, decision, ultron_risk_gate) | **PROVEN** | low | dedicated tests + green spine + determinism |
| `analytics` (metrics_oracle) | **PROVEN** | low | golden+parity+invariant (incl. new Sharpe/Recovery) |
| `runtime` (backtest_v2) | **PROVEN** | low | replay determinism (2 instruments), payload integrity |
| `config_layer` (production_config, config_builder, crt_engine_v2, execution_planner) | **PROVEN** | low–med | broad tests; **A-2 hardcoded knobs** = real gap |
| `engines` (crt/gaussian/zone/rr) | **PARTIALLY_TESTED** | med | engines never *isolated* in spine (per bnbusdt-in-spine ledger); scored together |
| `governance` (promotion_manager, model_registry) | **PARTIALLY_TESTED** | med | override-pruning API tests red on patch (branch); core promotion green |
| `data_ingestion` (dataset_integrity, ohlcv_schema) | **PARTIALLY_TESTED** | **high** | 21 reds from missing config section (A-1) — gate runs on defaults |
| `features` (feature_monitor, schema) | **PARTIALLY_TESTED** | med | drift thresholds hardcoded (A-2); 1 schema fail-open red |
| `research` | **PARTIALLY_TESTED** | low | runner determinism green; not in codebase-state-map (A-6) |
| `replay`, `cognitive` (ReplayMemory, Cluster) | **PARTIALLY_TESTED** | low | sidecar (F-012); cluster-collapse reds, off-spine |
| `portfolio` | **UNTESTED-in-path** | med | built but ORPHANED (F-013); allocator never invoked |
| `live`, `inout` (mt5/telegram bridges) | **UNTESTED-in-path** | med | env-gated; live PnL unverified (F-010) |
| `llm_research` | **UNTESTED** | low | zero test reference; sidecar |
| `strategies` (S01–S10) | **UNTESTED-in-path** | low | dormant (shadow-only config, F-012) |

## Recommendations (test hygiene; not behavior changes)
1. **Fence branch-scoped tests** — mark TP3/v4 + freq-boost tests `skipif` on the `patch` line (or a
   `@pytest.mark.tp3` deselected by default) so `pytest` green/red becomes a meaningful gate again (A-5).
2. **Resolve A-1** — adding the missing config sections (or gating-on-absent) clears 28 reds *and*
   restores the data-integrity gate's config governance.
3. **Close A-7** — add/restore `TelemetryCollector.on_retest_replay` (3 reds).
4. **Correct `testing.md`** counts 51→116 / 10→15 (A-6).
5. Consider an **engine-isolation** test harness so the 4 scoring engines can be attributed
   individually (currently only scored jointly).

## Verdict
The suite's *raw* 66-red headline overstates fragility: **0 reds touch the spine or trust layer**;
~55 are split-brain / branch-mix / dormant / env. After fencing branch tests and fixing A-1/A-7, the
suite would be a clean trust gate. Grade **B−** today (noisy gate), **A−** achievable cheaply.
