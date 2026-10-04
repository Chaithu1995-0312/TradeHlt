# Pre-registration — SWEEP→REVERSAL vs SWEEP→CONTINUATION forward-path comparison

**Status**: FROZEN before computation. **Authority**: diagnostic only, `economic_claims_allowed: false`. Grants no G001, no ontology authority, no promotion path — same ceiling as `docs/implementation_plan/no-context-from-soruces-humming-tower.md` Phases 4a-4f, which this program is downstream of.

## 1. Origin and objective

Phases 4a-4f (see the plan file above) established that a `SWEEP`-founded, magnitude-qualifying candle moving *opposite* to the founding sweep's implied continuation direction is deterministically rejected by `_displacement_entry_allowed`'s directional-contract gate (32/32), and that the evidence layer (`break_of_structure`+`trend_bias`) already identifies these reversals correctly on 30/32 bars — a representational gap, per the user-decided Position B (recorded, `configs/formulas/market_shapes.yaml:blocked_shapes:SweepReversal`).

This program asks a different, **economic** question that Position B did not answer: do these two populations — candles that continue in the swept direction versus candles that reverse against it — produce **materially different forward price behavior**? If yes, that is independent evidence the two deserve separate representation, beyond "a human/LLM would name them differently." If no, the current exclusion is easier to defend on economic grounds even though the representational gap is real.

## 2. Populations (fixed, not redefined here)

