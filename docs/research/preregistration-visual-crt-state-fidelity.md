# Pre-Registration — Visual CRT State Fidelity

> **Status:** PRE-REGISTERED (written before any item image is generated and
> before any label exists). Authority: research/docs only (§6.5 Authority
> Ladder). This document FREEZES the four questions, the two-arm design, the
> sample, my own predictions, and the interpretation rule **before** any label
> exists, so a null cannot be quietly re-spun into a finding and a hit cannot
> be threshold-shopped. Enforced socially by the Epistemic Integrity ritual
> (Program E-001,
> [`docs/governance/EPISTEMIC_INTEGRITY.md`](../governance/EPISTEMIC_INTEGRITY.md)).
>
> Clones the structure and the frozen "Order of operations" of
> [`preregistration-blind-label-descriptive-fidelity.md`](preregistration-blind-label-descriptive-fidelity.md).
> That program asked whether *feature values* match a chart reading. This
> program asks whether the engine's *CRT classification at a marked bar*
> matches what an independent observer can see. They are not the same
> measurement.

## Context & scope

The XAUUSD one-month OHLC odds comparison (F-080 / CH-xauusd-tv-odds) tested
whether *the same numbers* appear on both feeds. It cannot detect a state
machine that is internally consistent but semantically wrong — it feeds the
engine its own rules twice.

