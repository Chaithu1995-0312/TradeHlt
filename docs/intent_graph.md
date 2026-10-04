# Intent Graph — Repository-Wide User Thought Reconstruction

> **Purpose:** Recover the chain from `User Thought → Goal → Belief → Economic Meaning →
> Architecture Decision → Module → Runtime Effect` for every significant domain in this
> codebase. Produced during a repository-wide intent extraction and alignment audit
> (2026-06-13). Each chain is an *independent witness* — sourced from CLAUDE.md, goal.md,
> intelligence-compounding.md, assistant_project.md (2456 lines of session log),
> current-findings.md, signal-flow.md, codebase-state-map.md, and governance.md.
>
> **Evidence format per node:** Source doc:line (or session log date) — Confidence: [level]

---

## Chain 1: Capital Preservation (The "Don't Blow Up" Thought)

```
User Thought:
  "I don't want to lose money to randomness" — the primordial concern,
  predates any profit-seeking. Trading systems that produce +20% then -80%
  are unacceptable regardless of peak return.
  Evidence: intelligence-compounding.md:125    — Confidence: Certain
  Evidence: docs/analysis/phase0-economic-edge-diagnosis-2026-06-03.md    — Confidence: Certain

  ↓

Goal:
  Capital survival — zero catastrophic loss. Priority over profit.
  Risk gate is the LAST line of defense, not the first.
  Evidence: goal.md:25 "replay correctness > explainability > telemetry continuity > advisory-AI"
  Evidence: assistant_project.md:52 (priority order repeated)    — Confidence: Certain

  ↓

Belief:
  (a) Position-level risk gates should be deterministic, config-governed,
      and applied AFTER the trade plan is constructed, so they evaluate
      geometry+size together, not just an abstract score.
  (b) A single fat-tail loss can destroy years of compounding, so the
      gate must be hard (fail-fast, no fallback).
  (c) The LLM must never approve or place a trade — even an advisory
      override of the risk gate would violate the invariant.
  Evidence: goal.md:97 "LLM is advice, never a trigger"    — Confidence: Certain
  Evidence: signal-flow.md:97 "fail-fast — this is the last deterministic capital check"    — Confidence: Certain

  ↓

Economic Meaning:
  Survival > profit. The utility function is logarithmic (Kelly-adjacent),
  not linear. Avoiding -80% drawdown is worth more than capturing +5%
  upside at the same variance. Fat-tail protection is the primary value.
  Evidence: current-findings.md F-001 (F-002's "selection, not SL/TP" subordinate)    — Confidence: Likely

  ↓

Architecture Decision:
  Seven-check waterfall gate (UltronRiskGate) after the execution planner.
  Gate reads from config (max_risk_per_trade_pct, drawdown caps, daily-trade
  limit, correlation thresholds). Returns APPROVE/REJECT with structured reason.
  Separate object: UltronRiskGateWrapper (pre-scales risk_percent by regime)
  exists but is NOT wired in production — an ORPHAN of the same thought.
  Evidence: codebase-state-map.md:89 (UltronRiskGate table)    — Confidence: Certain
  Evidence: signal-flow.md:90–102 (Step 6 description)    — Confidence: Certain
  Evidence: assistant_project.md:1292–1297 (Ultron disambiguation: 3 objects, 1 orphan)    — Confidence: Certain

  ↓

Modules:
  src/core/ultron_risk_gate.py       — the 7-check waterfall
  src/core/ultron_risk_gate_wrapper.py — ORPHAN (regime pre-scaler, unwired)
  — Confidence: Certain

  ↓

Runtime Effect:
  Every trade plan passes through Approve/Reject gate before execution.
  If REJECT, trade is logged but never dispatched. Gate is fail-fast
  (no fallback for capital check).
  Evidence: signal-flow.md:97–98    — Confidence: Certain

ALIGNMENT STATUS: LIKELY ALIGNED — the gate exists and executes. However:
  - The orphan wrapper suggests a belief ("risk should be regime-scaled")
    that was never fully operationalized.
  - The gate is NOT exercised in the backtest spine (F-010: live PnL
    unverified), creating a backtest-vs-live divergence risk if config
    values differ (ultron_gate_enabled=false in backtest but true in live).
```

---

## Chain 2: Config Governance (The "No Accidental Promotion" Thought)

