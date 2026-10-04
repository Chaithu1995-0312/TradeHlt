# Domain Contract: Agent

## Purpose
Provide a deterministic, safe, auditable AI assistant that can execute pipeline workflows (tune→validate→promote→backtest), deliver advisory copilot insight on live signals, and run governance procedures — without any autonomous planning or execution authority.

## Why does this exist?
The user thought: *"I want an AI that helps me run the system — but it must be predictable and safe. Every write needs my confirmation; every plan is pre-defined in a lookup table."*

**Evidence:** CLAUDE.md:68–70; assistant_project.md:1210–1223 — Confidence: Certain

## Authority
- **Owns:** Deterministic plan execution (PlanCompiler with PLAN_REGISTRY), intent routing (IntentRouter), tool safety gates (Executor with confirm-gate + path-guard).
- **Decides:** Which tool sequence to run for a given intent (lookup table), whether a tool can write to the requested path.
- **Must NOT:** Plan autonomously — planning is deterministic lookup, not LLM generation.
- **Must NOT:** Write outside approved paths (configs/production/|logs/|results/) without user confirmation.
- **Must NOT:** Have write_tools_enabled non-empty by default.

## Must (Required Behaviors)
1. IntentRouter must classify user input using regex first (0.85 confidence threshold) — LLM fallback only if regex fails.
2. PlanCompiler must look up the tool sequence in PLAN_REGISTRY — never generate it via LLM.
3. Executor must require confirmed=True for write tools (y/N confirmation).
4. Executor must enforce path-guard (only allow writes to configs/production/*, logs/*, results/*).
5. Every tool execution must be logged (per-step + per-session to agent_audit.jsonl, agent_intent_log.jsonl).

## Must Never (Forbidden Behaviors)
1. Must NEVER allow the LLM to plan tool sequences (PLAN_REGISTRY is a hard prefix, not a suggestion).
2. Must NEVER bypass confirm-gate for write operations.
3. Must NEVER allow writes outside the path whitelist.
4. Must NEVER route a governance approve/reject decision through the LLM.

## Failure Modes
| Failure | Detection | Severity |
|---------|-----------|----------|
| IntentRouter classifies wrong intent | Manual review / audit log | MEDIUM |
| Path-guard blocks legitimate write | False positive — user must retry | LOW |
| LLM hallucination in arg-filling | Tool will fail at execution | LOW (bounded by plan lookup) |
| write_tools_enabled accidentally includes dangerous tool | Manual audit | MEDIUM |

## Economic Meaning
The agent reduces operator cognitive load at zero autonomy risk. Its value is in automating repetitive sequences (tuner→validator→promotion) while keeping the human in the loop for every write. The deterministic PLAN_REGISTRY is the key invention — it prevents the LLM from "deciding" what to do.

**Evidence:** CLAUDE.md:68–70; agent-reference.md — Confidence: Certain

## Evidence
- CLAUDE.md:68–70 (PlanCompiler: deterministic by design) — Confidence: Certain
- CLAUDE.md:29–31 (agent-reference.md) — Confidence: Certain
- assistant_project.md:1210–1223 (design doc: PlanCompiler added to prevent LLM planning) — Confidence: Certain