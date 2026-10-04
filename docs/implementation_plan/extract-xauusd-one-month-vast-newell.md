# Visual CRT State Fidelity — engine states vs. what an independent observer sees on the chart

> **Prior work in this session (COMPLETE, shipped):** the XAUUSD one-month OHLC odds comparison —
> 100% M15 coverage, 99.15% agreement, 30/30 divergences on the daily-open bar, F-080's
> double-counted denominator corrected to 1,378/21. Artifacts: `reports/xauusd_month_tv_engine_odds.md`,
> `scripts/research/tv_engine_odds.py`. **That work is done and is not revisited here.**

## Context

The odds comparison tested whether *the same numbers* appear on both feeds. It cannot detect a state
machine that is internally consistent but semantically wrong — it feeds the engine its own rules
twice. This plan tests a different thing:

> **Does the deterministic engine's CRT classification correspond to what an independent observer
> can actually see on the TradingView chart?**

Three findings from exploration reshape the design, and the plan is built around them:

**1. "What state is this candle" has no answer.** CRT state is path-dependent.
`configs/formulas/market_crt_states.yaml`'s own header states that memory-requiring states *"cannot
be resolved from a single bar's feature vector alone"*, and F-069 is the empirical proof — a per-bar
predicate resolver reproduces the engine at **10.77% EXPANSION recall**. `process_candle`
(`crt_engine_v2.py:2859`) dispatches on `state.current_state`, so an identical bar is evaluated
against completely different predicates depending on the path. The comparison must therefore ask
about **events at a marked bar given visible context**, in trader language, never "label this candle."

**2. The dominant confound is already measured and it is large.** The engine's swept envelope is a
trailing 14/16-bar count-window extreme (`m15_structural_range.py::from_child_window`), rebuilt on
every reset — not a level anyone would draw. `reports/monthly_tv_vs_active_production_semantic_comparison.md`
already scored this month's 84 sweeps against chart-visible levels: **5 of 84** align tightly with a
production SMC level, **51 of 84 touch no SMC level at all**, 30/84 match a prior closed H4 high/low.
A bare-chart observer will therefore disagree with most sweeps for a *known structural reason*. The
two-arm design below exists specifically to separate that cause from genuine classification
disagreement; without it the experiment mostly re-measures something already known.

**3. Only ~23% of the month is legibly captured.** Pixels-per-candle is exactly `1743 / n_bars`.
Shots 04/07/08/14 are ≥8px; the four wide shots covering the rest are 3.2–5.6px and are unusable for
per-candle work *by design* (`shot_plan.json` says so three times). Cropping cannot rescue them —
a crop is a crop. Re-capture narrow.

**Authority:** research/docs only. Grants no production, economic, or promotion authority (§6.5).
Descriptive fidelity is Authority-Ladder *"information exists"* and nothing more.

---

## Decisions taken (confirmed with user)

- **Two arms**: bare chart AND the same bars with the engine's range level drawn (states never shown).
- **Event-anchored sample + blind controls** (controls are non-optional — without them only agreement
  on engine-positives is measurable, and events the engine *missed* are undetectable).
- **Fresh cold subagents classify; user adjudicates a random subsample** to establish a reliability ceiling.
- **Full pre-registration with sealed user predictions**, cloning `docs/research/preregistration-blind-label-descriptive-fidelity.md`.

---

## A pre-declared limit, stated before anything is built

The month contains **2 RETESTs and 6 EXPANSIONs**. Under the `< 15 minority-class instances →
INSUFFICIENT` rule those cells **cannot produce a result at any effort level**, and DISPLACEMENT
(n=19) is marginal. Only **SWEEP (n=84)** can carry a real number. This is a property of the corpus,
declared now so a thin cell cannot later be presented as a null (E-001: underpowered ≠ negative).
TradingView history exists only for this month, so extending n means a new capture campaign on a
different window — out of scope here.

---

## Phase A — Pre-registration (before any image is generated)

Write `docs/research/preregistration-visual-crt-state-fidelity.md`, cloning the structure and the
frozen "Order of operations" of the existing prereg. It must freeze:

**The four questions** — trader language, no thresholds, no CRT vocabulary. The existing prereg's
doctrine governs here: asking *"did the high exceed h_ref while the close came back below it"* would
make the labeler a slow computer and measure nothing. **No rule card with engine thresholds is given
to the classifier** — the definitional collision *is* the measurement.

| # | Question shown | Options | Scored against |
|---|---|---|---|
| V1 | At the marked bar, did price spike beyond a prior extreme and then close back inside? | Above / Below / Neither | engine `SWEEP` + direction |
| V2 | Is the marked bar a strong directional push away from that spike? | Up / Down / Neither | engine `DISPLACEMENT` + direction |
| V3 | Does the marked bar carry that push further in the same direction? | Yes / No | engine `EXPANSION` |
| V4 | Has price come back close to the level it originally broke? | Yes / No | engine `RETEST` |

Plus per item: **confidence** (HIGH/MEDIUM/LOW) and **free-text visible evidence** — the mismatch
dossier fields (body/wick structure, relation to previous candle, location within the drawn range).

