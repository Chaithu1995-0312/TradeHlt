# Encyclopedia E4 — Sidecar / Support Modules (Group B)

**Phase:** E4  
**Status:** DONE (package + file map for non-spine support surfaces)  
**Date:** 2026-08-07  
**Parent:** [Chapter 24](../24-repository-encyclopedia.md) · [Encyclopedia index](README.md)

## Scope

Group B packages **support** the system but are **not required** to understand the candle→order
spine on day one. They are not all equally “dead” — some are LIVE data/ops helpers; many are
INERT, UNWIRED, RESEARCH, or OBSERVE_ONLY on the active production config.

| Package | `.py` files | Default posture |
|---|---:|---|
| `src/bitnet/` | 23 | Built; **inert** when `use_bitnet:false` (F-004/F-055) |
| `src/utils/` | 17 | LIVE helpers (logging, JSONL, manifests) |
| `src/retrieval/` | 9 | Enterprise RAG — optional tooling |
| `src/training/` | 8 | Offline train pipelines; TradeNet built/unwired (F-005) |
| `src/expansion/` | 6 | Controlled frequency expansion — ops/research |
| `src/portfolio/` | 6 | Allocator built; live spine still single-candle (F-013) |
| `src/replay/` | 6 | Replay memory / timing — sidecar (F-012 class) |
| `src/analytics/` | 5 | Offline metrics / clustering |
| `src/regime/` | 4 | Regime clustering / routing — research-adjacent |
| `src/msip/` | 6 | Shadow market state — OBSERVE_ONLY (Ch.18) |
| `src/multi_llm/` | 5 | Multi-LLM ops tooling (also root `multi_llm/`) |
| `src/events/` | 2 | Event fabric |
| `src/search/` | 1 | Regime weight searcher |
| `src/monitoring/` | 2 | Health endpoint (borderline dormant/ops) |
| **Total** | **~100** | |

**Not in E4:** Group C dormant strategies/scanner/journal (→ **E5**); research/gov (E2/E3); spine (E1).

**Rule:** SIDECAR ≠ deleted. Read when a task touches the package; do not promote into fusion without
Authority Ladder evidence.

---

## How to use

| Need | Package |
|---|---|
| BitNet zone gate / low-bit models | `bitnet/` + Ch.10 |
| Logging / JSONL / run manifests | `utils/` |
| Offline train / TradeNet | `training/` |
| Portfolio multi-instrument | `portfolio/` |
| Replay memory / pattern timing | `replay/` |
| Offline performance metrics | `analytics/` |
| Shadow MSV | `msip/` |
| Multi-LLM turn ledger / packs | `multi_llm/` + Ch.23 |
| Codebase RAG | `retrieval/` |
| Parameter expansion | `expansion/` |

---

## 1. `src/bitnet/` — BitNet / zone intelligence stack (23)

**Posture:** Full stack **built**; production **INERT** while `use_bitnet` false on active patch.
Shadow A/B (F-055) did not earn activation authority.

| File | Purpose |
|---|---|
| `__init__.py` | Package: BitNet parameter / zone discovery engine |
| `bitnet_inference.py` | Inference for dual JSON model schemas |
| `bitnet_runner.py` | Schema enforcement + fail-closed dimension checks |
| `bitnet_registry.py` | Version registry — Exists ≠ Selected ≠ Enabled |
| `model_contract.py` | Canonical serialization contract (`bitnet_v3`) |
| `model_bundle.py` | CONTRACT-C model.bundle write/validate |
| `composition.py` | Encoder → Backbone → Heads → Adapter composition |
| `encoders.py` / `backbones.py` / `heads.py` / `adapters.py` | Spec hierarchy components |
| `layers.py` | Pure numeric BitLinear primitives |
| `defaults.py` | Versioned numeric defaults (Spec v1.2.1) |
| `label_contracts.py` | CONTRACT-C label definitions |
| `contract_c_trainer.py` | CONTRACT-C trainer for BitLinear residual family |
| `runtime_types.py` | Shared inference value types |
| `zone_cosine_searcher.py` | Cosine match to zone vectors |
| `zone_validator.py` | Min quality criteria for candidate zones |
| `forward_tester.py` | OOS validation for zone registry |
| `stability_checker.py` | Zone stability across temporal splits |
| `population_label_audit.py` | Read-only population/label balance audit |
| `r25_kill_test.py` | R2.5 kill-test harness |
| `_smoke_test.py` | Module smoke test |

**Related:** `src/engines/zone_gate_engine.py` (E1), F-004/F-050/F-055, BitNet lineage audit.  
**Do not:** enable on active config without ΔG001 + promotion path.

---

## 2. `src/utils/` — shared helpers (17)

**Posture:** **LIVE support** — imported widely; not decision authority.

