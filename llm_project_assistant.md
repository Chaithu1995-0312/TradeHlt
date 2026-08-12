<!-- ============================================================= -->
<!-- MULTI-LLM WORKFLOW LOG — keep this doctrine block at the top.  -->
<!-- Companion to the machine record multi_llm/turn_ledger.jsonl.   -->
<!-- ============================================================= -->

# MULTI-LLM WORKFLOW LOG

> **This file tracks the multi-LLM *workflow*, not the codebase.** It is the human-readable
> narrative of how DeepSeek / Gemini / ChatGPT / Claude (coordinated by the User) collaborate:
> handoff cycles, cross-model coordination decisions, protocol/role/queue evolution, and
> discussion-level meta.
>
> **Split rule (CLAUDE.md §6 "Two logs — route by dimension").**
> - Codebase / engineering / research work (code, config, findings, backtests, tooling builds) →
>   [`assistant_project.md`](assistant_project.md).
> - Multi-LLM workflow *operation* (this file).
> - Tie-breaker: a change to governed code/config/findings logs to `assistant_project.md` (the
>   commit-hook needs it there); workflow-only logs here; genuinely both → primary dimension + a
>   one-line cross-link (no duplicate full entries, §6.2).
>
> **Companions:** machine per-turn record = `multi_llm/turn_ledger.jsonl`; rewind the thread with
> `python scripts/context/discussion.py --full|--rewind <turn>|--digest`. Same `📝 SESSION LOG
> ENTRY` block format as `assistant_project.md`; bounded by
> `python scripts/maintenance/rotate_session_log.py --file llm_project_assistant.md`.
> Governed by [`CLAUDE.md`](CLAUDE.md) §6 + §13.
---

---
📝 SESSION LOG ENTRY
Date: 2026-06-15
Topic: Workflow log established — split codebase tracking (assistant_project.md) from multi-LLM workflow (this file)
Decision/Output: Owner directive: assistant_project.md must hold ONLY codebase tracking; the multi-LLM workflow/conversation gets its own file. Created llm_project_assistant.md (this file) as the workflow log — human-readable companion to the machine multi_llm/turn_ledger.jsonl + discussion.py rewind. Added the routing rule to CLAUDE.md §6 ("Two logs — route by dimension") + §13 pointer. Generalized scripts/maintenance/rotate_session_log.py with --file (default assistant_project.md unchanged; other logs archive to docs/analysis/<stem>-archive with a <stem> prefix) so ONE rotator bounds both. Added tests/test_llm_project_assistant_log.py (structural floor mirroring test_session_log.py). The commit-hook (check_session_log_commit.py) is unchanged — governed code/config still requires a codebase-log entry. Forward-only: existing history stays in assistant_project.md (§6.2 append-discipline).
Belief Update / ROI / Goal: Goal: keep each log single-purpose so the codebase audit trail isn't diluted by workflow chatter (and vice-versa). Belief: the split is cleanly additive because enforcement was already scoped — test/rotation hard-target assistant_project.md and the commit-hook only fires on governed paths. Knowledge ROI: medium — clearer separation of concerns; the workflow narrative now has a home distinct from the engineering record and from the machine turn ledger. Action: route workflow-dimension entries here going forward.
Open Questions: Should the workflow log eventually be partly generated from turn_ledger.jsonl (currently hand-written, complementary)? Cap/keep value for workflow-log rotation (default 20).
Next Step: Per HANDOFF.md → Gemini confirms STORY-1.1 + gaps before DeepSeek plans Epic 1; future workflow-cycle narrative lands here, codebase changes in assistant_project.md.
---

