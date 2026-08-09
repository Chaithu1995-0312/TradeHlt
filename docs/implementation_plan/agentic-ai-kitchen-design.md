# Agentic AI Kitchen Design — Tradelatest

> **Status:** DESIGN + **P0 PARTIAL IMPLEMENTATION** (2026-08-07)  
> **Product name:** **GrokAgenticAI** (multi-specialist: OpsDoctor, CampaignRunner, …)  
> **Created:** 2026-08-07  
> **Scope:** Async “kitchen” agents around the CRT spine — **not** per-candle execution authority  
> **Authority:** Extends CLAUDE.md §6.5 Authority Ladder + `docs/architecture/llm-governance-layer.md`  
> **Grants no new authority:** path-guard, y/N, `ValidationReport.APPROVE`, UltronRiskGate unchanged  
>  
> **Shipped P0 code:** `src/agent/grok_agentic.py`, `goal.py`, `goal_loop.py`, `recipes/`,  
> `modes/ops_mode.py`, CLI brand + intents `ops_diagnose` / `campaign_run`.  
> **Shipped P1 TruthJanitor:** `modes/truth_mode.py`, recipe `truth_janitor`, intent `truth_janitor`.  
> Say: `Ask GrokAgenticAI …` · `python -m src.agent.cli --agent ops_doctor|campaign_runner|truth_janitor`  

---

## 0. One-sentence north star

**Upgrade the existing deterministic-plan agent into goal-oriented, tool-using kitchen agents that sense → act → replan under the same fences, while GenAI only explains — never scores candles or promotes configs.**

---

## 1. Problem statement

### 1.1 What exists today (proto-agent)

| Layer | Module | Behavior |
|-------|--------|----------|
| NL → intent | [`src/agent/intent_router.py`](../../src/agent/intent_router.py) | Regex fast-path → LLM fallback → `ask_user` |
| Intent → tools | [`src/agent/plan_compiler.py`](../../src/agent/plan_compiler.py) `PLAN_REGISTRY` | **Fixed** ordered `ToolStep` list — LLM never chooses tools |
| Arg fill | [`src/agent/tool_planner.py`](../../src/agent/tool_planner.py) `ArgFiller` | LLM extracts args only |
| Dispatch | [`src/agent/executor.py`](../../src/agent/executor.py) | Allowlist → path guard → y/N write confirm → handler |
| Loop | [`src/agent/agent_core.py`](../../src/agent/agent_core.py) `AgentCore.turn` | Linear plan execution, `max_iterations_per_turn` |
| Audit | [`src/agent/audit.py`](../../src/agent/audit.py) | `logs/agent_audit.jsonl` + `logs/agent_intent_log.jsonl` |
| CLI | [`src/agent/cli.py`](../../src/agent/cli.py) | `python -m src.agent.cli` |

This is **orchestrated automation** (prompt → fixed recipe), not full **agentic** behavior (goal → sense → choose next tool → stop on success/fail criteria).

### 1.2 Doctrine constraints (non-negotiable)

From [`docs/architecture/llm-governance-layer.md`](../architecture/llm-governance-layer.md):

1. **LLMs are advisory governance, never execution authority.**
2. No LLM on the replay/backtest candle hot path.
3. Write roots fenced: `configs/production/`, `logs/`, `results/` ([`executor.py` `_WRITE_ROOTS`](../../src/agent/executor.py)).
4. Promotion requires `ValidationReport.decision == "APPROVE"` ([`promotion_manager.py`](../../src/governance/promotion_manager.py)).
5. Copilot never places trades — Ultron remains sole risk authority ([`copilot_mode.py`](../../src/agent/modes/copilot_mode.py)).

From CLAUDE.md §6.5 Authority Ladder:

- Information ≠ economic usefulness ≠ production authority ≠ architecture justification.
- Research agents may produce drafts/artifacts; they do **not** auto-register findings as living truth without E-001 + human/findings process.

### 1.3 Gap (agentic vs current)

| Capability | Today | Target |
|------------|-------|--------|
| Goal object | Implicit in NL string | Explicit `AgentGoal` with success/fail criteria |
| Planning | Static `PLAN_REGISTRY` only | **Bounded** dynamic planner over allowlisted tools + optional recipe seeds |
| Observation | Tool result printed | Structured `Observation` → replan / stop |
| Proactivity | On-demand only | Threshold triggers (drift, stale data, failed gate) |
| GenAI role | Intent + arg fill + findings | Explicit **narrator** slot (report only) |
| Multi-step campaigns | One turn, max 6 steps | Multi-turn / multi-session campaign with checkpoint state |
| Control-plane graph | UI “recommended next” | Same graph as agent tool DAG |

---

## 2. Architecture target

### 2.1 Placement in system topology

