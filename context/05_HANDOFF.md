# 05 · Handoff & Protocol

> **GENERATED — do not edit by hand.** Regenerate with `python scripts/context/build_context.py` (the `Compile` trigger).
>
> A *derived view*, not a source of truth (MULTI_LLM_PROTOCOL.md §2: Shared Context is never authoritative on conflict). Edit the source, then re-Compile.
>
> **Sources:** multi_llm/roles, HANDOFF.md


## Roles (frozen — multi_llm/roles/)

- `ROLE_CHATGPT.md` — ROLE_CHATGPT.md — Chief Architecture Interpreter
- `ROLE_CLAUDE.md` — ROLE_CLAUDE.md — Chief Engineer (Executor)
- `ROLE_DEEPSEEK.md` — ROLE_DEEPSEEK.md — Chief Planner
- `ROLE_GEMINI.md` — ROLE_GEMINI.md — Chief Navigator
- `ROLE_USER.md` — ROLE_USER.md — Bridge & Principal Decision-Maker

## Mandatory response block (every model, every turn)

```
CURRENT_TASK:
NEXT_10_STEPS:
CONTEXT_DELTA:
FOR_NEXT_MODEL:
PROMPT_FOR_NEXT_MODEL:
CONFIRMATION:
```

Flow: DeepSeek→Gemini→ChatGPT→Claude→Tests/Findings→Gemini. Full mandate: `multi_llm/MULTI_LLM_PROTOCOL.md`.

## Live handoff state (HANDOFF.md)

# HANDOFF.md — Live Multi-LLM State

> Hand-edited working memory passed between models. Small by design. Updated at the end of each
> cycle (MULTI_LLM_PROTOCOL.md §4 step 9). The compiler folds this into `context/05_HANDOFF.md`.
> The User owns this file (`multi_llm/roles/ROLE_USER.md`).

```yaml
current_actor:   Claude
current_story:   STORY-1.1 (fix LLM connectivity fail-open contract) — DONE
completed:
  - Track-3 multi-LLM layer + memory/transfer + User role + log split (codebase vs workflow)
  - STORY-1.1: llm_scorer fail-open 0.5 -> 1.0; 82/82 llm tests green; spine byte-identical (181 passed)
blocked: []
next_actor:      Gemini
next_prompt: |
  STORY-1.1 is done (LLM fail-open contract fixed, spine unaffected). Read context/*.md +
  multi_llm/build_queue.jsonl. Re-confirm the LIVE Epic-1 failing set (the spec's list is stale —
  rr_fusion already passes), pick the next real story (gaussian_impl_switch or dual_gate), list the
  next 10, and flag gaps before DeepSeek plans it.
confirmation:    "Was this produced by the intended role (Claude=Executor)?  yes"
```
