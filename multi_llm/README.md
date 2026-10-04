# multi_llm/ — Multi-LLM Coordination Layer

> **One-line:** turns hand-operated models into coherent lanes with shared repo truth — so they
> stop drifting into separate realities or echo chambers.
>
> **The truth lives in the repo, not here.** These files are the *protocol* and the *roles*. The
> authoritative state lives in `CLAUDE.md`, `docs/current-findings.md`, the tests, and
> `configs/production/ACTIVE_VERSION`. This layer grants **no new authority** (CLAUDE.md §6.5 / §12).

## Dual-lane (HOW — initiated 2026-07-14)

| Lane | Path | Purpose |
|---|---|---|
| **I — Implementation** | `MULTI_LLM_PROTOCOL.md` + `roles/` + `build_queue.jsonl` | Code epics: DeepSeek plan → Gemini → ChatGPT → Claude execute |
| **R — Research** | **[`research_lane/`](research_lane/README.md)** | ERP research cycles: PROPOSAL → CRITIQUE → EXECUTION_EVIDENCE → DECISION; Promise Ladder PL-0… |

**Do not vote across models.** Research Lane HOW design:  
[`docs/research-readiness/edge-research-platform-mllm-how.md`](../docs/research-readiness/edge-research-platform-mllm-how.md).

## What's here
| File | Kind | Purpose |
|---|---|---|
| `MULTI_LLM_PROTOCOL.md` | authored | **Lane I** handoff mandate. |
| `research_lane/` | authored | **Lane R** packages, ledger, templates (initiated). |
| `PROMPT_PLAYBOOK.md` | authored | Operating prompt library (GATHER · ENHANCE · IMPLEMENT), relabeled to the frozen roles. |
| `ISSUE_TRACKING_PLAYBOOK.md` | authored | Conversation-diff → candidate `build_queue.jsonl` stories (one-queue, append-only). |
| `roles/ROLE_USER.md` | authored | The **User** = Bridge & Principal Decision-Maker (sets goal, moves context, approves). |
| `roles/ROLE_*.md` | authored | **Lane I** frozen responsibilities (Planner / Navigator / Interpreter / Executor). |
| `build_queue.jsonl` | generated | The single **implementation** story backlog. |
| `../HANDOFF.md` | hand-edited | Live handoff state: current actor, current story, next actor, next prompt. |
| `../context/*.md` | generated | The **Portable Mind** — derived views you paste into any model. Gitignored (regenerate on demand). |

## How to run one cycle
```
# 1. Regenerate the portable context (the "Compile" trigger)
python scripts/context/build_context.py

# 2. Hand context/*.md + the next prompt to each model in order:
#    DeepSeek (plan) -> Gemini (gaps/next) -> ChatGPT (explain/expand) -> Claude (build)

# 3. Claude implements + runs Validate + appends the SESSION LOG.
#    Reality (tests + docs/current-findings.md) decides.

# 4. Advance the queue + HANDOFF.md, then go to 1.
```

## Re-seed the queue (only when the spec changes)
```
python scripts/context/seed_build_queue.py        # writes multi_llm/build_queue.jsonl
python scripts/context/seed_build_queue.py --check # print, write nothing
```

## Track 1 bridge
`build_queue.jsonl` carries the 44 stories of `FULL_BUILD_SPECIFICATION.md` (the domain-first
refactor). The multi-LLM loop above is the vehicle that executes them — Epic 1 (repair the 23
failing tests) first. See the approved plan and CLAUDE.md §13.
