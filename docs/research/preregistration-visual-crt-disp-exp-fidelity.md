# Pre-Registration — Visual CRT DISPLACEMENT / EXPANSION fidelity (P-VSTATE-02)

> **Status:** PRE-REGISTERED (written before any item image is generated and
> before any label exists). Authority: research/docs only (§6.5).
>
> This is a **new** experiment. It does not amend
> [`preregistration-visual-crt-state-fidelity.md`](preregistration-visual-crt-state-fidelity.md)
> (Experiment 1, STOP / ARCHIVE). It does not score RETEST. It does not
> rewrite the ≥30 floor. It does not expand the corpus.

## Design lock (user 2026-08-18) — Option A

P-VSTATE-02 will measure **DISPLACEMENT** and **EXPANSION** on the existing
frozen 2-year XAUUSD corpus. **RETEST remains explicitly unmeasured /
INSUFFICIENT** because n=24 does not meet the pre-declared ≥30 floor.
**No corpus expansion. No floor rewrite.**

Census (already measured, not this experiment):
[`reports/xauusd_visual_state_exp2_feasibility.md`](../reports/xauusd_visual_state_exp2_feasibility.md).

| State | 2-year engine n | This experiment |
|---|---:|---|
| DISPLACEMENT | 399 | **measured** (eligible) |
| EXPANSION | 148 | **measured** (eligible) |
| RETEST | 24 | **unmeasured / INSUFFICIENT** — not in the item set |
| EXECUTION | 4 | **excluded** — engine-process state, no visual cell |

## Context

Experiment 1 asked whether engine SWEEP matches a chart reading. The
load-bearing prediction (Arm 2 κ ≥ 0.65, Δκ ≥ +0.30) failed. That result
does not speak to DISPLACEMENT or EXPANSION. Those cells were
INSUFFICIENT on the one-month file (n=19 / n=6). This experiment exists
only because the 2-year file has enough of those two events.

Same doctrine as Experiment 1: trader-language questions, no CRT
vocabulary on the labeling surface, no rule card, event-anchored (never
"label this candle"), join on timestamp, VISUAL claim, never
`TradingView_state`. F-019…F-043 are out of scope.

## Instrument & universe (frozen)

- Corpus: `data/mt5/XAUUSD_M15.csv` (47,275 bars, 2024-05-22 → 2026-05-21
  broker). **Frozen. Not re-fetched. Not extended.**
- Engine ground truth: `STATE_TRANSITION` events in
  `results/htf_objective_shadow/two_year/off/run_20260816_074305_XAUUSD/XAUUSD_events.jsonl`
  (byte-identical transition counts to
  `results/g001_baseline_f074on/run_20260815_155428_XAUUSD/XAUUSD_events.jsonl`:
  399 DISPLACEMENT, 148 EXPANSION of which 142 `DISPLACEMENT→EXPANSION`
  and 6 `SWEEP→EXPANSION`, 24 RETEST).
- **Join on `timestamp`, never `candle_index`.**
- Direction for DISPLACEMENT comes from the companion `SWEEP` event or
  the same-timestamp trace `crt.direction`. Missing direction → drop that
  item and report it; do not guess.
- In-repo TradingView shots do **not** overlap this corpus (Experiment 1
  month starts 2026-07-07; this file ends 2026-05-21). Capture, when
  later authorized, is a **new** campaign. This prereg does not authorize
  capture by itself.

## Questions (frozen wording — Experiment 1 V2 / V3 verbatim)

Only two scored questions. RETEST's V4 is **not asked**. SWEEP's V1 is
**not scored** (Experiment 1 already measured it on a different corpus).

| # | Question shown | Options | Scored against | Metric |
|---|---|---|---|---|
| D1 | Is the marked bar a strong directional push away from that spike? | Up / Down / Neither | engine `DISPLACEMENT` + direction (LONG→Up, SHORT→Down) | Cohen's κ (linear-weighted; Down < Neither < Up) |
| D2 | Does the marked bar carry that push further in the same direction? | Yes / No | engine `EXPANSION` | Cohen's κ |

Wording is copied from Experiment 1 V2 / V3 so a later comparison is not
a question-rewrite. No thresholds. No state names on the page.

Plus per item: confidence (HIGH / MEDIUM / LOW) and free-text visible
evidence.

## Two arms (frozen)

Same isolation as Experiment 1, because D1 refers to a prior spike. If
that level is invisible, disagreement is the known envelope confound, not
new information about displacement logic.

| Arm | Image |
|---|---|
| Arm 1 | Bare 48-bar crop. Neutral tick outside the plot. |
| Arm 2 | Identical crop plus **one** unlabelled, neutral horizontal line at the episode's sweep price (the extreme the displacement is supposed to leave). No state names, no direction colour. |

