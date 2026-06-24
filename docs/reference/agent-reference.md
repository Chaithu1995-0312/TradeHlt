# AGENT_REFERENCE.md

> Complete reference for the AI Automation Agent under `src/agent/`.
> 14 intents, 20 registered tools, 3 execution modes, deterministic planning.

---

## 1. Overview

```
User NL input
     │
     ▼
IntentRouter.classify()          (regex fast-path, LLM fallback)
     │        ↳ returns {mode, intent_key, confidence}
     ▼
PlanCompiler.build(intent_key)   (deterministic PLAN_REGISTRY lookup — NO LLM)
     │        ↳ returns Plan(intent_key, steps=[ToolStep, ...])
     ▼
ArgFiller.fill(plan, context)    (resolve {placeholder} args from state + prior tool outputs)
     │
     ▼
Executor.run(plan)               (confirm-gate for write tools + path-guard)
     │        ↳ dispatches each ToolStep via tool_registry.get_tool(name)
     ▼
AuditLogger.write_step() + write_session_summary()
     │        ↳ logs/agent_audit.jsonl + logs/agent_intent_log.jsonl
     ▼
Response to user
```

**Key design commitment**: planning is **deterministic** — `PLAN_REGISTRY` is a pure `Dict[str, List[ToolStep]]` lookup. The LLM classifies intent; it does **not** choose which tools to run.

---

## 2. Modes

| Mode          | File                                    | Purpose                                                                                              | Has write tools? |
| ------------- | --------------------------------------- | ---------------------------------------------------------------------------------------------------- | ---------------- |
| `pipeline`    | `src/agent/modes/pipeline_mode.py`      | Orchestrates tuner → validator → promotion → backtest. All quality gates run inside the tool handlers. | Yes              |
| `copilot`     | `src/agent/modes/copilot_mode.py`       | Live signal advisor. Read-only — copilot **never** places or cancels trades. `UltronRiskGate` remains the sole execution authority. | No               |
| `governance`  | `src/agent/modes/governance_mode.py`    | Meta-reasoner for autonomous governance via `ShadowPromotionGate`. Writes scratch files only; promotion goes through the gate. | Yes (governance.run_loop) |

---

## 3. Tool Registry

Registered in `src/agent/tool_registry.py` via the `register_tool(...)` decorator.

### 3.1 ToolSpec fields

```python
@dataclass
class ToolSpec:
    name:         str
    description:  str
    args_schema:  dict              # {param: {type, required, desc}}
    handler:      Callable
    write:        bool = False      # True → Executor demands per-call confirmation
    allowlist:    bool = True       # False → must appear in config.write_tools_enabled
```

### 3.2 Pipeline-mode tools (6)

| Tool                                  | Write | Args (required *)                                         | Purpose                                                     |
| ------------------------------------- | :---: | --------------------------------------------------------- | ----------------------------------------------------------- |
| `tuner.run_multi`                     |  ✔︎   | `data_dir*`, `instruments`, `n_iter`                      | Multi-instrument parameter grid search                      |
| `validator.validate`                  |       | `checkpoint_path`, `data_dir`, `config_id`                | Run `ConfigValidator.validate()` → `ValidationReport`       |
| `promotion.promote_from_checkpoint`   |  ✔︎   | `checkpoint_path`, `version*`, `data_dir`                 | Validate + promote approved config                          |
| `backtest.run_v2`                     |       | `config_path`, `data_dir`                                 | Run `BacktestRunner` on a production config                 |
| `live_hook.dry_run`                   |       | `instrument`, `data_path`                                 | Simulate live execution (no order dispatch)                 |
| `live_hook.enable`                    |  ✔︎   | `approval_code*`                                          | Enable live execution mode                                  |

### 3.3 Copilot-mode tools (7, all read-only)

