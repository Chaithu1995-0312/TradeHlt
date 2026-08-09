# Plan — Candle-State Edge Discovery: Non-Directional Transition Frontier (Program 4b)

## Context

The user proposed a "candle-state edge discovery engine" (state encoding × multi-timeframe ×
RR × holding period sweep) hunting a ≥70% win-rate edge, with a strong falsification-discipline
checklist. Reconnaissance (3 Explore agents) established three things that reshape the build:

1. **The discipline is already built.** The proposed `hypothesis_runner.py` / `walk_forward.py` /
   `monte_carlo.py` / `permutation_test.py` / `report_generator.py` map 1:1 onto existing,
   battle-tested modules: `HypothesisRunner` ([runner.py](src/research/runner.py)), `forward_walk()`
   with hard no-lookahead asserts ([forward_walk.py](src/research/measurement/forward_walk.py)),
   `EdgeAggregator` ([metrics.py](src/research/measurement/metrics.py)), and a 7-gate
   `QualificationGate` ([qualification.py](src/research/qualification.py)) that already enforces
   NET-of-cost expectancy, PF, beats-control, OOS retention, permutation p≤α, and Benjamini-Hochberg
   FDR. Rebuilding them violates the repo's "never reinvent existing patterns" rule.

2. **Most of the proposal is already falsified.** Program 1 is formally **KILLED**
   ([program-1-closure-2026-06-13.md](docs/analysis/program-1-closure-2026-06-13.md)). 7 of 10
   proposed hypotheses are already answered: directional next-bar candle prediction (F-019/020/021/
   025/027/035, crypto **and** FX), morphology clustering (F-023, all clusters win≈34%/mean_R≈0),
   continuation-after-sweep (F-026). Re-running these is named-forbidden "archaeology."

3. **Data reality:** M15-only on disk, 2yr, 12 symbols; resampler goes **upward only** (M15→H1/H4).
   No M5 → the M5-based proposed hypotheses cannot run without a fresh MT5 fetch.

**User mandate (confirmed):** NEW FRONTIER ONLY · M15-base only · expectancy-first gate with
WR/streak/rolling-10 as reporting-only · reuse the kernel, build only the missing pieces.

**Intended outcome:** a small additive layer that tests the *genuinely-untested, reopen-legal*
frontier — **multi-timeframe state conjunction (M15∧H1∧H4)** and **compression→expansion
TRANSITION forecasting (non-directional targets)** — pre-registered per the Epistemic Integrity
ritual, run through the unchanged qualification machinery. Likely high-knowledge-ROI outcome:
Stage-1 information may exist while Stage-2 economic consumption fails (consistent with F-030);
that null is a valid, valuable result, not a failure of the build.

---

## Architecture: two-stage gate (respects the §6.5 Authority Ladder)

Non-directional forecasts (predict vol/range expansion) are **Authority-Ladder Level 1
(information)**, not Level 2 (economic). They cannot flow directly through the trade-outcome
QualificationGate. So:

- **Stage 1 — Information gate (non-directional).** Does a candle-state conjunction / compression
  state carry predictive information about *forward* volatility/range expansion? Measured with
  mutual information + permutation, reusing
  [process_diagnostics.py](src/research/process_diagnostics.py) (`mutual_information`,
  `direction_conditional_entropy`) and
  [conditional_entropy_grid.py](src/research/conditional_entropy_grid.py)
  (`partition_stat`, `permutation_pvalue`, `candidate_cells`). Authority: **research/docs only.**
- **Stage 2 — Economic gate (only for Stage-1 survivors).** Convert a surviving conjunction into a
  *tradeable* Hypothesis (a compression→expansion **breakout** construction — enter the first range
  break after a predicted-expansion compression) and run it through the **unchanged**
  `HypothesisRunner` + `QualificationGate` (intrabar_fixed exit, 12bps). Promotion is
  expectancy-first; WR is reported, never promotes alone.

**No-lookahead** is automatic: the multi-TF state is computed inside `detect()` from the M15
`window` (past+current only); `resample()` drops the in-progress HTF bucket so only *closed* H1/H4
candles are ever visible.

---

## Files to create (all additive; the runner/gate/forward_walk are NOT modified)

New subpackage `src/research/candle_state/`:

- `__init__.py`
- `encoder.py` — **`CandleStateEncoder`**: pure fn, candle list → discrete state label
  (BULL_STRONG/BULL_WEAK/BEAR_STRONG/BEAR_WEAK/DOJI/EXPANSION/COMPRESSION/INSIDE_BAR/OUTSIDE_BAR)
  + continuous features (body%, upper/lower wick%, volume z-score, ATR ratio, range-expansion
  ratio). Reuses `bar.body_ratio`/`is_bullish` and [indicators.py](src/research/indicators.py)
  (`atr`, `sma`). No new feature registry — keep it local and pure.
