# Pre-Registration — LLM as Blind Visual Annotator (descriptive fidelity)

> **Status:** PRE-REGISTERED (written before any LLM annotation exists). Authority: research/docs
> only (§6.5 Authority Ladder). Sibling of
> [`preregistration-blind-label-descriptive-fidelity.md`](preregistration-blind-label-descriptive-fidelity.md)
> ("the human prereg"), which is **frozen and unmodified** by this program apart from an
> append-only navigational pointer.
>
> **CH-llm-blind-label-annotator-v1, 2026-08-31.**

## Why this is a separate pre-registration

The human prereg's *subject* is the human. Its stated purpose is to convert one unmeasured claim
into a number — *"Would an experienced discretionary trader broadly agree? **Yes.**"* — and its
design rests on the observation that *"the definitional collision between trader language and code
output **is** the measurement."*

Substituting an LLM does not execute that registration; it **replaces its experimental subject**.
An LLM's agreement with the code is no evidence about what a discretionary trader sees. Reporting
an LLM run under the human prereg would be instrument substitution against an unrun registration.

Hence: same instrument, different question, its own frozen predictions and gate.

## The one changed variable

| Held frozen (byte-identical reuse) | Changed |
|---|---|
| `results/blind_label/sample_manifest.json` — 100 items, seed `20260801`, Arm A=60 / B=30 / C=10 | **Labeler: human → LLM** |
| `results/blind_label/session_01.html` — the 1.4 MB stimulus (SVG candles, 48-bar windows) | |
| The four question wordings and option sets (reproduced below, not re-authored) | |
| `scripts/analysis/blind_label_score.py` — Cohen's κ, `q2_vol` linear-weighted, rest nominal | |
| `scripts/analysis/blind_label_sample.py` — not re-run; no re-sampling | |
| Arm semantics: A = population estimate, B = conditional-only, C = intra-rater | |
| The `INSUFFICIENT` rule (< 15 minority-class instances) and the Q4 on/off-screen split | |

**No re-sampling, no re-wording, no metric substitution.** A diff on the scorer or the manifest
invalidates any run made against this document.

### The four questions (reproduced verbatim from the human prereg — frozen, not re-authored)

| # | Question shown to labeler | Options | Scored against | Metric |
|---|---|---|---|---|
| Q1 | At the marked bar, is the market trending up, down, or neither? | Up / Down / Neither | `trend_bias` ∈ {1, −1, 0} | Cohen's κ |
| Q2 | For recent conditions, is the marked bar's volatility Low, Normal, or High? | Low / Normal / High | `volatility_regime` ∈ {0, 1, 2} | linear-weighted κ |
| Q3 | Did the marked bar spike through a recent high or low and then close back inside? | Above / Below / Neither | `liquidity_sweep` ∈ {1, −1, 0} | Cohen's κ |
| Q4 | Did the marked bar break market structure? | Broke up / Broke down / No break | `break_of_structure` ∈ {1, −1, 0} | Cohen's κ |

## The question this program asks

> Can an LLM, shown only a chart image and the frozen question, reproduce the code's feature label
> blind — and is it self-consistent enough for that number to mean anything?

Explicitly **not** asked: whether a human would agree (that is the human prereg, still unrun);
whether the features are predictive or economic (F-019…F-097 answered that separately and this
cannot revise them); anything about CRT `EXPANSION` (a different program — see
[`design-vision-semantic-observation-schema.md`](design-vision-semantic-observation-schema.md)).

## The inverted failure mode (LLM-specific, and the reason a high κ is not self-evidently good)

The human prereg deliberately avoids formula-shaped wording because it *"would make the labeler a
slow computer and measure nothing."* For an LLM that risk **inverts**: an LLM plausibly *can* act as
a slow computer — reconstructing the definition (e.g. "close beyond `last_swing_high`") and
evaluating it from the rendered bars, rather than perceiving structure.

Both a perceiving annotator and a definition-reconstructing annotator produce high κ. They are not
the same result, and the score alone cannot separate them. Two frozen diagnostics address this:

- **D1 — Q4 on/off-screen split.** `break_of_structure` compares against a forward-filled reference
  that may sit outside the 48-bar window. A *perceiving* annotator should degrade sharply when the
  reference is off-screen. A *reconstructing* annotator has nothing to reconstruct from either, so
  it should also degrade — but a **high off-screen κ is anomalous** and is pre-registered here as a
  signal of leakage or memorisation, not of skill.
- **D2 — free-text rationale, unscored.** The model is asked, after each answer, to state briefly
  what on the chart drove it. Never scored, never part of any κ. Read only after scoring, purely to
  classify perceiving vs reconstructing. Same quarantine discipline as the human prereg's own
  guards.

## Arm order and the stop rule (the substantive addition over the human prereg)

The human prereg treats intra-rater κ (Arm C) as a *guard*. For a nondeterministic labeler it is the
**gate**, and it runs **first**:

```
Arm C  (intra-model, 10 repeat_of pairs)
   ↓   pass
Arm A  (population estimate, 60 items)
   ↓
Arm B  (per-stratum conditional, 30 items)
```

**Stop rule (frozen):** if Arm C κ < **0.60** on a question, that question is reported as
`AMBIGUOUS_FOR_THIS_LABELER` and **no conclusion about the underlying feature is drawn from its
score** — inherited verbatim from the human prereg's intra-rater guard. If Arm C κ < 0.60 on **all
four** questions, the program halts at Arm C and reports that; Arm A/B are not computed. A labeler
that cannot reproduce itself cannot inform a code-agreement claim.

Arm C also carries an LLM-specific hazard the human design did not face: the 10 Arm-C items are
repeats presented at shuffled positions, so a long-context model may **recognise** the repeat rather
than re-derive it. Recognition inflates Arm C. Mitigation, frozen: each item is annotated in an
**independent session with no shared context**, so no repeat is visible within a context window.

## Model and prompt freeze

Changing any of these forks the experiment; it does not continue it.

| Field | Value |
|---|---|
| `model_id` | **`claude-opus-5`** — frozen 2026-08-31, before any annotation existed |
| `prompt_version` | `llm-blind-label/v1` |
| `temperature` | **not settable** by the annotation harness (subagent invocation exposes no temperature control). Recorded as an honest limitation, not a chosen value: run-to-run variation is therefore whatever the platform default produces, which is exactly the nondeterminism Arm C is designed to measure. Not tuned between arms because it cannot be. |
| `replicates` | 1 per item, except Arm C's `repeat_of` pairs which are 2 by construction |
| `session_isolation` | one item per session, no shared context |
| Image shown | the item's SVG window from `session_01.html`, unmodified |

The model is shown **only** the chart image and the question. Never: the feature names, the answer
options' code meanings, the manifest, timestamps, other items, or any prior answer.

## My pre-registered predictions (frozen before any annotation)

Distinct from the human prereg's predictions; those are about a trader and are not restated here.

| Cell | Prediction |
|---|---|
| Arm C, Q1 `trend_bias` | κ ≥ 0.75 — visually unambiguous, expect high self-consistency |
| Arm C, Q2 `volatility_regime` | κ ∈ [0.50, 0.75] — ordinal boundary judgement is where nondeterminism should bite hardest |
| Arm C, Q3 / Q4 | κ ≥ 0.65 |
| Arm A, Q1 | κ ≥ 0.55 |
| Arm A, Q3 `liquidity_sweep` | κ ≥ 0.45 — the "spike through then close back inside" wording is visually checkable |
| Arm A, Q2 (linear-weighted) | κ ∈ [0.25, 0.50] — no on-screen normalisation reference for "recent conditions" |
| Arm A, Q4 pooled | κ < 0.40 |
| Arm A, Q4 split | on-screen κ materially > off-screen κ; **off-screen κ ≥ 0.50 would be anomalous** (see D1) |
| Overall | Arm A κ ≤ Arm C κ per question — self-consistency bounds code-agreement |

## Pre-registered interpretation (fixed now)

- **Arm C fails the 0.60 floor on a question** → that question is uninterpretable for this labeler;
  no feature conclusion drawn. Not a feature defect.
- **Arm A high with Arm C high** → the LLM can reproduce the code's labels from an image blind.
  Authority-Ladder rung 1 ("information exists") **only** — no fusion, sizing, model weight, or
  `ACTIVE_VERSION` consequence, and no claim about human perception.
