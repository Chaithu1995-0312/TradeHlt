# Pre-Registration — Blind Labeling Test of Semantic-Layer Descriptive Fidelity

> **Status:** PRE-REGISTERED (written before any bar is labeled). Authority: research/docs only
> (§6.5 Authority Ladder). This document FREEZES the questions, the sample design, my own
> predictions, and the interpretation rule **before** any label exists, so a null cannot be
> quietly re-spun into a finding and a hit cannot be threshold-shopped. Enforced socially by the
> Epistemic Integrity ritual (Program E-001,
> [`docs/governance/EPISTEMIC_INTEGRITY.md`](../governance/EPISTEMIC_INTEGRITY.md)).

## Context & scope

[`results/feature_trace/semantic_layer_validation_7day.md`](../../results/feature_trace/semantic_layer_validation_7day.md)
rates every feature family for "Human agreement: Strong / Partial / Weak" and closes with
*"Would an experienced discretionary trader broadly agree? **Yes.**"* No trader was ever asked —
that rating is the report author's judgment, formatted as if it were measured. Everything the
report actually proves (geometry re-derivation, 7/7 definitional invariants, contradiction scan)
is **internal**: features checked against the same OHLCV they were computed from. That closed
loop is exactly why a real, externally-checkable defect (an MT5 server-time-labeled-as-UTC
timestamp offset touching the `session` canonical feature, `src/inout/mt5_candle_fetcher.py:186`)
survived a clean-bill-of-health audit untouched.

