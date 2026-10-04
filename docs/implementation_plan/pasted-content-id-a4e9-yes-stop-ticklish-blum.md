# Step C — what does the gate's `double_sweep` bonus mean? (2026-10-03)

## Context
CH-planner-liq-sweep-direction is built and measured but **not activated**: `v2_htfcrt_2026_08`
keeps `liq_sweep_semantics: legacy_unsigned`, by user decision. The blocker is
`GateIntelligence._intent_score`'s `+0.5·double_sweep`. On the live rail it is **necessary**
for every LIQ_SWEEP approval, because vol ≡ 0 and liquidity ≡ 0 there. So the 44 correctly aligned
approvals still pass only through an input whose meaning is unresolved. Step C establishes that
meaning from evidence, before any choice between C04, same-side confirmation, removal, or an existing
concept. PULLBACK/OQ7 stays deferred.

## Read-only findings so far (items 1–4, verified at source this turn)

**Correction first (E-001).** Caught me overclaiming; I owe you a correction. Census row 2 (B1-L, and the
MKT-C04 divergence row) assumed the gate consumer *meant* "same-side confirmation". That was my
inference, not grounded. The code lineage says otherwise (below). The defect claim survives in a
narrower form: the representation does not match the intent. The stated "expected input" was wrong.

**1. Origin of the bonus.**
- It arrived in the initial bulk commit `5897209f` (2026-04-30) with no design note.
- The term comes from the engine's `SweepEvent.double_confirmed` (`crt_engine_v2.py:965-968`):
  `prev_sweep is not None and prev_sweep.direction != direction`. That is an **ordered two-sided
  sequence ending in the current sweep**: the opposite side was swept first, and the current sweep's
  direction defines the trade.
- It is registered the same way at `active_models.yaml:301`.
- Every consumer treats it as a **bonus on the current sweep**:

| Consumer | Bonus |
|---|---|
| engine `score_sweep` (`crt_engine_v2.py:2087`) | +0.4 |
| engine risk adjustment (`crt_engine_v2.py:2387`) | +0.10 |
| `engines/scoring_engine.py:41-44` (EngineRunner CRT score) | sweep 0.7 → 1.0 |
| `strategies/s10_trap_strategy.py:161` | +0.10 |
| planner gate (`gate_intelligence.py:246`) | +0.5 |

- The engine's own flag is structurally always False (MKT-E01 divergence row, DEPRECATED I-13). So the
  ordered meaning has **never executed** anywhere.

**2. What the bonus actually receives.** FM-060 / FM-092 (`market_ontology.yaml:2703-2728`) is
**unordered**: both signs anywhere in W = 5 bars, not tied to the current sweep. Its registered
interpretation is *"trap / whipsaw… neither side is in control"*. That reads as a caution, while every
consumer applies a bonus.

So there are three meanings in play:
- (a) the intended ordered sequence, which is dead;
- (b) the registered unordered regime, worded as a caution;
- (c) a bonus wired to (b).

This is a **§6.2 TruthConflict**: intent (a) vs representation (b), with opposite polarity wording.

**3. Ontology v2 ownership.** No existing concept owns (a).
- MKT-C04 is (b).
- MKT-E04 `crt_displacement` (ACCEPTED, "directional impulse away from a specific prior sweep") is the
  only same-side confirmation concept. It is a later-bar event that no consumer ever meant.
- MKT-E03 `choch` is PROPOSED/UNDEFINED.
- "Same-side confirmation" would be a new invention. Per your rule it is not adopted to preserve
  approvals.

**4. Trained-model intent.**
- BitNet Legacy6 (`active_models.yaml:643`, MIAR) reads the *engine's* constant-False `double_sweep`
  and is off (`use_bitnet:false`, F-004).
- `s08_ml_ensemble` and `s10_trap` read the pipeline C04. No active trained artifact gives evidence for
  either meaning.

**Side observation, out of scope and recorded only:** `ttl_liq_sweep_sec = 300 s` is shorter than one
M15 bar. A live LIQ_SWEEP LIMIT expires inside the next bar, so its fill cannot be observed from M15
OHLC.

## Plan for item 5 — full-corpus measurement (OBSERVATION_ONLY, scratchpad script)
Preflight per §1.5:
- git status;
- interpreter;
- corpus `data/mt5/XAUUSD_M15.csv`, echo the row count;
- `sweep_semantics: e01_lifecycle` frame (per-side `_e01_sweep_upper/_lower`, `feature_pipeline.py:880`)
  plus the active frame.

Population: every bar × direction where `e01_direction_aligned` labels LIQ_SWEEP (7,542 active / 5,033 e01).
For each, compute the candidate flags on the same bars:
- **X0** current C04 (`double_sweep`);
- **X1** ordered (a): an opposite-side E01 event within W bars *before* the current bar, causal;
  bar-local two-sided counted separately;
- **X2** MKT-E04 displacement on the next k bars (diagnostic only, not decision-time-available);
- **X3** none (bonus removed).

Report, per candidate:
1. **Decision space.** Live-faithful gate approvals and flips vs X0, using the existing gate arithmetic.
2. **Information test.** Does the flag split the outcome of the aligned sweep entries?
   - Outcome object per your answer below.
   - `multi_tp_walk` (SEM-017, the production two-target object, F-088).
   - Gross R primary; SEM-015 cost secondary.
   - Time-split train/holdout for sign stability; block-bootstrap CI; n per cell.
   - Diagnostic only, no G001.

Reuse:
- the B1-L/B1-F harness (`liq_direction_ab.py`);
- `ExecutionPlanAdapter` (`src/research/model_runners/adapters/execution_plan.py`), which mirrors
  `live_engine_hook` `planner → compute_crt_levels(atr_abs)`;
- `multi_tp_walk` (`src/research/oracle/multi_tp_walk.py:124`).

## Records (after measurement, same turn)
- Correct the B1-L row 2 "expected input" and the MKT-C04 divergence row (`CORRECTED:` marker, history
  kept).
- Add the TruthConflict (a)/(b) to MKT-C04 as `decide_in` (an open decision).
- Note the TTL observation on the planner topic.
- Add a SESSION LOG entry.
- No code or config change.

## Then (your decision, not this turn)
Choose the role of the bonus from evidence:
- adopt (a) as a new PROPOSED concept (it has lineage, but has never executed);
- keep (b) and resolve its polarity wording;
- move confirmation to E04;
- or remove the bonus.

Then re-evaluate activation of `e01_direction_aligned`.

## Verification
- The script echoes the corpus path and row count.
- Population counts equal B1-F (7,542 / 5,033).
- The X0 approvals reproduce B1-F (44 / 40).
- `validate_all()` returns `[]`.
- The semantic tests, `test_doc_citations` and `test_topic_docs` pass.
- The floor stays at its 7 known reds.