- **Arm A high but D1 shows high off-screen Q4 κ** → treat as suspected definition-reconstruction or
  leakage, **not** perceptual skill; report as such and do not register a fidelity claim.
- **Arm A low with Arm C high** → the LLM is self-consistent but disagrees with the code. This is
  the interesting cell: it is evidence about the *definitional collision*, not about model quality,
  and D2's rationales are read to characterise it.
- **Any scored cell with < 15 minority-class instances** → `INSUFFICIENT`, never a null result
  (E-001: underpowered ≠ negative).
- Arm B is **conditional only** and is never blended into a marginal — inherited from the scorer's
  own rule.

## Order of operations (integrity-critical, frozen)

1. This document committed with predictions in the clear. *(← current step)*
2. `model_id` / `temperature` recorded above, **before** annotation.
3. Verify the instrument is untouched: `sample_manifest.json` `source_csv_sha256` and
   `prod_config_version` re-checked; `blind_label_score.py` and `blind_label_sample.py` unmodified
   (verify by `git status`, not by inspection).

   **Known blocker, measured 2026-08-31 — do not treat as satisfied without reading this.**
   `tests/test_blind_label_harness.py` does **not** currently pass in this environment:
   `1 failed, 4 passed, 6 errors`. Cause is *not* a correctness defect — the harness shells out to
   `blind_label_sample.py` with a hardcoded `timeout=120`
   (`tests/test_blind_label_harness.py:43`) and the sampler exceeds it here, so
   `test_same_seed_is_deterministic` raises `subprocess.TimeoutExpired` and the six tests depending
   on the regenerated-sample fixture error out. Confirmed **pre-existing and unrelated to this
   program**: `blind_label_sample.py`, `blind_label_score.py`, `test_blind_label_harness.py` and
   `results/blind_label/` are all untouched by it.

   Consequence for this gate, stated rather than glossed: the four tests that *do* pass are the
   scorer-behaviour ones (perfect-vs-random separation, `INSUFFICIENT` below min-n). The
   leak-proof, determinism and composition guarantees are currently **unverified in this
   environment**, because the tests asserting them cannot complete.

   **Gate as amended:** before any annotation, either (a) raise that subprocess timeout and get a
   green run, or (b) verify the three leak/composition properties directly against the *committed*
   `session_01.html` and `sample_manifest.json` — which are the artifacts this program will actually
   use, and which need no regeneration. Option (b) is sufficient and cheaper: this program reuses
   the committed sample and never re-runs the sampler. A spot check already performed shows the
   committed stimulus contains **zero** occurrences of the four feature names. Raising the timeout
   is a code change to a frozen-instrument test and is **out of scope for this pre-registration**;
   it must not be bundled in.
4. **Arm C annotation only.** Score. Apply the stop rule.
5. If passed: Arm A, then Arm B annotation. Score with the unmodified scorer.
6. Read D2 rationales — only now, after scoring — to classify perceiving vs reconstructing.
7. Report. Null results are reported as results.

## Non-interference with the human arm

The human program remains fully executable on the same 100 items afterwards. LLM answers are stored
separately (`results/blind_label/llm_labels_<model>_<date>.csv`) and are **never** shown to a future
human labeler, nor merged into any human answer file. This program consumes no part of the human
registration.

## Authority

Research/docs only. However this scores, it changes no config, no model weight, no fusion authority,
no `ACTIVE_VERSION` (§6.5: information ≠ economic usefulness ≠ authority ≠ architecture). It cannot
revise F-019…F-097, cannot re-open F-080, and says nothing about the CRT `EXPANSION` construction
gap.

---

## EXECUTION HALTED AT THE GATE — 2026-08-31 (appended after the attempt; nothing above altered)

> Append-only. No prediction, floor, question wording, interpretation rule or scope ceiling above
> has been changed. Amending a gate after discovering it cannot be met would be exactly the
> threshold-shopping this registration exists to prevent, so the gate stands as written and the
> program stops against it.

**Steps 1–3 completed. Step 4 was not run. Zero annotations were collected.**

### What was completed

