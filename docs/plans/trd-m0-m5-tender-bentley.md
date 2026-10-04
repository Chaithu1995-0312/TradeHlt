# Trd-M3 → M4 → M5 — Complete the Trading-Architecture Infrastructure Track

> Created: 2026-06-01 · Updated: 2026-06-01 · Milestone: Trd-M3..M5
> Home of record: [`docs/plans/claude-architecture-migration-eager-wreath.md`](../../../D:/Tradelatest/docs/plans/claude-architecture-migration-eager-wreath.md)
> Roadmap row: [`docs/architecture/roadmap.md §2`](../../../D:/Tradelatest/docs/architecture/roadmap.md)

## Context

The trading-architecture migration track is three milestones from done. **Trd-M0
(doctrine/mapping), Trd-M1 (telemetry normalization), Trd-M2 (event extraction) are
COMPLETE.** The remaining three — **M3 orchestration decoupling, M4 dependency inversion,
M5 LLM-layer hardening** — are all *infrastructure*: they make the existing "should we
trade?" engine clean, injectable, and governable but add **zero new decision capability**.

**Why now:** completing M3/M4/M5 is half of the hard entry gate for the parked capability
milestone Trd-M6 (Scenario-Aware Decisioning); the other half is the empirical-throughput
floor (Phase 5a/6c). This plan clears the *infrastructure* half.

**Hard constraints inherited from the migration doctrine** (`assistant_project.md` header):
every step is additive + reversible and scored against the **Five Governance Questions** —
(1) replay deterministic? (2) telemetry comparable across runs? (3) auditable later?
(4) can an LLM reason about the event? (5) is execution authority still isolated? The
acceptance gate for each milestone is **byte-identical trade ledger + summary** on a fixed
CSV + `slippage_seed` (logging/structure only — **no behavior change**).

> Path correction (from exploration): the old plan cited `src/inout/live_engine_hook.py`
> and `src/agent/llm_inference_client.py`. The real paths are
> **`src/runtime/live_engine_hook.py`** and **`src/config_layer/llm_inference_client.py`**.

---

## Trd-M3 — Orchestration Decoupling

**Goal:** kill the module-level singletons in `live_engine_hook.py` (replace with
injection) and defer the two hard import-time config loads — without changing live or
backtest behavior. The decision spine is already the model: `EngineRunner(config)`,
`DecisionEngine(config)`, `FusionEngine(config)`, `ExecutionPlannerV1_2(config)`,
`UltronRiskGate(config)` are all pure constructor-injection with no globals — **follow
that pattern**.

### 3.1 Singletons → injection
- **Current state** (`src/runtime/live_engine_hook.py`):
  - Module globals `live_engine_hook.py:85-96`: `_ENGINE_CONFIG_CACHE`, `_feature_monitor`,
    `_feature_store`, `_orchestrator`, `_kill_switch`, `_telegram`, `_mt5`, `_live_cfg`,
    `_regime_classifier`, `_config_router`.
  - Lazy fail-open accessors `_get_live_cfg()` (:417), `_get_orchestrator()` (:424),
    `_get_regime_classifier()` (:435), `_get_kill_switch()` (:447), `_get_telegram()`
    (:458), `_get_mt5()` (:468). Each is **optional-import guarded** and **swallows init
    failures** (fail-open) — this behavior is load-bearing and must survive.
- **Approach (additive):** introduce a `LiveEngineContext` dataclass holding the six
  injectable collaborators (orchestrator, regime classifier, kill switch, telegram, mt5,
  live cfg). `HookedLiveEngine.__init__` accepts an optional `context: LiveEngineContext |
  None = None`; when `None`, it builds the default context by calling the **existing
  `_get_*` helpers** (so production path is byte-identical). Tests/callers inject mocks.
  The module globals stay as the default-context backing store (backward-compatible) — the
  *coupling* removed is that `HookedLiveEngine` no longer reaches into module globals
  directly; it reads from its injected `context`.
- Preserve the fail-open + optional-import guards verbatim inside the default-context
  builder. No change to `EngineRunner`/`ExecutionPlannerV1_2`/`UltronRiskGate` construction
  (already injected, fresh per `process()` call).

### 3.2 Defer module-level config loads
Two modules fail at **import time** if their config section is absent — convert to lazy
cached accessors (mirror the existing `_get_live_cfg()` lazy pattern):
- `src/config_layer/llm_inference_client.py:81-96` — `_LG_CFG = _get_section("llama_gate")`
  plus the extracted module vars (`SERVER_URL`, `_REQUEST_TIMEOUT`, `_FAIL_COUNT_DISABLE`,
  …). Wrap in a cached `_lg_cfg()` function; resolve the derived constants on first use.
- `src/config_layer/config_validator.py:78-87` — `_VALIDATOR_CFG = _load_validator_cfg()`
  plus extracted gate thresholds (`_GATE_MIN_TRADES_PER_INSTRUMENT`, …). Wrap in a cached
  `_validator_cfg()` accessor.
