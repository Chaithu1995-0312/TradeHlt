# Architecture Truth Audit & Synchronization — Tradelatest

> Created: 2026-06-04 · Updated: 2026-06-04 · Milestone: cross-cutting (governance + Trd-track)
> Mode: evidence-only audit. Every claim cites `file:line` or is marked **NOT PROVEN** / **MISSING** / **DRIFT DETECTED**.

## Context

The user issued a 17-phase "Architecture Truth Audit" mandate: assume the architecture is wrong until proven, validate a **proposed pipeline** against the actual implementation, and produce a documentation-synchronization + correction plan. The proposed pipeline:

```
Execution:  MARKET DATA → FEATURE ENGINE → STATE ENGINE → TRANSITION GRAPH →
            PATTERN MEMORY LEDGER → BITNET FILTER → TRADENET MATCHER →
            LLM REASONER → ULTRON RISK GOVERNOR → ALERT ENGINE
Research:   FEATURE SPACE INTELLIGENCE → PATTERN DISCOVERY → PATTERN COURT →
            WALK FORWARD VALIDATION → SHADOW VALIDATION → QUANTUM OPTIMIZATION LAB
```

**Audit verdict (one line):** the *execution spine* is real and hardened; the *proposed "memory/learning" stages* (Transition Graph, Pattern Memory Ledger, Pattern Court, TradeNet wiring) are **MISSING or telemetry-only**, and the system's own living findings (F-001/F-005/F-011) already say intelligence is **not** the binding constraint — so the correct remediation is **truth-synchronization + a reproducibility foundation**, not building the killed stages.

**Approved scope (user):** (1) documentation truth-sync, (2) targeted code reliability fixes, (3) design the feature/state **persistence (reproducibility) layer**.

---

## DELIVERABLE 1 — Repository Truth Report (Phase 1 inventory)

### Execution spine

| Component | Status | Evidence |
|---|---|---|
| Market data ingest (Candle, M15 CSV, optional TimescaleDB) | **EXISTS** | `crt_engine_v2.py:95`; `agent/modes/pipeline_mode.py:80`; `data_ingestion/historical_fetcher.py:197` |
| Feature engine (38-dim `CANONICAL_FEATURES` v3.0, schema hash) | **EXISTS** | `features/feature_schema.py:46-122`; `features/crt_feature_builder.py:23` |
| Feature **persistence** of full vectors | **MISSING** | `feature_pipeline.py:786` (computed, not persisted); only 6-key snapshot in `logs/feature_snapshots.jsonl` (`engine_runner.py:55`) |
| State engine (9-state `CRTState`, `VALID_TRANSITIONS`) | **EXISTS** | `crt_engine_v2.py:63-72` (RANGE,SHADOW_PENDING,SWEEP,DISPLACEMENT,EXPANSION,EXPIRED,RETEST,EXECUTION,RESOLUTION); transitions `crt_engine_v2.py:1069` |
| State **persistence/versioning** across runs | **MISSING** | in-memory `EngineState` (`crt_engine_v2.py:250`); transitions streamed to `logs/crt_transitions.jsonl` but feature context empty |
| Transition **graph** (freq/expectancy/regime matrix) | **MISSING** | static `VALID_TRANSITIONS` only; no frequency/expectancy aggregation |
| Pattern Memory Ledger (state-seq → outcome → decay) | **PARTIAL / telemetry** | `replay/replay_memory_engine.py:113-249` clusters trades + 30-day decay, but cluster-keyed only, no state-sequence expectancy (F-012) |
| BitNet filter (live hard gate, `score<0.55` reject) | **EXISTS** | `crt_engine_v2.py:1793-1802`; persisted `backtest_v2.py:276`; `bitnet/bitnet_inference.py:317` (numpy fwd pass) — **adaptive threshold dormant** (hardcoded `0.55`, `:358`) |
| TradeNet matcher | **PARTIAL (built, unwired)** | `training/trade_net_v2.py` complete; fusion slot stub `fusion_engine.py:8`; `engine_runner.py:392` never passes `neural_fn` → `None` |
| LLM reasoner (tie-breaker, band 0.45–0.65, fail-open 1.0) | **EXISTS** | `config_layer/llm_inference_client.py`; `fusion_engine.py:610-652` (execution-authority isolation Trd-M5) |
| Ultron risk governor (7 checks, kill-switch) | **EXISTS (live-only)** | `core/ultron_risk_gate.py:69-87`; `live_engine_hook.py:864`; **not called in backtest** (`backtest_v2.py` zero hits) |
| Alert engine | **NOT PROVEN as discrete stage** | live outcome telemetry exists (`live_engine_hook.py:899`); no dedicated "alert engine" module found |
| Concept drift action | **PARTIAL (detect, no act)** | `features/feature_monitor.py`; `live_engine_hook.py:669-692` logs only (F-008) |
| Sidecar intelligence (CognitiveBus/ReplayMemory/HMF/Cluster) | **EXISTS (telemetry-only)** | `cognitive/cognitive_bus.py:12-15` ("NEVER returns to execution plane"); `engine_runner.py:429` fire-and-forget (F-012) |