```
User Thought:
  "Don't repeat mistakes." Every production config change must be
  intentional, reversible, and auditable. A bad config reaching production
  is a process failure, not a code failure.
  Evidence: intelligence-compounding.md:127 ("PromotionManager — 'Don't repeat mistakes'")    — Confidence: Certain

  ↓

Goal:
  Zero ungoverned config changes reach production. Every promotion is
  validated, hashed, logged, and rollback-able.
  Evidence: goal.md:19–20 ("Nothing reaches production without passing governance")    — Confidence: Certain

  ↓

Belief:
  (a) Validation through backtest + hard gates is superior to manual review.
  (b) SHA-256 hashing prevents silent config drift (same params = same hash).
  (c) Append-only audit log (promotion_log.jsonl) cannot be rewritten,
      making all promotion history immutable.
  (d) The "path to production" is a single function: PromotionManager —
      no other code path should write to configs/production/.
  Evidence: governance.md:1–5 (promotion flow)    — Confidence: Certain
  Evidence: governance.md:390 (write-authority matrix)    — Confidence: Certain

  ↓

Economic Meaning:
  Avoiding regressions in production is a high-ROI activity — a single
  ungoverned config that destroys 6 months of gains costs more than the
  entire governance infrastructure. Governance is the #1 binding constraint
  (F-001). The cost of a false promotion (bad config reaches live) exceeds
  the cost of a false rejection (good config delayed).
  Evidence: current-findings.md F-001 ("Intelligence is NOT the binding constraint —
    governance / throughput / consumption are")    — Confidence: Certain
  Evidence: current-findings.md F-006 ("config_integrity is a REAL check but ORPHANED")    — Confidence: Certain

  ↓

Architecture Decision:
  ConfigValidator (hard gates: min_trades=10, max_drawdown=35%, min_fitness=0.15;
  soft gates: win_rate, expectancy, cross-instrument consistency) produces
  ValidationReport with APPROVE/REJECT. Only APPROVED reports enter
  PromotionManager, which archives the existing config, writes the new one,
  computes SHA-256, and appends to promotion_log.jsonl.
  The config_integrity.py module EXISTS but is ORPHANED — it was written to
  be a runtime guard but has zero callers on the hot path.
  Evidence: governance.md:10–37 (the promotion path)    — Confidence: Certain
  Evidence: current-findings.md F-006:123 ("config_integrity is a REAL check but ORPHANED")    — Confidence: Certain

  ↓

Modules:
  src/governance/promotion_manager.py    — the only path to production
  src/config_layer/config_validator.py   — validation gates
  src/governance/config_integrity.py     — ORPHAN (check exists, gate doesn't)
  src/governance/shadow_promotion_gate.py — optional second-stage
  src/governance/meta_governor_executor.py — autonomous proposal (never promotes directly)
  — Confidence: Certain

  ↓

Runtime Effect:
  - Every config change goes through: tuner → ConfigValidator →
    PromotionManager → registry write + promotion_log append.
  - configs/production/ contains only governed versions + archived predecessors.
  - ACTIVE_VERSION is the runtime pointer (v2_multi_2026_04 on `patch`).
  - However: the deepdeektry suffix (F-016) EVADED this system — the
    config_integrity gate that should catch suffix mismatches is orphaned.
  Evidence: current-findings.md F-016 et al. (the deepdeektry suffix gap)    — Confidence: Certain

ALIGNMENT STATUS: LIKELY ALIGNED IN INTENT, PARTIALLY BROKEN IN EXECUTION
  - The governance path exists and is enforced.
  - But the ACTIVE_VERSION "v2_multi_2026_04 - deepdeektry" does not match
    any promotion_log entry (the log has "v2_multi_2026_04" without suffix).
    The orphaned config_integrity gate is the gap that allowed this.
  - The split-brain with v4 (F-016/F-007) is a BRANCH divergence, not a
    governance failure — but it manifested because governance is branch-scoped
    and the truth maintenance doctrine (since codified as §6.2) was absent.
```

---

## Chain 3: Deterministic Replay (The "Same Inputs, Same Outputs" Thought)

```
User Thought:
  "I must be able to trust the backtest." If the system cannot reproduce
  the same result from the same data under the same config, every backtest
  output is suspect and no improvement can be attributed correctly.
  Evidence: CLAUDE.md:91 ("Same inputs → same outputs")    — Confidence: Certain

  ↓

Goal:
  Byte-identical reproducibility across runs. No random seed drift, no
  wall-clock dependency, no hash-based ordering, no lookahead.
  Evidence: goal.md:91–92 (invariant #1: same inputs → same outputs)    — Confidence: Certain

  ↓

Belief:
  (a) Determinism is more important than speed — you can optimize later,
      but you cannot de-bias a non-reproducible result.
  (b) Slippage must be seeded deterministically. Comparison must ignore
      event_id/generation/wall-clock timestamp.
  (c) The research platform must produce byte-identical edge reports across
      runs — determinism is the trust foundation for every experiment.
  Evidence: goal.md:65–67 (standing rules: comparison ignores event_id/generation/timestamp)    — Confidence: Certain
  Evidence: assistant_project.md:1936–1937 (M3: byte-identical edge_report, deterministic provenance)    — Confidence: Certain

  ↓

Economic Meaning:
  Trust in the measurement instrument is the precondition for every economic
  finding. Without determinism, signal and noise are indistinguishable.
  The cost of a false discovery (acting on non-reproducible noise) is far
  higher than the cost of building reproducible infrastructure.
  Evidence: assistant_project.md:1952–1955 (Backtest Trust Layer: independence, parity, replay)    — Confidence: Likely

  ↓

Architecture Decision:
  (1) metrics_oracle.py — independent metric recompute (no MetricsEngine import),
      parity gate (10/10) + replay determinism gate (byte-identical).
  (2) Golden ledgers A–E with invariants — 113 tests exact.
  (3) Dataset integrity preflight (validate_dataset before any run).
  (4) Research platform: HypothesisRunner produces byte-identical edge_report
      via deterministic CandleLoader streaming + seeded forward_walk.
  Evidence: assistant_project.md:1953–1954 (trust layer: oracle + parity + golden ledgers)    — Confidence: Certain
  Evidence: assistant_project.md:1988–1991 (L3 cross-file + SHA-256 dup detection)    — Confidence: Certain

  ↓

Modules:
  src/runtime/backtest_v2.py           — the replay loop
  src/analytics/metrics_oracle.py      — independent metric recompute
  src/data_ingestion/dataset_integrity.py — preflight gate (FATAL/ERROR/WARN)
  src/data_ingestion/ohlcv_schema.py   — strict column schema enforcement
  src/research/runner.py                — deterministic HypothesisRunner
  — Confidence: Certain

  ↓

Runtime Effect:
  - Two backtest runs with same CSV + same config → byte-identical
    trades + telemetry + events + summary (proven for BNBUSDT and SOLUSDT).
  - Preflight gate REJECTs corrupt datasets before they can pollute results.
  - Research edge reports are byte-identical across runs.
  Evidence: assistant_project.md:2248 (proved full-artifact byte-determinism across 2 runs × 2 instruments)    — Confidence: Certain

ALIGNMENT STATUS: ALIGNED — proven by evidence (ledger SHA matches, golden
  ledgers pass, determinism test verifies byte-identity). This is the MOST
  aligned chain in the repository. The trust layer is the strongest asset.
```

