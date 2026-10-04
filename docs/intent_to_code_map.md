# Intent → Code Map

> **Purpose:** Answer "which files implement this thought? Which modules embody this belief?
> Which functions violate authority? Which code has no known purpose?"
>
> Each entry maps one intent/domain to its code implementation, then assesses alignment.

---

## Domain: Capital Preservation

### Thought → Code
| Intent Node | Code Implementation | File | Line(s) |
|-------------|-------------------|------|---------|
| Seven-check waterfall gate | UltronRiskGate.evaluate() | src/core/ultron_risk_gate.py | 156+ |
| Gate reads from config | ultron_risk_gate config section | configs/production/v2_multi_2026_04.json | — |
| Gate result contract | GateResult (APPROVE/REJECT) | src/core/types.py | 95 |
| Regime pre-scaler (never wired) | UltronRiskGateWrapper.evaluate() | src/core/ultron_risk_gate_wrapper.py | Entire file |
| KillSwitch (daily/weekly limits) | KillSwitch class | src/uat/kill_switch.py | Entire file |

### Authority Assessment
- **Correctly assigned:** `UltronRiskGate` owns trade-level approval. `KillSwitch` owns account-level loss limits. Split is clean.
- **Authority violation:** `ultron_risk_gate_wrapper.py` exists but is never called — it was designed to regime-pre-scale risk_percent, which would have introduced a second authority into the risk path. Its non-wiring is CORRECT per intent (simpler is safer), but the file is an orphan.

### Orphans
- `src/core/ultron_risk_gate_wrapper.py` — regime pre-scaler, never imported in production path.
- `src/scanner/`, `src/execution/loop.py`, `src/portfolio/` — the multi-signal scan→allocate→ExecutionLoop path (F-013).

---

## Domain: Config Governance

### Thought → Code
| Intent Node | Code Implementation | File | Line(s) |
|-------------|-------------------|------|---------|
| Validation gates | ConfigValidator.validate() | src/config_layer/config_validator.py | Entire file |
| Promotion path | PromotionManager.promote_from_report() | src/governance/promotion_manager.py | 52+ |
| SHA-256 hashing | _compute_config_hash() | src/governance/promotion_manager.py | (internal) |
| Audit log append | _log_event() | src/governance/promotion_manager.py | (internal) |
| Active version pointer | get_active_version() | src/config_layer/production_config.py | (internal) |
| Runtime integrity guard (orphaned) | active_version_is_governed() | src/governance/config_integrity.py | Entire file |
| Config schema validation | ConfigBuilder._validate_override_keys() | src/config_layer/config_builder.py | (internal) |

### Authority Assessment
- **Correctly assigned:** `PromotionManager` is the only path to production. `ConfigValidator` gates before promotion.
- **Authority violation:** `config_integrity.py` is a check that gates nothing — it was designed to be a runtime guard but has zero callers. This is the gap that allowed the "deepdeektry" suffix to evade detection (F-016/F-018).
- **Authority violation (partial):** The `promote_direct()` method exists as a deliberately-marked bypass. It is correctly documented but is a latent risk if used outside the "pre-validated hotfix" intent.

---

## Domain: Deterministic Replay

### Thought → Code
| Intent Node | Code Implementation | File | Line(s) |
|-------------|-------------------|------|---------|
| Replay loop | BacktestRunner.run() | src/runtime/backtest_v2.py | 1393+ |
| Independent metric recompute | metrics_oracle | src/analytics/metrics_oracle.py | Entire file |
| Preflight data gate | validate_dataset() | src/data_ingestion/dataset_integrity.py | Entire file |
| Strict OHLCV schema | require_ohlcv_columns(), validate_ohlcv_row() | src/data_ingestion/ohlcv_schema.py | Entire file |
| Golden ledgers | Golden ledgers A–E with invariants | tests/ | 113 tests |

### Authority Assessment
- **Correctly assigned:** Determinism is enforced at multiple layers — data ingestion, replay loop, metric recompute, test assertions.
- **No violations found.** This is the most aligned domain in the repository.

---

## Domain: Advisory-Only LLM

### Thought → Code
| Intent Node | Code Implementation | File | Line(s) |
|-------------|-------------------|------|---------|
| Circuit breaker | llm_inference_client (fail_count_disable=10) | src/config_layer/llm_inference_client.py | Entire file |
| Neutral fallback | returns 1.0 on failure | src/config_layer/llm_scorer.py | Entire file |
| Deterministic plan lookup | PlanCompiler with PLAN_REGISTRY | src/agent/plan_compiler.py | Entire file |
| Write gate | confirm-gate in Executor.dispatch() | src/agent/executor.py | Entire file |
| Path guard | path-guard in Executor | src/agent/executor.py | Entire file |

### Authority Assessment
- **Correctly assigned:** Multi-layer isolation — circuit breaker prevents LLM failure from blocking trading; PLAN_REGISTRY prevents LLM planning; confirm-gate + path-guard prevents LLM writes.
- **Gap noted:** The GovernanceOrchestrator (meta_governor_executor.py) references a 70B model while the actual available model is BitNet 3B. The LLM *layer* design may exceed what the available model can deliver.

---

## Domain: Intelligence Compounding