Per [`docs/architecture/signal-flow.md`](../architecture/signal-flow.md):

```
                    ┌─────────────────────────────────────────────┐
                    │  AGENTIC KITCHEN (async feeders)            │
                    │  Ops Doctor · Campaign Runner · Truth Janitor│
                    │  Research Runner · Multi-LLM Orchestrator   │
                    └───────────────┬─────────────────────────────┘
                                    │ invokes tools / CLIs
                                    ▼
 configs / models / logs / results ◄──► control_plane CommandSpec graph
                                    │
                                    │ DOES NOT own
                                    ▼
        SPINE (sync, deterministic): Candle → Features → Engines →
        Fusion → Decision → ExecutionPlanner → UltronRiskGate → order
```

Spine modules (do **not** agentize internals):

- [`src/features/feature_pipeline.py`](../../src/features/feature_pipeline.py)
- [`src/core/engine_runner.py`](../../src/core/engine_runner.py)
- [`src/engines/*`](../../src/engines/)
- [`src/config_layer/execution_planner.py`](../../src/config_layer/) (ExecutionPlannerV1_2)
- Ultron risk path (live hook / risk gate)

### 2.2 Layered agent stack

```
┌──────────────────────────────────────────────────────────────┐
│ L5  Narrator (GenAI) — findings_synthesizer / report drafts  │
├──────────────────────────────────────────────────────────────┤
│ L4  Goal Loop — AgentGoal + success criteria + stop policy   │
├──────────────────────────────────────────────────────────────┤
│ L3  Planner — seed recipes (PLAN_REGISTRY) + bounded replan  │
├──────────────────────────────────────────────────────────────┤
│ L2  Executor fences — allowlist / path / confirm / audit     │
├──────────────────────────────────────────────────────────────┤
│ L1  Tool handlers — thin wrappers over scripts & src APIs    │
├──────────────────────────────────────────────────────────────┤
│ L0  Domain systems — BacktestRunner, ConfigValidator, …      │
└──────────────────────────────────────────────────────────────┘
```

**Invariant:** L5 never calls L0 directly; L3 may only emit tool names present in REGISTRY; L2 never bypassed.

### 2.3 Relationship to multi-LLM protocol

[`multi_llm/MULTI_LLM_PROTOCOL.md`](../../multi_llm/MULTI_LLM_PROTOCOL.md) remains the **human-bridged** six-model assembly line. The kitchen agent **may**:

- pack story context (`scripts/context/pack_story.py`)
- update `multi_llm/build_queue.jsonl` / validate `HANDOFF.md`
- emit `PROMPT_FOR_NEXT_MODEL` blocks

It **may not** auto-apply another model’s code to `src/` without the Claude-executor + User approval rules (CLAUDE.md §13.8).

---

## 3. Core data contracts

### 3.1 `AgentGoal` (new)

```python
# Proposed: src/agent/goal.py
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

GoalKind = Literal[
    "ops_diagnose",
    "campaign_pipeline",
    "campaign_research",
    "training_refresh",
    "data_hygiene",
    "truth_janitor",
    "multi_llm_handoff",
]

Autonomy = Literal[
    "read_only",           # no write tools
    "confirm_writes",      # existing y/N
    "preapproved_writes",  # only tools in goal.preapproved_tools + path guard
]

@dataclass
class SuccessCriterion:
    metric: str                 # e.g. "validation.decision", "trades", "data.l3_status"
    op: Literal["eq", "ne", "gte", "lte", "contains"]
    value: Any

@dataclass
class AgentGoal:
    goal_id: str
    kind: GoalKind
    objective: str              # human-readable
    instruments: list[str] = field(default_factory=list)
    success: list[SuccessCriterion] = field(default_factory=list)
    fail_fast: list[SuccessCriterion] = field(default_factory=list)
    autonomy: Autonomy = "confirm_writes"
    preapproved_tools: list[str] = field(default_factory=list)
    max_steps: int = 12
    max_wall_s: int = 3600
    seed_intent: Optional[str] = None   # maps to PLAN_REGISTRY key if any
    measurement_contract_id: Optional[str] = None  # MC-* when research
    context: dict = field(default_factory=dict)
```

**Authority note:** A satisfied success criterion grants **campaign completion**, never §6.5 production authority.

### 3.2 `Observation` / `PlanRevision` (new)

```python
@dataclass
class Observation:
    step_index: int
    tool: str
    outcome: Literal["success", "fail", "denied", "refused"]
    metrics: dict               # extracted subset
    raw_ref: Optional[str]      # path or hash to full result
    error: Optional[str] = None

@dataclass
class PlanRevision:
    reason: str
    next_tools: list[str]       # must ⊆ REGISTRY and ⊆ allowed set for goal.kind
    args_hints: dict
    stop: bool = False
    stop_reason: Optional[str] = None
```

