# BitNet Design Specification — Evidence Consumer

> **What this is.** A **proposal** to move BitNet from a raw-feature gate embedded inside the CRT
> state machine to a consumer of specialist evidence at L3. It changes **what BitNet looks at**
> and **what it can perturb**. It does **not** change its authority stage (Safety) or its
> direction (veto).
>
> **Created:** 2026-07-29 · **Status: PROPOSED — not accepted, not implemented.**
> `use_bitnet` remains `false`. This document grants **no** authority (CLAUDE.md §6.5).
>
> **This requires an explicit product decision.**
> [`bitnet-cpp-specification-v1-2026-07-21.md`](../implementation_plan/bitnet-cpp-specification-v1-2026-07-21.md)
> §8.2 states: *"BitNet is not a fusion engine… Do not add BitNet to fusion weights without a new
> product decision and Authority Ladder evidence."* This proposal **is** that decision request.
>
> **Companions:** [`intelligence-topology.md`](intelligence-topology.md) (the L3 layer law) ·
> [`bitnet_qualification_protocol.md`](../governance/bitnet_qualification_protocol.md)
> (`BN_QUAL_V1` — how it would earn authority) ·
> [`bitnet_lineage_audit.md`](../governance/bitnet_lineage_audit.md) (implementation truth) ·
> MIAR §3.9 · template: [`envelope-layer-design.md`](envelope-layer-design.md) (`ENV_ARCH_V1`)

---

## 0. Objective (one sentence)

Give the safety veto access to the **panel's testimony** instead of a private six-feature view of
the same candles the panel already read.

---

## 1. Current design (implementation truth)

### 1.1 Architecture

`bitnet_score(features)` → `Legacy6Encoder` → `LegacyMLPBackbone` (6 → 16 → 8 dense) →
`ConfidenceSigmoidHead` → `CrtGateAdapter` → scalar in [0, 1].

**Inputs — exactly six raw keys, fail-fast on any missing** (`LEGACY6_KEYS`):

```
body_ratio · retest_depth · disp_strength · atr · candles_since_retest · double_sweep
```

**Output:** `state_acceptability_score` (MIAR's locked term — *not* "confidence", and never
p(win)).

**Consumption:** hard reject when `bn_score < bitnet_main_threshold` (0.55), inside
`crt_engine_v2`'s `approve_with_soft_conf` path. `use_bitnet` defaults to `false`, so it is
**inert on the active config** (F-004).

### 1.2 Where it sits

Inside the CRT state machine — **upstream of fusion**. `EXPECTED_ENGINES` excludes BitNet
entirely, and there is no BitNet call anywhere in `EngineRunner`, `FusionEngine`, or
`DecisionEngine`. It fires before the four specialists have been fused at all.

> **This is not drift.** MIAR §3.9 documents the Legacy6 raw inputs as BitNet's *intended*
> design. So this proposal is a genuine **intent change**, not a bug fix — and the target
> design's superiority is a **hypothesis**, not an established finding.

---

## 2. Why it is the wrong seat

Three independent defects, each sufficient on its own.

### 2.1 Wrong layer — correlated noise, not an independent check

BitNet reads L1 (raw candle geometry). So do CRT, Gaussian, Zone Gate, and RR. A model that
re-attends the event instead of reading the testimony cannot arbitrate the panel — it just adds a
fifth correlated opinion, upstream, where nobody can see it.

`model-design-intent.md` §7 already grades this **C**, describing it as *"a second, private
judgment seat"* that *"competes with the entire fusion committee… while answering to no one."*

### 2.2 Wrong mechanism — it mutates state instead of filtering

A BitNet reject **resets the CRT state machine**. Gate-ON is therefore a *divergent trajectory*,
not a filtered subset of gate-OFF: removed ≠ added.

