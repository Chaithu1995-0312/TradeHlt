# Plan: Freeze a Goal Layer (economic-objective layer) + close 2 data-governor gaps

## Context

**Why this change.** The user's architectural review argues for freezing a *Goal Architecture*
(`GOAL.md` / `goal_schema.py` / `goal_validator.py` + a hard Data Governor) **before** adding any
new interpreters (P&F, Wyckoff, Market Profile, Order Flow). The core insight is correct: the
system optimizes engines without an explicit, machine-checkable **business goal**, and bad data
silently manufactures fake edges.

**What exploration found (the reconciliation).** Most of the proposal already exists and is good —
so this plan is *additive and surgical*, not a greenfield build:

- **Data Governor — 8 of 10 checks already exist.** `src/data_ingestion/dataset_integrity.py` +
  `src/data_ingestion/ohlcv_schema.py` hard-check missing/duplicate/non-monotonic timestamps, NaN,
  invalid OHLC, negative volume, future timestamps, excessive gap ratio. It runs **before** any
  engine (data-validation-first, confirmed), is wired into both backtest entry points, and raises
  `DatasetIntegrityError`. It uses a **session-aware** `APPROVE/WARN/REJECT` model (crypto 24×7 vs
  FX weekend / 21:00 rollover) — a `test_fx_weekend_gaps_approve` test exists *specifically* so naive
  gap-rejection doesn't kill legitimate FX gaps. **Only 2 gaps remain:** resample completeness
  (4×M15 = 1×H1) and missing H1/H4 bars (`src/research/resample.py` is measure-only).
- **Metrics Layer — ~80% built.** `BacktestMetrics` (`src/runtime/backtest_v2.py`) computes
  profit_factor, expectancy (`avg_rr_net`), win_rate, avg_rr, max_drawdown_pct, return_to_max_dd,
  annualized_return, funnel_counts. **Missing:** trades-per-month / trade-frequency.
- **Acceptance Layer — exists.** `config_validator.py` enforces config-driven hard/soft promotion
  gates; the M4 `QualificationGate` (`src/research/qualification.py`) already forces research
  hypotheses to prove expectancy/PF/OOS/significance — the "prove Δexpectancy/Δfrequency/Δdrawdown"
  contract.
- **The genuine gap (the real insight):** the **Goal Layer is prose-only.**
  `docs/architecture/goal.md` defines invariants + a north-star but has **zero quantitative business
  targets** and no machine-readable artifact. Nothing ties config_validator thresholds + M4 + metrics
  back to one frozen economic objective.

**Framing.** `goal.md §1` declares "Profit is not the primary objective" with the priority order
*replay correctness > explainability > telemetry continuity > advisory-AI*. The business targets are
the **economic-objective dimension** that sits *alongside* (never above) those invariants, and the
advisory-first design respects that. This operationalizes CLAUDE.md §6.1 (ROI toward the user's
economic objective).

**Decisions locked with the user:**
1. **Authority:** telemetry now + a dormant `enforce` flag (default off) that can later flip the goal
   into a blocking promotion gate. Advisory-first because Program 1 is KILLED (F-019→F-027) — a
   blocking gate today rejects 100% of runs.
2. **Location:** a new top-level `goal` section in the production config JSON (reuses
   `get_prod_section`, honors the no-magic-numbers rule + branch-scoped ACTIVE_VERSION truth).
3. **Data:** extend the existing `dataset_integrity.py` (keep session-aware APPROVE/WARN/REJECT) —
   **do NOT** build a pure hard-reject module (would regress FX handling).
4. **Numbers:** freeze the user's example values as the starting canonical goal (editable later).

**Out of scope (explicitly deferred):** P&F / Wyckoff / Market Profile / Order Flow engines, and a
pre-fusion per-engine qualification contract beyond what M4 already provides. Those come *after* this
Goal Layer is frozen.

---

## Implementation

### 1. New `goal` config section (single source of truth for the economic objective)

Add a top-level `goal` key to the **active** config `configs/production/v2_multi_2026_04.json` **and**
the canonical `v1_multi_2026_03.json` / `v2_multi_2026_04.json` lineage. Starting values:

```jsonc
"goal": {
  "goal_id": "G001",
  "enforce": false,                       // dormant blocking flag (default OFF = advisory)
  "trades_per_month": {"min": 20, "target": 40, "max": 80},
  "avg_rr": {"min": 2.0},
  "win_rate": {"min": 0.35},
  "max_drawdown_pct": {"max": 0.10},
  "risk_per_trade": {"target": 0.005},
  "expectancy_r": {"min": 0.20},
  "timeframe": {"execution": "M15", "structure": "H1"},
  "instruments": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
  "constraints": {"reaction_only": true, "human_execution": true, "no_prediction": true}
}
```

Then **rehash**: `python scripts/maintenance/_compute_hash.py` (per config edit). Update each config's
`validation_summary` hash as the script dictates.

> **F-018 guard:** the active `patch` config lags HEAD code. `GoalSpec.from_prod_config` must
> **fail-soft when the `goal` section is absent** (return a disabled spec, advisory off) — never
> fail-fast — so older/lagging configs keep loading.

### 2. `src/config_layer/goal_schema.py` — `GoalSpec` dataclass

Copy the structure of `docs/reference/example-service.py` (`_require` strict accessor,
`from_prod_config` factory, named flow logger). Frozen `@dataclass`:

- Fields mirror the section above (nested ranges as small frozen value objects or simple
  `min/target/max` floats).
- `GoalSpec.from_prod_config(cfg: dict) -> "GoalSpec"`: read `cfg.get("goal")`; if absent →
  `GoalSpec.disabled()` (advisory off, all targets `None`). If present → `_require` each key,
  fail-fast on a malformed-but-present section.
- `enforce: bool` surfaced as a top-level field.

### 3. `src/config_layer/goal_validator.py` — `GoalValidator` + `GoalReport`

- `GoalReport` dataclass: per-criterion `{name, target, actual, pass: bool, gap}` rows + overall
  `decision: "PASS"|"FAIL"`, plus `enforced: bool`.
- `GoalValidator.evaluate(metrics) -> GoalReport`: pure, deterministic function of `BacktestMetrics`
  (so it cannot break replay/golden determinism). Compares trades_per_month, avg_rr, win_rate,
  max_drawdown_pct, expectancy_r against the `GoalSpec`. A disabled spec → `GoalReport` with all rows
  `None`/skipped and `decision="PASS"` (advisory no-op).
- Reuse existing metric fields; no recomputation of PnL.

### 4. Wire as additive telemetry (measure-only) — `src/runtime/backtest_v2.py`

After `MetricsEngine.compute()`, build the `GoalReport` and attach it to
`BacktestMetrics.distribution["goal_report"]` — the **same additive pattern** already used for
`_roi_block` and `feature_drift`. Never gates anything here. This is the F-006/telemetry-additive
convention (see [project_roi_metrics_layer], [project_phase6_roi_baseline]).

### 5. Add `trades_per_month` to metrics — `src/runtime/backtest_v2.py` (`MetricsEngine`)

Derive from the backtest span (first→last candle timestamp, already available) and
`approved_trades`: `trades_per_month = approved_trades / span_months`. Add as a computed property /
field on `BacktestMetrics` so `GoalValidator` can read it. Additive only.

### 6. Dormant flag-gated block — `src/governance/promotion_manager.py` (or `config_validator.py`)

When `GoalSpec.enforce == True`, fold `GoalReport` FAIL criteria into the promotion `hard_failures`
list so `ValidationReport.decision` becomes `REJECT`. **Default `enforce=false` → zero behavior
change today.** Place the check where `config_validator`'s hard gates already merge (keep one
acceptance authority; do not create a parallel gate).

### 7. Close the 2 data-governor gaps — `src/data_ingestion/dataset_integrity.py`

Add two checks, classified into the **existing** APPROVE/WARN/REJECT severity model with
**config-driven thresholds** under the existing `dataset_integrity` config section:

- **Resample completeness:** reuse `src/research/resample.py` to build H1/H4; for every emitted
  bucket whose window is fully tradable (session-aware, reuse `_is_tradable`), verify the expected
  child count (4×M15→H1, 4×H1→H4). Incomplete tradable buckets → severity per threshold.