### 3.3 Extend existing audit (additive)

Today ([`audit.py`](../../src/agent/audit.py), schemas [`docs/reference/schemas.md` §9.2](../reference/schemas.md)):

```
logs/agent_audit.jsonl      # per-step + session summary
logs/agent_intent_log.jsonl # session summaries
logs/agent_findings.jsonl   # findings synthesizer
logs/agent_sessions/*.json  # AgentState
```

**Additive fields** (backward-compatible):

```python
# on step records
"goal_id": str | None
"goal_kind": str | None
"replan": bool
"observation_metrics": dict | None

# on session / campaign summary
"goal": AgentGoal-as-dict
"success_met": bool
"criteria_eval": list[dict]
```

Optional future: emit `LLM_ADVISORY` envelopes per [`llm-governance-layer.md` §5](../architecture/llm-governance-layer.md) via `src/events/event_fabric.py`.

### 3.4 Config section (extend `agent`)

Present on v1 ([`configs/production/v1_multi_2026_03.json`](../../configs/production/v1_multi_2026_03.json) ~683+):

```json
"agent": {
  "enabled": true,
  "max_iterations_per_turn": 6,
  "intent_router": { "use_llm": true, "llm_confidence_floor": 0.6,
                     "regex_fallback_table": "src/agent/prompts/intent_patterns.json" },
  "write_tools_enabled": [],
  "audit_log_path": "logs/agent_audit.jsonl",
  "session_dir": "logs/agent_sessions",
  "groq": { "...": "..." },
  "findings": { "auto_synthesize_on_run": false, "redact_patterns": [...] }
}
```

**Proposed additive keys** (hash-neutral if top-level section already non-params; still config-first):

```json
"agent": {
  "goal_loop": {
    "enabled": false,
    "max_steps_default": 12,
    "max_wall_s_default": 3600,
    "replan_mode": "bounded_recipe",
    "allowed_goal_kinds": ["ops_diagnose", "campaign_pipeline", "truth_janitor"],
    "dynamic_tool_choice": false
  },
  "triggers": {
    "feature_drift_z": 3.0,
    "stale_data_hours": 48,
    "auto_ops_on_threshold": false
  },
  "tool_allowlists_by_kind": {
    "ops_diagnose": ["log.*", "collector.tail", "audit.*", "findings.*", "funnel.*"],
    "campaign_pipeline": ["tuner.*", "validator.*", "backtest.*", "promotion.*", "live_hook.dry_run"]
  }
}
```

Default `goal_loop.enabled: false` → byte-identical current CLI behavior.

---

## 4. Planner design (critical safety surface)

### 4.1 Modes of planning

| Mode | Description | When |
|------|-------------|------|
| **A. Recipe-only (current)** | `PLAN_REGISTRY[intent]` linear | Default; production-safe baseline |
| **B. Bounded recipe + branch** | Seed recipe; on observation, choose next step from a **declared branch table** | Campaign Runner v1 |
| **C. Allowlist free replan** | LLM/heuristics pick next tool ∈ `tool_allowlists_by_kind[kind]` only | Ops Doctor v1 (read-only tools) |
| **D. Open tool choice** | LLM any REGISTRY tool | **Forbidden** by design |

**Hard rule:** Mode D is never implemented. Mode C only for `write=False` tools unless `autonomy=preapproved_writes` with explicit list.

### 4.2 Branch table example (Campaign Runner)

```python
# Proposed: src/agent/recipes/campaign_pipeline.py
BRANCHES = {
    ("validator.validate", "decision=REJECT"): [
        "tuner.run_multi",           # re-tune
        # never auto-promote
    ],
    ("validator.validate", "decision=APPROVE"): [
        "promotion.promote_from_checkpoint",  # still confirm-gated
        "backtest.run_v2",
    ],
    ("tuner.run_multi", "fail"): [
        # stop — human
    ],
    ("promotion.promote_from_checkpoint", "error"): [
        # stop — do not retry promote blindly
    ],
}
```

Branch keys must be pure functions of structured metrics (not free-form LLM strings).

### 4.3 Intent router extension

[`intent_patterns.json`](../../src/agent/prompts/intent_patterns.json) gains:

```json
"ops_diagnose": {
  "mode": "ops",
  "patterns": ["diagnos", "why.*(no|zero).*trade", "throughput.*drop", "incident", "funnel.*fail"]
},
"campaign_run": {
  "mode": "pipeline",
  "patterns": ["campaign", "goal:.*", "until.*approv", "run until"]
},
"truth_janitor": {
  "mode": "governance",
  "patterns": ["doc drift", "census", "construction protocol", "sits", "citation sync"]
}
```

Unknown → existing `ask_user` path in [`agent_core.py`](../../src/agent/agent_core.py).

---

## 5. Flagship agents (deep design)

