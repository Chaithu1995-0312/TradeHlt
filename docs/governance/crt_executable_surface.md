# CRT Executable Surface Freeze — Phase 1

**Program:** CRT Closure (audit-first)  
**Phase:** 1 of 8  
**Status:** **PASS** — unique ACTIVE state-machine authority proven  
**Generated:** 2026-07-09 (UTC)  
**Pinned commit:** `ed1e418e47489dc8d76a2f7cc4e0cd340348b661` (worktree was DIRTY; inventory reflects code as read)  
**Active config:** `v2_multi_2026_04`  
**Machine-readable twin:** [`crt_executable_surface.json`](crt_executable_surface.json)

---

## Authority verdict

| Field | Value |
|---|---|
| **CRT_AUTHORITY_VERDICT** | **UNIQUE** |
| **CRT_ACTIVE_AUTHORITY** | `src/config_layer/crt_engine_v2.py` · `CRTEngine` (L2129) · `process_candle` (L2257) |
| **State enum** | `CRTState` (L64) — **9** members |
| **Transition map** | `VALID_TRANSITIONS` (L1075) · enforced in `StateMachine._transition` (L1095+) |
| **Config type** | frozen `CRTConfig` (L310) via `ConfigBuilder.build` |

### Why UNIQUE (not AMBIGUOUS)

Only **one** implementation:

1. Constructs `CRTEngine`, and  
2. Calls `process_candle` on the 9-state machine  

in production runtime code: **`src/runtime/backtest_v2.py`** (`CRTEngine(...)` @ L1776, `process_candle` @ L1948).

Other modules use the **name** “CRT” for **different roles**:

| Parallel | Path | Classification | Role |
|---|---|---|---|
| Fusion score slot | `src/engines/crt_engine.py` | **ACTIVE** | Scalar `compute()` for EngineRunner — **not** the SM |
| S01 strategy wrapper | `src/strategies/s01_crt_wrapper.py` | **ACTIVE** | Adapter over score slot; StrategyOrchestrator sidecar |
| Gaussian scorer | `src/config_layer/crt_gaussian_scorer.py` | **ACTIVE** | Scorer / F-050 name collision (Phase 2) |
| Sweep taxonomy | `src/config_layer/crt_sweep_taxonomy.py` | **ACTIVE** | Helper imported by SM |
| Feature builder | `src/features/crt_feature_builder.py` | **DEAD** | Zero call sites |
| Weekly research | `src/research/weekly_sweep/` | **RESEARCH_ONLY** | Separate ontology |

These are **not** dual state-machine authorities. Phase 1 does **not** treat name collision as SM split-brain.

### Live-path boundary (recorded, not a Phase 1 blocker)

`src/runtime/live_engine_hook.py` drives **EngineRunner** (`engines.crt_engine.compute` as the fusion “crt” score). It does **not** construct `CRTEngine` or call `process_candle`.

| Fact | Meaning |
|---|---|
| Backtest research spine | Full 9-state SM → `TRADE_OPENED` candidates (baseline: 13) |
| Live hook path | Fusion score path; SM not wired |

**Open item `OI-LIVE-SM`:** live/SM parity is deferred. It does not invalidate uniqueness of the SM implementation.

---

## CRT production surface (summary)

### Internal architecture (within `crt_engine_v2`)

```text
RangeDetector (L981)
    → StateMachine (L1088) + VALID_TRANSITIONS
    → UltronRiskEngine (L1528)   # CRT-internal gates (score/session/news/spread/BitNet)
    → ExecutionEngine (L1848)    # build_trade / open / exit updates
    → ResetLogic (L2074)
    → EventLogger (L444) + TelemetryCollector (L517)
Orchestrated by CRTEngine.process_candle (L2257)
```

### Production entry points

| Entry | Constructs SM? | Evidence |
|---|---|---|
| `backtest_v2.BacktestRunner.run` | **Yes** | L1776, L1948 |
| `backtest_v2.main` CLI | Yes (via runner) | L2671+ |
| `live_engine_hook` | **No** | L20 EngineRunner only |
| analysis monkeypatches | Research only | `scripts/analysis/p1_*`, `p3a_*`, `p3c_*` |

### Config construction chain

```text
instrument
  → market_router.get_crt_config (market_router.py:49)
  → ConfigBuilder.build / from_existing (config_builder.py:64+)
  → CRTConfig (frozen)
  → CRTEngine(config=...)
```

Direct `CRTEngine()` without config **raises** (L2141–2144).

### Environment overrides (names only)

| Env | Site | Effect |
|---|---|---|
| `TRUST_INTRABAR_TOUCH` | `crt_engine_v2.py:2151` | Overrides `exit_model` for intrabar vs close-only when set |

