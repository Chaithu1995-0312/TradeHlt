# Repository Evolution Audit — Liquidity-State Intelligence Thesis (2026-06-03)

> **Point-in-time snapshot, NOT a living doc.** Captures whether a proposed "liquidity-state
> intelligence" architecture already exists in Tradelatest under different names, grounded in
> code (`file:line`) and dated analysis. For current truth re-read the living docs (`CLAUDE.md`,
> `docs/architecture/goal.md`) and re-run the studies. Companion artifacts produced the same day:
> the reusable audit prompt (`repository-evolution-audit-PROMPT-2026-06-03.md`) and the economic
> diagnosis (`economic-edge-gap-analysis-2026-06-03.md`).

## What prompted this

A thesis was proposed: build a "liquidity-state intelligence" stack —
`liquidity constraints → state geometry → liquidity archetypes → profitability regions →
outcome database`. The suspicion (correct) was that much of it may already exist under other
names. This audit answers **"what already exists?"** so engineering months are not spent
rebuilding Zone Registry + Feature-Space Intelligence under a new label.

**This audit extends, rather than repeats,** the independent architecture audit in
[`audit-2026-06-02/`](audit-2026-06-02/readme.md), whose through-line —
*"the system is rich in built intelligence and poor in consumption; enablement ≠ consumption"*
([`dead-dormant-inventory.md`](audit-2026-06-02/dead-dormant-inventory.md)) — is the same
finding seen through a governance lens.

---

## 1. Thesis vs reality — three corrected assumptions

The original thesis carried three load-bearing assumptions. All three are wrong or stale:

| Assumption (thesis) | Reality (evidence) |
|---|---|
| OOS persistence study is **still open** | **COMPLETE.** Validated 4/4 instruments (BNB/SOL/ETH/BTC), temporal 70/30 split, no shuffle. Verdict "persistence is REAL," retention 0.93–1.51, **zero collapses** — but edge is **economically marginal** (+0.02–0.09R). [`feature-region-oos-persistence-2026-06-01.md:38,62`](feature-region-oos-persistence-2026-06-01.md) |
| ReplayMemory is **broken / dormant** | **FIXED 2026-06-02.** `center`/`centroid` fallback + `feature_weights` applied; cluster-0 collapse gone, with regression tests ([`tests/replay/test_assign_cluster.py`](../../tests/replay/test_assign_cluster.py)). It is *trustworthy* but deliberately async / monitoring-only, frozen behind the *Schema-Consistency-Before-Fusion* invariant. `_assign_cluster` [`replay_memory_engine.py:394`](../../src/replay/replay_memory_engine.py), `_build_cluster_stats` [`replay_memory_engine.py:432`](../../src/replay/replay_memory_engine.py). |
| Intelligence layer is **missing** | **Mostly present** (see §2). The binding ROI lever is **governance, not intelligence**: the entire +0.584R edge appears at the RETEST→EXECUTION gate, not the feature/geometry funnel. [`gate-contribution-bnbusdt-2026-06-03.md:17-19`](gate-contribution-bnbusdt-2026-06-03.md). Adding ASIA+OFF_SESSION to BNBUSDT moved ROI **+4.91%→+20.59%** (PF 1.79→2.54, 15→35 trades) with **zero new code** ([`session-sweep-bnbusdt-2026-06-01.md:44`](session-sweep-bnbusdt-2026-06-01.md)). |

**Reframed question:** not *"can we build liquidity-state intelligence?"* but
**"if OOS persistence is real, why is the economic edge marginal?"** — owned by Artifact C.

---

## 2. Concept → code completion map

Every liquidity-state concept already has a home in code:

| Liquidity-state concept | Exists as | Anchor (file:line) | Status | Completion |
|---|---|---|---|:---:|
| Liquidity feature space | `CANONICAL_FEATURES` indices 35–37 (`liquidity_distance`, `liquidity_pressure_score`, `volume_spike`) | [`feature_schema.py:46,65`](../../src/features/feature_schema.py) (DIM=38, [:76](../../src/features/feature_schema.py)) | LIVE | ~90% |
| State-transition geometry | CRT `VALID_TRANSITIONS`, 9 states + SHADOW_PENDING/EXPIRED branches | [`crt_engine_v2.py:1021`](../../src/config_layer/crt_engine_v2.py) (enum [:63](../../src/config_layer/crt_engine_v2.py)) | LIVE | 100% |
| Liquidity archetypes | Zone Registry (pure-Python KMeans, inverse-std weights) | [`scripts/research/discover_zones.py`](../../scripts/research/discover_zones.py) | LIVE | ~85% |
| Profitability regions | Zone Gate (hard gate, fused @0.20) + OOS-validated feature regions | [`zone_gate_engine.py:191`](../../src/engines/zone_gate_engine.py) | LIVE | ~80% |
| Path-profitability DB | ReplayMemory per-cluster stats (win_rate / mean_rr / failure_modes / trap_freq) | [`replay_memory_engine.py:432`](../../src/replay/replay_memory_engine.py) | LIVE, async, monitor-only | ~70% |
| Region health monitoring | MarketStateClusterEngine (6 regimes, cooldown) + ReplayDriftGovernor | [`market_state_cluster_engine.py:95`](../../src/regime/market_state_cluster_engine.py) | LIVE | ~75% |
| Temporal persistence validation | OOS persistence harness | [`scripts/research/feature_region_oos_study.py`](../../scripts/research/feature_region_oos_study.py) | COMPLETE (4/4) | 100% |