### 5.1 Ops Doctor (P0) — observability agent

**Goal kind:** `ops_diagnose`  
**Autonomy:** `read_only`  
**Success:** structured incident pack written under `results/incidents/` (or draft only in session) + narrative via GenAI  

#### Tool inventory (reuse + add)

| Tool | Exists? | Source |
|------|---------|--------|
| `log.get_run` / `log.get_trade` / `log.query` | Yes | [`log_query_mode.py`](../../src/agent/modes/log_query_mode.py) |
| `collector.tail` | Yes | [`copilot_mode.py`](../../src/agent/modes/copilot_mode.py) |
| `audit.tail` / `audit.inspect` | Yes | cross-mode (agent-reference) |
| `findings.list_recent` / `findings.explain` | Yes | [`findings_mode.py`](../../src/agent/modes/findings_mode.py) |
| `funnel.diagnose` | **New** | wrap `scripts/analysis/crt_funnel_diagnostic.py`, `funnel_diagnosis.py` |
| `crt.fail_reasons` | **New** | wrap `scripts/analysis/crt_fail_reason_diagnostic.py` |
| `feature.drift_snapshot` | **New** | read FeatureMonitor / backtest metrics `distribution.feature_drift` |
| `gate.m_gate_summary` | **New** | wrap `scripts/research/gate_measurement_m_gate_01.py` pattern (read artifacts) |
| `narrate.incident` | **New** (write=False or write to `results/`) | GenAI over observations — same pattern as [`findings_synthesizer.py`](../../src/agent/findings_synthesizer.py) |

#### Control flow

```
Goal: "Diagnose why BNBUSDT trade count collapsed"
  1. log.query(instrument=BNBUSDT, limit=N)
  2. collector.tail
  3. funnel.diagnose
  4. crt.fail_reasons (if funnel shows drop at SWEEP/RETEST)
  5. feature.drift_snapshot
  6. narrate.incident → results/incidents/{ts}_{instrument}.md + json
STOP when: pack complete OR max_steps
```

#### Proactive triggers (optional, config-gated)

| Signal | Source | Action |
|--------|--------|--------|
| FeatureMonitor Z > 3.0 | [`backtest_v2` FeatureMonitor wire](../../src/runtime/backtest_v2.py) / live hook | enqueue `ops_diagnose` |
| Zero trades in window | trade log / metrics | enqueue |
| Stale M15 CSV | data mtime vs `triggers.stale_data_hours` | enqueue `data_hygiene` not ops |

**Never:** auto-edit production config or disable gates.

#### Links

- Agent topic: [`docs/topics/ai-automation-agent.md`](../topics/ai-automation-agent.md)
- Signal flow async kitchen: [`docs/architecture/signal-flow.md`](../architecture/signal-flow.md)
- Findings mandate: [`docs/current-findings.md`](../current-findings.md) + CLAUDE.md §6.2 (agent drafts ≠ registered findings)

---

### 5.2 Campaign Runner (P0) — pipeline goal loop

**Goal kind:** `campaign_pipeline`  
**Autonomy:** `confirm_writes` (default)  
**Seed:** `full_pipeline` / `tune_and_validate` from [`PLAN_REGISTRY`](../../src/agent/plan_compiler.py)

#### Existing tools (handlers)

| Tool | Handler | Downstream |
|------|---------|------------|
| `tuner.run_multi` | subprocess `scripts/training/auto_tuner_multi.py` | `results/tuner/checkpoint_multi.json` |
| `validator.validate` | `ConfigValidator().validate(...)` | ValidationReport |
| `promotion.promote_from_checkpoint` | `PromotionManager.promote_from_tuner_checkpoint` | production config + log |
| `backtest.run_v2` | `BacktestRunner` | metrics |
| `live_hook.dry_run` | live dry path | no order |

Code: [`pipeline_mode.py`](../../src/agent/modes/pipeline_mode.py)

#### Control-plane parity graph

[`src/control_plane/registry.py`](../../src/control_plane/registry.py) already encodes workflow stages and `_RECOMMENDED_NEXT_BY_COMMAND`:

```
Data Prep → Tuning → Model Training → Validation & Promotion → Replay & Backtest → Live Runner
```

**Implementation:** map `CommandSpec.id` → agent tool name (or introduce `cp.run_command` tool that shells the same argv templates the HTTP UI uses). Prefer **one** dispatch path:

- Option 1: agent tools remain wrappers; CP stays UI-only  
- Option 2 (**recommended**): shared `src/control_plane/runner.py` invoked by both UI and agent  

#### Success / fail criteria examples

```python
success = [
  SuccessCriterion("validation.decision", "eq", "APPROVE"),
  SuccessCriterion("backtest.trades", "gte", 10),  # align ConfigValidator hard gate
]
fail_fast = [
  SuccessCriterion("tuner.returncode", "ne", 0),
  SuccessCriterion("validation.max_drawdown_pct", "gte", 35),
]
```

