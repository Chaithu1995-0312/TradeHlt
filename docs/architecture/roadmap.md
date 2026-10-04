# roadmap.md — Two-Track Milestone Map

> **Purpose:** One screen that separates the **two milestone tracks** which both use the
> labels M1–M5 and were becoming intertwined. This doc is a *router*: each row points to
> the canonical home that owns the detail. It does not redefine those docs.
>
> Created: 2026-06-01 · Updated: 2026-07-20 · Anchored to `v2_multi_2026_04`.

### Active engineering focus (2026-07-20)

Feature-layer free-form work is under a **governance** freeze
[`FEATURE_LAYER_MUTATION_FREEZE = ACTIVE`](../governance/feature-layer-mutation-freeze-2026-07-20.md)
(XAUUSD feature-matrix pin + schema/source SHAs + floor tests — **not** scientific closure).
**Default next work** is the
[`backtest/runtime roadmap`](../implementation_plan/backtest-runtime-roadmap-2026-07-20.md)
(runtime benchmarks open at R-1/R-2). M16 consumer-alignment and other named future programs
remain explicit exceptions, not the default queue.

---

## 0. The rule (read first)

**The `M1`–`M5` labels mean different things in each track. Never cross-reference a
milestone by number alone** — always qualify it: "governance M3" vs "trading M3." A bare
"M3" is ambiguous and is the source of the confusion this doc exists to end.

Two tracks, two purposes:

- **Governance track** — controls *ideas, decisions, and execution discipline*. "Can we
  trust how this idea moved through the system, and can we replay why?"
- **Trading architecture track** — controls *the engine itself*. "Is the engine
  replayable, observable, decoupled, and governable?"

They are orthogonal. Governance can advance while the engine is frozen, and vice versa.

---

## 1. Governance track (controls ideas / decisions / execution)

Home of record: [`idea-governance-framework.md`](idea-governance-framework.md) (the rules,
Gov-M1) + [`user-progress-registry.md`](../governance/user-progress-registry.md) (the live
operational view, Gov-M2).

| Milestone | Title | Status | Canonical home |
|---|---|---|---|
| Gov-M1 | Idea Governance Framework | ✅ Promoted / SHIPPED | [`idea-governance-framework.md`](idea-governance-framework.md) |
| Gov-M2 | User Progress Registry | 🟡 Forming / ACTIVE | [`user-progress-registry.md`](../governance/user-progress-registry.md) |
| Gov-M3 | Mandatory Review Checklist | ⏳ Forming / IDLE | registry row `Gov-M3` (idea-gov §3 P4) |
| Gov-M4 | Replayable Decision Journal | ⏳ Forming / IDLE | registry row `Gov-M4` (idea-gov §11) |
| Gov-M5 | Automated Governance Audits | ⏳ Forming / IDLE | registry row `Gov-M5` (idea-gov §9 T5/T6) |

Two-axis status (epistemic `State` + operational `Progress`) is defined in
[`user-progress-registry.md §4`](../governance/user-progress-registry.md). Gov-M3/M4/M5
are *designed but not built* — they exist as `Forming` Bricks in the registry, not code.

---

## 2. Trading architecture track (controls the engine)

Home of record:
[`claude-architecture-migration-eager-wreath.md`](../plans/claude-architecture-migration-eager-wreath.md)
(the migration plan + sequencing). Doctrine block lives at the top of
[`assistant_project.md`](../../assistant_project.md).

| Milestone | Title | Status | What it adds |
|---|---|---|---|
| Trd-M0 | Doctrine / Mapping | ✅ COMPLETE | the six architecture docs + service template |
| Trd-M1 | Telemetry normalization | ✅ COMPLETE (2026-05-29) | enveloped trade writers + per-episode LLM log |
| Trd-M2 | Event extraction | ✅ COMPLETE (2026-05-29) | emit CRTState transitions + silent EventTypes |
| Trd-M3 | Orchestration decoupling | ✅ COMPLETE (2026-06-01) | `live_engine_hook` singletons → injectable `LiveEngineContext`; `config_validator` config load deferred (lazy `_gates()`) |
| Trd-M4 | Dependency inversion | ✅ COMPLETE (2026-06-01) | `core/backtest_port.py` Protocol; `portfolio_validation` no longer imports `runtime.backtest_v2` at module level nor monkey-patches the runner; consumers use injectable factory |
| Trd-M5 | LLM-layer hardening | ✅ COMPLETE (2026-06-01) | `GOVERNANCE_MODE` (`core/governance_mode.py`), decision-path isolation assertions (fusion + Ultron), `LLM_ADVISORY` enveloped advisory event. *Follow-up:* LLM-client import-time config deferral (§5.2b) spun out — fragile cross-module refactor |
| **Trd-M6** | **Scenario-Aware Decisioning** | **🅿️ PARKED** | **first capability milestone — see §3** |