| Tool                   | Args (required *)                          | Purpose                                                       |
| ---------------------- | ------------------------------------------ | ------------------------------------------------------------- |
| `engine.run`           | `instrument*`, `features`                  | Run the CRT engine stack on a feature dict                    |
| `fusion.explain`       | `instrument*`, `engine_result`             | Per-component scores + fusion decomposition                   |
| `planner.plan`         | `instrument*`, `decision_json`, `features_json` | Generate trade plan (entry/SL/TP/RR/TTL)                 |
| `risk.check`           | `trade_plan*`, `account_state`             | Evaluate trade against risk constraints (no execution)        |
| `advise.veto`          | `signal_json*`, `reason`                   | Recommend vetoing a signal                                    |
| `advise.resize`        | `trade_plan*`, `new_size*`                 | Recommend position-size adjustment                            |
| `collector.tail`       | `n_rows`                                   | Retrieve last N rows from `collector.jsonl`                   |

### 3.4 Governance-mode tools (5)

| Tool                          | Write | Args (required *)                              | Purpose                                                       |
| ----------------------------- | :---: | ---------------------------------------------- | ------------------------------------------------------------- |
| `governance.run_loop`         |  ✔︎   | `dry_run`                                      | Run meta-governor + `ShadowPromotionGate` loop                |
| `reflection.load_merge`       |       | `collector_log`, `trades_csv`                  | Merge collector + trades into reflection dataset              |
| `reflection.generate_prompt`  |       | `collector_log`, `trades_csv`                  | Render meta-governor prompt from reflection data              |
| `meta_governor.dry_run`       |       | `collector_log`, `trades_csv`                  | Run `MetaGovernorExecutor` inference in preview (no write)    |
| `shadow.stage_candidate`      |       | `candidate_patch*`                             | Stage a candidate config patch for shadow backtest            |

### 3.5 Cross-mode tools (2)

| Tool             | Args (required *)           | Purpose                                    |
| ---------------- | --------------------------- | ------------------------------------------ |
| `audit.tail`     | `session_id`, `n_records`   | Retrieve session history from audit logs   |
| `audit.inspect`  | `session_id*`               | Detailed inspection of a single session    |

### 3.6 Registry helpers

```python
get_tool(name: str) -> ToolSpec
get_schema_text(mode: Optional[str]) -> str   # renders TOOL_SCHEMA for LLM prompts
```

---

## 4. Intent Router

File: `src/agent/intent_router.py`.

### 4.1 Classification flow

```python
class IntentRouter:
    def __init__(
        self,
        llm_chat_fn,
        patterns_path="src/agent/prompts/intent_patterns.json",
        use_llm=True,
        confidence_floor=0.6,
    ): ...

    def classify(self, user_input: str, conversation: list[dict]) -> dict:
        # 1. Regex fast path
        result = self._regex_classify(user_input)     # confidence 0.85 on match
        if result is not None:
            return result

        # 2. LLM fallback (only if regex missed)
        result = self._llm_classify(user_input, conversation)
        if result and result["confidence"] >= self.confidence_floor:
            return result

        # 3. Degenerate fallback
        return {"mode": None, "intent_key": "ask_user", "confidence": 0.0}
```

Regex patterns live in `src/agent/prompts/intent_patterns.json`. The `llm_chat_fn` is injected (usually `llm_inference_client.llm_chat`) and is expected to return a JSON blob the router extracts.

### 4.2 Intent catalogue

**Pipeline mode (7):**
- `tune_only`
- `tune_and_validate`
- `tune_and_promote`
- `validate_only`
- `promote_only`
- `backtest_only`
- `full_pipeline`

**Copilot mode (3):**
- `advise_signal`
- `veto_query`
- `resize_query`

**Governance mode (3):**
- `governance_inspect`
- `governance_propose`
- `governance_run`

**Cross-mode (1):**
- `audit_inspect`

**Degenerate fallback:** `ask_user` (returned when no intent is recognised).

---