Hard gates reference: ConfigValidator in [`src/config_layer/config_validator.py`](../../src/config_layer/config_validator.py) (min trades 10, max DD 35%, min fitness 0.15 — see CLAUDE.md Phase 1 summary).

#### Confirm policy

- Each `write=True` tool still returns `PendingConfirmation` unless `autonomy=preapproved_writes` **and** tool ∈ `preapproved_tools`.
- Promotion still fails closed if report not APPROVE — agent cannot override.

#### Session / resume

Reuse [`AgentState`](../../src/agent/state.py) + `--resume ses_*` ([`cli.py`](../../src/agent/cli.py)). Add `mode_context["goal"]` and `mode_context["observations"]`.

---

### 5.3 Truth Janitor (P1) — governance hygiene agent

**Goal kind:** `truth_janitor`  
**Autonomy:** `read_only` by default; optional confirm for doc patches under allowlisted paths  

#### Tools

| Tool | Wraps |
|------|--------|
| `gov.construction_check` | `python scripts/governance/construction_protocol.py check` |
| `gov.script_census` | `scripts/analysis/script_census.py` / seed SITS |
| `gov.feature_math_lint` | `scripts/analysis/feature_math_lint.py` |
| `gov.export_findings` | `scripts/governance/export_findings.py` |
| `gov.citation_audit` | pytest `tests/test_doc_citations.py` or analysis gen |
| `doc.propose_patch` | write=True only for `docs/**` under explicit allowlist + confirm |

Construction lifecycle: [`docs/governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md`](../governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md)

**Never auto-edit:** `configs/production/ACTIVE_VERSION`, living findings reverse, ontology without manifest.

---

### 5.4 Research Campaign Runner (P1)

**Goal kind:** `campaign_research`  
**Autonomy:** `confirm_writes` (artifacts under `results/`, `logs/` only)  

#### Constraints

- Bind `measurement_contract_id` when MC layer is sealed ([`docs/governance/MEASUREMENT_CONTRACT.md`](../governance/MEASUREMENT_CONTRACT.md) — currently OPEN / 0 sealed MC-*).
- Until MC sealed: agent may still run scripts but label outputs `Contract:UNKNOWN` / research-only (matches F-registry practice).
- Scripts live under `scripts/research/**` — register new tools via `@register_tool` + SITS if new scripts ([conventions §2.1](../reference/conventions.md)).

#### Example goal

```
objective: "M-GATE-01 style re-measure fusion gate ON vs OFF for BNBUSDT"
tools: research.gate_measure, backtest.run_v2 (read), narrate.report
success: artifact path exists + non-vacuity guard fields present
authority: NONE (docs/research only)
```

Related finding pattern: F-070 / F-037 in [`docs/current-findings.md`](../current-findings.md).

---

### 5.5 Training refresh chain (P1)

Maps control-plane recommended next:

```
opportunity_scanner → phase5_calibration → discover_zones
  → build_rr_dataset → train_rr_model → validate
```

Scripts (examples):

- [`scripts/research/opportunity_scanner.py`](../../scripts/research/opportunity_scanner.py)
- [`scripts/training/phase5_calibration.py`](../../scripts/training/phase5_calibration.py)
- [`scripts/research/discover_zones.py`](../../scripts/research/discover_zones.py)
- [`scripts/training/train_rr_model.py`](../../scripts/training/train_rr_model.py)

**Stop before** production promote / model registry active flip unless human goal explicitly includes promote **and** gates pass.

Contamination awareness: F-022 opportunities stream, F-041/F-045 label issues — agent narratives must cite these caveats when summarizing RR/zone training.

---

### 5.6 Multi-LLM Orchestrator (P2)

**Goal:** advance `multi_llm/build_queue.jsonl` story without inventing authority.

| Action | Tool wraps |
|--------|------------|
| Compile portable mind | `scripts/context/build_context.py` |
| Pack story | `scripts/context/pack_story.py` |
| Log turn | `scripts/context/log_turn.py` |
| Validate handoff | `tests/test_handoff_state.py` / schema check |
| Propose next prompt | GenAI over ROLE cards in `multi_llm/roles/` |

User remains Bridge/Decider ([`multi_llm/roles/ROLE_USER.md`](../../multi_llm/roles/ROLE_USER.md)).

---

## 6. Technical implementation plan

### 6.1 Package layout (proposed)

