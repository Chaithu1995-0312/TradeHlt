# Telemetry Completeness Report (2026-06-12)

> **Purpose (Phase 6):** for each stage Data→Features→Engines→Fusion→Decision→Execution→Trades→
> Metrics, verify enough artifacts exist to **replay and explain** a decision; identify missing logs.
> Cross-links [`event-taxonomy.md`](../architecture/event-taxonomy.md).

## Stage × artifact coverage matrix

| Stage | Artifact(s) | Replayable? | Explainable? | Gaps |
|---|---|---|---|---|
| **Data** | input CSV; `DatasetDecision` (logged) | ✅ | ✅ | decision logs to console; not a per-run JSONL artifact |
| **Features** | FeaturePipeline matrix (N×38); drift stats in `BacktestMetrics.distribution` | ✅ | ⚠️ | feature matrix not persisted per-run (rebuilt deterministically) |
| **Engines** | `*_crt_telemetry.jsonl` (per-candle state/scores, 11k+ records); `logs/engine_telemetry.jsonl` (score/conf/latency/cluster/failure) | ✅ | ✅ | engine telemetry to global `logs/`, not run dir |
| **Fusion** | fused score in events; `logs/decision_lineage.jsonl` (per-engine outputs) | ✅ | ⚠️ | **fusion intermediate weights** not consistently emitted |
| **Decision** | `*_events.jsonl`; rejection_reasons in summary | ✅ | ✅ | reject-reason taxonomy good |
| **Execution** | `ExecutionPlan` in events; `*_trades.csv` (entry/SL/TP/RR/TTL) | ✅ | ⚠️ | **UltronRiskGate sizing rationale** not fully traced; `TelemetryCollector.on_retest_replay` **missing (A-7)** |
| **Trades** | `*_trades.csv` (full ledger, 4dp R / 2dp capital) | ✅ | ✅ | the durable ledger artifact |
| **Metrics** | `*_summary.json`; `*_report.txt` | ✅ | ✅ | oracle-verified (Phase 4) |

## Strengths
- **Per-run, self-contained artifact set** (`trades.csv`, `crt_telemetry.jsonl`, `events.jsonl`,
  `summary.json`, `report.txt`) written to the output dir — and **proven byte-identical on replay**
  (Phase 5). A decision can be reconstructed end-to-end from these.
- Rich per-candle CRT telemetry (state transitions, expansion dwell/TTL, candidate lifecycle via
  `TelemetryCollector` in `crt_engine_v2.py`).
- Trade-level `collector.jsonl` (57 fields: features, context, per-engine scores, fusion output,
  outcome) supports offline learning/attribution.

## Gaps (ranked)
1. **A-7 — `TelemetryCollector.on_retest_replay` missing** → 3 `test_execution_planner_replay`
   failures. A retest-replay explainability path is broken. *(medium)*
2. **Fusion intermediate weights** not consistently persisted — given fusion weighting drives
   accept/reject, the *why* of a fused score is partially opaque. *(medium)*
3. **UltronRiskGate sizing rationale** (which sub-check reduced size, by how much) not in the
   per-run trail — sizing decisions are not fully auditable from artifacts. *(medium)*
4. **Global vs per-run split:** `logs/engine_telemetry.jsonl`, `logs/decision_lineage.jsonl`,
   `logs/collector.jsonl` write to a shared `logs/` path (appended/overwritten across runs) rather
   than the run dir — harder to attribute to a specific run for replay. *(low)*
5. **F-010 — live path telemetry unverified.** Backtest artifacts are rich; the live
   (ExecutionPlanner + UltronRiskGate) path's telemetry/PnL is not yet validated. *(blocks live research)*

## Verdict
The **backtest** decision trail is complete and deterministic enough to replay+explain spine
decisions (grade B+). The gaps are at the fusion-weight / risk-sizing explainability margin and in
the live path — not in the core ledger/metrics. Closing A-7 and emitting fusion weights + sizing
rationale would raise observability to A.
