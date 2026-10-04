# Behavior Contracts — Expected vs Forbidden

> **Purpose:** From intent (not from tests), define what each domain MUST do, MUST NEVER do,
> and who owns each decision. These contracts are the baseline for the alignment audit (Phase 5).
>
> Derived from: intent_graph.md (12 chains) + intent/ domain contracts + CLAUDE.md invariants.

---

## 1. Governance

### Expected Behaviors (What MUST happen)
1. ConfigValidator.validate() must return APPROVE before any promotion.
2. PromotionManager must SHA-256 hash the params and record the hash.
3. PromotionManager must archive the existing active config before writing a new one.
4. promotion_log.jsonl must receive a PROMOTED or PROMOTION_FAILED event on every promotion attempt.
5. ACTIVE_VERSION must be a version that exists in promotion_log.jsonl with a PROMOTED event.
6. Rollback must copy (not move) the archived config, update ACTIVE_VERSION, and append ROLLBACK entry.

### Forbidden Behaviors (What MUST NEVER happen)
1. ❌ A config change reaching production without an APPROVED ValidationReport.
2. ❌ A config version that does not exist in promotion_log.jsonl being set as ACTIVE_VERSION.
3. ❌ Any code path outside PromotionManager writing to configs/production/.
4. ❌ Editing or truncating promotion_log.jsonl.
5. ❌ Hot-swapping a config without restart.

### Authority Invariants
- **Owner:** PromotionManager (the only path to production).
- **Non-owner:** Any module in src/ that is not src/governance/promotion_manager.py.
- **LLM:** Never promotes — MetaGovernorExecutor proposes candidates but never writes to registry.

### Safety Invariants
- The config hash is load-bearing: any change to params changes the hash, which must be recomputed.
- The archive preserves the previous version byte-for-byte.

### Ordering Invariants
- Validate BEFORE promote. Archive BEFORE write. Hash BEFORE log. Log is last.

---

## 2. Execution (Decision Spine)

### Expected Behaviors (What MUST happen)
1. Every candle must be scored by all 4 engines (EXPECTED_ENGINES completeness check).
2. Fusion must combine all 4 scores or reject the candle (no partial fusion).
3. DecisionEngine must apply score_threshold from config.
4. ExecutionPlannerV1_2 must produce entry/SL/TP/RR/TTL for every ACCEPTED decision.
5. UltronRiskGate.evaluate() must evaluate every planned trade before dispatch.
6. CRT state machine must enforce VALID_TRANSITIONS — reject illegal jumps.

### Forbidden Behaviors (What MUST NEVER happen)
1. ❌ Fewer than 4 engine scores being fused.
2. ❌ LLM approving or rejecting a trade.
3. ❌ Any trade plan bypassing UltronRiskGate.
4. ❌ Lookahead in backtest replay (candle-by-candle only).
5. ❌ An ExecutionPlan with invalid geometry (TP below entry on long, etc.).

### Authority Invariants
- **Owner:** EngineRunner → FusionEngine → DecisionEngine → ExecutionPlanner → UltronRiskGate (in order).
- **Non-owner:** LLM agents (read-only tap at Step 4). INOUT (joins only at Step 6).
- **Decision contract:** Every step's output is a structured dict — no side effects.

### Ordering Invariants
1. Data Ingest → Feature Pipeline → Scoring → Fusion → Decision → Plan → Risk Gate → Execute.
2. No step may be skipped. No step may produce an output that the next step ignores.

---

## 3. Risk

### Expected Behaviors (What MUST happen)
1. UltronRiskGate.evaluate() must be called for every ExecutionPlan before dispatch.
2. KillSwitch must track daily and weekly realized PnL with date rollover.
3. KillSwitch must block new trades when limit exceeded (TRIPPED state prevents dispatch).
4. FeatureMonitor must detect HARD drift (Z > 3.0) and log WARNING.
5. All risk parameters must be read from the active governed config (no magic numbers).

### Forbidden Behaviors (What MUST NEVER happen)
1. ❌ A trade executing without UltronRiskGate evaluation.
2. ❌ LLM overriding a risk gate decision.
3. ❌ KillSwitch resetting silently (must be explicit reset()).
4. ❌ HARD drift event passing without at least a WARNING log.
5. ❌ Hot-swapping risk parameters mid-session.

