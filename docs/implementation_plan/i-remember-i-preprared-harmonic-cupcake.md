# CRT Dependency-Graph Discussion — Tracker

> **Mode: DISCUSSION ONLY. Nothing is written to the repository.** No docs, no findings, no
> artifacts, no code. This file lives outside the repo (`~/.claude/plans/`) and is the only
> thing that gets saved. It exists so the thread does not drift as context grows.

## Standing rules (do not drop these as context enlarges)

1. **Open every response with the tracker status table below.** Verbatim, updated.
2. **Work the items in order.** T1 → T2 → T3 → T4. Do not jump ahead.
3. **Source is the authority.** The Infrastructure Inventory is a *declaration layer built from
   docs* — it has already been caught missing something real (`MANIPULATION_C2`). Workbooks,
   docstrings, comments and other models' analyses are **hypotheses**; reproduce against code
   before repeating (§6.8, and the standing "verify source, not comments" lesson).
4. **Explain in graphs and plain language**, for the user *and* a coding LLM. Cite `file:line`.
5. **Name the producer.** `crt_engine_v2` (engine) and `crt_state_resolver` (resolver) are
   different constructions — F-069 measured 88.16 % agreement. "Does X depend on Y" has two
   answers unless the producer is named.

## Status

| # | Item | Status |
|---|---|---|
| **T1** | **The SMC dead end** — nine SMC scalars computed every bar, scored by nothing. Where exactly do they stop? Is the 39→48 schema move the whole story, or is there a second break? What would make one reachable? | **YET TO START** |
| **T2** | **Engine vs resolver sweep** — two producers, two sweep definitions, one config switch (`sweep_geometry`). Which feeds decisions today? What would `pipeline_swing` change? Does this explain F-069's gap? | **YET TO START** |
| **T3** | **Sujan vs repo CRT mapping** — map the narrated chain (Manipulation → Sweep → Displacement → Distribution) onto the real 12-state graph. Name where the two ontologies genuinely *disagree*, not merely differ in vocabulary. | **YET TO START** |
| **T4** | **Founding a sweep on SMC** — the pluggable founding is the one real opening. What would an FVG- or order-block-founded sweep require? What would make it a new ontology rather than a re-run? | **YET TO START** |

---

## Established this session (verified against source — do not re-derive, do not drift)

These are settled. Cite them; don't re-litigate them.

- **`MANIPULATION_C2` exists in code**, and the Infrastructure Inventory does not know it.
  `state_identity.py:60`; transitions `RANGE_C1 → MANIPULATION_C2 → DISTRIBUTION_C3` (F-075).
- **Manipulation is not downstream of Sweep — it is the same predicate at parent scale.**
  `market_ontology.yaml:4667` declares SP-001 consumers as *both* `CRTState.SWEEP entry` and
  `CRTState.MANIPULATION_C2 entry`, transitions `RANGE → SWEEP` and `RANGE_C1 → MANIPULATION_C2`.
- **CRT does not consume SMC.** `grep -in "fvg|order_block|breaker|mitigation|choch|eqh|pdh"
  src/config_layer/crt_engine_v2.py` → **zero hits**. The inventory's "no declared edge" is
  *correct*, not incomplete.
- **SP-001/SP-002 are pure scalar OHLC identities.** `src/structure/predicates.py:67-120`.
  `swept_high = high > h_ref and close < h_ref`. No config reads, no I/O, no state.
  `predicates.py` is the HOW; the ontology `definition` block is the WHAT (demoted 2026-08-19,
  RC-5); `tests/test_predicate_definition_binding.py` fails if they disagree.
- **Two distinct quantities are both called "sweep."** SP-001 = **strict** (`close < ref`),
  founding-range referenced, emits `SweepEvent`. FM-058/059/060 `liquidity_sweep` /
  `sweep_detected` / `double_sweep` = **inclusive** (`close <= ref`), swing-pivot referenced
  (`last_swing_high_price.shift(1)`), emits `int8` vector slots.
  `market_ontology.yaml:4680` carries the explicit DISTINCT QUANTITY WARNING.
- **`sweep_geometry` is resolver-only.** Declared `htf_range` at `market_crt_states.yaml:278`,
  read at `crt_state_resolver.py:263`. The engine has no such selector.
- **The founding is deliberately pluggable** — M15 structural range / parent candle / weekly
  calendar range / chart-visible pool. That independence is what made F-042 and F-081 legitimately
  new ontologies. **Nothing today founds a sweep on an FVG or order block.**

## The graph as currently established

```
OHLC ─┬─> SMC primitives ──> 48-dim vector ──> ✗ (no engine / gate / scorer reads them)
      │     order block · FVG · breaker · mitigation · PDH-PDL · EQH-EQL · CHoCH
      │
      └─> SP-001 swept_boundary ──> SP-002 directional_impulse ──> CRT construction
            (OHLC + caller-supplied reference level)          ──> RANGE · SWEEP · DISPLACEMENT
                                                                  EXPANSION · RETEST · EXECUTION
                                                                  RESOLUTION  (+ parent-scale
                                                                  RANGE_C1 · MANIPULATION_C2 ·
                                                                  DISTRIBUTION_C3)
```

Two parallel branches off OHLC that never meet. T1 tests the left branch's dead end; T2 tests
whether the right branch has one definition or two.
