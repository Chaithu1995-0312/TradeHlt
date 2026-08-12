# multi_llm/ISSUE_TRACKING_PLAYBOOK.md — Conversation-Diff → Story Modeling

> **What this is.** A prompt chain for turning two long multi-LLM conversations into trackable,
> auditable work items. It exists because the multi-LLM workflow produces *parallel transcripts*
> (the same task discussed by different models) and we need a disciplined way to extract the real,
> actionable differences and file them.
>
> **The one-queue rule (read first).** The issues this chain produces are **appended to the
> existing single backlog `build_queue.jsonl` as candidate `STORY-*` records** — never to a
> parallel Jira/tracker. This is the protocol's anti-drift "one queue" rule and the §6.2 rule-4
> append-discipline (preserve history; never silently delete). "Jira" here is a *modeling format*,
> not a second system of record.
>
> **Authority.** Advisory only — grants no new authority (CLAUDE.md §6.5 / §13). A modeled issue is
> a *candidate* story; it becomes real work only when the **User = Bridge** approves it into the
> queue, and it earns no production authority until it demonstrates G001 improvement (Authority
> Ladder, §6.5).

---

## The chain (4 prompts)

```
Transcript A ─┐
              ├─► (1) Summarize ─► (2) Compare (strict diff) ─► (3) Ambiguity-Resolve ─► (4) Model as STORY-* ─► append to build_queue.jsonl
Transcript B ─┘
```

### 1 · Summarize — clean each transcript
**Owner:** ChatGPT (Interpreter). Run once per transcript before comparing.

```
You are the Interpreter (ChatGPT role). You are given a long technical conversation.
Produce a cleaned, final technical reference by REMOVING: code-generation meta-instructions,
confirmations/fluff, over-explanation of already-covered basics, redundant diagrams/tables
(keep the most complete), and non-technical wrapper text.
PRESERVE: all specs (schemas/architectures/algorithms), code snippets, failure modes,
self-review points, and the emergent design's logical structure.
Output: one well-organized technical document.
```

### 2 · Compare — strict literal diff
**Owner:** Gemini (Navigator). Pure observation, no interpretation.

```
You are the Navigator (Gemini role). You are a strict comparison engine.
Input: Conversation A and Conversation B (cleaned).
Output ONLY the factual differences. Do NOT interpret, summarize, assume, or hallucinate.
- State each difference literally, using exact wording where possible.
- Note content present in one but not the other; note turn-order differences; note metadata diffs.
Format: a flat bullet list, one raw observation per line. No intro/outro.

Conversation A: [PASTE]
Conversation B: [PASTE]
```

### 3 · Ambiguity-Resolve — make each difference implementable
**Owner:** DeepSeek (Planner).

```
You are the Planner (DeepSeek role). Input: the strict diff list from step 2.
For each difference:
1. Identify the ambiguity (missing definition, unspecified default, open choice, contradiction).
2. Resolve it with a concrete, implementation-ready decision (default / formula / algorithm / spec)
   and a one-line rationale; on conflict, choose the more robust option or a unified approach.
Output: grouped, structured resolutions usable directly as an implementation reference.
```

### 4 · Model as candidate stories
**Owner:** DeepSeek (Planner) drafts; **User = Bridge** approves into the queue.
Emit one record per distinct, resolved difference, in the **existing `build_queue.jsonl` schema** —
*not* a free-form Jira object:

```json
{ "id": "STORY-<epic>.<n>", "epic": <int>, "epic_title": "<bucket>",
  "title": "<short action-oriented summary>",
  "status": "pending", "confidence": <0-100>,
  "files": ["path/to/file.py"], "depends_on": ["STORY-x.y"] }
```

Modeling rules:
- **One difference → one record.** Split a compound difference; if records are parent/child, encode
  the order via `depends_on`.
- **Traceability lives in the turn ledger, not the record.** Reference the source transcripts by
  `turn_ledger.jsonl` `turn_id` / `cycle_id` rather than pasting snippets — keep the queue line thin.
- **Verification = acceptance criteria** become the I-3 TestGen targets in
  [`PROMPT_PLAYBOOK.md`](PROMPT_PLAYBOOK.md) Phase 3.
- **Append, don't rewrite.** Add lines to `build_queue.jsonl`; never delete or renumber existing
  stories (§6.2 rule 4). Re-validate ids against `tests/test_handoff_state.py` (STORY refs must
  resolve; no duplicate ids).

---

## Cross-references
- [`PROMPT_PLAYBOOK.md`](PROMPT_PLAYBOOK.md) — GATHER/ENHANCE/IMPLEMENT prompts that *execute* a modeled story.
- [`MULTI_LLM_PROTOCOL.md`](MULTI_LLM_PROTOCOL.md) — one-queue / authority-hierarchy / anti-drift rules.
- `build_queue.jsonl` — the single backlog these stories land in (seeded by `scripts/context/seed_build_queue.py`).
- `CLAUDE.md §6.2` (append-discipline / minimize doc count) · `§6.5` (Authority Ladder) · `§13` (this layer).