- `mtf_conjunction.py` — **`MultiTFConjunctionBuilder`**: M15 window → resample to H1/H4 via
  [resample.py](src/research/resample.py) → encode each TF's last *closed* candle → conjunction key
  (e.g. `"M15=COMPRESSION|H1=UP|H4=BULL"`). Pure, no-lookahead.
- `transition_target.py` — non-directional **forward** target labelers: vol-expansion
  (`ATR_{t+1..t+k}/ATR_t > θ`), range-expansion, regime-transition flag. Used by Stage 1 only.
- `reporting.py` — additive reporting-only helpers consuming `list[Outcome]`:
  `streak_metrics` (max losing streak), `rolling_window_metrics(window=10)`, WR rollup.
  **Never** feeds the gate.

New hypothesis (Stage 2), registered into the **existing** `HYPOTHESIS_REGISTRY`:

- `src/research/hypotheses/compression_breakout.py` — the tradeable transition consumer.
  This *is* the user's "TransitionHypothesisRegistry" realized via the existing
  `register_hypothesis()` plugin (no parallel registry — convention).

Drivers (thin CLI wrappers, business logic in modules):

- `scripts/research/transition_information.py` — Stage 1 information gate.
- `scripts/research/qualify_transitions.py` — Stage 2 economic gate (mirrors
  [qualify_majors.py](scripts/research/qualify_majors.py)).
- `scripts/research/candle_state_report.py` — consolidated evidence table incl. **failures**
  (the user's FULL_RESULTS.csv / EDGE_SUMMARY.md, written under `results/research/candle_state/`).

Governance / docs (per Epistemic Integrity ritual, written BEFORE running):

- `docs/research/preregistration-program-4b.md` — the 6-question pre-registration check
  (artifact, INSUFFICIENT-explanation, sign-noise, statistical-vs-economic, parent-vs-children,
  raw-counts) for each transition hypothesis. **Mandatory before any finding is registered.**
- On results: add **F-040** to [current-findings.md](docs/current-findings.md) + the §6.2
  Repository Truths Index in CLAUDE.md (same turn), plus a memory file.

Tests `tests/research/`:

- `test_candle_state_encoder.py` — vocabulary correctness + determinism + pure (no lookahead).
- `test_mtf_conjunction.py` — resample-causality (only closed HTF bars visible), determinism.
- `test_transition_information.py` — MI/permutation kernel wiring + seeded determinism.
- `test_compression_breakout.py` — Signal emission + no-lookahead (entry_index guard).
- `test_reporting_metrics.py` — streak/rolling-10 correctness; assert reporting never alters verdict.

---

## Scope guards (doctrine compliance)

- **NEW frontier only.** Only the compression→expansion transition + MTF conjunction (non-directional
  targets) are promotion candidates. No SL/TP grids, entropy partitions, session sweeps, or
  directional candle-pattern searches with tweaked thresholds.
- **Clean-room replication = documentation only, ~zero new code.** A single labeled section in the
  report re-runs the existing toy pool via the *existing* `qualify_majors.py` to document
  reproduction of the F-019 null — explicitly NON-PROMOTABLE.
- **M15-base only.** M15 native + H1/H4 derived. No synthetic M5; M5 research requires an explicit
  MT5 fetch + new on-disk corpus (out of scope here).
- **Expectancy-first.** Existing 7-gate `QualificationGate` is the sole promote authority
  (intrabar_fixed + 12bps, matching every prior falsification for comparability). WR≥70% /
  max-streak≤3 / rolling-10 are reported alongside, never gating.

---

## Verification

1. `pytest tests/research/ -q` — new tests green; run twice to confirm byte-identical artifacts
   (determinism). Confirm reporting-metric test proves verdict-invariance.
2. **No-lookahead proof:** unit test feeds a window and asserts the MTF builder never sees an
   HTF bar overlapping the current M15 bar; `forward_walk`'s existing index assert covers Stage 2.
3. **Stage 1 run:** `python scripts/research/transition_information.py` on crypto majors → MI +
   permutation p per conjunction; record which (if any) clear the floor.
4. **Stage 2 run (only Stage-1 survivors):** `python scripts/research/qualify_transitions.py` →
   per-instrument + pooled M4 verdict.
5. `python scripts/research/candle_state_report.py` → consolidated CSV/MD incl. all failures.
6. Pre-register (doc) BEFORE step 3; on results, file F-040 + Repository Truths Index + memory,
   same turn. Append the §6 SESSION LOG entry.

## Most likely result (set expectation)

Stage-1 information PLAUSIBLE (vol has memory: H_atr=0.885, F-030), Stage-2 economic PASS
UNLIKELY (F-030: vol predictable but non-consumable in spot long/short; F-025: bottleneck is entry
information). A Stage-1-PASS / Stage-2-FAIL outcome is the high-knowledge-ROI result and closes the
last reopen-legal directional-adjacent frontier cleanly — it is the expected, valuable deliverable,
not a failure.
