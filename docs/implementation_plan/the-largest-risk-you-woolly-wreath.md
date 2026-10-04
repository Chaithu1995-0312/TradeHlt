# Plan — Program 2 / Phase E1: trap-continuation asymmetry (structural-event population, BNBUSDT)

## Context — why this work

Program 1 (next-bar directional ontology) is **KILLED**; reopening requires a **new ontology**. The
user opens **Program 2 = conditional/structural asymmetry**, and its leading branch is the one most
aligned with the CRT architecture: **Sweep → rejection → displacement → retest → continuation.** This
is a genuinely new label space (CRT *structural state*, not candle partitions) — the one conditioning
axis F-020 never tested (F-020 used candle session×vol×momentum; F-021/F-024 measured only the ~13
*executed* retests). **No one has measured the FULL sweep→retest event population's forward asymmetry,
conditioned on structural stage × regime.**

**Honest prior: null-leaning.** F-024 found MFE≈MAE on executed retests; the in-repo momentum study
(`bnbusdt_momentum_continuation_report.md`) found MFE/MAE≈1. So the study earns **one rigorous
measurement**, with the guards that made Program-1's nulls trustworthy (matched control + stratified
permutation + OOS + measure-only). **Two corrections baked in:** (a) the pure-retest population is
small (~44 on BNB, funnel-choked at DISP→EXPANSION per F-015), so we measure the **full structural
progression** (sweep/displacement/expansion/retest) where the early stages carry the power, testing
*does asymmetry grow as the trap completes?*; (b) the **pullback branch is deferred** — the user's
"RSI≈48 winners" premise contradicts the artifact (it reports winners RSI≈69), so no pullback work
until that's reconciled. Measure-only, **BNBUSDT-first**; cross-instrument confirm only if BNB leads.

## What already exists (reuse — ~90% per the audit)

- **Structural events + telemetry** — `crt_engine_v2.py`: `CRTState` machine (SWEEP→DISPLACEMENT→
  EXPANSION→RETEST), `RangeDetector.detect_sweep` (with `crt_sweep_taxonomy`), `try_*` transitions,
  the always-on `EXPANSION_RETRACE_CHECK` telemetry (`on_expansion_ended`) and the S0-wired
  `RETEST_REPLAY` (`on_retest_replay`). A backtest writes `{INSTR}_events.jsonl` (STATE_TRANSITION
  stream w/ direction + geometry) + `{INSTR}_crt_telemetry.jsonl` — both deterministic, harvestable
  post-hoc **without re-running the engine inline**.
- **Harvest pattern** — `research.adapters.spine_signal_source.ProductionSpineSource` (runs one
  deterministic `BacktestRunner`, parses an artifact by research index = `candle_idx − 1`). Mirror it.
- **Asymmetry measurement (100% reuse)** — `research.measurement.forward_walk.horizon_excursion`
  (exit-agnostic `mfe_r`, `mae_r`, `favorable_first`, `reached_{0.5,1,1.5,2,3}r`, `bars_to_first_1r`).
- **Significance (reuse)** — `research.selection_effect.stratified_permutation_p` + `seed_for`;
  `conditional_entropy_grid.{vol_terciles,vol_label,hour_to_session}` for conditioning labels.
- **Regime (reuse)** — `regime.regime_classifier.RegimeClassifier.classify` (threshold, deterministic);
  candle-only `volatility_ratio`/`range_size`; HTF-alignment harvested from telemetry metadata.
- **Data** — `runtime.backtest_v2.CandleLoader`.
- **Must-build (light, ~200 lines):** the structural-event harvester + the asymmetry/control core.

## Approach (measure-only, deterministic)

### E1.0 — Harvest the structural-event population (one BNB backtest)
Mirror `ProductionSpineSource`: run one deterministic BNBUSDT backtest (`prod_version=v2_multi_2026_04`),
then parse:
- `{BNBUSDT}_events.jsonl` → every `STATE_TRANSITION` into SWEEP / DISPLACEMENT / EXPANSION / RETEST,
  with `candle_index`, **continuation direction** (the trade/reversal direction the structure implies),
  entry≈event-candle close, geometry (disp_low/high, sweep_type).
- `{BNBUSDT}_crt_telemetry.jsonl` → `RETEST_REPLAY` (entry/direction/atr/disp/score) +
  `EXPANSION_RETRACE_CHECK` (max_depth, time_to_max, ended_by, shadow_used, HTF-alignment).
Emit a `StructuralEvent` list keyed by research index: `(stage, entry_index, entry, continuation_dir,
atr, regime/HTF/disp_strength features)`. Report the **funnel counts** per stage (sweep ≫ displacement
≫ expansion ≫ retest≈44) so power is explicit.

### E1.1 — Forward asymmetry per stage (exit-agnostic)
For each event, `horizon_excursion(signal_in_continuation_dir, candles[i+1:i+1+max_forward])` →
`mfe_r, mae_r, favorable_first, reached_kR`. Per **stage**: `E[mfe_r]`, `E[mae_r]`,
**asymmetry = E[mfe_r] − E[mae_r]**, `favorable_first_rate`, `n`. The core question: **does asymmetry
increase monotonically sweep → displacement → expansion → retest** (trap completing)?

### E1.2 — Matched control (the falsification baseline)
For each stage, draw the same N **random-bar entries** (matched continuation-direction distribution,
seeded) → baseline asymmetry. A real structural effect must **beat its control** (expect control
asymmetry ≈ 0, favorable_first ≈ 0.5).