```
src/agent/
  agent_core.py          # extend: GoalLoop path when goal_loop.enabled
  goal.py                # NEW AgentGoal, criteria eval
  goal_loop.py           # NEW observe → replan → stop
  recipes/
    __init__.py
    campaign_pipeline.py # branch tables
    ops_diagnose.py
    truth_janitor.py
  modes/
    ops_mode.py          # NEW tools for Ops Doctor
    research_mode.py     # NEW (optional)
    pipeline_mode.py     # existing
    ...
  plan_compiler.py       # keep PLAN_REGISTRY; add recipe seeds
  executor.py            # optional preapproved_writes path
  audit.py               # additive goal fields
```

### 6.2 Goal loop algorithm

```python
def run_goal(goal: AgentGoal, core: AgentCore) -> GoalResult:
    assert goal.kind in allowed_kinds(cfg)
    plan = seed_plan(goal)  # PLAN_REGISTRY or recipe
    observations = []
    for step_i in range(goal.max_steps):
        if wall_clock_exceeded(goal): break
        step = plan.next()
        if step is None:
            rev = replan(goal, observations)  # Mode B/C only
            if rev.stop: break
            plan.extend(rev.next_tools, rev.args_hints)
            continue
        # fill args → executor.dispatch (fences intact)
        obs = to_observation(step, result)
        observations.append(obs)
        if eval_fail_fast(goal, obs): break
        if eval_success(goal, observations): break
        if mode_B:
            plan.apply_branch(obs)
    narrative = optional_narrate(goal, observations)  # GenAI L5
    audit.write_goal_summary(...)
    return GoalResult(...)
```

### 6.3 Integration with AgentCore.turn

Minimal invasive path:

1. If NL matches new goal intents → build `AgentGoal` → `run_goal`  
2. Else → existing linear `PlanCompiler.build` path (unchanged)  
3. Config flag `agent.goal_loop.enabled` gates (1)

### 6.4 Control-plane shared runner (recommended)

Extract from UI/server job execution into:

```
src/control_plane/command_runner.py
  run_command(command_id: str, args: dict) -> dict
```

Agent tool:

```python
@register_tool(name="cp.run", write=depends_on_command, ...)
def _cp_run(command_id: str, args_json: str = "{}") -> dict:
    return command_runner.run_command(command_id, json.loads(args_json))
```

`write` flag must be derived from a static table (not LLM). Map promotion/live commands to write=True + confirm.

Registry source: [`src/control_plane/registry.py`](../../src/control_plane/registry.py) `core_command_specs()`, CLI matrix [`docs/reference/cli-matrix.md`](../reference/cli-matrix.md).

### 6.5 GenAI narrator (findings pattern)

Reuse [`findings_synthesizer.py`](../../src/agent/findings_synthesizer.py) patterns:

- redact via `agent.findings.redact_patterns`
- Groq client [`src/agent/groq_client.py`](../../src/agent/groq_client.py)
- never raise — `status=synthesis_unavailable` on failure
- append-only JSONL under `logs/` or `results/`

Config: `agent.findings.auto_synthesize_on_run` is currently **false** — keep false until goal loop proven; optional true only for draft findings, not living doc.

### 6.6 LLM client boundary

Chat path: `config_layer.llm_inference_client.llm_chat` (used by AgentCore / IntentRouter / ArgFiller).  
Fail-open / circuit behavior documented in llm-governance-layer for scorer; agent chat should treat empty/error as `ask_user` / stop, never as silent promote.

### 6.7 Tests (extend existing floors)

| Test file | Role |
|-----------|------|
| [`tests/test_agent_plan_compiler.py`](../../tests/test_agent_plan_compiler.py) | PLAN_REGISTRY determinism |
| [`tests/test_agent_executor_confirm.py`](../../tests/test_agent_executor_confirm.py) | confirm + path guard |
| [`tests/test_agent_intent_router.py`](../../tests/test_agent_intent_router.py) | classification |
| [`tests/test_agent_tool_registry.py`](../../tests/test_agent_tool_registry.py) | registration / write flags |
| **NEW** `tests/test_agent_goal_loop.py` | success/fail criteria, max_steps, no open tool choice |
| **NEW** `tests/test_agent_recipe_branches.py` | branch table purity |
| **NEW** `tests/test_agent_ops_tools_readonly.py` | ops tools write=False |
| [`tests/test_control_plane_registry.py`](../../tests/test_control_plane_registry.py) | if cp.run added |

### 6.8 Construction protocol

Any new feature math is forbidden in agent layer. Agent changes are orchestration-class:

1. Classify vs [`docs/governance/change_contracts.json`](../governance/change_contracts.json)  
2. BUILD_IMPACT_MANIFEST  
3. Implement  
4. `python scripts/governance/construction_protocol.py validate-completion …`  
5. Session log + topic sync for [`ai-automation-agent.md`](../topics/ai-automation-agent.md)

---

## 7. Autonomy ladder (operational policy)