---

## Chain 4: Advisory-Only LLM (The "LLM Is Not In Charge" Thought)

```
User Thought:
  "I don't want an LLM trading my money." A large language model can
  contribute narrative insight, tie-break ambiguous signals, and suggest
  research directions — but it must NEVER approve, place, or size a trade,
  and the system must survive its complete absence.
  Evidence: goal.md:95 ("The LLM is advice, never a trigger")    — Confidence: Certain

  ↓

Goal:
  LLM is completely isolated from execution authority. Fail-count
  disable kicks in after N failures, returning neutral (1.0). System
  must work identically with or without LLM connectivity.
  Evidence: CLAUDE.md:118–119 ("LLM is a tie-breaker, not a hot-path dependency")    — Confidence: Certain

  ↓

Belief:
  (a) If the system cannot tolerate the LLM being absent or wrong, the
      architecture is wrong.
  (b) Circuit-breaker pattern: after fail_count_disable failures, return
      neutral 1.0 — never block the trading loop.
  (c) Governance-mode agent uses deterministic PLAN_REGISTRY, not LLM
      planning. LLM's role is restricted to: intent classification,
      argument filling, copilot advice, summarization.
  Evidence: CLAUDE.md:118–119 (fail_count_disable=10, request_timeout=2.0s)    — Confidence: Certain
  Evidence: assistant_project.md:1221–1222 (PlanCompiler: deterministic PLAN_REGISTRY, LLM no longer chooses tools)    — Confidence: Certain

  ↓

Economic Meaning:
  LLM integration risk (hallucination, latency, cost) must be bounded
  to zero probability of execution impact. The LLM can ADD value through
  narrative/copilot insight, but can never SUBTRACT value through wrong
  actions. A neutral default (1.0) is the zero-cost fallback.
  Evidence: CLAUDE.md:118 (LLM is not a hot-path dependency)    — Confidence: Certain

  ↓

Architecture Decision:
  (1) llama_gate/llm_inference_client with circuit breaker (fail_count_disable=10,
      request_timeout=2.0s, returns 1.0 on failure).
  (2) PlanCompiler with deterministic PLAN_REGISTRY — LLM never plans,
      only fills arguments.
  (3) Agent Executor with confirm-gate + path-guard — write tools require
      per-call y/N confirmation. write_tools_enabled is empty by default.
  (4) Path-guard restricts write operations to configs/production/|logs/|results/.
  Evidence: CLAUDE.md:69 (PlanCompiler: deterministic by design)    — Confidence: Certain
  Evidence: CLAUDE.md:119 (fail_count_disable=10, returns 1.0 on failure)    — Confidence: Certain

  ↓

Modules:
  src/config_layer/llama_gate.py          — LLM client + circuit breaker
  src/config_layer/llm_inference_client.py — fail-open inference
  src/config_layer/llm_scorer.py          — circuit-breaker scorer
  src/agent/plan_compiler.py              — deterministic PLAN_REGISTRY
  src/agent/executor.py                   — confirm-gate + path-guard
  src/agent/tool_registry.py              — write_tools_enabled gate
  — Confidence: Certain

  ↓

Runtime Effect:
  - Every LLM call can fail silently without blocking the trading loop.
  - Agent plan execution is fully deterministic (PLAN_REGISTRY maps intent→tools).
  - Write operations require user confirmation + path whitelist.
  - No code path exists where an LLM output can directly place a trade.
  Evidence: CLAUDE.md:69 (deterministic by design)    — Confidence: Certain
  Evidence: codebase-state-map.md:61–62 (agent paths: executor + confirm-gate)    — Confidence: Certain

ALIGNMENT STATUS: ALIGNED — the LLM-isolation architecture is well-exercised
  and enforced at multiple levels (circuit breaker, PLAN_REGISTRY, confirm-gate,
  path-guard). The threat model (LLM hallucination → trade) is fundamentally
  mitigated. The orphan gap (GovernanceOrchestrator referencing 70B vs actual 3B)
  suggests the LLM *layer* design may exceed what the actual BitNet 3B can deliver.
```

---

## Chain 5: Intelligence Compounding (The "Never Lose Meaning" Thought)

