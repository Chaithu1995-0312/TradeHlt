# Audit — Tradelatest Live-Path Trace (§1 of the State Summary)

## Context

You asked for an **audit of the live-path trace only** (§1 of the *Tradelatest State Summary*
living doc). Goal: confirm every hop in §1 against the actual source, and flag anything the doc
states that the code does not actually do. The State Summary is your external working doc (not a
file in the repo — `grep` found no copy under `D:\Tradelatest`), so the deliverable is this report.

Scope of files read (all under `src/`, full reads unless noted):
`runtime/live_engine_hook.py`, `core/engine_runner.py`, `core/ultron_risk_gate.py`,
`core/ultron_risk_gate_wrapper.py`, `core/gate_intelligence.py::compute_crt_levels`.

**Verdict:** the trace is *directionally correct* but contains **one confirmed live-path defect**,
**two stale path references**, and **several framing inaccuracies**. Details below, each grounded in
`file:line`.

---

## Findings (ordered by severity)

### F-A — CONFIRMED DEFECT: Telegram alert + MT5 order are unreachable on the live path
**Severity: High · Confidence: Certain (file:line proven, no normalization exists)**

- `UltronRiskGate.evaluate()` returns `"decision": "approve"` / `"reject"` — **lowercase**
  ([ultron_risk_gate.py:192](src/core/ultron_risk_gate.py:192),
  [:344](src/core/ultron_risk_gate.py:344), [:365](src/core/ultron_risk_gate.py:365)).
- `UltronRiskGateWrapper.evaluate()` returns the gate's dict **verbatim** — "no fields added,
  removed, or modified" ([ultron_risk_gate_wrapper.py:95](src/core/ultron_risk_gate_wrapper.py:95),
  [:128](src/core/ultron_risk_gate_wrapper.py:128)).
- The live hook gates **both** the Telegram signal alert and the MT5 `send_order` on
  `ultron_result.get("decision") == "APPROVE"` — **uppercase**
  ([live_engine_hook.py:863](src/runtime/live_engine_hook.py:863),
  [:888](src/runtime/live_engine_hook.py:888)).
- A repo-wide grep confirms **no `.upper()` / normalization** sits between the wrapper output and
  these checks.

**Consequence:** `"approve" != "APPROVE"`, so on a genuinely approved trade the Telegram alert and
the MT5 order placement blocks **never execute**. The doc's §1 closing line ("`TelegramBridge` and
`MT5Bridge` … called after Ultron approval") describes the *intent*; the code is wired but dead.
This contradicts the trace.

> Note: this is a real fix candidate but is **out of audit scope**. Recommended follow-up below.

### F-B — Path drift: two modules are cited at the wrong location
**Severity: Medium (breaks navigation) · Confidence: Certain**

| Doc says | Actual |
|---|---|
| `src/inout/live_engine_hook.py` | `src/runtime/live_engine_hook.py` |
| `src/features/feature_store.py` | `src/core/feature_store.py` (import is `from core.feature_store import FeatureStore`, [live_engine_hook.py:37](src/runtime/live_engine_hook.py:37)) |

Other §1/§2 paths checked (`engine_runner`, `execution_planner`, `gate_intelligence`,
`ultron_risk_gate`, `fusion_engine`, `strategy_orchestrator`) are correct.

### F-C — Framing error: StrategyOrchestrator is NOT a 5th engine inside EngineRunner
**Severity: Medium · Confidence: Certain**

Doc §1 step 3 says *"EngineRunner.run() orchestrates 4 core engines + StrategyOrchestrator as 5th
engine."* Reality:
- `EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}` — exactly 4; the completeness check
  rejects only on these ([engine_runner.py:52](src/core/engine_runner.py:52),
  [:725](src/core/engine_runner.py:725)).
- StrategyOrchestrator runs **outside** EngineRunner — as a *pre-run* in the live hook **before**
  `EngineRunner.run()` ([live_engine_hook.py:633-674](src/runtime/live_engine_hook.py:633)), and its
  consensus is injected via `context["strategy_consensus_score"]`.
- Inside EngineRunner it becomes a 5th `engine_results` entry **only conditionally** — when
  `strategy_consensus_score >= 0.0` — and FusionEngine consumes it **only if**
  `weight_strategy_consensus > 0` ([engine_runner.py:706-717](src/core/engine_runner.py:706)). It is
  **not** part of the mandatory completeness set.

