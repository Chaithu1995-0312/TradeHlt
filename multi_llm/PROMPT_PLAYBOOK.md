# multi_llm/PROMPT_PLAYBOOK.md — Operating Prompt Library

> **What this is.** A library of copy-paste prompts for running one cycle of the multi-LLM
> workflow, organized as **GATHER → ENHANCE → IMPLEMENT**. It is the prompt-level companion to
> [`MULTI_LLM_PROTOCOL.md`](MULTI_LLM_PROTOCOL.md) (which defines the handoff *mandate*) and to
> [`docs/architecture/trigger-vocabulary.md`](../docs/architecture/trigger-vocabulary.md) (which
> defines the *triggers*). Every prompt here is wrapped in the protocol's §3 handoff block.
>
> **Authority.** These prompts are **advisory orchestration and grant no new authority**
> (CLAUDE.md §6.5 / §13). They never bypass write-authority, the path-guard, the `y/N` confirm,
> the `APPROVE`-`ValidationReport` promotion gate, or the §6 SESSION LOG mandate.
>
> **Provenance + the role map (read first).** These prompts were adapted from an external "Jarvis"
> ChatGPT prompt-pack that used a *different* role map. They have been **relabeled to this repo's
> frozen roles** ([`roles/ROLE_*.md`](roles/), enforced by `tests/test_handoff_state.py`). The
> original→repo mapping is recorded once, here, and **nowhere else applies**:
>
> | Original pack stage | Repo owner (frozen) |
> |---|---|
> | central orchestrator | **User = Bridge/Principal** + `turn_ledger.jsonl` |
> | Clarifier (architecture snapshot) | **ChatGPT = Interpreter** (assumption/risk exposure) + **Gemini = Navigator** (gap/open-questions) |
> | call-graph / Pyan analysis | **Gemini = Navigator** / the `Map` trigger |
> | service-boundary audit | **Claude = Executor** + the `Validate` gate |
> | the 5 prompt transforms | **User = Bridge** sharpening §3 `PROMPT_FOR_NEXT_MODEL` |
> | spec writer | **DeepSeek = Planner** |
> | diff / test generation | **Claude = Executor** |
> | audit / sign-off | **Reality = Tests + Findings** via `Validate` (not a model) |
> | commit / PR / changelog | **Claude = Executor** (CLAUDE.md §3 flow) |
>
> The repo role map is **frozen** — do not reintroduce the original labels as role assignments.

---

## How the three phases map to existing triggers

| Phase | Purpose | Existing trigger(s) | Owner |
|---|---|---|---|
| **GATHER** | Understand the codebase before touching it | `Orient` / `Map` | ChatGPT (Interpreter) + Gemini (Navigator) |
| **ENHANCE** | Sharpen the handoff prompt before sending | — (crafting `PROMPT_FOR_NEXT_MODEL`) | User (Bridge) |
| **IMPLEMENT** | Plan → build → verify → record | `Implement` → `Validate` | DeepSeek (Planner) → Claude (Executor) → Reality |

State is **not** a new file — it lives where the protocol already puts it: the in-flight task is the
§3 `CURRENT_TASK`; each model's spec/diff/tests/review are captured verbatim in
`turn_ledger.jsonl`; the backlog is the single `build_queue.jsonl`. (No `jarvis_state.json`.)

---

## Phase 1 — GATHER (always run before touching code)

### G-1 · Clarifier — Architecture Snapshot
**Owner:** ChatGPT (Interpreter) produces it; Gemini (Navigator) validates `open_questions`.
**Output:** a JSON object pasted into the §3 `CONTEXT_DELTA`. Do **not** open a parallel state file.

```
You are the Interpreter (ChatGPT role, per multi_llm/roles/ROLE_CHATGPT.md).

Codebase context:
[PASTE: file tree, e.g. `git ls-files '*.py' | sort | head -80`, or the relevant services/<svc>.md]

Task:
[DESCRIBE: the feature, bug, or change in plain language]

Analyse the relevant existing architecture and output ONLY a JSON object:
{
  "task_description": "atomic, single-responsibility restatement",
  "affected_files": ["path/to/file.py"],
  "existing_patterns": ["pattern name: brief description"],
  "dependencies": ["service or module this touches"],
  "constraints": ["must not break X", "follow Y convention"],
  "open_questions": ["any ambiguity to resolve before coding"]
}

Rules:
- Do NOT write code or suggest solutions.
- Mark uncertain paths: "path/to/file.py (unverified)".
- If open_questions exist, stop and hand to the Navigator (Gemini) before the chain continues.
```

### G-2 · Call-Graph (Pyan) Analysis
**Owner:** Gemini (Navigator) / the `Map` trigger. Aligns with `scripts/analysis/gen_pyan.py` and the
repo's `graph.dot` (CLAUDE.md §3.4 / §10).

```
# Generate the graph first (the repo already ships this):
python scripts/analysis/gen_pyan.py    # writes graph.dot

# Then paste graph.dot into:
You are the Navigator (Gemini role, per multi_llm/roles/ROLE_GEMINI.md).
Read the Graphviz DOT call graph below.
[PASTE: graph.dot]

Answer:
1. Subgraph + edge semantics for THIS project.
2. The 3 most central nodes by fan-in/fan-out (show counts).
3. Dependency cycles / strongly-connected components, if any.
4. Where the proposed change lands (which service/seam) and its blast radius.
5. Modules that look like test/stub code.
Cite node names as `ModuleA → FunctionB → ClassC` (CLAUDE.md §10). No filler.
```