| Level | Name | Allowed | Confirm | Example |
|-------|------|---------|---------|---------|
| 0 | Observe | read tools | n/a | Ops Doctor v0 |
| 1 | Draft | write `logs/`, `results/` drafts | y/N or preapproved | incident packs, findings draft |
| 2 | Campaign | tuner/validator/backtest | y/N each write | Campaign Runner |
| 3 | Promote | promotion tool | y/N **and** APPROVE report | human-in-loop only |
| 4 | Live enable | `live_hook.enable` | y/N + approval_code | rare, existing tool |
| ✗ | Hot-path score | — | forbidden | never |
| ✗ | Silent config edit | — | forbidden | never |

Matches product text: *autonomous never uncontrolled* — access control (`write_tools_enabled`, allowlists), audit trails, continuous monitoring (triggers).

---

## 8. Phased delivery

### Phase 0 — Design freeze (this doc)
- No behavior change  
- Align with User which P0 ships first  

### Phase 1 — Contracts + flag off
- Add `goal.py`, criteria eval pure functions  
- Additive audit fields  
- Config keys default off  
- Tests green; CLI identical  

### Phase 2 — Ops Doctor (read-only)
- `ops_mode.py` tools wrapping analysis scripts  
- Mode C replan over read-only allowlist  
- Incident pack artifact schema  
- Intent patterns + docs topic update  

### Phase 3 — Campaign Runner (Mode B)
- Branch tables for pipeline  
- GoalLoop in AgentCore behind flag  
- Resume + multi-session campaign id  

### Phase 4 — CP shared runner
- `command_runner.py` + `cp.run` tool  
- CLI matrix sync  

### Phase 5 — Truth Janitor + Research
- Construction/census tools  
- Research recipes with measurement-contract hooks  

### Phase 6 — Proactive triggers (optional)
- Scheduler / control-plane job enqueue (stdlib only; no broker)  
- Still confirm on writes  

---

## 9. Explicit non-goals

1. Replacing `PLAN_REGISTRY` entirely with free-form LLM tool choice  
2. LLM inside `EngineRunner` / CRT / fusion hard path (beyond existing uncertainty arbiter)  
3. Auto-promotion without APPROVE  
4. Auto-editing `docs/current-findings.md` as living truth  
5. Agent reading `.env` / secrets  
6. Multi-LLM code apply without Claude+User path  
7. Weakening `_WRITE_ROOTS` or auto-confirm  

---

## 10. Link catalog (implementation map)

### Agent core
| Resource | Path |
|----------|------|
| Package init / mode load | [`src/agent/__init__.py`](../../src/agent/__init__.py) |
| Turn loop | [`src/agent/agent_core.py`](../../src/agent/agent_core.py) |
| Intent | [`src/agent/intent_router.py`](../../src/agent/intent_router.py) |
| Patterns | [`src/agent/prompts/intent_patterns.json`](../../src/agent/prompts/intent_patterns.json) |
| Plans | [`src/agent/plan_compiler.py`](../../src/agent/plan_compiler.py) |
| Arg fill | [`src/agent/tool_planner.py`](../../src/agent/tool_planner.py) |
| Executor | [`src/agent/executor.py`](../../src/agent/executor.py) |
| Registry | [`src/agent/tool_registry.py`](../../src/agent/tool_registry.py) |
| State | [`src/agent/state.py`](../../src/agent/state.py) |
| Audit | [`src/agent/audit.py`](../../src/agent/audit.py) |
| CLI | [`src/agent/cli.py`](../../src/agent/cli.py) |
| Findings GenAI | [`src/agent/findings_synthesizer.py`](../../src/agent/findings_synthesizer.py) |
| Groq | [`src/agent/groq_client.py`](../../src/agent/groq_client.py) |

### Modes
| Mode | Path |
|------|------|
| Pipeline | [`src/agent/modes/pipeline_mode.py`](../../src/agent/modes/pipeline_mode.py) |
| Copilot | [`src/agent/modes/copilot_mode.py`](../../src/agent/modes/copilot_mode.py) |
| Governance | [`src/agent/modes/governance_mode.py`](../../src/agent/modes/governance_mode.py) |
| Findings | [`src/agent/modes/findings_mode.py`](../../src/agent/modes/findings_mode.py) |
| Log query | [`src/agent/modes/log_query_mode.py`](../../src/agent/modes/log_query_mode.py) |

### Governance / promotion
| Resource | Path |
|----------|------|
| PromotionManager | [`src/governance/promotion_manager.py`](../../src/governance/promotion_manager.py) |
| ShadowPromotionGate | [`src/governance/shadow_promotion_gate.py`](../../src/governance/shadow_promotion_gate.py) |
| ConfigValidator | [`src/config_layer/config_validator.py`](../../src/config_layer/config_validator.py) |
| Construction protocol | [`scripts/governance/construction_protocol.py`](../../scripts/governance/construction_protocol.py) |
| Doc protocol | [`docs/governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md`](../governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md) |
| Measurement contract | [`docs/governance/MEASUREMENT_CONTRACT.md`](../governance/MEASUREMENT_CONTRACT.md) |

