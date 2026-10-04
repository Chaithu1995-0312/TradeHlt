# Intent Alignment Audit

> **Purpose:** Compare reality (code, tests, runtime, dependency graph) against the intent graph,
> behavior contracts, and authority model. Find hidden bypasses, split-brains, orphans,
> contradictory doctrines, and economically misaligned code.
>
> **Method:** For each domain, compare the behavior contract (from Phase 4) against actual code
> behavior (from document evidence, current-findings, and session logs). Evidence is cited;
> confidence is stated. Do NOT optimize for green scores — optimize for truth.

---

## Audit Finding Inventory

### A-1: ACTIVE_VERSION Suffix Drift (Governance)

**Status:** CONFIRMED (F-016, F-018)

The runtime ACTIVE_VERSION is "v2_multi_2026_04 - deepdeektry" but the promotion_log has
"v2_multi_2026_04" (no suffix). The config_integrity gate that should detect this mismatch
is ORPHANED (F-006).

**Contract violated:** Governance §1 Expected #5: "ACTIVE_VERSION must be a version that exists
in promotion_log.jsonl with a PROMOTED event."

**Severity:** HIGH — the active config has an undocumented experimental suffix that evaded
the governance path.

**Root cause:** config_integrity.active_version_is_governed() exists but is never called
on any runtime path.

---

### A-2: Config-In-Code Split-Brain (Governance)

**Status:** RESOLVED (R1/R2 fixes per 2026-06-12)

On `patch`, the active config lacked sections (dataset_integrity, uat, live_integration) that
HEAD code expected, causing 28 test failures. Three config knobs were hardcoded overrides
(bitnet_main_threshold, feature_monitor drift thresholds). R1 added the missing sections;
R2 wired the hardcoded knobs to config. Both were proven behavior-neutral via ledger SHA.

**Contract violated:** Governance §1 Forbidden #3 (other code paths existing — the active
config silently ran on code defaults for those sections/knobs).

**Severity:** HIGH (pre-fix) → RESOLVED.

**Root cause:** F-016 branch split-brain — v2 config predates sections added to HEAD code.

---

### A-3: Backtest-vs-Live Risk Gate Divergence (Execution)

**Status:** CONFIRMED (F-010)

UltronRiskGate is exercised in the live path but NOT in the backtest spine. If the gate's
config values differ between backtest and live (ultron_gate_enabled=false in one but true
in the other), the backtest and live PnL will diverge structurally.

**Contract violated:** Execution §1 Expected #5 plus Risk §1 Expected #1 (UltronRiskGate must
evaluate every planned trade).

**Severity:** HIGH — live PnL is structurally UNVERIFIED against backtest projections.

**Root cause:** The decision spine in backtest mode does not wire through UltronRiskGate
in the same way as the live path.

---

### A-4: LLM-Is-Isolated Violation Never Found, But Design-Intended Chain Exceeded (Advisory-Only LLM)

**Status:** NOT A VIOLATION — design exceeds available model

The multi-layer LLM isolation (circuit breaker, PLAN_REGISTRY, confirm-gate, path-guard) is
faithfully implemented. However, the GovernanceOrchestrator references a 70B model while the
actual available model is BitNet 3B. The *layer* design may exceed what the model can deliver.

**Contract violated:** None — the isolation contract is met. This is a capability gap, not an
authority violation.

**Severity:** LOW — the isolation works; the LLM just can't deliver the insight the layer
was designed for.

---

### A-5: Orphan Modules With No Economic Purpose (Multiple Domains)

**Status:** CONFIRMED (F-005, F-006, F-012, F-013)

Five orphan clusters identified:

| Orphan | Domain | Evidence | Economic Cost |
|--------|--------|----------|---------------|
| ultron_risk_gate_wrapper.py | Risk | Designed as regime pre-scaler, never imported | Cognitive load + future confusion |
| config_integrity.py | Governance | Has full check logic, zero callers | HIGH — allowed deepdeektry drift |
| scanner/ + execution/loop.py + portfolio/ | Execution | Multi-signal path built but never called | Development time + complexity |
| replay_memory/ + cognitive/ + cluster/ + hmf/ | Memory | Sidecar-only, zero spine consumption | Development time + complexity |
| trade_net_v2.py | Execution | Complete 3-head model, fusion socket is stub | Development time |