---
📝 SESSION LOG ENTRY
Date: 2026-06-15
Topic: Queue advance — STORY-1.1 executed (User-directed, no full model cycle run this turn)
Decision/Output: User directed Claude to execute STORY-1.1 directly (the DeepSeek→Gemini→ChatGPT pre-steps were not run as separate web turns this session — the User is operating Claude directly, which the protocol permits since the User is the principal). build_queue.jsonl STORY-1.1 status pending → done; HANDOFF.md next_actor = Gemini to re-confirm the live Epic-1 set. CODEBASE details (the actual fix + verification) are in assistant_project.md per §6 Two-logs (cross-link, not duplicated here).
Belief Update / ROI / Goal: Goal: keep the workflow log as the coordination/queue narrative, distinct from the engineering record. Belief: a User-directed direct execution is a valid cycle variant (principal authority, ROLE_USER.md). Knowledge ROI: low (bookkeeping) — but demonstrates the §6 routing in practice (code → codebase log; queue/coordination → here). Action: advance to the next Epic-1 story via Gemini.
Open Questions: none.
Next Step: Gemini re-confirms the live Epic-1 failing set + next story; or User directs the next direct execution.
---

---
📝 SESSION LOG ENTRY
Date: 2026-06-15
Topic: Mandate — Code & Execution Authority: Claude is the sole coder/executor in the codebase
Decision/Output: Per owner directive, encoded a non-optional mandate: CLAUDE.md §13 new sub-block "Code & Execution Authority" — only Claude writes/edits code + runs execution; DeepSeek/Gemini/ChatGPT are advisory (propose code as INPUT to Claude, never applied directly; no other model commits/runs spine/promotions). Reinforced in ROLE_CLAUDE.md (Owns: "sole coder/executor") + MULTI_LLM_PROTOCOL.md §2. Explicitly grants NO new authority — governs WHO implements, not WHAT is allowed; User approval + §6 gates (SESSION LOG, write-authority/path-guard, y/N, APPROVE) + Reality/Tests/Findings all still bind. The three advisory role files already said "Must NOT write code" — consistent. Doc-only (CLAUDE.md/protocol/role); not a governed src/config path → workflow log. Gates: doc_citations + context_compiler + handoff_state + topic_docs = 18 passed.
Belief Update / ROI / Goal: Goal: prevent role drift (other models silently producing/applying code). Belief: making "Claude implements, others advise" a written mandate closes the biggest multi-LLM failure mode (conflicting authority / undisciplined writes). Knowledge ROI: low-medium — formalizes existing practice into an enforceable-by-doctrine rule; the test floor stays on form (handoff/logs), the who-codes rule is doctrine (external models unenforceable, like the handoff mandate). Action: mandate live; continue Epic-1 execution as the sole executor.
Open Questions: none.
Next Step: Continue Track-1 Epic 1 (next real failing story) under the Code & Execution Authority mandate; HANDOFF → Gemini to re-confirm the set.
---

---
📝 SESSION LOG ENTRY
Date: 2026-06-15
Topic: Refined the Code & Execution mandate — advice is shared (all models incl. Claude recommend); only implementation is Claude-exclusive
Decision/Output: Owner clarification: it's not "others advise, Claude only implements" — Claude ALSO advises, and EACH LLM advises, as RECOMMENDATIONS (non-binding). Updated CLAUDE.md §13 Code & Execution Authority to "Implementation is Claude's alone; advice is everyone's": every model (DeepSeek/Gemini/ChatGPT + Claude) contributes non-binding recommendations; Claude is advisor + sole implementer; no model's advice — including Claude's own — is authority (User weighs, evidence settles). Mirrored in ROLE_CLAUDE.md ("Also advises (dual role)") + MULTI_LLM_PROTOCOL.md §2. Doc-only → workflow log. Gates: doc_citations + context_compiler + handoff_state + topic_docs = 18 passed.
Belief Update / ROI / Goal: Goal: prevent the mandate from over-narrowing Claude into a mute compiler. Belief: separating the two axes — IMPLEMENTATION (Claude-exclusive) vs ADVICE (shared, non-binding, everyone incl. Claude) — is the precise rule; it preserves Claude's reasoning value while keeping single-writer discipline and §6.5 (advice ≠ authority). Knowledge ROI: medium — sharpens the role model; aligns with the Authority Ladder (no LLM, not even the implementer, owns truth). Action: mandate finalized; proceed with Epic-1 execution.
Open Questions: none.
Next Step: Continue Epic 1 under the finalized mandate; HANDOFF → Gemini to re-confirm the live failing set.
---