| File | Purpose |
|---|---|
| `logging_config.py` | Centralized per-flow logging |
| `console_safe.py` | Windows/cp1252-safe console output |
| `jsonl_writer.py` | Canonical append-only JSONL helper |
| `trade_logger.py` | Trade event logging |
| `llm_logger.py` | Structured LLM session logger (UAT/SIT) |
| `log_identity.py` / `log_index_writer.py` | Log identity + index writers |
| `engine_telemetry.py` | Structured engine observability wrapper |
| `integrity_events.py` | Integrity-event telemetry spine |
| `sweep_trace_logger.py` | CRT sweep decision traces (`sweep_trace.jsonl`) |
| `episode_summarizer.py` | Episode summarization helpers |
| `pattern_hasher.py` | Stable pattern IDs for replay/memory |
| `run_manifest.py` | Provenance manifest for research runs (ERP H1/H2/H3) |
| `validation_contract.py` | Mechanical anti-hallucination checks over manifests |
| `config_dumper.py` | Dump resolved config to timestamped JSON |
| `registry_refresh.py` | mtime hot-reload tracker for model/config files |
| `zone_schema_migrator.py` | BitNet zone schema migration utility |

---

## 3. `src/training/` — offline training (8)

**Posture:** RESEARCH / OFFLINE. TradeNet **built but unwired** in fusion (F-005).

| File | Purpose |
|---|---|
| `train_pipeline.py` | Main train pipeline (incl. Phase-5 calibration gate before register) |
| `trainer.py` | Trainer core loop |
| `evaluator.py` | Offline evaluation |
| `phase5_calibration.py` | Phase-5 calibration (note: historical gaussian artifact builder path) |
| `stage1_dataset_builder.py` | Stage-1 truth dataset for TradingLLM-class training |
| `trade_net_v2.py` | TradeNet v2 model definition / train surface |
| `training_trigger.py` | Programmatic gate to invoke auto-train |
| `bar_semantic_tracker.py` | Append-only bar-level semantic journal for train/eval |

**Related:** E2 RR clean labels; `models/*` artifacts; never confuses train success with production authority.

---

## 4. `src/portfolio/` — multi-instrument allocation (6)

**Posture:** **BUILT / ORPHANED from live single-candle spine** (F-013). Research/ops use only until wired.

| File | Purpose |
|---|---|
| `allocator.py` | PortfolioAllocator — multi-instrument capital allocation |
| `capital_policy.py` | Capital policy rules |
| `correlation_engine.py` | Cross-instrument correlation |
| `exposure_tracker.py` | Exposure tracking |
| `replay.py` | Read-only shadow replay of allocator over historical ledger |
| `__init__.py` | Package marker |

---

## 5. `src/replay/` — institutional replay memory (6)

**Posture:** SIDECAR (F-012 class — zero spine consumption by default).

| File | Purpose |
|---|---|
| `replay_memory_engine.py` | Persistent institutional memory layer |
| `replay_similarity_index.py` | Similarity search over replay vectors |
| `replay_drift_governor.py` | Contamination / staleness / cluster drift monitor |
| `timing_advisor.py` | Read API for Pattern Timing Library (measure-only Phase 1) |
| `timing_reconstructor.py` | Forward-walk timing augmentation of outcomes |
| `__init__.py` | Package marker |

---

## 6. `src/analytics/` — offline analytics (5)

**Posture:** OFFLINE research/ops metrics (not live decision).

| File | Purpose |
|---|---|
| `metrics_oracle.py` | Independent backtest metric recompute (trust layer) |
| `performance.py` | Win rate, expectancy, drawdown breakdowns |
| `clustering.py` | Cluster losing trades by condition |
| `sl_tp_comparator.py` | Dual SL/TP method comparator |
| `__init__.py` | Package exports |

---

## 7. `src/expansion/` — controlled frequency scaling (6)

**Posture:** OPS/RESEARCH — bounded parameter/frequency expansion; not free optimizer.

| File | Purpose |
|---|---|
| `expansion_engine.py` | Expansion engine core |
| `config_mutator.py` | Config mutation helpers for expansion trials |
| `evaluator.py` | Expansion trial evaluation |
| `policy_schema.py` | Expansion policy schema |
| `llm_pattern_extractor.py` | Optional LLM pattern extraction for expansion |
| `__init__.py` | Package: controlled trade frequency scaling |

---

## 8. `src/regime/` — regime surfaces (4)

**Posture:** RESEARCH-adjacent (complements E2 `regime_conditioning`; not Ultron).

| File | Purpose |
|---|---|
| `regime_classifier.py` | Regime classification |
| `market_state_cluster_engine.py` | Cluster-native market state classification |
| `config_router.py` | Regime → config routing helper |
| `__init__.py` | Package marker |

---

## 9. `src/msip/` — Market State Interpretation Platform shadow (6)

