# Plan: Multi-LLM Coordination Layer (Track 3) → driving the Domain-First Refactor (Track 1)

## Context

You run four LLMs by hand — DeepSeek (planner), Gemini (navigator), ChatGPT (interpreter), Claude
(executor) — and the real, felt pain is **context drift**: each model accumulates private
assumptions until you have "4 independent realities" and contradictory architectures. The ChatGPT
"Project OS" thread proposes a large fix (context compiler, portable mind, role files, handoff
protocol, documentation compiler, cognitive domains, session manager).

**Decision (yours):** build the multi-LLM layer **first** (Track 3), then execute the
`FULL_BUILD_SPECIFICATION.md` domain-first refactor (Track 1) **driven through** that multi-LLM
workflow.

**Key finding that shapes this plan:** an Explore pass confirmed ~90% of the proposed "Project OS"
**already exists** in this repo under other names. So this plan builds **only the genuinely-absent
~10%** and wires it to the abundant existing substrate — it does **not** rebuild what's there.
This respects CLAUDE.md §6.2 (existing-doc-first, minimize doc count, zero silent truth divergence)
and §6.1's "no premature framework" guardrail.

### Already exists — DO NOT rebuild (derive from / point to these)
| Capability | Existing source of truth |
|---|---|
| Canonical memory / context | `CLAUDE.md`, `MEMORY.md`, `assistant_project.md`, `docs/knowledge-map.md` |
| Findings registry | `docs/current-findings.md` + CLAUDE.md Repository Truths Index (`tests/test_current_findings.py`) |
| Impact-driven doc compiler | `gen_citation_map.py`, `gen_code_map.py` + `tests/test_doc_citations.py`, `tests/test_topic_docs.py` |
| Session manager | `assistant_project.md` SESSION LOG + `tests/test_session_log.py` + rotation + commit-hook |
| Cognitive domains | `docs/intent/` (7), `docs/topics/` (26), `docs/architecture/` (22) |
| Dependency/intent map | `docs/architecture/code-map.generated.md`, `docs/intent/*`, `module-roles.generated.md` |
| Active runtime truth | `configs/production/ACTIVE_VERSION` + §4.0 precedence |

### Genuinely absent — what we build
1. **Role files** (frozen, hand-authored): what each model owns.
2. **Handoff protocol** (one doc): the mandatory response structure + authority hierarchy.
3. **Context compiler** (one script): regenerates a small set of *portable context files* **from**
   the canonical sources above — the "Portable Mind" you upload to any model.
4. **Live handoff state + build queue**: `HANDOFF.md` (current actor / next actor) and a
   machine-readable story queue seeded from `FULL_BUILD_SPECIFICATION.md` — the bridge to Track 1.

---

## Track 3 (build now)

### Phase A1 — Static authored docs (no code)
Create `multi_llm/` at repo root (discoverable; these are meant to be grabbed and uploaded):

- `multi_llm/MULTI_LLM_PROTOCOL.md` — the mandate. Mandatory response block for **every** model
  (`CURRENT_TASK`, `NEXT_10_STEPS`, `CONTEXT_DELTA`, `FOR_NEXT_MODEL`, `PROMPT_FOR_NEXT_MODEL`,
  `CONFIRMATION`); the flow `DeepSeek→Gemini→ChatGPT→Claude→Tests/Findings→Gemini`; the **Authority
  Hierarchy** (`Reality > Tests > Findings > Repository > Shared Context > LLMs`) — tied to CLAUDE.md
  §6.5 Authority Ladder so it doesn't become a competing doctrine.
- `multi_llm/roles/ROLE_DEEPSEEK.md`, `ROLE_GEMINI.md`, `ROLE_CHATGPT.md`, `ROLE_CLAUDE.md` — frozen
  responsibilities (Planner / Navigator / Interpreter+ParameterExpansion / Executor). `ROLE_CLAUDE.md`
  must restate the non-negotiables it already lives under: §6 SESSION LOG, write-authority/path-guard,
  promotion gate, no silent config defaults (§6.5).
- `multi_llm/README.md` — index + "how to run a cycle" + explicit "these files are the *protocol*;
  the *truth* lives in the repo" statement.

### Phase A2 — Context compiler (code, mirrors `gen_citation_map.py`)
- `scripts/context/build_context.py` — **stdlib-only, deterministic, `--check` mode**, every output
  stamped `GENERATED — do not edit · regenerate with python scripts/context/build_context.py`. It
  reads canonical sources and writes portable files to `context/`:
  - `context/01_GLOBAL_CONTEXT.md` ← CLAUDE.md §1/§4/§6.x doctrines + `docs/architecture/goal.md`
  - `context/02_CURRENT_STATE.md` ← `configs/production/ACTIVE_VERSION` + current branch + latest N
    SESSION LOG entries + `NEXT_10_STEPS` (from the build queue, A3)
  - `context/03_FINDINGS.md` ← `docs/current-findings.md` non-terminal findings + Repository Truths Index
  - `context/04_DEPENDENCY_AND_INTENT.md` ← `code-map.generated.md` summary + `docs/intent/*` titles
  - `context/05_HANDOFF.md` ← role-file summaries + protocol summary + current `HANDOFF.md` state