### Cached features (RETEST stamp)

Set at retest accept (`StateMachine` ~L1384):

`retest_depth`, `body_ratio`, `disp_strength`, `retest_index`, `session`, `double_sweep`

**Phase 2 note (F-050):** `retest_depth` here is **cross-candle displacement retrace**, not pipeline FM-021 same-candle `retest_depth`. Document only — no remediation in Phase 1.

### Candidate emission (`TRADE_OPENED`)

Site: `CRTEngine.process_candle` soft-conf approval path → `try_retest_to_execution` → `ExecutionEngine.build_trade` → event + action (`~L2733–2758`).

Action payload includes: `action`, `trade_id`, `risk_pct`, `live_metrics`, `state_after`.  
Event metadata includes: `id`, `session_name`, `S_score`, `sl`, `tp1`, `tp2`, `risk_pct`.

### Emitted actions (inventory)

`RESET`, `TRADE_*` (exits), `SHADOW_SWEEP_DETECTED`, `SWEEP_DETECTED`, `SHADOW_LEAK`, `SHADOW_EXPANSION_CONFIRMED`, `DISPLACEMENT_CONFIRMED`, `SWEEP_EXPIRED`, `EXPANSION_CONFIRMED`, `RETEST_CONFIRMED`, `EXPANSION_EXPIRED`, `EXPANSION_TTL_RESET`, `FILTER_REJECTED`, `SHADOW_ADVISORY_BLOCK`, **`TRADE_OPENED`**, `CONFIRMATION_FAILED`, `EVALUATING_SOFT_CONF`.

### Reset paths

Canonical: `StateMachine.reset_to_range` (L1439). Also `ResetLogic`, expansion TTL → `EXPIRED` → RANGE, filter rejects, soft-conf timeout, shadow advisory block, backtest gap-reset calling into SM.

### Persistence

No CRTEngine checkpoint/restore. Exports only: `dump_event_log`, `dump_telemetry`, `get_live_metrics`.

---

## Deferred / open items (frozen — do not work now)

| ID | Title | Resume when |
|---|---|---|
| **OI-ER-001** | 13-candidate EngineRunner admission provenance | After CRT CLOSED or re-auth |
| **OI-F048-E2E** | F-048 end-to-end reconciliation / split | After OI-ER-001 |
| **OI-GATE6** | Gate 6 remediation | After CRT closed + OI-ER-001 |
| **OI-ARCH-MS** | MarketSnapshot / StructuredOpportunity design | After CRT closed |
| **OI-LIVE-SM** | Live path does not wire CRTEngine SM | Later live/SM audit |

---

## Phase 1 stop conditions

| Check | Result |
|---|---|
| Unique ACTIVE SM? | **YES** — `crt_engine_v2.CRTEngine` |
| Parallel SMs? | **NO** |
| Name collisions without dual SM? | YES (score slot / S01 / scorer) — classified, not blockers |
| Live SM wired? | **NO** — recorded as OI-LIVE-SM |
| **PHASE1_STATUS** | **PASS** |
| **CRT_CLOSURE_STATUS** | not yet (Phases 2–8 pending) |

---

## What Phase 1 did **not** do

- No production code / config / model / formula / threshold changes  
- No EngineRunner admission provenance  
- No formula-contract deep dive (Phase 2)  
- No 9-state body-level graph expansion (Phase 3)  
- No remediation  

---

## Next step (requires authorization)

**Phase 2 — CRT input and formula contract**  
Map every raw/derived CRT value to Formula Registry / Market Ontology / Geometry Census; document F-050 boundary semantics without remediating.

---

## Return block (Phase 1)

```text
CRT_ACTIVE_AUTHORITY = src/config_layer/crt_engine_v2.py :: CRTEngine (L2129) / process_candle (L2257)
CRT_PARALLEL_IMPLEMENTATIONS = engines.crt_engine ACTIVE(score-slot); s01_crt_wrapper ACTIVE(sidecar);
  crt_gaussian_scorer ACTIVE(scorer); crt_sweep_taxonomy ACTIVE(helper);
  crt_feature_builder DEAD; weekly_sweep RESEARCH_ONLY
CRT_EXECUTABLE_SURFACE_PATH = docs/governance/crt_executable_surface.json
CRT_AUTHORITY_VERDICT = UNIQUE
OPEN_ITEMS_FROZEN = OI-ER-001, OI-F048-E2E, OI-GATE6, OI-ARCH-MS, OI-LIVE-SM
PHASE1_STATUS = PASS
NEXT = await Phase 2 authorization
```