### E1.3 — Conditioning (only on the populous stages)
Stratify SWEEP/DISPLACEMENT/EXPANSION by **regime** (vol-tercile · HTF-alignment · displacement-strength
tercile) → per-cell asymmetry vs control. Does asymmetry emerge in a *conditional* cell that the
unconditional average hides? (The F-020 lesson, applied to structural state.)

### E1.4 — Significance + OOS (strict bar)
Stratified/bootstrap permutation (shuffle structural-vs-control labels, recompute asymmetry, seeded)
+ chronological **70/30 OOS**. A **continuation-asymmetry pocket** requires: asymmetry **> control**,
**permutation-significant**, **OOS-sign-stable**, and `favorable_first > 0.5 + floor`. **Doctrine: a
pocket is a PRE-REGISTERED OOS CANDIDATE for E2 (a tradeable rule), never an edge.** If null across
stages + cells → the structural pipeline adds no directional asymmetry (strengthens Program-1 at the
structural level), and E2 is NOT entered.

### New files (additive, isolated, deterministic)
- `src/research/structural_asymmetry.py` — pure core: per-(stage, cell) asymmetry + favorable_first +
  control + stratified-permutation + OOS + the pocket verdict (reuses `horizon_excursion` + the
  `selection_effect` permutation pattern).
- `src/research/adapters/structural_event_source.py` — harvester (mirror `ProductionSpineSource`):
  one backtest → `events.jsonl` + `crt_telemetry.jsonl` → `StructuralEvent` list.
- `scripts/research/phase_e_structural_asymmetry.py` — driver: harvest BNB → measure per stage +
  conditional vs control → deterministic JSON + markdown (funnel counts + asymmetry table + verdict).
- `configs/research/research_config_phase_e.json` — BNBUSDT, prod_version, max_forward, conditioning
  knobs, n_permutations, oos_split, control seed, favorable_first floor. No magic numbers in Python.
- `tests/research/test_structural_asymmetry.py` — determinism; **planted-asymmetry recovery** (a
  synthetic event set with real forward asymmetry MUST surface — harness validity, makes a null
  trustworthy); **control calibration** (random entries → asymmetry≈0 / favorable_first≈0.5); OOS split.

### Record (doc-first — finding only AFTER results)
`docs/analysis/structural-asymmetry-bnbusdt-2026-06-13.md` first; then the next finding (likely "no
continuation asymmetry beyond control at any structural stage/regime on BNBUSDT M15 — the trap pipeline
adds no directional asymmetry" OR "asymmetry pocket at stage/cell X"); a **Funding-Ledger `Program 2 —
RESEARCH` entry** (opening the new ontology, citing the new finding); memory + `MEMORY.md` pointer;
SESSION LOG.

## Critical files

| Action | Path |
|---|---|
| **New** core | `src/research/structural_asymmetry.py` |
| **New** harvester | `src/research/adapters/structural_event_source.py` |
| **New** driver | `scripts/research/phase_e_structural_asymmetry.py` |
| **New** config | `configs/research/research_config_phase_e.json` |
| **New** tests | `tests/research/test_structural_asymmetry.py` |
| **New** analysis doc | `docs/analysis/structural-asymmetry-bnbusdt-2026-06-13.md` |
| Reuse (no edits) | `adapters/spine_signal_source.py` (pattern), `measurement/forward_walk.horizon_excursion`, `selection_effect`, `conditional_entropy_grid`, `regime/regime_classifier.py`, `runtime.backtest_v2.CandleLoader`, the S0 RETEST_REPLAY + EXPANSION_RETRACE_CHECK telemetry |
| Update (records) | `docs/current-findings.md` (finding + Program-2 ledger entry), `CLAUDE.md` index, `MEMORY.md` + memory |

## Out of scope (deferred)
- **E2 tradeable continuation rule** — gated on an E1 asymmetry pocket; not built here.
- **Pullback branch** — premise (RSI≈48 winners) contradicts the artifact (RSI≈69); reconcile first.
- Compression-breakout / conditional-momentum branches; crypto-6 (confirm-gate only if BNB leads).
- No spine/config/ACTIVE_VERSION/promotion changes, no live, no Program-1 reopen.

## Verification
1. **Unit tests:** `pytest tests/research/test_structural_asymmetry.py` — determinism, planted-asymmetry
   recovery, control calibration (favorable_first≈0.5), OOS split.
2. **Sanity:** stage funnel counts match the backtest (retest≈44, sweep≫retest); control asymmetry≈0;
   the unconditional retest asymmetry reproduces the F-024 MFE≈MAE picture.
3. **Driver runs:** `python scripts/research/phase_e_structural_asymmetry.py` → per-stage + conditional
   asymmetry vs control + verdict; deterministic JSON.
4. **Determinism gate:** run twice; JSON body byte-identical.
5. **Findings contract (after doc + finding + ledger):** `pytest tests/test_current_findings.py` green.
6. **No collateral:** `pytest tests/research` green; `git diff --stat` shows only new files + the
   records edits; ACTIVE_VERSION / configs / spine untouched.

## Done =
A reproducible, deterministic **structural-asymmetry map** for BNBUSDT — forward continuation-asymmetry
(MFE/MAE, favorable_first) across the sweep→displacement→expansion→retest progression and within
regime/HTF cells, each vs a matched control, with stratified permutation + OOS. If a cell clears the
strict bar (> control, significant, OOS-stable) → a pre-registered OOS candidate for E2 (gated) + a
cross-instrument confirm. If null (the likely outcome) → the CRT structural pipeline adds **no
directional continuation asymmetry** on BNBUSDT M15 — extending Program-1's conclusion to the
structural-state axis, and Program 2 pivots to a different frontier (target/horizon/asset/objective).