```
User Thought:
  "I don't just want the code to work — I want every session to build on
  every previous session. The repository should grow smarter over time,
  not just accumulate more files." This is explicit in CLAUDE.md §6.1.
  Evidence: CLAUDE.md:149–160 ("Intelligence Compounding Doctrine")    — Confidence: Certain

  ↓

Goal:
  Zero intelligence loss + continuous intelligence compounding. Every tool
  output must be interpreted in terms of the user's economic objectives.
  Intelligence = ROI-weighted belief change toward a goal, not accumulated data.
  Evidence: intelligence-compounding.md:21–32 (one goal: zero intelligence loss)    — Confidence: Certain

  ↓

Belief:
  (a) Information ≠ intelligence. Data without meaning is noise.
  (b) "Artifacts are recoverable. Meaning is not." — the economic *why* is
      the true intelligence; code is just its manifestation.
  (c) ROI without a goal is undefined — every interpretation starts from
      the user's objective.
  (d) Modules are frozen thoughts — understanding *what* code does is
      insufficient without knowing *why* it exists.
  Evidence: intelligence-compounding.md:104–133 (Modules are frozen thoughts)    — Confidence: Certain
  Evidence: CLAUDE.md:164–167 (forbidden raw Tool→Memory path)    — Confidence: Certain

  ↓

Economic Meaning:
  The repository's primary utility is NOT the code but the accumulated
  understanding of what works, what doesn't, and why — encoded as findings,
  session logs, and doctrine. A null financial result with a clear conclusion
  (e.g. "EMA gate is non-binding → stop exploring it") carries HIGH
  knowledge-ROI. Intelligence leakage = finding an answer and losing it.
  Evidence: intelligence-compounding.md:146–149 (high ROI on null results)    — Confidence: Certain

  ↓

Architecture Decision:
  (1) Per-response SESSION LOG with Belief Update / ROI / Goal field (§7.4).
  (2) current-findings.md — living repository of validated conclusions,
      test-enforced by test_current_findings.py.
  (3) Truth Maintenance Doctrine (§6.2) — 7 rules, append-discipline,
      branch-scoped truth, Authority tiers 0–4.
  (4) Memory files (.claude/projects/memory/) with MEMORY.md index.
  (5) docs/analysis/ — point-in-time evidence (not living docs).
  Evidence: CLAUDE.md:200–222 (§6.2 Repository Truth Maintenance Doctrine)    — Confidence: Certain
  Evidence: CLAUDE.md:139–148 (§6 Persistent Logging Mandate)    — Confidence: Certain

  ↓

Modules:
  assistant_project.md           — append-only SESSION LOG (2456 lines, 100+ entries)
  docs/current-findings.md       — living repository truths (F-001..F-025)
  docs/architecture/intelligence-compounding.md — doctrine long-form
  tests/test_current_findings.py — enforcement
  — Confidence: Certain

  ↓

Runtime Effect:
  - Every response appends a timestamped SESSION LOG entry capturing decisions,
    belief updates, and open questions.
  - Findings are added/flipped in the SAME turn they are validated or overturned.
  - The enforcement test ensures the Truths Index ↔ current-findings ↔ CLAUDE.md
    are synchronized.
  - History is never deleted — superseded findings stay as rows.
  Evidence: CLAUDE.md:221–222 (Findings Mandate)    — Confidence: Certain

ALIGNMENT STATUS: ALIGNED — the doctrine is operationalized through a multi-layer
  system (SESSION LOG → findings → test enforcement → memory). The weakest link
  is that this is CLAUDE-specific infrastructure — a human or different LLM
  reading the repo would not see CLAUDE.md's §6/§6.1/§6.2 enforced the same way.
```

---

## Chain 6: Four-Engine Scoring (The "Diverse, Independent Opinions" Thought)

```
User Thought:
  "A single model will overfit to one pattern. I want four independent
  scoring engines, each looking at the candle from a different angle —
  CRT (structure), Gaussian (statistical), Zone Gate (cluster membership),
  RR (risk-reward). Consensus among them is meaningful; any single one
  can be wrong."
  Evidence: goal.md:40–52 (four engines, independently)    — Confidence: Certain

  ↓

Goal:
  Every candle is scored by exactly four engines. Partial fusion is forbidden.
  A missing engine is a hard reject, not a quiet partial score.
  Evidence: goal.md:93–94 (invariant #2: all four engines or nothing)    — Confidence: Certain

  ↓

Belief:
  (a) Model diversity reduces the probability of acting on a single model's
      error. The fusion gate checks completeness BEFORE combining scores.
  (b) Each engine has a distinct ontology: CRT=market structure,
      Gaussian=statistical likelihood, Zone=cluster similarity, RR=risk geometry.
  (c) No engine is optional — if any fails to produce a score, the candle
      produces no trade. This is a deliberate throughput sacrifice for quality.
  Evidence: engine_runner.py:EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}    — Confidence: Certain
  Evidence: CLAUDE.md:115–116 ("Four engines are mandatory")    — Confidence: Certain

  ↓

Economic Meaning:
  The fusion of four independent, complementary signals is expected to
  produce higher-quality decisions than any single engine. The completeness
  gate is a safety invariant: partial information is worse than no information.
  This belief has been PARTIALLY FALSIFIED by F-002/F-021: the evidence shows
  that selection (which candle gets a trade) matters far more than the
  scores themselves — the engine diversity alone does not drive edge.
  Evidence: current-findings.md F-002 ("the edge is in the decision PROCESS")    — Confidence: Likely
  Evidence: current-findings.md F-021 ("RETEST selection IS the session filter")    — Confidence: Likely

  ↓

Architecture Decision:
  (1) EngineRunner.run() unconditionally invokes all 4 engines.
  (2) After scoring, completeness check (EXPECTED_ENGINES set diff).
  (3) FusionEngine.compute() combines scores under weighted-completeness gate.
  (4) Dual-engine regime gate (RegimeGovernor) runs optionally as Step 6.
  Evidence: signal-flow.md:48–62 (Step 3: scoring engines)    — Confidence: Certain
  Evidence: assistant_project.md:1282–1291 (EngineRunner 8-step wiring)    — Confidence: Certain

  ↓

Modules:
  src/config_layer/crt_engine_v2.py          — CRT state machine (the spine)
  src/engines/heuristic_gaussian_engine.py    — Gaussian scoring
  src/engines/ml_gaussian_engine.py           — ML Gaussian (env-opt-in)
  src/engines/zone_gate_engine.py             — BitNet zone scoring
  src/engines/rr_engine.py                    — risk-reward scoring
  src/core/engine_runner.py                   — orchestrator
  src/core/fusion_engine.py                   — weighted fusion
  — Confidence: Certain

  ↓

Runtime Effect:
  Every candle is scored by all 4 engines. If any engine is unavailable,
  the candle produces NO trade (completeness reject). The fused score is
  the weighted combination of all 4 scores.
  Evidence: signal-flow.md:57–58 (missing_engines = EXPECTED_ENGINES - engine_results.keys())    — Confidence: Certain

ALIGNMENT STATUS: TECHNICALLY ALIGNED, ECONOMICALLY FALSIFIED
  - The code faithfully implements "4 engines, complete, fused."
  - But the research program (F-019/020/021/025) has shown that the
    four-engine scoring pipeline produces NO positive-expectancy edge
    under realistic exits + cost. The ARCHITECTURE is correct — it does
    what the user asked — but the BELIEF that engine diversity creates
    edge has been empirically falsified.
  - NOTE: This is NOT a code bug. It is a belief-intent gap: the user
    thought diverse engines → edge, but the evidence says otherwise.
```

