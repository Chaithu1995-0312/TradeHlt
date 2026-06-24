# Intent-vs-Code Reconciliation — 2026-06-05

> **Point-in-time analysis (not a living doc).** Reconciles *intended implementation logic* (from
> `docs/plans/` + `docs/analysis/`) against *what the code actually does today*, for the bounded set of
> items that were **unreconciled, ambiguous, or where older analysis now contradicts the code**. The
> ~8 already-reconciled subsystems (findings F-001/02/03/04/05/06/08/10/12) are cross-referenced, not
> re-derived.
>
> **See also:** [`../knowledge-map.md`](../knowledge-map.md) · [`../current-findings.md`](../current-findings.md) · [`readme.md`](readme.md)

**Verdict vocabulary:** `IMPLEMENTED` (code matches intent) · `WIRED-BUT-INERT` (runs but doesn't change
the decision) · `ORPHANED` (built, no caller) · `DEAD` (unreachable branch) · `OFFLINE-BY-DESIGN` ·
`DRIFTED-DOC` (code moved past the doc; the doc is stale) · `BY-DESIGN` (intentional gap, documented).

## Verdicts

| # | Item | Intended logic (source) | Code reality (`file:line`) | Verdict |
|---|---|---|---|---|
| 1 | **Regime → fusion weights** | regime selects per-regime fusion weights | regime re-detected in `engine_runner.py:765`, passed to fusion at `engine_runner.py:777` (`fusion.compute(regime=…)`); per-regime weights applied in `fusion_engine.py:290`. (Live `live_engine_hook.py:659` also injects `context["fusion_weights"]`, but EngineRunner re-detects and ignores that field.) | **IMPLEMENTED** — the routing works inside EngineRunner. `integration-audit.md` "never injected into context" is **DRIFTED-DOC**. (Sub-note: the `context["fusion_weights"]` injection at `:659` is itself ORPHANED/unread — harmless dead path.) |
| 2 | **Correlation Engine v2** | rolling 20-day Pearson + static fallback | `portfolio/correlation_engine.py:44 · CorrelationEngine`, `:98 · correlation`, `:232 · _compute_matrix` (Pearson), `:260 · _heuristic_correlation` (fallback) | **IMPLEMENTED** — the "never built / 0%" intent-gap claim is stale. *But* its only consumer is the portfolio allocator (item 6 path), which is orphaned. |
| 3 | **StrategyOrchestrator (S1–S10)** | consensus is a weighted input to fusion | consensus injected `live_engine_hook.py:721` / `backtest_v2.py:1952` → `engine_runner.py:733` → fused `fusion_engine.py:348 · fuse_strategy_results` **iff** `weight_strategy_consensus > 0` | **IMPLEMENTED (conditional)** — consumed when the config weight > 0; the "byte-identical / inert" reading holds only when that weight is 0. F-012 "consumed" is correct. |
| 4 | **Zone expectancy** | use zone outcome stats (`mean_rr`, `tp_hit_rate`) in the decision | stats exist in `models/zone_registry.json` (`meta.mean_rr`, `meta.tp_hit_rate`) but `zone_gate_engine.py` uses only Gaussian geometry + threshold (`:238`,`:240`); expectancy never read | **ORPHANED** — carried, never consumed; the gate is geometric only. |
| 5 | **Scanner / ranker / signal_pool / universe** | multi-symbol scan + rank + pool | `scanner/scanner.py:14`, `ranker.py:24`, `signal_pool.py:18`, `universe.py:12`; **zero importers** in `src/` outside the orphaned ExecutionLoop | **ORPHANED** |
| 6 | **ExecutionLoop** | continuous multi-signal tick pipeline | `execution/loop.py:31`; **zero callers** in `src/`; live uses `EngineRunner → ExecutionPlannerV1_2 → UltronRiskGate` (`live_engine_hook.py`) | **ORPHANED (scaffolding)** |
| 7 | **ForwardTester** (bitnet + llm_research) | OOS validation of models/policies | `bitnet/forward_tester.py`, `llm_research/forward_tester.py`; callers only in research/training (`expansion_engine`, `model_registry`, `llm_research.evaluator`) — none on live/backtest spine | **OFFLINE-BY-DESIGN** |
| 8 | **DecisionEngine.decide_batch + force-accept fallback** | batch decide; if none pass, promote top-N | `decision_engine.py:162 · decide_batch` (fallback `:186`); **zero callers**; live uses `decision_engine.py · evaluate` per candle (`engine_runner.py:961`) | **DEAD** (unreachable branch) |
| 9a | **Feedback Break 1** — discover_zones ↔ scanner | auto-trigger zone discovery from scan output | two separate control-plane commands; no programmatic link (`control_plane/registry.py`) | **ORPHANED** (manual workflow) |
| 9b | **Feedback Break 2** — live trade → training data | live `TradeRecord` carries the feature vector | `journal/schema.py:9 · TradeRecord` has **no** feature vector; live persists only `bitnet_score_at_entry` (`live_engine_hook.py:916`). (Backtest's local TradeRecord *does* carry `features`, `backtest_v2.py:259`.) | **WIRED-BUT-INERT** — can't build a training set from live trades. |
| 9c | **Feedback Break 3** — model hot-reload | promote without restart | `RegistryWatcher` + lazy `model_registry.py · get_active()` per call (`live_engine.py:113`) | **IMPLEMENTED** (fixed) |
| 9d | **Feedback Break 4** — promotion failures → integrity events | emit to `integrity_events.jsonl` | `model_registry.py:235` logs to Python logger only; `utils/integrity_events.py` exists but isn't called here | **DRIFTED-DOC** (silent omission) |
| 9e | **Feedback Break 5** — drift → retrain trigger | drift drives remediation | drift detected `live_engine_hook.py:676` but no live action (ties to **F-008**); retrain is CLI-only | **OFFLINE-BY-DESIGN** |
| 10 | **ConfigValidator fidelity** | validate configs against the real engine | `config_validator.py` runs the **CRT BacktestRunner** + a flat 4-metric `_fitness_score` (`:151`); **no** Fusion / Zone / BitNet / regime / orchestrator | **BY-DESIGN** (documented in the module docstring) — fast-path proxy; a validated config can still differ live (ties to **F-010**). |

## Already reconciled — see findings (not re-derived)

| Subsystem | Finding | Verdict captured |
|---|---|---|
| BitNet gate (live, persisted; adaptive threshold frozen) | **F-004** | live hard gate, score persisted |
| TradeNet v2 (built, fusion slot stub) | **F-005** | built-but-unwired |
| `config_integrity` (real, not enforced at runtime) | **F-006** | orphaned-from-runtime |
| ReplayMemory / CognitiveBus / Cluster / HMF | **F-012** | sidecar-only telemetry |
| Drift detected, not acted on | **F-008** | detection ≠ action |
| Headline ROI backtest-only; live PnL unverified | **F-010** | measure ≠ live |
| Edge is process (selection/throughput), not features | **F-001/F-002/F-003** | economic verdicts |

## Stale analysis flagged

- **`integration-audit.md` (2026-05-02)** — its "regime never injected", "StrategyOrchestrator should be a 5th engine (parallel/not wired)", and "Correlation Engine not built" claims are now **superseded**: regime routing (item 1), orchestrator consumption (item 3), and the correlation engine (item 2) are all implemented. Scanner-bypass (item 5/6) still holds. A supersession banner is added atop that file.
- **`audit-2026-06-02/dead-dormant-inventory.md`** — already carries supersession notes for TradeNet (F-005) and Probability Surface; this doc additionally updates the 5 feedback breaks (item 9a–9e: Break 3 now fixed, others as noted).

## Synthesis — the one architecture takeaway

The repo contains a **complete but ORPHANED multi-signal path**: `scanner → ranker → signal_pool →
Regime/ConfigRouter → PortfolioAllocator (+ CorrelationEngine) → ExecutionLoop → OverrideHandler`, plus
`DecisionEngine.decide_batch`'s force-accept fallback. **None of it is on the live or backtest decision
path** — both run the single-candle spine `EngineRunner → FusionEngine → DecisionEngine.evaluate →
ExecutionPlannerV1_2 → UltronRiskGate`. So portfolio-level risk limits, cross-instrument correlation,
zone expectancy, and multi-symbol allocation are **built and tested but not enforced live today**. This
is captured as finding **F-013**.
