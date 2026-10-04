# Incorporate the "Jarvis" ChatGPT workflow pack into `multi_llm/`

## Context

The user dropped `ChatGpt workflow-20260615T142326Z-3-001.zip` (25 files: `.md`, `.docx`, `.js`,
`.json`) and asked to "incorporate into current workflows." The pack is a **multi-LLM
orchestration system ("Jarvis")** — the *same family* as the repo's existing `multi_llm/` layer
(CLAUDE.md §13), but authored independently, so it carries a **conflicting role map** and a
copy-paste/Jira flavor.

**The conflict (why this needs care, per CLAUDE.md §6.2 rule 3 — never silently overwrite frozen truth):**

| Stage | Repo `multi_llm/` (FROZEN, test-enforced) | Jarvis pack |
|---|---|---|
| Orchestrator | **User = Bridge/Principal** | Jarvis (a model) |
| Planner | **DeepSeek** | DeepSeek = Auditor |
| Navigator | **Gemini** | — |
| Interpreter | **ChatGPT** | ChatGPT = Architect |
| Optimizer/Quant | — | Gemini split → Think + Pro |
| Executor | **Claude** | Claude = Implementer ✓ |

The repo's roles are frozen in `multi_llm/roles/ROLE_*.md` and enforced by
`tests/test_handoff_state.py` (`_ROLES = {DeepSeek, Gemini, ChatGPT, Claude}`).

**User decisions (locked):**
1. **Keep the repo's frozen role map** — map Jarvis concepts *onto* existing roles; do not touch
   `ROLE_*.md`, `turn_ledger.py` ROLES, or the tests.
2. **Incorporate all four** new prompt categories: GATHER, ENHANCE, IMPLEMENT, Jira/diff-tracking.
3. **Fold into the repo as markdown; drop the binaries** (no `.docx`, no `build_doc.js`,
   no `jarvis_state.json`).

**Intended outcome:** the genuinely-additive value of the pack (reusable prompt transforms +
gather/implement prompt chains + a conversation-diff→issue capability) becomes part of the live
`multi_llm/` workflow, expressed in the repo's frozen role vocabulary and bound to the existing
single queue / handoff state — adding capability without adding doc entropy or a competing protocol.

## What is NOT incorporated (and why)

- **`build_doc.js`** (55 KB JS doc generator) — conflicts with the repo's Python generator
  (`scripts/context/build_context.py`) and the §13 "truth stays in repo / generated views only"
  doctrine. Dropped.
- **`jarvis_state.json`** — a parallel state file. Its fields already map onto existing state:
  `task`→`CURRENT_TASK` (§3 block), `spec/diff/tests/audit`→`turn_ledger.jsonl`,
  `agent_log`→`turn_ledger.jsonl`, queue→`build_queue.jsonl`. Adding it violates the anti-drift
  "one queue / one state" rule. Dropped — documented as a mapping instead.
- **Jarvis role cards / Gemini-Think-Pro split / ChatGPT-as-Architect** — conflicts with the frozen
  map (decision 1). The *stage concepts* are kept; the *role reassignments* are not.
- **The 25 raw `.docx`/`.js` binaries** — not committed (decision 3).

## Role mapping (Jarvis stage → repo frozen role)

This mapping is the core content; every prompt in the new docs is relabeled accordingly:

| Jarvis stage / agent | Repo owner |
|---|---|
| Jarvis (orchestrate, log, route) | **User = Bridge** (+ `turn_ledger.jsonl`) |
| G1 Clarifier (architecture snapshot JSON) | **ChatGPT = Interpreter** (assumption/risk exposure) + **Gemini = Navigator** (open-questions/gap check) |
| G2 Pyan DOT analysis | **Gemini = Navigator** / the `Map` trigger (aligns with `scripts/analysis/gen_pyan.py`, `graph.dot`) |
| G3 micro-service boundary audit | **Claude = Executor** + the `Validate` gate (aligns with `docs/architecture/service-boundary-map.md`) |
| E1–E5 ENHANCE transforms | **User = Bridge** crafting the §3 `PROMPT_FOR_NEXT_MODEL` field |
| I1 SpecWriter | **DeepSeek = Planner** |
| I2 DiffGen ‖ I3 TestGen | **Claude = Executor** |
| I4 Audit / sign-off | **Reality = Tests + Findings** via the `Validate` trigger (not a model) |
| Commit / PR / Changelog writers | **Claude = Executor** (already in CLAUDE.md §3 flow) |
| Jira issue modeling / conversation-compare | feeds the existing **`build_queue.jsonl`** (one queue) |