### Research layer

| Component | Status | Evidence |
|---|---|---|
| Feature space intelligence | **PARTIAL (real, marginal, frozen)** | F-011; `analysis/feature-region-oos-persistence-2026-06-01.md:44`; `plans/probability-surface-advisory.md` SCOPED |
| Pattern discovery (scanner + expansion) | **EXISTS** | `scripts/research/opportunity_scanner.py`; `expansion/expansion_engine.py:24` |
| Pattern Court (DISCOVERED/VALIDATING/SHADOW/LIVE/DECAYING/KILLED lifecycle) | **MISSING** | no such state machine; closest = `ShadowPromotionGate` + `model_registry` promotion + Funding Ledger states (different topology) |
| Walk-forward validation | **EXISTS (no lookahead verified)** | `backtest_v2.py:4` "zero lookahead"; `training/trainer.py:489-527` expanding-window, no shuffle |
| Shadow validation | **EXISTS** | `governance/shadow_promotion_gate.py`; `promotion_log.jsonl` (v4 promoted 2026-06-02) |
| Quantum optimization lab | **MISSING** | grep `quantum\|qaoa\|annealing` → zero hits in `src/` |

### Governance

| Component | Status | Evidence |
|---|---|---|
| ConfigValidator (hard+soft gates) | **EXISTS, enforced** | `config_layer/config_validator.py` |
| PromotionManager (APPROVE-only) | **EXISTS, enforced** | `governance/promotion_manager.py:97` |
| `config_integrity` | **ORPHANED** | only caller = cutover script (F-006) |
| ACTIVE_VERSION | **v4_multi_2026_06** (governed) | `configs/production/ACTIVE_VERSION:1` (verified directly) |

---

## DELIVERABLE 2 — Architecture Readiness Report (proposed vs actual)

- **Stages 1–9 of the execution pipeline are largely buildable on top of what exists** — the spine (data→feature→state→BitNet→fusion→LLM→Ultron) is real.
- **"PATTERN MEMORY LEDGER" + "TRANSITION GRAPH" are the architecturally missing middle.** They are *named in the proposal as spine stages* but exist only as **telemetry sidecars** (F-012). They cannot become spine stages without the persistence layer (Deliverable 8C) because the data they need (full feature vectors + state sequences) is discarded.
- **TradeNet socket is empty by construction** (`fusion_engine.py:8`); wiring it is a 1-line init change but is **FROZEN-adjacent** — it has no training loop feeding it and findings say it is not the constraint.
- **Pattern Court + Quantum Lab do not exist.** Pattern Court's *intent* (promotion lifecycle) is partially served by `ShadowPromotionGate` + Funding Ledger. Quantum is **NOT PROVEN / MISSING** — treat as research-only, do not build.
- **Readiness conclusion:** the binding gap is **reproducibility/persistence**, not model intelligence. This aligns with F-001 (intelligence not binding) and is the prerequisite for *any* of the missing learning stages.