- **Step 1/2 — model and prompt frozen** before any annotation: `model_id = claude-opus-5`,
  `prompt_version = llm-blind-label/v1`. `temperature` recorded as *not settable* by the harness.
- **Step 3, route (b) — PASSED, 7/7** against the committed artifacts: zero feature-name leaks in
  the stimulus; zero `<text>` elements; no manifest reference; composition A=60/B=30/C=10, n=100;
  all 100 items have an SVG; all 10 Arm-C repeats resolve to an original on the same
  `target_row_index`; `source_csv_sha256` matches the corpus on disk. (Manifest provenance noted:
  it was generated under `prod_config_version: v2_multi_2026_04`, not the current
  `ACTIVE_VERSION`. Internally consistent — the frozen `answers` are what this program scores
  against — but recorded rather than glossed.)
- **Stimulus rasterised faithfully.** `scripts/analysis/blind_label_rasterize.py` renders each
  item's SVG to PNG so annotation is a vision task and never SVG-source parsing. A first render was
  **wrong and was caught before any annotation**: extracting the bare `<svg>` dropped
  `session_01.html`'s `<style>` block, silently destroying three channels at once — the green/red
  up-down distinction, the dark chart background, and the **orange highlight + dashed vertical line
  that identify the marked bar**. Fixed by injecting the stimulus CSS verbatim; verified by colour
  histogram (`#26a269` up, `#c01c28` down, `#f5a623` mark present) and by eye. Also established:
  the marked bar is always the **last** bar in the 48-bar window (`target_row_index ==
  context_end_index`, offset 47).

### The blocker — the intra-rater gate is UNEVALUABLE BY CONSTRUCTION

`blind_label_score.py` sets `MIN_CELL_N = 15` and `_kappa` returns
`{"status": "INSUFFICIENT", "kappa": None}` below it. Arm C contributes **one pair per Arm-C item**
— 10 items, therefore **n = 10 < 15** — so `arm_c_intra_rater` can never be `SCORED`.

Verified empirically, not by reading: a synthetic **perfect-label** set (every item answered with
the manifest's own key — the best case attainable) was scored through the unmodified scorer:

| Question | n | status | κ |
|---|---|---|---|
| `q1_trend` | 10 | `INSUFFICIENT` | `None` |
| `q2_vol` | 10 | `INSUFFICIENT` | `None` |
| `q3_sweep` | 10 | `INSUFFICIENT` | `None` |
| `q4_bos` | 10 | `INSUFFICIENT` | `None` |

(Arm A scores normally at n=60, so this is specific to Arm C's allocation, not a broken scorer.)

**The stop rule therefore cannot be satisfied in either direction.** It is written as "if Arm C
κ < 0.60, halt"; the actual state is that Arm C κ is *undefined*. An unevaluable ceiling cannot be
passed, and this registration's own reasoning — *"a labeler that cannot reproduce itself cannot
inform a code-agreement claim"* — forbids proceeding to Arm A/B on an unverified ceiling. So the
program halts here.

### This is NOT a result about the LLM

No annotation was collected, so nothing whatsoever has been measured about whether an LLM can
reproduce the code's labels. This is a **blocker about the instrument**, and conflating the two
would be precisely the E-001 error this document is written to avoid.

### It affects the human program identically

The blocker is in the shared instrument, not in the LLM arm. The human registration's own
interpretation rule — *"Intra-rater ceiling < 0.6 on any question → that concept is inherently
ambiguous for this labeler; no conclusion about the underlying feature is drawn from that
question's score"* — depends on a number its own scorer cannot produce at n=10. Whoever runs the
human arm will hit this wall too.

### What would clear it (each requires its own registration — deliberately NOT done here)

1. **Re-sample with ≥15 Arm-C items.** Forbidden here: this registration froze *no re-sampling*, and
   a new sample forks the experiment.
2. **Lower `MIN_CELL_N`, or compute intra-rater κ outside the scorer.** Forbidden here: both are
   metric substitution against a frozen instrument, and `MIN_CELL_N` encodes the
   underpowered-≠-negative discipline (E-001) that the rest of the design depends on.

Either is a legitimate future program. Neither may be done inside this one, and neither may
retro-fit this registration.
