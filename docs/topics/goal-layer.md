# Topic: Goal Layer (economic-objective layer)

> **Topic-visibility unit.** One concept, narrated in human language, kept in sync with the
> code on every working response (`CLAUDE.md §6.1`). Read this to understand the topic — what
> code it covers, how it's reached, what tests it, what's still open — **without loading the
> rest of the codebase**. Link, don't inline.
>
> Created: 2026-06-14 · Updated: 2026-07-26 (G001 consumer attribution ledger) · Status: living

## In plain language
The Goal Layer is the system's single, machine-readable statement of **what success means in
business terms** — trades/month, RR, drawdown, expectancy — frozen as goal id **G001** in the
active production config. It exists because the codebase was rich in engines and fusion but had
no explicit economic objective above them: you could optimize a config to a great fitness score
and still drift away from the trading outcome the owner actually wants. The Goal Layer closes
that gap. It is the *economic-objective* dimension that sits **alongside, never above**, the
`goal.md` invariant ordering (replay correctness > explainability > telemetry > advisory-AI):
a run that meets every business target but breaks determinism is still rejected.

Authority is **advisory-first**. Every backtest emits a `goal_report` comparing measured metrics
to G001 (measure-only telemetry — it never changes a decision). A dormant `goal.enforce` flag
(default `false`) can later turn goal failure into a hard promotion gate. It is dormant by design:
the spine currently produces ~0.8 trades/month with negative expectancy under realistic exits
(Program 1 closed — F-019→F-027), so today the Goal Layer's value is to *quantify the gap to
G001*, not to block 100% of runs.

## Code covered
- [`src/config_layer/goal_schema.py`](../../src/config_layer/goal_schema.py) — `GoalSpec` (frozen dataclass) + `load_goal_spec()`. Reads the `goal` config section; **fail-soft** when absent (returns `GoalSpec.disabled()`), fail-fast when present-but-malformed.
- [`src/config_layer/goal_validator.py`](../../src/config_layer/goal_validator.py) — `GoalValidator.evaluate(metrics, spec)` → `GoalReport`. Pure/deterministic comparison; missing metric ⇒ `SKIP` (not FAIL).
- [`src/runtime/backtest_v2.py`](../../src/runtime/backtest_v2.py) — `BacktestMetrics.trades_per_month` (span-derived) + `MetricsEngine._attach_goal_report()` attaches the report to `distribution["goal_report"]` (additive, measure-only, same pattern as the ROI block).
- [`src/config_layer/config_validator.py`](../../src/config_layer/config_validator.py) — `_run_quality_gates()` folds goal FAILs into `hard_failures` **only when `goal.enforce=True`** (dormant; fail-open on load error).

## Ins / Outs
- **Ins:** the `goal` section of `configs/production/<ACTIVE_VERSION>.json` via `get_prod_section("goal")` (G001: `trades_per_month` {min/target/max}, `avg_rr`, `win_rate`, `max_drawdown_pct`, `risk_per_trade`, `expectancy_r`, `timeframe`, `instruments`, `constraints`, `enforce`); measured metrics dict (`trades_per_month`, `win_rate`, `max_drawdown_pct`, `expectancy_r`; `avg_rr` reports SKIP — no faithful aggregate metric).
- **Outs:** `GoalReport.to_dict()` `{enabled, enforced, goal_id, decision: PASS|FAIL, criteria:[{name, comparator, target, actual, gap, status}]}` — surfaced in `BacktestMetrics.to_dict()["distribution"]["goal_report"]`.

## Entry points & validations
- **Reached via:** any backtest (`BacktestRunner` → `MetricsEngine.compute` → `_attach_goal_report`); the promotion path (`config_validator.validate` → `_run_quality_gates`) when `goal.enforce=True`.
- **Validated by:** the config_hash is unaffected (it covers only `params`), so the goal section is governance-neutral; goal enforcement (when on) flows through the existing `ValidationReport` APPROVE/REJECT gate — no parallel authority.

## Tests
- [`tests/test_goal_schema.py`](../../tests/test_goal_schema.py) — parse, partial goal, **absent-section fail-soft (F-018)**, malformed fail-fast, real-config G001 load.
- [`tests/test_goal_validator.py`](../../tests/test_goal_validator.py) — PASS/FAIL per criterion, gap-sign convention, SKIP-not-FAIL, disabled no-op, enforced flag.
- [`tests/test_goal_metrics.py`](../../tests/test_goal_metrics.py) — span-derived `trades_per_month`, additive `goal_report` telemetry, advisory (never gates).
- [`tests/test_resample_completeness.py`](../../tests/test_resample_completeness.py) — GUARD: HTF data-completeness is already enforced by the M15 gap gate + native-HTF gap analysis, so no new validator was added to the frozen `dataset_integrity.py`.

## Fits in architecture
Layer 0 / economic objective, above the data→engines→fusion→risk→execution spine. See
[`docs/architecture/goal.md`](../architecture/goal.md) §1.1 (canonical targets) and the
acceptance siblings it unifies: `config_validator` (promotion gate) and the M4
`QualificationGate` (`src/research/qualification.py`).

## Discussion (filled in-session)
> Standing parallel-discussion surface. Append dated entries; never delete — supersede.

- **Risks:** 2026-06-14 — `avg_rr` SKIP was CLOSED by Metrics Layer V2 ([metrics-layer.md](metrics-layer.md)): the bound now compares against realized `avg_rr_net`; `avg_planned_rr` is advisory telemetry in `distribution.metrics_v2.rr`.
- **Challenges:** 2026-06-14 — the owner proposed a full `GOAL.md`/`goal_validator`/Data-Governor freeze; ~80% already existed (data integrity, ROI metrics, config_validator, M4). Built only the genuine gap (machine-readable goal + advisory report), reused the rest.
- **Blockers:** none.
- **Ambiguities:** 2026-06-14 — aspirational G001 vs measured reality; resolved as advisory-first + dormant `enforce` so targets can be aspirational without blocking.
- **Enhancements:** 2026-06-14 — flip `goal.enforce=true` once an edge clears G001; add a true avg-RR metric; per-instrument goal overrides.
- **Need more info:** the canonical numbers are the owner's example values — revisit when a real edge exists.
- **2026-07-26 — Semantic vs economic separation formalized:** permanent ledger
  [`docs/governance/g001_consumer_attribution.md`](../governance/g001_consumer_attribution.md)
  attributes each consumer (CRT spine, fusion, zone, BitNet, RR, session, Ultron, shadow)
  with semantic_status vs economic_status vs authority_ladder_level. All consumers currently
  ladder=0; economic MEASURED_POSITIVE count=0. Feature-layer parity lives in
  [`fm_ownership_consumer_matrix.md`](../governance/fm_ownership_consumer_matrix.md) and
  **never** sets G001 authority (`economic_authority=NONE` per FM). Rebuild:
  `python scripts/governance/build_g001_consumer_attribution.py` (+ ownership matrix sibling).