## 5. PLAN_REGISTRY (deterministic lookup)

File: `src/agent/plan_compiler.py`. Every intent maps to an **ordered** list of `ToolStep`. The LLM never chooses tools or ordering.

### 5.1 Pipeline plans

| Intent                | Tool sequence                                                                                           |
| --------------------- | ------------------------------------------------------------------------------------------------------- |
| `tune_only`           | `tuner.run_multi`                                                                                       |
| `tune_and_validate`   | `tuner.run_multi` → `validator.validate`                                                                |
| `tune_and_promote`    | `tuner.run_multi` → `validator.validate` → `promotion.promote_from_checkpoint`                          |
| `validate_only`       | `validator.validate`                                                                                    |
| `promote_only`        | `promotion.promote_from_checkpoint`                                                                     |
| `backtest_only`       | `backtest.run_v2`                                                                                       |
| `full_pipeline`       | `tuner.run_multi` → `validator.validate` → `promotion.promote_from_checkpoint` → `backtest.run_v2` → `live_hook.dry_run` |

### 5.2 Copilot plans

| Intent           | Tool sequence                                                                   |
| ---------------- | ------------------------------------------------------------------------------- |
| `advise_signal`  | `engine.run` → `fusion.explain` → `planner.plan` → `risk.check` → `advise.veto` |
| `veto_query`     | `engine.run` → `fusion.explain` → `advise.veto`                                 |
| `resize_query`   | `engine.run` → `fusion.explain` → `advise.resize`                               |

### 5.3 Governance plans

| Intent                  | Tool sequence                                                                                   |
| ----------------------- | ----------------------------------------------------------------------------------------------- |
| `governance_inspect`    | `reflection.load_merge` → `meta_governor.dry_run`                                               |
| `governance_propose`    | `reflection.load_merge` → `reflection.generate_prompt` → `meta_governor.dry_run` → `shadow.stage_candidate` |
| `governance_run`        | `reflection.load_merge` → `meta_governor.dry_run` → `governance.run_loop`                       |

### 5.4 Cross-mode

| Intent           | Tool sequence  |
| ---------------- | -------------- |
| `audit_inspect`  | `audit.tail`   |

### 5.5 PlanCompiler API

```python
@dataclass
class ToolStep:
    tool_name: str
    args:      dict
    required:  bool = True

@dataclass
class Plan:
    intent_key: str
    steps:      list[ToolStep]

class PlanCompiler:
    @staticmethod
    def build(intent_key: str) -> Plan: ...
    # Returns an ask_user Plan if intent_key is not in PLAN_REGISTRY.
```

---

## 6. Executor

File: `src/agent/executor.py`. Two guards sit between the plan and the handler:

1. **Confirm-gate** — if `ToolSpec.write is True`, the executor yields to the REPL for explicit confirmation before invoking the handler.
2. **Path-guard** — writes that target paths outside the expected roots (`configs/`, `results/`, `logs/`) are rejected before the handler runs.

For each step the executor records a per-step audit record (see §8) and, once the plan completes, writes a session summary.

---

## 7. Agent State

File: `src/agent/state.py`.

```python
@dataclass
class AgentState:
    session_id:   str
    messages:     list[dict]          # [{role, content}]
    last_intent:  str | None
    last_outcome: dict | None         # {success, metrics, error}
```

`AgentState` is held in memory for the duration of a REPL session; it is **not** persisted between sessions. Persistence lives in the audit JSONL logs instead.

---

## 8. Audit Logs

Written by `src/agent/audit.py` (`AuditLogger`).

### 8.1 Per-step record → `logs/agent_audit.jsonl`