### G-3 · Service-Boundary Audit
**Owner:** Claude (Executor) drafts; the `Validate` gate confirms. Aligns with
[`docs/architecture/service-boundary-map.md`](../docs/architecture/service-boundary-map.md).

```
You are the Executor (Claude role) reviewing a module against repo conventions.
Module path: src/<package>/<module>.py
[PASTE: the module]

Confirm or flag each (per docs/reference/conventions.md + example-service.py):
[ ] Single public entry point / PascalCase class with typed public methods
[ ] Private helpers prefixed with _
[ ] from_prod_config / _require strict accessors — NO silent config defaults (CLAUDE.md §6.5)
[ ] No magic numbers (every tunable in configs/production/*.json)
[ ] No new HTTP/REST surface (control plane is stdlib + localhost-only)
[ ] Appears correctly in graph.dot / service-boundary-map.md
For each FAIL: quote file:line, show the code, give the compliant fix.
OVERALL: PASS | NEEDS REVISION
```

---

## Phase 2 — ENHANCE (sharpen every handoff prompt)

The **User = Bridge** applies these five transforms when filling the §3 `PROMPT_FOR_NEXT_MODEL`
field. They prevent the common failures: vague context, hallucinated paths, missing output spec.

| # | Transform | What to add |
|---|---|---|
| **E-1** | Context layer (always first) | Prepend the G-1 JSON + the relevant `context/*.md` Portable-Mind excerpt. |
| **E-2** | Output format | State the exact shape (JSON keys, unified-diff, table) the next model must return. |
| **E-3** | Uncertainty guard | "Mark anything unverified `(unverified)`; if blocked, write `# BLOCKED: …` and continue." |
| **E-4** | Role + constraint pairing | Name the frozen role (`roles/ROLE_*.md`) and its one binding constraint for this task. |
| **E-5** | Step-by-step trigger | For analysis/planning, ask for explicit reasoning before the answer. |

> A `# BLOCKED:` output is **never** passed downstream — resolve it (check the codebase or ask the
> Bridge) and re-issue, per the protocol's anti-drift discipline.

---

## Phase 3 — IMPLEMENT (plan → build → verify → record)

Order: **SpecWriter (Planner) → DiffGen ‖ TestGen (Executor, parallel) → Validate → Commit/PR/Changelog.**

### I-1 · SpecWriter
**Owner:** DeepSeek (Planner).

```
You are the Planner (DeepSeek role, per multi_llm/roles/ROLE_DEEPSEEK.md).
Task: [G-1 task_description]   Constraints: [G-1 constraints]

Write a spec (no code, ≤400 words):
1. What must be built.
2. Exact paths of every file to create/modify.
3. Public interface: signatures + docstrings for new services.
4. Acceptance criteria: 3–5 in Given/When/Then form.
5. Assumptions + out-of-scope.
Place new behavioral knobs in configs/production/*.json (no magic numbers, CLAUDE.md §6.5).
```

### I-2 ‖ I-3 · DiffGen and TestGen (run in parallel)
**Owner:** Claude (Executor). Two windows, same spec + G-1 context.

```
# I-2 DiffGen
You are the Executor (Claude role). Spec: [I-1]   Architecture: [G-1 patterns/files/constraints]
Produce a unified git diff implementing the spec.
- Follow conventions visible in affected_files exactly; full type hints; specific-exception handling.
- One-line comment above non-obvious logic. No hardcoded secrets/paths/magic numbers.
- Do NOT generate tests. Do NOT touch files outside the spec.
- If blocked: `# BLOCKED: [what to verify]` and continue.

# I-3 TestGen
You are the Executor (Claude role). Spec: [I-1]
Write pytest tests: APPROVE path + every hard-failure branch + circuit-breaker open path (if external I/O)
+ optional-dep-absent path. One named test per acceptance criterion. No masking mocks.
```

### I-4 · Audit / Sign-off  → the `Validate` gate (Reality, not a model)
There is **no model auditor** in this repo — review authority is **Reality = Tests + Findings**
(MULTI_LLM_PROTOCOL.md §2 authority hierarchy). Run the `Validate` trigger:

```
pytest per docs/reference/testing.md  +  determinism/byte-identical replay check
+  doc-citation resolution (tests/test_doc_citations.py)  →  score the Five Governance Questions.
```
Apply the diff/tests locally first; only proceed when green. A failure routes back to I-2/I-3.

### I-5 · Commit / PR / Changelog
**Owner:** Claude (Executor) — already the CLAUDE.md §3 flow. Conventional commit
(`type(scope): summary`, body = what+why, end with the `Co-Authored-By` trailer); PR body with
What / Why / How-to-test; changelog in Keep-a-Changelog form. Then append the §6 SESSION LOG and
advance `build_queue.jsonl` + `HANDOFF.md`.

---

## Cross-references
- [`MULTI_LLM_PROTOCOL.md`](MULTI_LLM_PROTOCOL.md) — the §3 handoff block + authority hierarchy these prompts live inside.
- [`ISSUE_TRACKING_PLAYBOOK.md`](ISSUE_TRACKING_PLAYBOOK.md) — conversation-diff → `build_queue.jsonl` story modeling.
- [`docs/architecture/trigger-vocabulary.md`](../docs/architecture/trigger-vocabulary.md) — `Orient`/`Map`/`Implement`/`Validate`.
- `CLAUDE.md §3` (how to add a feature) · `§6` (SESSION LOG) · `§6.5` (no silent config defaults) · `§13` (this layer).
