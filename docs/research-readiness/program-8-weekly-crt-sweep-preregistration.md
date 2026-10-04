# Program 8 — Weekly CRT Sweep (FX majors, Direction×Vol 3×3 diagnostic) · PRE-REGISTRATION

> **Program 8 tests the ICT/CRT weekly liquidity theory: Monday+Tuesday form an accumulation
> range; a Wednesday-Friday sweep of that range (a stop-hunt) resolves into the real directional
> move in the OPPOSITE direction of the sweep. This is a genuinely NEW ontology (weekly, not
> next-bar/M15-local) — it is NOT a reopen of Program 1 (F-019...F-025, next-bar directional,
> KILLED) or Program 2 (F-026, structural sweep→displacement→retest asymmetry, FROZEN); both of
> those tested intraday/local-range structure, never a weekly-calendar accumulation range.**

Status: **PRE-REGISTERED — design frozen, NOT yet run** · Date: 2026-07-01 · Branch: `patch`
Governance: reuses the M4 gate verbatim (`src/research/qualification.py`) + CLAUDE.md §6.2
Epistemic Integrity ritual (E-001) + §6.5 Authority Ladder. **No finding number is assigned
here** — F-042 is minted only once this is run and read.

**Naming note:** "Program 7" is already promised (prose-only, no header) to crypto Open
Interest in the F-033/F-034 notes and the Program 6 header's Reopen Conditions
(`docs/current-findings.md:460,472,689`). This initiative is **Program 8** everywhere, leaving
that promise untouched (per explicit user decision, 2026-07-01).

---

## 1. The question

*Does a Monday+Tuesday accumulation range, swept on Wednesday-Friday, predict a forward move in
the direction OPPOSITE the sweep (the classic "judas swing" / stop-hunt-then-reverse reading),
net of realistic costs, on FX majors?* This is tested as a directional CONSUMER hypothesis
(`weekly_sweep_reversal`) through the frozen M4 QualificationGate — identical machinery to every
Program 1–6 pass, no new statistics.

## 2. Construction

- **Accumulation range** (`src/research/weekly_sweep/weekly_range.py::current_week_range`):
  `h_ref = max(high)`, `l_ref = min(low)` over the current ISO week's calendar Monday+Tuesday
  bars. **Range-lock rule:** the range is only considered formed once at least one Tuesday bar
  is present — a sweep can only fire Wednesday onward, matching the theory's own wording (no
  separate "is it Wednesday" gate is needed).
- **Sweep detection** (`detect_weekly_sweep`): `swept_high = bar.high > h_ref and bar.close <
  h_ref` (symmetric for low) — reimplements `config_layer.crt_engine_v2.RangeDetector
  .detect_sweep`'s geometry and its `short-on-high-sweep / long-on-low-sweep` convention against
  a WEEKLY range instead of CRT's local/intraday range (CRT itself has zero weekly memory).
  Weekday-gated to Wed/Thu/Fri only; a one-shot-per-boundary-per-week guard prevents the same
  boundary refiring on every subsequent bar that also closes back inside.
- **Exit geometry** (RANGE-WIDTH-DERIVED, not a flat ATR multiple): target the OPPOSITE boundary
  of the swept range (`tp_atr_mult = range_width / atr`), `sl_atr_mult = sl_range_frac *
  range_width / atr`. Requires `apply_signal_defaults: false` in the research config — the one
  field that diverges from the FX toy-family pattern, since leaving it `true` would let
  `HypothesisRunner.run_instrument()` silently overwrite this geometry with flat defaults.
- **Week-validity guards:** (a) `min_accumulation_bars` — a holiday-shortened-week bar-count
  floor; (b) `max_intraweek_gap_minutes` — a NEW guard closing a blind spot the bar-count floor
  alone would miss: an internal data outage (e.g. a 3-hour Monday dropout) could still clear the
  bar-count threshold while silently understating the true weekly high/low, so any
  consecutive-bar gap inside the Mon+Tue accumulation window exceeding this threshold invalidates
  the week; (c) `is_week_structurally_valid` (optional, `check_week_validity`) — a
  broker-calibrated veto using `data_ingestion.session_autoderive.derive_weekly_mask` /
  `is_tradable_by_mask`, computed once per instrument in the driver and passed down.

## 3. Direction×Volatility 3×3 diagnostic (informational only — NOT a second gate)

