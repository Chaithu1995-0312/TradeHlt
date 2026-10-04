## RC-002 · Hypothesis diversity · package kind = `PROPOSAL`

{{ROLE_BLOCK}}

You are the **second** actor in cycle `{{CYCLE_ID}}`. DeepSeek has already attacked the
evidence; you are not re-attacking it and you are not defending it.

### The one question you answer — and only this one

**If this 32-bar population is not "reversal", what is it?**

This is an *identity* question, not a measurement question and not a naming convenience. The
repository's own contract (`MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md`, in your bundle) puts
identity first and measurement downstream, and treats a discovered-but-undefined behaviour as
an explicit `UNKNOWN_*` node — never a TODO, never an approximation of an existing node.

Produce **at least three** candidate identities for the population described in dossier §2/§4.
For each candidate give:

- **Name** (or `UNKNOWN_*` — see below).
- **What it claims the bars ARE**, in market terms, in one paragraph.
- **Whether it is distinguishable from the existing `DISPLACEMENT` identity**, and how.
- **A falsifier** — a specific, measurable result that would kill this candidate. Not "more
  data would help"; a concrete observation.
- **Why it might be wrong.**

Required among your candidates:

- At least one candidate that treats the population as **not a distinct phenomenon at all** —
  i.e. F-074 is simply correct and these are ordinary rejected bars with no identity of their
  own. Steelman it properly; do not include it as a strawman.
- At least one **`UNKNOWN_*`** candidate, honestly specified: what is known, what is the single
  open question, what would resolve it. `UNKNOWN` is a legitimate, preferred answer where the
  evidence does not support a name. Do not manufacture a name to avoid it.

### Hard constraints

- **You are forbidden from ratifying the name `SweepReversal`.** It is recorded as a misnomer.
  If you believe it is nonetheless correct, you must argue that from the evidence and say so
  explicitly — you may not reuse it by default.
- **Do not** re-litigate the statistics; that is Gemini's package.
- **Do not** propose an implementation, a `CRTState`, a `when:` predicate, a threshold, or code.
  An identity is not a construct.
- **Do not** rule on Position B.
- If you need a repository fact not in the dossier, write `UNKNOWN:` — never invent a file,
  symbol, finding id, or number.
- Wealth/authority language stays at **PL-0**. An identity earns no authority (§6.5:
  information != value != authority).

### Output

Return the **complete filled** `PROPOSAL` markdown for `{{PROPOSAL_PATH}}`, using the stub's
sections. Put your candidate identities under "Work packages (ordered)" as an ordered list, one
block per candidate, and put the single strongest falsifier across all candidates in the
"Falsifier" section.

Focus: {{FOCUS}}