Correct framing: *the live hook runs StrategyOrchestrator first and injects its consensus into
context; EngineRunner forwards it to FusionEngine as an optional 5th weighted input, not a mandatory
engine.*

### F-D — `compute_crt_levels` raises; it does not return zeros (stale guard rationale)
**Severity: Medium · Confidence: Certain (behavior) / Likely (runtime impact)**

Doc §1 step 5 (and the live hook's GAP-6 comment at
[live_engine_hook.py:754-758](src/runtime/live_engine_hook.py:754)) state the function *"returns
sl=0.0 / tp=0.0 when ATR=0 or the direction is unknown."* Actual:
`compute_crt_levels` **raises `ValueError`** when `atr <= 0` or `direction ∉ {1,-1}`
([gate_intelligence.py:62-67](src/core/gate_intelligence.py:62)).

The call site ([live_engine_hook.py:724](src/runtime/live_engine_hook.py:724)) is **not** wrapped in
a try/except, so that edge raises an uncaught exception out of `process()` — the downstream
`_sl_ok`/`_tp_ok` naked-order guard ([:759-773](src/runtime/live_engine_hook.py:759)) is never
reached for the `atr=0` / `direction=0` case. (In practice `atr=0` is likely filtered earlier by the
min-ATR adapter gate, so the live trigger is `direction == 0` reaching `decision == "execute"`.)

### F-E — `UltronRiskGate` module self-test is stale (asserts a reason string the code no longer emits)
**Severity: Low (self-test only) · Confidence: Certain**

The RR-floor reject reason is `"rr_too_low_after_costs"`
([ultron_risk_gate.py:246](src/core/ultron_risk_gate.py:246)), but the `__main__` self-test asserts
`risk_reason == "rr_too_low"` ([:475](src/core/ultron_risk_gate.py:475)). Running the module
directly fails at Test 3. Not on the live path, but it's drift inside a file the trace depends on.

### F-F — Injected RegimeClassifier weights appear unused by the fusion path
**Severity: Low–Medium · Confidence: Likely (needs one more confirmation in fusion_engine.py)**

The live hook classifies regime via `RegimeClassifier` and injects both `context["regime"]` and
`context["fusion_weights"]` ([live_engine_hook.py:594-606](src/runtime/live_engine_hook.py:594)).
But `EngineRunner.run()` **recomputes its own regime** via `detect_regime(input_data, dual_cfg)` and
calls `self.fusion.compute(engine_results, regime=current_regime)` —
`context["fusion_weights"]` is never passed to fusion
([engine_runner.py:742](src/core/engine_runner.py:742),
[:754](src/core/engine_runner.py:754)). So the doc's implication (step 1 "injects regime" → step 3
"applies regime-aware fusion weights" *from that injection*) is misleading: fusion weighting is
driven by EngineRunner's internal `detect_regime`, not the injected classifier label/weights.
(The `UltronRiskGateWrapper` regime **does** come from `engine_outputs["regime"]`, which is
`detect_regime`'s value — so the wrapper is consistent; only the *fusion-weight injection* looks
dead.) Recommend confirming `fusion_engine.compute()` ignores context before hardening this in the
doc.

### F-G — Possible feature-count drift: live hook says "35", schema doc says 38
**Severity: Low · Confidence: Possible (schema layer, outside live-trace scope)**

The live hook comments reference *"35 CANONICAL_FEATURES"*
([live_engine_hook.py:256](src/runtime/live_engine_hook.py:256),
[:343](src/runtime/live_engine_hook.py:343)), while State Summary §2 (and `FEATURE_SCHEMA` v3.0)
says **38**. Flagged for a separate schema-layer check — not part of the live-path trace, do not
resolve blindly.

---

## What the doc got RIGHT (keep as-is)

- The **two-Ultron distinction** is correct and well-stated: `UltronRiskGate` (capital protection,
  in the live hook) is explicitly *distinct from* `RegimeGovernor` (signal-quality, Step 6 inside
  EngineRunner). Code confirms ([engine_runner.py:38-41](src/core/engine_runner.py:38),
  [ultron_risk_gate.py:4-12](src/core/ultron_risk_gate.py:4)).
- **CRT is the sole SL/TP authority** — ExecutionPlanner computes entry only; SL/TP1/TP2 come from
  `compute_crt_levels` ([live_engine_hook.py:718-737](src/runtime/live_engine_hook.py:718)). ✓