- Keep values cached after first resolution so steady-state behavior and numbers are
  unchanged. This removes the import-time hard dependency (a microservice-seam blocker)
  without altering any threshold.

### 3.3 M3 verification
- Live + backtest run on fixed CSV + `slippage_seed` → trade ledger + summary
  **byte-identical** to pre-M3 baseline.
- Importing `llm_inference_client` / `config_validator` no longer triggers a config read
  (assert via a test that patches `production_config` and imports the module).
- `pytest` per [`docs/reference/testing.md`](../../../D:/Tradelatest/docs/reference/testing.md).
- Five Governance Questions: pass (pure structural; execution authority untouched).

---

## Trd-M4 — Dependency Inversion

**Goal:** stop governance/analytics/agent/expansion from importing the concrete
`runtime.backtest_v2.BacktestRunner` at module level (the dependency currently points
*upward*, governance→runtime). Introduce a neutral **port** in `core`, inject the factory,
and normalize the result contract + remove the monkey-patch.

### 4.1 Define the port — `src/core/backtest_port.py` (NEW)
- A `typing.Protocol` `BacktestPort` with the minimal consumed contract:
  `run(candle_source, total_candles, output_dir="results") -> BacktestResult`.
- A `BacktestResult` Protocol exposing exactly the fields consumers read (all confirmed in
  `backtest_v2.py:970` `BacktestMetrics`): `approved_trades`, `win_rate`, `avg_rr_net`,
  `max_drawdown_pct`, `total_pnl_rr_net`, `capital_curve`, `total_return_pct`,
  `annualized_return_pct`, `profit_factor`, `return_to_max_dd`, plus `to_dict()` (:1024)
  and `wins`/`losses` (read by expansion).
- A `BacktestFactory` callable type `(config, csv_path) -> BacktestPort`.
- **No change to `BacktestRunner`** — Protocol is structural, so `BacktestRunner`
  (`backtest_v2.py:1379`, `run` :1517) already satisfies the port. The precedent for an
  abstract contract in this codebase is `src/strategies/base_strategy.py:66` (`ABC`); we use
  `Protocol` to avoid forcing inheritance on `BacktestRunner`.

### 4.2 Invert the consumers
Each consumer accepts an injected `factory: BacktestFactory` (default lazily imports
`runtime.backtest_v2.BacktestRunner` **inside the function**, breaking the module-level
upward edge) and types its parameter against `core.backtest_port`:
- `src/governance/portfolio_validation.py:28` (import), construct `:343`, run `:346`.
- `src/config_layer/config_validator.py:146` (import), construct `:154`, run `:155`.
- `src/analytics/sl_tp_comparator.py:589`.
- `src/governance/expansion_integration.py:115` (already passes the class as a param — make
  it the typed factory).
- `src/expansion/expansion_engine.py:55` (already param — type it).
- `src/agent/modes/pipeline_mode.py:136`.
- (`src/runtime/unified_replay_harness.py:24` is same-layer runtime→runtime — leave.)

### 4.3 Normalize the result contract + remove the monkey-patch
- **Remove** `_patch_runner_for_journal_access` (`portfolio_validation.py:467-489`) which
  rebinds `BacktestRunner.run` to read trades back from the written CSV. Replace with the
  documented result accessor / CSV read performed *outside* the runner (the port returns
  `BacktestMetrics`; trade rows are read from `{instrument}_trades.csv` via a helper, not by
  patching the class). This is the user-approved cleanup — inversion is incomplete while a
  global monkey-patch persists.
- **Standardize return shape:** the port returns `BacktestMetrics`. Consumers that today
  expect a `dict` (`expansion_engine.py`, `expansion_integration.py`, `pipeline_mode.py`)
  switch to `.to_dict()` (`backtest_v2.py:1024`) or typed-field access; dataclass consumers
  (`config_validator`, `portfolio_validation`) are unchanged. Document old→new in
  `event-taxonomy.md` if any field name shifts (continuity rule).

### 4.4 M4 verification
- `grep` confirms **no module-level** `from runtime.backtest_v2 import …` remains in
  `governance/`, `analytics/`, `config_layer/`, `agent/`, `expansion/` (lazy in-function
  imports only).
- Validation/portfolio runs produce identical metrics to pre-M4 (byte-identical summary).
- Monkey-patch removed; `portfolio_validation` aggregation still reads the same trades.
- `pytest`; Five Governance Questions: pass (replay/telemetry unaffected — pure wiring).

---

## Trd-M5 — LLM-Layer Hardening

**Goal:** make every LLM advisory call an enveloped, replayable, comparable event; add a
`GOVERNANCE_MODE` flag; add decision-path assertions that execution authority stays
isolated. The replay hot path already has **no LLM** — fusion's LLM gate fires only on the
`evaluate()` path (`fusion_engine.py:616-633`), which is behind `fusion_use_evaluate`
(default **off**); `compute()` (the replay path) has no LLM. M5 must not change that.

