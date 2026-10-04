# PROMPT_FOR_DEEPSEEK

Cycle: `RC-002` · Generated: 2026-09-03T20:45:16Z

**Paste this prompt + CONTEXT_BUNDLE.md into deepseek.**

Output must update `multi_llm/research_lane/proposals/deepseek/RC-002/CRITIQUE.md` content (return full filled PROPOSAL markdown).

---

## RC-002 · Technical critic · package kind = `CRITIQUE`

**Model:** `deepseek`
**Research role:** `technical_critic`
**author_role:** `technical_critic`

**Role-specific instruction:**
Default: if a PROPOSAL already exists for this cycle from another model, produce a CRITIQUE-oriented plan of attacks (still fill PROPOSAL only if none exists; otherwise write your output into PROPOSAL as 'critic plan package' and note CRITIQUE next). Prefer finding leakage, H1/H2/H3, multiple-testing, and freeze defects.


You are the **first** actor in cycle `RC-002`. You go first deliberately: if the
retraction in §4 of the dossier is itself defective, every downstream turn is wasted.

### The one question you answer — and only this one

**Is the Phase 4g retraction sound, or is it an over-correction?**

The executing model (Claude) previously claimed these 32 bars were "sweep-then-reversal" with a
same-bar `trend_bias` flip. It has since measured that claim to be false and retracted it,
concluding instead that the population is *trend resumption after a counter-trend sweep*. Your
job is to attack **that retraction**, with the same rigour you would apply to the original
claim. A retraction is a claim.

Attack surfaces, at minimum:

1. **Selection.** The 32 bars were selected by a filter chain (675 -> 127 -> 88 -> 32). Does
   any step in that chain make the retraction's conclusion partly circular? Specifically:
   the population is *defined* as candles that moved against the founding sweep. Does that
   definition mechanically force `trend_bias` to look "already aligned"?
2. **The base-rate control (§5).** One statistic survived at p ~ 4e-07, one was withdrawn as
   vacuous. Is the surviving control the *right* control? Is the corpus-wide base rate the
   correct denominator, or does the qualifying-magnitude subpopulation (n=127) need its own?
3. **Power and scope.** n=32, one instrument, one 30-day window, one config epoch, no holdout.
   Is that enough to retract a decision? Is it enough to *sustain* one?
4. **Leakage / confounding.** `trend_bias` is `sign(ema_fast - ema_slow)` over a rolling window
   that includes bars before `t`. Is "already aligned at `t-1`" partly an artifact of the EMA
   window overlapping the move itself?
5. **Freeze defects.** Was anything measured after seeing an intermediate result, in a way that
   would not have survived pre-registration?

### Hard constraints

- **Do not** propose a name or an identity for the population. That is Grok's package.
- **Do not** propose an ontology change, a state, a transition, or a code change.
- **Do not** rule on whether Position B survives. That is the Principal's decision.
- **Do not** answer any question the dossier does not put to you.
- If you need a repository fact that is not in the dossier, write `UNKNOWN:` — never invent a
  file, symbol, finding id, or number.
- Wealth/authority language stays at **PL-0**.

### Output

Return the **complete filled** `CRITIQUE` markdown for `multi_llm/research_lane/proposals/deepseek/RC-002/CRITIQUE.md`, using the
template's sections exactly: target package · **blocking defects** (must fix before any
DECISION) · non-blocking risks · leakage/confounding/multiple-testing notes · alternative
explanation · recommendation (REJECT / REPAIR / ACCEPT).

Your recommendation is about **the evidence**, not about Position B.

Focus: attack the Phase 4g retraction
