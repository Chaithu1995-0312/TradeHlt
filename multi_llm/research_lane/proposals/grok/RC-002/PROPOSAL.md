# PROPOSAL — identity of the 32 directional-contract bars

```yaml
schema_version: "1.0"
package_id: RC-002-PROP-GROK-001
kind: PROPOSAL
cycle_id: RC-002
created_at: 2026-09-04T00:00:00Z
author_role: hypothesis_diversity
author_model: grok
claim_type: process
related_package_ids: [RC-002-CRIT-DEEPSEEK-001]
status: PROPOSED
promise_rung_max_claim: PL-0
```

**Lane:** semantic certification. **Question:** if the 32 bars are not "reversal," what are they?

They still have no established identity. Both prior names are unsupported.
**`SweepReversal` was NOT ratified.**

## Candidates (ordered)

1. **`UNKNOWN_SWEEP_CHILD_MEMBERSHIP`** *(honest default)*.
   Known: 32/32 Gate-0 rejects; CHoCH correctly silent; flip mechanism false; resumption rates
   vacuous; outcomes AMBIGUOUS. **Open question:** does the candle *belong* to the still-held sweep
   as a child, or is that sweep a spectator? Until that is answered, a name is an invention.

2. **`NOT_A_DISTINCT_OBJECT`** *(the F-074 steelman)*.
   These are ordinary rejects of "is this the displacement of *this* sweep?" **Complements of a
   named gate are not automatically a market object.** F-074 already named this population and
   refused it as DISPLACEMENT.

3. **`SAME_SIDE_CONTINUATION_THROUGH_SWEEP`**.
   The geometric *dual* of DISPLACEMENT: impulse **through** the raided side (successful auction /
   stop-run that became a break), not *away* from it. Not "trend resumption." Not a reversal.

4. **`INDEPENDENT_IMPULSE_WITH_LIVE_SWEEP`**.
   A magnitude candle that would have existed anyway; the held sweep is a spectator of TTL/age,
   not a parent.

5. **`MISPARENTED_DISPLACEMENT`** *(H_tool)*.
   Ordinary DISPLACEMENT of a *different* founding event than the one recorded in
   `displacement_direction`. Dossier gap #4 (`sweep_sig` vs `liquidity_sweep`, 38.42% opposite-side)
   is relevant **only if** it supplies a matching parent on these 32.

## Strongest falsifier

**Whether each of the 32 extends or closes beyond the held sweep's extreme on the swept side.**

- They don't → **candidate 3 dies**.
- They do, and the 39 continuation bars leave the *other* side → **candidates 2 and 4 die**.
- `sweep.price` not recoverable → **stop naming; UNKNOWN stays**.

## Out of scope

**D-16:** do not run another OHLCV directional expectancy test on these 32. That family already
returned AMBIGUOUS.

---

## Executor note — recoverability gate only (Claude, 2026-09-04)

> Filed in the ledger as **`RC-002-EVID-CLAUDE-001`** (`EXECUTION_EVIDENCE`), separate from this
> PROPOSAL. The author filed their own ledger line for `RC-002-PROP-GROK-001`; an executor scribe
> line briefly collided with it and was removed in favour of the author's, with the executor-only
> content re-filed under its correct kind and `author_role`.

The falsifier's own stop-condition is a recoverability check, so that check was run. **The
falsifier itself was NOT run** — new EXECUTION_EVIDENCE requires a DECISION freeze
(`research_lane/README.md`), and this is a new measurement, not verification of a published claim.

**Gate result: PASS, but the falsifier is under-specified.** "The held sweep's extreme" admits two
different referents, and they are not equally recoverable:

| Definition of "the held sweep's extreme" | Recoverable? |
|---|---|
| **(1)** the HTF range bound that `_detect_htf_range_sweep` actually tested against (`range_h_ref` / `range_l_ref`) | **NO** — not emitted to the trace; needs a new run |
| **(2)** the extreme (`raw_high`/`raw_low`) of the founding SWEEP candle itself | **YES** — founding bar identifiable **32/32**, all 32 carry a non-zero `sweep_sig`, so the swept side is known |
| **(3)** engine `SWEEP.price` (84 events carry `price` + `direction`) | **YES but cross-constructor** — these are the *engine's* sweeps; the 32 came from *resolver* occupancy, and F-069 measured only 88.16% agreement between the two |

This matters semantically, not just practically: under the active `htf_range` founding mode the
sweep is defined against the **range bound**, so definition (1) is arguably the correct referent —
and it is the one that is not recoverable. Definitions (1) and (2) can disagree on a candle that
pushes past the founding candle's high but not past the range bound, which is exactly the region
candidate 3 lives in.

**Routed to Gemini** (turn 3, test design) rather than resolved here: which referent the test
should use, and whether definition (2) alone is sufficient to kill candidate 3 honestly.