**A/B/C/D classification of the thesis components:**
- **A — Already implemented:** state geometry, liquidity feature space, OOS validation.
- **C — Implemented under different names:** "liquidity archetypes" = Zone Registry;
  "profitability regions" = Zone Gate / feature regions; "outcome / path DB" = ReplayMemory.
- **B — Partially implemented:** region health monitoring (live but advisory-only); a *named*
  "Probability Surface" advisory module is **scoped-not-built** — the capability exists as Zone
  Gate + the OOS study ([`dead-dormant-inventory.md:31`](audit-2026-06-02/dead-dormant-inventory.md)).
- **D — Contradicting existing architecture:** none. The thesis is an **evolution** of
  Feature-Space Intelligence, not a replacement. There is **no rebuild**.

---

## 3. What exists / partial / dead — the genuinely open set

The proposed architecture is **70–90% present**. The narrow open set:

1. **Per-instrument registry routing (designed, unwired).** CognitiveBus loads one global
   `zone_registry.json`; per-instrument registries exist (`models/replay/zone_registry_*.json`)
   but `DecisionSnapshot.instrument` is ignored. CognitiveBus is *dormant* — gated by an absent
   `cognitive_layer` in the ACTIVE config ([`dead-dormant-inventory.md:10`](audit-2026-06-02/dead-dormant-inventory.md)).
2. **ReplayMemory re-homing.** RME is async/monitoring-only by design; before any non-zero
   fusion weight it must move to the synchronous deterministic decision path and be measured
   additively (weight 0.0 → earn weight). Frozen behind *Schema-Consistency-Before-Fusion*.
3. **The marginal-edge problem.** Zones persist OOS but barely pay (+0.02–0.09R; 6/8 zones are
   persistently *negative* — the signal is a small durable *gradient*, not a profitable space,
   [`feature-region-oos-persistence-2026-06-01.md:77-79`](feature-region-oos-persistence-2026-06-01.md)).
   **This is the real question — see Artifact C.**

**Built-but-not-consumed (the C3 pattern):** BitNet score at entry, zone *expectancy* (mean_rr,
not just geometry), concept drift, regime fusion weights, orchestrator consensus — all built,
none reaching the decision ([`dead-dormant-inventory.md:22-31`](audit-2026-06-02/dead-dormant-inventory.md)).
**Dead inventory** is small: nothing in the thesis is architecturally dead.

---

## 4. Two tracks — stated neutrally, then the call

### Track G — Governance / throughput (evidence-backed, reversible)
- Per-instrument session policy via the landed resolver `resolve_allowed_sessions`
  ([`production_config.py:281`](../../src/config_layer/production_config.py)) + `_canon_session`
  ([:266](../../src/config_layer/production_config.py)). **Measured +4.91%→+20.59% on BNB, no new code.**
- Wire-and-measure the already-built dormant signals (drift→size-down, zone expectancy, BitNet
  score persistence) — the top-10 ROI actions, **none of which is new intelligence**
  ([`top-10-roi-actions.md`](audit-2026-06-02/top-10-roi-actions.md)).

### Track I — Liquidity-state intelligence (the thesis)
- Feature-feature V2 (richer liquidity features), archetype registry refinement, Probability-
  Surface advisory wiring. **Bounded by the measured marginal edge** and by the per-candle
  feature→outcome model sitting at chance (AUC 0.5149, [`edge-attribution-2026-06-03.md:3`](edge-attribution-2026-06-03.md)).

### The call (user requested the doc decide)
**Lead with Track G; gate Track I behind Phase 0 (Artifact C).** Track G is proven, reversible,
and pure policy. Track I cannot be funded until the economic diagnosis (Artifact C) reconciles
the paradox and shows a feature track can move outcome AUC materially off 0.5. **The #1 risk is
rebuilding Zone Registry + Feature-Space Intelligence under new names while the marginal-edge
cause goes undiagnosed.**

---

## 5. Pointer to the diagnosis

The question *"why doesn't persistence pay, and can any feature track beat AUC 0.5 OOS?"* is
owned by [`economic-edge-gap-analysis-2026-06-03.md`](economic-edge-gap-analysis-2026-06-03.md)
(Phase 0: Economic Edge Diagnosis) — including the opportunity-cost / funding matrix and the
single gating question. This audit does not duplicate it.

---

## Caveats

- All ROI/funnel numbers are **backtest-measured** on specific BNBUSDT runs and configs; `UltronRiskGate`
  + `ExecutionPlannerV1_2` are live-only and not in the backtest spine, so live PnL is unverified
  ([`top-10-roi-actions.md:29`](audit-2026-06-02/top-10-roi-actions.md)).
- Completion percentages are judgment calls anchored to code presence + wiring, not a metric.
- The funnel counts differ by config/window: v1 (15 trades, [`roi-funnel-diagnosis-bnbusdt-2026-05-30.md:13`](roi-funnel-diagnosis-bnbusdt-2026-05-30.md))
  vs v4 (35 trades, [`gate-contribution-bnbusdt-2026-06-03.md:13`](gate-contribution-bnbusdt-2026-06-03.md)). Cite the config when quoting.
</content>
