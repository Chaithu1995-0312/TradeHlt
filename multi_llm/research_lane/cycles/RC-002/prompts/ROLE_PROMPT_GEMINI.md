## RC-002 · Quant critique · package kind = `CRITIQUE`

{{ROLE_BLOCK}}

You are the **third** actor in cycle `{{CYCLE_ID}}`. **This prompt was rewritten mid-cycle**
because turn 1 already answered its original question — do not look for it.

### What turn 1 settled (so you do not redo it)

DeepSeek's `CRITIQUE` (`RC-002-CRIT-DEEPSEEK-001`) argued the retraction's surviving statistic
was selection-induced. The executor ran the deciding measurement and **confirmed it**:

```
statistic:  trend_bias(t-1) aligned with candle dir(t) on the 32 bars = 29/32 = 90.62%
first (wrong) denominator:  all bars                = 47.86%  -> p ~ 4e-07   [withdrawn]
correct question: is a founding sweep counter-trend by nature?
    sweep implied dir OPPOSITE trend_bias =  182/203 = 89.66%  corpus-wide
    P(>=29/32 | 0.8966) = 0.574                                 -> VACUOUS
```

Both Phase 4g statistics are now dead (no-flip p=0.826; pre-aligned p=0.574). The population's
identity is `UNKNOWN`. **That is settled. Do not re-argue it.**

### The one question you answer — and only this one

**Given the selection rule, is there any statistic that COULD discriminate this population — and
what would it take to run it honestly?**

This is a forward design question, not another critique of a dead number. Address:

1. **The matched-control problem.** The 32 are defined by `candle_dir != sweep_implied_dir`. Any
   quantity correlated with that relationship is contaminated by construction. Name the classes
   of quantity that are **not** — and be concrete, not categorical.
2. **A concrete candidate test.** Propose one measurable statistic, computable from the fields in
   dossier §3 plus per-bar OHLC, that would separate these 32 from a properly matched control if
   they are genuinely a distinct phenomenon, and return null if they are not. State its null,
   its control group, and its falsifier.
3. **Serial dependence and effective n.** The 2,038 bars are heavily autocorrelated —
   `trend_bias` flips on only 4.5% of them, and the 203 sweep events are not independent draws.
   Estimate the **effective** sample size for your proposed test, and say what real n (in bars,
   or in months of M15 data) it would need for a decisive result.
4. **Is 89.66% itself suspicious?** Founding sweeps being counter-trend ~90% of the time is a
   structural property of `_detect_htf_range_sweep` (raw high/low/close against frozen HTF range
   bounds) meeting an EMA-sign trend measure. Is that rate what you would *expect* from those two
   constructions, or does it indicate something worth its own investigation? Answer as a
   statistician, not as an ontologist.
5. **Pre-registration.** Turn 1's defect #4 (no pre-registration, post-hoc hypothesis selection)
   is accepted. State the minimum pre-registration your proposed test in (2) would require.

### Hard constraints

- **Do not** name or characterise the population — that is Grok's package.
- **Do not** re-litigate the dead statistics.
- **Do not** propose ontology, states, predicates, or code. A test design is not an implementation.
- **Do not** rule on Position B.
- **Do not** propose a test you cannot state a null and a falsifier for.
- If you need a number not in the dossier, write `UNKNOWN:` and name the exact computation that
  would produce it. Never estimate a repository number from memory.
- Wealth/authority language stays at **PL-0**. A discriminating test earns information, never
  authority (§6.5).

### Output

Return the **complete filled** `CRITIQUE` markdown for `{{PROPOSAL_PATH}}`. Map the template's
sections onto this task: "blocking defects" = why the *currently available* evidence cannot
settle the identity question; "recommendation" = REPAIR (run your proposed test before any
identity claim) / REJECT (no test can discriminate here, say why) / ACCEPT (the `UNKNOWN` verdict
is already the correct terminal state).

Focus: {{FOCUS}}