If the sweep price is missing, Arm 2 is not generated for that item and
the item is reported as `arm2_unavailable` — not scored as disagreement.

Arm 1 and Arm 2 labelled by **different** cold agents. Batching within an
arm is allowed (Experiment 1 disclosed deviation); no agent crosses arms.

## Sample (frozen)

- **Positives:** every `STATE_TRANSITION` with `state_to ∈ {DISPLACEMENT, EXPANSION}`
  on the frozen events file (399 + 148). Not a subsample. No post-hoc
  thinning.
- **RETEST events are not items.** They stay in the census table as
  n=24 / INSUFFICIENT. Including them as scored rows would be a floor
  rewrite. Not done.
- **Controls:** equal number of `action == NONE` bars, matched on session
  and candle-range percentile, seeded.
- Seed recorded in the manifest. Default seed `20260818`.
- Opaque hashed filenames. 48-bar context, no lookahead. ≥ 8 px/candle
  or fail closed.
- **Coverage is not disagreement.** A window TradingView will not frame,
  or that lands below 8 px/candle, is dropped from the κ denominator and
  counted as coverage. If the captured-and-legible count for
  DISPLACEMENT or EXPANSION falls below 30, that cell is `INSUFFICIENT`
  — the ≥30 floor still binds after capture loss.

## My predictions (frozen before any label)

Informed by Experiment 1: drawing an engine level did **not** produce
κ ≥ 0.65 on SWEEP. This prereg does not recycle that claim.

| Cell | Prediction |
|---|---|
| D1 DISPLACEMENT, Arm 1 | κ ∈ [0.15, 0.40] |
| D1 DISPLACEMENT, Arm 2 | κ ∈ [0.25, 0.50] |
| D1 Arm2 − Arm1 | ∈ [0.00, +0.20] — some information in the sweep line, not a large decomposition |
| D2 EXPANSION, Arm 1 | κ ∈ [0.10, 0.35] |
| D2 EXPANSION, Arm 2 | κ ∈ [0.15, 0.45] |
| RETEST | unmeasured / INSUFFICIENT by construction (n=24) |
| Controls, Arm 1, D1 | observer-positive (Up or Down) on silent bars ≤ 15% — Experiment 1's ≥20% sweep-call prediction failed (4.5%) |
| LLM-vs-human ceiling | must be a scored cell (minority ≥ 15) before any engine conclusion; predicted κ ≥ 0.50 if that floor is met |

## User's predictions

- File: `docs/research/visual-crt-disp-exp-user-predictions.SEALED.md`
- SHA-256 at seal time: `4e52b25e9df8c0bc9d96d667a5acf866641dae22dae9b27b5e4cff6e005ef4a7`

No item is generated, and no capture is run, until that slot holds a
64-hex digest.

## Pre-registered interpretation

- **Arm 2 high and delta at the top of the predicted band** → given the
  sweep level, displacement classification is the more faithful of the
  two arms. Still not an engine defect either way. Not G001.
- **Arm 2 also low (below its predicted floor) and the human ceiling on
  that question is a scored κ ≥ 0.5** → only then a §6.8 review of
  displacement/expansion *meaning*. Experiment 1 did not authorize that
  review for SWEEP because the ceiling was INSUFFICIENT; the same gate
  applies here.
- **Ceiling INSUFFICIENT or < 0.5** → no conclusion about the engine
  from that question.
- **Captured n < 30 for a class** → `INSUFFICIENT`, never a null.
- **RETEST** is not a cell. Do not report a RETEST κ.

A paired Arm1→Arm2 change is **not** a causal effect: different agents
label the two arms (Experiment 1 lesson).

## Order of operations (frozen)

1. This document is written with my predictions in the clear.
2. User seals predictions; SHA-256 is recorded here.
3. Capture is a **separate authorized step** (not this document).
   Event-centered, live-market edges, `frame_shot` two-sided assertion
   not loosened. Coverage losses recorded.
4. Sampler generates blinded Arm 1 / Arm 2 items from captured shots
   only. Manifest is the answer key; labeling surfaces never see it.
5. Different cold agents label the two arms. User adjudicates a
   **stratified** ~30-per-class subsample (not a uniform 30 — Experiment 1's
   uniform 30 left V1 minority=2). Stratify on engine D1 / D2 positives
   so the ceiling can actually score.
6. Scorer reuses `build_confusion`. Verdict token:
   `RENDERED_PENDING_HUMAN_ADJUDICATION` until the ceiling is a scored
   cell; then still a VISUAL claim, never self-certified.
7. Sealed SHA re-verified, then opened. Findings gated. Default: no new
   F-id.

## Authority

Research/docs only. Grants no production, no G001, no CRT re-closure,
no RETEST result, and no permission to treat 24 as ≥30.