- **BitNet not wired into the live path** — confirmed by the explicit comment + default-0 fields
  ([live_engine_hook.py:830-834](src/runtime/live_engine_hook.py:830)). ✓
- **FeatureStore is the canonical ingestion boundary** with raw-dict fail-open fallback
  ([live_engine_hook.py:555-570](src/runtime/live_engine_hook.py:555)). ✓
- **Kill-switch pre-check blocks execution + returns early** before Telegram/MT5
  ([live_engine_hook.py:843-855](src/runtime/live_engine_hook.py:843)). ✓ (Note: this `KillSwitch`
  in the live hook is separate from `UltronRiskGate`'s *own* persisted kill-switch at
  [ultron_risk_gate.py:202-212](src/core/ultron_risk_gate.py:202) — two independent kill mechanisms;
  the doc lists only the latter under Ultron's checks.)

---

## Corrected §1 trace (drop-in replacement for your State Summary)

1. **`HookedLiveEngine.process()`** (`src/runtime/live_engine_hook.py`) — entry for live candles.
   Calls `super().process()`, builds `_build_engine_input` (strict OHLCV), then **FeatureStore**
   path (fallback to raw dict on failure). Initialises `RegimeClassifier` and injects
   `context["regime"]`. **Runs StrategyOrchestrator as a pre-step** and injects
   `context["strategy_consensus_score"]`. Then calls `EngineRunner(engine_config).run(...)`.
2. **`FeatureStore.process()`** (`src/core/feature_store.py`) — canonical ingestion boundary;
   validates canonical features, computes history-derived `double_sweep`, stamps
   `_data_integrity="real"`. *(Feature count 35 vs 38 unresolved — see F-G.)*
3. **`EngineRunner.run()`** (`src/core/engine_runner.py`) — 7 internal steps: adapter gate →
   run 4 engines (crt/gaussian/zone_gate/rr) **+ optional injected strategy_consensus** →
   completeness check (4 only) → fusion (regime from internal `detect_regime`) → fusion-threshold
   gate → belief gate → **RegimeGovernor** (Step 6, signal-quality) → **DecisionEngine** (sole
   emitter of `execute`/`reject`).
4. **`ExecutionPlannerV1_2.plan()`** (`src/config_layer/execution_planner.py`) — derives intent,
   calls `GateIntelligence.decide()`, computes **entry only** (no SL/TP).
5. **`compute_crt_levels()`** (`src/core/gate_intelligence.py`) — sole SL/TP1/TP2 authority.
   **Raises `ValueError` on `atr<=0` or `direction∉{1,-1}`** (does *not* return zeros — F-D).
6. **`UltronRiskGateWrapper.evaluate()` → `UltronRiskGate.evaluate()`** (`src/core/…`) — capital
   protection; returns `decision="approve"/"reject"` (**lowercase**).
7. **Post-gate dispatch** — kill-switch early-return; then Telegram + MT5 **intended** on approval —
   **currently dead due to the `APPROVE` vs `approve` mismatch (F-A).**

---

## Recommended follow-ups (OUT of audit scope — your call)

1. **Fix F-A** (one-line, high value): make the live hook checks case-insensitive, e.g.
   `str(ultron_result.get("decision", "")).lower() == "approve"` at
   [live_engine_hook.py:863](src/runtime/live_engine_hook.py:863) &
   [:888](src/runtime/live_engine_hook.py:888). Needs a live/integration test asserting the dispatch
   fires on approval. *(Requires confirming intended casing convention — `UltronRiskGate` is
   lowercase, while governance/types use `"APPROVE"`; align rather than just patch.)*
2. **Fix F-E**: update the `__main__` self-test assertion to `"rr_too_low_after_costs"`.
3. **Confirm + record F-F** by reading `fusion_engine.compute()`; if context weights are indeed
   ignored, either wire them or remove the injection to kill the illusion.
4. **Schema check F-G** separately (35 vs 38) — schema layer, not the live trace.

## Verification for any fix taken later
- F-A: add a unit test driving `HookedLiveEngine.process()` (or a focused harness) with a trade that
  passes Ultron, assert MT5/Telegram bridge stubs are invoked. Run the existing live-hook tests +
  `pytest` per `docs/reference/testing.md`.
- F-E: `python src/core/ultron_risk_gate.py` should print all 6 PASS lines.