**Contract violated:** No explicit "no orphans" contract exists, but the implicit contract is
that code serves a known economic purpose (intelligence-compounding.md:104–133: "Modules are
frozen thoughts"). Orphan modules are frozen thoughts with no consumer.

**Severity:** MEDIUM — the orphans extract a recurring cognitive load tax on every reader.

---

### A-6: Economic Falsification of Core Design Belief (Architecture)

**Status:** CONFIRMED (F-019, F-020, F-021, F-025)

The four-engine scoring spine + CRT state machine — the system's core architectural belief —
has been empirically falsified for its target universe (crypto majors, M15, intrabar+12bps).
The research program cleanly falsified entry direction (F-019), conditional direction (F-020),
selection beyond session (F-021), and exit geometry (F-025).

**Contract violated:** No explicit contract says "the spine must produce edge." The implicit
economic contract (the system exists to produce profitable trades) is what is violated.

**Severity:** PARADIGMATIC — this is not a code bug. The code is correct. The *design belief*
was wrong. This is the most important finding in the audit.

**Root cause:** The CRT market ontology and four-engine scoring architecture were designed
under assumptions that do not hold for crypto-major M15 under realistic exits and costs.

---

### A-7: INOUT Database Contradiction (File-Backed Infrastructure)

**Status:** CONFIRMED — HISTORICAL

The file-backed invariant ("no database") was violated by INOUT's TimescaleDB integration.
This was since rectified by archiving INOUT (2026-05-02).

**Contract violated:** File-Backed §1: "Zero external infrastructure dependencies."

**Severity:** MEDIUM (historical) — the violation was detected and corrected.

---

### A-8: LLM-Agent Plan Not Fully Deterministic for All Intents (Agent)

**Status:** NOT CONFIRMED — but a potential gap

The PlanCompiler uses a deterministic PLAN_REGISTRY, but the IntentRouter can fall back to
LLM classification if regex fails (0.85 confidence threshold). If the LLM misclassifies the
intent, the deterministic plan becomes wrong.

**Contract violated:** Agent §1 Forbidden #1: "LLM planning tool sequences" — the LLM does not
*generate* the plan but can *select* the wrong plan via misclassification.

**Severity:** LOW — bounded by the LLM fallback being a last resort after regex failure.
The wrong plan would still be deterministic.

---

### A-9: Truth Maintenance Doctrine Is CLAUDE-Only (Preservation)

**Status:** CONFIRMED — LIMITATION

The Truth Maintenance Doctrine (§6.2), Findings Mandate, SESSION LOG requirement, and
Revalidate-by deadlines are all enforced through CLAUDE.md + test_current_findings.py.
A human reader or different LLM agent would not have CLAUDE.md's procedural mandates
enforced the same way.

**Contract violated:** Preservation §1 Expected #2: "Every code change must check docs, tests,
findings, topics." — this is only enforced when the agent follows CLAUDE.md.

**Severity:** MEDIUM — the system works for the intended CLAUDE agent but does not generalize.

---

## Hidden Bypasses

| Bypass | Path | Detection | Impact |
|--------|------|-----------|--------|
| promote_direct() | PromotionManager.promote_direct() | Only visible in promotion_log notes field | Can bypass ConfigValidator entirely |
| .gitignore ignores docs/ | docs/ is untracked | Git status | Doc changes invisible in git history on `patch` |
| Hardcoded KillSwitch path | ultron_risk_gate.py:44 logs/kill_switch_state.json | Code review | Blocks multi-instance deployment |

---

## Split-Brains

| Concept | Authority A | Authority B | Divergence |
|---------|-----------|-----------|------------|
| Active version | F-007 said v4_active (TP3 line) | F-016 says v2_active (patch) | Branch-scoped — resolved per-branch |
| Config sections | Code expects dataset_integrity/uat/live_integration | v2 config lacks them | RESOLVED (R1) |
| opportunities.jsonl outcome | Artifact says SL_HIT (36.8% self-consistent) | Governing exit says TP | F-022: detection stream ≠ trade ledger |

---

## Contradictory Doctrines

| Doctrine A | Doctrine B | Contradiction |
|-----------|-----------|---------------|
| "No database" (goal.md §3 #7) | INOUT used TimescaleDB (historical) | Resolved by archival |
| "File-backed state" | psycopg2-binary in installed packages | Resolved by INOUT archival |

---

## Alignment Score Matrix

| Domain | Intent Confidence | Architecture Alignment | Behavior Alignment | Authority Alignment | Economic Alignment | Unknowns | Risk | Drift | Overall |
|--------|-----------------|----------------------|-------------------|-------------------|-------------------|----------|------|-------|---------|
| Governance | Certain | LIKELY (80%) | PARTIAL (60%) — deepdeektry suffix evaded | PARTIAL (60%) — config_integrity orphaned | HIGH — governance is the #1 constraint | How the suffix got added | HIGH — A-1, A-2 | DRIFT (F-016, F-018) | ⚠️ ATTENTION NEEDED |
| Execution | Certain | ALIGNED (100%) — spine faithfully implemented | ALIGNED (100%) — every invariant enforced | ALIGNED (100%) — no authority violations | FALSIFIED — spine produces no edge on target universe | Whether FX/H1 would differ | PARADIGMATIC (A-6) | BELIEF DRIFT (user thought vs reality) | ⚠️ PARADIGM GAP |
| Risk | Certain | ALIGNED (90%) — UltraGate + KillSwitch + Monitor exist | PARTIAL (70%) — F-010 live unverified, F-008 drift unacted | ALIGNED — gates enforce their domains | MEDIUM — risk is hygiene, not alpha | Whether drift→size-down would help | MEDIUM — A-3 | NO DRIFT observed | ✅ FUNCTIONAL |
| Memory | Certain | ALIGNED — multi-layer (log → findings → tests) | ALIGNED — SESSION LOG + findings + enforcement | ALIGNED — authority is in §6.2 | HIGH — knowledge preservation is repo's top asset | Readability for non-CLAUDE agents | LOW — A-9 | NO DRIFT | ✅ ALIGNED |
| Research | Certain | ALIGNED — isolated, separate config, one-way adapter | ALIGNED — byte-identical, qualification gate, truth standards | ALIGNED — never imports forbidden modules | VERY HIGH — null findings are high ROIs | Whether results generalize beyond crypto M15 | LOW — well-guarded | NO DRIFT | ✅ ALIGNED |
| Agent | Certain | ALIGNED — deterministic plan, confirm-gate, path-guard | ALIGNED — PLAN_REGISTRY lookup, write_tools_enabled empty | ALIGNED — multi-layer isolation | HIGH — reduces cognitive load at zero autonomy risk | LLM misclassification via fallback path | LOW — A-8 | NO DRIFT | ✅ ALIGNED |
| Preservation | Certain | ALIGNED — tiers, rules, enforcement tests | ALIGNED — test_current_findings green | ALIGNED — precedence-based authority | HIGH — prevents compound drift costs | Human non-compliance risk | MEDIUM — A-9 | NO DRIFT | ✅ ALIGNED |

---

## Key Findings (Non-Obvious)

### 1. The system's code is MORE aligned with its design intent than the design intent is aligned with economic reality.

The code faithfully implements the user's requested architecture: 4-engine scoring, CRT state
machine, config governance, deterministic replay, LLM isolation, research independence. The
gap is NOT between code and intent — it is between *intent and reality*: the market ontology
the user chose does not produce edge on the target universe.

### 2. The orphan modules are the second-highest priority finding.

Five orphan clusters (ultron_risk_gate_wrapper, config_integrity, scanner/loop/portfolio,
replay_memory+cognitive+cluster+hmf, trade_net_v2) represent significant development effort
that never integrated into the primary decision loop. Of these, config_integrity.py is the
most consequential — its non-wiring directly enabled the deepdeektry suffix drift.

### 3. The most aligned domain (Deterministic Replay) is also the least leveraged.

The replay trust layer is the strongest asset in the repository — proven byte-identical,
audited independently, golden-ledger-verified. But it only measures. It does not create alpha.
The system can perfectly measure its own lack of edge.

### 4. The Truth Maintenance system works — F-007→F-016 proves it.

The branch-scoped v4→v2 correction is a textbook example of the doctrine operating correctly:
evidence was gathered, contradiction surfaced, finding superseded, history preserved, and the
enforcement tests remained green throughout.

---

## Truth Table: Every Module Assessed Against Its Purpose

| Module | Stated Purpose | Actual Role | Aligned? | Notes |
|--------|---------------|-------------|----------|-------|
| ultron_risk_gate.py | Last capital defense | Last capital defense | ✅ | Live path only; not in backtest |
| ultron_risk_gate_wrapper.py | Regime pre-scaler | Orphan | ❌ | Never called |
| config_integrity.py | Runtime integrity guard | Orphan | ❌ | Has logic, zero callers |
| promotion_manager.py | Only path to prod | Only path to prod | ✅ | Suffix gap detected too late |
| config_validator.py | Validate before promote | Validate before promote | ✅ | Hard + soft gates enforced |
| backtest_v2.py | Deterministic replay | Deterministic replay | ✅ | Proven byte-identical |
| metrics_oracle.py | Independent metric recompute | Independent metric recompute | ✅ | 10/10 parity gate |
| dataset_integrity.py | Preflight data gate | Preflight data gate | ✅ | Crypto approvals, FX warnings |
| crt_engine_v2.py | CRT state machine spine | CRT state machine spine | ⚠️ | Correct code, disproven belief |
| engine_runner.py | 4-engine orchestrator | 4-engine orchestrator | ✅ | Completeness enforced |
| fusion_engine.py | Weighted score fusion | Weighted score fusion | ✅ | Correctly implemented |
| decision_engine.py | Threshold-based accept/reject | Threshold-based accept/reject | ✅ | Config-driven |
| execution_planner.py | Entry/SL/TP/TTL plan | Entry/SL/TP/TTL plan | ✅ | Intent-specific multipliers |
| llama_gate.py | LLM client + circuit breaker | LLM client + circuit breaker | ✅ | Fail-open, neutral fallback |
| plan_compiler.py | Deterministic plan lookup | Deterministic plan lookup | ✅ | PLAN_REGISTRY enforced |
| executor.py | Confirm-gate + path-guard | Confirm-gate + path-guard | ✅ | Write_tools_enabled empty by default |
| research/runner.py | Deterministic experiment runner | Deterministic experiment runner | ✅ | Byte-identical edge reports |
| research/qualification.py | 7-gate qualification | 7-gate qualification | ✅ | Correctly rejects all candidates |
| scanner/* + execution/loop.py + portfolio/* | Multi-signal scan→allocate→execute | Orphan | ❌ | Built, never wired |
| trade_net_v2.py | Neural fusion model | Orphan | ❌ | Fusion socket is permanently stub |

---

## Conclusion

The repository faces a fundamental and non-obvious challenge: **the code is correct; the design belief is wrong.**

The user asked for a 4-engine, CRT-state-machine-governed trading system with config governance,
deterministic replay, LLM isolation, and research independence. Every one of those requirements
was faithfully implemented. The codebase is internally consistent — the architecture matches the
specification, the invariants are enforced, the tests pass.

But the research program (F-019/020/021/025) showed that under realistic exits and costs, the
entire paradigm produces no positive-expectancy edge on its target universe (crypto majors, M15).
This is NOT a code bug. It is a belief-intent gap: the user's design beliefs (four-engine fusion
creates edge, CRT state machine captures structure, session filter selects winners) were falsified
by measurement.

The governance gap (A-1: deepdeektry suffix, A-2: missing config sections) is a more tractable
but still important secondary finding — it shows that the config governance infrastructure,
while well-designed, has an orphan gap that allowed an undocumented suffix to enter the runtime.

The orphan modules (5 clusters) represent development effort without economic return. Their
cognitive load cost is ongoing.

**The honest answer to "does the code faithfully implement the user's intended ideology?":**
- For code behavior: YES — the architecture matches the specification.
- For economic outcomes: NO — the specification was falsified by measurement.
- This is NOT a contradiction. It is the repository's most important truth.