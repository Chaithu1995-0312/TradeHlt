# Concatenated implementation plans — part 10 of 10

Source directory: `docs/implementation_plan/`
Files in this part: 16

## Contents

1. `tradelatest-state-summary-cryptic-gosling.md` (12155 bytes)
2. `user-may-want-to-jolly-acorn.md` (6277 bytes)
3. `using-the-current-feature-state-frolicking-unicorn.md` (8325 bytes)
4. `walk-me-through-claude-md-hazy-kite.md` (5800 bytes)
5. `we-have-states-defined-whimsical-penguin.md` (16737 bytes)
6. `we-need-to-commit-reactive-quilt.md` (6798 bytes)
7. `which-model-best-wokrs-atomic-church.md` (14419 bytes)
8. `wlak-me-thorugh-grok-ticklish-axolotl.md` (8122 bytes)
9. `xauusd-gaussian-toward-economics-2026-07-23.md` (16739 bytes)
10. `yes-based-on-the-stateful-flamingo.md` (9692 bytes)
11. `yes-i-can-do-sprightly-hamster.md` (37775 bytes)
12. `yes-i-found-the-polymorphic-gem.md` (14593 bytes)
13. `yes-i-traced-the-floofy-forest.md` (8451 bytes)
14. `yes-the-missing-invariant-tender-bengio.md` (9904 bytes)
15. `yes-the-sources-now-recursive-babbage.md` (7766 bytes)
16. `your-edge-research-platform-compiled-scott.md` (5797 bytes)


================================================================================
SOURCE_FILE: docs/implementation_plan/tradelatest-state-summary-cryptic-gosling.md
SOURCE_BYTES: 12155
PART: 10/10 FILE 1/16
================================================================================

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


================================================================================
SOURCE_FILE: docs/implementation_plan/user-may-want-to-jolly-acorn.md
SOURCE_BYTES: 6277
PART: 10/10 FILE 2/16
================================================================================

# Backwards-Dependency Refactor — Review of Haiku's Work + Completion Plan

## Context
A prior Haiku session ran the ownership audit (Pyan `graph.dot`) and implemented two of the three
HIGH backwards-dependency fixes:
- **HIGH #1** — extract `state_identity.py` to break `crt_engine_v2 ↔ state_contract_loader/state_topology`.
- **HIGH #3** — move `make_neural_fn_v2()` from `trainer.py` → `trade_net_v2.py`.
- **HIGH #2** (`llm_inference_client`) — intentionally PARKED.

This turn reviewed that work, found and repaired defects it introduced, and got the core + doc-citation
tests green. Plan mode then re-activated, so the remaining governance close-out items are captured here
for approval before execution.

---

## Review Findings

### What Haiku did correctly
- Created `src/config_layer/state_identity.py` holding `CRTState`/`Direction`/`RejectReason`/`VALID_TRANSITIONS`/`CRTConfig` (data-only, zero cyclic imports).
- Removed those definitions from `crt_engine_v2.py`; added a re-export line (`crt_engine_v2.py:36`) so old imports still resolve.
- Repointed `state_contract_loader.py` + `state_topology.py` to import from `state_identity`.
- Moved the `make_neural_fn_v2()` factory to `trade_net_v2.py`; removed it from `trainer.py`.
- Source-level dependency direction is now clean (verified this turn).

### Defects Haiku introduced (now FIXED this turn)
1. **16 broken imports** from the blanket `sed`. Lines that imported a *moved* symbol AND a *stayed*
   symbol (e.g. `from config_layer.crt_engine_v2 import CRTConfig, EngineState, StateMachine, Range, Direction, Candle`)
   were wholesale rewritten to `state_identity`, which does not contain `Candle/StateMachine/EngineState/Range/...`.
   → Repaired by pointing those mixed lines back to `crt_engine_v2` (which re-exports the moved symbols).
   Files: `interpreters/{contract,point_and_figure,reference}.py` + 13 test files.
2. **Doc-citation drift** (`tests/test_doc_citations.py` went RED): `docs/topics/crt-spine.md:20`
   cited `crt_engine_v2.py:1143 · VALID_TRANSITIONS` (now at `state_identity.py:69`).
   → Fixed crt-spine.md (test green), plus living-doc citations in `CLAUDE.md:73/148` and
   `docs/architecture/event-taxonomy.md:72`.

### Defects Haiku introduced — STILL OPEN (need execution approval)
3. **SESSION LOG never persisted** (§6, non-optional). Haiku printed the log block in chat but did
   not append it to `assistant_project.md`. No entry for the refactor OR this review exists there.
4. **`docs/architecture/citation-map.generated.md`** not regenerated — a GENERATED artifact that may
   still carry stale `crt_engine_v2` line/symbol citations for the 5 moved symbols.
