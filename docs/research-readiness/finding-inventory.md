# Finding Inventory — Severity & Research-Blocking Lens (2026-06-12)

> **Purpose (Phase 1):** reconstruct every current finding under the `FindingSeverity` schema and
> classify it by *research-blocking* impact — the lens [`docs/current-findings.md`](../current-findings.md)
> (confidence-graded) does not carry. This file is a **view**, not a second source of truth: each
> row cites the authoritative F-id. New findings discovered by this audit are prefixed `A-`.
>
> **Severity:** `critical` = can *invalidate* a research conclusion · `medium` = can *distort* ·
> `low` = cosmetic / doc-drift. **research_blocking** = must be fixed (or explicitly fenced) before a
> finding derived from the affected path can be trusted.

## A. New findings from this audit (evidence: source + the full-suite run)

| id | description | severity | impact | evidence | fix_cost | research_blocking |
|---|---|---|---|---|---|---|
| **A-1** | **[RESOLVED 2026-06-12 by R1 — sections added, behavior-neutral.]** **Config↔code split-brain.** Active `v2_multi_2026_04` (patch) lacked config sections HEAD code/tests require — `dataset_integrity`, `uat`, `live_integration` — causing 28 suite failures (`Section '…' not found`). The **Dataset-Integrity gate's thresholds are absent from the active config**, so the data-trust layer runs on hardcoded defaults or is test-only. | **critical** | Data validation a researcher *thinks* is governed by config is actually running on code defaults; per-run reproducibility of the gate is unpinned. | 21×`dataset_integrity`, 5×`uat`(err), 2×`live_integration` in `/tmp/tl_pytest_full.txt`; `get_full_config_dict` shows `data_ingestion` present but no `dataset_integrity` | medium (add sections to a governed config + re-hash, OR gate-on-absent) | **YES** |
| **A-2** | **[bitnet+drift-z RESOLVED 2026-06-12 by R2 — wired, behavior-neutral; `news_blackout_minutes` still inert.]** **Hardcoded config knobs (silent no-op when tuned).** `bitnet_main_threshold` (config 0.55) was unread — gate compares literal `0.55` at [crt_engine_v2.py:1686,1756](../../src/config_layer/crt_engine_v2.py); `feature_monitor.{hard,soft}_drift_z` unread — `FeatureMonitor` hardcodes 3.0/2.5 at [feature_monitor.py:166](../../src/features/feature_monitor.py:166). `news_blackout_minutes` declared but never consumed. | **medium** | A researcher tuning these in config sees zero effect and may conclude "the lever doesn't work" — a false negative. Magic-number convention break (CLAUDE.md §5). | [config-reachability-report.md](config-reachability-report.md) HARDCODED_OVERRIDE rows | low (wire the field OR delete the knob) | partial (refines F-004) |
| **A-3** | **Sharpe & Recovery absent from headline metrics + (was) unverified.** `BacktestMetrics` computes neither; Sharpe exists only in sidecar `portfolio_validation` (population-variance, per-trade). **Mitigated this session:** independent `sharpe()`+`recovery_factor()` added to `metrics_oracle`, parity-checked vs production. | **medium**→resolved | Headline PnL/PF/MAR verified; Sharpe now cross-checked. Recovery has no production counterpart (MAR is the %-space analog). | [metric-integrity-report.md](metric-integrity-report.md) | done | no (closed) |
| **A-4** | **Determinism gate too narrow.** `test_replay_determinism` covered BNBUSDT ledger+7 metrics only — not telemetry JSONL artifacts, not a 2nd instrument. **Mitigated this session** (see Phase 5). | **medium**→resolved | Replay of decisions/telemetry now proven, not assumed. | [determinism-report.md](determinism-report.md) | done | no (closed) |
| **A-5** | **[RESOLVED 2026-06-12 by R3 — capability-probe skipif; 14 fenced→skip-with-reason, 0 fail.]** **Branch-mixed test suite.** TP3/v4 + frequency-boost + promotion-override tests run on `patch` and failed by design (F-016). | **medium** | A researcher running `pytest` sees red and cannot tell real regressions from branch mismatch — erodes the suite as a trust gate. | 5×`tp3_enabled`, 2×`_FREQ_BOOST`, `test_roi_gaps`, `test_promotion_engine_overrides` | medium (mark branch-specific / skip-on-patch) | partial |
| **A-6** | **Doc drift.** `testing.md` claims 51 files/10 domains; actual ~115/13. `codebase-state-map.md` missing `src/research/` row. `AGENTS.md` control-plane alignment. | **low** | Misleads navigation; not a conclusion-invalidator. | `test_codebase_structure_doc`, `test_control_plane_doc_alignment` failures | low | no |
| **A-7** | **Telemetry method gap.** `TelemetryCollector` has no `on_retest_replay` — 3 `test_execution_planner_replay` failures (matches stale memory note, now confirmed real). | **medium** | An execution-planner replay/explain path is broken; reduces decision auditability. | `test_execution_planner_replay.py:44` | low–medium | partial |

## B. Existing findings (F-001…F-017) under the severity lens

Authoritative record: [`docs/current-findings.md`](../current-findings.md). Severity here = research-blocking impact.

| F-id | conclusion (short) | severity | research_blocking | note |
|---|---|---|---|---|
| F-001 | Intelligence not the binding constraint | low | no | economic framing; not a trust defect |
| F-002 | Edge in decision PROCESS not static features | medium | no | shapes *where* to research, not trust |
| F-004 | BitNet hard gate live & persisted; adaptive threshold dormant | medium | partial | **see A-2** — the *config knob* is hardcoded |
| F-005 | TradeNet v2 built but unwired (fusion stub) | low | no | dormant; flagged so no one assumes it runs |
| F-006 | `config_integrity` real but ORPHANED (gates nothing) | **medium** | **yes** | a governance check a researcher may assume protects them does not |
| F-008 | Concept drift DETECTED but not acted on | medium | partial | + A-2: the drift *thresholds* aren't even config-driven |
| F-010 | Headline ROI backtest-only; live PnL UNVERIFIED | **medium** | partial | research on live-PnL claims is blocked until verified |
| F-012 | ReplayMemory/CognitiveBus/Cluster/HMF sidecar-only | low | no | explains the dormant-sidecar test failures (assign_cluster etc.) |
| F-013 | scan→allocate→ExecutionLoop + PortfolioAllocator ORPHANED | **medium** | partial | live runs single-candle spine; portfolio-level research blocked |
| F-016 | active config = v2_multi_2026_04 on patch; v4 = post-TP3 line | **critical** | **yes** | the split-brain root; **A-1/A-5 are its concrete symptoms** |
| F-009/11/14/15/17 | per-instrument doctrine, OOS persistence, timing edges, session lever | low–medium | no | economic conclusions; trust-neutral |

## Summary counts

- **critical (research-blocking):** A-1, F-016 (same root: patch config lags HEAD code).
- **medium (research-blocking / partial):** F-006, F-010, F-013, A-5, A-7, A-2/F-004, F-008.
- **resolved this session:** A-3 (Sharpe/Recovery oracle), A-4 (determinism breadth).
- **low:** A-6 doc drift, plus trust-neutral economic findings.

**The single highest-leverage fix:** resolve the config↔code split-brain (A-1/F-016) — bring the
active config's required sections in line with HEAD code (or formally fence the post-TP3 line),
which simultaneously clears the 28 config-section failures and restores the data-integrity gate's
config governance.
