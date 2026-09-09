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

---
📝 SESSION LOG ENTRY
Date: 2026-09-04
Topic: Lane R cycle RC-002 opened — role-separated relay for the Position B ambiguity (workflow dimension)
Decision/Output: Routing designed against `RESEARCH_ROLES.md`'s binding rule ("same problem -> different roles -> different package kinds; never four models answer the same prompt and vote"): DeepSeek `CRITIQUE` (attack the retraction, FIRST so a defective retraction kills the cycle cheaply) -> Grok `PROPOSAL` (identity candidates) -> Gemini `CRITIQUE` (statistics only) -> ChatGPT `DECISION` draft (one of ten §6.8 verdicts, `status: PROPOSED`, explicitly not a tie-breaker) -> Principal binds. Each prompt forbids answering another model's question. RC-001 recorded as a STALLED cycle (stubs written 2026-07-14, never filled) — not reused. HANDOFF.md advanced to `current_actor: Claude` / `next_actor: DeepSeek`, which also turned a pre-existing red floor green. Scorecard RC-002 column opened. Grok's missing `_ROLES` seat routed around, not patched. Codebase dimension (the `initiate_plan.py` change + the base-rate control) logged in `assistant_project.md` — not duplicated here per §6.
Belief Update / ROI / Goal: Goal: resolve an identity question measurement cannot settle. Belief: the relay's value is role SEPARATION, not model count — the tool's PROPOSAL-only limitation was quietly pushing every cycle toward the banned voting shape. Knowledge ROI: medium-high. Action: bridge in order; watch for any model answering another's question.
Open Questions: whether Grok gets a real `_ROLES` seat or stays ledger-only.
Next Step: DeepSeek turn 1; capture verbatim via `log_turn.py --actor deepseek --story RC-002`.
---

---
📝 SESSION LOG ENTRY
Date: 2026-09-04
Topic: RC-002 turn 1 workflow - the critic seat paid for itself on its first package (D-19)
Decision/Output: DeepSeek returned `RC-002-CRIT-DEEPSEEK-001` (CRITIQUE, PL-0). Executor adjudicated by MEASUREMENT rather than deference (section 13.8: advice is non-binding, evidence settles) - defects #1/#2 CONFIRMED, #3 confirmed as a consequence, #4 accepted with one narrowing ("selective reporting" does not fit: the vacuous statistic was published as withdrawn in the dossier before the critique existed). Recommendation REPAIR executed same turn across dossier, config blocker, memory, and plan file. **Gemini's prompt was re-scoped mid-cycle** because turn 1 answered its original question - a live demonstration that role separation, not model count, is what the relay buys: had all four models received the same prompt, three would now be reasoning from a dead statistic. Ledger 8 lines schema-valid; scorecard D-19 row now reads 2 confirmed blocking defects / 3 spec changes, so the keep/drop rule's "0 defects -> lighter critic" branch does not apply. Codebase dimension logged in `assistant_project.md`.
Belief Update / ROI / Goal: Goal: resolve an identity question without contaminating it. Belief: CONFIRMED that ORDERING matters as much as separation - putting the critic FIRST was the design decision that saved the cycle; a critic placed last would have invalidated three completed turns. Knowledge ROI: high. Action: regenerate Grok's bundle against the corrected dossier before bridging turn 2.
Open Questions: whether Gemini's re-scoped question is now the cycle's most valuable turn, ahead of Grok's.
Next Step: Grok turn 2 on the corrected dossier; capture via `log_turn.py --actor grok --story RC-002`.
---

---
📝 SESSION LOG ENTRY
Date: 2026-09-04
Topic: RC-002 turn 2 workflow — Grok PROPOSAL filled (identity, not a vote)
Decision/Output: Grok returned `RC-002-PROP-GROK-001` (`proposals/grok/RC-002/PROPOSAL.md`). Role held: hypothesis_diversity only — did not attack DeepSeek's critique, did not design Gemini's test, did not draft ChatGPT's verdict, did not rule on Position B, did not ratify `SweepReversal`. Five identity candidates with a single shared falsifier (same-side extension of held sweep extreme). Honest default remains UNKNOWN. `log_turn.py --actor grok` cannot run (`src/multi_llm/turn_ledger.py` `ROLES` = DeepSeek/Gemini/ChatGPT/Claude); package is carried by `research_cycle_ledger.jsonl` (now 9 lines) as the cycle README already routed. HANDOFF.md not updated (Grok has no `_ROLES` seat; `test_handoff_state.py` would go red). Codebase dimension (the filled PROPOSAL + rotation) logged in `assistant_project.md`.
Belief Update / ROI / Goal:
  Goal: resolve an identity question without contaminating the remaining turns.
  Belief: turn 2 did what the seat is for — alternative identities that do not reuse dead names — and stopped at recommendation. The critic-first ordering still looks right: Grok reasoned from UNKNOWN, not from the withdrawn "resumption" reading.
  Knowledge ROI: medium-high. Diversity package exists; it is not evidence.
  Action: bridge Gemini (turn 3, re-scoped CRITIQUE). Watch for any model answering Grok's identity question or treating these five names as votes.
Open Questions: whether Gemini's discriminating-test design can be constructed without `sweep.price` on the 32-bar artifact.
Next Step: User pastes `proposals/gemini/RC-002/PROMPT_FOR_GEMINI.md` + that folder's CONTEXT_BUNDLE.md. Do not paste Grok's PROPOSAL into Gemini as a prompt (cycle README: ChatGPT is the only turn that sees 1-3).
---


---
📝 SESSION LOG ENTRY
Date: 2026-09-04
Topic: RC-002 closed model-side - what the relay actually bought, measured against its own keep/drop rule
Decision/Output: Four role-separated turns plus one re-run. **Measured value (scorecard D-19):** 2 confirmed blocking defects from the critic seat, 4 spec changes forced by valid critique, 3 genuinely new hypotheses from the diversity seat, and a verdict that CHANGED when the composing turn finally received its inputs. **Two of the executor's own claims were killed before they reached an ontology decision** - one by DeepSeek (selection-induced circularity, headline statistic p 4e-07 -> 0.574), one by the executor's own disclosed control (the no-flip statistic, p=0.826). **Two process defects were found in the harness itself:** a ledger id collision when the executor scribe-filed a package whose author had already filed one (rule adopted: when the author files their own record, the executor files EVIDENCE, not a copy), and a composing turn that ran without its inputs because the requirement lived in PROSE rather than in the bundle (fixed at the manifest - the same silent-gap class as F-056/F-079/F-083/F-085, reproduced in my own harness). **Ordering mattered as much as separation:** the critic first saved the cycle; a critic last would have invalidated three completed turns. **The re-run was worth it and I argued against it** - I recommended binding v1 directly on the grounds that the verdict was robust; it was not. Codebase dimension logged in `assistant_project.md`.
Belief Update / ROI / Goal: Goal: know whether this relay earns its operating cost. Belief: CONFIRMED it does, on this cycle, on measured criteria rather than impression - the keep/drop rule's "0 blocking defects -> lighter critic" and "no EXECUTION_EVIDENCE -> LLM theater" branches both fail to trigger. Knowledge ROI: high. Action: keep the four-seat structure; keep critic-first ordering; never again put a turn's required inputs in prose instead of its bundle.
Open Questions: whether Grok deserves a real `_ROLES` seat (it produced the cycle's most original content and cannot legally be named `next_actor`).
Next Step: Principal binds RC-002; no model actor has pending work.
---
