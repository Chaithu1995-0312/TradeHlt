# HANDOFF.md — Live Multi-LLM State

> Hand-edited working memory passed between models. Small by design. Updated at the end of each
> cycle (MULTI_LLM_PROTOCOL.md §4 step 9). The compiler folds this into `context/05_HANDOFF.md`.
> The User owns this file (`multi_llm/roles/ROLE_USER.md`).

```yaml
current_actor:   Claude (Executor)
current_story:   RC-003 EXECUTED on the Phase-1 admitted corpus — first non-null on this population; awaiting Principal
standing_rules:
  # All XAUUSD M15 analysis/backtest/live CSV loads → Phase-1 frozen candidate only (fail-closed)
  canonical_corpus: data/mt5/XAUUSD_M15.csv  # sha256 4d73f5cebe33ec91…b26aba56; range ..2026-05-21T23:45:00
  regression_fixture: data/XAUUSD_M15_1year.xlsx  # sha256 prefix e0bb97d9 — detector test only
  xauusd_phase1_frozen_candidate: docs/governance/xauusd_m15_phase1_frozen_candidate.json
  xauusd_phase1_path: data/mt5/XAUUSD_M15.csv
  xauusd_phase1_sha256: 4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56
  xauusd_phase1_range: 2024-05-22T01:00:00 → 2026-05-21T23:45:00  # 47275 rows; exclude all later timestamps
  xauusd_phase1_status: FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION  # NOT AUTHORITATIVE/VALIDATED/APPROVED/ECONOMICALLY_ADMISSIBLE
  xauusd_phase1_enforcer: src/data_ingestion/xauusd_phase1_candidate.py (guard_xauusd_csv_path wired in CandleLoader/BacktestRunner)
  xauusd_forbidden_paths: data/XAUUSD_M15.csv (extended 486cf361…), data/mt5/_rejected/XAUUSD_M15.csv
  ohlcv_corpus_freeze: OHLCV-CORPUS-FREEZE-2026-07-10
  corpus_authority: docs/governance/CORPUS_AUTHORITY.md
  xauusd_adjudication: docs/governance/corpus_authority_XAUUSD_M15_adjudication-2026-07-10.md
  hypothesis_policy: re-derive from scratch on MT5 with pre-registration; H-SECONDLOW-002 archived
  detector_module: src/research/secondlow_v1/
  enforcement: tests/research/test_secondlow_v1_detector_regression.py
  sealed_evaluation: H-SECONDLOW-002_Complete_Package/data/sealed_evaluation_set_v1.json  # 21 PRE timestamps, SEALED
  data_policy: H-SECONDLOW-002_Complete_Package/SECONDLOW_RESEARCH_DATA_POLICY.md
  development_corpus: UNAVAILABLE in-repo — prospective MT5 fetch required
  preregistration: H-SECONDLOW-002_Complete_Package/preregistration-H-SECONDLOW-003-v0.1.md  # APPROVED 2026-07-06
  h_secondlow_003_verdict: ARCHIVE_OR_MODIFY (5 EXPOSED / 16 REF; Rule1-4 fail; effect -1.95 ATR median diff)
  forward_plan: H-SECONDLOW-002_Complete_Package/SECONDLOW_Forward_Research_Plan_v1.md
  next_action: Phase-1 CONTENT-ADDRESSED PASS (see xauusd_phase1_validation_report-2026-07-10); residuals remain — do NOT promote to AUTHORITATIVE; feature_38_lineage_census-2026-07-10 complete; next = optional independent open-time/broker calendar or Phase-2 candle math with multi-boundary awareness
completed:
  - RC-002 INITIATED (Lane R): 4 role-separated packages + cycle-scoped dossier/manifest;
    initiate_plan.py gained --manifest/--kind/--prompt (parity-proven byte-identical on RC-001)
  - Track-3 multi-LLM layer + memory/transfer + User role + log split (codebase vs workflow)
  - STORY-1.1: llm_scorer fail-open 0.5 -> 1.0; 82/82 llm tests green; spine byte-identical (181 passed)
  - STORY-1.2 / 1.3: dual-gate + rr-fusion ALREADY GREEN (stale spec) — verified, marked done (no-op)
  - STORY-1.4: gaussian impl switch — stale env-var tests -> config-first (§6.5); ml_gaussian docstring synced (test+doc only)
  - STORY-1.5: replay zone-registry key drift — _build_cluster_stats schema_version dispatch (_zone_cluster_id, fail-fast, no silent default). PLUS re-applied the patch-branch _assign_cluster center/feature_weights repair -> test_assign_cluster 12/12 green
  - STORY-1.6: feature-schema TruthConflict — kept fail_closed=True (test updated to expect False) + wired check_compatibility into MLGaussianEngine (register hash at load, equal-length/order-mismatch guard at compute)
blocked: []
verification:
  - Gate A: 40/40 target tests green (was 4 failing)
  - Gate B: golden-ledger + oracle + invariants + replay-determinism 180/180 byte-identical (spine-neutral; active gaussian_impl=heuristic)
  - Gate C: full suite 1787 passed / 10 failed — ZERO new failures; remaining 10 all pre-existing (timing_reconstructor volume-fixture, agents_path_alignment) — assign_cluster 8 now FIXED
next_actor:      DeepSeek
next_prompt: |
  RC-003 is executed. Phase-1 ADMITTED corpus (47,275 bars, sha 4d73f5ce), n=553 violating /
  1,100 control, both far past the declared floor of 150. PRIMARY (close beyond the swept extreme,
  Referent A = HTF range bound): 0.8047 vs 0.3891, diff +0.4156, block-bootstrap CI excludes zero.
  FIRST NON-NULL on this population in the whole programme, and it falsified the pre-registration's
  own frozen prediction that it would find nothing.
  TWO DEFECTS DECLARED, NOT REPAIRED (section 8 forbids fishing a repair from results): S1's control
  is degenerate (asks close > own high, impossible, p=0 by construction); and the PRIMARY control is
  NOT matched on proximity — violating bars sit in SWEEP having just probed the very bound under
  test. So the gap cannot yet separate a real break-through from a proximity selection effect.
  KILL MAP: nothing dies. SAME_SIDE_CONTINUATION_THROUGH_SWEEP is the leading hypothesis, well
  powered and openly confounded. Identity remains UNKNOWN.
  PROVENANCE CAVEAT: the run executed against an uncommitted working-tree resolver (3,382 lines from
  concurrent sessions, sha ea5d7068), NOT against HEAD 0fa3768 — F-071 class. Verified: the red
  resolver test passes at HEAD and fails against the working tree, before and after RC-003's change.
  NOTHING pending for a model actor. Two Principal decisions open: (1) whether to register a finding
  in docs/current-findings.md — deliberately not done, two interpretations were already retracted in
  RC-002 and the confound here is self-declared; (2) whether to authorize a proximity-matched
  replication, which is a NEW pre-registration, not a re-cut of RC-003.
  Cycle record: multi_llm/research_lane/cycles/RC-003/README.md
confirmation:    "Was this produced by the intended role (Claude=Executor)?  yes"  # RC-002 closed model-side; Claude authored only 2 EXECUTION_EVIDENCE gate checks
```
