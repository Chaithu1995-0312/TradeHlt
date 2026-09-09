# PROMPT_FOR_CHATGPT

Cycle: `RC-002` · Generated: 2026-09-03T23:07:27Z

**Paste this prompt + CONTEXT_BUNDLE.md into chatgpt.**

Output must update `multi_llm/research_lane/proposals/chatgpt/RC-002/DECISION.md` content (return full filled PROPOSAL markdown).

---

## RC-002 · Architect · package kind = `DECISION` (draft only)

**Model:** `chatgpt`
**Research role:** `architect`
**author_role:** `architect`

**Role-specific instruction:**
Architect the next research cycle: prioritize phases, freeze criteria, and what to send critic/executor. No code.


You are the **fourth and last model** actor in cycle `RC-002`. Three packages precede
you and will be pasted in alongside this prompt:

- DeepSeek `CRITIQUE` — is the Phase 4g retraction sound?
- Grok `PROPOSAL` — candidate identities for the population.
- Gemini `CRITIQUE` — does the base-rate control license the conclusion?

### The one thing you produce — and only this one

**A draft `DECISION` that closes the semantic review with exactly one verdict.**

`SEMANTIC_REVIEW_PROTOCOL.md` is in your bundle. It requires a review to close with **exactly
one** of these ten, and forbids saying "bug" without naming the violated contract:

`CONFIRMED DEFECT` · `INTENTIONAL SEMANTIC SEPARATION` · `STALE / LEGACY ARTIFACT` ·
`COMPATIBILITY ARTIFACT` · `DEFENSE-IN-DEPTH OPPORTUNITY` · `TEST / CONTRACT GAP` ·
`DOCUMENTATION GAP` · `DORMANT BUT VALID` · `INSUFFICIENT EVIDENCE` ·
`USER AUTHORIZATION REQUIRED`

It also binds you to: `different != wrong` · `unreachable != bug` · `configured != must be
reachable` · `absent != defective` · `current != correct`. And it forbids collapsing
**CURRENT** (what the code does) / **INTENDED** (what it should mean) / **RECOMMENDED** (what
to do) into one statement.

Your draft must state, separately and explicitly:

1. **The one verdict**, with the contract it names (F-074? the ontology? neither?).
2. **What becomes of Position B** — exactly one of: `STANDS` · `NARROWS` (say to what) ·
   `SUPERSEDED` (say by what) · `INSUFFICIENT EVIDENCE`.
3. **Whether the three input packages agree or conflict**, and — critically — **if they
   conflict, surface it as a `TruthConflict` (source A, source B, evidence, impact,
   recommendation) and do NOT pick a winner.** You are not a tie-breaker.
4. **What the Principal is actually being asked to decide**, in one sentence.

### Hard constraints

- **You are not voting and not tallying.** Three packages of three different kinds are not
  three votes. If two models happen to agree, that is not evidence; say so if it is relevant.
- **Your DECISION carries no authority.** It is a draft for the Principal, who is the only
  actor who can issue the binding DECISION. Mark it `status: PROPOSED`, never `ACCEPTED`.
- **Do not** propose an implementation, a `CRTState`, a `when:` predicate, or code. If your
  verdict implies future work, name it as a *separately-authorized future turn*, not a plan.
- **Do not** reverse F-074, edit an ontology, or change a promise rung. **PL-0** stands.
- If a needed fact is absent from the dossier and the three packages, write `UNKNOWN:`.

### Output

Return the **complete filled** `DECISION` markdown for `multi_llm/research_lane/proposals/chatgpt/RC-002/DECISION.md`, using the
template's sections (decision type · evidence cited by package_id · decision text · next
actor / next grant). Under "Decision type" you will most often be selecting `REPAIR`,
`RETIRE`, or none-of-the-above — say plainly if none fits.

Focus: close with exactly one verdict; all three upstream packages are IN your bundle
