# Plan — Add `BLOCKED_ON_EVIDENCE` primitive to the multi-LLM protocol

## Context
A multi-round adversarial review (ChatGPT ↔ Claude, User bridging) of a large ChatGPT proposal
(~20 new doctrine/protocol/MT5 files) collapsed, by full convergence, to a **single genuine delta**.
MT5 is explicitly out of scope. Evidence (read-only verified) showed 4 of ChatGPT's 5 "strong keeps"
already exist in the repo:
- Role specialization → `multi_llm/roles/ROLE_*.md` + CLAUDE.md §13.2
- User bridge → `roles/ROLE_USER.md` + `MULTI_LLM_PROTOCOL.md` §1/§4
- Information-flow discipline → `MULTI_LLM_PROTOCOL.md` §3 response block + §5 anti-drift
- Zero-assumption / anti-fabrication → §5 rule 4 + CLAUDE.md §13.3 E-3 "Uncertainty Guard" + §4.0 + E-001

The **only** primitive genuinely absent is a named, structured halt for when a required fact is
*absent* — distinct from `# UNKNOWN:` (uncertain, §13.3 E-3) and `TruthConflict` (two artifacts
disagree, §6.2 rule 3). Without it the failure path is: missing fact → inference → plausible
reasoning → hallucination. With it: missing fact → STOP → bridged evidence request → resume.

**Decision (User + ChatGPT converged):** surgical edit only. **Reject** `CONSTITUTION.md` (new file,
§6.2 rule 5), **reject** `CLAUDE.md §14` (always-loaded bloat, duplicates §13/§6.2/protocol). Goal:
maximum epistemic gain, near-zero entropy.

## The change (one edit, one file)
Append **anti-drift rule 6** to `multi_llm/MULTI_LLM_PROTOCOL.md` §5 (currently ends at rule 5,
line ~132). Existing-doc-first (§6.2 rule 1). No new files. Proposed text:

```
6. **Blocked on evidence.** When a required fact is *absent* — not merely uncertain (that's the
   `# UNKNOWN:` Uncertainty Guard, CLAUDE.md §13.3 E-3), and not two artifacts *conflicting* (that's
   a `TruthConflict`, §6.2 rule 3) — and any conclusion would therefore be speculative, the model
   **stops and emits a `BLOCKED_ON_EVIDENCE` block instead of inferring.** It does not advance the
   pipeline; the User (bridge) routes the request to the named model and returns the evidence before
   reasoning resumes. Grants no authority — it is a halt, not a decision.

   ```
   BLOCKED_ON_EVIDENCE
   Reason:                <why reasoning cannot continue>
   Required Evidence:     <the specific artifact needed — file:line, test result, config value…>
   Target Model:          <who can produce it: Claude=code/tests · ChatGPT/Gemini=analysis · User=external>
   PROMPT_FOR_NEXT_MODEL: <copy-paste request that returns exactly that evidence>
   Blocked Conclusions:   <what stays unstated until the evidence arrives>
   Status:                WAITING
   ```
   This reuses the §3 handoff fields (`Target Model` ↔ `FOR_NEXT_MODEL`; `PROMPT_FOR_NEXT_MODEL`):
   it is an *exception path* on the existing block, not a new mechanism.
```

**Critical file:** `multi_llm/MULTI_LLM_PROTOCOL.md` (§5, after line ~132).

## Obligations triggered by touching `multi_llm/` (CLAUDE.md §13.7 + §6)
- Emit the §3 handoff block (`CURRENT_TASK / NEXT_10_STEPS / CONTEXT_DELTA / FOR_NEXT_MODEL /
  PROMPT_FOR_NEXT_MODEL / CONFIRMATION`) in the implementing turn.
- Keep `HANDOFF.md` valid/consistent.
- Append a `📝 SESSION LOG ENTRY`. Routing (§6 tie-breaker): primary dimension is workflow/protocol →
  `llm_project_assistant.md`, with a one-line cross-link in `assistant_project.md` (satisfies the
  commit hook + `test_session_log.py`). Confirm routing at implement time.

## Verification
1. **Citation drift:** check `docs/architecture/citation-map.generated.md` for any `MULTI_LLM_PROTOCOL.md:§5`
   line-anchored citation; appending at the end of §5 shifts nothing above it, but confirm (`test_doc_citations.py`, ±30-line window).
2. **Run the guard tests** (no behavior change expected — doc-only additive edit):
   `python -m pytest tests/test_handoff_state.py tests/test_context_compiler.py tests/test_session_log.py tests/test_llm_project_assistant_log.py -q`
3. **Manual read-through:** the new rule 6 reads consistently with rules 1–5 and the §3 field names.
4. No config/code touched → no rehash, no determinism/oracle run needed.

## Out of scope (explicitly rejected this thread)
MT5 platform work; `CONSTITUTION.md`; `CLAUDE.md §14`; per-model `*_SYSTEM_PROMPT.md`; any new
findings registry / intelligence-promotion files; the Postgres/Kafka/Redis stack (violates §1
file-backed constraint). The "promote F-001" instruction was an id collision (F-001 is taken) and
is dropped; no finding is created — this is an orchestration-convenience rule, not an evidence claim.
```
