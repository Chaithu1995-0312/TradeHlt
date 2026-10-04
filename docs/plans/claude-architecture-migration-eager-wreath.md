# Architecture Migration — Event-Driven, LLM-Context-Economy Governance

> Created: 2026-05-28 · Updated: 2026-05-29 · Milestone: Trd-M0

## Context

Migrate Tradelatest toward an event-driven, replay-governed, explainable,
advisory-LLM, microservice-compatible architecture — **MAP before changing**.
Profitability is *not* the objective. Priority order: replay correctness >
explainability > telemetry continuity > advisory-AI > (structure validity ≠
execution validity).

Three exploration findings anchor the work:
1. **Migration is already underway.** `src/events/event_fabric.py` defines a canonical
   envelope (`event_id`, monotonic `generation`, `event_type`, `instrument`, `source`,
   ISO ts, `schema_hash`, `parent_event_id`, `payload`) with declared invariants. A
   `CognitiveBus`, `ReplayDriftGovernor`, and telemetry emitters already emit 5
   enveloped types. **Consolidate on this fabric — never fork it.**
2. **Decision spine is already microservice-clean** (config injected, structured dict
   returns): `EngineRunner → FusionEngine → DecisionEngine → ExecutionPlannerV1_2 →
   UltronRiskGate`. The coupling lives in the *orchestration* layer.
3. **LLM authority is already isolated** — no LLM on the replay hot path; fusion LLM is
   an uncertainty-zone tie-breaker; agent has path-guard + `y/N` confirm; promotion
   requires an `APPROVE` ValidationReport.

## North Star — Why these docs exist (LLM context economy)

The end state is an **LLM-event-microservices** architecture. Microservices beat "one
LLM holding all context" for one reason: **context economy**. Separating the system
into services — each with documented **ins / internal flow / outs** — lets a future
LLM load only the *one service* it's working on, never the whole codebase. Therefore:

- **Every doc is a self-contained, loadable context unit** (ins → flow → outs),
  readable without loading the code.
- `service-boundary-map.md` + the per-service human-language docs are the *primary*
  LLM context units.
- Telemetry is **curated into per-episode "LLM logs"** so context does not grow
  unbounded as logs accumulate — the LLM reads compact causal narratives, not the raw
  firehose.
- **Every application flow is captured/documented** so the LLM always has a map.

This north star ranks above refactor speed.

## The Five Governance Questions (gate for every recommendation)

1. Does replay remain deterministic?
2. Does telemetry remain comparable across runs?
3. Can this state be audited later?
4. Can an LLM reason about this event?
5. Is execution authority still isolated?

Encoded as a pre-merge checklist header in `assistant_project.md`.

## Decisions (confirmed)

- **Scope this pass:** six documents + **Trd-M1** (telemetry normalization, including the
  per-episode LLM log) + **Workstream A** (plan persistence). Trd-M2–Trd-M5 are roadmap only.
- **New-doc location:** `docs/architecture/`; `assistant_project.md` stays at repo root
  (existing canonical doctrine + SESSION LOG ritual, CLAUDE.md §6).
- **Per-service human-language docs:** `docs/architecture/services/<svc>.md` — one per
  service. Template defined now; individual files authored **on demand ("on ask")**.
- **LLM log:** a **per-episode SUMMARY** record — the full enveloped event stream rolled
  up into one record per CRT episode. Full firehose telemetry retained separately for
  audit.
- **First code seam:** telemetry normalization (Trd-M1).

## Workstream A — Persist session plans to `docs/implementation_plan/` (do first)

**Why:** Plan-mode files write to the *global* `~/.claude/plans/` (this plan lives at
`C:\Users\Hi\.claude\plans\claude-architecture-migration-eager-wreath.md`), shared
across projects and easy to lose. User wants every session's plan version-controlled.