---

## Chain 7: No Database / File-Backed (The "Simple, Survivable Infrastructure" Thought)

```
User Thought:
  "No database, no message broker, no cloud services. I want to be able
  to inspect every piece of state by reading a file with any text editor.
  The system should survive a full rebuild from a git clone + pip install."
  Evidence: CLAUDE.md:11 ("Everything is file-backed — no database, no message broker, no cloud deps")    — Confidence: Certain

  ↓

Goal:
  Zero external infrastructure dependencies. State is in JSON configs,
  JSONL event logs, CSV data files. A complete system snapshot is a
  directory copy.
  Evidence: goal.md:104 (invariant #7: no database, no broker, no cloud dependency)    — Confidence: Certain

  ↓

Belief:
  (a) Complexity kills trading systems. Each infrastructure dependency
      adds a failure mode.
  (b) File-backed state is more inspectable, more auditable, and more
      portable than any database.
  (c) JSONL append-only logs are the ideal format for telemetry: they
      are human-readable, machine-parseable, trivially compressible,
      and cannot be silently mutated.
  Evidence: CLAUDE.md:11 (file-backed: no DB, no broker, no cloud)    — Confidence: Certain

  ↓

Economic Meaning:
  Infrastructure simplicity is a direct contributor to reliability.
  Every database connection, message queue, and cloud API call is a
  potential point of failure that does not contribute to trading edge.
  The cost of in-memory/on-disk state is essentially zero compared to
  the cost of operational complexity.
  Evidence: goal.md:104 (invariant #7 listed alongside determinism/no-lookahead)    — Confidence: Certain

  ↓

Architecture Decision:
  (1) All state is files: configs/production/*.json (config), data/*_M15.csv
      (market data), logs/*.jsonl (telemetry), models/*.json (artifacts).
  (2) PromotionManager writes configs + promotion_log.jsonl (append).
  (3) Telemetry is additive JSONL — new fields added, old ones never removed.
  (4) The AI agent's audit trail is logs/agent_audit.jsonl.
  (5) No ORM, no connection pool, no database migration.
  Evidence: CODEBASE-STATE-MAP.md:27 ("All state is files — JSON configs + JSONL event logs")    — Confidence: Certain

  ↓

Modules:
  configs/production/*            — governed configurations
  data/*_M15.csv                  — market data (OHLCV)
  logs/*.jsonl                    — event telemetry
  models/*.json                   — trained model artifacts
  src/config_layer/production_config.py — file-backed config loader
  — Confidence: Certain

  ↓

Runtime Effect:
  - Start the system: it reads data/ CSV files and configs/production/ version.
  - During a backtest: it writes results/run_<ts>_<instr>/ artifacts.
  - After a session: the full state is on disk.
  - No database to start, no broker to connect, no cloud to authenticate.
  Evidence: README.md:34–38 (run first backtest with CSV file)    — Confidence: Certain

ALIGNMENT STATUS: LARGELY ALIGNED — the file-backed invariant holds for
  the core system. HOWEVER: sprint history shows psycopg2-binary was
  installed and INOUT had TimescaleDB schema DDL — a CONTRADICTION,
  though the INOUT kitchen has since been archived. The "no DB" rule
  was violated in intent (INOUT assumed a database) before being
  restored by archival.
```

---

## Chain 8: Research Isolation (The "Don't Let Experiments Corrupt Production" Thought)

```
User Thought:
  "I need to experiment freely without any risk to the live trading path.
  A research module should not even be ABLE to import production
  infrastructure — the dependency direction goes one way only."
  Evidence: CLAUDE.md:6 (governance/execution/research separation implied)    — Confidence: Certain
  Evidence: assistant_project.md:1902 (research modules isolated from live CRT spine)    — Confidence: Certain

  ↓

Goal:
  Research is a separate, parallel infrastructure that measures the
  production system from outside. Zero coupling from research → production.
  Research can import from data_ingestion and utils, but never from
  engine_runner/fusion/decision/promotion.
  Evidence: assistant_project.md:1902 ("Isolation lint clean — no engine_runner/promotion_manager/config_validator imports")    — Confidence: Certain

  ↓

Belief:
  (a) The measurement instrument must be independent of the thing being
      measured. If research reuses the production scoring code, it loses
      an independent audit.
  (b) The truth standard (intrabar_fixed exits, flat 12bps cost) must be
      consistent across ALL research experiments.
  (c) Discovery and production are fundamentally different activities
      with different truth standards — they must not share infrastructure.
  Evidence: assistant_project.md:2014–2018 (B0: research already did intrabar touch + SL-before-TP)    — Confidence: Certain

  ↓

Economic Meaning:
  Research independence is the precondition for honest measurement. A
  research result that reuses production code tests whether the production
  system is self-consistent, NOT whether the behavior is economic. The
  cost of false discovery from non-independent measurement is infinite
  (it leads to believing edge exists when it doesn't).
  Evidence: assistant_project.md:2017 (RESEARCH/SPINE_COST_MODEL_VERSION diverged deliberately)    — Confidence: Likely

  ↓

Architecture Decision:
  (1) src/research/ is a separate package with its own config system
      (research_config.json, not production_config.json).
  (2) It uses its own CandleLoader (not BacktestRunner), own forward_walk
      (not EngineRunner), own metrics (EdgeAggregator, not MetricsEngine).
  (3) The spine is measured AS A HYPOTHESIS via ProductionSpineSource
      adapter — one-way coupling.
  (4) Multiple truth standards: RESEARCH_TRUTH_STANDARD_VERSION,
      SPINE_COST_MODEL_VERSION, QUALIFICATION_VERSION — not shared.
  Evidence: assistant_project.md:1902 (forward_walk.metrics — isolated)    — Confidence: Certain
  Evidence: assistant_project.md:2015–2016 (provenance.py: TRUTH_STANDARD_VERSION=2.0)    — Confidence: Certain

  ↓

Modules:
  src/research/contracts.py        — Signal, Outcome, EdgeReport, Hypothesis Protocol
  src/research/runner.py            — deterministic HypothesisRunner
  src/research/measurement/         — forward_walk, metrics
  src/research/forensics.py         — trade-by-trade analysis
  src/research/qualification.py     — M4 QualificationGate (7 ordered gates)
  src/research/process_characterization.py — volatility/direction diagnostics
  src/research/hypotheses/          — spine_hypothesis, expansion_breakout, etc.
  — Confidence: Certain

  ↓

Runtime Effect:
  Research experiments run on CSV data through their own pipeline, produce
  edge_reports, and file findings. They never touch production configs,
  the live spine, or the promotion path. The spine can be measured AS A
  hypothesis through a one-way adapter.
  Evidence: assistant_project.md:1902–1904 (isolation lint clean, no forbidden imports)    — Confidence: Certain

ALIGNMENT STATUS: ALIGNED — isolation is well-enforced (test-level lint check,
  separate config, separate runner, one-way spine adapter). The discipline
  of multiple truth standards is sophisticated and correct.
```