## Files to create

### 1. `multi_llm/PROMPT_PLAYBOOK.md` (new)
The operating prompt library for the workflow, in three sections mirroring GATHER → ENHANCE →
IMPLEMENT, **with every prompt relabeled to the frozen role names** per the table above. Source
text comes from the pack's `G1_clarifier.md`, `I2_diffgen.md`, `I4_audit.md`, `KICKOFF_TEMPLATE.md`,
`Jarvis_Prompt_Framework.docx` (GATHER/ENHANCE/IMPLEMENT sections, already extracted), and the
`AGENT_ROLES.md` constraint cards.
- **GATHER**: Clarifier JSON prompt, Pyan DOT-analysis prompt, boundary-audit checklist.
- **ENHANCE**: the 5 transforms (context layer · output format · uncertainty guard · role+constraint
  pairing · step-by-step trigger) — framed as how the Bridge sharpens `PROMPT_FOR_NEXT_MODEL`.
- **IMPLEMENT**: SpecWriter → DiffGen‖TestGen → Validate(Audit) → Commit/PR/Changelog prompts.
- Header cross-links to `MULTI_LLM_PROTOCOL.md` §3 (handoff block), `docs/architecture/trigger-vocabulary.md`,
  and CLAUDE.md §3. Explicit note: these are **advisory orchestration, grant no new authority** (§6.5 / §13).

### 2. `multi_llm/ISSUE_TRACKING_PLAYBOOK.md` (new)
The conversation-comparison → issue-modeling capability (the pack's `MultiLLMConversationComparisonPrompts.docx`
+ `Jira Task Creation.docx` + `Multi agent work flow tracking prompt.docx`), relabeled and **bridged to
the existing single queue**: the Jira-style issues these prompts produce are appended to
`multi_llm/build_queue.jsonl` as candidate `STORY-*` records (append-discipline, §6.2 rule 4) — not a
parallel tracker. Documents the 3-prompt chain: summarize → compare (strict diff) → ambiguity-resolve →
issue-model.

## Files to modify (surgical)

- **`multi_llm/README.md`** — add two bullet links to the new playbooks under the existing file map.
- **`CLAUDE.md` §13** — one sub-bullet pointer to `PROMPT_PLAYBOOK.md` / `ISSUE_TRACKING_PLAYBOOK.md`
  (minimal; §13 is already the multi_llm pointer section).
- **`docs/architecture/trigger-vocabulary.md`** — add a short cross-reference row/note: GATHER↔`Orient`/`Map`,
  ENHANCE↔prompt-crafting, IMPLEMENT↔`Implement`, Audit↔`Validate`. Keeps the new prompts discoverable
  from the trigger vocabulary instead of as an orphan layer.

## Explicitly unchanged (frozen-map guarantee)
`multi_llm/roles/ROLE_*.md`, `multi_llm/MULTI_LLM_PROTOCOL.md` role table, `src/multi_llm/turn_ledger.py`
`ROLES`, `tests/test_handoff_state.py`. No role added; no test contract changed.

## Optional (recommend, low cost)
`tests/test_multi_llm_playbooks.py` — assert both playbooks exist and that any "role:" assignment in
them uses only the frozen role names (a guard that catches future drift back toward the Jarvis map).
Mirrors the repo's "convert prose mandate → test floor" pattern.

## Verification

1. **Frozen-map compliance** — grep the two new docs to confirm no role *assignment* uses
   `Architect`/`Auditor`/`Think`/`Pro`/`Jarvis` (the words may appear only in a "mapped from" note).
2. **No regressions** — `pytest tests/test_handoff_state.py tests/test_context_compiler.py -q`
   (docs-only change; must stay green).
3. **No binaries / parallel state** — confirm no `.docx`, `build_doc.js`, or `jarvis_state.json`
   was added (`git status` shows only the 2 new `.md` + 3 edited files).
4. **Discoverability** — links resolve from `README.md`, CLAUDE.md §13, and trigger-vocabulary.
5. **SESSION LOG (CLAUDE.md §6, mandatory)** — append the `📝 SESSION LOG ENTRY` block to
   `assistant_project.md`. (Workflow-operation dimension → may also note in `llm_project_assistant.md`
   per §6 "two logs"; the codebase log is the primary.)
6. `context/` regeneration is **not** required (roles unchanged), but `python scripts/context/build_context.py`
   stays byte-identical — run only if you want to confirm.
