# OSS Integration & Comparative Benchmark Architecture

| Field | Value |
|---|---|
| Status | **ACTIVE DESIGN + LAB SCAFFOLD** |
| Authority | Research / lab only — **no production authority** |
| Effective | 2026-08-12 |
| Lab root | [`oss_lab/`](../../oss_lab/README.md) |
| Plan | [`docs/implementation_plan/oss-integration-benchmark-lab.md`](../implementation_plan/oss-integration-benchmark-lab.md) |
| Construction class | `DOCUMENTATION_ONLY` + isolated lab package (no production spine wiring) |

---

## Final design principle

> The goal is **not** “use open source because it exists.”
>
> The goal is: **use mature open source to accelerate generic capabilities while preserving Tradelatest’s unique semantic, market, research, governance, and capital authorities.**

```text
BUILD:  ontology · semantic chain · CRT · testimony · governance · capital · Semantic OS
BORROW: research infra · ML/RL experiment · event-driven replay · execution sim · tooling
PROVE:  equivalence · speed · throughput · lookahead · cost · slippage · fill · economics · repro
UNKNOWN: whenever evidence is insufficient
```

**Never trade architectural authority for convenience.**

---

## 1. Existing architecture trace (OSS-relevant)

### A. Deterministic trading spine (runtime authority)

```text
OHLCV → canonical candle → Feature Pipeline → canonical feature vector
  → STATE → CONTEXT → SHAPE → CRT lifecycle
  → independent model testimony → Fusion → Decision
  → Execution Planner → Entry → CRT geometry → SL/TP → RR
  → Ultron (capital/economic) → Order
```

**Key modules (do not replace):**

| Layer | Authority location |
|---|---|
| OHLCV / corpus | `src/data_ingestion/`, `docs/governance/CORPUS_AUTHORITY.md` |
| Features / ontology | `src/features/`, `configs/formulas/market_ontology.yaml` |
| STATE / CONTEXT / SHAPE | `feature_states`, `market_context`, `market_shape` |
| CRT | `src/config_layer/crt_engine_v2.py`, `state_identity` |
| Testimony | `model_evidence`, engines under `src/engines/` |
| Fusion / Decision | `src/core/fusion_engine.py`, `decision_engine.py` |
| Planner | `src/config_layer/execution_planner.py` |
| Ultron | `src/core/ultron_risk_gate.py` |
| Backtest harness | `src/runtime/backtest_v2.py` |

### B. Research architecture

```text
Hypothesis → pre-registration → experiment → measurement → artifact
  → finding → evidence → governance → possible promotion
```

**Reuse candidates:** `src/research/experiment_spec.py`, `measurement/forward_walk.py`,
`measurement/metrics.py` (EdgeAggregator — quarantined from promotion), `costs.py`,
`provenance.py`, `contracts.py` (Signal/Outcome/EdgeReport).

### C. Governance architecture

```text
Authority → construction validation → config validation → promotion
  → ACTIVE_VERSION → runtime → audit/evidence → finding/closure/reopen
```

**Reuse:** `change_contracts.json`, `construction_protocol.py`, `promotion_manager.py`,
`MEASUREMENT_CONTRACT.md`, runtime benchmark suite pin (separate from feature freeze).

### D. Semantic OS

L0–L6 meaning/control-plane interface. **Not runtime authority.** Fail closed; represent
UNKNOWN rather than invent meaning. Planned OSS entities: `oss_lab/governance/semantic_os_mapping.json`
(Phase 9 — not yet authored into live YAML).

### E. Knowledge systems

| System | Role |
|---|---|
| Canonical Knowledge Book | Architecture narrative |
| Repository Encyclopedia | Implementation map |
| Semantic OS | Meaning / relationships |
| Coverage/measurement | Degree of understanding |

---

## 2. Existing repository capability inventory

| Capability | Existing location | Lab reuse posture |
|---|---|---|
| XAUUSD M15 frozen corpus | `docs/governance/xauusd_m15_phase1_frozen_candidate.json` + `src/data_ingestion/xauusd_phase1_candidate.py` | **Primary benchmark dataset pin** |
| Runtime benchmark suite | `docs/governance/runtime-benchmark-suite-2026-07-20.md` | Sibling authority; lab does not override |
| Research metrics (PF, E, MFE/MAE, DD) | `src/research/measurement/metrics.py` | Formula alignment; **separate** lab path (no promotion) |
| Cost model (flat bps) | `src/research/costs.py` | Declared cost variable |
| MT5 cost calibration | `src/research/mt5_cost_calibration.py` | MEASURED/UNKNOWN discipline template |
| Forward-walk MFE/MAE | `src/research/measurement/forward_walk.py` | Path stats recompute when native missing |
| ExperimentSpec / corpus pin | `src/research/experiment_spec.py` | Pattern for lab scenarios |
| Provenance stamps | `src/research/provenance.py` | RunManifest alignment |
| Trade journal record | `src/journal/schema.py` | **Different** TradeRecord — do not conflate |
| Performance analyzer (currency) | `src/analytics/performance.py` | Quarantined; not comparable to R-metrics |
| Backtest metrics engine | `src/runtime/backtest_v2.py` (`MetricsEngine`) | Spine descriptive metrics |
| Ultron cost tax | `src/core/ultron_risk_gate.py` | Production cost authority |
| Measurement contract schema | `docs/governance/measurement_contract.schema.json` | Future MC seal for lab claims |
| Registry patterns | `active_models.yaml`, script/framework/hypothesis registries | Pattern for OSS registry |
| Isolation package precedent | `mt5_analytics/`, `multi_llm/` | Physical pattern for `oss_lab/` |