This program converts the one unmeasured claim into a number: a human blind-labels 100 bars from
the production feature frame, the labels are scored against the code's own output, and the result
is reported as chance-corrected agreement (Cohen's κ). It measures **descriptive fidelity only** —
whether the layer describes what a trader sees on the chart. It is explicitly **not** an economic
or predictive-value test; F-019 through F-043 already answered that question, separately, and
this program cannot revise any of them (§6.5 Authority Ladder: information about descriptive
fidelity grants no fusion/production authority).

## Instrument & universe (frozen)

- Corpus: `data/mt5/XAUUSD_M15.csv` run through the standard production path —
  `FeaturePipeline.run()` including `finalize()` (`src/features/feature_pipeline.py:1250`),
  active config `v2_multi_2026_04`.
- Full finalized frame (~47,197 rows, 2024-05-22 → 2026-05-21), **not** the 634-bar / 7-day slice
  the existing report used — one week is one regime sample, a limitation the report itself named
  for its own Phase-1 predecessor but did not apply to itself.
- Warmup rows excluded per `required_warmup_rows()` (`feature_pipeline.py:222-257`, currently 78).

## The four questions (frozen wording, trader language in / code semantics out)

Deliberately phrased the way a discretionary trader thinks about a chart, not the way the formula
reads — asking "did the high exceed the prior swing high while the close came back below it"
would make the labeler a slow computer and measure nothing. The definitional collision between
trader language and code output **is** the measurement.

| # | Question shown to labeler | Options shown | Scored against | Metric |
|---|---|---|---|---|
| Q1 | At the marked bar, is the market trending up, down, or neither? | Up / Down / Neither | `trend_bias` ∈ {1, −1, 0} | Cohen's κ |
| Q2 | For recent conditions, is the marked bar's volatility Low, Normal, or High? | Low / Normal / High | `volatility_regime` ∈ {0, 1, 2} | linear-weighted κ (ordinal) |
| Q3 | Did the marked bar spike through a recent high or low and then close back inside? | Above / Below / Neither | `liquidity_sweep` ∈ {1, −1, 0} | Cohen's κ |
| Q4 | Did the marked bar break market structure? | Broke up / Broke down / No break | `break_of_structure` ∈ {1, −1, 0} | Cohen's κ |

Chosen because they are exactly the four families the existing report graded — two confidently
("Strong": `trend_bias`, `liquidity_sweep`) and two with hedges ("Partial":
`volatility_regime`, `break_of_structure`) — maximizing diagnostic value per labeled bar.

## Sample design (frozen, seeded)

- **Arm A — 60 items, uniform random** over all eligible bars. This is the only arm from which a
  real-world agreement estimate may be quoted; it preserves true class base rates.
- **Arm B — 30 items, stratified** on rare/interesting classes: nonzero `liquidity_sweep`
  (≈19% base rate), fresh-transition `break_of_structure`, and expansion-onset bars (top-decile
  `candle_range` immediately following 3+ bars of below-median range), ~10 per stratum. Reported
  **only as within-stratum conditional κ** ("κ among sweep bars," "κ among fresh-BOS bars"), never
  blended into a marginal/population-rate estimate — this is stricter than reweighting and avoids
  importance-weighting machinery entirely. Arm A alone is the sole source of any population-rate
  quote.
- **Arm C — 10 items, repeats** of Arm-A items, re-presented at shuffled positions with no visual
  marker distinguishing them from first presentations → measures **intra-rater reliability**, the
  ceiling every feature κ is reported as a fraction of.
- Seeded RNG (seed value recorded in the manifest at generation time). Sampled items kept ≥60 bars
  apart so 48-bar display windows do not overlap and one answer cannot be inferred from another.
- Presentation order shuffled; timestamps and all feature values suppressed on the labeling page.

## Off-screen-reference diagnostic (frozen)

`break_of_structure` compares `close` against `last_swing_high/low_price`
(`feature_pipeline.py:731-732`), a forward-filled reference that can sit hundreds of bars back —
potentially outside the 48-bar display window. If the reference level is not visible, disagreement
is not evidence the feature is wrong. Per item the manifest records whether `ref_high`/`ref_low`
falls inside the displayed range; Q4's κ is reported **both pooled and split** on this flag.

## My pre-registered predictions (frozen before any label is collected)

| Question | Prediction |
|---|---|
| Q1 `trend_bias` | κ ≥ 0.60 |
| Q3 `liquidity_sweep` | κ ≥ 0.60 |
| Q2 `volatility_regime` (linear-weighted) | κ ∈ [0.30, 0.55], disagreement concentrated on expansion-onset bars |
| Q4 `break_of_structure` | κ < 0.40 overall, but κ ≥ 0.60 restricted to fresh-transition, on-screen-reference bars |
| Intra-rater ceiling (Arm C) | κ ≥ 0.75 on all four questions |
| Q4 conditional split | κ materially lower when `ref_high`/`ref_low` is off-screen than when on-screen |

## User's predictions

Recorded by the user in a separate, sealed file. Its SHA-256 is committed here **before** any
label is collected; I do not open that file until after scoring is complete.

- User prediction file: `docs/research/blind-label-user-predictions.SEALED.md` (git-ignored /
  not read by me until reveal)
- SHA-256 at seal time: `<TO BE FILLED BY USER, THEN RECORDED HERE>`

## Pre-registered interpretation (fixed now, before results exist)

- **All four questions score high** → the existing report's self-assessment is vindicated by
  measurement. This still grants **no** economic or promotion authority (§6.5) — descriptive
  fidelity is Authority-Ladder "information exists," nothing more.
- **Q1/Q3 score low** (below my predicted floor) → the report over-claimed "Human agreement:
  Strong" for those families; same-turn duty is a doc correction to
  `semantic_layer_validation_7day.md` plus a registered finding (§6.2 rule 2/3).
- **Q4 scores high overall** (contradicting my prediction) → the report's "Partial" hedge for
  `break_of_structure` was too pessimistic; the latching complaint is theoretical, not perceptual.
- **Intra-rater ceiling < 0.6 on any question** → that concept is inherently ambiguous for this
  labeler; **no conclusion about the underlying feature is drawn from that question's score**.
  This is the guard against blaming a feature for a badly-posed question.
- **Any scored cell with < 15 minority-class instances** is reported `INSUFFICIENT`, never as a
  null result (E-001 discipline: underpowered ≠ negative).

## Order of operations (integrity-critical, frozen)

1. This document is written and committed with my predictions in the clear.
2. User records predictions in a separate sealed file; its SHA-256 is added to this document.
3. `scripts/analysis/blind_label_sample.py` generates the blinded sample + labeling HTML +
   `sample_manifest.json` (the answer key — never referenced by the HTML).
4. `tests/test_blind_label_harness.py` proves the HTML leaks no answer, the sample is
   deterministic under its seed, and the scorer distinguishes perfect from random labels.
5. User labels via the HTML, exports CSV.
6. `scripts/analysis/blind_label_score.py` scores against the manifest.
7. The user's sealed file is opened and its SHA-256 re-verified against the value recorded in
   step 2 — proving neither side revised predictions after seeing results.

## Authority

Research/docs only. A descriptive-fidelity score, however it comes out, changes no config, no
model weight, no fusion authority, no `ACTIVE_VERSION` (§6.5 Authority Ladder: information ≠
economic usefulness ≠ authority ≠ architecture).
