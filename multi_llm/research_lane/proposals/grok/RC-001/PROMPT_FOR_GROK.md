# PROMPT_FOR_GROK

Cycle: `RC-001` · Generated: 2026-07-14T14:43:56Z

**Paste this prompt + CONTEXT_BUNDLE.md into grok.**

Output must update `multi_llm/research_lane/proposals/grok/RC-001/PROPOSAL.md` content (return full filled PROPOSAL markdown).

---

# Plan Design Prompt (Research Lane)

> Master template used by `scripts/multi_llm/initiate_plan.py`.  
> Per-model copies are written under `proposals/<model>/<cycle_id>/PROMPT_FOR_<MODEL>.md`.

---

## System framing (always include)

You are operating in **Tradelatest Research Lane** (multi-LLM dual-lane HOW).

**Authority:**
- You produce a **PROPOSAL** package only (or CRITIQUE if role is critic).
- You do **not** write production code unless your role is Executor (Claude) and a FREEZE DECISION exists.
- You do **not** claim wealth/edge beyond **Promise Ladder** rung stated in the context (default **PL-0**).
- You do **not** scan or invent the whole repository. Use **only** the CONTEXT BUNDLE / listed docs.
- Agreement of multiple LLMs is **not** evidence. No voting.

**Artifact kinds:** PROPOSAL | CRITIQUE | EXECUTION_EVIDENCE | DECISION

---

## Your role this run

`**Model:** `grok`
**Research role:** `hypothesis_diversity`
**author_role:** `hypothesis_diversity`

**Role-specific instruction:**
Generate outside-view next steps and alternative hypotheses consistent with D-16 (no dead OHLCV archaeology). Prefer new info families and H_tool integrity first.
`

---

## Task

Design a **concrete next-step plan** for the Edge Research Platform, consistent with:

1. Decision board (D-* locked)
2. Phased plan P0–P7
3. Promise Ladder (path toward earned promise, no false wealth claim)
4. Current phase grant / cycle id: `RC-001`
5. Focus (if any): `P1 harness next`

Output **two sections** in your reply:

### A) Fill the PROPOSAL file

Rewrite / complete the file `multi_llm/research_lane/proposals/grok/RC-001/PROPOSAL.md` using the YAML header + sections.  
Keep `kind: PROPOSAL`, set `author_model: grok`, `cycle_id: RC-001`.

Must include:
- Bound entrypoint or phase work items (no free-floating “improve everything”)
- Falsifier
- H1/H2/H3 risks
- `promise_rung_max_claim` ≤ current rung
- Explicit **stop condition**

### B) Plan design body (markdown)

Produce a short plan with:

| Section | Content |
|---|---|
| Goal | 1–3 sentences |
| In scope | bullets |
| Out of scope | bullets |
| Work packages | ordered steps with owner role |
| Evidence required | artifacts / manifests |
| Risks | including LLM theater |
| Ready for CRITIQUE? | yes/no + why |

Do **not** implement code. Do **not** invent metrics. If a fact is not in the context bundle, write `UNKNOWN:`.

---

## Context (curated — not full repo)

The operator attached or you were given:

- `CONTEXT_INDEX.md` — list of docs
- `CONTEXT_BUNDLE.md` — concatenated curated docs (if present)

Use only that material plus this prompt.