### Control plane / CLI surface
| Resource | Path |
|----------|------|
| Command registry | [`src/control_plane/registry.py`](../../src/control_plane/registry.py) |
| HTTP server | [`src/control_plane/server.py`](../../src/control_plane/server.py) |
| CLI matrix | [`docs/reference/cli-matrix.md`](../reference/cli-matrix.md) |

### Spine (call, do not reimplement)
| Resource | Path |
|----------|------|
| EngineRunner | [`src/core/engine_runner.py`](../../src/core/engine_runner.py) |
| Backtest | [`src/runtime/backtest_v2.py`](../../src/runtime/backtest_v2.py) |
| Live hook | [`src/runtime/live_engine_hook.py`](../../src/runtime/live_engine_hook.py) |
| Feature pipeline | [`src/features/feature_pipeline.py`](../../src/features/feature_pipeline.py) |

### Docs doctrine
| Resource | Path |
|----------|------|
| Agent reference | [`docs/reference/agent-reference.md`](../reference/agent-reference.md) |
| Agent topic | [`docs/topics/ai-automation-agent.md`](../topics/ai-automation-agent.md) |
| Agent memory | [`docs/memory/agent-memory.md`](../memory/agent-memory.md) |
| LLM governance | [`docs/architecture/llm-governance-layer.md`](../architecture/llm-governance-layer.md) |
| Signal flow | [`docs/architecture/signal-flow.md`](../architecture/signal-flow.md) |
| Schemas (agent audit) | [`docs/reference/schemas.md`](../reference/schemas.md) §9.2 |
| Multi-LLM protocol | [`multi_llm/MULTI_LLM_PROTOCOL.md`](../../multi_llm/MULTI_LLM_PROTOCOL.md) |
| Example service pattern | [`docs/reference/example-service.py`](../reference/example-service.py) |

### Analysis scripts useful as Ops tools
| Script | Role |
|--------|------|
| `scripts/analysis/crt_funnel_diagnostic.py` | Funnel |
| `scripts/analysis/crt_fail_reason_diagnostic.py` | Reject reasons |
| `scripts/analysis/funnel_diagnosis.py` | Funnel alt |
| `scripts/analysis/compress_logs_for_llm.py` | Context compression |
| `scripts/research/gate_measurement_m_gate_01.py` | Gate A/B |
| `scripts/governance/feature_surface_query.py` | Feature surface |

### Tests
| Test | Path |
|------|------|
| Plan compiler | `tests/test_agent_plan_compiler.py` |
| Executor | `tests/test_agent_executor_confirm.py` |
| Intent | `tests/test_agent_intent_router.py` |
| Registry | `tests/test_agent_tool_registry.py` |
| Shadow gate | `tests/test_shadow_promotion_gate.py` |
| Handoff | `tests/test_handoff_state.py` |

---

## 11. Worked example (Campaign Runner)

**User:** `goal: tune BNBUSDT until validation APPROVE then backtest; skip live`

1. Intent → `campaign_run` / goal kind `campaign_pipeline`  
2. Seed plan ≈ `tune_and_validate` + `backtest.run_v2` (skip promotion unless asked)  
3. `tuner.run_multi` → confirm → checkpoint  
4. `validator.validate` → REJECT → branch → re-tune once (max) or STOP with report  
5. APPROVE → optional promote (confirm) → `backtest.run_v2`  
6. Success criteria eval → session summary + optional GenAI narrative  
7. All steps in `logs/agent_audit.jsonl` with `goal_id`

---

## 12. Open decisions (User)

1. Ship **Ops Doctor** or **Campaign Runner** first?  
2. Is Mode C (allowlist free replan) acceptable for read-only only?  
3. Should `cp.run` unify control-plane and agent, or keep thin wrappers?  
4. May Level-1 drafts write under `results/incidents/` without y/N if path-guarded?  
5. Research campaigns blocked until first sealed `MC-*`, or allowed with UNKNOWN labels?

---

## 13. Acceptance criteria for “design implemented”

- [ ] `goal_loop.enabled=false` preserves current agent CLI behavior  
- [ ] No spine/module changes to scoring math  
- [ ] Executor fences still covered by `test_agent_executor_confirm`  
- [ ] New tools registered + SITS if new scripts  
- [ ] Topic `ai-automation-agent.md` Updated + Discussion entry  
- [ ] Construction protocol completion green for the change class  
- [ ] SESSION LOG + no claim of production authority for research outputs  

---

*End of design. Implementation starts only after User selects Phase 2/3 scope.*