**Posture:** **OBSERVE_ONLY** — never mutates CRT; never gates execution (Ch.18 brief).

| File | Purpose |
|---|---|
| `market_state_vector.py` | MSV value object (schema pin) |
| `interpretation_config.py` | `msip_shadow` HOW config; off when absent/disabled |
| `shadow_emitter.py` | Pure build + append-only emit |
| `disagreement.py` | Shadow vs CRT disagreement taxonomy (telemetry) |
| `isolation.py` | Import/mutation isolation policy |
| `__init__.py` | Shadow package marker |

**Related:** `run_h_msip_001/002` (E2); no production cutover without explicit gates.

---

## 10. `src/multi_llm/` — multi-LLM ops package (5)

**Posture:** OPS tooling for hand-operated multi-model workflow; **isolated from trading spine**.
(Repo root `multi_llm/` holds protocol docs, ledger, roles — Ch.23.)

| File | Purpose |
|---|---|
| `turn_ledger.py` | Append-only multi-LLM turn record |
| `context_pack.py` | Bounded upload-ready context pack for one task |
| `discussion.py` | Reconstruct / rewind discussion (view-only) |
| `tokens.py` | Heuristic token estimates for pack bounds |
| `__init__.py` | Coordination layer package |

---

## 11. `src/retrieval/` — codebase RAG (9)

**Posture:** OPTIONAL tooling (ChromaDB + embeddings). Not on candle→order path.

| File | Purpose |
|---|---|
| `retriever.py` | High-level retrieval + context assembly |
| `vector_store.py` | ChromaDB hybrid search store |
| `embedding.py` | sentence-transformers embedding pipeline |
| `chunking.py` | Structure-aware semantic chunking |
| `corpus.py` | Repo document discovery by domain |
| `config.py` | Retrieval tunables |
| `monitor.py` | RAG metrics |
| `claude_integration.py` | Claude Code RAG-grounded task helpers |
| `__init__.py` | Enterprise RAG package |

---

## 12. Small surfaces

### `src/events/` (2)

| File | Purpose |
|---|---|
| `event_fabric.py` | Canonical Event Fabric for runtime eventing |
| `__init__.py` | Package marker |

### `src/search/` (1)

| File | Purpose |
|---|---|
| `regime_weight_searcher.py` | Search/sweep helpers for regime weights (research/ops) |

### `src/monitoring/` (2)

| File | Purpose |
|---|---|
| `health_checker.py` | Lightweight stdlib HTTP health on port 8788 |
| `__init__.py` | Package marker |

**Note:** Control plane dashboard is 8787 (E1); health checker is a separate lightweight surface.

---

## Cross-cutting findings (why these stay sidecar)

| Finding / class | Implication for E4 |
|---|---|
| F-004 / F-055 | BitNet hard gate inert / shadow not activated |
| F-005 | TradeNet fusion slot unwired |
| F-012 | Replay / cognitive / HMF sidecar-only |
| F-013 | Portfolio allocator + scan loop orphaned from live single-candle spine |
| F-060 | Live Gaussian channel near-constant — separate from `bitnet/` package |
| Ch.18 MSIP | Shadow only; no CRT mutation |

---

## Danger flags

| Flag | Meaning |
|---|---|
| **INERT_UNTIL_CONFIG** | Present in tree; inactive unless config enables (BitNet) |
| **UNWIRED** | Built but no production caller (TradeNet neural slot, portfolio live) |
| **OBSERVE_ONLY** | MSIP shadow, many replay/timing measure paths |
| **OPTIONAL_DEPS** | retrieval (ChromaDB, sentence-transformers) may be absent |
| **NO_FUSION_AUTHORITY** | None of E4 grants §6.5 production weight by existing |

---

## E4 exit criterion

| Criterion | Status |
|---|---|
| Every Group B package listed in Ch.24 has a section | **Met** |
| File-level purpose for bitnet/utils/training/portfolio/replay/analytics/expansion/regime/msip/multi_llm/retrieval/events/search/monitoring | **Met** |
| Explicit non-authority vs spine | **Met** |
| Deep train/BitNet tutorials | **Out of scope** (lineage audits + topics) |

---

## Next

- **E5** — Group C dormant (`strategies`, `scanner`, `journal`, `cognitive`, `feedback`, `llm_research`, `data_ingestion`, `uat`, `ui`)  
- **E6** — Remaining scripts outside research/governance/analysis catalogs  

---
**Related:** [Ch.10](../10-four-scoring-engines.md) · [Ch.18 MSIP](../18-field-guide-governance.md) · [Ch.23](../23-multi-llm-coordination.md) · [E1](E1-spine-implementation.md) · [E3](E3-governance-tooling.md) · [Ch.24](../24-repository-encyclopedia.md)