---

## Chain 9: CRT State Machine Spine (The "Market Structure Drives Everything" Thought)

```
User Thought:
  "Markets don't move randomly — they cycle through recognizable structural
  phases: ranging, sweeping liquidity, displacing, expanding, retesting,
  executing, resolving. The trading system should model this lifecycle."
  Evidence: goal.md:48–52 (9-state CRT lifecycle, golden path)    — Confidence: Certain

  ↓

Goal:
  A state machine that classifies every candle's market structure context.
  The state determines whether a setup exists, and the setup's phase
  determines the trading decision.
  Evidence: CLAUDE.md:121–122 (CRTState transitions: RANGE→SWEEP→DISPLACEMENT→EXPANSION→RETEST→EXECUTION→RESOLUTION)    — Confidence: Certain

  ↓

Belief:
  (a) The CRT state machine is the "spine" — it is not just one of four
      engines, it is the orchestrating structure that the other three
      engines are ancillary to.
  (b) State transitions are a fixed legal graph — illegal jumps are rejected.
  (c) The state machine plus session filter IS the selection mechanism
      (F-021: RETEST selection = session filter).
  Evidence: goal.md:49–51 (CRT state machine is the spine)    — Confidence: Certain
  Evidence: current-findings.md F-021 ("the spine's RETEST selection IS the session filter")    — Confidence: Likely

  ↓

Economic Meaning:
  The CRT state machine encodes a specific market ontology — the belief
  that market structure follows the CRT lifecycle. If markets DO follow
  this structure, the spine captures the decision-relevant context. If
  they DON'T (as F-019/020/021/025 suggest), the spine is a structural
  constraint with no edge. The economic finding: under intrabar+12bps,
  the CRT spine produces no positive-expectancy trades.
  Evidence: current-findings.md F-025 ("FOURTH falsification — entry/conditional/selection/exit all null")    — Confidence: Likely

  ↓

Architecture Decision:
  (1) CRT config lives in crt_engine.py/crt_engine_v2.py — ~2500 lines
      covering state machine, configuration, scoring, and telemetry.
  (2) 9 states (RANGE, SWEEP, DISPLACEMENT, EXPANSION, RETEST, EXECUTION,
      RESOLUTION, SHADOW_PENDING, EXPIRED) with VALID_TRANSITIONS map.
  (3) The Engines are invoked inside the state machine's process_candle().
  (4) Backtesting replays the state machine candle-by-candle.
  Evidence: codebase-state-map.md:43 (crt_engine_v2.py: CRTState, CRT computation)    — Confidence: Certain
  Evidence: signal-flow.md:29–112 (Steps 1–7: the CRT spine walk)    — Confidence: Certain

  ↓

Modules:
  src/config_layer/crt_engine_v2.py — CRT state machine (~2500 lines)
  src/config_layer/crt_engine.py    — legacy wrapper
  src/runtime/backtest_v2.py        — replays the state machine
  — Confidence: Certain

  ↓

Runtime Effect:
  Every candle flows through process_candle() which walks the state machine.
  The state determines whether a setup (SWEEP) is detected, whether it
  progresses through EXPANSION and RETEST to EXECUTION, and whether the
  trade eventually resolves or expires. All four ancillary engines score
  the candle inside this same loop.
  Evidence: signal-flow.md:25–112 (Steps 1–7)    — Confidence: Certain

ALIGNMENT STATUS: TECHNICALLY ALIGNED, ECONOMICALLY FALSIFIED
  - The state machine is faithfully implemented and enforces legal transitions.
  - But the market ontology it encodes has been empirically falsified for
    the crypto-major M15 universe. The architecture is correct code that
    implements a disproven belief. This is the most important finding in
    the audit: the code is RIGHT but the THOUGHT was WRONG.
  - This is NOT a code bug — it is a design belief that was falsified
    through the research program.
```

---

## Chain 10: Truth Maintenance (The "Never Let Documentation Drift" Thought)

