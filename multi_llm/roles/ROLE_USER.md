# ROLE_USER.md — Bridge & Principal Decision-Maker

> Frozen role. Part of [`../MULTI_LLM_PROTOCOL.md`](../MULTI_LLM_PROTOCOL.md). The User is a
> **first-class actor**, not just plumbing: the human who owns the goal, moves context between
> models, and gives final approval. The four LLMs are workers; the User is the principal.

## Owns
- **The bridge.** Carry `context/*.md` + the per-story pack + each `PROMPT_FOR_NEXT_MODEL` between
  models (DeepSeek → Gemini → ChatGPT → Claude). No model talks to another directly.
- **Routing.** Decide which model goes next when the pipeline branches, and when to stop a cycle.
- **The goal.** Set / change the economic objective (G001) and priorities the workers serve.
- **Approval gates.** Approve irreversible / outward-facing actions and promotions — the `y/N`
  confirm and the `APPROVE` promotion gate are the User's, never an LLM's.
- **Conflict resolution.** When workers disagree or a `TruthConflict` is surfaced, the User decides
  (or runs the test that decides).

## Responsibilities each cycle
- Run `Compile` (`build_context.py`), `pack_story.py`, and `log_turn.py` between turns.
- Capture every model's response verbatim via `log_turn.py` (the no-loss guarantee depends on it).
- Keep `HANDOFF.md` honest (current actor / next actor / what's blocked).
- Advance `multi_llm/build_queue.jsonl` as stories complete.

## Authority (where the User sits)
Above the **LLMs** — the User directs them and may override their *advice*. **Below
Reality / Tests / Findings** — the User cannot wish a failing test green or a losing strategy
profitable (CLAUDE.md §6.5: *evidence has no authority; only demonstrated G001 improvement grants
authority* — this binds the User too). The User decides **what to do** about evidence, never what
the evidence **is**. Authority hierarchy: `Reality > Tests > Findings > Repository > Shared
Context > User > LLMs`.

## Must NOT
- Be bypassed on irreversible / outward-facing actions (Claude must wait for User approval).
- Be expected to hold the whole codebase in their head — that is what the per-story `pack_story.py`
  packs are for. The User reviews the *bounded* view, not the repo.

## Not a turn-logging model
The User is the operator/decider, not a model whose responses fill the ledger; `next_actor` in
`HANDOFF.md` is always one of the four LLMs. The User's decisions live in `HANDOFF.md` approvals,
the §6 SESSION LOG, and the `y/N` / `APPROVE` gates.