### Thought → Code
| Intent Node | Code Implementation | File | Line(s) |
|-------------|-------------------|------|---------|
| Per-response SESSION LOG | Structured block appended to | assistant_project.md | Entire file |
| Living repository truths | current-findings.md | docs/current-findings.md | Entire file |
| Doctrine long-form | intelligence-compounding.md | docs/architecture/intelligence-compounding.md | Entire file |
| Truths Index ↔ findings sync | test_current_findings.py | tests/ | Entire file |
| Citation validity | test_doc_citations.py | tests/ | Entire file |

### Authority Assessment
- **Correctly assigned:** The doctrine is operationalized through test-enforced artifacts. test_current_findings.py creates a closed loop between the Truths Index and findings.
- **Limitation:** This infrastructure is CLAUDE-specific — a different LLM or a human reading the repo would not have CLAUDE.md's §6/§6.1/§6.2 enforced the same way.

---

## Domain: Four-Engine Scoring

### Thought → Code
| Intent Node | Code Implementation | File | Line(s) |
|-------------|-------------------|------|---------|
| CRT engine | CRTEngine.process_candle() | src/config_layer/crt_engine_v2.py | Entire file (~2500 lines) |
| Gaussian engine | HeuristicGaussianEngine.compute() | src/engines/heuristic_gaussian_engine.py | Entire file |
| ML Gaussian engine | MLGaussianEngine.compute() | src/engines/ml_gaussian_engine.py | Entire file |
| Zone gate engine | ZoneGateEngine.evaluate() | src/engines/zone_gate_engine.py | Entire file |
| RR engine | RREngine.compute() | src/engines/rr_engine.py | Entire file |
| Orchestrator | EngineRunner.run() | src/core/engine_runner.py | 546+ |
| Fusion | FusionEngine.compute() | src/core/fusion_engine.py | 290+ |
| Completeness check | EXPECTED_ENGINES set diff | src/core/engine_runner.py | (internal) |

### Authority Assessment
- **Correctly assigned:** All four engines are independently scorable and completeness-checked. The orchestrator enforces the "all four or nothing" invariant.
- **Belief-intent gap (not a code bug):** The user believed diverse engines → edge. The research program (F-019/020/021/025) falsified this belief. The code is technically correct — it does what was asked — but the underlying economic assumption has been disproven for the target universe.

---

## Domain: CRT State Machine Spine

### Thought → Code
| Intent Node | Code Implementation | File | Line(s) |
|-------------|-------------------|------|---------|
| State machine | CRTEngine class | src/config_layer/crt_engine_v2.py | Entire file |
| 9-state lifecycle | CRTState enum | src/config_layer/crt_engine_v2.py | (enum) |
| Legal transitions | VALID_TRANSITIONS | src/config_layer/crt_engine_v2.py | ~1025/1073/1098 |
| Scoring inside loop | process_candle() invokes all engines | src/config_layer/crt_engine_v2.py | (internal) |
| Telemetry | TelemetryCollector | src/config_layer/crt_engine_v2.py | ~200 lines |

### Authority Assessment
- **Correctly assigned:** The state machine is the spine — it orchestrates scoring, selection, and telemetry. VALID_TRANSITIONS is enforced.
- **Belief-intent gap (not a code bug):** The CRT market ontology (RANGE→SWEEP→DISPLACEMENT→...) is faithfully implemented. But for the crypto-major M15 universe, the entire state machine produces no positive-expectancy edge under realistic exits + cost. The code is right; the design belief was wrong.

---

## Domain: File-Backed Infrastructure

### Thought → Code
| Intent Node | Code Implementation | File | Line(s) |
|-------------|-------------------|------|---------|
| Config loader | get_prod_section() | src/config_layer/production_config.py | Entire file |
| JSONL telemetry | logs/*.jsonl | logs/ | Entire directory |
| Market data | data/*_M15.csv | data/ | Entire directory |
| Model artifacts | models/*.json | models/ | Entire directory |

### Authority Assessment
- **Largely aligned.** The file-backed invariant holds for the core system.
- **Contradiction noted:** sprint history shows psycopg2-binary was installed and INOUT had TimescaleDB schema DDL. The INOUT kitchen has since been archived, restoring the invariant.

---

## Orphans (Code Without Known Purpose)

| File | Reason for Orphan Status | Finding |
|------|------------------------|---------|
| src/core/ultron_risk_gate_wrapper.py | Regime pre-scaler — designed to be called before UltronRiskGate, never wired | F-013 (related) |
| src/governance/config_integrity.py | Runtime integrity guard — has check logic but zero callers on hot path | F-006 |
| src/scanner/* + src/execution/loop.py + src/portfolio/* | Multi-signal scan→allocate→ExecutionLoop — built but never called | F-013 |
| src/replay/replay_memory_engine.py + src/cognitive/ + src/features/cluster.py + src/analytics/hmf.py | Sidecar-only — zero spine consumption | F-012 |
| src/training/trade_net_v2.py | Complete 3-head model but fusion socket is permanently stub | F-005 |

## Economic Meaning
The codebase has ~5 identified orphan modules/abstractions. These represent developer time spent building infrastructure that was never integrated into the primary decision loop. The economic cost is the opportunity cost of that time, plus ongoing cognitive load (readers must understand why these files exist). Total cost estimate: medium.

## Unknowns
- Whether any orphan was deliberately built as "future architecture" rather than abandoned work.
- Whether the multi-signal path (F-013) was the original design intent that was later superseded by the single-candle spine.