**No existing Qlib / Nautilus / FinRL integration** (grep: design mentions in knowledge graph only).

---

## 3. OSS capability matrix

| oss_id | Role | Trust | Decision | Adapter | Forbidden authorities |
|---|---|---|---|---|---|
| OSS-TRADLATEST-BASELINE | Local baseline | T2 (lab) | APPROVED_FOR_LAB | `adapters/tradelatest` | (is the authority) |
| OSS-QLIB | Research engine | T2 | DISCOVERED | stub | ontology, CRT, Fusion, Decision, Ultron, prod config |
| OSS-NAUTILUS | Runtime/replay adapter | T3 | DISCOVERED | stub | same + ExecutionPlanner + governance |
| OSS-FINRLX | RL/portfolio research | T2 | DISCOVERED | stub | same |
| **OSS-CODEBASE-MEMORY** | Repo intelligence (structural graph) | **T1** | DISCOVERED | stub | Semantic OS authority, ontology, CRT, core, prod |
| **OSS-LEAN** | Independent execution lab | **T3** | DISCOVERED | stub | CRT/Fusion/Decision/Planner/Ultron/strategies |
| **OSS-INFIGRAPH** | Repo intel (AST/Cypher) | **T1** | DISCOVERED | stub | same as Codebase-Memory |
| **OSS-VECTORBT** | Vectorized research | T2 | **DEFERRED** | stub | prod/core/governance (Commons Clause legal) |
| **OSS-RIG-METHOD** | Repo-graph methodology paper | **T0** | REFERENCE_ONLY | none | not a dependency |

Machine source: `oss_lab/registry/oss_capabilities.jsonl`.  
Evaluation queue: `oss_lab/governance/evaluation_queue.md`.

### Dual-track reuse (monitor scan 2026-08-12)

```text
TRACK A EXECUTION     DatasetManifest → BenchmarkTradeRecord → CanonicalMetrics
TRACK B REPO INTEL    repo tree → StructuralFactRecord → Semantic OS ingestion (meaning stays local)
```

**Reuse verdict:** existing OSS lab is the correct home. Repo-intel needs only the thin
`StructuralFactRecord` contract — not a second laboratory.

---

## 4. OSS registry schema

- Schema: `oss_lab/registry/schema.json`
- Loader: `oss_lab/registry/loader.py` (fail-closed required fields; T4 external banned by default)
- Trust tiers: T0 reference · T1 dev tool · T2 research · T3 runtime adapter · T4 production authority (**default forbidden**)

---

## 5. Adapter architecture

```text
                    ┌─────────────────────┐
   DatasetManifest  │  EngineAdapter      │  BenchmarkTradeRecord[]
   ────────────────►│  bind + normalize   ├──────────────────────► CanonicalMetrics
                    │  (thin)             │
                    └──────────┬──────────┘
                               │ native only inside adapter
                    ┌──────────▼──────────┐
                    │ qlib / nautilus /   │
                    │ finrl / backtest_v2 │
                    └─────────────────────┘
```

Rules:

1. Production spine **never** imports `oss_lab`.
2. Adapters may import `src.*` for reuse.
3. Missing fields → Presence tokens + provenance (never invent).
4. Dependency isolation: external packages only importable inside their adapter subtree **after** pin + APPROVED_FOR_LAB.

---

## 6. Canonical benchmark schema

| Contract | Path |
|---|---|
| BenchmarkTradeRecord | `oss_lab/contracts/trade_record.py` |
| DatasetManifest | `oss_lab/contracts/dataset_manifest.py` |
| RunManifest | `oss_lab/contracts/run_manifest.py` |
| MetricCell | `oss_lab/contracts/metric_cell.py` |
| FillModelDeclaration | `oss_lab/contracts/fill_model.py` |

Primary dataset: **BM-XAUUSD-M15-PHASE1-FROZEN** (hash `4d73f5ce…`, 2024-05-22→2026-05-21, 47,275 rows).

---

## 7. Benchmark runner design

| Runner | Role | Status |
|---|---|---|
| `runners/normalize_demo.py` | Smoke normalize + metrics | SHIPPED |
| Future `runners/backtest_baseline.py` | Shell to `backtest_v2` with pinned corpus + gate mode | PLANNED |
| Future `runners/compare_matrix.py` | Fill comparison matrix from evidence | PLANNED |
| Future per-OSS runners | Isolated venv / optional deps | PLANNED |

