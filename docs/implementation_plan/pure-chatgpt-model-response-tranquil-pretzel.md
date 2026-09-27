# BitNet — Theory of Design (discussion artifact, no implementation)

**Date:** 2026-09-23 · **Branch:** `grokbotchanges` · **Active config:** `v2_htfcrt_2026_08`
**Mode:** plan mode — design theory only. No code, config, retrain, or enable.
**Constraint from user:** no subagents; schema gathered inline from source + artifacts;
`docs/implementation_plan/` read for reference only; **gaps are recorded, not fixed.**

---

## Context

BitNet is the CRT spine's optional hard-reject gate. Its architecture program is *finished* —
contracts A/B/C frozen, the Encoder→Backbone→Heads→Adapter hierarchy implemented in
`src/bitnet/`, an R1 CONTRACT-C trainer and an R2.5 kill-test harness both shipped. What is
not finished is evidence, and the question this session answers is *why*, from the schema
rather than from the plan documents' own summaries.

The answer that falls out of the artifacts: **BitNet's three schemas — serve domain, train
population, and label — describe three different objects.** Architecture is not the binding
constraint; population and label definition are.

---

## Source-verified state (all re-read this session)

### Declared intent
`docs/governance/miar_registry.json` → `bitnet`:
- intent: *"Should this opportunity be rejected because the semantic state is unsafe?"*
- output `state_acceptability_score`; authority: **veto on approve path only when enabled**
- non-goals: never optimize entries, never replace fusion, never estimate continuous envelopes
- stage `safety`, order 8; alignment **ALIGNED**; falsification: F-055

`active_models.yaml` → `bitnet`: status `dormant`, `enabled:false`, threshold 0.55,
evidence F-004 / F-050 / F-055.

### Runtime contract
- `bitnet_score(features)` → `get_default_composition().predict(...).confidence`
  ([bitnet_inference.py:325](src/bitnet/bitnet_inference.py:325))
- composition = `enc_legacy6_v1 + bb_legacy_mlp_6_16_8_v1 + hd_confidence_sigmoid_v1 + ad_crt_gate_v1`
  ([composition.py:121](src/bitnet/composition.py:121))
- call site: `crt_engine_v2.py:2176-2195` — registry `assert_serve_allowed`, FM-027→`retest_depth`,
  FM-028→`disp_strength`, FM-070→`candles_since_retest`, then `< bitnet_main_threshold` → `LOW_SCORE`
- active config `v2_htfcrt_2026_08`: `crt_engine.use_bitnet = false`, threshold 0.55, no `bitnet` section

### Evidence ladder position (spec v1.2.6 R0–R6)
| Stage | State | Artifact |
|---|---|---|
| R0 platform | DONE | `src/bitnet/{encoders,backbones,heads,adapters,composition}.py` |
| R1 trainer | DONE | `contract_c_trainer.py`, bundle `results/bitnet/bundles/smoke_c_r1` |
| R2.5 kill-test | **FAIL_INVESTIGATE_NO_R3** on 3 of 4 real runs | `results/bitnet/r25/*_evaluation_report.json` |
| R3 / R4 / R6 | not reached | — |

R2.5 detail (real XAUUSD windows, not the synthetic smoke which PASSed):
- `xauusd_2mo`: fails `feature_ablation` (zeroing 19 of 38 dims **lowers** MSE) and
  `label_shuffle_kill` (AUC 0.655 on true holdout after training on shuffled y — *higher* than
  the 0.637 real-label AUC)
- `xauusd_existing_2mo`: `holdout_gt_random` AUC 0.496; ablation negative
- `xauusd_W2026-02-23`: AUC 0.497, `prediction_collapse` (pred_std 0.0047), ablation ~0

### Why those failed — the population/label audit
`results/bitnet/audit/population_label_multi_2026_07_22.md`, contract
`BITNET_LABEL_ATR_RACE_BULL_V1`: pooled **n=188,673, pos_rate 0.958**;
`EXTREME_IMBALANCE_ge_95pct_majority` on 10 of 12 datasets (XAUUSD windows 0.977–0.989).
The R2.5 XAUUSD run's holdout is `n=517` at `label_pos_rate 0.990` → roughly **5 negatives**.
AUC and the shuffle test are unpowered by construction.

> Precision note (E-001): the harness's own suggested diagnosis for a shuffle-kill failure is
> "leakage / eval bug." The artifacts do not support that reading here. The observed cause is
> the label base rate — a majority-class predictor scores ~0.99 accuracy and a noisy AUC
> regardless of y. The FAIL is a correct stop signal with an incorrect default explanation.

### Economic prior
`results/bitnet/shadow_diagnostic_majors.json` (F-055): gate-ON vs OFF, book level —
BNB NEUTRAL (11→11 trades, 2 removed averaging **+0.43R**, i.e. winners), ETH INERT,
pooled ΔE −0.13R, 0/4 instruments improve. Mechanism recorded in the artifact itself: a reject
**resets the CRT state machine**, so gate-ON is a divergent trajectory — `removed != added`.
BitNet is not a filter over a fixed entry set.