**Key fact:** Trd-M0…M5 are **all infrastructure** — they make the existing
"should we trade?" engine clean and replayable but add **zero new decision capability**.
**Trd-M6 is the first milestone that adds engine capability.** Trd-M0–M5 are now **all
complete (2026-06-01)** — the full infrastructure track is done; the Trd-M6 entry gate's
infra precondition is satisfied (the empirical-throughput floor remains the other half).

---

## 3. Trd-M6 — Scenario-Aware Decisioning (PARKED)

Full definition + entry gate live in the migration plan
([`…eager-wreath.md` → Migration Sequencing](../plans/claude-architecture-migration-eager-wreath.md)).
Summary:

- **What:** every accepted signal becomes *forward-conditional* — it carries a small
  **enumerated, deterministic** scenario set (continuation · sweep-trap · invalidation)
  with explicit invalidation/confirmation conditions, **consumed** at two existing
  boundaries: `UltronRiskGate` (probability-weighted sizing) and the in-trade management
  surface (dynamic invalidation exit, replacing the static bracket + breakeven rule at
  `runtime/backtest_v2.py:2059-2094`). The orphaned
  [`market_state_cluster_engine.py`](../../src/regime/market_state_cluster_engine.py)
  becomes the scenario-*prior* input rather than dead code.