Never: silent download, silent resample, silent timezone rewrite.

---

## 8. Metric calculation design

`oss_lab/metrics/canonical.py`:

| Metric | Definition |
|---|---|
| Profit Factor | sum(positive net) / abs(sum(negative net)) |
| Expectancy | mean(net_pnl) |
| Expectancy R | mean(net_pnl / initial_risk) when risk PRESENT |
| Max drawdown | peak-to-trough cumulative net equity |
| Sharpe | **UNKNOWN** unless return_frequency declared; never invent annualization |
| MFE/MAE | median of PRESENT path stats |
| Trade count | completed vs incomplete; signals/orders/fills separate |

Status tokens: VERIFIED · MEASURED · REPRODUCED · UNKNOWN · NOT_APPLICABLE · FAILED · NOT_RUN.

---

## 9. Lookahead certification design

`oss_lab/runners/lookahead_cert.py`:

- Run A original · Run B mutate after T
- Pre-T identity required for: features, states, context, shape, CRT, testimony, decision, entry
- FAIL → first divergent timestamp + object
- Docs claims are **not** proof

---

## 10. Cost / slippage / fill-model design

- Separate: gross, fees, spread, financing, slippage, other, net
- Modes: NO_COST vs WITH_COST
- Fill model is a **declared experimental variable** (`FillModelDeclaration`)
- Reuse `research.costs.CostModel` and `mt5_cost_calibration` discipline (MEASURED/UNKNOWN)
- Do not compare engines without documenting fill assumptions

---

## 11. Reproducibility design

`RunManifest` captures: git commit, engine version, dependency lock hash, dataset hash, config hash, schema hash, seed, OS/runtime, command, timestamp.

Triple-run requirement: signals/orders/fills/trades/equity/metrics hashes equal if deterministic; else quantify variance.

---

## 12. Semantic OS integration

Design seed: `oss_lab/governance/semantic_os_mapping.json`.

Live YAML authoring deferred to Phase 9 (full CN/BD/CT schema is heavy; must not break `tests/test_semantic_os.py`).

---

## 13. Governance integration

Lifecycle: `oss_lab/governance/lifecycle.md`  
Risks: `oss_lab/governance/risk_register.md`  
UNKNOWNs: `oss_lab/governance/unknown_register.md`

OSS results never auto-enter `docs/current-findings.md` or promotion.

---

## 14–16. Initial adapter plans

### Qlib (T2)

- Use: feature experiments, model comparison, research workflow acceleration
- Do not redefine ontology/CRT/Decision/Ultron
- Distinguish PUBLISHED vs INDEPENDENT REPRODUCTION vs TRADLATEST RESULT
- Next: license confirm (MIT), pin commit, isolated optional extra, map outputs → BenchmarkTradeRecord

### NautilusTrader (T3)

- Use: event-driven replay, fill-model experiments, throughput/latency
- Do not replace CRT/Fusion/Decision/Planner/Ultron/governance
- **LGPL-3.0 legal review** hard gate before APPROVED_FOR_INTEGRATION
- Next: legal note, pin, adapter-only isolation

### FinRL-X (T2)

- Use: RL / portfolio / timing / risk overlay research
- Published paper-trading ≠ edge evidence
- Separate observed vs annualized return
- Next: verify license (currently UNKNOWN), pin, independent reproduction protocol

---

## 17. Benchmark scenario definitions

`oss_lab/scenarios/bm_xauusd_m15_phase1.json` — primary comparative scenario.

Optional future: RB1 2-month window for fast iteration (reuse runtime suite CSV) — separate dataset_id.

---

## 18–19. Risk & UNKNOWN registers

See `oss_lab/governance/risk_register.md` and `unknown_register.md`.

---

## 20. Implementation order (lowest risk first)

| Phase | Deliverable | Status |
|---|---|---|
| 0 | Discovery | DONE |
| 1 | OSS registry + capability contract | SHIPPED |
| 2 | Canonical benchmark schema | SHIPPED |
| 3 | Tradelatest baseline adapter | ADAPTER SHIPPED (real `backtest_v2` trades-CSV normalization, money-unit PnL); runner PLANNED |
| 4 | Independent metrics/evidence layer | SCAFFOLD |
| 5 | Qlib adapter | STUB / PLANNED |
| 6 | Nautilus isolated adapter | STUB / PLANNED |
| 7 | FinRL-X research adapter | STUB / PLANNED |
| 8 | Lookahead/cost/slippage/fill certs | DESIGN + probe helper |
| 9 | Semantic OS integration | DESIGN seed |
| 10 | Governance/promotion integration | DESIGN |

**Do not begin with deep runtime integration.**

---

## Comparison matrix

Template: `oss_lab/reports/comparison_matrix_template.json` (all cells NOT_RUN/UNKNOWN until evidence exists).

---

## Invariants

1. External OSS is a capability provider, not an authority.
2. Identical market reality via DatasetManifest pin.
3. Independent metric authority over normalized evidence.
4. UNKNOWN over invention.
5. Research ≠ production.
6. Encapsulated dependencies only.