---

## DELIVERABLE 3 — Data Loss Report (Phase 2)

Path `raw candle → feature → signal → trade → outcome`; permanently discarded:

1. **Full 38-dim feature vector at decision time** — only a 6-key subset persists (`engine_runner.py:55`, `feature_snapshots.jsonl`). *Reconstruction: impossible without re-running the pipeline on identical OHLCV.*
2. **Per-candle indicator intermediates** (ATR/RSI/MACD/EMA) — not logged. *Reconstruction: recompute-only.*
3. **Feature-frame history** — `FeatureStore` bounded deque max 1000 (`core/feature_store.py:84`), lost on exit.
4. **State-transition feature context** — `crt_transitions.jsonl` records from/to/reason but `metadata.features` is empty.
5. **State-sequence probabilities** — no transition matrix; graph is deterministic, not probabilistic.

**Blocks future intelligence:** (1)+(4)+(5) make exact replay and "why was this trade rejected" forensics impossible, and make Pattern Memory Ledger / TradeNet training infeasible without recompute. **This is the #1 research-integrity finding.**

---

## DELIVERABLE 4 — Pattern Memory Readiness Report (Phases 5/6)

- Can map historical trade → preceding **cluster**? **YES** (`replay_memory_engine.py:194`).
- Can map historical trade → preceding **state sequence**? **NO** (state context discarded).
- Sequence expectancy (e.g. P(EXECUTION | EXPANSION→RETEST))? **MISSING.**
- Pattern decay? **YES** (exp decay, 30-day half-life, `replay_memory_engine.py:145`).
- **Verdict:** memory is **cluster-keyed telemetry**, not a causal state-sequence ledger. Readiness for the proposed Ledger = **blocked on persistence (Deliverable 8C)**.

## DELIVERABLE 5 — Feature Space Intelligence Readiness Report (Phases 3/14)

- Features reproducible **exactly**? **NO** (Deliverable 3). Schema *contract* reproducible (hash) — values not.
- OOS persistence real but marginal (F-011, retention 0.93–1.51, 6/8 zones negative). Advisory path **FROZEN** pending RME schema repair (done 2026-06-02, `project_rme_schema_repair`).
- Quantum lab: **MISSING**, research-only, do not build.

---

## DELIVERABLE 6 — Documentation Drift Report (Phase 15)

| # | Drift | Authoritative | Stale/Conflicting | Severity |
|---|---|---|---|---|
| D1 | Active prod config | `ACTIVE_VERSION` = **v4_multi_2026_06** (F-007) | `MEMORY.md` index ("Active prod = v2_multi_2026_04"); `user-progress-registry.md:10,124` | **HIGH** |
| D2 | Probability Surface state | `current-findings.md` Funding Ledger = **KILLED** | `plans/probability-surface-advisory.md` = "SCOPED, not implemented" | **HIGH** |
| D3 | Zombie plans | Funding Ledger: Liquidity V2 / TradeNet V2 / Prob-Surface = KILLED/FROZEN | `docs/plans/*` (63 files) carry **no** KILLED/FROZEN markers | **MEDIUM** |
| D4 | TradeNet v2 build status | F-005: BUILT-but-unwired | `analysis/audit-2026-06-02/dead-dormant-inventory.md` "designed-not-built" | MEDIUM (archived, dated) |
| D5 | BitNet adaptive threshold | F-004: dormant (hardcoded `0.55`) | code static `crt_engine_v2.py:358,1800` | LOW (frozen, documented) |
| D6 | Concept-drift gating | F-008: detect-not-act | `live_engine_hook.py:676` matches finding | LOW (gap documented) |
| D7 | Internal audit contradiction (this audit) | `CRTState` = 9 states (`:63-72`) | a sub-agent claimed 5 states — **rejected**, verified by direct read | resolved |