This program converts the unmeasured claim into numbers: a cold observer
labels marked bars from TradingView crops, the labels are scored against the
engine's own `STATE_TRANSITION` events, and the result is reported as
chance-corrected agreement (Cohen's κ) **per arm**. It measures **descriptive
fidelity only** — whether the engine's classification corresponds to what is
visible on the chart. It is explicitly **not** an economic or predictive-value
test; F-019 through F-043 already answered that question, separately, and this
program cannot revise any of them (§6.5: information about descriptive
fidelity grants no fusion/production authority).

Three findings from exploration reshape the design and are frozen here:

1. **"What state is this candle" has no answer.** CRT state is path-dependent.
   `configs/formulas/market_crt_states.yaml`'s own header states that
   memory-requiring states *"cannot be resolved from a single bar's feature
   vector alone"*, and F-069 is the empirical proof — a per-bar predicate
   resolver reproduces the engine at **10.77% EXPANSION recall**.
   `process_candle` dispatches on `state.current_state`, so an identical bar
   is evaluated against completely different predicates depending on the
   path. The comparison therefore asks about **events at a marked bar given
   visible context**, in trader language, never "label this candle."

2. **The dominant confound is already measured and it is large.** The
   engine's swept envelope is a trailing 14/16-bar count-window extreme
   (`m15_structural_range.py::from_child_window`), rebuilt on every reset —
   not a level anyone would draw.
   `reports/monthly_tv_vs_active_production_semantic_comparison.md` already
   scored this month's 84 sweeps against chart-visible levels: **5 of 84**
   align tightly with a production SMC level, **51 of 84 touch no SMC level
   at all**, 30/84 match a prior closed H4 high/low. A bare-chart observer
   will therefore disagree with most sweeps for a *known structural reason*.
   The two-arm design exists specifically to separate that cause from genuine
   classification disagreement; without it the experiment mostly re-measures
   something already known.

3. **Only ~23% of the month is legibly captured.** Pixels-per-candle is
   exactly `1743 / n_bars`. Shots 04/07/08/14 are ≥8px; the four wide shots
   covering the rest are 3.2–5.6px and are unusable for per-candle work *by
   design* (`shot_plan.json` says so three times). Cropping cannot rescue
   them — a crop is a crop. Re-capture narrow (`month-legible` preset).

## Instrument & universe (frozen)

- Corpus: `data/XAUUSD_M15.csv` (2,116 bars, 2026-07-07 01:00 → 2026-08-06
  23:45 broker). **Not re-fetched.**
- Engine ground truth: `STATE_TRANSITION` events in
  `results/htfcrt_1month_parent_wired/run_20260816_011239_XAUUSD/XAUUSD_events.jsonl`
  (active config `v2_htfcrt_2026_08`, parent-CRT wired; 84 SWEEP / 19
  DISPLACEMENT / 6 EXPANSION / 2 RETEST = **111 transitions**).
- Per-bar range level for Arm 2:
  `results/crt_survey_trace/20260815T062829Z/trace.jsonl` →
  `crt_inputs.active_range.h_ref / l_ref`.
- **Join on `timestamp`, never `candle_index`.** Bases differ by a constant
  per-run offset (`crt_state_confusion_matrix.py::remap_event_indices_to_ohlcv`).
- **Fail closed on a config mismatch.** These two artifacts come from
  different runs. State sequences must agree on every shared timestamp
  before they are used together. The known 85-vs-84 sweep delta is one sweep
  inside the 78-bar backtest warmup and is not a mismatch. Disagreement
  elsewhere aborts; do not reconcile by hand.
- TradingView history exists only for this month. Extending n means a new
  capture campaign on a different window — out of scope.

## A pre-declared limit (frozen, before anything is built)

The month contains **2 RETESTs and 6 EXPANSIONs**. Under the
`< 15 minority-class instances → INSUFFICIENT` rule those cells **cannot
produce a result at any effort level**, and DISPLACEMENT (n=19) is
marginal. Only **SWEEP (n=84)** can carry a real number. This is a property
of the corpus, declared now so a thin cell cannot later be presented as a
null (E-001: underpowered ≠ negative).

## The four questions (frozen wording, trader language in / CRT vocabulary out)

Deliberately phrased the way a discretionary trader thinks about a chart,
not the way the formula reads — asking *"did the high exceed h_ref while
the close came back below it"* would make the labeler a slow computer and
measure nothing. **No rule card with engine thresholds is given to the
classifier.** The definitional collision between trader language and engine
output **is** the measurement.

| # | Question shown | Options | Scored against | Metric |
|---|---|---|---|---|
| V1 | At the marked bar, did price spike beyond a prior extreme and then close back inside? | Above / Below / Neither | engine `SWEEP` + direction (SHORT→Above, LONG→Below) | Cohen's κ (linear-weighted; Below < Neither < Above) |
| V2 | Is the marked bar a strong directional push away from that spike? | Up / Down / Neither | engine `DISPLACEMENT` + direction (LONG→Up, SHORT→Down) | Cohen's κ (linear-weighted; Down < Neither < Up) |
| V3 | Does the marked bar carry that push further in the same direction? | Yes / No | engine `EXPANSION` | Cohen's κ |
| V4 | Has price come back close to the level it originally broke? | Yes / No | engine `RETEST` | Cohen's κ |

Plus per item: **confidence** (HIGH / MEDIUM / LOW) and **free-text visible
evidence** — the mismatch-dossier fields (body/wick structure, relation to
the previous candle, location within the drawn range).

The marked bar is indicated by a **neutral tick outside the plot area**.
No vertical event marker sits on the candle. No state name appears on any
labeling surface.

## Two arms (frozen)

| Arm | Image | What it isolates |
|---|---|---|
| Arm 1 | Bare 48-bar crop. Marked bar indicated by a neutral tick outside the plot. | What a chart reader sees with no engine geometry. |
| Arm 2 | Identical crop plus two **unlabelled, neutral-coloured** horizontal lines at the engine's `h_ref` / `l_ref`. No state names, no direction-encoding colours, no vertical event markers. | What a chart reader sees **given the engine's own level**. |

Arm 1 and Arm 2 **must be labelled by different cold subagents**. Reusing
one agent across arms anchors Arm 2 on Arm 1 and destroys the delta — which
is the load-bearing measurement.

## Sample design (frozen, seeded)

- **Positives:** all 111 `STATE_TRANSITION` events (not a subsample).
- **Controls:** ~111 bars with `crt.action == NONE`, matched on **session**
  and **candle-range percentile** so they are not trivially distinguishable
  from positives. Controls are non-optional — without them only agreement
  on engine-positives is measurable, and events the engine *missed* are
  undetectable.
- Seeded RNG (seed recorded in the manifest at generation time). Default
  seed `20260818`.
- Presentation order shuffled. Items carry **opaque hashed filenames**
  (`item_a3f9c2.png`) with no timestamp, instrument, or state name in the
  name.
- Context window: 48 bars ending at the marked bar (no lookahead).
- Every generated item must be **≥ 8 px/candle**; fail closed below it.
- `overlaps_prior_item` is recorded per item. Event-anchored items cluster,
  so context windows overlap and answers are not fully independent. κ is
  reported both pooled and split on this flag (mirrors how the feature-level
  prereg splits Q4 on off-screen references).

## Capture (frozen)

`tools/tv_forensic/shot_plan.json` preset `month-legible`: twenty M15 shots
of 160 bars each with ≥50-bar overlap, tiling the full 2,116-bar corpus at
~11 px/candle (1743 / 160). Overlap guarantees every item has a full
48-bar context window inside a single shot. Every edge sits on a
live-market bar from the engine CSV (never a calendar edge inside a
weekend gap). `frame_shot`'s two-sided assertion is **not loosened**; on
refusal the window is narrowed and split, and the refusal is recorded.

## My pre-registered predictions (frozen before any label is collected)

| Cell | Prediction |
|---|---|
| V1 SWEEP, Arm 1 (bare) | κ ∈ [0.15, 0.35] — most swept levels are invisible |
| V1 SWEEP, Arm 2 (level drawn) | κ ≥ 0.65 |
| **V1 Arm2 − Arm1 delta** | **≥ +0.30** — the load-bearing prediction; this is the decomposition |
| V2 DISPLACEMENT | Arm 1 κ ∈ [0.30, 0.50]; Arm 2 κ ∈ [0.45, 0.65]; likely reported INSUFFICIENT at n=19 |
| V3 / V4 | INSUFFICIENT by construction (n=6, n=2) |
| Controls, Arm 1 | observers call a sweep on ≥20% of engine-silent bars — the false-negative channel |
| LLM-vs-human ceiling | κ ≥ 0.55, below the 0.75 the feature-level prereg predicted (states are harder) |

## User's predictions

Recorded by the user in a separate, sealed file. Its SHA-256 is committed
here **before** any item is generated; I do not open that file until after
scoring is complete.

- User prediction file: `docs/research/visual-crt-user-predictions.SEALED.md`
- SHA-256 at seal time: `130b928c54f504d85edc78994d95a4771882a4b87725b6b442640ad3085baf63`

`scripts/research/visual_state_sample.py` refuses to emit the real item set
until this slot holds a 64-hex digest. `--allow-unsealed` exists only so
the floor tests can run against synthetic fixtures.

## Pre-registered interpretation (fixed now, before results exist)

- **Arm 2 high, Arm 1 low, delta large** → engine classification is
  faithful *given its own level*; the divergence from a chart reading is
  **level choice, not state logic**. Doc/finding about level visibility;
  **no engine defect**.
- **Arm 2 also low** → the state logic diverges from an observer given the
  *same* level. This is the only branch that would warrant a §6.8 semantic
  review — and only if the user-adjudicated ceiling on that question is
  ≥ 0.5.
- **High observer-positive rate on controls** → engine misses chart-visible
  sweeps. Information about **coverage**, not correctness.
- **Ceiling < 0.5 on a question** → that question is ambiguous for this
  classifier; **no conclusion about the engine** is drawn from it (guard
  against blaming the engine for a badly-posed question).
- **Any cell < 15 minority instances** → `INSUFFICIENT`, never a null.

## Order of operations (integrity-critical, frozen)

1. This document is written and committed with my predictions in the clear.
2. User records predictions in `docs/research/visual-crt-user-predictions.SEALED.md`;
   its SHA-256 is added to this document.
3. `tools/tv_forensic/capture_tv.py --preset month-legible` captures the
   twenty narrow M15 shots (one invocation). On `frame_shot` refusal: do
   not loosen the assertion; narrow and split; record it.
4. `scripts/research/visual_state_sample.py` generates the blinded sample
   (Arm 1 + Arm 2 crops + labeling HTML + `manifest.json`). The manifest
   is the answer key and is **never referenced by any labeling surface**.
5. `tests/test_visual_state_harness.py` proves the labeling surfaces leak
   no answer, the sample is deterministic under its seed, and the scorer
   distinguishes perfect from random labels. Each floor is
   mutation-verified to fail against a leaky surface or a degenerate
   scorer.
6. Two **different** cold subagents label Arm 1 and Arm 2. Each receives
   only the image path and the frozen question text
   (`docs/research/visual-crt-labeler-brief.md`). Subagent blinding is
   **procedural, not mechanical** — disclosed honestly. The user then
   adjudicates a random ~30-item subsample (mechanically blind HTML) →
   LLM-vs-human ceiling.
7. `scripts/research/visual_state_score.py` scores against the manifest.
   Reuses `build_confusion` (`scripts/research/crt_state_confusion_matrix.py`);
   does not reimplement the matrix.
8. The user's sealed file is opened and its SHA-256 re-verified against
   the value recorded in step 2 — proving neither side revised predictions
   after seeing results.
9. Findings decision is **gated** (§6.2). Results are brought before any
   finding is edited. Default is **no new F-id**.

## Authority

Research/docs only. A descriptive-fidelity score, however it comes out,
changes no config, no model weight, no fusion authority, no
`ACTIVE_VERSION` (§6.5 Authority Ladder: information ≠ economic usefulness
≠ authority ≠ architecture). Anything read off pixels is a **VISUAL**
claim under the `smc_visual_verification.py:19-30` split — *"never
self-certifies; renders the evidence and stops."* The headline verdict
will be `RENDERED_PENDING_HUMAN_ADJUDICATION`, bounded by the measured
ceiling. F-079 is the standing warning: a skipped measurement and an
absent one must never look identical.

Never a column called `TradingView_state`. TradingView declares no state.
Every conclusion records `engine_state`, `visual_state`,
`visual_confidence`, `visual_evidence`.