Both drawn from the same 127-bar magnitude-qualifying set (`candle_range >= 1.0*atr_abs`, `|close-open| >= 1.2*atr_abs`, `body_ratio >= 0.65` — the config's own `atr_multiplier_min`/`atr_min_displacement`/`body_ratio_min`), on `data/XAUUSD_M15.csv` (2026-07-07 to 2026-08-06, 2,038 non-warmup bars):

- **CONTINUATION** (n=39): reached `DISPLACEMENT`/`EXPANSION` occupancy — the candle's own direction matched the founding sweep's implied continuation direction.
- **REVERSAL-CANDIDATE** (n=32): `SWEEP` held at the time, magnitude qualifies, but the candle's own direction was *opposite* the founding sweep's implied direction (Residual Attribution's `DIRECTIONAL_CONTRACT_VIOLATION` bucket, exhaustively enumerated, zero unattributed).

The other 56 rejected bars (`FAR`/`RECENT`/`JUST_EXPIRED` — no active `SWEEP` to define "opposite direction" against) are **excluded** from both arms; they are not a comparable population for this question.

## 3. Outcome metric — reused, not invented

`horizon_excursions()` (`src/research/oracle/exit_analysis.py:75`) — exit-agnostic MFE/MAE in price, both directions, no-lookahead-safe (window `i+1..i+horizon`), bar-for-bar agreement with the scalar `forward_walk` version already asserted by `tests/research/test_exit_ceilings.py`. Called exactly as `exit_geometry_scan.py::stage_ceilings` calls it: `entry = close` array, `high`/`low` from the full raw series.

For each bar, **direction is fixed to the direction the qualifying candle itself moved** (not a hypothesized trade call): `LONG` for a bullish qualifying candle, `SHORT` for a bearish one. This applies symmetrically to both arms — a CONTINUATION bar's direction already equals its founding sweep's implied direction by construction; a REVERSAL-CANDIDATE bar's direction is its own actual (reversed) direction.

R-normalization: `risk_distance = atr_abs` at each bar (`atr * close`, FM-074 convention, already computed identically to the Residual Attribution and magnitude-qualification passes).

**Control**: `passive_exposure_r` (`src/research/oracle/exit_analysis.py`) — same-direction buy-and-hold over the same horizon, in R — the "binding control" this repo's own F-086/F-087 always compare against, not zero.

## 4. Horizons — reused, not invented

`(20, 40, 96)` M15 bars — `exit_geometry_scan.py:82`'s exact `HORIZONS` tuple (40 is "the oracle program's horizon," F-086's own default). Reported per-horizon, not pooled — a horizon-dependent effect is a different finding from a horizon-invariant one.

## 5. Cost model — none, and this is a fact about the measurement layer, not a choice

`horizon_excursions()` is a pure path-ceiling measurement; neither population has an actual entry/stop/target, so `SEM-015`/`SEM-016` (which price *realized fills*) do not apply here — the same layer F-086 itself measures gross MFE/MAE at, before any cost model is applied. Gross only, reported as gross, not silently compared to something cost-adjusted.

## 6. Statistical treatment — reused, not invented

`bootstrap_ci()` (`src/research/measurement/bootstrap.py:35`), deterministic-seeded via `seed_from_key`. For each population, at each horizon: point estimate + bootstrap CI on mean MFE (R), mean MAE (R), and mean net excursion; the same for `passive_exposure_r`. Between-population: point estimate + bootstrap CI on the **difference** in each of those means (CONTINUATION − REVERSAL-CANDIDATE). No p-value-only reporting; no test that assumes normality (n=32/39 is too small for that assumption).

## 7. What this explicitly is not

- **Not a sealed MC-* contract.** No train/holdout embargo split — at n=32/39, splitting further would gut power on both arms below anything interpretable. This is a **single-pass diagnostic**.
- **Not an economic claim, regardless of result.** `economic_claims_allowed: false`. A large measured difference is information about the market process, not authority to change the ontology, add a state, or claim G001.
- **Not a re-derivation of F-086/F-087's own results** on this corpus — those measured the *every-bar* population; this measures two specific, already-fully-attributed sub-populations of magnitude-qualifying `SWEEP`-held candles.
- **No new candidate, arm, or horizon may be added after seeing the computed output.** If the frozen set above returns a null or an ambiguous result, that is the result — a follow-up would need its own, separately-authorized pre-registration, not a widened search on this one (matching the anti-overfit discipline already established for `BC4-RESIDUAL-ATTRIBUTION` and `MC-*` elsewhere in this repo).

## 8. Frozen predictions (stated before computing, so a null is checkable against them)

No directional prediction is made about which population "wins" — the objective is descriptive comparison, not a hypothesis test with a predicted sign. The only frozen prediction is structural: **given n=32/39, at least one of the six (2 populations x 3 horizons) MFE/MAE cells is expected to show a bootstrap CI crossing zero** — i.e., some result at this sample size is expected to be statistically ambiguous, and that outcome must be reported as ambiguous, not rounded toward either population being "different."

## 9. EXECUTED — result (append-only, dated 2026-09-03)

Ran exactly as frozen in §2-6, no arm/horizon/metric added after seeing output. Reused `horizon_excursions`, `passive_exposure_r`, `bootstrap_ci` verbatim (imported, not reimplemented). n at each horizon shrinks slightly below the nominal 39/32 as the forward window runs off the end of the corpus (horizon=96 → n=35/30) — expected, not a defect.

**NET (MFE+MAE combined, R units) — every cell's bootstrap CI crosses zero, both populations, all three horizons:**

| Horizon | CONTINUATION net (n) | REVERSAL_CANDIDATE net (n) | Between-pop diff CI |
|---|---|---|---|
| 20 | −0.25R (−1.32, +0.78), n=37 | −0.29R (−1.55, +0.80), n=32 | (−1.59, +1.69) — crosses zero |
| 40 | +0.14R (−1.46, +1.75), n=36 | −0.76R (−3.27, +1.65), n=31 | (−2.06, +3.83) — crosses zero |
| 96 | +0.90R (−2.57, +4.21), n=35 | +0.17R (−3.41, +3.69), n=30 | (−4.30, +5.77) — crosses zero |

MFE and MAE individually are both large and clearly non-zero for both populations at every horizon (e.g. horizon=40: CONTINUATION MFE +3.57R / MAE −3.44R; REVERSAL_CANDIDATE MFE +4.24R / MAE −5.00R) — both populations see substantial two-sided excursion, consistent with the ATR-normalized R scale at these horizons on this corpus. `PASSIVE` (buy-and-hold the qualifying candle's own direction) is not distinguishable from zero either, at any horizon, for either population.

**Verdict: AMBIGUOUS, exactly the frozen §8 prediction — not a clean null and not a clean positive.** At n=32/39, this comparison cannot distinguish CONTINUATION from REVERSAL_CANDIDATE forward net path behavior from each other, nor either population from passive exposure, at any of the three frozen horizons. Per §7, no further arm, horizon, or metric is added in response to this result — a genuinely powered version of this question needs a larger corpus (more months of magnitude-qualifying `SWEEP`-held candles), which is a separate, future, explicitly-authorized program, not a re-cut of this one.

**What this does and does not say about Position B (`configs/formulas/market_shapes.yaml:blocked_shapes:SweepReversal`)**: nothing retracts it. Position B was a representability finding (the evidence layer already identifies the reversal; occupancy has no construct for it) — independent of whether the two populations are economically distinct. This program tested a *further, additional* line of evidence (economic distinctness) that the representability finding did not itself require. Its ambiguity means that additional evidence is inconclusive at this sample size — not that the representational gap isn't real, and not that it is more urgent than already stated.