---

## DELIVERABLE 7 — Profitability / Impact Matrix

| Item | Profit | Research | Reliability | Maint | Priority |
|---|:--:|:--:|:--:|:--:|---|
| Feature/state persistence layer (8C) | ○ | ●●● | ●● | ● | **P1** (foundation) |
| Doc truth-sync D1/D2/D3 | ○ | ●● | ●● | ●●● | **P1** (cheap, stops rediscovery) |
| Act on concept drift (8B-ii) | ●● | ● | ●●● | ● | **P2** |
| Wire `config_integrity` at runtime (8B-i) | ○ | ○ | ●●● | ●● | **P2** |
| Backtest ↔ live parity (Ultron in backtest) | ●●● | ●● | ●● | ● | **P2** (F-010 OPEN: live PnL unverified) |
| Build Pattern Memory Ledger / Transition Graph | ? | ●● | ● | ●● | **P3** (gated on 8C; not the constraint) |
| Wire TradeNet / Pattern Court / Quantum | ✗ | ○ | ○ | ✗ | **DO NOT BUILD** (KILLED/FROZEN/MISSING) |

---

## DELIVERABLE 8 — Prioritized Remediation Plan (executable after approval)

### 8A — Documentation truth-sync (P1, doc-only, additive)
- **D1:** update `MEMORY.md` index line + `memory/project_trd_m6_downstream.md` ("Active prod = v2_multi_2026_04" → **v4_multi_2026_06**, cite `ACTIVE_VERSION` + promotion_log 2026-06-02). Update `docs/governance/user-progress-registry.md:10,124` (flip the v2 "active/SHIPPED" rows; never delete — supersede per §6.2).
- **D2/D3:** add a `> Status: KILLED — see current-findings Funding Ledger (F-001/F-011)` banner to `plans/probability-surface-advisory.md` and any plan implementing Liquidity V2 / TradeNet V2 / Prob-Surface. Do not delete plans (replay).
- **D4:** add a dated "SUPERSEDED by F-005" note atop `analysis/audit-2026-06-02/dead-dormant-inventory.md`.
- Per §6.1/§6.2: bump affected `docs/topics/*` + re-affirm findings dates.

### 8B — Targeted code reliability fixes (P2, each behind governance/promotion)
- **(i) Wire `config_integrity` at runtime (F-006).** Call `config_integrity` checks at config-load in `runtime/backtest_v2.py` + `inout/live_engine_hook.py` startup (fail-fast if active version ungoverned / validation_summary stale). Mirrors existing `_require` fail-fast pattern. Add config flag `governance.enforce_config_integrity`.
- **(ii) Act on concept drift (F-008).** In `live_engine_hook.py:669-692`, on **HARD** drift (Z>3.0) apply a size-down / block via a new advisory passed to `UltronRiskGateWrapper` (prescale only — never bypass the gate, SR-1). Config: `feature_monitor.hard_drift_action ∈ {log, size_down, block}` (default `log` to preserve current behavior). Backtest: instantiate `FeatureMonitor` for parity telemetry only.
- *(Backtest↔live parity — Ultron in backtest — flagged P2 but deferred to its own plan; F-010 is OPEN and larger.)*