- **NOT Trd-M6:** a learned probabilistic path-tree / Monte-Carlo over futures — that is a
  later milestone; it collides with `replay correctness` (#1 priority) and the
  advisory-LLM / no-lookahead doctrine.
- **Why parked (decision 2026-06-01):** (1) the infra foundation isn't built —
  Trd-M3/M4/M5 are pending; (2) the engine is throughput-starved and barely validated
  (15 trades), and the #1 ROI lever is the SESSION config, not a new intelligence layer
  (MEMORY `project_phase6b_funnel_diagnosis.md`). Scenario logic on a 15-trade sample
  risks fitting noise.
- **Entry gate (BOTH required):** Trd-M3/M4/M5 complete **and** the empirical validation
  floor cleared (Phase 5a threshold sweep + Phase 6c session sweep → materially larger,
  still-profitable trade sample).
- **Entry-gate status (2026-06-01):**
  - *Infra half — DONE.* Trd-M3/M4/M5 complete (suite 1211 passed / 0 failed).
  - *Empirical half — PARTIAL (session sweep done; see
    [`docs/analysis/session-sweep-bnbusdt-2026-06-01.md`](../analysis/session-sweep-bnbusdt-2026-06-01.md)).*
    BNBUSDT session expansion (`+ASIA +OFF_SESSION`) lifts throughput **15 → 35 trades
    (+133%) with quality *improved*** (PF 1.79→2.54, ROI +4.91%→+20.59%, MAR 6.65, DD flat). **⚠ Stale (2026-06-11, F-017):** these
    figures are in-sample under the *close-only* exit model; under the governing `intrabar_touch`
    model + a 70/30 OOS split they do **not** survive — true V0 = 15 / PF 1.03 / +0.12%
    (KEEP_INCUMBENT). See [`current-findings.md` F-017](../current-findings.md).
    **But 35 is the hard session ceiling** (V4==V3) — the literal ≥40 floor is **not** reachable
    via sessions alone; 40+ needs the *next* funnel bottleneck (detection/RETEST supply), not
    Trd-M6. The Phase 5a threshold sweep stays **excluded** (proven non-binding, Phase 6b).
  - *Part 4A feature-region OOS study — DONE (BNBUSDT, 2026-06-01, see
    [`docs/analysis/feature-region-oos-persistence-2026-06-01.md`](../analysis/feature-region-oos-persistence-2026-06-01.md)).*
    Geometry-region persistence is **real, not coincidence** (both train-profitable zones persist OOS,
    retention 0.93/1.51, no collapse) **but economically marginal** (~+0.03R, ~2% TP in the raw universe).
    Methodology: feature standardization (inverse-std weights) was essential — equal weights cluster by
    price scale. **Verdict: QUALIFIED YES** — Probability-Surface branch is viable as a low-weight advisory
    input, **gated on** per-instrument confirmation (SOL/ETH/BTC) + the ReplayMemory schema repair.
    **Per-instrument confirmation — DONE (2026-06-02): GENERALIZES 4/4** (BNB/SOL/ETH/BTC all persist,
    zero collapses; edge grows +0.02R→+0.09R BNB→BTC). Caveat: `persist_share=1.0` is conditioned on
    train-profitability (~2/8 zones; bulk is persistently negative) and edge is marginal. **Precondition
    #1 now satisfied. ReplayMemory schema/weighting repair + 4 per-instrument `zone_v1` registries also DONE
    (2026-06-02) → both Fusion-wiring preconditions met; advisory granted YES (measure-only, weight 0.0) under
    a focused sub-plan ([`probability-surface-advisory.md`](../plans/probability-surface-advisory.md)).**
  - *Phase 6e governance re-validation — DONE (2026-06-01, see
    [`docs/analysis/phase6e-shadow-advisory-ab-bnbusdt-2026-06-01.md`](../analysis/phase6e-shadow-advisory-ab-bnbusdt-2026-06-01.md)).*
    Forensics: 100% of the 35→105 funnel gap is one flag, `shadow_advisory_only=True` (Phase 4b
    policy). A/B (flip→False): throughput 35→89 but **PF collapses 2.54→1.52, DD 3.1%→8.2%** →
    **Phase 4b RE-CONFIRMED at n=89; flag stays True; 35 is correct-by-policy.** Cheap config levers
    (sessions + shadow) are **exhausted** for BNBUSDT; the next throughput lever is upstream
    detection supply, not governance or intelligence.
  - *Key reframe:* session expansion is **instrument-specific** — strongly positive for
    BNBUSDT, rehabilitates SOLUSDT, **degrades ETHUSDT**, BTCUSDT unprofitable either way. So
    the recovered profitable trades make **Trd-M6 optimization, not necessity, for BNBUSDT**;
    the broader open problem is **per-instrument edge quality**, which Trd-M6 does not obviously
    address. Next investment: ship **instrument-scoped** session expansion (cheap) before Trd-M6.
  - *Decision (2026-06-02): Trd-M6 stays downstream.* The precondition to un-park is that the
    instrument-scoped session promotions ship first — **#1 BNBUSDT**, **#2 SOLUSDT** — followed by
    **Part 4A per-instrument OOS confirmation**. 35 @ PF 2.54 clears the *spirit* of the throughput
    floor for BNBUSDT; the literal ≥40 needs upstream **detection supply**, which is **not** Trd-M6.
    Enabling mechanism landed 2026-06-02: `engine_runner.allowed_sessions_overrides`
    (`production_config.py` resolver) gives per-instrument session sets with global fallback for
    every other instrument, so BNBUSDT can run +ASIA +OFF_SESSION without touching ETH/BTC.
  - *Re-evaluation (2026-06-02, backlog #7): Trd-M6 STAYS PARKED — verdict reaffirmed, status advanced.*
    Precondition progress this session: **#1 ConfigValidator is now session-override-aware** (validates
    per-instrument session sets, not global defaults); **BNBUSDT V3 + SOLUSDT folded into a
    validated-ready candidate** (`configs/production/v3_multi_2026_06.json`, ConfigValidator APPROVE —
    BNB 39 trades/PF 1.63, SOL 31/PF 0.98≈breakeven-improved) — **staged, ACTIVE_VERSION NOT flipped
    (operator cutover pending)**; **Part 4A OOS generalizes 4/4**; **ReplayMemory repair complete**.
    Remaining un-park gates, unchanged in spirit: (a) **operator ships V3** (the cutover), (b) the
    literal **≥40 throughput** floor needs **upstream detection / RETEST supply** — the session ceiling
    is 35 (BNB) — which is **not** Trd-M6, and (c) **per-instrument edge quality** (ETH degrades, BTC
    unprofitable) is a separate research question Trd-M6 does not address. **Conclusion: Trd-M6 remains
    optimization, not necessity.** Next investment order: V3 cutover → detection-supply work for ≥40
    throughput → ETH/BTC edge research. Un-park only when throughput ≥40 arrives from upstream supply
    *and* the foundation justifies scenario-aware decisioning.

---

## 4. Cross-references

- [`idea-governance-framework.md`](idea-governance-framework.md) — governance-track rules.
- [`user-progress-registry.md`](../governance/user-progress-registry.md) — governance-track live status.
- [`claude-architecture-migration-eager-wreath.md`](../plans/claude-architecture-migration-eager-wreath.md) — trading-track plan + Trd-M6 definition.
- [`assistant_project.md`](../../assistant_project.md) — trading-track doctrine block + SESSION LOG.
- [`codebase-state-map.md`](codebase-state-map.md) — what the engine does today.
- [`goal.md`](goal.md) — the priority order both tracks inherit.