- **Missing H1/H4 bars:** detect tradable H1/H4 slots with no emitted bar. Honor the session calendar
  so FX weekends / 21:00 rollover are **not** false-flagged (the whole reason to extend, not replace).

Keep `raise_on_fail` / skip-not-abort semantics identical. Bump the relevant validator version
constant if the report shape changes.

### 8. Docs + truth sync (same-turn, per §6.2 / §6.3 / §6.4)

- `docs/architecture/goal.md`: add a "Canonical economic targets (machine-readable)" subsection that
  **points at** the `goal` config section; keep the existing priority ordering and invariants intact.
- `docs/reference/config-reference.md`: document the new `goal` section keys + editing/rehash rule.
- `docs/reference/schemas.md`: add `GoalSpec` + `GoalReport` shapes (§ dataclasses) and the new
  `goal_report` distribution line.
- `docs/topics/`: promote/update **one** topic doc (`goal-layer.md`) from `_template.md` per the Topic
  Sync Mandate (only that file).
- **No finding flip:** this is new infrastructure, not the validation/overturning of a conclusion, so
  `docs/current-findings.md` is unchanged. Record the build as a memory entry + SESSION LOG.

---

## Critical files

| File | Change |
|---|---|
| `configs/production/v2_multi_2026_04.json` (+ v1/v2 lineage) | new `goal` section; rehash |
| `src/config_layer/goal_schema.py` | **new** — `GoalSpec` (fail-soft when absent) |
| `src/config_layer/goal_validator.py` | **new** — `GoalValidator` + `GoalReport` |
| `src/runtime/backtest_v2.py` | attach `goal_report` telemetry; add `trades_per_month` |
| `src/governance/promotion_manager.py` / `config_validator.py` | dormant `enforce` fold-in |
| `src/data_ingestion/dataset_integrity.py` | resample-completeness + missing-H1/H4 checks |
| docs: `goal.md`, `config-reference.md`, `schemas.md`, `topics/goal-layer.md` | sync |

## Reused existing code (do not reinvent)
- `docs/reference/example-service.py` — `_require` / `from_prod_config` / flow-logger template.
- `get_prod_section` (`src/config_layer/production_config.py`) — config access + ACTIVE_VERSION truth.
- `BacktestMetrics` ROI block / `feature_drift` — the additive-telemetry attach pattern.
- `dataset_integrity._is_tradable` + session calendar — session-aware gap logic to keep.
- `src/research/resample.py` — deterministic M15→H1/H4 aggregation for completeness checks.
- `config_validator` hard/soft gate merge point — the single acceptance authority.

---

## Verification

1. **Unit tests (new):**
   - `tests/test_goal_schema.py` — `from_prod_config` parses the section; **absent section →
     disabled spec, no exception**; malformed-but-present → fail-fast.
   - `tests/test_goal_validator.py` — PASS/FAIL per criterion + gap math; disabled spec = advisory
     no-op PASS; `enforce=True` folds FAIL into hard_failures, `enforce=False` does not.
   - `tests/test_dataset_integrity.py` (extend) — incomplete H1 bucket → REJECT/WARN; missing H1/H4
     bar detected; **`test_fx_weekend_gaps_approve` still APPROVES** (no regression).
   - metrics test — `trades_per_month` correct over a known span.
2. **Determinism / replay gates:** run the Backtest Trust Layer parity/replay/golden tests
   (`[project_backtest_trust_layer]`). Confirm `goal_report` is deterministic and golden artifacts
   updated intentionally (additive field).
3. **ORIENT_RUNTIME:** `get_active_version()` still loads `v2_multi_2026_04` after rehash; schema
   keys present (no `unknown override key` error).
4. **End-to-end:** run a BNBUSDT backtest; confirm `goal_report` appears in metrics telemetry,
   `enforce=false` changes no decision, and flipping `enforce=true` in a throwaway config turns a
   goal-missing run into a promotion REJECT.
5. **Full suite + Five Governance Questions** per `docs/reference/testing.md`; append SESSION LOG.