**F-055 measured exactly this.** On BNBUSDT the gate produced **50 `LOW_SCORE` rejects** and net
trades still went **11 → 11**. A veto that merely skipped the candidate would have reduced the
count. This is an **undeclared side effect** — MIAR grants BitNet "veto on approve path only," not
state mutation. See [`model-responsibility-matrix.md`](model-responsibility-matrix.md) §3.2.

### 2.3 Wrong units — not scale-invariant, and train/serve-skewed

- **Raw `atr`.** The 4th input is `state.atr_abs`, unnormalized. Identical weights therefore mean
  different things per instrument (BNB ≈ 2.7 vs BTC in the hundreds). A structural
  scale-invariance defect, independent of any label problem.
- **F-050 key skew.** The model was trained on pipeline formulas FM-021/FM-020 under the names
  `retest_depth` / `disp_strength`. The call site now maps CRT's FM-027 / FM-028 cache emissions
  onto those same key names. If `use_bitnet` were flipped without retraining, the model would
  score mathematically different quantities under the names it was trained on.

### 2.4 What the evidence says

| Finding | Result |
|---|---|
| **F-004** | Real hard-reject gate when enabled; **inert** on active config (`use_bitnet:false`) |
| **F-050** | Train/serve key skew — `CONDITIONAL_SKEW` if enabled without retrain |
| **F-055** | Shadow A/B: pooled E **+0.156R → +0.023R**, ΔE = **−0.133R**, PF 1.29 → 1.04; **0 / 4 instruments improved** (SOL −0.35R). Underpowered (n < 30) — so *not* a hard economic claim, but zero positive instruments |

Lineage verdict: `INERT + CONDITIONAL_SKEW`.

---

## 3. Target design

### 3.1 Inputs — the specialist evidence bundle

BitNet reads **L2 outputs**, never L1:

| Field | Source | Form |
|---|---|---|
| `crt_score` | CRT scorer | ordinal [0,1] |
| `crt_state` | CRT FSM | categorical (one-hot over the 9 legal states) |
| `gaussian_score` | Gaussian | ordinal [0,1] — conformity, **not** p(win) |
| `zone_passed` · `zone_score` | Zone Gate | binary + ordinal |
| `rr_polarity` | RR engine | ordinal [0,1] — candle commitment |
| `fusion_normalized_score` | Fusion | ordinal [0,1] |
| `regime` | Regime | categorical |

**Hard constraint — scale invariance.** Every input is a ratio, a z-score, or a category. **No
raw price, no raw ATR, no absolute magnitudes.** This is what §2.3 got wrong, and it is
non-negotiable: a safety layer that means different things on different instruments is not a
safety layer.

### 3.2 Placement

L3 — after fusion-completeness, before Decision. It reads the bundle; it never touches
`crt_engine_v2`. **Removing the in-FSM call site is part of this proposal**, and is what converts
§2.2's 🟡 into a clean ➖.

### 3.3 Output

`state_acceptability_score` ∈ [0,1] — unchanged semantics, unchanged locked name.

---

## 4. How Decision should consume it

### 4.1 What Decision must **not** do

- Must not add BitNet to fusion **weights**. It is not a witness; it does not testify.
- Must not let a BitNet **pass** promote, upweight, or rescue anything.
- Must not read the score as a probability or as p(win).
- Must not allow BitNet to mutate CRT state, re-enter the FSM, or fire before all four
  specialists have scored.

### 4.2 What Decision **should** do — two channels

**Channel A — Safety veto (binding, negative-only).**
`score < threshold` → reject with an explicit `bitnet_unsafe` reason at the decision layer, where
it is visible in the ledger. The candidate is **skipped**; the state machine is untouched. This
is the whole behavioral difference from today: a filter, not a perturbation.

**Channel B — Advisory acceptability score (logged, never acted on).**
The score is stamped into the decision record and `TradeProvenanceV1` on **every** candidate,
including approved ones — giving a measurable series for `BN_QUAL_V1` without granting authority.