```
User Thought:
  "The code is the truth, but if the docs disagree with the code, someone
  will trust the docs and make a wrong decision. I need a system to
  detect and resolve documentation drift automatically."
  Evidence: CLAUDE.md:194–222 (§6.2 Repository Truth Maintenance Doctrine)    — Confidence: Certain

  ↓

Goal:
  Zero silent truth divergence. When code changes, the corresponding docs,
  findings, tests, and topic files must change in the same turn.
  Evidence: CLAUDE.md:201 ("zero silent truth divergence")    — Confidence: Certain

  ↓

Belief:
  (a) Most "bugs" in the repo are documentation entropy — uncontrolled
      truth duplication — not code errors.
  (b) Aligned = no-op. DOC_DRIFT = code wins (fix the doc). CODE_DRIFT =
      doc wins (fix the code).
  (c) When authorities disagree, surface a TruthConflict — never silently
      resolve or invent a third answer.
  (d) History is preserved; truth evolves on top of it.
  Evidence: CLAUDE.md:200–222 (§6.2 rules 1–7)    — Confidence: Certain

  ↓

Economic Meaning:
  Documentation drift costs compound exponentially — each reader who
  trusts stale docs and makes a wrong decision creates a cost that
  grows with the number of readers. The enforcement tests (test_current_findings,
  test_doc_citations, test_topic_docs) are cheap insurance against this.
  Evidence: CLAUDE.md:222 (Findings Mandate + test enforcement)    — Confidence: Certain

  ↓

Architecture Decision:
  (1) 4 authority tiers (runtime > code schema > promotion_log > session memory).
  (2) 3 enforcement tests: test_current_findings (truths ↔ index ↔ CLAUDE.md),
      test_doc_citations (path:line symbols), test_topic_docs (concept docs).
  (3) Append-discipline: never delete a finding — mark SUPERSEDED/RETIRED.
  (4) Findings Mandate: validate or overturn in the SAME turn.
  Evidence: CLAUDE.md:194–212 (Tiers 0–4, 7 rules, Findings Mandate)    — Confidence: Certain

  ↓

Modules:
  docs/current-findings.md                    — living truths
  docs/architecture/citation-map.generated.md — citation index
  tests/test_current_findings.py              — truth index ↔ findings sync
  tests/test_doc_citations.py                — path:line citation validity
  tests/test_topic_docs.py                   — topic doc sync
  — Confidence: Certain

  ↓

Runtime Effect:
  - Every session that validates/overturns a finding must flip it in
    current-findings.md in the same response.
  - test_current_findings.py fails if any non-terminal finding is in
    the index but not in current-findings, or vice versa.
  - test_doc_citations.py fails if code moves and doc path:line refs
    become stale.
  - The truth system is itself test-enforced, creating a closed loop.
  Evidence: CLAUDE.md:222 (Findings Mandate enforced by tests)    — Confidence: Certain

ALIGNMENT STATUS: ALIGNED — the truth maintenance system is self-reinforcing
  and test-enforced. The F-007→F-016 reconciliation (branch-scoped v4→v2
  correction) is a worked example of the system operating correctly. The
  residual risk is human non-compliance (forgetting to update findings
  in the same turn), which the SESSION LOG mandate partially mitigates.
```

---

## Chain 11: Advisory AI Agent (The "Deterministic Automation, Not Autonomous AI" Thought)

```
User Thought:
  "I want an AI assistant that helps me run the system — but it must be
  predictable and safe. It should follow a script (deterministic plans),
  not generate plans on its own. Every write operation needs confirmation."
  Evidence: CLAUDE.md:68–70 (PlanCompiler: deterministic by design — do not route planning through LLM)    — Confidence: Certain

  ↓

Goal:
  An agent that can execute pipelines (tune→validate→promote→backtest),
  provide advisory copilot insight on live signals, and run governance
  procedures — all without any autonomous planning authority.
  Evidence: agent-reference.md (3 modes: pipeline, copilot, governance)    — Confidence: Certain

  ↓

Belief:
  (a) Deterministic plan registry (PLAN_REGISTRY) is superior to LLM-driven
      planning for reliability and auditability.
  (b) The agent should never have write authority by default (write_tools_enabled
      empty). Writes require both path-guard and y/N confirm.
  (c) The agent operates in three distinct authority modes: pipeline (triggers
      the spine), copilot (taps the spine read-only), governance (runs offline).
  Evidence: CLAUDE.md:69–70 (deterministic by design, write authority matrix)    — Confidence: Certain

  ↓

Economic Meaning:
  The agent reduces the operator's cognitive load without introducing
  autonomy risk. Pipeline mode automates rote sequences (tuner→validate→promote).
  Copilot mode provides narrative insight without trading authority.
  Governance mode provides offline reasoning without execution reach.
  The cost of a single autonomous mistake is higher than the total benefit
  of all automation.
  Evidence: CLAUDE.md:67–70 (3 surfaces: CLI, control plane, agent)    — Confidence: Likely

  ↓

Architecture Decision:
  (1) IntentRouter: regex (0.85 confidence) → LLM fallback → ask_user.
  (2) PlanCompiler: PLAN_REGISTRY maps intent_key → ordered ToolStep list.
  (3) Executor: confirm-gate + path-guard for write operations.
  (4) ToolRegistry: 20 tools grouped by mode, write flags explicit.
  (5) Audit: per-step + per-session logs to agent_audit.jsonl.
  Evidence: CLAUDE.md:29–31 (agent-reference.md: complete agent reference)    — Confidence: Certain
  Evidence: CLAUDE.md:69 (PlanCompiler: deterministic by design)    — Confidence: Certain

  ↓

Modules:
  src/agent/intent_router.py    — regex + LLM intent classification
  src/agent/plan_compiler.py    — deterministic PLAN_REGISTRY
  src/agent/executor.py         — confirm-gate + path-guard
  src/agent/tool_registry.py    — 20 tools, write flags
  src/agent/audit.py            — structured audit JSONL
  — Confidence: Certain

  ↓

Runtime Effect:
  - User speaks a command → IntentRouter classifies → PlanCompiler
    returns a deterministic tool sequence → Executor runs each tool
    (write tools require y/N).
  - The agent never "decides" what to do — it follows a lookup table.
  - Every action is logged in agent_audit.jsonl for replay.
  Evidence: CLAUDE.md:67–70 (agent surfaces and deterministic design)    — Confidence: Certain

ALIGNMENT STATUS: ALIGNED — the agent architecture faithfully implements
  the "deterministic, confirm-gated, auditable" vision. The PlanCompiler's
  PLAN_REGISTRY is the key innovation that prevents LLM-driven planning.
  The write_tools_enabled empty-by-default default ensures safety.
```