### Semantic OS comparison (§6.7)
```
--ground --kind NOUN --token bitnet
  → status UNKNOWN · "no authority record matches 'bitnet'"
--ground --kind IMPLEMENTATION --token src/bitnet/bitnet_inference.py --symbol bitnet_score
  → status GROUNDED · authority disk+ast · evidence_class PROVEN · semantic_id null
```
`docs/governance/semantic_os/*.yaml` mentions BitNet in exactly 3 negative clauses
("does not enable BitNet/TradeNet by presence alone", a fail-open symptom, an enablement-audit
detection note) plus a `build_bitnet_features` file-identity row. There is **no BitNet concept
node, no boundary, no contract, no journey.**

So: MIAR carries the intent, `active_models.yaml` carries the runtime + evidence, the ontology
carries the *features* (FM-027/028/070 name the BitNet call boundary explicitly), and the
Semantic OS — the layer that governs what may be *claimed* — has no BitNet identity at all.
The implementation grounds only as a file+symbol on disk, with `semantic_id: null`.

---

## The three schemas that do not meet

| | Serve domain | Train population | Label |
|---|---|---|---|
| Defined by | CRT `RETEST` → `approve_with_soft_conf` | `retest_depth > 0.05` on every pipeline bar (`bar_filter_id = retest_depth_gt_0.05_FM021`) | 2·ATR before 1·ATR within 40 bars, timeouts dropped, bullish-only |
| Size (XAUUSD 2yr) | **~24 RETEST entries / 4 EXECUTIONs** (`userinvestigation/linkcostmodelstateengineschema.txt` reference run) | **188,673** pooled | pos_rate **0.958** |
| Identity | FM-027 / FM-028 / FM-070 + `atr_abs` | FM-021 / FM-020 + relative ATR | — |

Three separate mismatches, each independently sufficient to void an R3 comparison:

1. **Population mismatch.** The gate is trained on ~188k bars it will never be asked about and
   evaluated on ~24 it will. A veto learned on the unconditional bar distribution is not a veto
   over the CRT-committed distribution.
2. **Identity mismatch (F-050).** Same names, different math, plus absolute-vs-relative `atr`.
   CONTRACT-C C.1 forbids exactly this; the artifact predates the contract.
3. **Question mismatch.** MIAR asks *"is this state unsafe?"* — a left-tail question. The label
   answers *"did a 2:1 ATR race win?"* — a central-tendency question whose positive class is
   96% of the population. A safety veto trained on a win label has no negatives to learn from.

---

## Gaps found and deliberately NOT fixed (user instruction)

1. **`use_bitnet:true` is not executable today.** `bitnet.defaults.LEGACY6_KEYS` carries
   `candles_since_sweep` (swept in by the F-107 v6.0 rename) while the call site injects
   `candles_since_retest` and the ontology's FM-070 entry states the encoder expects
   `candles_since_retest`. Probed read-only: `Legacy6Encoder().encode(apply_crt_serve_aliases(crt_dict))`
   → `KeyError: 'candles_since_sweep'`. F-004's "inert" now understates it: the enable path is
   **broken-if-enabled**, and nothing tests the enabled path. Same silent-gap class as F-085/F-056.
2. **`enc_canonical38_v1` no longer means 38.** `Canonical38Encoder().dim()` returns **48**
   (live `CANONICAL_FEATURES`, `SCHEMA_VERSION 6.0`) while `DEFAULT_INPUT_DIM = 38` and the R2.5
   runs used `feature_dim 38`. A default-built CONTRACT-B composition fails closed at
   `composition.py:207` (48 != 38) — correct behaviour, stale constant, misleading id.
3. **Registry `feature_order` vs `LEGACY6_KEYS`** disagree on the same key (`models/bitnet/bitnet_registry.json`).
4. **Semantic OS has no BitNet noun** — under §6.7 no "BitNet" repository claim can be grounded.

---

## Theory of design — what would make BitNet effective

**Premise.** The architecture program answered "what shape should the model be?" and froze a
good answer. The unanswered question is the ML-research one: *over which population, against
which label, is a safety veto learnable at all?* Every artifact above points at the same
conclusion — **design the population and the label first; the network is the least important
decision left.**

### Five design principles the evidence forces

**P1 — A veto must be trained on the distribution it vetoes.** Either widen the serve domain to
where n exists (`SWEEP` 1,792 / `DISPLACEMENT` 399 / `EXPANSION` 142 transitions in the
reference run) or accept a proxy population with an explicitly declared transfer assumption.
Training on all bars and serving at RETEST is neither.

**P2 — Match the label to the question, not to the trade.** "Unsafe" is a left-tail predicate
(toxic fill, immediate adverse excursion, gap-through), not a win predicate. A toxicity label
is *designable in balance*: the quantile is a knob. This single reframe converts a 96/4 problem
into whatever ratio the design chooses, and it is the only change that makes the R2.5 kill tests
informative rather than degenerate.