> ⚠️ **Channel B requires a MIAR amendment before implementation.** MIAR §3.9's non-goals
> currently read *"never positive score contribution as purpose."* Logging a score on approved
> candidates is arguably a positive-side contribution even when inert. The amendment must state
> that the advisory channel is **observation-only, with no consumer**, and must keep the locked
> vocabulary (`acceptability score`, never `confidence`). **Do not implement Channel B until MIAR
> §3.9 is amended.**

### 4.3 Authority ladder

| Level | BitNet state |
|---|---|
| Information exists | Score computed and logged (Channel B) |
| Economic usefulness | Measured ΔG001 from Channel A in shadow |
| Authority earned | Channel A becomes binding — **only** after `BN_QUAL_V1` GATE-S PASS |
| Architecture justified | Not sought. No new layer beyond the L3 slot |

---

## 5. Relationship to the open CRT conflict

Removing the in-FSM call site partially resolves a **recorded, undecided** conflict.

[`crt_intent_contract.md`](../governance/crt_intent_contract.md) documents that `crt_engine_v2` is
a pre-decomposition monolith conflating MIAR Stage 1 (structure) + Stage 3 (BitNet safety) +
Stage 4 (approval) + Stage 5 (execution), against MIAR's own requirement that these be owned
separately. Three remediations are proposed — relabel / physically extract / accept as documented
drift — and the decision **is still awaiting a user ruling**.

**This proposal does not pre-empt that ruling.** It removes Stage 3 from the monolith only. Stages
4 and 5 remain conflated regardless of what happens here. If the ruling is "physically extract,"
this work is a subset of it; if the ruling is "accept as documented drift," this proposal still
stands on its own §2 merits.

---

## 6. Explicit non-goals

1. **Never** optimize entries — a safety layer that can promote is not a safety layer.
2. **Never** replace or duplicate fusion.
3. **Never** re-derive market structure from raw candles.
4. **Never** fire before all four specialists have scored.
5. **Never** mutate CRT state.
6. **Never** be read as a calibrated probability.
7. **Never** absorb HMF's bidirectional allocation role — see
   [`intelligence-topology.md`](intelligence-topology.md) §4.

---

## 7. Relationship to HMF

L3 already has a dormant tenant. BitNet is the **safety** channel (binding, negative-only); HMF is
the **judgment** channel (advisory, bidirectional). Neither absorbs the other; both constraints in
topology §4 are binding. If a future program wants one unified L3 arbiter, that is a merge
decision requiring a new MIAR entry.

---

## 8. Migration

**Design target, not an implementation instruction.** Nothing here is built by this document.

| Phase | Work | Gate |
|---|---|---|
| 0 | This document accepted | product decision |
| 1 | MIAR §3.9 amendment (inputs + Channel B wording) | MIAR edit |
| 2 | Clean labels — the current contract is bullish-only and `DIAGNOSTIC_ONLY` | `BN_QUAL_V1` GATE-L |
| 3 | Retrain on the evidence bundle (scale-invariant) | GATE-O |
| 4 | Shadow A/B via `scripts/research/model_shadow_protocol.py` | GATE-S |
| 5 | Channel A binding | GATE-P |

`use_bitnet` stays `false` through **all** phases. Full ladder:
[`bitnet_qualification_protocol.md`](../governance/bitnet_qualification_protocol.md).

**Retraining is mandatory, not optional.** The existing artifact is a 6-input model; the target is
a different input space entirely. No weight transfer is possible or attempted.

---

## 9. Falsification

This proposal is **wrong** if any of the following hold:

1. A retrained evidence-consuming BitNet shows no discrimination on clean labels (GATE-O FAIL) —
   the safety question may simply not be answerable from L2 outputs.
2. Shadow ΔG001 is ≤ 0 (GATE-S FAIL) — repeating F-055's result at the new layer would mean the
   layer was never the problem.
3. Its vetoes prove redundant with `UltronRiskGate`'s existing rejections — a second safety
   authority earning nothing.

Any of these ⇒ BitNet stays inert and this document is marked SUPERSEDED, not quietly revised.