### 8C — Feature/State persistence layer (P1 foundation, the reproducibility fix)
Goal: make every decision **exactly replayable** and unblock any future Ledger/TradeNet.
- **New module** `src/runtime/decision_recorder.py` (copy `docs/reference/example-service.py` template): on each decision, append a self-contained JSONL line to `logs/<instrument>/decision_vectors.jsonl` containing: `timestamp, instrument, schema_hash, candle_ts, full 38-dim feature vector, crt_state, prior_state, transition_reason, fusion_score, bitnet_score, decision, reject_reason`.
- **Wire** as fire-and-forget from `engine_runner.py` alongside the existing `FEATURE_SNAPSHOT_LOG` (extend, don't replace). Reuse `feature_schema.SCHEMA_HASH` for version stamping so vectors are invalidated correctly when schema changes (load-bearing per CLAUDE.md §4).
- **Config section** `inout` / new `decision_recorder` block (enable flag, path, max rotation) — no magic numbers; re-hash via `scripts/maintenance/_compute_hash.py`.
- **Storage:** JSONL only (no DB — convention). Size: comparable to `crt_transitions.jsonl` (~229MB observed) → add rotation.
- **Tests** `tests/`: APPROVE-path record written, schema_hash stamped, disabled-flag no-op, rotation boundary, vector round-trips to `extract_feature_vector` dim=38.
- **Determinism check:** replaying recorded vectors through `FusionEngine.evaluate` reproduces the logged `fusion_score` (no lookahead).

---

## DELIVERABLE 9 — Exact Files To Modify

- `MEMORY.md`, `memory/project_trd_m6_downstream.md` (D1)
- `docs/governance/user-progress-registry.md` (D1)
- `docs/plans/probability-surface-advisory.md` (+ other KILLED-initiative plans) (D2/D3)
- `docs/analysis/audit-2026-06-02/dead-dormant-inventory.md` (D4)
- `src/runtime/backtest_v2.py`, `src/inout/live_engine_hook.py` (8B-i, 8B-ii)
- `src/core/ultron_risk_gate.py` wrapper path (8B-ii prescale)
- `configs/production/v4_multi_2026_06*.json` + re-hash (8B/8C config)
- **NEW** `src/runtime/decision_recorder.py`, `tests/test_decision_recorder.py` (8C)
- `src/core/engine_runner.py` (wire recorder, 8C)

## DELIVERABLE 10 — Exact Documents To Update (per §6.1/§6.2 same-turn)

- `docs/current-findings.md` — re-affirm F-006/F-008 dates; add finding if drift-gating ships; index↔doc consistency (CI `tests/test_current_findings.py`).
- `docs/topics/*` for any touched concept (drift, governance, feature-schema, replay).
- `docs/reference/schemas.md §9` — document the new `decision_vectors.jsonl` line schema.
- `docs/reference/config-reference.md` — new config keys.
- `assistant_project.md` — SESSION LOG entry (§6).

---

## DELIVERABLE — Self-Critique (Phase 17)

- **Assumptions:** classifications rely on grep/explore breadth; an "alert engine" or quantum stub could exist under an unsearched name → marked **NOT PROVEN**, not MISSING-with-certainty for the alert engine.
- **Weak evidence:** transition-graph "MISSING" is from absence-of-search; a probabilistic matrix could be computed offline in an analysis script not yet found. Mitigation: 8C makes it constructible regardless.
- **Alternative interpretation:** the discarded feature vectors may be *intentional* (storage cost), and findings say intelligence isn't the constraint — so 8C's ROI is *research/reliability*, not profit. Stated honestly in the impact matrix (profit ○).
- **What could invalidate:** if a feature-vector dump already exists somewhere in `logs/` or `results/` that I didn't enumerate, 8C is partially redundant — **first step of 8C execution must grep `logs/`/`results/` for any existing full-vector dump before building.**
- **Bias check:** I deliberately did *not* propose building the proposed-but-killed stages (Pattern Court, TradeNet wire, Quantum) — risk is I'm over-trusting the Funding Ledger. Reopen only via documented Reopen Conditions (§6.2).

## Verification (after execution)
1. `python scripts/maintenance/_compute_hash.py` — config re-hash clean.
2. `pytest tests/test_decision_recorder.py tests/test_current_findings.py tests/test_topic_docs.py` green.
3. Run a short backtest with recorder enabled → `decision_vectors.jsonl` non-empty, dim=38, schema_hash stamped; replay reproduces `fusion_score` (determinism).
4. `grep` MEMORY/registry for `v2_multi_2026_04` → only superseded/historical references remain.
5. Toggle `feature_monitor.hard_drift_action=log` → behavior identical to today (safe default).