```json
{
  "ts":           "2026-04-25T00:00:00Z",
  "session_id":   "sess_abc123",
  "plan_id":      "plan_xyz789",
  "step_index":   0,
  "mode":         "pipeline",
  "intent_key":   "tune_and_validate",
  "tool":         "tuner.run_multi",
  "args_hash":    "a1b2c3d4e5f6g7h8",
  "result_hash":  "99112233aabbccdd",
  "write":        true,
  "confirmed":    true,
  "outcome":      "success",
  "latency_ms":   1203,
  "error":        null
}
```

### 8.2 Session summary → `logs/agent_audit.jsonl` + `logs/agent_intent_log.jsonl`

```json
{
  "ts":                "2026-04-25T00:00:05Z",
  "session_id":        "sess_abc123",
  "plan_id":           "plan_xyz789",
  "intent":            "tune and validate the candidate",
  "intent_key":        "tune_and_validate",
  "mode":              "pipeline",
  "plan_steps":        ["tuner.run_multi", "validator.validate"],
  "outcome":           "completed",
  "metrics":           {"tuner_score": 0.52, "promotion_status": "not_attempted"},
  "write_confirmed":   true,
  "total_latency_ms":  2714
}
```

### 8.3 Field semantics

| Field            | Meaning                                                                 |
| ---------------- | ----------------------------------------------------------------------- |
| `args_hash`      | `SHA256(json(args))[:16]` — args not stored raw (may contain secrets)   |
| `result_hash`    | `SHA256(json(result))[:16]` — or `null` on failure                      |
| `confirmed`      | `true` / `false` for write tools; `null` for read tools                 |
| `outcome`        | `"success" \| "failed" \| "skipped"`                                    |
| `write_confirmed` | Session-level — `true` if at least one write tool was confirmed        |

---

## 9. Agent Config (from production JSON)

```json
"agent": {
  "model":                    "bitnet_3b",
  "repl_enabled":             true,
  "copilot_auto_narrate":     false,
  "write_tools_enabled":      [
    "tuner.run_multi",
    "promotion.promote_from_checkpoint",
    "live_hook.enable",
    "governance.run_loop"
  ]
}
```

A tool marked `write=True` AND `allowlist=False` must appear in `write_tools_enabled` or the executor refuses to run it.

---

## 10. CLI

```bash
python -m src.agent.cli
```

The REPL drives `AgentCore.turn(user_input)`. Every turn does: `IntentRouter → PlanCompiler → ArgFiller → Executor → AuditLogger` and returns the assistant reply.

---

## 11. Adding a new tool

1. Implement the handler as a plain function. Keep side effects local; return a JSON-serialisable dict.
2. Register it in `src/agent/tool_registry.py`:
   ```python
   @register_tool(
       name="mymode.my_tool",
       description="One-line purpose.",
       write=False,
       args_schema={"foo": {"type": "str", "required": True, "desc": "..."}},
   )
   def my_tool(foo: str) -> dict:
       ...
   ```
3. Add the intent → tool sequence to `PLAN_REGISTRY` in `src/agent/plan_compiler.py`.
4. Update `src/agent/prompts/intent_patterns.json` with regex patterns for the new intent.
5. Add a test in `tests/test_agent_tool_registry.py` and, if the intent is new, a plan-compiler test in `tests/test_agent_plan_compiler.py`.
6. For write tools: add the tool name to `agent.write_tools_enabled` in the production config (see `docs/CONFIG_REFERENCE.md`).

---

## 12. Invariants enforced by tests

- Every tool in `PIPELINE_TOOLS`, `COPILOT_TOOLS`, `GOVERNANCE_TOOLS` is registered (`test_agent_tool_registry.py`).
- Write tools are correctly flagged (`test_agent_tool_registry.py`).
- `TOOL_SCHEMA` markdown renders without error (`test_agent_tool_registry.py`).
- Every intent in `PLAN_REGISTRY` has ≥1 step (`test_agent_plan_compiler.py`).
- Write tools without confirmation are blocked in the executor (`test_agent_executor_confirm.py`).
- Intent router regex patterns are non-empty and compile (`test_agent_intent_router.py`).