**My predictions, in the clear** (falsifiable, recorded before any label exists):

| Cell | Prediction |
|---|---|
| V1 SWEEP, Arm 1 (bare) | κ ∈ [0.15, 0.35] — most swept levels are invisible |
| V1 SWEEP, Arm 2 (level drawn) | κ ≥ 0.65 |
| **V1 Arm2 − Arm1 delta** | **≥ +0.30** — the load-bearing prediction; this is the decomposition |
| V2 DISPLACEMENT | Arm 1 κ ∈ [0.30, 0.50]; Arm 2 κ ∈ [0.45, 0.65]; likely reported INSUFFICIENT at n=19 |
| V3 / V4 | INSUFFICIENT by construction (n=6, n=2) |
| Controls, Arm 1 | observers call a sweep on ≥20% of engine-silent bars — the false-negative channel |
| LLM-vs-human ceiling | κ ≥ 0.55, below the 0.75 the feature-level prereg predicted (states are harder) |

**Pre-registered interpretation** (fixed now):
- Arm 2 high, Arm 1 low, delta large → engine classification is faithful *given its own level*; the
  divergence from a chart reading is **level choice, not state logic**. Doc/finding about level
  visibility; **no engine defect**.
- Arm 2 **also** low → the state logic diverges from an observer given the *same* level. This is the
  only branch that would warrant a §6.8 semantic review.
- High observer-positive rate on controls → engine misses chart-visible sweeps. Information about
  **coverage**, not correctness.
- Ceiling < 0.5 on a question → that question is ambiguous for this classifier; **no conclusion about
  the engine** is drawn from it (guard against blaming the engine for a badly-posed question).
- Any cell < 15 minority instances → `INSUFFICIENT`, never a null.

Then: user writes `docs/research/visual-crt-user-predictions.SEALED.md`; I record its SHA-256 in the
prereg **before** any item is generated, and do not open it until scoring is complete.

## Phase B — Legible capture

Add a `month-legible` preset to `tools/tv_forensic/shot_plan.json`: ~19–24 M15 shots of **~150–160
bars each with ≥50-bar overlap**, tiling the full 2,116-bar corpus at ~11px/candle (proven legible —
shot 04 reads fine at 8.63). Overlap guarantees every item has a full 48-bar context window inside a
single shot.

Run as **one invocation** (`--preset month-legible`): `calibrate_clock` runs once per invocation
(`capture_tv.py:710`) and `bridge.setup` no-ops while symbol+interval are unchanged, so batched cost
is ~30–45s fixed + ~10s/shot ≈ **5–8 min**, versus 30–40 min as one-off invocations.

Two known hazards, both already documented in the tool: `frame_shot`'s two-sided assertion
(`capture_tv.py:213-225`) **aborts the whole run**, not one shot — and it has permanently defeated
`02_h4_july_setup`. Put every edge on a live-market bar (the shot-02 defect was an *edge* in a gap,
not an internal weekend). **Do not loosen the assertion**; narrow and split on refusal, and record it.

## Phase C — Item generation (blinded, seeded)

New `scripts/research/visual_state_sample.py`, modelled on `scripts/analysis/blind_label_sample.py`
(whose manifest-as-answer-key pattern and mechanically-tested blinding are the precedent to copy).

**Engine ground truth** — join on `timestamp`, **never** `candle_index` (bases differ by a constant
per-run offset; `crt_state_confusion_matrix.py::remap_event_indices_to_ohlcv:96` exists for exactly this):
- Events: `results/htfcrt_1month_parent_wired/run_20260816_011239_XAUUSD/XAUUSD_events.jsonl` (active
  config, parent-CRT wired; 84 SWEEP / 19 DISP / 6 EXP / 2 RETEST).
- Per-bar range level for Arm 2: `results/crt_survey_trace/20260815T062829Z/trace.jsonl`
  → `crt_inputs.active_range.h_ref / l_ref`.
- **Fail closed on a config mismatch.** These two artifacts come from different runs. Verify the state
  sequences agree on shared timestamps before using them together; if they disagree, re-run
  `scripts/analysis/xauusd_excel_feature_state_trace.py --csv data/XAUUSD_M15.csv` against the active
  config rather than reconciling by hand. The known 85-vs-84 sweep delta is explained (one sweep sits
  inside the 78-bar backtest warmup) and is not a mismatch.

**Sample**: all 111 engine transitions + ~111 controls drawn from `action == NONE` bars, **matched on
session and candle-range percentile** so controls are not trivially distinguishable from positives.
Seeded RNG, seed recorded in the manifest. Presentation order shuffled. Items carry **opaque hashed
filenames** (`item_a3f9c2.png`) with no timestamp or instrument in the name.

**Two renders per item**, from the same crop:
- **Arm 1** — bare crop, 48-bar context, marked bar indicated by a neutral tick outside the plot area.
- **Arm 2** — identical crop plus two **unlabelled, neutral-coloured horizontal lines** at `h_ref` /
  `l_ref`, drawn via `annotate.py`'s `Frame.y_of` (`:93-101`) off the sidecar `plot.price_calibration`.
  No vertical event markers, no state names, no direction-encoding colours.