**P3 — Identity before weights.** CONTRACT-C C.1 already states the rule; the two key-name
drifts above show it is enforced on envelopes but not on the *code constants*. The encoder's key
list should be derived from the ontology/registry rather than hand-written, so a schema rename
cannot silently break the serve path.

**P4 — A veto's loss is asymmetric; MSE on {0,1} is the wrong objective.** The costs are
unequal (false reject = a forgone winner, and F-055 shows the two removed BNB entries averaged
+0.43R; false accept = a taken loser). The right offline target is precision at a fixed recall
on the toxic class, with the operating threshold chosen on the cost curve — not a single 0.55
constant inherited from a different model.

**P5 — The veto is a trajectory perturbation, not a filter.** Because a reject resets the CRT
state machine, no entry-set arithmetic is valid. Only book-level A/B (the existing
`bitnet_shadow_diagnostic.py` method, and F-036/F-070's byte-diff discipline) can measure it.
This also means a *better classifier does not imply a better book* — that link has to be
measured, never assumed.

### Options

| | Option | Buys | Costs / honest objection |
|---|---|---|---|
| **A** | Repair in place: fix key drift, retrain legacy-6 under a new label contract on the RETEST domain | Smallest surface; keeps CONTRACT-A byte-stable | RETEST domain is n≈24/instrument/2yr — **not trainable**. A is a hygiene fix wearing an ML costume |
| **B** | Re-found as a **toxicity veto** on a widened structural domain (score at DISPLACEMENT/EXPANSION), new `BITNET_LABEL_TOXICITY_*` contract, identities from the ontology, asymmetric objective | The only option that satisfies P1+P2 simultaneously; makes R2.5 meaningful; reuses the whole frozen platform unchanged | Widening the scoring point is a **semantic change to the gate's stage** (MIAR stage 8 `safety`) — needs an intent decision, not just code; new label contract must be versioned, not edited |
| **C** | Demote to a **research ranker / monitoring channel** with no veto authority; log `state_acceptability_score` on every candidate, never reject | Zero production risk; builds the labelled serve-domain corpus that A/B both lack; honest under §6.5 | Defers the question; produces information, not authority |
| **D** | **Retire the socket** — keep CONTRACT-A frozen as history, mark `bitnet` RETIRED | Defensible on evidence: F-055 (0/4 improve), R2.5 FAIL, broken enable path, no Semantic OS identity | F-055 is underpowered (n<30) and R2.5 failed *on a bad label*, not on the model — retiring now discards the platform before the real experiment was ever run |

### Ordering the theory implies

The dependencies are strict and mostly non-ML:

1. Name the serve domain (which CRT state the veto scores) — an **intent** decision (MIAR/ontology),
   not a code change.
2. Declare the population as a registered object, with n reported per instrument, *before* any label.
3. Design the toxicity label with a chosen class ratio; version it as a new `label_contract_id`
   (never edit `BITNET_LABEL_ATR_RACE_BULL_V1`, per C.3 and the audit's own recommendation).
4. Re-run R2.5 — and expect the kill tests to now be *capable* of failing for real reasons.
5. Only then R3 (backbone-only A/B), and only then R4 shadow at book level.
6. Enable is R6 and requires measured ΔG001 + user approval; nothing before that grants authority.

Steps 1–3 are where the value is. Steps 4–6 are already built.

### Ambiguities for the user

- **Stage semantics:** does widening the scoring point (B) violate MIAR's `stage: safety, order 8`,
  or is the stage about *authority* (veto) rather than *position* (RETEST)? This is an intent
  question the reviewer should not settle alone.
- **6 vs 48:** spec §12 open question 4 is still open, and the canonical surface has moved twice
  since the spec was written (39→48 at v5.0, names at v6.0). B implies choosing.
- **Toxicity definition:** adverse-excursion threshold, gap-through, or cost-relative — three
  different vetoes.

---

## Verification (for whichever option is later authorized)

Read-only checks used this session, reusable as the evidence floor:

```bash
venv/Scripts/python.exe scripts/governance/query_semantic_os.py --ground --kind NOUN --token bitnet
venv/Scripts/python.exe -X utf8 -c "import sys;sys.path.insert(0,'src');from features.feature_schema import CANONICAL_FEATURES,SCHEMA_VERSION;print(SCHEMA_VERSION,len(CANONICAL_FEATURES))"
venv/Scripts/python.exe -m pytest tests/test_bitnet_inference.py tests/test_bitnet_parity.py tests/test_bitnet_r25_kill_test.py -q
```

Plus, for any future enable-path work: a test that actually exercises `use_bitnet=true` end to
end — its absence is what let gap #1 through.

---

## Status

Design discussion only. No file in the repository was modified. Gaps 1–4 are recorded here and
left for a later authorized turn, per the user's instruction.