5. **Graph not regenerated** — `graph.dot` still shows the 3 pre-fix backwards edges. `gen_pyan.py`
   fails on Windows (`WinError 206`, command line too long). Backwards-dep removal was instead proven
   at the source level this turn (HIGH #1 + #3 both RESOLVED).
6. **No memory file** written for the durable belief (Intelligence-Compounding mandate §6.1).
7. Optional hygiene: `crt_engine_v2.py` may have a now-unused `Enum`/`auto` import (1 residual match).

---

## Verified state after this turn's repairs
- `python -m pytest tests/ --collect-only` → **3348 tests collected, 0 import errors**.
- Targeted suites green: CRT/config/state (134p/10s), interpreters+ontology (46p), state
  contract+topology (39p), training (70p), doc-citations+topic-docs (5p).
- Source-level verifier: HIGH #1 and HIGH #3 backwards edges both **RESOLVED**; dependency
  direction is one-way (`crt_engine_v2 → {loader,topology} → state_identity`; `trade_net_v2 → trainer`).

---

## Remaining Work (execute on approval)

1. **Regenerate the citation map** (GENERATED artifact — never hand-edit):
   `python scripts/analysis/gen_citation_map.py` → rewrites `docs/architecture/citation-map.generated.md`.
   Then re-run `tests/test_doc_citations.py` + `tests/test_topic_docs.py` to confirm green.

2. **Full regression sweep** (the plan's original success criterion — only targeted subsets ran so far):
   `python -m pytest tests/ -q` from repo root (ACTIVE_VERSION = `v2_multi_2026_04` resolves at root).
   Investigate any red that isn't pre-existing (baseline the repo already had unrelated M-state).

3. **Optional hygiene**: remove the now-unused `Enum`/`auto` import from `crt_engine_v2.py` if
   confirmed dead (grep for remaining uses first; skip if still referenced).

4. **Graph regeneration** (best-effort): `gen_pyan.py` hits `WinError 206` on Windows. Either
   (a) run it in a chunked/`@argfile` mode if supported, or (b) record that the graph is refreshed on
   the next Linux/CI run and rely on the source-level proof. Do NOT block completion on this.

5. **SESSION LOG (§6, non-optional)** — append ONE `📝 SESSION LOG ENTRY` block to
   `assistant_project.md` covering both the refactor and this review/repair, including the
   `Belief Update / ROI / Goal` line. (Backfill Haiku's missing entry as part of the same block.)

6. **Memory file (§6.1)** — write a `project`-type memory (e.g. `project_backwards_dep_refactor.md`)
   capturing: the ownership-via-dependency-direction method, the `sed`-mixed-import gotcha, the
   re-export back-compat pattern, and that HIGH #2 remains parked; add a one-line pointer to `MEMORY.md`.

7. **Archive the audit** (post-implementation housekeeping): move the scratchpad
   `BACKWARDS_DEPENDENCY_AUDIT.md` + `ownership_audit.py` into `docs/governance/ownership-audit-2026-07-18.md`
   (living record of the method + the 3 findings), so the method is reusable for future "shared service" hunts.

8. **HIGH #2 remains PARKED** — no action; noted as the next cycle's candidate (`llm_transport` extraction).

---

## Verification (end-to-end)
- `python -m pytest tests/test_doc_citations.py tests/test_topic_docs.py tests/test_current_findings.py -q` → green (governance floors).
- `python -m pytest tests/ -q` → no new reds vs baseline.
- Source-level dep check re-run → HIGH #1 + #3 both RESOLVED (already passing).
- `assistant_project.md` tail shows the new SESSION LOG block; `MEMORY.md` shows the new pointer.
- `git status` review before any commit (commit only on explicit user request; branch first if on main).


================================================================================
SOURCE_FILE: docs/implementation_plan/using-the-current-feature-state-frolicking-unicorn.md
SOURCE_BYTES: 8325
PART: 10/10 FILE 3/16
================================================================================

# Plan — Single-paragraph semantic market description from the current feature/state inventory

## Context

The request is a **semantic-description exercise**, not a code change: produce one coherent
natural-language paragraph that describes a single market episode using only the feature and state
vocabulary the repository already establishes, walking observable candle values → feature states →
structural states → CRT/HTF context → decision state → execution intent. Nothing is to be built,
measured, promoted, or claimed. The value is in demonstrating that the repository's separate
vocabularies (canonical vector slots, FM identities, feature states, CRT states, HTF posture,
objective status, direction, reject reasons, trade intent, intent/termination) can narrate one
episode without collapsing into each other — which is exactly the `different registers stay
distinct` discipline of CLAUDE.md §6.6 / §6.8.

Deliverable = the paragraph, emitted in the response. No repository file changes.

## Vocabulary sources consulted (read-only, verified this session)

- `src/features/feature_schema.py` — `CANONICAL_FEATURES`, schema v5.0, `CANONICAL_FEATURE_DIM = 48`
  (v5.0 added the 9 SMC slots at indices 39–47).
- `configs/formulas/market_ontology.yaml` — FM identities and their declared `states:` blocks
  (FM-054…FM-061 structural states, FM-050 `volatility_regime`, FM-068 `rsi_state`,
  FM-069 `displacement_flag`, FM-063 `volume_spike`, FM-051/052 temporal, FM-020/021/027/028,
  FM-041 `atr` vs FM-074 `atr_absolute`, FM-064/065).
- `configs/formulas/market_crt_states.yaml` — the `feature_states:` roster and the CRT-state
  predicates/`valid_transitions`.
- `src/config_layer/state_identity.py` — `CRTState` (12 members: 9 execution-timeframe +
  3 disjoint parent-timeframe), `Direction`, `RejectReason`, `VALID_TRANSITIONS`.
- `src/config_layer/htf_state.py` — `HTFState`, `ObjectiveStatus`, `Objective`.
- `src/config_layer/crt_engine_v2.py:2301` — `_derive_trade_intent` → `liq_sweep` / `pullback` /
  `breakout` / `reversal`.
- `src/execution/execution_intent_v1_0.py` — `IntentState`, `TerminationReason`.
- Active config: `configs/production/ACTIVE_VERSION` = `v2_htfcrt_2026_08` (parent-CRT armed, F-075).

## Semantic consistency constraints honored in the draft

- The SWEEP predicate requires `displacement_flag: NoDisplacement`, so the sweep bar and the
  body-dominated displacement bar are described as **successive** bars, not one bar holding both.
- `SellSideSweep` pairs with `LowerLow` and a LONG consequence per FM-058's own declared semantics.
- Only legal edges are named: `RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION →
  RESOLUTION`, with `SHADOW_PENDING` and `EXPIRED` mentioned as the legal branches they are.
- Parent-timeframe `RANGE_C1 → MANIPULATION_C2 → DISTRIBUTION_C3` is kept as a **separate track**,
  never interleaved with the 9 execution states (state_identity.py disjoint sub-graph).
- `HTFState.DISTRIBUTION` is kept distinct from `CRTState.DISTRIBUTION_C3` (F-077).
- `rsi_state: NeutralMomentum` + `session: LONDON` + directional `trend_bias` are chosen so the
  EXECUTION predicate is coherent rather than contradicted.
- No formulas, no transitions, no meanings invented; no decision-relevance inferred from vector
  membership; no authority or profitability claimed.

## The paragraph (deliverable)

> On this M15 bar the candle reports its `open`, `high`, `low`, `close` and `volume`, and the shape
> those four prices make is what everything downstream reads first: `body_size` against
> `candle_range` (FM-002) gives `body_ratio` (FM-010), while `atr` (FM-041, close-relative) and its
> absolute form `atr_absolute` (FM-074) say how large that range is for this instrument, so
> `volatility_ratio` and the tercile bucket `volatility_regime` (FM-050) can call the bar
> `HighVolatility` rather than `NormalVolatility` or `LowVolatility`; `ema_fast` sits above
> `ema_slow`, so `ema_spread` and `trend_strength` (FM-064) carry a `Bullish` `trend_bias` (FM-054)
> instead of `Neutral` or `Bearish`, `rsi_14` (FM-042) stays inside its configured band so
> `rsi_state` (FM-068) reads `NeutralMomentum` and not `Overbought` or `Oversold`, and
> `momentum_score` with the split `macd_line`, `macd_signal`, `macd_hist_raw` and `macd_hist_z`
> describes the same push in its own units, while `volume_ratio` lifts `volume_spike` (FM-063) from
> `NoSpike` to `VolumeSpike`; structurally this bar traded through the prior swing reference and
> closed back inside it, so `liquidity_sweep` (FM-058) resolves to `SellSideSweep` with
> `sweep_detected` (FM-059) at `SweepDetected` and `double_sweep` (FM-060) still `NoDoubleSweep`,
> `break_of_structure` (FM-057) holds at `NoBreak` even as `lower_low` reads `LowerLow` against the
> carried `swing_low` (FM-067) while `higher_high` stays `NoHigherHigh`, `swing_high` remains
> `NoSwingHigh`, and `displacement_flag` (FM-069) is still `NoDisplacement` on this bar — the
> liquidity picture around it being given by `liquidity_distance`, `liquidity_pressure_score`,
> `pdl_distance`, `pdh_distance`, `eql_distance`, `eqh_distance`, `order_block_distance`,
> `fvg_distance`, `breaker_distance` and `mitigation_block_distance`, with `change_of_character`
> summarising `break_of_structure` against `trend_bias`; on the next bar the body dominates its
> range and `displacement_flag` turns `Displacement`, `disp_strength` (FM-020) and
> `displacement_atr_ratio` (FM-028) sizing that impulse away from the side just swept, after which
> price returns toward the fast-EMA reference so `retest_flag` (FM-061) becomes `RetestActive`,
> `retest_depth` (FM-021) and `displacement_retrace` (FM-027) become meaningful rather than zero,
> and `candles_since_retest` (FM-065) begins counting; read as the execution-timeframe state
> machine, that same sequence carries the engine out of `RANGE` into `SWEEP`, on into
> `DISPLACEMENT` and then `EXPANSION` — where a window flip could instead have left it in
> `SHADOW_PENDING`, or a TTL could have moved it through `EXPIRED` back to `RANGE` — and here it
> advances to `RETEST`; on the parent timeframe a separate three-candle track reads
> `RANGE_C1`, then `MANIPULATION_C2`, then `DISTRIBUTION_C3`, and that parent carries its own
> posture `HTFState.EXPANSION` (as opposed to `ACCUMULATION`, `DISTRIBUTION`, `REVERSAL` or
> `UNKNOWN`) together with an `ObjectiveStatus` of `EXISTS` rather than `NONE`, `ACHIEVED` or
> `INVALIDATED`, oriented `Direction.LONG`; at the decision surface the bar's `session` (FM-052) is
> `LONDON` at its `hour_of_day` (FM-051), so the signal is not turned away as `OUTSIDE_SESSION`,
> nor as `LOW_SCORE`, `NO_DOUBLE_SWEEP`, `NEWS_FILTER`, `HIGH_SPREAD` or `INVALID_STATE`, leaving
> `RETEST → EXECUTION` and then `RESOLUTION` as the remaining legal path; the setup that results is
> classified as the `liq_sweep` intent rather than `pullback`, `breakout` or `reversal` because the
> sweep flags are the ones that are set, and the execution intent for it opens as `PROPOSED` and
> ends either `EXECUTED` or `TERMINATED` under `REJECTED`, `EXPIRED`, `REPLACED` or `CANCELLED`.

## Execution steps

1. Emit the paragraph above as the response body — single paragraph, no list, no table, no
   repository explanation.
2. Append the `📝 SESSION LOG ENTRY` block to `assistant_project.md` per CLAUDE.md §6/§7.4
   (this is the only file write; it is the standing logging mandate, not a change to the system
   being described).

## Verification

- Every name used traces to one of the read-only sources listed above; nothing is introduced that
  those files do not declare.
- Registers stay separate: `HTFState.DISTRIBUTION` ≠ `CRTState.DISTRIBUTION_C3`; the parent
  three-candle track is never spliced into the 9-state execution graph; `Direction`, `RejectReason`,
  trade intent (`liq_sweep`…), and `IntentState`/`TerminationReason` are used only in their own
  layers.
- No transition is named that is absent from `VALID_TRANSITIONS`, and no state combination is
  asserted that `market_crt_states.yaml` predicates contradict.
- No economic, authority, or profitability claim appears (CLAUDE.md §6.5 Authority Ladder); the
  paragraph is descriptive only and grants nothing.


================================================================================
SOURCE_FILE: docs/implementation_plan/walk-me-through-claude-md-hazy-kite.md
SOURCE_BYTES: 5800
PART: 10/10 FILE 4/16
================================================================================

# Plan — Harden CLAUDE.md's doctrine-only mechanisms into test-enforced ones

## Context

Discussion thread (LeCun critique → CLAUDE.md as a "bolt-on world-model/memory" answer)
surfaced two weak links in the prosthesis:

- **#4 prosthetic-grounding fragility** — the SESSION LOG / belief-update / "same-turn"
  mandates are **prose-only**. A single non-compliant turn silently breaks the compounding
  chain. Grounded by Explore agent: ZERO tests touch `assistant_project.md`, the SESSION LOG
  block, the `Belief Update / ROI / Goal` field, or `MEMORY.md`.
- **#3 context-ceiling** — every always-loaded artifact is **append-only, unbounded, no
  rotation/consolidation**. Grounded: `assistant_project.md` = 232 KB / 2,456 lines / 122
  entries (~2 KB/session, no cap); `docs/current-findings.md` = 44 KB / 26 findings (terminal
  F-003/F-007 kept inline forever); CLAUDE.md findings table = 24 always-loaded rows; only
  bounding mechanism is the freshness-CI flag (`test_current_findings.py`), which *flags* but
  never *removes*.

Core realization: the **same technique** (convert a doctrine into a mechanical CI invariant)
hardens #4 AND bounds #3. What it can NEVER do is enforce the *semantics* (truth of a belief,
soundness of ROI) — that residual is irreducible and stays doctrine.

## Scope boundary (the shell vs. the semantics)

| Test-enforceable (the shell — DO) | NOT test-enforceable (the semantics — leave doctrine) |
|---|---|
| SESSION LOG block exists, parses, all 6 fields present | Whether the belief update is *true* |
| `Belief Update` line non-empty; if ≠"none" contains Goal:/Belief:/Action: | Whether the ROI reasoning is *sound* |
| Every finding `Evidence:` pointer resolves to a real file/line | Whether a conflict was *honestly surfaced* vs. silently resolved |
| Flipped finding has a non-empty `Reversal:` field | Whether the *right* finding was updated |
| Artifact size caps (forces consolidation) | — |

## Work items

### A. Harden #4 — convert grounding-shell mandates to tests
1. **`tests/test_session_log.py` (new)** — parse `assistant_project.md` into `📝 SESSION LOG
   ENTRY` blocks; assert each has all 6 fields (Date/Topic/Decision/Belief/Open/Next), Date is
   `YYYY-MM-DD`, and `Belief Update / ROI / Goal` is non-empty (and when ≠ "none" contains the
   `Goal:`…`Belief:`…`Action:` tokens). Mirror the parsing style of `tests/test_current_findings.py`.
2. **Evidence-resolvability** — extend `tests/test_current_findings.py`: every `Evidence:`
   that is a `path:line` or `docs/...` link must resolve (reuse the `_resolve()` helper in
   `tests/test_doc_citations.py`). Closes the gap where Evidence is *present* but dangling.
3. **Reversal-on-flip** — in `tests/test_current_findings.py`, assert any finding whose Status
   moved to SUPERSEDED/RETIRED (detected via `Supersedes:`/`Reversal:` presence) carries a
   non-empty `Reversal:` line.
4. **Commit-linkage hook (CI, not pytest)** — a pre-commit/CI check: if a commit touches
   `src/**` or `configs/production/**`, require a new SESSION LOG entry dated today with a
   non-trivial Decision/Output. Converts "every *response*" (uncheckable — responses aren't
   durable) into "every code-changing *commit*" (checkable). Deliberately ignores pure-discussion
   turns; targets the consequential ones.

### B. Bound #3 — convert "never delete" into "archive past a cap"
5. **Terminal-findings migration** — move SUPERSEDED/RETIRED findings out of
   `docs/current-findings.md` into `docs/analysis/findings-archive.md`, leaving a one-line
   tombstone + pointer in the living doc. Add a test asserting the living doc contains **no**
   terminal-status findings (they must live in the archive). Keeps §6.2 rule-4 history while
   delinting the hot path.
6. **Session-log rotation** — `scripts/maintenance/rotate_session_log.py`: keep the doctrine
   preamble + last ~20 entries in `assistant_project.md`; spill older entries to
   `docs/analysis/session-log-archive/`. Add a test capping `assistant_project.md` line count.
   Safe because durable conclusions are already distilled into findings + memory files (the log
   is forensic-replay redundant for everything else).
7. **Consolidation cadence** — wire the existing (currently-unused) `consolidate-memory` skill
   into the freshness gate: when non-terminal finding count or memory-file count crosses a
   threshold, CI emits a "consolidate" action item.

## Critical files
- `tests/test_current_findings.py` (extend: Evidence-resolve, Reversal-on-flip, no-terminal-in-living, cap)
- `tests/test_doc_citations.py` (reuse `_resolve()`)
- `tests/test_session_log.py` (new)
- `docs/current-findings.md` + new `docs/analysis/findings-archive.md`
- `assistant_project.md` + new `docs/analysis/session-log-archive/`
- `scripts/maintenance/rotate_session_log.py` (new)
- CI config / pre-commit hook for item 4

## Verification
- `pytest tests/test_session_log.py tests/test_current_findings.py tests/test_doc_citations.py -q` green.
- Deliberately corrupt a SESSION LOG block (drop the Belief field) → new test goes red.
- Deliberately leave a SUPERSEDED finding in the living doc → migration test goes red.
- Run `rotate_session_log.py` on a copy → `assistant_project.md` shrinks below cap, archive
  gains the spilled entries, no entry lost (count conserved).
- Confirm determinism per `docs/reference/testing.md` (no flakiness from date-based asserts —
  freeze "today" via a fixture).

## Non-goals / honest limits
- Does NOT make the model's beliefs *correct* — only their *form* checkable. The residual
  prosthetic-grounding fragility (semantics) is irreducible by design and stays doctrine.
- Does NOT change runtime/spine behavior; docs + tests + maintenance scripts only (additive).


================================================================================
SOURCE_FILE: docs/implementation_plan/we-have-states-defined-whimsical-penguin.md
SOURCE_BYTES: 16737
PART: 10/10 FILE 5/16
================================================================================

# SK — Structural Kernel: one governed CRT implementation, research as consumers

## Context

**The problem.** CRT state logic is not single-source. The audit below found the same
boundary-sweep predicate written **verbatim in six places**, and the F-074 directional
displacement contract written in three. Every copy's own docstring says it "mirrors
`RangeDetector.detect_sweep`'s geometry exactly" — and **nothing checks that it still
does**. When F-074 landed (2026-08-13) it had to be hand-propagated to three files. That
is the failure mode: a geometry fix is a manual broadcast, and drift is silent.

**The goal (user-set).** One governed structural implementation + configuration. Research
consumes that same implementation. When research finds something valuable, we can trace
exactly which program produced the evidence and promote it — without minting another
competing CRT implementation.

**The distinction this design turns on.** The existing "research isolation" policy
(`weekly_sweep` / `visual_crt` module docs: *"reimplement the small shared arithmetic
locally; never import the live spine"*) conflated two different independences:

| | Value | Verdict |
|---|---|---|
| **Founding independence** — *what do we call liquidity?* (a weekly calendar range, a chart-visible pool, an M15 structural range) | This is what made F-042 and F-081 legitimate NEW ontologies rather than sweeps of the incumbent. It is the only thing F-028's reopen condition ever asked for. | **Preserve, permanently** |
| **Arithmetic independence** — *how do we test "swept"?* | Bought nothing. Costs correctness: 6 copies, 1 manual broadcast per fix, 0 mechanical checks. | **Eliminate** |

The kernel unifies the arithmetic and the sequencing. The **founding stays pluggable** —
that is the whole point, and it is why this is not a loss of research freedom.

---

## Audit findings (the evidence this design rests on)

### Vocabulary — already single-source ✅
`src/config_layer/state_identity.py:43` owns `CRTState` (12) + `VALID_TRANSITIONS`.
`state_topology.py` / `state_contract.py` / `state_contract_loader.py` are re-exports.
`active_models.yaml:125` is edge-set parity-gated at every `CRTEngine()` construction
([state_contract_loader.py:139](src/config_layer/state_contract_loader.py:139)).

### Transition graph — two declarations, one un-gated ⚠️
`configs/formulas/market_crt_states.yaml:245` declares a **second** graph with no parity
test, and it already differs: `SHADOW_PENDING: [SWEEP, EXPANSION, RANGE]` vs the enum's
`[SWEEP, RANGE]`. The engine reaches EXPANSION from SHADOW_PENDING as a two-step
([crt_engine_v2.py:1057](src/config_layer/crt_engine_v2.py:1057)), so the direct edge is
plausibly a deliberate collapse — but nothing records that, so it is indistinguishable
from drift.

### The duplicated predicate — 6 verbatim copies ❌

`swept_high = high > ref and close < ref` (symmetric for low):

| # | Site |
|---|---|
| 1 | [crt_engine_v2.py:882](src/config_layer/crt_engine_v2.py:882) — `RangeDetector.detect_sweep` (**the authority**) |
| 2 | [parent_crt.py:154](src/config_layer/parent_crt.py:154) — `_detect_parent_sweep` |
| 3 | [weekly_range.py:185](src/research/weekly_sweep/weekly_range.py:185) — `detect_weekly_sweep` |
| 4 | [weekly_range.py:160](src/research/weekly_sweep/weekly_range.py:160) — `_first_sweep_this_week` (a second inline copy in the same file) |
| 5 | [visual_crt/geometry.py:93](src/research/visual_crt/geometry.py:93) — `detect_pool_sweep` |
| 6 | [crt_state_resolver.py:1068](src/features/crt_state_resolver.py:1068) — `_detect_htf_range_sweep` |

F-074 directional impulse (`long: close > open and close > sweep_price`) — 3 copies:
[crt_engine_v2 `try_sweep_to_displacement`](src/config_layer/crt_engine_v2.py:1083),
[parent_crt.py:162](src/config_layer/parent_crt.py:162),
[visual_crt/geometry.py:162](src/research/visual_crt/geometry.py:162).

### State calculators — 9 sites
Production (3): `crt_engine_v2` (M15 machine) · `parent_crt.py:150` (parent TF C1/C2/C3,
armed on `v2_htfcrt_2026_08`) · `htf_state.py:88` (`classify_htf_state`, separate enum).
Second construction (1): `crt_state_resolver.py` (1,545 lines, does **not** import
`CRTState`, YAML-driven; F-069: 88.16% agreement, EXPANSION recall 10.77%, determination
*divergent construction*).
Research re-implementations (5): `visual_crt/geometry.py`+`retest.py` ·
`weekly_sweep/weekly_range.py` · `candle_state/encoder.py` (separate vocabulary) ·
`zone_mapping/displacement_zone_event_study.py` · `regime/market_state_cluster_engine.py`.
Consumers only (~100): `backtest_v2`, `structural_event_source`, `shadow_emitter`,
`features/smc/*`, `terminals/*`, `tools/tv_forensic/*`, ~40 scripts, ~50 tests.

### Governance gap
The sweep and displacement predicates are **not registered anywhere in the ontology**.
`structural_states:` (line 2095) holds feature-vector slots (FM-054…), not these. Under
§6.6 that makes them discovered-but-undefined market semantics — registering them is the
*mandated origin* of this change, not an optional extra.

---

## Design

Four layers. Founding and thresholds are **data**; geometry and sequencing are **one
governed implementation**.

```
L3  configs/formulas/structure_profiles.yaml   ← what a program declares
      profile: founding + clock + thresholds + walk_spec + lifecycle + owner
        │
L2  src/structure/founding.py                  ← where research stays free
      RangeFounding protocol: h_ref / l_ref / formed_at_index / clock_id
      adapters: M15SLR · ParentRange · WeeklyRange · VisualPool · HTFRange
        │
L1  src/structure/walk.py                      ← one sequencing engine
      StructureWalk(spec, predicates, founding) -> events
        │
L0  src/structure/predicates.py                ← one arithmetic
      swept_boundary() · directional_impulse() · retest_band()
      pure · stateless · thresholds are parameters · no defaults
```

**L0 doctrine mirrors [`candle_math.py`](src/features/candle_math.py)** — the existing
precedent for exactly this problem (F-046: `body_ratio` computed in three places that had
to agree). Mechanism not policy; lives in code; never configurable; never `eval`'d.
Thresholds carry **no defaults** — a silent default is the config-illusion class F-056
documented, and `visual_crt/geometry.py` already enforces this convention.

**L2 is the research freedom guarantee.** A new program (the F-081 successor, say) adds a
`RangeFounding` — a new answer to *what is liquidity* — and a profile. It writes **zero**
geometry. F-028's reopen condition ("a NEW ontology, not a sweep") is satisfied by a new
founding, which is exactly what F-042 and F-081 actually were.

**L3 delivers the traceability the user asked for.** Every structural event carries
`profile_id` + `program_id` + `predicate_versions` (`src/structure/events.py`). So:

- *"which research program produced this evidence?"* → read `program_id` off the event.
- *"promote it"* → flip that profile's `lifecycle: RESEARCH → SHADOW → PRODUCTION` through
  the **existing** promotion gate. **No new code, no new implementation.** This is the
  §6.5 maturity ladder applied to structure instead of to a scalar knob.

### Two scope decisions (user-set)

- **Resolver: kernel for geometry only.** `crt_state_resolver.py` routes its predicates
  through L0 but keeps its own declarative sequencing and its own `market_crt_states.yaml`
  graph. The F-069 construction difference is **not** silently resolved — it is registered
  as an open `TruthConflict` for a separate authorized turn. Removing duplicated arithmetic
  must not smuggle in a semantic decision (§6.8: no silent remediation).
- **Kernel includes sequencing.** L1 owns the SWEEP→DISPLACEMENT→RETEST walk, so
  `crt_engine_v2.StateMachine` and `ParentCRTTrack` both become consumers of one walk
  engine driven by different specs. This is the high-value half **and** the risky half —
  it is stateful (shadow memory + TTL, EXPIRED, reset logic, sweep age, soft-confirmation,
  the parent-bias join), so it cannot be proven by a pure-function probe and is sequenced
  **last**, after L0–L3 have already banked most of the benefit.

---

## Milestones

Each is a separate authorized turn under
[`REPOSITORY_CONSTRUCTION_PROTOCOL.md`](docs/governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md)
with a BUILD_IMPACT_MANIFEST. **A milestone that cannot prove byte-identity STOPS and files
a `TruthConflict` — it never reconciles a difference silently.**

### SK-0 — Register the semantics (no behavior change, hash-neutral)
§6.6 requires the ontology to be the origin of the change, so this is genuinely first.
1. New non-frozen `structural_predicates:` section in
   [`market_ontology.yaml`](configs/formulas/market_ontology.yaml) — `SP-001 swept_boundary`,
   `SP-002 directional_impulse`, `SP-003 retest_band`. Each carries `formula`, `impl`,
   `semantics.why_it_exists`, and the 6/3 current call sites under `lineage.produced_by`.
   The frozen runtime sections (`primitives`/`feature_compositions`/`derived_metrics`) are
   untouched — new node types go in a non-frozen sibling (§6.6 constraint 1).
2. New `structural_walks:` section — walk specs as data (`crt_m15_9state`,
   `parent_crt_3candle`).
3. Add `tests/test_crt_states_yaml_transition_parity.py`: `market_crt_states.yaml` vs
   `state_identity.VALID_TRANSITIONS`, with the `SHADOW_PENDING→EXPANSION` edge as an
   **explicitly declared, commented allowance** (the two-step collapse) rather than a
   silent difference. Mirrors the gate at
   [state_contract_loader.py:139](src/config_layer/state_contract_loader.py:139).
4. Register the F-069 resolver construction difference as a `canonical_unknowns:` node with
   an `epistemic:` block (`known_invariants`: 88.16% / 10.77% EXPANSION recall;
   `unknown_mechanism`: whether the declarative EXPANSION entry is semantically equivalent;
   `resolution_metric`; `falsification_conditions`).

**Gate:** `validate_registry() == []`, ontology tests green, config hash unchanged
(non-`params` sections are hash-neutral).

### SK-1 — Predicate kernel
`src/structure/predicates.py`. All 6 sweep sites + 3 impulse sites become kernel calls.
Leaf-first order — **`weekly_range.py` → `visual_crt/geometry.py` → `parent_crt.py` →
`crt_state_resolver.py` → `crt_engine_v2.py` last** (the engine is highest-risk and moves
only once the kernel has four green migrations behind it).

**Gate per site:** (a) exhaustive differential of old vs new predicate over every bar of
every corpus the site's finding rests on — the predicates are pure, so this is decisive;
(b) byte-identical backtest ledger; (c) `feature_math_lint` green.

### SK-2 — Founding providers
`src/structure/founding.py` + 5 adapters. Pure renaming/typing of what each detector
already holds — no arithmetic moves. Byte-identical by construction; ledger diff confirms.

### SK-3 — Profiles + provenance  ← *this is the milestone that delivers the stated goal*
1. `src/structure/profile.py` + `configs/formulas/structure_profiles.yaml`. Strict
   `_require()`, no silent defaults (§6.5 hard rule). Seed profiles reproduce today's
   behavior exactly: `SP-PROF-crt-m15-live` (PRODUCTION), `SP-PROF-parent-h4`
   (PRODUCTION), `SP-PROF-weekly-fx` (RESEARCH, F-042), `SP-PROF-visual-xau`
   (RESEARCH, F-081).
2. `src/structure/events.py` — `profile_id` / `program_id` / `predicate_versions` on every
   emitted event.
3. Back-reference: each affected finding's `evidence:` block in
   [`docs/current-findings.md`](docs/current-findings.md) gains
   `structure_profile: SP-PROF-…`, so F-042/F-081 stay exactly replayable.
4. Document the promotion path in
   [`docs/reference/governance.md`](docs/reference/governance.md): promoting a research
   structure = a profile lifecycle flip through the existing `APPROVE` gate. Grants no
   authority by itself (§6.5 — authority still requires measured ΔG001).

### SK-4 — Sequencing kernel (highest risk, last)
`src/structure/walk.py`. `StateMachine` and `ParentCRTTrack` become consumers of one walk
engine. Must preserve, without behavior change: shadow memory + TTL (F-068's
`pending_displacement_created_idx` fix), EXPANSION TTL/`EXPIRED` (Phase 3b), reset logic
(`retrace_reset_pct` / `extension_reset_fib` / HTF clock), sweep age, the soft-confirmation
window (including F-067's measured-not-fixed double EMA update — **preserved as-is**, since
changing it here would be an unauthorized behavior change), and the parent-bias join at
EXECUTION (CT-009).

**Gate (all required):** byte-identical trade ledger **and** event stream on every corpus a
live finding rests on — XAUUSD, BNB/ETH/BTC/SOL, the 5 FX majors — plus the XAUUSD
freeze-pin vector SHA, `SCHEMA_HASH`, and `FEATURE_ORDER_HASH` unchanged. Any divergence
stops the milestone.

> Note on corpus scope: standing preference is XAUUSD-only for *probes*. This is not a
> probe — it is a parity gate, and its whole purpose is to cover every corpus a registered
> finding depends on. Flagging the distinction rather than assuming it.

### SK-5 — Enforcement + policy supersession
1. Extend [`scripts/analysis/feature_math_lint.py`](scripts/analysis/feature_math_lint.py)
   to structural predicates, reusing its existing `durable_key` AST-fingerprint +
   append-only retirement manifest + monotonic ratchet (the F-047 mechanism). **A new local
   re-derivation of the sweep predicate then fails CI** — competing implementations become
   mechanically impossible, not merely discouraged.
2. Add a `state_calculators:` census to
   [`crt_object_relations.yaml`](docs/governance/crt_object_relations.yaml) listing all 9
   sites with `timeframe` / `vocabulary` / `authority` / `founding`, with
   `tests/test_crt_object_relations.py` asserting exhaustiveness.
3. Mark the module-level isolation policy **SUPERSEDED** (with reason and date) in
   `weekly_sweep/weekly_range.py` and `visual_crt/geometry.py` — §6.2 rule 4, never delete.
4. Register a finding: the arithmetic-vs-founding distinction, and that F-074 required a
   3-file manual broadcast.

---

## No loss of information — four explicit guarantees

1. **Behavioral.** Nothing is replaced until the replacement is proven byte-identical on
   the corpora that matter. A divergence is a **stop condition** and a `TruthConflict`
   (§6.2 rule 3) — never a silent reconcile. SK-1's predicates are pure, so their proof is
   exhaustive rather than sampled.
2. **Evidence.** Profiles are frozen and versioned, never edited in place. F-042 and F-081
   remain replayable via their `structure_profile:` back-reference. No finding's evidence
   chain is invalidated — which is precisely why the resolver's sequencing is left alone
   (folding it in would have invalidated F-069's baseline and every parity artifact built
   on it).
3. **Knowledge.** The existing docstrings encode real decisions — F-074's rationale,
   F-072's `atr_abs`-not-`atr` warning, the pool-visibility rule, the isolation precedent.
   These migrate into the ontology nodes' `semantics:` / `epistemic:` blocks. Deleting a
   docstring without rehoming its reasoning is the intelligence loss §6.1 names.
4. **History.** The superseded isolation policy, the 6-copy census, and the F-069
   divergence are all recorded as `SUPERSEDED` / registered nodes — append-discipline, not
   removal.

## Out of scope

No change to `ACTIVE_VERSION` or any active config's `params`. No re-enabling of
`rr_fusion`. No unification of `candle_state/encoder.py` or
`market_state_cluster_engine.py` (genuinely different vocabularies, not CRT).
`msip_1_verification_package/` is a frozen verification snapshot — **must not** be
migrated. Grants no production or G001 authority (§6.5).

## Verification

Per milestone:

```bash
python -m pytest tests/test_crt_object_relations.py tests/test_state_contracts.py tests/test_crt_state_invariants.py tests/test_state_topology_phase.py tests/test_crt_executable_state_graph.py tests/test_crt_adversarial_closure.py tests/test_directional_displacement.py tests/research/test_weekly_sweep.py tests/research/test_visual_crt_trade_object.py tests/test_parent_crt_track.py -q
```

```bash
python scripts/analysis/feature_math_lint.py && python scripts/governance/construction_protocol.py check
```

Byte-identity gate (SK-1 / SK-2 / SK-4) — XAUUSD ledger + freeze-pin vector SHA:

```bash
python -m src.runtime.backtest_v2 --instrument XAUUSD --data-dir data/mt5 --emit-ledger
```

Grounding for every new noun introduced (§6.7):

```bash
python scripts/governance/query_semantic_os.py --ground --kind NOUN --token SP-001
```


================================================================================
SOURCE_FILE: docs/implementation_plan/we-need-to-commit-reactive-quilt.md
SOURCE_BYTES: 6798
PART: 10/10 FILE 6/16
================================================================================

# Plan: Commit all pending work, clean working tree (commits only, no code edits)

## Context
`git status` currently shows 13 modified tracked files and ~450 untracked
paths on `feature/truth-registry-v2` (a mix of real work-in-progress: new
`src/`/`tests/` modules, research packages, reports, docs, the `multi_llm/`
coordination layer, plus some scratch/junk that accumulated alongside it).
The user wants the tree brought to a clean state (`git status` empty) purely
through `git add`/`git commit` — no file content should be rewritten, no
refactors, no SITS registration workflow. This continues the same restoration
pattern already visible in recent history (`9b1b5ed`…`8696844`, "B2"–"B5 of
tree-restoration").

Two exceptions were explicitly approved by the user (not "code," but small,
necessary deviations to avoid an unsafe commit):
1. Delete 2 corrupted, unreadable-named files left over from a broken
   terminal command (0 bytes / 1.7KB, not real content).
2. Fix a one-line `.gitignore` typo (`models\` → `models/`) so the existing
   ignore intent for the 459MB `models/` artifact tree actually works —
   without committing `models/` itself.

## Excluded from any commit (left untracked, per user decision)
- `models/` (459MB trained-model binaries/checkpoints) — gitignore fixed so
  it's ignored going forward.
- `docs (2).zip`, `docs (3).zip`, `scripts (2).zip`,
  `bundles/who_how_what_bundle.zip` (duplicate/regenerable exports, ~6.5MB).
- `terminals/`, `agent-tools/` (session/tool-call scratch logs).
- **Proposed, flagging for review:** `xauusd_backtest_run/` (9MB generated
  backtest run output — JSONL/CSV/txt) is the same category as `models/`
  (regenerable artifact tree, not source). Recommend excluding it too,
  leaving it untracked, unless you want it committed — will confirm during
  execution if you'd rather include it.

## Pre-flight (safety, read-only)
- `.env` already confirmed properly gitignored (`git check-ignore -v .env`
  → matched `.gitignore:9`). No secret files appear in the untracked list.
- Before staging, grep the untracked set for obvious secret patterns
  (`api_key`, `BEGIN PRIVATE KEY`, `AKIA`, `sk-`, `ghp_`, `xox[bp]-`) as a
  final check — per repo's git-safety convention of reviewing anything
  suspicious before it's committed.

## Commit sequence
All commits keep file **content** byte-identical to what's on disk today —
each is `git add <paths>` + `git commit` only. Grouped thematically,
extending the existing "N of tree-restoration" commit-message convention:

1. **`chore: remove corrupted debug artifacts from a broken terminal command`**
   — `rm` the 2 garbled-name files, commit the deletion.
2. **`fix(gitignore): correct models/ ignore pattern (models\ -> models/)`**
   — the one approved config edit.
3. **`chore(tree): commit modified tracked files (B6 of tree-restoration)`**
   — the 13 `M` files (`assistant_project.md`, `configs/formulas/market_ontology.yaml`,
   `docs/book/encyclopedia/E1b-features-registry.md`, two
   `docs/governance/SEMANTIC_OS_*` files, `docs/governance/model_paths_literal_debt.json`,
   two `scripts/research/xauusd_episode_*` files, `src/bitnet/bitnet_registry.py`,
   `src/engines/live_engine.py`, `src/features/feature_states.py`,
   `src/features/market_context.py`, `tests/test_feature_states.py`).
4. **`feat(tree): commit new src/tests modules (B7 of tree-restoration)`**
   — `src/features/magnitude_states.py`, `src/research/episode_agreement.py`,
   `src/research/episode_propositions.py`, `ui_kits/control_plane/ExplorerPanel.jsx`,
   `mt5_analytics/evaluate_bar_features_outcome.py`, and their matching
   `tests/test_*.py`.
5. **`chore(tree): commit root-level analysis scripts + census outputs (B8 of tree-restoration)`**
   — root `_*.py` probes, `audit.py`, `count_audit_tmp.py`, the census
   `*.csv`/`*.jsonl`/`*.json` files, `codebase-atlas-explorer.html`,
   `codebase_explorer.html`, `flow_context/telemetry.json`, `flow_graphs/telemetry.dot`.
6. **`docs(tree): commit root-level and governance docs (B9 of tree-restoration)`**
   — root planning/analysis `*.md`/`*.txt` (`AMBIGUITY_REPORT.md`,
   `HANDOFF.md`, `MASTER_ARCHITECTURE_REFERENCE.md`, the `ZONE-X-*.md` set,
   `YAML_CONSUMER_AUDIT_*.md`, etc.), `docs/governance/EPISODE_SEMANTIC_INTEGRATION_PHASE2.md`
   + `docs/governance/build_manifests/*`.
7. **`docs(tree): commit research reports (B10 of tree-restoration)`**
   — the full `reports/` tree (incl. `reports/parity_experiment/`, `reports/research/`, `reports/analysis/`).
8. **`chore(tree): commit research packages (B11 of tree-restoration)`**
   — `research/H-G001-001*`, `H-SECONDLOW-002_Complete_Package/`,
   `msip_1_verification_package/`.
9. **`chore(tree): commit multi-LLM coordination layer (B12 of tree-restoration)`**
   — `multi_llm/` (README, protocol, roles, research_lane, build_queue.jsonl,
   console.html), `llm_project_assistant.md`.
10. **`chore(tree): commit ChatGpt workflow library + grok exports (B13 of tree-restoration)`**
    — `ChatGpt  workflow/` (docx/html prompt library), `grok/` (PDFs, xlsx,
    scripts), plus root reference binaries `CRTClaude.pdf`, `Claude20day.pdf`,
    `DOC_TRACKING_INDEX.xlsx`, `scripts_business_functionality.xlsx`,
    `SujanTraderCRTExp.txt`, `DesignPlan1.txt`, `GrokCRTStatesAnalysis.md`.
11. **`chore(tree): commit scratch run logs (B14 of tree-restoration)`**
    — `pytest_full_run.log`, `pytest_output.txt`, `xauusd_backtest_console.txt`,
    `logs_phase1_run1_tmp.txt`, `fallback_sweep_after_b1.txt`,
    `fallback_sweep_before.txt`, `.fallback_after_b1_failures.txt`,
    `.fallback_before_failures.txt`, `knowledge_graph.json`.
12. **`docs: append SESSION LOG entry for tree-cleanup commits`** — per
    CLAUDE.md §6 (non-optional persistent logging mandate), append one
    `📝 SESSION LOG ENTRY` block to `assistant_project.md` summarizing this
    cleanup (this is a log append, not a code change).

After each commit, verify with `git status --short` that the expected paths
moved from `??`/`M` to committed. Final check: `git status` should be empty
except for the intentionally-excluded paths above (`models/`, the zips,
`terminals/`, `agent-tools/`, and `xauusd_backtest_run/` if still excluded).

## Verification
- `git log --oneline -15` shows the new commits in order.
- `git status --porcelain -uall` at the end shows only the deliberately
  excluded paths (or is fully empty if you'd rather include
  `xauusd_backtest_run/` too — flag during execution).
- `git show --stat` on commit 2 confirms only `.gitignore` changed, one line.
- No file's content differs from its pre-commit working-tree state (this
  plan performs zero rewrites other than the one approved `.gitignore` line
  and the two approved deletions).


================================================================================
SOURCE_FILE: docs/implementation_plan/which-model-best-wokrs-atomic-church.md
SOURCE_BYTES: 14419
PART: 10/10 FILE 7/16
================================================================================

# Research Provenance Spine — making the LLM→config pipeline mechanically governed

## Context

The requested pipeline already exists in this repo as ~70% built parts, joined by **prose,
not by types**:

```
OHLCV → Deterministic Semantic Features → LLM Knowledge Layer → Semantic Observations
     → Hypothesis Generator → Research Validation → Qualified Strategy Rule → Production Config
```

Feature derivation (ontology → registry → `candle_math`/`derived_math`) and Research
Validation (the M4 gate, `forward_walk`, `metrics_oracle`) are built. Promotion
(`ConfigValidator` → `PromotionManager` → `promotion_log.jsonl`) is a real write-authority
gate. What is missing is the **connective tissue**.

**The binding reason to build this now: the codebase is under active bug-fix.** Every fix
silently invalidates every result produced before it, and *nothing in the repo records that
this happened*. There is no artifact that answers "was this result produced before or after
the fix?" — so results accumulate at an unknown and undeclared level of trust.

Three source-verified symptoms (read this session, not quoted from findings):

1. **Results are not stack-pinned.** `baseline_capture.build_manifest()` records the schema
   hash, config sha256 and two model families — no ontology, no `active_models.yaml`, no
   composite identity. Backtest run records carry no stack identity at all.
2. **`baseline_capture.py:100` hashes the wrong file** — `models/zone_registry.json` while
   the active config's `zone_registry_path` is `models/zone_registry_v4_2026_07.json`. It
   pins the rollback artifact, not what loads. A concrete instance of the general problem.
3. **The trust ladder is ritual, not structure.** §6.5's Authority Ladder and E-001's
   pre-registration check are enforced by discipline. Nothing structurally prevents an
   unvalidated claim from being cited as evidence.

**Intended outcome:** authority becomes a *positional* property of a record's place in an
append-only chain, not a claim any record can make about itself — and every bug fix becomes
a recorded epoch boundary rather than a silent one.

### Standing constraint — findings are UNTRUSTED input

Per user direction: the existing findings corpus (F-019…F-061) is treated as **possibly
bug-contaminated** and is **not** a design premise, evidence, or justification anywhere in
this plan. It is a *subject* of this system, never an input to it. Findings triage —
deciding which conclusions survive — is explicitly **deferred until the code is built and
reviewed**. This plan does not read, cite, revalidate, or flip a single finding.

Corollary that makes this safe to operate *during* the bug-fix period: because a `PROMOTE`
verdict from a superseded `stack_epoch` cannot promote (invariant 3 below), any
observation or validation run minted against buggy code **auto-expires** when the fix bumps
the epoch. Contamination cannot leak into production by age.

---

## The structural idea

> **Authority is positional, not asserted.**

An observation is structurally incapable of reaching `configs/production/` — not by policy,
but because each stage can only be minted from the prior stage's id:

| Stage | Record | Minted from | Authority |
|---|---|---|---|
| Semantic Observation | `OBSERVATION` | nothing (LLM output) | `NONE` — hard-coded |
| Hypothesis | `HYPOTHESIS` | ≥1 `observation_id`; freezes a `preregistration_hash` | `NONE` |
| Research Validation | `VALIDATION_RUN` | one `hypothesis_id` whose prereg hash still matches | evidence only |
| Qualified Rule | `QUALIFIED_RULE` | ≥1 run with `verdict == PROMOTE` at the *current* `stack_epoch` | may propose a config delta |
| Production | existing `promotion_log.jsonl` | one `rule_id` | write authority |

Same shape as `src/journal/`'s tier split (permanent identity vs. churning detail) and
`production_bundle.py`'s conservative-on-conflict rule — reuse the pattern, don't invent one.

**Four refusal invariants** — this is what "harden" means concretely:

1. `PromotionManager` accepts a `rule_id`, never a run/hypothesis/observation id.
2. A run whose `hypothesis.preregistration_hash` no longer matches is dead — the spec was
   edited after the result (anti-p-hacking, currently ritual-only).
3. A `PROMOTE` verdict from a **superseded `stack_epoch`** cannot promote. This is the
   invariant that makes the system safe to run on a codebase still being fixed.
4. A rule's `config_delta` may only touch keys classified BEHAVIORAL by
   `scripts/analysis/behavior_census.py` (§6.5). Research can tune thresholds; it can never
   restructure the engine.

---

## Phase 0 — Stack identity (prerequisite for everything else)

New: `src/config_layer/stack_version.py` — sibling of `production_bundle.py`, read-only,
`authority: NONE` in its meta.

**`behavior_hash`** — only inputs that can move a trade ledger:
1. HOW — `ACTIVE_VERSION` + **sha256 of the whole config file** (the in-file `config_hash`
   covers `params` only; new top-level sections are hash-neutral per §6.5).
2. WHAT — digest over frozen runtime sections (`primitives`, `feature_compositions`,
   `derived_metrics`, `rolling_indicators`) taking only
   `{id, version, lifecycle, formula, impl, numerator, denominator, clip, active}`.
   Excluding `taxonomy`/`semantics`/`lineage`/`notes` is what buys churn-free versioning.
3. EXECUTION — `SCHEMA_VERSION` + `CANONICAL_FEATURE_DIM` + `SCHEMA_HASH`, **plus sha256 of
   `candle_math.py` and `derived_math.py` sources**. Required: `SCHEMA_HASH` is md5 over
   joined feature *names* (`feature_schema.py:178`) and is blind to a formula change — which
   is exactly the bug-fix case this plan exists to catch.
4. WHO-enabled — only families where `BundleMember.executes_checkpoint` is True:
   `(family, selected_version, artifact_sha256)`. A disabled family cannot move a ledger.

**`provenance_hash`** — the above plus full-file sha256 of `market_ontology.yaml` and
`active_models.yaml`, ontology `version` + `spec_schema.semantic_registry.version`,
`meta.schema_version`, `state_contract_schema_version`, **all** families with their
`execution_status`, every model-registry sha256, `ProductionBundle.divergences`, and git SHA
**explicitly flagged unreliable** (the working tree structurally diverges from HEAD — a bare
git SHA is a false pin; verify tree state at implementation time).

Reuse, don't rebuild: `load_production_bundle()` already reconciles Selected vs Enabled
across all 6 families and already withholds `executes_checkpoint` on conflict. The
"checklist per version (CRT / zone / RR / TradeNet / trained models)" **is**
`ProductionBundle.executing_families()` — it exists.

**Epoch ledger** — `configs/stack_epoch_log.jsonl`, append-only, `promotion_log.jsonl`
discipline. `stack_epoch` increments only on a previously-unseen `behavior_hash`; a
provenance-only change appends `kind: "STACK_PROVENANCE"` against the current epoch. Never
rewrite a line (§6.2 rule 4). **Every bug fix that changes executed math produces a new
epoch — that is the point.**

**Also fix here:** the `baseline_capture.py:100` zone-registry path bug, and replace its 3
hardcoded registry hashes + 2-family `get_active*` calls by delegating to
`load_production_bundle()`.

---

## Phase 1 — Stamp results and analysis (the actual "harden" ask)

Every artifact under `results/` and every research driver run emits a `VALIDATION_RUN`
record. Additive; **must be parity-proven byte-identical** on the ledger (the module is
read-only, so any diff means an import side-effect).

```
{"kind":"VALIDATION_RUN","run_id","hypothesis_id"|null,"stack_epoch","behavior_hash",
 "dataset_fingerprint","ledger_path","ledger_sha256","gate_spec",
 "metrics":{...from metrics_oracle...},"verdict":"PROMOTE|REJECT|INSUFFICIENT",
 "authority":"evidence_only","timestamp"}
```

`hypothesis_id` is nullable so **existing** drivers can be stamped immediately without
waiting on Phase 2. `dataset_fingerprint` must record *which* `dataset_integrity` layers
actually ran (L1/L2/L3 coverage is not uniform across entry points — verify call sites at
implementation time), never assert all three.

**Payoff from this phase onward:** results produced before and after any given bug fix become
mechanically distinguishable. No retroactive claim is made about existing results — they
simply carry no epoch, which is itself the honest answer. Triage of the historical corpus is
**out of scope until the code is built and reviewed**.

---

## Phase 2 — Observation and hypothesis ledgers

```
OBSERVATION  {observation_id, stack_epoch, feature_scope:[FM-0NN...], instrument_scope,
              timeframe, claim, falsification_condition (REQUIRED), generated_by,
              prompt_hash, authority:"NONE", status:"UNVALIDATED"}
HYPOTHESIS   {hypothesis_id, observation_ids:[...], interpreter_spec, gate_spec,
              preregistration_hash, frozen_at, authority:"NONE"}
```

`falsification_condition` is non-nullable — §6.6's epistemic block made a schema constraint
instead of a ritual. `interpreter_spec` compiles to the existing Level-4 Interpreter Contract
so a hypothesis runs through the unchanged M4 gate; **confirm that API shape before
implementing** — it was not re-read this session.

**Storage location decision:** these are PRIMARY records (not regenerable, not runtime
noise), so they cannot live under gitignored `data/`. Proposed: a tracked `research_ledger/`
at repo root, sibling in discipline to `configs/promotion_log.jsonl`. Verify against
`.gitignore` before creating.

---

## Phase 3 — The promotion gate (first write-authority change)

`PromotionManager.promote_from_qualified_rule(rule_id, version)` enforcing the four refusal
invariants. Requires user approval per §6.2 — it changes the only path to production.

---

## Phase 4 — The Claude-as-observer protocol

"Pure Claude coding agent" is read here as: **the LLM Knowledge Layer is a governed protocol,
not a new service.** No LLM microservice, no new runtime dependency — consistent with
CLAUDE.md §4 ("LLM is a tie-breaker, not a hot-path dependency") and `agent/`'s deterministic
`PLAN_REGISTRY` design.

Deliverable: a skill + output contract that makes a Claude session emit valid `OBSERVATION`
records from deterministic feature evidence — required `feature_scope` in FM ids, required
falsification condition, `authority: NONE` stamped structurally. The vocabulary for market
narratives already exists in `configs/research/market_story_ontology.yaml` +
`src/research/synthetic/`; reuse it rather than inventing a parallel one.

Placed last for dependency reasons only (it needs the ledgers to write into). It is *not*
blocked on the codebase being bug-free — invariant 3 makes observations minted against buggy
code expire on their own.

*Alternative if a scripted generator is preferred:* route through the existing
`llm_inference_client` (already fails to neutral 1.0 after `fail_count_disable`). Costlier,
and adds a runtime dependency the repo has deliberately avoided.

---

## Files

| File | Change |
|---|---|
| `src/config_layer/stack_version.py` | NEW — `compute_stack_version()`, `resolve_epoch()`, `append_epoch_record()` |
| `src/config_layer/production_bundle.py` | additive helper only; no logic change |
| `src/runtime/baseline_capture.py` | delegate to bundle; **fix** the zone-registry path bug |
| `src/runtime/backtest_v2.py` | stamp `stack_epoch` + `behavior_hash` on the run record |
| `src/governance/promotion_manager.py` | Phase 3 — `promote_from_qualified_rule` + 4 invariants |
| `configs/stack_epoch_log.jsonl` | NEW append-only |
| `research_ledger/*.jsonl` | NEW append-only (location to confirm vs `.gitignore`) |
| `docs/reference/schemas.md` §9 | document all 5 line shapes |
| `docs/knowledge-map.md` | record the chain (§6.2 rule 1 — update the doc that owns the topic) |

## Tests (floors)

`tests/test_stack_version.py`
1. **Determinism** — two calls, unchanged inputs, identical `behavior_hash`.
2. **Churn guarantee** — editing `semantics`/`notes`/`taxonomy` moves `provenance_hash`,
   leaves `behavior_hash` byte-identical.
3. **Sensitivity** — an ACTIVE formula, a `params` value, or an *enabled* artifact does move
   it. Includes the bug-fix case: change a `derived_math` function body, assert the hash moves.
4. **Inert-model insensitivity** — mutating a non-executing family does not.
5. **Ledger** — append-only, monotonic epoch, provenance-only change does not increment.

`tests/test_research_provenance.py`
6. **Positional authority** — an observation/hypothesis/run id passed to `PromotionManager` is refused.
7. **Pre-registration immutability** — editing a hypothesis post-run invalidates the chain.
8. **Stale epoch refused** — a `PROMOTE` from a superseded epoch cannot promote.
9. **Behavioral-only delta** — a rule touching a STRUCTURAL key is refused.
10. **Append-only** — no line rewrite in any ledger.

## Verification

1. `pytest tests/test_stack_version.py tests/test_research_provenance.py -v`.
2. Compute on HEAD, re-run after only a `notes:` edit in `market_ontology.yaml` — assert
   epoch unchanged, provenance changed. Then edit a `derived_math` body — assert epoch moves.
3. **Parity proof**: XAUUSD freeze-pin backtest byte-identical before/after Phases 0–1.
   Known caveat: byte-identity only covers exercised paths and XAUUSD yields 0 trades on the
   freeze slice — also run BNBUSDT gate-ON.
4. `python src/runtime/baseline_capture.py --label stackver` — confirm the manifest carries
   the ontology, the WHO layer, all 6 families, and the **v4** zone registry.
5. Existing floors green: `test_active_models_registry.py`, `test_feature_lineage.py`,
   `test_doc_citations.py`.

## Open — surfaced, deliberately not resolved (§6.2 rule 3)

`active_models.yaml` `gaussian.identity.runtime_binding.compatibility.feature_schema_dim: 38`
vs `feature_schema.py` `CANONICAL_FEATURE_DIM = 39` / `SCHEMA_VERSION = "4.0"`. Both values
read directly from source this session — this is a file-vs-file disagreement, not a finding.
Exactly the drift class `stack_version` exists to surface, so it is a motivating exhibit, but
resolving it needs a user decision (does 38 mean the scored subset, as zone_gate's
`scored_dims: 38` does, or is it stale post-v4?). Not touched by this plan.


================================================================================
SOURCE_FILE: docs/implementation_plan/wlak-me-thorugh-grok-ticklish-axolotl.md
SOURCE_BYTES: 8122
PART: 10/10 FILE 8/16
================================================================================

# Certify the live decision rail against deterministic historical replay

## Context

The paper TickDB run at 17:27 ended `closed_bars=80 process_calls=0`, with two `FEATURE_REJECT`
records in `logs/live_rail.jsonl`. The working hypothesis was that the feeder cannot construct the
canonical feature surface. **That hypothesis is wrong, and the real cause is located.**

What actually happened, traced through source:

1. The feeder worked. `FeaturePipeline` ran (`rows_before=80 rows_after=2 drop=78`), `ready()`
   returned True, `as_trade_data()` passed its own 48-key completeness check.
2. `hook.process(...)` **was called** — twice. `LiveRailOrchestrator.process_calls` increments
   *after* the call (`live_rail_orchestrator.py:213`), so an exception inside makes a real call
   invisible. `process_calls=0` under-reports; it does not mean "never reached".
3. The exception came from `filter_canonical_inputs` in
   [`src/engines/zone_gate_engine.py:164-166`](src/engines/zone_gate_engine.py:164) — ZoneGate got
   19 of the 48 canonical keys.
4. **Root cause:** [`live_engine_hook.py:279`](src/runtime/live_engine_hook.py:279) declares
   `global _ENGINE_CONFIG_CACHE, _feature_monitor` — **`_feature_store` is not in that list**, yet
   line 394 assigns `_feature_store = FeatureStore(...)` inside the same function. That assignment
   binds a function-local and is discarded. The module global (line 92) stays `None` forever, so the
   guard at line 817 never fires and `engine_input` remains the reduced `_build_engine_input()` dict.

The canonical ingestion boundary therefore **never runs on the live path**. The T-11 comment at
lines 809-816 ("a validation failure must REJECT the tick, never downgrade it") hardened the
exception path in 2026-07-19; the block it protects is unreachable. Skipped validation is
indistinguishable from absent validation — the same silent-gap class as F-079 / F-056 / F-083.

§6.8 classification: **CONFIRMED DEFECT** (violated contract: FeatureStore's documented role as the
canonical ingestion boundary + the T-11 fail-closed intent).

Scope guard: F-073 means there is no production live loop, so this bites the paper rail only. No
production-loss claim. Backtests use a different path and are unaffected.

Two corrections to carry into the work:
- The canonical surface is **48** features (schema v5.0, F-076), not 39. Two docstrings still say
  39 — `feature_pipeline.build_features` (:375) and `live_engine_hook` (:378). DOC_DRIFT, fix in the
  same turn as the code (§6.2 rule 6).
- The run log shows `pip_value_per_lot missing for XAUUSD → defaulting to 10.0 USD`. That is a
  silent config default on a capital-sizing input (§6.5 forbids it). Record it; do not fix here.

## Approach

A fail-forward certification, not a single bug fix: each replay run exposes the next seam. The
harness must make each seam legible and distinct, which is why instrumentation comes first.

### Phase 0 — Make the instrument honest (no behavior change)

Without this, the certification cannot tell "never called" from "called and threw".

- `live_rail_orchestrator.py`: split the two `_audit` sites that both emit `FEATURE_REJECT` —
  `:199` (feeder could not build features) becomes `FEEDER_REJECT`; `:215` (the engine raised)
  becomes `ENGINE_ERROR`, carrying the exception type and the raising module.
- Add `process_attempts` alongside `process_calls`; increment it *before* the call.
- Isolate run artifacts: `--report-dir results/live_rail_cert/<run_id>/` instead of appending to
  the shared `logs/live_rail.jsonl`. Confirm `UltronRiskGate` cannot write
  `logs/kill_switch_state.json` during a paper run; if it can, point it at the run dir.
- Update `tests/test_live_rail_orchestrator.py:242,268`, which assert on the old `FEATURE_REJECT`
  string.

### Phase 1 — Historical replay source, two arms

Reuse what exists rather than adding a venue. Use `data/mt5/XAUUSD_M15.csv` (XAUUSD only, per
standing instruction).

- **Arm A — bar injection.** `LiveRailOrchestrator.run_until_bar_queue_empty()` +
  `ingest_closed_bar()` already exist for exactly this. Feed `ClosedBar` objects straight from the
  CSV. This isolates the feature→decision seam with `BarBuilder` out of the picture.
- **Arm B — tick replay.** A new `OhlcvTickReplayPort` implementing `MarketDataPort`, expanding each
  M15 bar into ticks in O→H→L→C order so `BarBuilder` reconstructs it. **Binding assertion:** the
  rebuilt bar must equal the source bar exactly; if it does not, the arm is testing a fiction and
  must fail, not warn.

Arm A is the primary certification path; Arm B additionally certifies `BarBuilder`.

### Phase 2 — Fix the singleton (the actual defect)

Add `_feature_store` to the `global` declaration at `live_engine_hook.py:279`. Then make the skip
impossible to reintroduce silently: when `_STORE_AVAILABLE` is true but `_feature_store` is `None`
at line 817, **raise** rather than falling through to the reduced dict.

This is behavior-changing on the live path by construction — it makes validation stricter, on a rail
with no production caller. It needs a BUILD_IMPACT_MANIFEST (`CH-live-rail-cert-replay`) per §3.3b,
and a grep proving no other module reads `_feature_store`.

### Phase 3 — Walk the remaining seams

Pre-registered prediction, to be recorded before the run: `_build_ohlcv_and_auxiliary` documents
auxiliary as "all remaining CANONICAL_FEATURES … every one is MANDATORY", and the feeder already
supplies all 48, so Phase 2 alone may carry a bar through to a decision. If a further seam raises,
record it as its own row and fix one at a time — never widen a contract to make a run pass.

### Phase 4 — Certification criteria

A run certifies only if all of these hold:

- `process_attempts == process_calls` and `process_calls > 0`
- every bar past warmup produces exactly one terminal record (`NO_ORDER`, `FILL`, `PREFLIGHT_REJECT`)
- `FEEDER_REJECT == 0` and `ENGINE_ERROR == 0`
- zero orders: `hook_submit_orders=false`, `dry_run=true`, MT5 `send_order` and Telegram send counts
  both 0
- **determinism**: the same corpus slice replayed twice yields byte-identical audit records once
  wall-clock `ts` is excluded

## Critical files

| File | Change |
|---|---|
| [`src/runtime/live_engine_hook.py`](src/runtime/live_engine_hook.py) | `:279` global fix · `:817` fail-closed on None · `:378` docstring 39→48 |
| [`src/runtime/live_rail_orchestrator.py`](src/runtime/live_rail_orchestrator.py) | split reject kinds, `process_attempts`, report-dir |
| `src/inout/live_rail/ohlcv_replay_port.py` | new — Arm B port, round-trip assertion |
| `scripts/live/run_live_rail.py` | `--corpus` / `--arm {bars,ticks}` / `--report-dir`; SITS-register |
| [`src/features/feature_pipeline.py`](src/features/feature_pipeline.py) | `:375` docstring 39→48 |
| `tests/test_live_rail_orchestrator.py` | update the two reject-kind assertions |
| `tests/test_live_rail_replay_cert.py` | new — Phase 4 criteria incl. the determinism pair |

Reuse, do not rebuild: `LiveRailFeeder` (the only feature builder — do not add a third),
`run_until_bar_queue_empty` / `ingest_closed_bar`, `CandleLoader` for the CSV, `BarBuilder`,
`PaperVenueExecutor`.

## Verification

```bash
venv/Scripts/python.exe -m pytest tests/test_live_rail_orchestrator.py tests/test_live_rail_feeder.py tests/test_live_rail_replay_cert.py -q
```

```bash
LIVE_ENGINE_ENABLED=1 venv/Scripts/python.exe scripts/live/run_live_rail.py --paper --arm bars --corpus data/mt5/XAUUSD_M15.csv --limit 500 --report-dir results/live_rail_cert/run1
```

Then re-run into `run2` and diff the two audit files with `ts` stripped — they must be identical.
Confirm `git status` shows no change to `configs/production/ACTIVE_VERSION`, and that the run wrote
nothing outside `results/live_rail_cert/`.

## Out of scope

No live venue, no `dry_run=false`, no `ACTIVE_VERSION` edit, no promotion, no G001 or economic
claim. This is replay/integration certification; F-073 stays OPEN until a production loop exists,
and F-010 stays OPEN because this rail still has no exit loop.


================================================================================
SOURCE_FILE: docs/implementation_plan/xauusd-gaussian-toward-economics-2026-07-23.md
SOURCE_BYTES: 16739
PART: 10/10 FILE 9/16
================================================================================

# Design: XAUUSD Gaussian — From Registry Promote to Economics

**Date:** 2026-07-23  
**Status:** DESIGN — **E0 + E1 + E2 IMPLEMENTED**; **xau_metals_protocol_v1 EXECUTED** (20260722T211010Z, n_perm=200 CLI; primary INSUFFICIENT; no economic authority)  
**Authority:** Grants **no** production wire, **no** `gaussian_impl=ml`, **no** G001 claim until Phase E passes  
**Primary artifact (today):** `xauusd_nb_20260722T194904Z`  
**Semantic journal:** `results/gaussian_xauusd_train/gaussian_xauusd_train_20260722T194904Z/bar_semantic_journal.jsonl`  
**Hashes:** `results/gaussian_xauusd_train/HASHES_AND_CLOSURE.json`

---

## 0. Problem statement (why we are not economic yet)

| What we have | What economics requires |
|---|---|
| Registry **Promoted: Yes** (XAUUSD active pointer) | **ΔG001 / book E[R] / PF** under governing exit |
| Labels from **CRT SWEEP** + fixed 1R/1R `forward_walk` | Entries that map to a **decision consumer** (or pre-registered candidate set) |
| mean labeled `y_rr` ≈ **−1.06 R** (journal) | Net expectancy ≥ 0 OOS, beats controls, M4 gates |
| Score surface on 2m bars (mean ~0.62) | **Conditional** economics: high-score vs low-score units |
| Live `gaussian_impl=heuristic` | Optional later: shadow ML consumer A/B (still not authority until ΔG001) |

**Authority Ladder (non-negotiable):**

```text
Information (corr, scores)
    → Economic usefulness (measured NET E[R], PF, ΔG001 vs control)
        → Authority (allowed to influence production)
            → Architecture (complexity justified)
```

Today we sit at **Information + registry hygiene**. This design moves to **Economic usefulness measurement**. Authority is a later, evidence-gated decision.

---

## 1. North star (one sentence)

**Build a pre-registered, journal-grounded measurement chain that answers: does the XAUUSD Gaussian NB improve selection economics vs controls under `forward_walk(intrabar_fixed)+cost`, and only then discuss production authority.**

---

## 2. Design principles

1. **Reuse existing gates** — M4 `QualificationGate` (`src/research/qualification.py`); do not invent a parallel promote standard.  
2. **Reuse existing shadow eval** — `scripts/research/build_gaussian_family_shadow_eval.py` already supports XAUUSD + `candidate-mode` + econ stride.  
3. **Journal is the entry ontology** — every candidate must be reconcilable to `bar_semantic.v1` kinds (`SWEEP_CANDIDATE`, `LABEL_ACCEPTED`, `HOLDOUT`).  
4. **Holdout discipline** — train already excluded trailing 2m (`HOLDOUT` in journal); economics OOS must respect chronology.  
5. **Config-first consumer knobs** — any threshold on NB score is config-declared if it ever influences a path; research scripts may use explicit CLI first.  
6. **No silent live flip** — `gaussian_impl` stays `heuristic` until a separate, measured shadow → optional config PR.  
7. **Negative results are success** — 0 PROMOTE is a valid closed experiment (per qualification module doctrine).

---

## 3. Enhancement architecture (layers)

```text
┌─────────────────────────────────────────────────────────────┐
│  E3  Authority decision (OPTIONAL, human + ΔG001)           │
│      promote consumer / gaussian_impl=ml|shadow_ml          │
└──────────────────────────▲──────────────────────────────────┘
                           │ only if E2 PROMOTE + ΔG001
┌──────────────────────────┴──────────────────────────────────┐
│  E2  M4 QualificationGate on score-conditioned candidates   │
│      PROMOTE | REJECT | INSUFFICIENT                        │
└──────────────────────────▲──────────────────────────────────┘
                           │ outcomes + controls
┌──────────────────────────┴──────────────────────────────────┐
│  E1  Economic measurement harness (NET R ledger)            │
│      high-score / low-score / random / long-only controls   │
│      forward_walk + CostModel (same as M4)                  │
└──────────────────────────▲──────────────────────────────────┘
                           │ candidates + scores
┌──────────────────────────┴──────────────────────────────────┐
│  E0  Candidate + score layer (journal-aligned)              │
│      SWEEP units from journal OR re-stream with same codes  │
│      score via promoted XAUUSD NB (name-anchored 39-dim)    │
└─────────────────────────────────────────────────────────────┘
         ▲
┌────────┴────────┐
│ bar_semantic.v1 │  already closed (label_build proof)
└─────────────────┘
```

---

## 4. Phase plan

### Phase E0 — Candidate + score contract (1–2 days)

**Goal:** Deterministic table: one row per economic unit with features, NB score, direction, bar_index, train/holdout flag.

| Field | Source |
|---|---|
| `bar_index`, `timestamp`, `direction` | Journal `LABEL_ACCEPTED` / `SWEEP_CANDIDATE` or CRT re-stream |
| `split` | `train` if ts < holdout_start else `oos` (match journal HOLDOUT) |
| `score`, `expected_rr` | `load_gaussian_model(xauusd_nb_…194904Z)` name-anchored |
| `reason_code_origin` | journal lineage for LLM explain |

**Deliverables:**

- `scripts/research/xauusd_gaussian_econ_units.py`  
  - Input: Phase-1 corpus + model version + journal path  
  - Output: `results/gaussian_xauusd_econ/units_<ts>.jsonl` + manifest with hashes  
- Unit tests: holdout boundary matches journal `HOLDOUT` count (~267); score dim = 39  

**Exit:** N_train + N_oos units with scores; no economics yet.

**Reuse:** Journal already encodes accept/holdout; avoid redefining entry mid-flight.

**E0 SHIPPED (2026-07-23):**

| Item | Path / value |
|---|---|
| Script | `scripts/research/xauusd_gaussian_econ_units.py` |
| Tests | `tests/test_xauusd_gaussian_econ_units_e0.py` (4 passed) |
| Units | `results/gaussian_xauusd_econ/units_LATEST.jsonl` (n=3247 = 2980 train + 267 oos) |
| Manifest | `results/gaussian_xauusd_econ/e0_manifest_LATEST.json` |
| Pins | HOLDOUT=267, LABEL_ACCEPTED=2980, dim=39, score fails=0 |
| Authority | still RESEARCH_ONLY / no E1 economics |

---

### Phase E1 — Economic ledger (2–3 days)

**Goal:** Net R for each unit under **governing** exit (same family as train labels, but report economics honestly).

| Choice | Default | Rationale |
|---|---|---|
| Exit | `intrabar_fixed` | Governing research truth |
| Cost | 12 bps (or FX/gold-appropriate if config exists) | Align clean_labels / M4 |
| SL/TP | **Two arms:** (A) fixed 1R/1R as train; (B) production planner mults if available | Separates “fit the training label” from “planner-realistic” |
| Entry set | Sweep-only first (journal ontology) | No silent switch to TRADE_OPENED until Phase E1b |

**Arms (pre-register before run):**

| Arm ID | Rule | Control peers |
|---|---|---|
| `nb_top_decile` | Take unit if score ≥ p90 (train-calibrated quantile) | — |
| `nb_bottom_decile` | score ≤ p10 | anti-skill check |
| `random_match_n` | Random subset size-matched to top decile | permutation peer |
| `all_sweeps` | All units | baseline detection set |
| `long_only` / `short_only` | Direction filters | direction bias |

**Metrics (per arm, IS/OOS chronological):**

- n, mean net R, PF, win rate, max DD (optional), bootstrap CI if n allows  

**Deliverables:**

- Extend or call `build_gaussian_family_shadow_eval.py --instrument XAUUSD` with  
  `--candidate-mode sweep` and explicit score thresholds from E0 model  
- Output: `results/gaussian_xauusd_econ/ledger_<ts>.json` + per-arm tables  
- Link each arm back to journal `reason_code` vocabulary in the report  

**Exit:** Written E[R] for top-decile vs controls on **OOS (2m holdout + earlier OOS slice)**.  
**Still no authority** even if E[R] > 0 (need M4).

**Kill criteria (pre-registered):**

- Top-decile OOS E[R] ≤ all_sweeps E[R] **and** ≤ random → **no skill** → stop, freeze model as registry-only.  
- n_oos top-decile < `QualConfig.min_samples` → INSUFFICIENT, do not invent denser entries without new design.

**E1 SHIPPED (2026-07-23):**

| Item | Value |
|---|---|
| Script | `scripts/research/xauusd_gaussian_econ_ledger.py` |
| Tests | `tests/test_xauusd_gaussian_econ_ledger_e1.py` (6 passed) |
| Ledger | `results/gaussian_xauusd_econ/ledger_LATEST.jsonl` |
| Manifest | `results/gaussian_xauusd_econ/e1_manifest_LATEST.json` |
| Train p10 / p90 | 0.500014 / 0.622459 (train-only) |
| OOS all_units E[R] | **−0.532** (n=267, PF 0.31) |
| OOS top_decile E[R] | **−0.451** (n=174, PF 0.37) |
| OOS random E[R] | **−0.638** (n=174) |
| OOS bottom_decile | **n=0** (train floor ≈ p10; OOS scores sit above floor) |
| Kill verdict | **SKILL_SIGNAL_RESEARCH_ONLY** — top beats all & random on OOS **but all E[R]<0** |
| Economic authority | **NO** — negative expectancy; not M4 |

---

### Phase E1b — Optional entry upgrade (only if E1 kill or underpowered)

If sweep set is economically dead or underpowered:

| Option | When | Cost |
|---|---|---|
| B1 RETEST/EXECUTION-only candidates | Journal/CRT can emit denser structure nearer entries | New journal kinds or CRT state filter |
| B2 Spine `TRADE_OPENED` only | Honest live path; likely n≪30 on XAU | Expect INSUFFICIENT; still valuable null |
| B3 Planner-true SL/TP from `ExecutionPlannerV1_2` | Closer to live R geometry | Config-driven mults; parity tests |

**Rule:** One new entry ontology at a time; new `bar_semantic` reason codes if stream changes.

### Pre-registration superseding v0 (2026-07-23) — NOT YET EXECUTED

After conversation falsification, a **new frozen protocol** was pre-registered (do not edit after OOS):

| Piece | v0 (done) | **v1 pre-reg** |
|---|---|---|
| Cost | 12 bps flat | **Fixed USD RT 0.40** (+ sensitivity grid diagnostic) |
| Entry | SWEEP | **RETEST enter edge** |
| Control | broken multi-tag random | **Per-split size-match + acceptance_test** |
| Model | trained once | **No retrain** (same weights) |

- Machine: `configs/research/xau_metals_protocol_v1.json`  
- Human: `docs/research/xau_metals_protocol_v1_preregistration.md`  
- Loader: `src/research/xau_metals_protocol.py`  
- Status: `PRE_REGISTERED_NOT_EXECUTED` until a runner is implemented and run  


---

### Phase E2 — M4 QualificationGate (1–2 days)

**Goal:** Binary research verdict under unified gate.

Wire E1 outcomes into `QualificationGate`:

1. min_samples  
2. expectancy NET  
3. PF NET  
4. beats winning control  
5. OOS retention  
6. permutation vs control  
7. BH if multi-hypothesis cohort (multiple thresholds/arms)

**Deliverables:**

- `scripts/research/xauusd_gaussian_m4_qualify.py`  
- Artifact: `results/gaussian_xauusd_econ/m4_<ts>.json`  
- Finding row candidate only if PROMOTE (else document REJECT/INSUFFICIENT in session log + optional analysis note — **no** silent F-id)

**Exit:**

| Verdict | Action |
|---|---|
| PROMOTE | Proceed to E3 discussion (still not auto-wire) |
| REJECT | Close program for this entry/label protocol; journal remains research gold |
| INSUFFICIENT | Either stop or E1b with pre-registered plan |

**E2 SHIPPED (2026-07-23):**

| Item | Value |
|---|---|
| Script | `scripts/research/xauusd_gaussian_m4_qualify.py` |
| Tests | `tests/test_xauusd_gaussian_m4_e2.py` (3 passed) |
| Manifest | `results/gaussian_xauusd_econ/e2_m4_manifest_LATEST.json` |
| Cohort | **any_PROMOTE=False** · economic_authority=False |
| `nb_top_decile` | **REJECT** gate2_expectancy E[R]=−0.25 |
| `all_units` | **REJECT** gate2_expectancy E[R]=−0.96 |
| `long_only` / `short_only` / `nb_bottom_decile` | **REJECT** (all E[R]<0) |
| Program close | Research protocol on sweep+1R/1R+12bps is **economically rejected** under M4; registry pointer may remain; no E3 |

---

### Phase E3 — Toward authority (gated; optional)

Only if E2 = PROMOTE **and** measured consumer ΔG001 vs baseline:

| Step | Action | Forbidden without evidence |
|---|---|---|
| E3a | Shadow config: `gaussian_impl=shadow_ml` or instrument-scoped ML load for XAUUSD only | Editing active production to `ml` |
| E3b | Gate-ON A/B ledger sha + trade count (F-036 method) on XAU if spine admits trades | Claiming pivotality without byte-diff |
| E3c | Human approve: authority to influence fusion weight / veto | Auto-promote economic claim into findings Certain |

**Config-first:** new knobs (`score_accept_quantile`, instrument ML path) via strict `_require` sections; rehash if `params` touched.

**Default recommendation if E2 PROMOTE but spine n tiny:** keep **research consumer** (filter research candidates only); do **not** force live complexity.

---

## 5. What we explicitly will not do (anti-scope)

- Treat registry promote as economic promote  
- Train on F-022 contaminated opportunity streams as “production labels” without flagging  
- Silent truncate 39→38 or ambient vector hacks  
- Flip `gaussian_impl=ml` on active `v2_multi_2026_04` without E2+E3  
- Optimize score thresholds after seeing OOS (pre-register quantiles on train only)  
- Claim gold FX cost model is free — cost_bps must be declared and sensitivity-noted  

---

## 6. Semantic journal’s permanent role

The journal is the **epistemic substrate** for economics, not a side log:

| Economics question | Journal answer |
|---|---|
| What was an entry? | `SWEEP_CANDIDATE` / `LABEL_ACCEPTED` only |
| What was excluded from fit? | `HOLDOUT` |
| Why no live trade semantics? | No `TRADE_OPENED` kind exists in this run |
| Why mean R negative? | Aggregate `LABEL_ACCEPTED.payload.y_rr` |
| LLM explanation of a unit | `reason_code` + `narrative` + payload |

**Enhancement E0+:** append optional kinds (research-only, additive):

- `ECON_UNIT_SCORED`  
- `ECON_ARM_DECISION` (taken/skipped + arm_id)  
- `ECON_OUTCOME` (net R, exit_reason)  

Same `bar_semantic.v1` or bump to `v1.1` with backward-compatible readers.

---

## 7. Success metrics (program level)

| Milestone | Success |
|---|---|
| E0 | Units JSONL + hash; holdout parity with journal |
| E1 | Pre-registered arms; OOS table published |
| E2 | M4 verdict file; 0 PROMOTE is success if honest |
| E3 | Only if PROMOTE + ΔG001; otherwise program CLOSED research-only |

---

## 8. Suggested first implementation PR (minimal)

**PR-1 (E0 only):**

1. `scripts/research/xauusd_gaussian_econ_units.py` — journal → scored units  
2. Manifest + SHA under `results/gaussian_xauusd_econ/`  
3. Tests: holdout count, feature dim 39, model load of promoted version  
4. No config edits, no promote changes  

**PR-2 (E1):** economic arms + report  
**PR-3 (E2):** M4 wrapper  

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| Sweep set has no skill (likely given mean y_rr −1) | Pre-registered kill at E1; stop without entry fishing |
| Threshold fishing | Quantiles frozen on train; OOS read-only |
| Confusing registry promote with econ promote | Every report header: `REGISTRY_ACTIVE ≠ ECONOMIC_AUTHORITY` |
| Underpowered OOS 2m | Report INSUFFICIENT; optional longer OOS in E1b with pre-reg |
| Live path never uses NB | Document as intentional until E3 |

---

## 10. Decision for user

**Recommended next step:** Implement **Phase E0** only (scored units from journal + promoted model).  

Then run **E1** with pre-registered arms before any threshold tuning.

---

## 11. Closure of this design doc

This design **moves toward economics** without claiming economics.  
It preserves:

- Journal truth (why not economic today)  
- Authority Ladder  
- Existing M4 / shadow-eval machinery  
- Config-first and no premature live wire  

**Current state after design:** still **REGISTRY_ACTIVE / RESEARCH_ONLY**.  
**Next state after E0–E2:** either **ECONOMICALLY_REJECTED (closed)** or **M4_PROMOTE_CANDIDATE → E3 discussion**.


================================================================================
SOURCE_FILE: docs/implementation_plan/yes-based-on-the-stateful-flamingo.md
SOURCE_BYTES: 9692
PART: 10/10 FILE 10/16
================================================================================

# Plan — Codify the Truth-Maintenance Doctrine + Active-Version Mandate into CLAUDE.md

> Created: 2026-06-11 · Updated: 2026-06-11 · Scope: doc-only (no code, no config writes)

## Context — why this change

Across this session we diagnosed **F-016 (split-brain version truth)** and a broader pattern:
findings, docs, and runtime can disagree, and an agent reading stale history infers the wrong
state. The proposed remedy was a "Repository Truth Maintenance Doctrine."

Exploration reversed two assumptions and reframed the work:

1. **The runtime is already correctly file-driven.** `get_active_version()`
   ([production_config.py:60](src/config_layer/production_config.py)) fail-fasts (`RuntimeError`)
   on a missing/empty `ACTIVE_VERSION`; unknown override keys raise `ValueError`
   ([config_builder.py:190](src/config_layer/config_builder.py)). **F-016's split-brain exists
   only at the agent/LLM reasoning layer** — so the fix is doctrinal (a CLAUDE.md mandate to read
   `ACTIVE_VERSION` first), not code.

2. **The truth-maintenance scaffolding is ~85% built**, but CLAUDE.md is missing the doctrine the
   rest of the repo *already cites*. Four forward-references point at CLAUDE.md mandates that do
   not exist yet:
   - `docs/topics/readme.md:5` → "CLAUDE.md **§6.1** Topic Sync Mandate" (collides — §6.1 is
     Intelligence Compounding)
   - `docs/current-findings.md:17` → "CLAUDE.md **§6.2** Findings Mandate" (absent)
   - `docs/architecture/trigger-vocabulary.md:82` → "CLAUDE.md **§6.3** Citation Sync Mandate"
     (absent)
   - `current-findings.md:8` + `trigger-vocabulary.md:79` → "CLAUDE.md → **Repository Truths
     Index**" (absent)

**Intended outcome:** make those four references real and self-consistent, add the Active-Version
mandate that closes F-016 at the reasoning layer, and wrap them under one "Truth Maintenance
Doctrine" — *without creating new docs* (which is itself the doctrine's Rule 1/Rule 5). Existing
living substrate (`current-findings.md`, `analysis/readme.md`, `knowledge-map.md`,
`test_doc_citations.py`) is referenced, not duplicated.

## Scope (confirmed with user)

- **Doc-only.** No code edits, no config writes.
- **Flag — don't touch — the pointer suffix.** `configs/production/ACTIVE_VERSION` =
  `v2_multi_2026_04 - deepdeektry`; the ` - deepdeektry` suffix is the orphaned F-006 residual.
  Documented as a known finding here; **no write** — defer to a separate governed change that
  verifies the registry key + `promotion_log.jsonl` PROMOTED entry first.

## Numbering reconciliation (the one judgment call)

§6.1 is entrenched as **Intelligence Compounding** (referenced by CLAUDE.md §7.4, `MEMORY.md`, and
`docs/architecture/intelligence-compounding.md`). The docs' cited scheme wants §6.1=Topic Sync,
§6.2=Findings, §6.3=Citation Sync. Resolution that **minimizes total reference churn**:

| Mandate | Target § | Matches existing citation? | Action |
|---|---|---|---|
| Intelligence Compounding | §6.1 (unchanged) | — | leave as-is |
| **Truth Maintenance Doctrine** (umbrella + Repository Truths Index + Findings Mandate) | **§6.2** | ✅ `current-findings.md:17` cites §6.2 Findings | add |
| **Citation Sync Mandate** | **§6.3** | ✅ `trigger-vocabulary.md:82` cites §6.3 | add |
| **Topic Sync Mandate** | **§6.4** | ❌ docs cite §6.1 | add + fix 2 refs |

Net: defining §6.2/§6.3 at the cited numbers validates two references *for free*; only the
Topic-Sync §6.1→§6.4 reference needs editing (2 occurrences).

## Changes

### 1. `CLAUDE.md` — new `§4.0 Active Version Resolution (Mandatory)` (lead-in to §4 Constraints)
Codify the user-authored content:
- **Runtime Truth Precedence (Tier 0–4):** `ACTIVE_VERSION` (Tier 0) > schema physically present
  in code / `CRTConfig`+`ConfigBuilder` (Tier 1) > `promotion_log.jsonl` (Tier 2) >
  `assistant_project.md`/historical findings (Tier 3) > LLM memory (Tier 4). Lower tiers describe
  history; never override higher.
- **`ORIENT_RUNTIME` ritual (A–E):** read `configs/production/ACTIVE_VERSION` → load that config →
  verify schema compat vs `CRTConfig`/`ConfigBuilder` → record `ACTIVE_VERSION=<v>` → only then
  plan/execute. Version truth is **branch-scoped**. If a config carries keys absent from
  `CRTConfig` → conclude "schema/version mismatch," do **not** migrate or execute (cites the real
  `ValueError` at [config_builder.py:190](src/config_layer/config_builder.py)).
- One-line cross-link to §6.2.

### 2. `CLAUDE.md` — new `§6.2 Repository Truth Maintenance Doctrine` (sibling to §6.1)
- **The 7 rules** (condensed): existing-docs-first; detect drift (ALIGNED / DOC_DRIFT[code wins] /
  CODE_DRIFT[doc wins] / AMBIGUOUS[human]); never silently resolve conflicts → emit a
  `TruthConflict` and ask; preserve history via `SUPERSEDED_BY`/`INVALIDATED_BY`/`BRANCH_SPECIFIC`
  (never delete); minimize doc count; mandatory cross-sync; human confirmation on multi-authority
  disagreement.
- **Points at** (does not duplicate) the living substrate: `docs/current-findings.md`,
  `docs/analysis/readme.md` (point-in-time, not living), `docs/knowledge-map.md`,
  `docs/timeline.md`.
- **Findings Mandate** (the §6.2 the docs cite): validate/overturn a conclusion → add/flip a
  finding in the same turn; set `Validated`/`Revalidate-by`, cite `Evidence`, fill `Reversal`;
  never delete. Mirror the rule already stated in `current-findings.md:17–21`.
- **Repository Truths Index (thin, always-loaded):** compact bulleted list of **active** findings
  (id · one-line verdict · confidence) extracted from `current-findings.md`'s non-SUPERSEDED rows,
  with a pointer to the full record. Satisfies `current-findings.md:8` ("the thin always-loaded
  index lives in CLAUDE.md"). Kept fresh by the Findings Mandate; covered by
  `tests/test_current_findings.py`.

### 3. `CLAUDE.md` — new `§6.3 Citation Sync Mandate`
Codify what `trigger-vocabulary.md:82` already references: when code that a `path:line · Symbol`
citation points at moves, update the citation in the same turn; use
`docs/architecture/citation-map.generated.md` to find them; enforced by
`tests/test_doc_citations.py` (±30-line drift window).

### 4. `CLAUDE.md` — new `§6.4 Topic Sync Mandate`
Codify what `docs/topics/readme.md:5` references: when you change code a topic covers, update that
**one** topic doc the same response, bump `Updated:`, append a dated Discussion entry; enforced by
`tests/test_topic_docs.py`. This is the `Sync` Tier-2 trigger's doctrine home.

### 5. Fix the dangling references (the drift this doctrine exists to kill)
- `docs/topics/readme.md:5` — `§6.1 Topic Sync Mandate` → `§6.4 Topic Sync Mandate`.
- `docs/architecture/trigger-vocabulary.md:82` — the `§6.1` in "The CLAUDE.md §6.1/§6.3 mandates"
  → `§6.4` (the `§6.3` Citation Sync reference becomes valid once §6.3 exists — no edit).

## Files to modify
- `CLAUDE.md` — add §4.0, §6.2, §6.3, §6.4 (4 additive sections; Intelligence Compounding §6.1
  untouched).
- `docs/topics/readme.md` — 1 ref fix (§6.1→§6.4).
- `docs/architecture/trigger-vocabulary.md` — 1 ref fix (§6.1→§6.4).

No other files. No `src/`, no `configs/`.

## Verification (read-only / tests)
1. `pytest tests/test_doc_citations.py tests/test_topic_docs.py tests/test_current_findings.py`
   — confirm citation/topic/findings invariants still pass after edits.
2. Grep proof that no dangling CLAUDE.md mandate references remain:
   `rg "§6\.\d Topic Sync|§6\.\d Findings|§6\.\d Citation Sync|Repository Truths Index"` across
   `docs/` → every hit now resolves to a section that exists in `CLAUDE.md`.
3. Confirm §6.1 (Intelligence Compounding) text and its §7.4/`MEMORY.md` references are unchanged
   (no collateral renumbering).
4. Manual read-through: the Tier 0–4 precedence + `ORIENT_RUNTIME` correctly names
   `configs/production/ACTIVE_VERSION` and the real `ValueError` failure path.

## Out of scope (explicit)
- The 8-phase "trustworthy laboratory" audit (reachability / metric-integrity / determinism /
  telemetry / test-gap / readiness reports) — deferred to a follow-up plan.
- Any new trading doctrine (immediate-entry / tiny-SL / reject-first).
- Cleaning the `ACTIVE_VERSION` ` - deepdeektry` suffix (F-006) — flag only.
- No new standalone docs created (doctrine Rule 5).

---
📝 SESSION LOG ENTRY
Date: 2026-06-11
Topic: Plan — codify Truth-Maintenance Doctrine + Active-Version mandate into CLAUDE.md (doc-only)
Decision/Output: Plan written. Runtime already file-driven (get_active_version fail-fast) → F-016 is a reasoning-layer fix. Found 4 forward-refs to non-existent CLAUDE.md mandates (§6.1 Topic Sync collides; §6.2 Findings, §6.3 Citation Sync, Repository Truths Index absent). Resolution: §6.1 stays Intelligence Compounding; add §4.0 Active Version Resolution + §6.2 Truth Maintenance (umbrella + Findings Mandate + Truths Index) + §6.3 Citation Sync + §6.4 Topic Sync; fix 2 §6.1→§6.4 refs. Pointer suffix flagged, not touched.
Belief Update / ROI / Goal: Goal: zero silent truth divergence (intelligence compounding). Belief: the split-brain is documentation entropy, not a runtime bug — and the cure already exists, just uncited. Knowledge ROI: high — defining §6.2/§6.3 at the numbers docs already cite validates 2 refs for free. Action: codify, don't create; defer lab audit.
Open Questions: Should the thin Repository Truths Index list all active F-### inline (maintenance burden) or a tighter top-N? Confirm at execution from current-findings.md active rows.
Next Step: On approval, apply the 6 edits and run the 3 doc tests.
---


================================================================================
SOURCE_FILE: docs/implementation_plan/yes-i-can-do-sprightly-hamster.md
SOURCE_BYTES: 37775
PART: 10/10 FILE 11/16
================================================================================

# Tradelatest Semantic OS v2 — Build 1 (L1 + L5 + L6)

## Context

The repo already has a Canonical Book (26 chapters), a Repository Encyclopedia (813 rows + JSONL twin),
a market ontology (54 `FM-*` nodes with full epistemic blocks), MIAR (17 model-intent entries), a Closure
& Authority Index (11 surfaces), and ~250 governance artifacts. What it does **not** have is a way to
*reason across them*. Today an agent can find `feature_pipeline.py`; it cannot answer "who owns ATR
normalization", "what guarantees no lookahead", or "what breaks if I change this."

Three concrete gaps, verified against source:

1. **No concept layer.** Nothing enumerates Market→Feature→State→Engine→Decision→Execution→Risk→
   Research→Governance as first-class nodes. The two closest — MIAR's 7 `stages` and the closure index's
   11 `surfaces` — use different, unreconciled vocabularies and answer different questions.
2. **No cross-surface query.** `scripts/governance/feature_surface_query.py` is exactly the right
   pattern (evidence-classed, fail-closed on ambiguity, freshness from embedded `generated_at`) but joins
   only the *feature* surface.
3. **Impact is declared, never computed.** `construction_protocol.py validate-completion` diffs a
   *human-written* manifest against `git status`. Nothing computes blast radius, even though every input
   exists: `graph.dot` (696 edges), `config-consumer-graph.generated.json` (763 nodes / 1,295 edges),
   `build_lineage_graph()`, `citation-map.generated.md`, findings `evidence_paths`.

**Outcome:** an advisory, queryable semantic layer that answers *why / who owns / what breaks* by
traversing relationships — built by **joining and computing** from existing authorities, never by
duplicating them.

### The rule that shapes everything

> Hand-author **only** what code cannot answer: why it exists, what invariant must never break, why this
> design, why alternatives were rejected, which finding justifies it.
> Imports, dependencies, callers, package, ownership, size, tests, reachability, runtime path — **generated**.

This is mechanically enforced (validator #14, `_FORBIDDEN_HAND_FIELDS`), not merely stated.

### Four entities

| Entity | Count | Source | Notes |
|---|---|---|---|
| **Concepts** `CN-###` | ~50 | HAND | Stable meaning. *References* MIAR/closure/ontology/book/findings; owns none of them. |
| **Boundaries** `BD-###` | ~40 | HAND | Architectural seams, **not files**. Owner + member globs + consumers + the invariant protected. Survives implementation churn. |
| **Journeys** `JN-###` | 4–8 | HAND | Ordered semantic paths across concepts. Machine twin of `signal-flow.md`. |
| **Objects** `OBJ:<path>` | 844 | **100% GENERATED** | Zero manual maintenance. Every field computed + evidence-classed. |

**Evidence is not a new registry** — it joins `data/findings.jsonl` (70), `data/hypothesis_registry.jsonl`
(18), `data/framework_registry.jsonl` (41), and pytest discovery.

### Decisions taken (do not re-litigate)

- **Granularity:** concept + boundary contracts hand-authored; ~844 objects fully generated.
- **Vocabulary:** new axis *above* MIAR and Closure, joined by validated FKs. Neither is edited.
- **Scope:** L1 + L5 + L6. L2/L3/L4 are projections of L1, not separate work.
- **Enforcement:** guard tests on GREEN_FLOOR; validation is **graph integrity**, not file presence.
- **Authority:** `authority: "advisory"` pinned on every record (§6.5). Grants **zero** production authority.
- **Untracked inputs:** targeted `git add` of the 6 artifacts (Phase 0).
- **Change class:** reuse `SCRIPT_LIFECYCLE_CHANGE` + `DOCUMENTATION_ONLY`; file the
  `GOVERNANCE_REGISTRY_ADDITION` gap as a follow-up.
- **Import graph:** add an AST import census for `scripts/` + `tests/` + root in build 1.

---

## Verified facts this plan rests on

| Claim | Verified |
|---|---|
| `graph.dot` is `src/`-only | 696 `->` edges, dotted module names, **0** `scripts`/`tests` nodes |
| Code universe on disk | 472 src + 351 scripts + 21 root = **844**; tests 411 (→ 1,255 with `--universe all`) |
| Encyclopedia denominator is stale | 813 rows vs 844 on disk — 38 src + 21 root missing, 0 tests |
| `module_attribution` ownership is empty | `owner_surface` = `UNATTRIBUTED` on **463/463**; `regime` populated (RESEARCH 180 / PLATFORM 90 / SUBSTRATE 56 / DECISION 55 / TERMINAL 51 / MODEL_LINEAGE 31) |
| 6 inputs untracked | `encyclopedia_rows.jsonl`, `module_attribution_stubs.jsonl`, `config-consumer-graph.generated.json`, `miar_registry.json`, `closure_authority_index.json`, `change_contracts.json` — all UNTRACKED, **not** ignored. `graph.dot` + `citation-map.generated.md` are TRACKED. |
| Citation map recall is low | 20 rows / 18 symbols, several stored as bare basenames → HEURISTIC only |

---

## File inventory

### Committed PRIMARY (hand-authored truth)

| Path | Role |
|---|---|
| `docs/governance/semantic_os/concepts.yaml` | ~50 Concept records |
| `docs/governance/semantic_os/boundaries.yaml` | ~40 Boundary records |
| `docs/governance/semantic_os/journeys.yaml` | 4–8 Journey records |
| `docs/governance/SEMANTIC_OS_CONTRACT.md` | Charter — mirrors `MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md` |
| `docs/governance/build_manifests/CH-semantic-os-v2.{impact,completion}.json` | §3.3b entry/exit |

YAML (not JSONL) because prose fields need block scalars; precedent is `configs/formulas/market_ontology.yaml`.
Under `docs/` because `.gitignore` line 2 ignores `data`.

### Logic — `src/` (committed)

| Path | Role |
|---|---|
| `src/governance/semantic_os.py` | Enums, `_REQUIRED_FIELDS` per kind, `ValidationError`, `validate_record`, `SemanticOSRegistry`, `dump`, all 14 graph validators. **Mirrors `src/governance/framework_registry.py` shape exactly.** |
| `src/governance/semantic_objects.py` | `discover_universe()`, `ast_import_census()`, `build_objects()`, `ObjectIndex`, `FIELD_EVIDENCE_CLASS`, `coverage_report()` |
| `src/governance/semantic_query.py` | **L5.** `SemanticIndex`, `Answer`, `QUESTION_REGISTRY`, `AmbiguousAliasError` |
| `src/governance/semantic_impact.py` | **L6.** `blast_radius()`, `required_checks_for()`, `draft_impact_manifest()` |

PR-6 pattern (`src/governance/script_seed.py`): logic in `src/`, thin CLI in `scripts/`, so tests import
it without `spec_from_file_location`.

### Thin CLIs — `scripts/` (committed, **SITS-registered same turn**)

| Path | Role |
|---|---|
| `scripts/governance/seed_semantic_os.py` | Write path → `data/semantic_os/*.jsonl` via `SemanticOSRegistry.dump()`, pinned `_TS` |
| `scripts/governance/query_semantic_os.py` | Read path — L5 + L6 + `--validate` |

Two scripts only, to minimise SITS surface. Named `query_semantic_os.py` (not `semantic_os.py`) to avoid
shadowing `src/governance/semantic_os.py` under `pythonpath = ["src","scripts","."]`.

### Tests (committed)

`tests/test_semantic_os.py` · `test_semantic_os_objects.py` · `test_semantic_query.py` ·
`test_semantic_impact.py` — each with an autouse module-scoped reseed fixture copied from
`tests/test_framework_registry.py:30-36` (because `data/` is gitignored).

### Generated projection (gitignored, disposable)

`data/semantic_os/{concepts,boundaries,journeys,objects}.jsonl` + `index_meta.json`

### Modified

| Path | Change |
|---|---|
| `scripts/maintenance/check_governance_invariants.py:69` | +4 GREEN_FLOOR targets; +6 `GOVERNED_FILES` |
| `tests/test_governance_invariant_check.py` | pin the new GREEN_FLOOR members |
| `docs/reference/schemas.md` | new §9.10 Concept · §9.11 Boundary · §9.12 Journey · §9.13 Object, in the §9.9 TypedDict-literal style |
| `docs/governance/script_registry_stubs.jsonl` | regenerated |
| `scripts/governance/seed_script_registry.py` | 2 real `purpose` OVERLAYs (never `GRANDFATHER_UNCLASSIFIED`) |
| `docs/reference/script-matrix.md` | regenerated |
| `assistant_project.md` | SESSION LOG entry (§7.4) |

**Not touched:** no `src/` runtime path, no `configs/`, no `models/`, no `active_models.yaml`.
`PRODUCTION_BEHAVIOR_CHANGED = NO`.

### ID namespaces

`CN-###` · `BD-###` · `JN-###` · `JN-###.S##` (steps) · `OBJ:<posix-path>` (objects).

Two-letter + zero-padded matches every existing namespace (`FM-`, `SEM-`, `UNK-`, `RC-`, `IND-`, `MOD-`,
`SCR-`, `F-`, `H-`); none of CN/BD/JN collides. **Objects deliberately break the pattern** — a sequential
`OBJ-0001` needs a pinned allocation ledger (exactly why `module_attribution_stubs.jsonl` exists), which
reintroduces the maintenance the user's contract forbids. `OBJ:<path>` is stable by construction, is the
natural join key against every artifact (they all key on path), and follows the repo's own precedent in
`config-consumer-graph.generated.json` (`file:<path>`, `cfg:<section>.<key>`).

---

## Record schemas

Legend: **H** hand-authored (required in YAML) · **C** computed at seed (pinned) · **D** derived at query
time (**forbidden in the YAML source**).

### Concept `CN-###`

- **Identity (H):** `id`, `name`, `aliases`, `status` (ACTIVE|PROPOSED|SUPERSEDED|RETIRED),
  `supersedes`, `superseded_by`; `authority: "advisory"` (**C**, pinned literal).
- **Intent (H):** `why_it_exists`, `problem_it_solves`, `explicit_non_goals` (vocabulary borrowed from
  `miar_registry.entries[]`).
- **Authority — references only (H):** `miar_stage` (FK→7 stages), `miar_entry` (FK→entries[].id),
  `closure_surface_id` (FK→11 surfaces), `ontology_ids` (FK→`FM-*`/`SEM-*`/`UNK-*`/`RC-*`/`IND-*`),
  `owner_boundary` (FK→exactly one BD), `related_boundaries`, `canonical_source` (one repo path).
- **Contracts (H):** `invariants`, `preconditions`, `postconditions`,
  `assumptions[] {assumption, falsified_by: F-NNN|null, status: HOLDS|FALSIFIED|UNTESTED}`.
- **Behavior (H):** `behavior`, `failure_modes[] {mode, symptom, detection, finding}` — `mode` is the FK
  target for journey steps.
- **Reasoning (H):** `why_this_design`, `alternatives_rejected[] {alternative, why_rejected, evidence}`,
  `research_findings` (FK→F-NNN), `hypotheses` (FK→H-NNN), `framework_ids`.
- **LLM (H):** `summary_50` (≤320 chars, enforced), `summary_200` (≤1400), `retrieval_keywords`,
  `semantic_tags` (closed vocabulary in the charter).
- **Doc anchors (H):** `book_chapter` (must exist **and** be in `docs/book/README.md` TOC), `topic_doc`,
  `intent_chain`, `intent_domain_doc`, `related_concepts`, `orphan_justification`.
- **C:** `created`, `last_validated` (pinned `_TS`), `schema_version: "semantic_os/1"`.

**`_FORBIDDEN_HAND_FIELDS` (D — schema violation if present in YAML):** `objects`, `modules`,
`authoritative_modules`, `tests`, `config_keys`, `consumers`, `dependencies`, `imports`, `reachability`,
`book_status`, `citations`, `bytes`, `package`, `owner_surface`, `evidence_count`, `journey_steps`,
`entry_points`, `blast_radius`. *This list is the hand-author rule, mechanised.*

### Boundary `BD-###`

- **H:** `id`, `name` (e.g. "Feature Production"), `kind`
  (PRODUCTION|POLICY|AUTHORITY|TRANSPORT|STORAGE|OBSERVATION), `status`, `authority_layer` (WHAT|HOW|WHO —
  vocabulary from `WHAT_HOW_WHO_EXECUTABLE_BOUNDARY_MAP_V1.json`).
- **H:** `owner` (one repo path), `owner_symbol` (validated with the ±30-line drift window),
  `members` (**globs** and/or explicit paths), `members_exclude`, `consumers` (BD-ids and/or paths).
- **H, required non-empty:** `invariant_protected`, `invariant_violation_symptom`.
- **H:** `contract {inputs, outputs, guarantees, non_guarantees, enforced_by_tests}`.
- **H:** `concepts` (FK→CN, bidirectionally enforced), `closure_surface_id`, `miar_stage`,
  `change_classes` (FK→`change_contracts.json` keys — **the root of L6's `required_checks`**),
  `evidence[] {path, symbol, line, type}`, `findings`, `why_this_boundary`.
- **D:** `members_resolved`, `member_count`, `import_fan_in/out`, `cross_boundary_imports`,
  `config_keys_read`, `test_files`, `uncovered_members`, `orphan_members`.

A boundary is **not a file list you maintain** — you maintain the glob and the invariant. Renaming a module
inside `src/features/` changes nothing; a glob matching zero files is a validation error. That is the
churn-survival property.

### Journey `JN-###`

- **H:** `id`, `name`, `kind` (RUNTIME|RESEARCH|GOVERNANCE|AGENT|CONFIG), `status`, `source_doc`
  (the prose ancestor), `trigger`, `terminal_outcomes`, `why_this_path`.
- **H `steps[]`:** `step_id` (`JN-001.S03`), `order` (1..N contiguous), `name`, `concept` (FK, required),
  `boundary` (FK, required — must be the concept's `owner_boundary` or in `related_boundaries`),
  `failure_mode` (**FK into that concept's own `failure_modes[].mode`**), `on_failure`
  (HALT|SKIP|DEGRADE|REJECT|FALLBACK), `next[]` (branches allowed), `evidence {path, anchor}`.
- **H `async_feeders[]`:** `{name, joins_at_step, kind}` — the 4 from `signal-flow.md` §2.
- **D:** `objects_traversed`, `config_keys_on_path`, `required_checks_union`, `invariants_on_path`.

`failure_mode` being an FK into the concept's declared modes is what stops journeys degenerating into
free-text narrative.

---

## The generated Object layer

**Universe = disk enumeration** (`--universe code` default = 844; `--universe all` adds tests = 1,255).
Artifacts are *enrichments*, never the denominator — denominator drift is precisely why
`test_module_attribution.py` enforces enumeration HARD. Every object carries
`present_in: ["encyclopedia","module_attribution","script_registry"]` plus a top-level `coverage_gaps`
block recording the measured 38 / 21 / 9 / 411 deltas.

| Field | Source | evidence_class |
|---|---|---|
| `id`, `path`, `kind` | disk `rglob`, POSIX-normalised | PROVEN |
| `bytes`, `sha256` | recomputed from disk (**not** read from encyclopedia — its `bytes` is a snapshot) | PROVEN |
| `package` | path → dotted, `src.` stripped (mirrors `gen_code_map._pkg`) | PROVEN |
| `classes`, `functions`, `has_main` | `ast.parse` top-level defs | PROVEN |
| `purpose` | encyclopedia `purpose`, else docstring line 1, + explicit `purpose_source` | TEXT_REFERENCE |
| `relevance`, `phase`, `group`, `book_status` | encyclopedia | HEURISTIC (curated classification) |
| `imports` / `consumers` | `graph.dot` fwd/rev edges (src/) **+ `ast_import_census()`** (scripts/tests/root) | PROVEN |
| `graph_reachable_from` | BFS from declared entry points | PROVEN — *reachability ≠ "runs in production"* |
| `owner_boundary` | `boundaries.yaml` glob resolution | PROVEN |
| `owner_surface` | `module_attribution.owner_surface` | **`UNATTRIBUTED` on 463/463 — emitted verbatim, never guessed** |
| `regime`, `reachability_declared` | module_attribution | HEURISTIC (stub notes say "regime is a package heuristic"; reachability all UNKNOWN) |
| `config_keys` | config-consumer-graph edges + per-key `verdict` from `config-reachability-report.json` | PROVEN iff `verdict == READ_AND_USED`, else HEURISTIC |
| `tests_importing` | AST import scan of `tests/**` | PROVEN |
| `test_text_references` | `\bbasename\b` regex over `tests/` | TEXT_REFERENCE — **never called coverage** |
| `doc_citations` | `citation-map.generated.md` | HEURISTIC (18 symbols, bare basenames, low recall) |
| `findings_evidence`, `framework_evidence` | exact path in `evidence_paths[]` / `evidence[].path` | PROVEN |
| `script_registry` block | 22 SITS keys verbatim | PROVEN |
| `entry_points` | `control_plane_id`/`agent_tool_id` + `control_plane/registry.py` + `agent/tool_registry.py` | PROVEN |
| `concepts`, `journey_steps` | FK walk via `owner_boundary` | PROVEN |

### Must be `null`, never guessed

1. **Call-level edges.** Everything is module-import-level. `pyan_call_flow.dot` (~64.8k edges, tracked)
   resolves by name heuristic with unpinned freshness → HEURISTIC at best, **excluded from build 1**.
2. **Dynamic imports.** `importlib`/`__import__` are invisible to both graphs → `dynamic_import_risk: true`
   on token presence only, class TEXT_REFERENCE.
3. **`owner_surface`.** 0/463 attributed. Real ownership comes from `owner_boundary` — this is the concrete
   gap the Boundary layer closes.
4. **Behavioural test coverage.** No `.coverage`/`coverage.xml` in the repo. Textual hits ≠ coverage; two
   separate fields, never merged.
5. **"Runs in production".** `relevance` (curated) / `reachability_declared` (UNKNOWN) / graph reachability
   (real, but reachability) stay **three separate fields**, never collapsed into one `is_live`.
6. **`purpose` for the 38 src + 21 root files absent from the encyclopedia** → docstring fallback with
   `purpose_source`, or `null`. Never synthesised.

### Determinism & freshness

Pinned `_TS`, all lists sorted, `json.dumps(sort_keys=True)`, records sorted by `id` → byte-identical
reruns (pattern: `test_script_matrix_sync.py`). A separate `inputs` block records per artifact
`{path, sha256, embedded_generated_at, exists, stale}`; freshness comes from the **embedded** timestamp
(`_latest_by_generated_at` discipline, `feature_surface_query.py:80`), never the filename. Caveat recorded,
not silently normalised: encyclopedia `generated_at` is a date string (`"2026-08-07"`) while the config
graph carries full ISO — not cross-comparable.

---

## L5 — Semantic Query Engine

```python
from governance.semantic_query import SemanticIndex, AmbiguousAliasError, Answer

idx = SemanticIndex.load()
idx.resolve("atr normalization")        # -> CN-/BD-/FM-id; raises AmbiguousAliasError
idx.get_concept("CN-012"); idx.get_boundary("BD-004")
idx.get_journey("JN-001"); idx.get_object("src/core/engine_runner.py")
idx.filter(miar_stage=..., closure=..., tag=..., search=...)
idx.answer("owner", target="FM-041")    # -> Answer
idx.summary(); idx.sources; idx.meta["stale_artifacts"]
```

```python
@dataclass(frozen=True)
class Answer:
    question: str; target: str
    verdict: str                 # ANSWERED | PARTIAL | UNANSWERABLE | AMBIGUOUS
    rows: list[dict]             # {claim, evidence_class, artifacts, detail}
    weakest_evidence_class: str  # PROVEN | HEURISTIC | TEXT_REFERENCE
    caveats: list[str]; unanswerable_reason: str | None
```

`QUESTION_REGISTRY` is a **closed slug vocabulary** — no NL parsing, mirroring §3.3's "Deterministic by
design — do not route planning through the LLM."

**Reusing `feature_surface_query.py`:** `scripts/governance/` has no `__init__.py`, so its docstring's
`from scripts.governance...` import does not actually work — `tests/test_feature_surface_query.py:14-19`
loads it via `importlib.util.spec_from_file_location`. Do the same; expose as
`idx.feature_surface: FeatureSurfaceIndex | None`; on failure set
`meta["feature_surface"] = "UNAVAILABLE: <reason>"` and degrade dependent answers.

### CLI (`scripts/governance/query_semantic_os.py`)

```
--summary  --concept ID|NAME|ALIAS  --boundary  --journey  --object PATH
--list {concepts|boundaries|journeys|objects}  --search TEXT
--stage MIAR_STAGE  --closure SURFACE_ID  --tag TAG  --field FIELD (repeatable)
--ask SLUG --target X            # the five question resolvers
--validate [--strict]            # graph integrity; exit 1 on error
--impact PATH|ID [--depth N]     # L6
--emit-impact-manifest PATH --change-id ID [--write]
--sources  --json
```

`sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at import (cp1252 guard,
`feature_surface_query.py:43`).

### The five questions — honest answerability

| Ask | Join path | Verdict | Weakest class |
|---|---|---|---|
| `--ask guarantees --target no_lookahead` | tags/invariants → CN → BD `invariant_protected` + `contract.guarantees` + `enforced_by_tests` + `evidence[]` → members → `tests_importing`; cross-join `feature_surface_query` PIT classes for all 38 vector features + `docs/book/05-*.md` | **PARTIAL** — the declared enforcement set is provable; "nothing else can introduce lookahead" is **not provable by any artifact here** | TEXT_REFERENCE |
| `--ask owner --target "atr normalization"` | alias → ontology (`FM-041 atr` + ATR-normalised `derived_metrics`) → CN → BD `owner` + `owner_symbol` (drift-checked) + `authority_layer`; cross-check `fm_ownership_consumer_matrix.json` | **AMBIGUOUS by design** — 3 candidates (FM-041 kernel period; ATR-normalised derived metrics; the CRT-local recompute that `WHAT_HOW_WHO_...json` records as `DUPLICATED_AUTHORITY / MARKET_MATH_LEAK_INTO_WHO`, parity unproven). Fails closed rather than picking. `owner_surface` **cannot** answer this today — reported as a gap, not an answer | PROVEN per candidate |
| `--ask writers --target execution_geometry` | CN → BD "Execution Planning" → members → `graph.dot` reverse edges → config-consumer-graph `cfg:execution_planner.*` → `boundary.change_classes` → `required_checks` | **PARTIAL** — import edges + `READ_AND_USED` config keys PROVEN; call-level "this function mutates that field" **not available**. Mandatory caveat: *import edge ≠ mutation* | HEURISTIC |
| `--ask disproved --target CN-0NN` | CN `assumptions[].falsified_by` → `findings.jsonl` (`status`, `reversal`, `supersedes`) + `hypothesis_registry.jsonl` (`status: falsified`, `findings[]`) + framework registry | **ANSWERED** where declared (the registries already carry structured falsification, e.g. H-001 `falsified` → F-019/F-021/F-026); else keyword search over 70 findings + 18 hypotheses → PARTIAL | PROVEN / TEXT_REFERENCE |
| `--ask authoritative --target CN-0NN` | CN `canonical_source` → BD `owner` (+drift-verified symbol) → `evidence[]` → members → closure status → encyclopedia `relevance` → graph importers | **ANSWERED**, ranked: `owner` (exactly one) > drift-verified evidence > glob members (*membership ≠ authority*) > importers. Mandatory caveat quoted from the index: **"CLOSURE IS BOUNDARY-SCOPED AND NON-TRANSITIVE"** — never infer authority from an upstream CLOSED surface | PROVEN |

---

## L6 — Impact engine

**Seed normalisation:** path → itself · `CN-id` → its boundary's members · `BD-id` → `members_resolved` ·
`JN-id` → union over step boundaries · `FM-*`/`SEM-*` → `feature_surface_query` row's
`PRODUCERS.write_sites` + `impl_refs` · `section.key` → config-graph consumers.

| Layer | Source | evidence_class |
|---|---|---|
| **imports** | `graph.dot` reverse-BFS (`--depth N`) **+ `ast_import_census()`** for scripts/tests/root | PROVEN |
| **config** | config-consumer-graph + `config-reachability-report.json`; seed → keys it reads → *co-consumers* | PROVEN iff `verdict == READ_AND_USED`, else HEURISTIC |
| **fm_lineage** | `features.registry.build_lineage_graph()` → descendants → affected `CANONICAL_FEATURES` → `SCHEMA_HASH` invalidation flag | PROVEN |
| **doc_citations** | `citation-map.generated.md`, exact path then basename | HEURISTIC — 18 symbols, low recall, stated as a caveat |
| **findings** | exact path in findings/framework/hypothesis `evidence` | PROVEN |
| **semantic** | boundary globs → concepts → journey steps → **`invariants_at_risk`** | PROVEN |
| **checks** | matched `boundary.change_classes` → `required_checks` ∪ static path→class fallback ∪ GREEN_FLOOR if a seed hits `GOVERNED_PREFIXES`/`GOVERNED_FILES` ∪ `tests_importing` | PROVEN |

**Static path→class fallback** for seeds no boundary claims: `configs/production/*` →
`PRODUCTION_CONFIG_CHANGE` · `configs/formulas/market_ontology.yaml` → `FEATURE_IDENTITY_CHANGE` ·
`src/features/**` → `FORMULA_CHANGE`+`DERIVED_METRIC_CHANGE` · `feature_schema.py` →
`DATASET_SCHEMA_CHANGE` · `active_models.yaml`/`models/**` → `ACTIVE_MODEL_CHANGE` · `src/core/**`,
`execution_planner.py` → `RUNTIME_DECISION_PATH_CHANGE` · `scripts/**` → `SCRIPT_LIFECYCLE_CHANGE` ·
docs-only → `DOCUMENTATION_ONLY`.

GREEN_FLOOR is **imported**, not copied — `spec_from_file_location`, exactly as
`tests/test_governance_invariant_check.py:13-16` does.

Output carries per-row `evidence_class` plus a top-level `weakest_evidence_class` so a reader cannot
over-trust the aggregate, and an `inputs` block with per-artifact sha256 / availability.

### Draft manifest emission

`--emit-impact-manifest <out> --change-id CH-x [--write]` (stdout unless `--write`). Fills the computed
fields of `_IMPACT_MANDATORY` (`construction_protocol.py:45`): `change_classes`, `affected_files`,
`affected_feature_ids`, `affected_models`, `affected_production_config`, `required_checks_ack` — plus
underscore-prefixed `_generated_by` / `_evidence_classes` / `_caveats` (safe: `validate_impact` only checks
mandatory-field presence and literal `"UNKNOWN"` values).

**Deliberate:** `objective` and `rollback_boundary` emit as drafts **and** the emitter writes
`"unknowns": [{"question": "objective not authored by a human", "blocking": true}]`, so the raw draft
**fails `validate-impact`** until a human writes the objective. Two tests pin this
(`test_emitted_draft_manifest_fails_validate_impact`, and passes once filled). The engine computes the
mechanical 80%; it can never fake the authored 20%.

---

## Graph integrity validation

All in `src/governance/semantic_os.py`, each returning `list[ValidationError]` (`component_id`, `kind`,
`detail`) mirroring `framework_registry.ValidationError`.

1. `validate_schema` — required fields per kind, enums, types, `authority == "advisory"` pinned, summary caps
2. `validate_unique_ids_global` — CN/BD/JN/step ids unique **and disjoint from** all 12 ontology sections,
   F-, H-, MOD-, SCR-, framework ids, MIAR entry ids, closure `surface_id`s, `change_classes` keys
3. `validate_no_orphan_concepts` — every CN referenced by ≥1 BD **and** ≥1 JN step, or carries a non-empty
   `orphan_justification`; every BD has ≥1 concept and ≥1 resolved member; every JN has ≥2 steps
4. `validate_no_cyclic_ownership` — DFS-colour CN→`owner_boundary`→BD→`concepts`→CN and BD→`consumers`→BD;
   self-consumption is an error
5. `validate_bidirectional_consistency` — `CN.owner_boundary == BD` ⟺ `CN ∈ BD.concepts`
6. `validate_fk_resolution` — miar stage/entry, closure surface, ontology ids, findings (**reusing**
   `framework_registry.valid_finding_ids()`), hypotheses, framework ids, change classes, `book_chapter`
   exists **and** is in the README TOC, `topic_doc`, `canonical_source`, CN cross-refs
7. `validate_boundary_members` — every glob resolves to ≥1 real file; explicit paths exist; **no file
   claimed by two boundaries**; reports `unclaimed_objects`
8. `validate_spine_coverage` — a pinned `SPINE_FILES` set (`engine_runner.py`, `feature_pipeline.py`,
   `crt_engine_v2.py`, `fusion_engine.py`, `decision_engine.py`, `execution_planner.py`,
   `ultron_risk_gate.py`, `backtest_v2.py` + the 7 signal-flow step modules) is 100% boundary-claimed;
   monotonic `_BOUNDARY_COVERAGE_FLOOR` ratchet mirroring `_ATTRIBUTED_FLOOR`
9. `validate_journey_dag` — `order` 1..N contiguous & unique; `next` targets in-journey; **acyclic**; every
   step reachable from order-1; **every edge strictly forward in `order`**; ≥1 terminal;
   `async_feeders[].joins_at_step` resolves
10. `validate_journey_step_fks` — step `concept`/`boundary` resolve; boundary ∈
    `{concept.owner_boundary} ∪ related_boundaries`; **`failure_mode` ∈ `concept.failure_modes[].mode`**
11. `validate_evidence` — **reuses** framework_registry's `_resolve` + ±30-line symbol-drift window
12. `validate_alias_uniqueness` — concept names + aliases form one key domain; collision = error
    (fail-closed); collision with an ontology alias = warning
13. `validate_referenced_objects_reachable` — every referenced path exists; every `src/` object appears in
    `graph.dot` (absence ⇒ `stale_graph` error)
14. `validate_no_derived_in_source` — `_FORBIDDEN_HAND_FIELDS` absent from the YAML

### Negative (mutation) tests — required by repo precedent

Using the `_mutate(deepcopy)` pattern from `tests/test_semantic_registry.py:76-79`. One test per violation
class, each asserting the **specific** message substring (not merely "errors non-empty"):

`test_orphan_concept_is_caught` · `test_cyclic_ownership_is_caught` · `test_self_consuming_boundary_is_caught` ·
`test_duplicate_id_with_frozen_fm_is_caught` (`FM-002`) · `..._with_finding_is_caught` (`F-001`) ·
`..._with_mod_is_caught` (`MOD-0001`) · `..._with_scr_is_caught` (`SCR-001`) ·
`test_duplicate_concept_id_is_caught` · `test_unknown_miar_stage_is_caught` ·
`test_unknown_closure_surface_is_caught` · `test_unknown_ontology_id_is_caught` (`FM-999`) ·
`test_unknown_finding_is_caught` (`F-999`) · `test_unknown_change_class_is_caught` ·
`test_missing_book_chapter_is_caught` · `test_book_chapter_not_in_toc_is_caught` ·
`test_boundary_glob_matching_nothing_is_caught` · `test_file_claimed_by_two_boundaries_is_caught` ·
`test_empty_invariant_protected_is_caught` · `test_owner_symbol_drift_is_caught` ·
`test_journey_cycle_is_caught` · `test_journey_order_gap_is_caught` · `test_journey_backward_edge_is_caught` ·
`test_unreachable_journey_step_is_caught` · `test_step_failure_mode_not_declared_is_caught` ·
`test_step_boundary_not_owned_by_concept_is_caught` · `test_async_feeder_dangling_step_is_caught` ·
`test_bidirectional_mismatch_is_caught` · `test_missing_required_field_is_caught` ·
`test_derived_field_in_hand_source_is_caught` · `test_authority_must_be_advisory` ·
`test_ambiguous_alias_is_caught` · `test_referenced_object_missing_from_disk_is_caught` ·
`test_src_object_missing_from_graph_dot_is_caught` · `test_spine_coverage_floor_cannot_regress` ·
`test_summary_50_over_cap_is_caught`

**Positive/contract:** `test_live_registry_is_clean` · `test_seed_is_byte_identical_on_rerun` ·
`test_every_concept_has_nonempty_why_it_exists` · `test_all_seven_miar_stages_have_a_concept` ·
`test_journey_jn001_covers_signal_flow_steps_1_to_7_and_4_feeders`.

**Object/query/impact suites** carry their own negatives: no PROVEN import deps where the source is
unavailable; `owner_surface` never fabricated; every emitted field has a `FIELD_EVIDENCE_CLASS` entry;
ambiguous alias raises; no `Answer` row claims PROVEN from a name-based source; emitted draft manifest
**fails** `validate_impact`; impact output deterministic for a fixed seed.

---

## Build sequence

Each phase leaves the repo green and is independently verifiable.

**Phase 0 — Construction Protocol entry + track the inputs.** *(approval gate)*
`git add` the 6 untracked artifacts — a **targeted 6-file add, never `git add -A`** (standing blocker:
836 untracked / 68 in `src/`; a partial commit breaks the build). Write
`docs/governance/build_manifests/CH-semantic-os-v2.impact.json` classified
`["SCRIPT_LIFECYCLE_CHANGE", "DOCUMENTATION_ONLY"]`; run `validate-impact`. File the
`GOVERNANCE_REGISTRY_ADDITION` change-class gap as a tracked follow-up.

**Phase 1 — schema + registry core, walking skeleton.**
`src/governance/semantic_os.py` + the 3 YAMLs with 2 concepts / 2 boundaries / 1 journey +
`scripts/governance/seed_semantic_os.py` (**SITS same turn**) + `tests/test_semantic_os.py` with the full
mutation suite. Verify: tests green, seed byte-identical, `--validate` exit 0. No GREEN_FLOOR change yet.

**Phase 2 — Object layer + AST import census.**
`src/governance/semantic_objects.py` (incl. `ast_import_census()` covering the 783 files `graph.dot`
misses) + `--objects` on the seed CLI + `tests/test_semantic_os_objects.py`. Verify 844 objects and that
`coverage_gaps` matches the measured 38/21/9/411 deltas. **Record** the encyclopedia/attribution staleness;
do **not** regenerate those artifacts in this build (separate governed change).

**Phase 3 — author the real semantics.** *(approval gate + user participation — the largest phase)*
~50 concepts, ~40 boundaries, 4–8 journeys. Seeded from: `docs/intent_graph.md` (12 Chains, each already
carrying Thought / Goal / Belief / Economic Meaning / Architecture Decision / Modules / Runtime Effect /
Alignment Status — a near one-to-one match for `why_it_exists` / `why_this_design` / `invariants`),
`docs/intent/` (7 domain files), `docs/intent_to_code_map.md` (intent→file:line → BD `evidence[]`),
`docs/book/README.md` Concept Index (~20 concepts with canonical chapters → `book_chapter`),
`docs/topics/` (26 → `topic_doc`), `miar_registry.json` (17 entries × 7 stages → `miar_stage`,
`explicit_non_goals`, `falsification`), `closure_authority_index.json` (11 surfaces),
`WHAT_HOW_WHO_EXECUTABLE_BOUNDARY_MAP_V1.json` (→ `authority_layer` + several ready-made boundaries),
`signal-flow.md` Steps 1–7 + §2.1–2.4 + §3 matrix (→ JN-001).
Split **3a** mechanical extraction proposal (every field citing its source line) → user review → **3b**
commit. `why_this_design` / `alternatives_rejected` are historical facts; per §6.2 rule 3 and §6.6
"never fabricate", they must be user-confirmed, not invented.

**Phase 4 — L5 Semantic Query Engine.** `src/governance/semantic_query.py` +
`scripts/governance/query_semantic_os.py` (**SITS**) + `tests/test_semantic_query.py`.

**Phase 5 — L6 Impact Engine.** `src/governance/semantic_impact.py` + `--impact` /
`--emit-impact-manifest` on the existing CLI (no third script) + `tests/test_semantic_impact.py`.

**Phase 6 — enforcement + docs.** *(approval gate)*
GREEN_FLOOR additions + `test_governance_invariant_check.py` pins; `docs/reference/schemas.md`
§9.10–§9.13; `docs/governance/SEMANTIC_OS_CONTRACT.md`; SESSION LOG; `validate-completion` →
`CH-semantic-os-v2.completion.json`. Any `CLAUDE.md` edit is separately gated.

**Phase 7 — verification sweep.**

---

## Verification

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/seed_semantic_os.py
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/seed_semantic_os.py --objects
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --validate
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --summary
```

The five questions:

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --ask guarantees --target no_lookahead --json
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --ask owner --target "atr normalization" --json
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --ask writers --target execution_geometry --json
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --ask disproved --target CN-012 --json
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --ask authoritative --target CN-012 --json
```

L6:

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --impact src/features/feature_pipeline.py --json
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/query_semantic_os.py --impact src/features/feature_pipeline.py --emit-impact-manifest docs/governance/build_manifests/CH-probe.impact.json --change-id CH-probe
```

Tests:

```bash
D:/Tradelatest/.venv/Scripts/python.exe -m pytest -q tests/test_semantic_os.py tests/test_semantic_os_objects.py tests/test_semantic_query.py tests/test_semantic_impact.py
```

SITS (same turn as any new `scripts/**/*.py`):

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/analysis/script_census.py --write-stubs docs/governance/script_registry_stubs.jsonl && D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/seed_script_registry.py && D:/Tradelatest/.venv/Scripts/python.exe scripts/analysis/generate_script_matrix.py
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe -m pytest -q tests/test_script_registry.py tests/test_script_matrix_sync.py
```

Construction Protocol + green floor:

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/construction_protocol.py validate-impact docs/governance/build_manifests/CH-semantic-os-v2.impact.json
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all
```

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/construction_protocol.py check
```

Determinism — run the seed twice and compare hashes:

```bash
D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/seed_semantic_os.py --objects && sha256sum data/semantic_os/*.jsonl > /tmp/a.txt && D:/Tradelatest/.venv/Scripts/python.exe scripts/governance/seed_semantic_os.py --objects && sha256sum data/semantic_os/*.jsonl > /tmp/b.txt && diff /tmp/a.txt /tmp/b.txt && echo BYTE-IDENTICAL
```

---

## Known limits (stated, not hidden)

1. **Import edges are module-level, not call-level.** L6 answers "which modules could be affected", never
   "which function mutates which field."
2. **`citation-map.generated.md` has 18 symbols** with several bare basenames → doc-citation blast radius
   has low recall and is HEURISTIC.
3. **`owner_surface` is `UNATTRIBUTED` on 463/463 and `reachability` is `UNKNOWN` on all.** The Object
   layer will faithfully report 0% attribution. That will look alarming; it is the truth, and it is the
   gap the Boundary layer closes.
4. **The `~813` encyclopedia denominator is stale** (38 src + 21 root missing, 0 tests). Honest
   denominator is 844 code objects; the delta is recorded in `coverage_gaps`, not silently patched.
5. **No behavioural test coverage data exists** in the repo. `test_text_references` is textual and is never
   labelled coverage.
6. **Q1 (no-lookahead) can never return ANSWERED.** The enforcement set is provable; exhaustiveness is not.
7. **This layer is advisory (§6.5).** `authority: "advisory"` is pinned with a negative test. Boundary
   membership grants zero production authority; only demonstrated ΔG001 does.


================================================================================
SOURCE_FILE: docs/implementation_plan/yes-i-found-the-polymorphic-gem.md
SOURCE_BYTES: 14593
PART: 10/10 FILE 12/16
================================================================================

# Close the three real gaps in the Monthly TV ↔ Active Production comparison

## Context

The monthly comparison report **already exists** and is registered:
[reports/monthly_tv_vs_active_production_semantic_comparison.md](reports/monthly_tv_vs_active_production_semantic_comparison.md)
+ `.json` twin (2026-08-16), cited as Notes in F-074/F-075/F-076/F-077/F-078. It carries the
11-dimension table with verdicts and §6.8 tags, and its own lines 7–10 already disclaim the
Jul 15/20 episode work.

Three premise corrections verified against disk before planning (§6.2 rule 3 — surfaced, not
silently adopted):

| Claim | Verified truth |
|---|---|
| "Monthly report still missing" | Exists, 12.9 KB, registered in 5 findings |
| "Episode comparison used `v2_multi_2026_04` / schema v4.0 / 39 features" | `configs/production/ACTIVE_VERSION` = `v2_htfcrt_2026_08`; that string appears in **zero** TV/forensic artifacts. Schema is **v5.0 / 48** (`feature_schema.py:141,292`, F-076) |
| "Comparison is the missing deliverable" | The report is done; its *inputs* are incomplete — see below |

What is actually missing, and what this plan closes:

1. **TV coverage is 5 of ~22 trading days.** `01_h4_july_macro` (Jul 1→Aug 7) and
   `02_h4_july_setup` (Jul 10→Aug 1) — the only month-spanning shots — are defined in
   `shot_plan.json` but have no PNG and no sidecar. Jul 7–14 and Aug 1–6 have zero TV capture.
2. **H4 shots can never reconcile.** `capture_tv.py:391` gates the OHLC diff on
   `interval == "15"` because `engine_data.diff_table:288` hardcodes `cursor += timedelta(minutes=15)`.
   Both H4 sidecars carry `NOT_APPLICABLE` structurally, so any *new* macro H4 shot would too.
3. **SMC row 8 is presence-only.** The report states plainly that a human-eye check that a
   detected order block / FVG matches what is visible was not performed.

Outcome: the report's TradingView side becomes genuinely month-wide, H4 shots carry real
reconciliation verdicts, and row 8 upgrades from `TEST/CONTRACT GAP` to a verified row — or the
gaps are recorded as measured failures. No production behavior changes.

---

## Pre-registration (E-001 ritual — fix verdict rules BEFORE running)

Written into the manifest before any capture, so a result cannot be reverse-fitted:

- **H4 grid alignment is MEASURED, never assumed.** TradingView's `OANDA:XAUUSD` H4 bars are
  exchange-session anchored; the engine's are calendar-true broker-time buckets, and the resolved
  broker offset is **+3** (odd), so broker 00:00/04:00/08:00 map to UTC 21:00/01:00/05:00. The
  grids may not align 1:1. Candidate anchors are scored by actual OHLC agreement exactly as
  `resolve_offset` does, and **fail closed**: if no anchor is decisive, the sidecar keeps
  `status: NOT_APPLICABLE` with `reason: H4_GRID_UNRESOLVED`. An unresolved grid is a recorded
  absence, not a pass.
- **MATCH threshold is inherited, not re-chosen:** `MATCH_TOLERANCE = 3.0`,
  `DECISIVE_RATIO = 5.0` (`engine_data.py:24-25`). H4 bars aggregate 16 M15 bars, so absolute
  error scales — the H4 tolerance is stated as `16 × MATCH_TOLERANCE` **or** the tolerance is
  applied to the *mean* per-child error, decided and written down before the first H4 diff runs,
  never after seeing the number.
- **Corpus boundary is declared up front:** `data/XAUUSD_M15.csv` starts **2026-07-07 01:00**.
  `h4_july_macro` requests Jul 1 → Aug 7, so **Jul 1–6 has no engine bars at all**. That shot's
  reconciliation can cover Jul 7 onward only; the pre-corpus span is reported as
  `NO_ENGINE_BAR`, never silently dropped from the denominator.
- **SMC verification separates two claims:** a *mechanical* check (verifiable — e.g. the
  `pdh_distance` reference level equals the max of the prior day's TV bars in the sidecar) and a
  *visual* check (human judgment). Mechanical failures are defects; visual mismatch alone is
  `INSUFFICIENT EVIDENCE` pending user adjudication, not a defect.
- **Verdict vocabulary is the closed §6.8 set.** No row says "bug" without naming a contract.

`TASK_CLASS = OBSERVATION_ONLY` (`docs/governance/TASK_CLASSIFICATION_BEHAVIOR_POLICY.md:59-73`).

---

## Workstream A — H4 reconciliation (do this FIRST)

Ordered first deliberately: without it, every new H4 macro shot from Workstream B is captured
permanently unreconcilable, and re-capturing later is wasted browser work.

**Constraint to honor:** `engine_data.py:103-109` explicitly forbids re-implementing HTF
aggregation inside this tool ("duplicating HTF aggregation here would be a second, unverified
reimplementation of the same geometry the codebase's own doctrine warns against"). So do not
write new aggregation math — reuse the canonical builder.

1. **New `tools/tv_forensic/htf_bars.py`** — the only file that bridges the tool to `src/`.
   - Imports `ParentCandleBuilder` from [src/features/parent_candle.py](src/features/parent_candle.py:62)
     and `period_key`/`period_start` from `features.calendar_periods`. Uses the `sys.path`
     bootstrap pattern already in [scripts/research/htf_parent_telemetry_extract.py](scripts/research/htf_parent_telemetry_extract.py).
   - `aggregate_engine_bars(engine_bars, rule="H4") -> dict[datetime, Bar]`: feeds the M15
     `Bar`s through `ParentCandleBuilder` in chronological order, converts each closed parent
     back to `engine_data.Bar`. No-lookahead is inherited from the builder (only closed periods
     are ever exposed, `parent_candle.py:99-105`).
   - `resolve_htf_anchor(...)`: scores candidate grid anchors by OHLC agreement against the
     sidecar's TV bars, returning a decisive/not-decisive result mirroring
     [OffsetResult.decisive](tools/tv_forensic/engine_data.py:51) — including its D-2 anchor-floor
     rule (winner must match every usable anchor).
   - Optional-import guard: if `src/` is unimportable, callers fall back to today's
     `NOT_APPLICABLE` rather than crashing (matches the tool's existing Pillow/Playwright pattern).

2. **Generalize `engine_data.diff_table`** — add `step_minutes: int = 15`, replacing the
   hardcoded increment at `:288`. Default preserves current behavior exactly.

3. **Rewire `capture_tv.py:391-426`** into three branches: M15 → unchanged; supported HTF rule
   with a decisive anchor → real `OK`/`DIVERGENT` status; anything else → `NOT_APPLICABLE` with
   a specific reason (`H4_GRID_UNRESOLVED`, `SRC_UNAVAILABLE`, or the existing interval reason).

4. **Byte-identity gate (non-negotiable).** Extend
   `tests/test_tv_forensic_smoke.py::test_engine_data_decisive_reproduces_all_real_captured_shots`
   to assert the 5 existing M15 sidecars reproduce **exactly** under the refactor. Add H4 cases:
   aggregation correctness against a hand-checked parent, anchor resolution decisive/not-decisive
   branches, and fail-closed on `src/` absence.

5. **Backfill** the two existing H4 sidecars (`03_h4_jul27_31`, `09_h4_jul15_20`) from their own
   stored `bars` — deterministic, zero new capture, exactly the D-1 backfill precedent. Preserve
   originals as `*_PRE_H4RECON.json` (§6.2 rule 4).

---

## Workstream B — capture the missing month

Two tiers, because reconciliation and legibility have different needs. OHLC reconciliation reads
TV bars from the `tv_bridge` API into `bars_by_epoch` — **not** from pixels — so a dense wide
window still reconciles at full fidelity; only the *visual* dimension needs a readable frame.

1. **Reconciliation tier** — new wide M15 shots in `shot_plan.json` covering the two blind spans:
   `m15_jul07_14` (2026-07-07 01:00 → 2026-07-14 23:45) and `m15_aug01_06`
   (2026-08-01 00:00 → 2026-08-06 23:45), both `clock: broker`, plus a new preset
   `month-fill`. These close rows 1–2 across the whole corpus.
2. **Visual tier** — run the existing `--preset macro`, which already contains
   `h4_july_macro` + `h4_july_setup` + `h4_jul27_31`. With Workstream A landed these produce real
   H4 verdicts instead of `NOT_APPLICABLE`.
3. **Known risk to check, not assume:** `frame_shot`'s two-sided achieved-vs-requested assertion
   (`capture_tv.py:212-224`) may reject a 5-week window if `zoomToBarsRange` silently clamps. If
   it raises on `h4_july_macro`, report the framing failure and fall back to the `--via-ui`
   Go-to-date path; do not loosen the assertion — it is the guard that caught shot 04's original
   mis-framing.
4. Capture launches Playwright against tradingview.com (read-only page loads, writes only under
   `tools/tv_forensic/shots/`). Verified available: `playwright.sync_api` importable, chromium-1234
   present, Pillow 12.2.0.

---

## Workstream C — SMC visual verification (report row 8)

**New `scripts/research/smc_visual_verification.py`** (read-only; writes only under
`results/monthly_tv_semantic_report/`).

- `results/monthly_tv_semantic_report/smc_feature_month.json` stores only `{timestamp, value}`
  per hit — normalized distances, no price levels, so nothing drawable. Get real levels by
  calling the canonical detectors directly: [find_active_order_block](src/features/smc/order_block.py:55),
  [find_active_fvg](src/features/smc/fvg.py:40), [find_active_breaker](src/features/smc/breaker.py:25),
  [find_active_mitigation_block](src/features/smc/mitigation.py:25), plus
  `pdh_pdl_distance`/`eqh_eql_distance` in `levels.py`. Each returns a `Zone`
  (`_geometry.py:33`) carrying price edges. Reuse — do not re-derive.
- **Mechanical layer (verifiable):** for each feature with an independently checkable reference,
  assert it against the sidecar's own TV bars — e.g. the PDH/PDL level equals the prior day's
  max/min of TV bars; an FVG's edges equal the gap between the recorded bar pair; a `Zone` marked
  active is not already mitigated per `is_mitigated`. Emit pass/fail per instance.
- **Visual layer:** render zones onto the shot PNG reusing `annotate.py`'s `Frame`
  (`annotate.py:65`, price→y via the sidecar's `plot.price_calibration`), `dash_h`, `font`, and
  `stagger` — note `stagger` keys on `(event, broker)` post-D-6, so distinct zones at one price
  will not collapse onto a shared row. Output `<shot>_SMC_ANNOTATED.png`, one per feature family
  to keep frames readable.
- Deliverable for the user: annotated PNGs plus a per-feature mechanical pass/fail table. Row 8
  upgrades only for the claims mechanically proven; anything resting on eyeball judgment is
  presented for adjudication, not self-certified.

---

## Governance (required, not optional)

- **BUILD_IMPACT_MANIFEST first** — `docs/governance/build_manifests/CH-monthly-tv-coverage-h4-recon.impact.json`,
  modeled on `CH-crt-semantic-execution-reconstruction.impact.json` (report-only precedent) and
  `CH-parent-crt-caller-wire.impact.json` (fuller pair). Change classes:
  `SCRIPT_LIFECYCLE_CHANGE` (new script under `scripts/research/`) + `DOCUMENTATION_ONLY`
  (report edits). Mandatory fields per `construction_protocol.py:45-48`; any `unknowns` entry
  must be non-blocking or it halts.
  Validate: `python scripts/governance/construction_protocol.py validate-impact <manifest>`.
- **SITS registration** for the new script, same turn (`docs/reference/conventions.md` §2.1):
  `script_census.py --write-stubs` → **add a Python overlay in `seed_script_registry.py` with a
  real `purpose`** (stubs alone fail the PR-3 ratchet) → `seed_script_registry.py` →
  `generate_script_matrix.py`.
- **§6.7 grounding** — every repo path/symbol the updated report cites must return `GROUNDED`:
  `python scripts/governance/query_semantic_os.py --ground --kind IMPLEMENTATION --token <path> --symbol <Name>`
  and `--kind EVIDENCE --token F-0NN` for each finding.
- **Findings** — update the report + `.json` twin in place; append Notes to F-075 (H4 shots now
  reconciled / coverage closed), F-076 (row 8 outcome), F-079 (its `NOT_APPLICABLE` D-1 marker is
  now a real branch, not a permanent terminus). Register a **new F-id only if** H4 reconciliation
  finds genuine divergence — pre-registered as the sole condition, so a null result cannot be
  inflated into a finding. Never delete a superseded claim (§6.2 rule 4).
- **Untracked-tree note:** `reports/monthly_tv_*` and all of `tools/tv_forensic/` are currently
  untracked (review defect D-3). Flag for the user; do **not** `git add -A` — ~15 concurrent
  Claude sessions run against this repo.
- **Two logs** — codebase log `assistant_project.md` per §6.

---

## Verification

```bash
python -m pytest tests/test_tv_forensic_smoke.py -q
```

1. **Byte-identity** — the 5 existing M15 sidecars reproduce exactly under the refactored
   `diff_table` (the extended regression test). This is the pass/fail gate on Workstream A.
2. **Non-vacuity** — H4 diff must actually compare bars: assert `summary.compared > 0` on the
   backfilled H4 sidecars. A `compared: 0` "clean" result is the silent-gap failure F-079 exists
   to prevent.
3. **Coverage arithmetic** — regenerate
   `results/monthly_tv_semantic_report/ohlc_clock_reconciliation.json` and confirm
   `shots_never_captured` shrinks to `[]` and `unreconciled_shots` shrinks to `[]` (or names
   exactly which grid failed to resolve, with its reason).
4. **Full-month claim check** — the report's Coverage table must state the new true numbers
   (trading days covered / ~22) computed from the sidecars on disk, not asserted.
5. **Read-only posture** — verify by directory listing that nothing under `configs/`, `src/`,
   `data/`, or `configs/production/ACTIVE_VERSION` changed; only `tools/tv_forensic/shots/`,
   `results/monthly_tv_semantic_report/`, `reports/`, the new script, and tests.
6. `python scripts/governance/construction_protocol.py validate-completion <manifest>` —
   re-executes required checks; it never trusts logs.
7. Broader floors touched by the new script:
   `python -m pytest tests/test_script_registry.py tests/test_script_matrix_sync.py tests/test_current_findings.py -q`

---

## Out of scope

- **No production behavior change.** No `ACTIVE_VERSION` edit, no `parent_crt.objective_gate`
  flip, no model retrain (F-076's 6 stale families stay stale), no promotion. Grants no G001 and
  no authority (§6.5).
- **No economic claim.** Report row 11 stays `NOT ADMISSIBLE` — nothing here powers the n=2
  RETEST corpus.
- **CRT closure stays `REOPENED`.** Closure criteria are code-internal; this touches none.
- **Romeo/Sujan equivalence (F-077) stays NOT established** — better TV coverage does not
  adjudicate a semantic non-equivalence. The crosswalk machine-twin is a separate deliverable the
  user did not select.


================================================================================
SOURCE_FILE: docs/implementation_plan/yes-i-traced-the-floofy-forest.md
SOURCE_BYTES: 8451
PART: 10/10 FILE 13/16
================================================================================

# Plan — Register absolute ATR as a first-class ontology identity, fix F-072's 2 live sites

## Context

Previous phase of this session (fully executed, committed on `feature/truth-registry-v2`,
commits `788d499`…`2d9df3e`): restored 1,838 uncommitted files to git (half of `src/`, the
entire Semantic OS, CI, the pre-commit hook), and registered findings F-071/F-072/F-073
correcting and extending an earlier 27-hole architecture map. See that history in
`docs/current-findings.md`.

This phase addresses **F-072**: `compute_crt_levels` (`src/core/gate_intelligence.py:24-84`)
requires price-unit ATR, but the canonical `atr` feature is close-relative
(`atr_14_raw/close`). Three call sites feed the ratio into price-unit SL/TP arithmetic.

**Why now, and why this scope.** Verification (this session) found the root cause is not
three independent bugs — it's a **missing ontology node**. Absolute ATR (the quantity these
sites actually need) has no registered FM identity; it exists under three different names
(`atr_14_raw`, `atr_14`, `state.atr_abs`) with no single source of truth. The ontology
already documents this gap in its own words at `market_ontology.yaml:932`: *"No first-class
FM id exists for the bare absolute-ATR intermediate."* The same missing-node class has
already produced this exact defect **twice before** it hit F-072: the FM-050 runtime-metadata
mislabel (2026-07-19, 4 sites) and the FM-028 `depends_on` correction (2026-07-31). Patching
the 3 call sites without registering the node would be the fourth recurrence of the same root
cause — and would also violate CLAUDE.md §3.3b/§6.6 (new/renamed quantities are registered
through the ontology → registry chain first; "never local formula math").

**Reachability, verified this session (changes urgency, not scope):**

| Site | Status |
|---|---|
| `live_engine_hook.py:916` | Dead — `HookedLiveEngine` is never instantiated (F-073, parked) |
| `research/model_runners/adapters/execution_plan.py:279` | Registered in the model-runner registry, never actually run (no output under `results/model_runners/`) |
| `config_layer/execution_planner.py:390,403,406` | **Actually exercised** — `scripts/research/live_path_replay.py` ran it (BNB/BTC/ETH/SOL, `results/live_path_replay/`), but its own conclusion (0/35 trades reach execution — 3 unrelated upstream blockers) doesn't depend on entry-price geometry, and no registered finding cites this artifact. So: no contaminated conclusion today, but a live landmine the moment upstream blockers are fixed. |

**F-073 (no live rail) is explicitly parked** — scoped this session (repair = fix one bad
import + implement a `simulate_one` method that was speced but never built, for a
`write=False` diagnostic tool; the underlying `HookedLiveEngine` class already passes 36/36
tests) but deliberately not decided. This plan's work is valid and complete under either
future outcome of that fork.

## What to build

### 1. Register the ontology node

In `configs/formulas/market_ontology.yaml`, add a new `rolling_indicators` entry for
absolute ATR (proposed `FM-071` — next free id; confirm against the live registry at
execution time in case another id landed since). Model it on the existing `FM-041` (`atr`,
close-relative) entry immediately above it (`market_ontology.yaml:1065-1096`):

- `formula`: `SMA(<feature_pipeline.atr_period>) of true_range` (no `/close`)
- `depends_on: [true_range]` (FM-040)
- `units: price_absolute` (matching FM-040's convention, not FM-041's `dimensionless`)
- `source_of_truth`: both real producers — `feature_pipeline.py` (`atr_14_raw`, the pre-division
  intermediate inside `compute_canonical_volatility_features`) and `crt_engine_v2.py`
  (`state.atr_abs`, `compute_atr` at `:869-882`) — note in `semantics.description` that these
  are the same quantity computed twice on two independent code paths (not yet unified;
  unifying the *implementation* is out of scope here, only the *identity* is being registered).
- Cross-link: update FM-041's own note to point at the new node instead of only describing
  the gap in prose.

### 2. Re-point the two existing gap acknowledgments

- `market_ontology.yaml:932` (FM-028's note) — replace *"No first-class FM id exists…"* with
  a reference to the new node; change `depends_on` from `[candle_range, true_range]` to
  `[candle_range, <new-FM-id>]` if that's a closer match to what `displacement_atr_ratio`
  actually consumes (check `derived_math.displacement_atr_ratio`'s signature first).
- `market_ontology.yaml:1454-1456` (the `volatility_regime` node's note, FM-050 lineage) —
  same treatment: point `depends_on` at the new node instead of describing the workaround in
  prose.

### 3. Fix the 2 live (non-dead) call sites

- `src/config_layer/execution_planner.py:390,403,406` — `close` is already in local scope
  (`:389`). Change `atr = float(features["atr"])` to consume the absolute form:
  `atr_abs = float(features["atr"]) * close` (or read a newly-emitted absolute-ATR feature if
  one exists on this code path — check `features` dict contents at the call site first; if
  the feature pipeline doesn't emit an absolute form on this path, the multiply-by-close
  derivation is the correct fallback, matching the existing FM-030/031 `atr_absolute` arm
  precedent at `market_ontology.yaml:725,763`). Use `atr_abs` in the `0.1 * atr` LIQ_SWEEP
  branches.
- `src/research/model_runners/adapters/execution_plan.py:279-287` — same treatment;
  `close` availability needs a quick check at the call site (verify before assuming, unlike
  `execution_planner.py` where it's confirmed in scope).
- **Leave `live_engine_hook.py:916` alone** — F-073 is parked, so this site stays dead and
  unfixed; touching it now would be scope creep into the parked fork.

### 4. Extend `feature_math_lint.py` (the guard)

`scripts/analysis/feature_math_lint.py` currently enforces *who may derive a registered
name*. Add a second, narrower check: flag a call site where a name known to be
close-relative (`atr`, and by the same pattern `ema_spread`/`momentum_score` under the
default `normalization_basis`) is passed into a function/parameter whose docstring or
existing usage establishes it expects absolute/price-unit input, without an accompanying
`* close` (or equivalent) in the same expression. This is a narrower, more heuristic check
than the existing derivation lint — scope it conservatively (a few known dimensional pairs,
not a general unit-inference system) and expect it to need a `_KNOWN_DIVERGENCES`-style
allowlist for the FM-061-class consumers that read `atr` correctly today.

## Verification

1. `python scripts/governance/seed_semantic_os.py --check` and the ontology's own registry
   validator (`python -m features.registry` or whatever `validate_registry()` entry point
   `CLAUDE.md §6.6` names) — new node passes schema, no `UNKNOWN_*` dangling refs.
2. `pytest tests/test_formula_registry.py tests/test_feature_lineage.py tests/test_candle_math.py tests/test_derived_math.py` — the existing ontology floor stays green (these are in
   `GREEN_FLOOR`).
3. Byte-identity check on the canonical feature vector for at least one instrument (XAUUSD
   freeze-pin, per the FM-030/031 precedent) — registering a node and fixing 2 non-canonical
   call sites must not change any of the 39 vector values. `tests/test_feature_layer_freeze.py`.
4. `pytest tests/test_execution_planner.py tests/test_model_runners_execution_plan.py` — the
   two fixed call sites' existing test suites must still pass; add a new assertion that the
   LIQ_SWEEP entry-price offset is now `~0.1 * atr_abs` (price-unit magnitude), not
   `~0.1 * atr_ratio`.
5. Re-run `scripts/research/live_path_replay.py` for at least BNBUSDT and diff its
   `results/live_path_replay/` output before/after — since its own conclusion doesn't depend
   on entry-price geometry (verified above), the diff should be null or extremely narrow; if
   it changes trade counts, that's a signal something else was silently depending on the bug.
6. `python scripts/analysis/feature_math_lint.py --check` — 0 new violations after the guard
   extension (only pre-existing pinned divergences).
7. Update `docs/current-findings.md` F-072: flip `Status: OPEN` → `RESOLVED` (or partially —
   note explicitly that `live_engine_hook.py:916` remains unfixed pending F-073), per the
   §6.2 Findings Mandate, same turn as the code change.


================================================================================
SOURCE_FILE: docs/implementation_plan/yes-the-missing-invariant-tender-bengio.md
SOURCE_BYTES: 9904
PART: 10/10 FILE 14/16
================================================================================

# Documentation Drift Protocol + F-038 live reconciliation

## Context

**Why this change.** A repository governance discussion identified a missing invariant:
> *Every code/config/runtime-truth change must trigger a documentation-truth decision.*

The motivating example is **F-038** (the rr_fusion "fix"). Investigation this turn proved the
example is not hypothetical — it is a **live, in-flight split-brain right now**:

| Source | Says | rr_fusion deployed? |
|---|---|---|
| `current-findings.md:517,531` (F-038 header/body) | "FIX SHIPPED — disabled in `v2_multi_2026_04.json` (the file ACTIVE_VERSION points to)" | claims YES |
| **committed HEAD** `configs/production/ACTIVE_VERSION` | `v2_multi_2026_04 - deepdeektry` → loads `…- deepdeektry.json:50` `enabled: true` | **NO** |
| **working-tree** `ACTIVE_VERSION` (uncommitted `M`) | `v2_multi_2026_04` → loads `v2_multi_2026_04.json:34` `enabled: false` | YES (only once committed) |
| `docs/governance/finding_dependency_audit.md:94` (untracked, today) | "Fix NOT deployed to prod config" ⚠FLAG | NO (correct vs HEAD) |

The resolver is `src/config_layer/production_config.py:60` (`get_active_version`) → `:116`
(`Path(registry_dir)/f"{version}.json"`). The fix-edit landed on `v2_multi_2026_04.json`, but at
HEAD that file was **not** the active one (the deepdeektry variant was). So the finding's
parenthetical "(the file ACTIVE_VERSION points to)" was **false at HEAD** — a documentation claim
diverged from deployed reality, exactly the failure the protocol must prevent.

**Intended outcome.** (1) Encode the missing invariant as durable doctrine; (2) use F-038's live
drift as its worked first application — reconcile the truth so docs match deployed reality.

**Key constraint discovered — most of this already exists.** CLAUDE.md §6.2 (Repository Truth
Maintenance Doctrine) already covers ~80% of the proposed protocol: drift classification
(`ALIGNED`/`DOC_DRIFT`/`CODE_DRIFT`/`AMBIGUOUS` = rule 2), `TruthConflict` surfacing + "never
silently resolve, ask the user" (rule 3), Sync mandates (rule 6 + §6.3 citation + §6.4 topic +
Findings Mandate = Step 4), and CORRECTED/SUPERSEDED-not-delete + audit logs (rule 4, E-001 "fix the
SOURCE" = Step 5). The protocol must **extend**, not duplicate, these — per §6.2 rule 1
(existing-doc-first) and rule 5 (minimize doc count).

## User decisions (locked)

- **Placement:** thin rule inside CLAUDE.md §6.2 → long-form `docs/governance/` doc (mirrors the
  §6.1↔`intelligence-compounding.md`, §6.5↔`config-first-doctrine.md` pattern).
- **Approval-gate strength:** auto-fix clear `DOC_DRIFT` (code wins); **require user approval only
  for AMBIGUOUS/split-brain conflicts or conclusion downgrade/reversal**. Matches existing §6.2
  rules 2–3; avoids friction on routine doc fixes.
- **F-038:** reconcile now as the worked first application.

## Part A — Doctrine

### A1. Long-form doc: `docs/governance/DOCUMENTATION_DRIFT_PROTOCOL.md` (new)

Self-contained long-form, written as the expansion of the §6.2 thin rule (NOT a re-statement of
§6.2). Sections:

- **The invariant.** "Every code/config/runtime-truth change triggers a documentation-truth
  decision." Reporting a discrepancy is necessary but **not sufficient** — the turn is incomplete
  until the doc decision is made and recorded.
- **The 5-step process**, each cross-linking the §6.2 rule it operationalizes rather than redefining
  it: (1) Classify drift [§6.2 rule 2] → (2) Present impact: believed vs true, artifacts affected,
  whether a conclusion downgrades [§6.2 rule 3 `TruthConflict` shape] → (3) **Gate** [see A3] →
  (4) Synchronize all affected artifacts [§6.2 rule 6 + §6.3 + §6.4 + Findings Mandate] →
  (5) Audit-trail entry [§6.2 rule 4 + E-001 "fix the SOURCE not just chat"].
- **Audit-trail format**, aligned to the existing `finding_dependency_audit.md` Audit Log table:
  `Date · Cause of drift · Previous belief · New verified reality · Verification method
  (static / runtime / economic replay)`.
- **Completion criterion** (the genuinely new floor): a task touching governed code/config/runtime
  is not complete until — code done · tests pass · runtime verified · **doc-impact assessed** ·
  required (gated) doc updates approved · **audit entry recorded**. Extends the §7.4 SESSION LOG
  close, does not replace it.
- **Worked example:** the corrected F-038 story (from Part B) as the canonical illustration.
- **Authority note:** grants NO new authority — never bypasses §6 SESSION LOG, write-authority /
  path-guard, `y/N`, or the `APPROVE` promotion gate (consistent with every other §6.x doctrine).
  Ties to §6.5 Authority Ladder and E-001.

### A2. Thin rule in `CLAUDE.md` §6.2 (edit)

Insert a short **"Documentation Drift Protocol"** subsection within §6.2 (after the seven rules,
before the Findings Mandate), 4–8 lines: state the invariant + the gate + completion-criterion in
one paragraph, then point to the long-form doc. Add the doc to the §2 companion-docs table and to
the §6.2 record-systems pointer line. No renumbering of other sections.

### A3. The approval gate (the one true delta)

State the calibrated rule explicitly so it does not contradict §6.2 rule 2's auto-fix:
- **Auto-fix (no gate):** unambiguous `DOC_DRIFT` where code/config/runtime is plainly authoritative
  and no conclusion changes (e.g. a stale path, a corrected scope sentence).
- **Gate (user approval required):** `AMBIGUOUS`/split-brain (two authorities disagree, winner
  unclear) **or** any change that downgrades/reverses a registered finding's status/confidence, or
  edits an active config / `ACTIVE_VERSION`.

### A4. Enforcement (recommended, consistent with `project_doctrine_test_enforcement`)

This repo turns prose mandates into test floors. Add a lightweight `tests/governance/` test
asserting: (a) `docs/governance/DOCUMENTATION_DRIFT_PROTOCOL.md` exists and contains the invariant
sentence + the 5 step headers; (b) the §6.2 thin-rule pointer to it exists in `CLAUDE.md`. Mirror
the existing `tests/test_current_findings.py` / `test_session_log.py` style (string/section
presence, not behavioral). Keep it minimal — the gate and completion-criterion are process, not
unit-testable.

## Part B — F-038 live reconciliation (the worked first run of the protocol)

Apply the protocol to its own example. Classification = **AMBIGUOUS → resolved by §4.0 Tier-0**
(deployed runtime truth wins): the intended active config is `v2_multi_2026_04` (per F-016 doctrine
and the working-tree `ACTIVE_VERSION`), which deploys `enabled: false`.

1. **Establish canonical truth.** Confirm `ACTIVE_VERSION = v2_multi_2026_04` (working-tree value)
   is the intended Tier-0 truth → resolves to `v2_multi_2026_04.json` (`rr_fusion.enabled: false`).
   The HEAD value (`…- deepdeektry`, `enabled: true`) is the stale state the fix supersedes.
2. **Correct F-038 finding** (`docs/current-findings.md` ~`:531`): append a `CORRECTED:` note to the
   "Fix B SHIPPED" paragraph — at committed HEAD `ACTIVE_VERSION` pointed to
   `v2_multi_2026_04 - deepdeektry` (`enabled: true`), so the parenthetical "(the file ACTIVE_VERSION
   points to)" was false at HEAD; deployment is real only with `ACTIVE_VERSION=v2_multi_2026_04`
   committed. **Preserve history — do not delete** (§6.2 rule 4).
3. **Resolve the audit FLAG** (`docs/governance/finding_dependency_audit.md`): flip F-038 ⚠FLAG →
   RESOLVED, refresh the F-016 row note (`ACTIVE_VERSION` working-tree flip), and add a dated
   **Audit Log** row in the protocol's format. (File is untracked — also note it should be committed.)
4. **Surface the residual TruthConflict (gate, do NOT auto-resolve):** two config files now disagree
   — `v2_multi_2026_04.json` (`enabled: false`, `gaussian_impl: heuristic`) vs
   `v2_multi_2026_04 - deepdeektry.json` (`enabled: true`, `gaussian_impl: ml`). Per the user's
   gate, present this as a `TruthConflict` and **ask the user** whether the deepdeektry variant
   should be archived/removed or kept. Do not delete it unprompted.
5. **Memory:** update the F-038 memory file (`project_zone_gate_topk_config.md`, which carries the
   F-038 record) with the deploy-state correction; add the protocol as a new doctrine memory +
   `MEMORY.md` index line.

## Critical files

- **New:** `docs/governance/DOCUMENTATION_DRIFT_PROTOCOL.md`; `tests/governance/test_documentation_drift_protocol.py`
- **Edit:** `CLAUDE.md` (§6.2 thin rule + §2 table row); `docs/current-findings.md` (F-038 CORRECTED note);
  `docs/governance/finding_dependency_audit.md` (FLAG→RESOLVED + audit row + F-016 note)
- **Reference (read, do not duplicate):** `docs/governance/EPISTEMIC_INTEGRITY.md`,
  `docs/architecture/intelligence-compounding.md` (long-form pattern),
  `docs/research-readiness/config-first-doctrine.md` (long-form pattern)
- **Config decision (gated, no edit without approval):** `configs/production/ACTIVE_VERSION`,
  `configs/production/v2_multi_2026_04 - deepdeektry.json`
- **SESSION LOG:** append the §7.4 block to `assistant_project.md` (governed-doc change → codebase log).

## Verification

1. `pytest tests/governance/test_documentation_drift_protocol.py tests/test_current_findings.py -q`
   — new floor green; findings-index invariant (every non-terminal F-id ↔ table) still green.
2. `pytest tests/test_doc_citations.py tests/test_topic_docs.py -q` — no citation/topic drift from
   the edits.
3. Manual truth re-check: `git show HEAD:configs/production/ACTIVE_VERSION` vs working tree, and
   confirm `current-findings.md` F-038 + `finding_dependency_audit.md` now agree with the working-tree
   deployed reality (no remaining contradiction between the three sources in the Context table).
4. Confirm the SESSION LOG block is both shown and persisted to `assistant_project.md` (§6 mandate).


================================================================================
SOURCE_FILE: docs/implementation_plan/yes-the-sources-now-recursive-babbage.md
SOURCE_BYTES: 7766
PART: 10/10 FILE 15/16
================================================================================

# Backtest Trust Layer

## Context

**Why:** Research doctrine for this repo is `replay correctness > explainability > telemetry > advisory-AI > profit`. Before any further sweeps, OOS runs, or M4 qualification are trusted, the *measuring instrument* (the backtest accounting + metric layer) must be proven correct. An error near the top of the pipeline (prices → trade accounting → PnL → metrics) corrupts everything beneath it: optimizing a wrong PF is optimizing a bug, not an edge.

**Goal:** Establish a Backtest Trust Layer that (1) audits every trade-accounting and metric calculation, (2) fixes confirmed P0 correctness defects, and (3) institutionalizes the result with an independent recompute oracle + a byte-identical replay gate, so the numbers are reconciled before optimization resumes.

**Decisions taken (this session):**
- Deliverable = **Audit + fix confirmed P0 + institutional gate**.
- Intrabar close-only exit = **measure the realism gap, keep close-only as the default baseline**; promote any default change to a separate, evidence-gated decision (do not silently re-price all history).

## Confirmed findings (file:line evidence)

| # | Severity | Finding | Evidence |
|---|----------|---------|----------|
| F1 | P0 (leakage) | `center=True` swing detection: a swing flagged at bar *t-1* needs bars up to *t+SWING-1*, so the `.shift(1)` reference at decision bar *t* can absorb future-bar price info. Documented "backtest-valid, LIVE-UNSAFE" but **magnitude unquantified**. | `src/features/feature_pipeline.py:341-342`, consumers at `:359-360`, `:592-593` |
| F2 | P0 (realism) | Intrabar exit is **close-only**: a wick through SL/TP inside a bar never fills; exit triggers only when `candle.close` crosses the level. Understates stop-outs; distorts WR/RR/DD/PF/ROI. | `src/config_layer/crt_engine_v2.py:1962-1964` (called with `candle.close` from `backtest_v2.py:2178`) |
| F3 | P1 (RNG hygiene) | `on_trade_opened` calls `compute_fill_prices(...)` and **discards** all four results (`_, _, _, _ =`), then re-draws `entry_slip` again — burning RNG draws on a thrown-away computation; used entry/exit slips are not the paired pair. Deterministic (seed=42) but defective. | `src/runtime/backtest_v2.py:750-756`, `:385-396` |
| F4 | P1 (drift) | Divergent metric formulas across 4 modules: **PF ×3**, **expectancy ×4**, **max-DD ×3**, **win-rate ×2** — different units (R vs currency) and sentinels. Need to prove only the canonical `backtest_v2` path feeds `ConfigValidator`/promotion; quarantine/reconcile the rest. | `runtime/backtest_v2.py` (canonical) vs `analytics/performance.py:33-77`, `analytics/sl_tp_comparator.py:217`, `research/measurement/metrics.py:61-106` |
| F5 | P1 (consistency) | `score_std_dev` computed two ways: full std (`promotion_manager.py:382`) vs half-std penalty (`config_validator.py:197`). | as cited |
| — | OK | `slippage_seed: 42` (non-zero) → replay determinism preserved where threaded. Research harness uses sorted iteration + `sort_keys=True`. | `configs/production/v1_multi_2026_03.json:369`; `src/research/runner.py:102,124` |

## Workstreams

### WS1 — Trade-accounting & metric audit (read-only, produces findings doc)
Write `docs/analysis/backtest-trust-audit-2026-06-10.md` (point-in-time analysis, per `docs/analysis/` convention). For each of: entry/exit price, spread, slippage, commission (note: **none modelled** — flag), position sizing, planned RR, realized RR, per-trade PnL, aggregate PnL — record the authoritative `file:line`, the formula as written, units (R / pips / currency / %), and a verdict (correct / suspect / defect). Resolve F4/F5 by tracing which formula each *decision path* (`ConfigValidator.validate` → fitness gate; `PromotionManager`) actually consumes.

### WS2 — Fix confirmed P0/P1 defects (surgical, additive)
- **F3 (RNG hygiene):** in `runtime/backtest_v2.py:750`, remove the discarded `compute_fill_prices` call and source entry fill from a single paired draw (or call `compute_fill_prices` once and *use* its outputs). Preserve seed=42 determinism; regenerate the baseline ledger and document the (expected small) delta.
- **F4/F5 (formula unification):** make `backtest_v2` MetricsEngine the single source; have `analytics/*` and `research/measurement/metrics.py` either import the canonical helpers or be explicitly quarantined as non-decision analytics (docstring + assertion they never feed promotion). No magic-number formulas duplicated.
- **F1/F2 are NOT silently changed** — handled measure-only in WS4.

### WS3 — Independent recompute oracle + replay gate (the institutional layer)
- New `src/analytics/metrics_oracle.py`: **pure** functions that recompute PF, expectancy, win-rate, max-DD (R and %), total-return, CAGR, MAR **from the trade ledger alone** (`list[TradeRecord]` / `trades.csv`), independent of `MetricsEngine`. Config-driven constants via `get_prod_section`; no re-derivation of formulas inline.
- New `tests/analytics/test_metrics_oracle_parity.py`: run a backtest, then assert oracle output == reported `BacktestMetrics` within tight tolerance. Any divergence = a trust-layer failure.
- New `tests/runtime/test_replay_determinism.py`: run the same CSV+seed+config twice; assert byte-identical trade ledger + summary (formalizes `docs/architecture/replay-governance.md` §6 as an executable gate).

### WS4 — Exit-model realism measurement (measure-only, no default change)
Add a flagged intrabar high/low-touch detection path alongside close-only (config toggle, default = close-only). Run both on the standard universe; emit a comparison (`WR/RR/DD/PF/total-return` delta) into the audit doc. Same approach to **quantify F1**: run a causal (trailing) swing detector vs `center=True` and report the edge inflation. Output is evidence for a *future* gated decision — the live default does not move in this plan.

### WS5 — Governance: freeze optimization until reconciled
Document in the audit doc + `MEMORY.md` pointer: sweeps/OOS/M4 are **frozen** until WS3 parity + replay gates are green. Score against the Five Governance Questions. Append the §6 SESSION LOG entry to `assistant_project.md`.

## Critical files
- Read/trace: `src/runtime/backtest_v2.py` (accounting + MetricsEngine), `src/config_layer/crt_engine_v2.py` (exit logic, Trade), `src/config_layer/config_validator.py` (fitness gate), `src/governance/promotion_manager.py` (std-dev), `src/features/feature_pipeline.py` (swing lookahead).
- Edit (WS2): `src/runtime/backtest_v2.py`, `src/analytics/performance.py`, `src/analytics/sl_tp_comparator.py`, `src/research/measurement/metrics.py`.
- New (WS3/WS4): `src/analytics/metrics_oracle.py`, `tests/analytics/test_metrics_oracle_parity.py`, `tests/runtime/test_replay_determinism.py`, `docs/analysis/backtest-trust-audit-2026-06-10.md`, plus a config flag for the intrabar/causal-swing toggles in `configs/production/v1_multi_2026_03.json` (then `python scripts/maintenance/_compute_hash.py`).

## Verification
1. `pytest tests/analytics/test_metrics_oracle_parity.py tests/runtime/test_replay_determinism.py -v` → both green (oracle reconciles; replay byte-identical).
2. Full regression: `pytest` per `docs/TESTING.md` → no regressions from WS2 edits.
3. Re-run baseline backtest pre/post WS2 → ledger delta is only the expected RNG-hygiene change, documented.
4. WS4 comparison table present in the audit doc with concrete deltas; no change to live default exit/swing behavior.
5. Five Governance Questions scored; §6 SESSION LOG appended.

## Out of scope
Flipping the intrabar default to high/low touch (separate evidence-gated decision); commission modelling (flagged, not added); F1 causal-swing cutover for live mode; any new sweeps/optimization (frozen per WS5).


================================================================================
SOURCE_FILE: docs/implementation_plan/your-edge-research-platform-compiled-scott.md
SOURCE_BYTES: 5797
PART: 10/10 FILE 16/16
================================================================================

# ERP — Shape documentation hierarchy: add the Level-2 explanation layer

## Context
The owner wants shape knowledge organized as a **4-level read-order hierarchy** so any coding LLM knows
where to look, with a strict **authority gradient** — mathematics is authoritative; explanations and
stories are descriptive and carry no authority (never invert into a math source):

```
Level 1  SHAPE_LIBRARY.md            what mathematically exists   (AUTHORITATIVE, generated)
Level 2  shape_explanations.md  NEW  what each shape means to a human (NO authority)
Level 3  market_story_ontology.yaml  closest story family          (labels, no authority)
Level 4  REPORT.md                   why it matters / governance   (generated)
```

The gap is **Level 2** — there is no LLM→human explanation layer today. This increment creates it for the
only `LIBRARY_OK` unit (IC-003B Arm S N=4, 6 shapes `S_N4_k6_s00..s05`) and wires the read-order so it is
discoverable, **without letting explanations acquire authority**. Doc-only; research-only; no code path,
config, gate, or `ACTIVE_VERSION` change (§6.5).

## Governance decisions baked into the design (the reason this is safe)
1. **Authoritative source is `results/research/ic_003b/SHAPE_LIBRARY.md`** (the owner's note said `ic_003/`,
   but IC-003 is the *archived LIBRARY_FAIL* run with **no** shapes; the real shapes are in **`ic_003b/`**).
   Note this correction in the file header.
2. **Level 1 & 4 are GENERATED** — never hand-edit `SHAPE_LIBRARY.md` / `REPORT.md` (re-run clobbers them).
   All hierarchy pointers live in **hand-maintained** docs (the new file + the boundary registry).
3. **Anti-hallucination (H1/H2):** every shape's "Math" block is **grounded in real numbers** — the
   cluster's `medoid_trade_id`'s actual 38 entry features (from the trace corpus) + `outcome_mix_oos` +
   `tp_rate_oos` from `report.json`. No feature adjective is written unless the medoid/centroid numbers
   support it. The "LLM explanation" is an explicit human *gloss on those real numbers*, contributor-tagged.
4. **Robustness caveat with teeth (E-001):** these 6 shapes are the *only* OK unit and are **marginal**
   (G2 0.0561), **seed-fragile** (k\* unstable 4/6/12), and **near-noise** (silhouette ≈0.06, ~10-20%
   variance captured); Arm C reads as a weak continuum, not discrete archetypes. The file header states this
   prominently and every shape carries a `stability: LOW` field, so no reader mistakes a gloss for an
   archetype.

## Files
- **NEW `docs/research-readiness/shape_explanations.md`** (hand-maintained, Level 2). Structure:
  - **Header:** the 4-level read-order diagram; the AUTHORITY BOUNDARY (math authoritative; this file grants
    no authority — §6.5); the ROBUSTNESS CAVEAT (near-noise / seed-fragile / weak-continuum, cite the
    IC-003B robustness block); SOURCE run = `results/research/ic_003b/` verdict `IC003B_PARTIAL`.
  - **Per-shape (×6), run-sectioned `## IC-003B — Arm S N=4`:** `shape_id` · Math (medoid trade + its real
    entry features + `outcome_mix_oos` + `tp_rate_oos` + n_is/n_oos) · Representative trades
    (`representative_trade_ids_oos`) · **LLM explanation** (Claude-seeded, `contributor: Claude` tag; a
    factual gloss on the medoid's numbers) · Research note (`Descriptive only. Not predictive.` +
    `stability: LOW`).
  - **Contributor convention:** other models (GPT/Gemini/Grok) append their own `contributor:`-tagged
    explanation under a shape — never overwrite; disagreement is kept, not resolved into false consensus.
- **MODIFY `docs/research-readiness/erp-information-class-boundary.{json,md}`** — add a thin
  `shape_documentation_hierarchy` pointer (the 4 levels + the "no authority below Level 1" rule) under the
  IC-003B entry, so the ERP machine index carries the read-order. Bump doc-control to v1.3.
- **NEW (optional, recommended) `tests/research/test_shape_explanations.py`** — light floor: file exists;
  carries the no-authority + robustness caveat phrases; every `shape_id` it documents ⊆ the real ids in
  `results/research/ic_003b/report.json` (anti-drift / anti-hallucination). Skips if the results artifact is
  absent (gitignored). Mirrors `test_information_class_registry.py` discipline.
- **MODIFY `assistant_project.md`** — §6 SESSION LOG entry. **NEW memory** update (extend
  `project_ic003b_sequence_geometry.md` with the hierarchy, no new memory file).

## Reuse (do not reinvent)
- Grounding data: `results/research/ic_003b/report.json` (`arm_S["4"].shapes[*]`: `medoid_trade_id`,
  `outcome_mix_oos`, `tp_rate_oos`, `representative_trade_ids_oos`).
- Medoid feature lookup: the trace corpus `results/research/trace_corpus/xauusd/` (traces keyed by
  `trade_id` like `mean_reversion_010537`), same join the corpus builder used.
- Caveat text: the IC-003B `robustness` block already in the boundary registry (this session).
- Floor pattern: `tests/research/test_information_class_registry.py`.

## Explicitly NOT in this increment
No edit to generated `SHAPE_LIBRARY.md` / `REPORT.md`; no story-ontology change (Level 3 mapping is a later,
separate step and needs its own grant); no new engine / config / gate / `ACTIVE_VERSION` change; no
promotion — the explanation + story layers grant **no** authority; explaining a shape ≠ endorsing it.

## Verification
- `python -c "import json; json.load(open('.../erp-information-class-boundary.json'))"` valid.
- `pytest tests/research/test_information_class_registry.py tests/research/test_shape_explanations.py -q` green.
- Grep confirms `shape_explanations.md` documents exactly the 6 real `S_N4_k6_s*` ids, carries the
  no-authority + `stability: LOW` caveats, and its Math blocks cite real medoid trade ids present in the
  corpus (no invented feature adjectives).