Crop geometry from the sidecar: `bars[].x` for time→x, `plot.rect` for bounds — the same mapping
`annotate.py` consumes, so nothing new is derived.

`manifest.json` is the answer key and is **never referenced by any labeling surface**.

## Phase D — Classification

**Arm 1 and Arm 2 must be labelled by different cold subagents.** Reusing one agent across arms
anchors Arm 2 on Arm 1 and destroys the delta — which is the load-bearing measurement.

Each subagent receives **only** the image path and the frozen question text. It is instructed not to
read repo artifacts. **Disclose honestly:** unlike `blind_label_sample.py`, where the HTML
mechanically contains no answers, subagent blinding is **procedural, not mechanical** — a tool-using
agent could in principle look. Hashed filenames make accidental lookup much harder but do not
eliminate the hole. The user-adjudicated subsample *is* mechanically blind, which is part of why it matters.

Then: the user adjudicates a random ~30-item subsample → **LLM-vs-human ceiling**. Bulk numbers are
reported as a fraction of that ceiling, never at face value.

## Phase E — Scoring and report

New `scripts/research/visual_state_score.py`. **Reuse `build_confusion`**
(`scripts/research/crt_state_confusion_matrix.py:601`) — it is generic over two aligned label lists
plus `source_indices` and accepts a visual column verbatim; only a CSV loader shim is needed. Do not
reimplement the matrix.

Outputs: per-question Cohen's κ (linear-weighted where ordinal) per arm; the **Arm2−Arm1 delta**;
per-state recall/precision; control false-positive rate; κ reported both pooled and split on an
`overlaps_prior_item` flag (event-anchored items cluster, so context windows overlap and answers are
not fully independent — mirroring how the existing prereg splits Q4 on off-screen references); and a
**mismatch dossier** per disagreement in the format you specified (engine / visual / OHLC-match /
confidence / visible evidence).

Report to `reports/xauusd_visual_crt_state_fidelity.md`. Every conclusion records
`engine_state`, `visual_state`, `visual_confidence`, `visual_evidence` — **never** a column called
`TradingView_state`, because TradingView declares no state.

## Phase F — Governance

1. `BUILD_IMPACT_MANIFEST` → `docs/governance/build_manifests/CH-visual-crt-state-fidelity.impact.json`, `OBSERVATION_ONLY`.
2. `tests/test_visual_state_harness.py`: blinding (no answer reachable from any labeling surface),
   determinism under seed, and a scorer that **distinguishes perfect from random labels**. Each floor
   must be mutation-verified to fail against a leaky manifest or a degenerate scorer.
3. SITS-register both new scripts (`script_census --write-stubs` → overlay in `seed_script_registry.py`
   → `seed` → `generate_script_matrix`).
4. Open the sealed prediction file, re-verify its SHA-256 against the recorded value.
5. Findings decision is **gated** (§6.2): bring results before editing any finding. The default is
   *no new F-id* — a clean measurement is not a discovery.
6. SESSION LOG entry in `assistant_project.md`.

**Governance ceiling, stated up front:** anything read off pixels is a **VISUAL** claim under the
`smc_visual_verification.py:19-30` split — *"never self-certifies; renders the evidence and stops."*
The headline verdict will be `RENDERED_PENDING_HUMAN_ADJUDICATION`, bounded by the measured ceiling.
F-079 is the standing warning: a skipped measurement and an absent one must never look identical.

---

## Verification

```bash
python tools/tv_forensic/capture_tv.py --preset month-legible
```

```bash
python -m pytest tests/test_visual_state_harness.py tests/test_tv_forensic_smoke.py -q
```

```bash
python scripts/research/visual_state_sample.py --seed 20260818 --out-dir results/visual_crt_state_fidelity
```

```bash
python scripts/research/visual_state_score.py --labels results/visual_crt_state_fidelity/labels --out reports/xauusd_visual_crt_state_fidelity.md
```

Pass conditions, each named:
- **Legibility**: every generated item ≥ 8 px/candle; assert at generation, fail closed below it.
- **Blinding**: no item filename, image, or labeling instruction contains a timestamp, price, state
  name, or engine field; test asserts this over the whole generated set.
- **Determinism**: same seed reproduces the item set byte-identically.
- **Ground-truth join**: 100% of items resolve to an engine record by timestamp; zero index-based joins.
- **Config consistency**: events and trace artifacts agree on state at every shared timestamp, or the run aborts.
- **Control balance**: controls and positives statistically indistinguishable on candle-range percentile
  and session (report the balance check, don't assert a p-value).
- **Scorer sanity**: perfect labels → κ = 1.0; shuffled labels → κ ≈ 0.
- **Arm independence**: Arm 1 and Arm 2 label files come from different agent invocations (recorded in the manifest).

## Out of scope

No engine, config, or model change. No re-fetch of the corpus. No promotion, retrain, or CRT
re-closure. This measures **descriptive fidelity** — whether the engine's labels match what is
visible — and says nothing about predictive or economic value; F-019…F-043 answered that separately
and this cannot revise them.