- **A1 — Capture now.** Create `docs/implementation_plan/` and copy this plan into it.
- **A2 — Automate via `PostToolUse` hook (built with the `update-config` skill, which
  is authoritative for exact schema).** Fires on the `Write` tool; copies the file into
  `docs/implementation_plan/` only when (a) `file_path` is under `~/.claude/plans/` and
  (b) the hook `cwd`/`CLAUDE_PROJECT_DIR` is `D:\Tradelatest` (guard against other
  projects' plans). Notes: `ExitPlanMode` is *not* a hook event; `Write` passes
  `file_path` in `tool_input`; Windows runs PowerShell — use an `args` array + a stdin
  wrapper that reads the hook JSON, checks `cwd`, then `Copy-Item`. Place in
  **project** settings (`D:\Tradelatest\.claude\settings.json`).
- **A3 — Verify:** writing a throwaway plan lands in `docs/implementation_plan/`;
  writing a file *outside* the plans dir does not trigger a copy.

## Deliverables — Six Documents (in `docs/architecture/`, except assistant_project.md)

Authored from exploration evidence with concrete `file:line` citations. Each is a
standalone LLM context unit.

1. **`codebase-state-map.md`** — package tree + one-line role per module; decision-spine
   trace (class/method/file:line); hidden-coupling inventory (Tier 1–3 blockers:
   module-level config loads `llm_inference_client.py:82`/`config_validator.py:78`/all
   `strategies/S01–S10`; engine↔`core.model_registry` `ml_gaussian_engine.py:53`;
   upward governance→runtime `portfolio_validation.py:28`,`config_validator.py:146`;
   `live_engine_hook.py:85–96` singletons; hardcoded paths `ultron_risk_gate.py:44`).
   Per layer: behavior · hidden coupling · replay risk · missing telemetry · event
   boundary · microservice seam.
2. **`event-taxonomy.md`** — the 9 `EventType` members (`event_fabric.py:56–65`, which
   are emitted vs declared-only); 7 `CRTState` transitions (`crt_engine_v2.py:52–60`) +
   legal-transition graph; **enveloped vs non-enveloped split** (non-enveloped:
   `fusion_trades.jsonl` `trade_logger.py:121/153/178`, `sweep_trace.jsonl`,
   `integrity_events.jsonl`); full JSONL inventory; CRT lifecycle + **episode boundary**
   definition (feeds the LLM log); Mermaid state diagram.
3. **`service-boundary-map.md`** (keystone for context economy) — candidate services
   (Feature/Ingestion, Scoring, Decision Spine, Execution/Risk, Governance, Replay,
   Telemetry/Bus, LLM Advisory, Agent/Control-Plane). **Per service: inputs, internal
   flow, outputs (the LLM-loadable contract)**, current crossings, blockers, effort
   tier. Dependency-direction doctrine (governance/analytics must not import
   `runtime.backtest_v2` — invert via abstract interface). Mermaid dependency map.
4. **`replay-governance.md`** — comparability contract (same CSV + `BacktestConfig`
   incl. `slippage_seed` + `PROD_VERSION`); determinism guarantees (seeded slippage
   `backtest_v2.py:379`, timestamp-keyed feature lookup `:1620–1621`, `.shift(1)` lag);
   replay-risk register (`FeaturePipeline` `center=True` `feature_pipeline.py:341`
   live-unsafe; `datetime.now()` metadata-only; `schema_hash` passive/audit-only); no
   lookahead, deterministic seeds, env timestamps excluded from comparison.
5. **`llm-governance-layer.md`** — isolation evidence (fusion tie-breaker, fail-open
   neutral, agent path-guard `executor.py:27–31`, promotion `APPROVE`
   `promotion_manager.py:138–145`); doctrine (advisory, never execution authority);
   hardening (`GOVERNANCE_MODE` flag, decision-path assertions, `CIRCUIT_OPEN`
   monitoring-only); LLM advisory-call event contract (every call emits an enveloped,
   replayable, comparable event).
6. **`assistant_project.md`** (root, append) — doctrine header: the five governance
   questions as a pre-merge checklist, the priority ordering, "consolidate on
   `event_fabric`," and the migration-sequencing index. Preserves the SESSION LOG ritual.

## Deliverable — Per-service human-language docs (template + one exemplar)

`docs/architecture/services/<svc>.md`, one per service, written in plain English so an
LLM (or human) can load a single service's context without the code. **Template:**
Purpose (1 line) · Inputs (data + contracts) · Internal flow (happy path + key
branches, prose) · Outputs (data + contracts) · Events emitted · Replay notes ·
Upstream/downstream services. This pass: define the template + write **one exemplar**
(the Decision Spine) to validate it. Remaining services authored on demand.

## Migration Sequencing (surgical, reversible)

- **Trd-M0** ✅ COMPLETE — Map & doctrine (the six docs + service-doc template/exemplar). No behavior change.
- **Trd-M1** ✅ COMPLETE (2026-05-29) — Telemetry normalization + **per-episode LLM log**.
- **Trd-M2** ✅ COMPLETE (2026-05-29) — Event extraction (emit `CRTState` transitions + declared-silent EventTypes).
- **Trd-M3** ✅ COMPLETE (2026-06-01) — Orchestration de-coupling: `live_engine_hook`
  singletons → injectable `LiveEngineContext`; `config_validator` module-level config load
  deferred to a lazy cached `_gates()` accessor (+ PEP 562 `__getattr__` for back-compat).
- **Trd-M4** ✅ COMPLETE (2026-06-01) — Dependency inversion: `core/backtest_port.py`
  (`BacktestPort`/`BacktestResult`/`BacktestFactory` Protocols); `portfolio_validation` +
  `config_validator` build the runner via the injectable factory (no module-level
  governance→runtime import); monkey-patch of `BacktestRunner.run` removed.
- **Trd-M5** ✅ COMPLETE (2026-06-01) — LLM-layer hardening: `GOVERNANCE_MODE`
  (`core/governance_mode.py`, strict/advisory), decision-path isolation assertions
  (fusion `evaluate()` + `UltronRiskGate.evaluate()`), `LLM_ADVISORY` enveloped advisory
  event. **Follow-up:** the LLM-client import-time config deferral was spun out (fragile
  cross-module refactor touching default-arg snapshots in already-fragile connectivity-test
  modules) — see plan `trd-m0-m5-tender-bentley.md §5.2b`.
- **Trd-M6** 🅿️ PARKED — Scenario-Aware Decisioning (first *capability* milestone; Trd-M0–Trd-M5 are
  all infrastructure and add no new decision capability). Definition + entry gate below.

Each step is scored pass/fail against the five governance questions.

## Trd-M6 🅿️ PARKED (decided 2026-06-01) — Scenario-Aware Decisioning

> Two-track context: this is **Trd-M6** (trading track), distinct from **Gov-M6** (governance track).
> See [`docs/architecture/roadmap.md`](../architecture/roadmap.md). Trd-M0–Trd-M5 make the
> "should we trade?" engine clean/replayable but add **zero new capability**; Trd-M6 is the
> first milestone that adds engine capability.

**What it is (reframed from "Scenario Intelligence"):** make every accepted signal
*forward-conditional* — it carries a small **enumerated, deterministic** scenario set
(continuation · sweep-trap · invalidation) with explicit invalidation/confirmation
conditions, **consumed at two boundaries that already exist**: `UltronRiskGate`
(probability-weighted sizing) and the in-trade management surface (dynamic invalidation
exit, replacing the static bracket + breakeven rule at `runtime/backtest_v2.py:2059-2094`).
The orphaned `src/regime/market_state_cluster_engine.py` (already emits
`BREAKOUT_CONTINUATION` / `RANGE_TRAP` / `VOLATILE_REVERSAL` / `trap_probability` /
`compression_score`, currently unwired) becomes the scenario-*prior* input rather than
dead code.

**Explicitly NOT Trd-M6:** a learned probabilistic path-tree / Monte-Carlo over futures with
expected-RR-per-scenario. Deferred to Trd-M7 — it collides with the #1 priority (`replay
correctness`) and the doctrine (LLM is a tie-breaker, **not** a hot-path dependency;
no-lookahead in replay). The deterministic enumerable set respects all three; a learned
distribution does not.

**Why the real gap is a consumer, not a forecaster:** scenario-flavored signal already
exists unconsumed (the orphaned regime engine proves it). A richer distribution layered
on a static-bracket engine produces *inert telemetry*, not edge. Trd-M6 builds the consumer.

**Doctrinal constraints (the five governance questions):** deterministic replay
(cluster/rule-based scoring, byte-identical across runs); no-lookahead (scenarios scored
only from candles ≤ now; invalidation is a forward *rule* evaluated as candles arrive);
LLM stays advisory; **ship measure-only first** (additive scenario telemetry, no gating)
per the proven Phase-6 ROI pattern, then connect a consumer, then gate.

**Entry gate — BOTH must hold before Trd-M6 leaves "parked":**
1. **Infra:** trading-track Trd-M3, Trd-M4, Trd-M5 complete (the foundation Trd-M6 consumes). *Today only
   Trd-M0/Trd-M1/Trd-M2 are done.*
2. **Empirical floor:** the throughput/validation gap is closed — Phase 5a (threshold
   sweep) + Phase 6c (session-config sweep) land, and the engine clears a
   minimum-trade-count + stable-PF floor (exact threshold = operator's call; proposed: a
   sweep configuration producing a materially larger, still-profitable trade sample than
   today's 15 — MEMORY `project_phase6_roi_baseline.md` / `project_phase6b_funnel_diagnosis.md`).

## Trd-M1 ✅ COMPLETE (2026-05-29) — Telemetry Normalization + LLM Episode Log

**Goal:** bring trade-domain JSONL onto the canonical envelope **and** add a curated
per-episode LLM log — without changing any decision, replay, or profitability behavior.

**Part 1 — Envelope the trade writers.**
- Targets: `trade_logger.py` (`_write :190`, records `:120/:152/:177`) and
  `sweep_trace_logger.py`.
- **Documented exception:** `integrity_events.py` *intentionally* avoids `event_fabric`
  (docstring `:16–18`) so it stays importable from `scripts/`; its `{ts,event,severity,
  source,payload}` shape is already auditable. Recorded as a deliberate exception in
  `event-taxonomy.md` — **not migrated**.
- Approach: add an additive `EventType` (e.g. `TRADE_LIFECYCLE`) or reuse
  `DECISION_SNAPSHOT` (decide in `event-taxonomy.md`); **grep consumers** of
  `fusion_trades*.jsonl` first → default to **dual-write** (legacy flat file untouched +
  new enveloped stream) unless grep proves in-place wrap is safe; wrap legacy record as
  `make_event_envelope(..., payload=<record>)`.

**Part 2 — Per-episode LLM log (`logs/llm_episodes.jsonl`).**
- A **deterministic, read-only projection**: a per-episode aggregator rolls up all
  enveloped events within one CRT lifecycle episode (`RANGE → … → RESOLUTION` or
  `EXPIRED`, boundary reuses `EpisodeMarker`/`CRTState` `crt_engine_v2.py:52–60,:150`)
  into **one summary record**, flushed at episode close.
- Summary payload: `episode_id`, `instrument`, `state_path` (the transition sequence),
  entry/exit (candle ts + prices), `decision` + `reason`, key features at decision,
  outcome (`rr`, `win`), drift severity, governance flags, and **`child_event_ids`**
  linking back to the full firehose for audit drill-down.
- It **never influences a decision** (execution authority isolated). Uses **candle
  timestamps**, not wall-clock, so episodes are replay-comparable.

**Replay/comparability guardrails (load-bearing):**
- ENTRY/EXIT keep using candle time (`opened_at`/`closed_at`); never wall-clock.
- Envelope `event_id` / `generation` / wall-clock `timestamp` are **NOT replay-
  comparable** — comparison keys on `payload` + candle ts. `generation` may interleave
  with threaded `CognitiveBus`; never use for cross-run correlation.
- The episode summarizer must be deterministic: same CSV + seed → byte-identical
  `llm_episodes.jsonl` payloads.

## Rollback Strategy

- Docs (Trd-M0): `git revert`.
- Trd-M1: additive. Part 1 dual-writes (legacy file untouched) until an explicit cutover;
  Part 2 writes a brand-new log only. No telemetry field removed without a documented
  superseding field (continuity rule). Hook (A2) is removable by deleting the
  settings.json entry.

## Telemetry Contracts

- Every cross-component event uses `make_event_envelope()` (fabric invariant #1).
- `schema_hash` on every event; offline audit vs current `FEATURE_ORDER_HASH`.
- **LLM episode log:** exactly one record per closed episode; fixed payload schema;
  `child_event_ids` resolve to real firehose events; replay-comparable on candle ts.
- No field removed without a superseding field; renames documented old→new in
  `event-taxonomy.md`.

## Verification

**Docs (Trd-M0):** every `file:line` resolves (spot-check); enveloped/non-enveloped
inventory matches actual writers; Mermaid parses; service-doc exemplar matches code.

**Trd-M1 (determinism is the acceptance gate):**
- Baseline run on fixed CSV + `slippage_seed`; snapshot `{instrument}_trades.csv` +
  `{instrument}_summary.json`.
- Apply Trd-M1, re-run identical CSV + seed → trade ledger + summary **byte-identical**.
- New enveloped trade events carry every legacy payload field (dual-write: legacy file
  unchanged). `llm_episodes.jsonl` **byte-identical across two identical runs**; each
  episode's `child_event_ids` resolve to real firehose events.
- Run `pytest` per `docs/reference/testing.md`.
- Append SESSION LOG ENTRY to `assistant_project.md`.

**Workstream A:** hook fires for plans-dir writes only, and only in this project's cwd.

## Out of Scope (this pass)

- Trd-M2–Trd-M5 not executed; per-service human docs beyond the one exemplar are on-demand.
- No config edits/rehash/promotion; no profitability tuning; no blind rewrites; no new
  parallel event system; `integrity_events.py` untouched.
- Trd-M1 must not alter any decision, gate, or replay behavior — logging/projection only.