### Authority Invariants
- **Owner:** UltronRiskGate (trade-level), KillSwitch (account-level), FeatureMonitor (drift-level).
- **Non-owner:** LLM (never overrides), ExecutionPlanner (plans but does not approve).

### Safety Invariants
- The risk path is fail-fast — no fallback for capital check.
- KillSwitch must survive process restart (JSON-persisted state).

---

## 4. Memory (Intelligence Compounding)

### Expected Behaviors (What MUST happen)
1. Every response must append a SESSION LOG entry to assistant_project.md.
2. Every validated or overturned conclusion must be added/flipped in current-findings.md in the same turn.
3. Superseded findings must remain as rows (never deleted).
4. test_current_findings must enforce synchronisation between Index and findings.

### Forbidden Behaviors (What MUST NEVER happen)
1. ❌ A finding existing only in a session log without being formalized in current-findings.md.
2. ❌ Deleting a finding (must mark SUPERSEDED or RETIRED).
3. ❌ CLAUDE.md Truths Index diverging from current-findings.md.
4. ❌ Silently reviving a KILLED/FROZEN initiative without meeting its Reopen Conditions.

### Authority Invariants
- **Owner:** CLAUDE.md §6/§6.1/§6.2 (for LLM), current-findings.md (for readers).
- **Non-owner:** Any module in src/ (findings are documentation, not code).

### Ordering Invariants
- Findings are added/flipped in the SAME turn they are validated or overturned — never deferred.

---

## 5. Research

### Expected Behaviors (What MUST happen)
1. Every experiment must use a consistent truth standard (intrabar_fixed exits, flat 12bps cost).
2. Every experiment must be deterministic (byte-identical edge report ×2).
3. M4 QualificationGate must be applied before any behavior is deemed qualified.
4. Findings must be filed in current-findings.md.

### Forbidden Behaviors (What MUST NEVER happen)
1. ❌ Importing from engine_runner, promotion_manager, or config_validator.
2. ❌ Writing to configs/production/ or modifying ACTIVE_VERSION.
3. ❌ Modifying the production spine.
4. ❌ Overriding the qualification gate's verdict.
5. ❌ Claiming edge without M4 qualification.

### Authority Invariants
- **Owner:** HypothesisRunner → EdgeAggregator → M4 QualificationGate.
- **Non-owner:** Production spine (one-way adapter only). Promotion path.

### Ordering Invariants
- Measure before qualify. Qualify before file finding. Never skip qualification.

---

## 6. Agent

### Expected Behaviors (What MUST happen)
1. IntentRouter: regex first (0.85 threshold) → LLM fallback → ask_user.
2. PlanCompiler: PLAN_REGISTRY lookup (never LLM generation).
3. Executor: confirm-gate for write tools. Path-guard enforced.
4. Every action logged (per-step + per-session).

### Forbidden Behaviors (What MUST NEVER happen)
1. ❌ LLM planning tool sequences (PLAN_REGISTRY is authoritative).
2. ❌ Write operations bypassing confirm-gate.
3. ❌ Writes outside configs/production/|logs/|results/.
4. ❌ LLM routing a governance approve/reject decision.

### Authority Invariants
- **Owner:** PlanCompiler (planning), Executor (execution), IntentRouter (classification).
- **Non-owner:** LLM (only fills arguments, never decides what to do).

---

## 7. Preservation (Truth Maintenance)

### Expected Behaviors (What MUST happen)
1. Authority tiers: runtime(0) > code schema(1) > promotion_log(2) > memory(3) > LLM(4).
2. Every code change must check docs, tests, findings, topics in the same turn.
3. Every conflict detected must be surfaced (TruthConflict), never silently resolved.

### Forbidden Behaviors (What MUST NEVER happen)
1. ❌ Silently resolving a conflict between authorities.
2. ❌ Deleting a finding (must mark SUPERSEDED).
3. ❌ Citing a stale finding as active.
4. ❌ Assuming branch-global truth without stating the branch.

### Authority Invariants
- **Owner:** The 4-tier priority system (no single owner — authority is precedence-based).
- **Non-owner:** Session memory (Tier 4 — weakest; advisory only).