- `tests/test_context_compiler.py` — mirrors `tests/test_doc_citations.py`: (a) compiler runs and all
  source paths resolve, (b) outputs non-empty, (c) **determinism** (run twice → byte-identical), (d)
  **no hand-edit drift** (regenerate and diff against committed `context/*.md`, like the citation-map
  freshness check), (e) header stamp present on every generated file.

### Phase A3 — Live handoff state + build queue (the bridge to Track 1)
- `HANDOFF.md` (repo root) — small hand/compiler-merged state: `current_actor`, `current_story`,
  `completed`, `blocked`, `next_actor`, `next_prompt`. This is the working-memory file passed between models.
- `data/build_queue.jsonl` — append-only story queue **seeded from `FULL_BUILD_SPECIFICATION.md`**
  (one line per story: `id`, `epic`, `title`, `status`, `confidence`, `files`, `depends_on`). Matches
  the repo's JSONL convention. Feeds `NEXT_10_STEPS` in `context/02_CURRENT_STATE.md`.
  - `scripts/context/seed_build_queue.py` — one-time parser of the spec's epic/story tables → JSONL.

### Phase A4 — Minimal CLAUDE.md wiring (one entry, not a new doctrine)
- Add a single short section (e.g. CLAUDE.md §13 "Multi-LLM Layer") + a `Compile` trigger to §12
  Trigger Vocabulary pointing at `multi_llm/` and `scripts/context/build_context.py`. Keep it thin —
  the detail lives in `multi_llm/`, per minimize-doc-count.

---

## Track 1 (after Track 3, executed *through* the multi-LLM workflow)

Once A1–A4 exist, the operating loop becomes: compile `context/*.md` → hand to DeepSeek/Gemini/ChatGPT
for the next story's plan/gaps/explanation → **Claude executes** the story → tests+findings decide →
regenerate context → advance the queue. The first stories to run are `FULL_BUILD_SPECIFICATION.md`
**Epic 1 (repair the spine — fix the 23 failing tests)**, because nothing downstream is trustworthy
on a broken foundation (F-010/trust-layer discipline). **Not planned in detail here** — each epic
gets planned as it surfaces in the queue. The F-001 / Program-1 tension (don't over-invest in
tooling vs. the real binding constraint) is carried as an explicit gate before Epics 4–10.

---

## File inventory
```
NEW  multi_llm/MULTI_LLM_PROTOCOL.md
NEW  multi_llm/README.md
NEW  multi_llm/roles/ROLE_DEEPSEEK.md
NEW  multi_llm/roles/ROLE_GEMINI.md
NEW  multi_llm/roles/ROLE_CHATGPT.md
NEW  multi_llm/roles/ROLE_CLAUDE.md
NEW  scripts/context/build_context.py        (mirrors scripts/analysis/gen_citation_map.py)
NEW  scripts/context/seed_build_queue.py
NEW  tests/test_context_compiler.py          (mirrors tests/test_doc_citations.py)
NEW  HANDOFF.md
NEW  data/build_queue.jsonl                   (generated by seed_build_queue.py)
NEW  context/01_GLOBAL_CONTEXT.md ... 05_HANDOFF.md   (generated by build_context.py)
MOD  CLAUDE.md                                (+§13 + one Compile trigger; thin)
```

## Conventions to follow (reuse, don't invent)
- Context compiler = stdlib-only + deterministic + `--check` + GENERATED header — copy
  `scripts/analysis/gen_citation_map.py` structure exactly.
- Generated-file freshness test = copy `tests/test_doc_citations.py` regenerate-and-diff approach.
- JSONL append-only for `build_queue.jsonl` — same discipline as `promotion_log.jsonl`.
- Windows console output through `src/utils/console_safe.py` if the scripts print non-ASCII.
- Append the §6 SESSION LOG entry on every implementation turn (the layer must obey, not bypass, it).

## Verification
1. `python scripts/context/seed_build_queue.py` → inspect `data/build_queue.jsonl` (44 stories present).
2. `python scripts/context/build_context.py` then `--check` again → byte-identical (determinism).
3. `pytest tests/test_context_compiler.py -v` → all green (resolve, non-empty, determinism, no-drift, header).
4. `pytest` full suite → no new reds introduced (purely additive layer).
5. Manual: open `context/*.md` — confirm each is a faithful *derived view* of its source, not a fork,
   and small enough to paste into an external model.

## Out of scope / deferred
- The 44-story refactor itself (Track 1) — planned per-epic as the queue advances; Epic 1 first.
- ChatGPT's "impact-driven documentation compiler" and "cognitive-domain context bundles" — already
  covered by existing citation/topic/code-map machinery; not rebuilt.
- Any n8n / Claude-API gate (Epics 6–7 of the spec) — far downstream, behind the F-001 gate.
- Automating LLM-to-LLM calls — the human stays the bridge for now (matches the proposal).