### 5.1 LLM advisory event contract
- Add `EventType.LLM_ADVISORY` to `src/events/event_fabric.py:68` (additive, after
  `STATE_TRANSITION` — same pattern Trd-M1/M2 used). 12 → 13 members.
- Emit an enveloped event via `make_event_envelope()` (`event_fabric.py:118-156`) right
  after the fusion LLM gate fires (`fusion_engine.py:633`). Payload: `g_score`, `l_score`,
  `llm_weight`, `[llm_lower_band, llm_upper_band]`, blended `base`, `instrument`,
  `llm_fired`, and **candle timestamp** (so it is replay-comparable on the `evaluate()`
  path — never wall-clock). The event **never feeds back into a decision** (read-only
  projection; execution authority isolated).
- Surface fail-open / circuit-open as monitoring-only events: when
  `llm_inference_client.py` (fail-open empty string, :281) or `llm_scorer.py` (neutral 0.5,
  circuit state :48-52) returns the neutral fallback, emit an `LLM_ADVISORY` event flagged
  `circuit_open=True`. No behavior change to the fail-open path.

### 5.2 GOVERNANCE_MODE flag
- New key in the existing production-config `governance` section
  (`configs/production/*.json`, governance section already present) — e.g.
  `"governance_mode": "strict" | "advisory"`, with an optional `GOVERNANCE_MODE` env
  override read at use site (precedent: env flags + config flags like `fusion_use_evaluate`,
  `enable_llm`). `strict` → assertions raise; `advisory` (default) → assertions log a
  WARNING (preserves fail-open). **Re-hash the config** after editing
  (`python scripts/maintenance/_compute_hash.py`).

### 5.3 Decision-path assertions (execution authority isolated)
- At fusion `evaluate()` entry: assert the LLM result is consumed as a *score nudge only*
  (it blends `base`, never sets `action`) — under `strict` raise if invoked off the
  advisory contract; under `advisory` log.
- At `UltronRiskGate.evaluate()` entry (`src/core/ultron_risk_gate.py:69`): assert the
  inbound plan carries no LLM-derived execution authority (capital gate is final and
  rule-based). Reinforces, not replaces, the existing guards: agent path-guard
  (`executor.py:27-31`) and promotion `APPROVE` gate (`promotion_manager.py:138-145`).

### 5.4 M5 verification
- Replay determinism: backtest (`compute()` path, LLM off) byte-identical pre/post-M5 —
  M5 touches only the `evaluate()` path + additive event emission.
- `LLM_ADVISORY` events are well-formed envelopes; on the `evaluate()` path with a fixed
  seed they are comparable on candle ts; on the replay path **zero** are emitted.
- `GOVERNANCE_MODE=strict` makes a deliberately-violating test raise; default `advisory`
  logs and continues.
- `pytest`; Five Governance Questions: pass (Q4 LLM-reasoning + Q5 isolation are the point
  of this milestone).

---

## Sequencing & Rollback

- **Order: M3 → M4 → M5.** Each ships and validates independently; each is scored against
  the Five Governance Questions and ends with a `📝 SESSION LOG ENTRY` appended to
  `assistant_project.md` (CLAUDE.md §6) + a Topic Sync update (§6.1) for any touched topic
  doc.
- **Rollback:** all additive. M3 keeps module globals as default-context backing
  (`git revert` safe); M4 default factory preserves the old construction (revert restores
  module imports); M5 is a new EventType + new events + flag — no field removed, no replay
  path touched. No config field removed without a documented superseding field (continuity
  rule).

## Out of Scope
- Trd-M6 (Scenario-Aware Decisioning) stays **parked** — needs the empirical-throughput
  floor (Phase 5a/6c) in addition to this infra.
- No profitability tuning, no new decision capability, no new parallel event system.
- `integrity_events.py` stays a deliberate non-enveloped exception (Trd-M1 decision).

## Verification (end-to-end, all three)
1. Capture a baseline: backtest on a fixed CSV + `slippage_seed` → snapshot
   `{instrument}_trades.csv` + `{instrument}_summary.json` (and `llm_episodes.jsonl`).
2. After each milestone, re-run identical CSV + seed → ledger + summary **byte-identical**.
3. `grep` proves the M4 upward imports are gone (lazy in-function only).
4. New `LLM_ADVISORY` envelopes resolve and are replay-comparable on the `evaluate()` path;
   replay path emits none.
5. Full `pytest` per [`docs/reference/testing.md`](../../../D:/Tradelatest/docs/reference/testing.md) green at each step.
6. Update `docs/architecture/roadmap.md §2` status rows (M3/M4/M5 → COMPLETE) and the
   migration plan sequencing block as each lands.