---

## Chain 12: Event-Driven Migration (The "One Service At A Time" Thought)

```
User Thought:
  "The current codebase is too large for an LLM to load at once. I want
  to migrate toward microservices so a future LLM loads only the one
  service it needs. This is an evolution, not a rewrite."
  Evidence: assistant_project.md:45–49 ("North star — LLM context economy.")    — Confidence: Certain

  ↓

Goal:
  Event-driven LLM-event-microservices. Each service has documented
  ins → internal flow → outs, loadable as a unit. Telemetry curated
  into per-episode "LLM logs" for compact history.
  Evidence: goal.md:129–136 ("event-driven LLM-event-microservices")    — Confidence: Certain

  ↓

Belief:
  (a) The five decision-spine modules are already microservice-shaped
      (inject-config, dict-returns, no shared mutable state).
  (b) The migration happens in sequenced milestones (M0→M5), not one
      big refactor.
  (c) Microservice boundaries = context separation for LLM loading.
  Evidence: codebase-state-map.md:84–93 (decision spine: all 5 stages inject-config + dict-returns)    — Confidence: Certain
  Evidence: goal.md:135–136 (M0–M5 sequencing)    — Confidence: Certain

  ↓

Economic Meaning:
  Context economy directly reduces LLM token costs and improves reasoning
  quality. Loading 200 lines of one service is cheaper AND more accurate
  than loading 2000 lines of the full codebase. The microservice migration
  is a direct investment in LLM-as-developer efficiency.
  Evidence: assistant_project.md:45–49 (LLM context economy)    — Confidence: Likely

  ↓

Architecture Decision:
  (1) M0: Map & doctrine (done: CODEBASE_STATE_MAP, EVENT_TAXONOMY,
      SERVICE_BOUNDARY_MAP, REPLAY_GOVERNANCE, LLM_GOVERNANCE_LAYER).
  (2) M1: Telemetry normalization (envelope trade writers).
  (3) M2: Event extraction (CRTState transitions).
  (4) M3: Orchestration de-coupling (kill live_engine_hook singletons).
  (5) M4: Dependency inversion (governance stops importing backtest_v2).
  (6) M5: LLM-layer hardening.
  Evidence: assistant_project.md:69–77 (M0–M5 sequencing)    — Confidence: Certain

  ↓

Modules:
  docs/architecture/event-taxonomy.md      — authoritative event catalogue
  docs/architecture/service-boundary-map.md — candidate microservices
  docs/architecture/replay-governance.md    — determinism/replay contract
  src/events/event_fabric.py               — canonical event envelope
  — Confidence: Certain

  ↓

Runtime Effect:
  (Still in M0/M1 phase — the codebase remains a monolith.) The event
  fabric exists. Trade writers are not yet enveloped (M1 pending).
  Service boundaries are documented but not enforced at the import level.
  Evidence: assistant_project.md:119 (event fabric exists — consolidate, don't fork)    — Confidence: Certain

ALIGNMENT STATUS: LARGELY ALIGNED, PARTIALLY EXECUTED
  - The doctrine is codified and the M0 deliverables are complete.
  - M1–M5 are still in-progress — the monolith is documented but not
    yet decomposed. The hidden-coupling inventory (codebase-state-map.md §3)
    identifies the hard blockers.
  - The migration has NOT yet yielded a tangible reduction in loadable
    context size.
```

---

## Summary of Alignment Status

| Chain | Domain | Alignment | Key Gap |
|-------|--------|-----------|---------|
| 1 | Capital Preservation | LIKELY ALIGNED | Orphan UltronRiskGateWrapper; gate not exercised in backtest |
| 2 | Config Governance | PARTIALLY BROKEN | ACTIVE_VERSION suffix evades promotion_log check |
| 3 | Deterministic Replay | ALIGNED | Strongest chain — proven byte-identical |
| 4 | Advisory-Only LLM | ALIGNED | Multi-layer isolation; 70B-vs-3B gap unresolved |
| 5 | Intelligence Compounding | ALIGNED | CLAUDE-specific; doesn't enforce for other readers |
| 6 | Four-Engine Scoring | TECHNICALLY ALIGNED, ECONOMICALLY FALSIFIED | Architecture correct, belief wrong |
| 7 | No Database / File-Backed | LARGELY ALIGNED | INOUT had psycopg2 (since archived) |
| 8 | Research Isolation | ALIGNED | Test-level lint, separate config, one-way adapter |
| 9 | CRT State Machine Spine | TECHNICALLY ALIGNED, ECONOMICALLY FALSIFIED | Correct code, disproven belief |
| 10 | Truth Maintenance | ALIGNED | Self-reinforcing, test-enforced |
| 11 | Advisory AI Agent | ALIGNED | Deterministic, confirm-gated, auditable |
| 12 | Event-Driven Migration | LARGELY ALIGNED | M1–M5 not yet executed |

Confidence in this summary: Likely (based on extensive document evidence but
without reading every line of every source module).