Split-axis encoding (corrected during design review — see §7 permutation caveat for the
analogous statistical-scope correction):
- **Direction axis** — `CandleStateEncoder.encode(window).direction` (5-state, collapsed to 3
  buckets — BULL/BEAR/DOJI — only in the driver's reporting layer).
- **Volatility axis** — `RegimeLabeler` (`interpreters.regime_observer`), reconstructed with a
  WIDENED `tercile_window` (config `regime_tercile_window`, ~2000 M15 bars ≈ 20 trading days),
  deliberately NOT `CandleStateEncoder`'s own bundled `.vol` field, which classifies from a
  single bar's true range against a short 14-bar trailing ATR — a local/noisy measure, not a
  macro-liquidity baseline. `RegimeLabeler`'s own default `tercile_window` (480, ≈1 week) is also
  too short for this program's intent and is explicitly overridden.

The raw (uncollapsed) `"{direction}/{vol}"` token is stored in `Signal.meta` at detection time;
the driver computes, per collapsed 3×3 cell, `n`/`wins`/`profit_factor`/`expectancy_rr` on the
SAME outcome population already produced by the M4-gated run — no permutation test, no BH
correction, no OOS split per cell (small-N would make per-cell significance meaningless). This
mirrors Program 6b's diagnostics-appendix discipline: **a component/breakdown of a result must
never receive more authority than the result being decomposed** (Authority Ladder, §6.5).

## 4. Universe, data, cohort (FROZEN — no parameter search)

The 5 FX majors already qualified for F-035: **EURUSD, AUDUSD, EURCAD, GBPUSD, USDJPY** (XAUUSD
excluded — it REJECTs the FX-tuned dataset-integrity gap gate, same rationale as F-035). Data
reused verbatim from `data/*_M15.csv` — no refetch. Single candidate, single config family (no
spine arm — the spine's own SL/TP geometry and CRT-only-by-design scope, F-037, make a
spine-vs-weekly_sweep comparison out of scope for this pass):

| name | family | authority |
|---|---|---|
| `weekly_sweep_reversal` | structural | TRADEABLE (BH cohort of 1) |

Fixed parameters (`configs/research/research_config_weekly_sweep.json`): `min_accumulation_bars
= 40`, `sl_range_frac = 0.25`, `atr_period = 14`, `max_intraweek_gap_minutes = 30`,
`regime_tercile_window = 2000`, `check_week_validity = true`, `window_size = warmup = 2200`
(widened from the FX-toy 64 to see both a full ISO week and the regime baseline),
`max_forward = 200` (~2 trading days, an approximation of "the rest of the week" — the frozen
`forward_walk` machinery has no variable per-signal horizon concept; accepted as a documented
limitation, not a reason to modify frozen measurement code).

## 5. Controls (gate 4 must beat the WINNING control)

The 3 standard falsification controls already registered platform-wide: `random_uniform`
(50/50), `random_biased_70` (70/30), `always_long`.

## 6. Gates (M4 — reused VERBATIM)

`evaluate_pre_bh` → cohort BH (trivially size 1) → `finalize`: (1) n≥30 else INSUFFICIENT · (2)
E≥0 · (3) PF≥1 · (4) beats the winning control · (5) 70/30 OOS retention (IS>0, OOS>0,
OOS/IS≥0.5) · (6) permutation p≤0.05 · (7) BH FDR 0.05. Costs 12bps round-trip, n_perm 2000,
α 0.05, oos_split 0.3 — identical to F-035's FX config for direct comparability.

## 7. Pre-registered priors & forbidden claims (E-001)

**Expected outcome = REJECT or INSUFFICIENT** (per-instrument scopes are likely INSUFFICIENT —
weekly cadence produces far fewer signals than any prior M15-bar program, and `q_min_samples=30`
stays unchanged, no gate-tuning; POOLED is the primary decision-bearing scope). This continues
the F-019→F-041 track record of directional-consumer nulls under the intrabar_fixed+12bps
standard — recorded BEFORE the run. No "the weekly theory works" claim until the gate speaks;
**edge = UNKNOWN until then.**

**Permutation-test scope caveat (verified against `qualification.py:94-128` during design
review):** the M4 gate's permutation test is an exact two-sample permutation over per-*outcome*
(per detected weekly-sweep event) RR values, shuffling the hypothesis/control label across the
pooled outcome set — deterministic, seeded. It is **Level-4A-equivalent** (a naive-shuffle
falsification floor): it can reject pure noise, but because it treats outcomes as exchangeable
events it **cannot by itself** distinguish "genuine weekly-sequence alpha" from "outcomes
clustering because several consecutive weeks shared one market regime." **A PROMOTE verdict
would require follow-up scrutiny (e.g. a whole-week block-bootstrap) before being read as proof
of the specific weekly mechanism — not built in this pass, triggered ONLY if this program
unexpectedly PROMOTEs.** A REJECT/INSUFFICIENT (the expected outcome) is unaffected by this
caveat.

**No parameter archaeology.** This program's fixed parameters (§4) — the geometry construction,
the reversal-not-continuation choice, the range-width-derived exit, the FX universe, the cost/gate
constants — are forbidden reopen routes if this REJECTs ("Program 8 with a bigger
min_accumulation_bars / different sl_range_frac / continuation instead of reversal" is
archaeology). A `weekly_sweep_continuation` variant is explicitly OUT OF SCOPE for this pass — a
separate, not-automatic decision, not a rescue of a REJECTed reversal result.

## 8. Determinism & isolation

Pure stdlib + research-internal imports; sorted instruments; RNGs seeded from stable strings
(`_seed_for(hypothesis_name)`); the JSON body carries NO wall-clock (separate `_manifest.json`)
→ byte-comparable across runs. The only new code is additive: `src/research/weekly_sweep/`
(new package) + `src/research/hypotheses/weekly_sweep_reversal.py` (new file) +
`scripts/research/qualify_weekly_sweep.py` (new driver). No changes to `runner.py`,
`qualification.py`, `costs.py`, `forward_walk.py`, `regime_observer.py`, or
`candle_state/encoder.py`. Research authority only (§6.5); no production/fusion weight even on
a PROMOTE.

## 9. Research Envelope

| field | value |
|---|---|
| Ontology | Weekly liquidity-sweep (ICT/CRT), ISO-week Mon+Tue accumulation range |
| Universe | 5 FX majors, M15 (same corpus as F-035) |
| Signal source | `research.weekly_sweep.weekly_range` (new, pure, no-lookahead geometry) |
| Costs | 12 bps round-trip |
| Statistics | permutation (2000, per-outcome, Level-4A-equivalent) + BH (cohort of 1) + 70/30 OOS |
| Controls | random_uniform, random_biased_70, always_long |
| Decision | INSUFFICIENT / REJECT / PROMOTE |
| Diagnostic (non-authoritative) | Direction×Vol 3×3 breakdown (CandleStateEncoder direction × RegimeLabeler macro volatility) |
| Authority if PROMOTE | research only (§6.5); permutation-scope caveat applies (§7) |
| Out of scope | continuation variant; any further threshold/window sweep; spine comparison |
