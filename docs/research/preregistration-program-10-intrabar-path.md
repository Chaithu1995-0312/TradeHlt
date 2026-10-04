# Pre-Registration — Program 10 (Intrabar Path: Ambiguity Census, M5 Resolution, Path Model)

> **Status:** PRE-REGISTERED (written before any run). Authority: research/docs only (§6.5
> Authority Ladder). This document FREEZES the populations, the thresholds, the stated prior, the
> F-025 revision rule, and the closure rule **before** results exist, so a null cannot be re-spun
> into a finding and a large correction cannot be spun into "the falsifications were wrong."
> Enforced socially by the Epistemic Integrity ritual (Program E-001,
> [`docs/governance/EPISTEMIC_INTEGRITY.md`](../governance/EPISTEMIC_INTEGRITY.md)).

## Context & scope

Every economic finding from F-019 to F-043 is measured through
`src/research/measurement/forward_walk.py`. When a single bar's range spans **both** the stop and
the target, that kernel resolves the ordering **pessimistically**: the `sl_hit` branch
(`forward_walk.py:127`) returns before the `tp_hit` branch (`:141`) is ever reached. In the
governing `intrabar_fixed` mode `trail_stop` never ratchets (the ratchet is `trailing`-only,
`:95-96`/`:109-110`), so `trail_past_tp` is always false for a valid signal and the tie-break
**always** resolves to SL. `crt_engine_v2.py:2471` mirrors the same ordering in the runtime.

This convention has never been measured. It is a **modelling assumption presented as a
measurement**, and it sits underneath every economic conclusion in the repository.

### Why this is not a diffuse "findings may be affected" risk

From `src/research/exit_grid.py:186-201`:

```
structural_upper_bound          = e_gross      − min_achievable_cost
perfect_information_upper_bound = mfe_capture  − min_achievable_cost
reality_gap                     = perfect − structural
```

`min_achievable_cost` **cancels**, so exactly:

```
reality_gap  ≡  mfe_capture − e_gross
```

- `mfe_capture` = mean `max_favorable_excursion_r`, produced by `horizon_excursion`
  (`forward_walk.py:278`) — exit-agnostic, walks the full horizon, **never touches the tie-break**.
- `e_gross` = `expectancy_gross` over `rr_gross_intrabar` = `forward_walk(exit_model="intrabar_fixed")`
  — **fully exposed to the tie-break**.

Therefore a pessimistic bias in the tie-break inflates F-025's `reality_gap = +4.16R`
**one-for-one** and deflates `ceiling_utilization = −4%` correspondingly. F-025 is the primary
support for the standing conclusion *"the bottleneck is entry information, not exits."* The
correction is exact and pre-computable with a single unknown: mean per-event R-bias × ambiguous mass.

**Program 10 runs before all discovery work** (Phases A–E). Discovery cannot exceed the quality of
its labels; measurement precedes inference.

## The detection instrument (frozen, and exact)

The tie-break leaves an **exact signature** in the returned `Outcome`. No re-scan of the kernel is
performed, so the census cannot drift from the kernel it audits.

```
P1 fired  ⟺  outcome == "SL_HIT"  AND  time_to_tp is not None
```

**Proof of exactness, both directions** (`forward_walk.py:124-144`):
- `time_to_tp` is assigned at `:124-125`, which executes *before* the `sl_hit` block at `:127`.
- If `tp_hit` were true on any **earlier** bar without `sl_hit`, the function would have returned
  `TP_HIT` at `:141-144` on that bar. So an `SL_HIT` can only carry a non-None `time_to_tp` if
  `tp_hit` and `sl_hit` fired on the **same** bar. (⇐)
- Conversely a same-bar collision necessarily sets `time_to_tp` before returning `SL_HIT`. (⇒)

Invariant asserted by test: on every detected P1 event, `time_to_tp == duration_candles`.

## Populations (counted SEPARATELY — conflating them is the primary way this census could lie)

| ID | Site | Current treatment | Bias character | Touches F-025? |
|---|---|---|---|---|
| **P1** | `forward_walk.py:127` | resolved as SL | **directional bias in `e_gross`** | **YES** |
| **P2** | `forward_walk.py:221` (OCO D1) | signal CANCELLED, dropped from n | selection effect, not bias | no |
| **P3** | `forward_walk.py:251` (OCO D2) | TP never credited on fill bar | directional, OCO-only | no |

P2/P3 are reported for completeness and to make Program 9's straddle verdict interpretable (its
cancelled mass is currently unquantified). Only P1 enters the F-025 revision rule.

## Universe (frozen)

| Group | Instruments | Data |
|---|---|---|
| crypto (primary) | BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT | `data/binance/{SYM}_M15.csv` (+ `_M5.csv` for 0B) |
| fx (robustness) | EURUSD, GBPUSD, AUDUSD, USDJPY, EURCAD | `data/mt5/{SYM}_M15.csv` (+ `_M5.csv`) |

XAUUSD excluded from the FX primary per F-035 (holiday gap gate).

## FROZEN metrics and thresholds

Reported per instrument **and** per SL/TP cell of the F-025 42-cell grid, so the census is directly
commensurable with `results/research/phase_d/phase_d_exit_grid.json`.

| Metric | Definition |
|---|---|
| `ambiguity_rate` | `n_p1 / n_signals` |
| `per_event_r_swing` | `rr_if_TP − rr_if_SL`. In `intrabar_fixed`, `rr_if_SL ≡ −1.0` exactly (trail_stop==sl) and `rr_if_TP = tp_atr_mult / sl_atr_mult` ⇒ swing `= tp_mult/sl_mult + 1.0` |
| `max_bias_R` | `ambiguity_rate × mean(per_event_r_swing)` — the worst case in which **every** tie-break is decided wrongly |
| conditioning | `atr_ratio` of the ambiguous bar, session, instrument, `tp_dist / bar_range` |

`max_bias_R` is deliberately an **upper bound**, not an estimate. 0B replaces the bound with a
measured split; the bound alone can only trigger the stop gate, never a finding of harm.

### Stop gate (frozen)

> If pooled `max_bias_R < 0.05R`, Program 10 CLOSES at 0A with the finding *"the same-bar tie-break
> convention is immaterial at the incumbent geometry"* and phases 0B–0D are NOT funded.

## Stated prior (recorded BEFORE running)

> **CORRECTED 2026-07-19, before any census result was read.** The first draft of this section
> claimed: *"F-025 already reports `plain_stop_loss 90.55% + same_bar 9.25%`. The 9.25% is an
> existing estimate of P1's mass at the incumbent cell."* **That was an overclaim on a neighbouring
> quantity.** Preserved per §6.2 rule 4; the corrected prior follows.

**What F-025's `same_bar_conflict` actually counts.** `research.forensics._classify:100` defines it
as `co.outcome == "TP_HIT" and ib.outcome == "SL_HIT"` — a trade that close_only scores a win and
intrabar scores a loss. Despite the name this is **neither necessary nor sufficient** for P1:

- **Not sufficient** — it requires the bar *close* to cross TP under close_only. A genuine P1 bar
  that wick-touches both levels and then closes back inside the range is classified
  `plain_stop_loss`, not `same_bar_conflict`.
- **Not necessary** — a bar may wick the SL while closing well above it (intrabar `SL_HIT`), after
  which close_only keeps walking and closes above TP several bars later. That is counted as
  `same_bar_conflict` with **no same-bar collision at all**.

The two sets overlap but neither contains the other. `same_bar_conflict` is better read as
*"intrabar reversed a close_only winner"* — a close-vs-wick disagreement over an arbitrary horizon,
not a single-bar ordering ambiguity.

**Corrected prior.** P1's mass is **genuinely unknown a priori**. F-025's `count_pct 9.11%` /
`r_lost_pct 9.25%` is registered here as a **loose reference point for a related quantity**, NOT as
a prediction of the census result. Registering it prevents the census from being presented as
having discovered it, which was the original and still-valid purpose of this section.

**Direction of the expectation (not a point estimate).** At the incumbent 1.0×2.0 cell the closed
form gives `per_event_r_swing = 2.0/1.0 + 1.0 = 3.0R`, so `max_bias_R = 3.0 × ambiguity_rate`. The
0.10–0.50R revision band below therefore corresponds to an ambiguity rate of roughly 3.3%–17%. No
specific rate inside that range is predicted. Ambiguity is expected to **rise with tighter TP and
wider SL** (a bar must span both levels), so per-cell dispersion should exceed pooled, and the
incumbent cell is not expected to be the worst.

**Required additional measurement (added by this correction).** Because the two populations were
conflated once already, the census must report the **overlap** — `|P1 ∩ same_bar_conflict|`,
`|P1 \ same_bar_conflict|`, `|same_bar_conflict \ P1|` — so the relationship becomes a measured
quantity rather than an assumption. Any future comparison between this census and F-025's loss
decomposition must cite that overlap table, never equate the two counts.

## F-025 revision rule (FROZEN before the number is seen)

Let `Δ = |measured bias in e_gross|`, in R, from 0B's resolved split (not 0A's bound).

| Δ | Action on F-025 |
|---|---|
| `< 0.10R` | `Update:` line — the +4.16R gap is confirmed robust to the convention. Conclusion unchanged. |
| `0.10 – 0.50R` | `Update:` with a corrected `reality_gap` **range** and restated `ceiling_utilization`; the entries-not-exits attribution becomes an interval. Status stays VALIDATED; `Confidence` reviewed. |
| `> 0.50R` | Full `CORRECTED:` entry per §6.2 rule 4 + the E-001 mandatory phrase, propagated to `docs/analysis/exit-grid-crypto6-2026-06-13.md`, F-041B's scope note, and `docs/analysis/program-1-closure-2026-06-13.md`. |

### Pre-committed bound on what a large Δ may claim

> **Even at Δ > 0.50R, this does NOT overturn F-019 / F-020 / F-021 / F-035.** Those rest on
> PF ≪ 1 (0.02–0.10) and on entropy/selection decompositions that are robust to a per-event R shift
> of this magnitude. A tie-break correction moves the **gap decomposition**, not the **sign of the
> directional null**. Any write-up claiming otherwise is out of scope for Program 10 and requires
> its own pre-registration.

Reporting is **per-cell as well as pooled**: tight-TP/wide-SL cells collide most, so the 42-cell
grid's *ranking* may shift even where pooled bias is small.

## 0B — M5 resolution (frozen)

`m15_children()` joins on `resample.bucket_floor(ts, "M15")` (`resample.py:73`) — the same public
floor the up-aggregator uses, so alignment is definitionally consistent with the ladder.

| # | Guard | Rule |
|---|---|---|
| D1 | corpus parity precondition | `resample(m5,"M15")` must reproduce `data/{provider}/{SYM}_M15.csv` bar-for-bar. Any M15 bar failing parity is **EXCLUDED from the census**, never patched. |
| D2 | read-window invariant | resolving M15 bar `t` may read only M5 bars with `bucket_floor(ts,"M15") == floor(t)`. |
| D3 | measurement-only firewall | the resolved order is written to a report and **never** returned into a `Signal`, an `Outcome`, or any hypothesis. Test-enforced. |

Output taxonomy is **three** buckets, never two:
`RESOLVED_SL_FIRST` · `RESOLVED_TP_FIRST` · `RESIDUAL_AMBIGUOUS` (a single M5 child touched both —
the ambiguity recurs and is **not** resolved).

## 0C — Path model (frozen)

Two variants, pre-registered as **distinct hypotheses**. Variant A will look substantially better
than B; reporting A's numbers under B's framing is the identified failure mode.

| | Conditions on | Legitimate use | Live-usable |
|---|---|---|---|
| **A RESOLVER** | bars `< t` **+ bar `t`'s realized OHLC** | retrospective bound-tightening; imputing P1 | **No** |
| **B FORECASTER** | bars `< t` only | forward path prediction — **the headline claim** | Yes |

Targets: `P(low_first)`, `E[MFE_r]`, `E[MAE_r]`, `P(TP before SL)`.

Estimator: `src/replay/replay_similarity_index.py` reused **as a library** over a new
candle-geometry index. Frozen deviations from its live defaults: `decay_lambda = 0.0` for the
primary claim (the live `0.023` is a recency prior that interacts with the IS/OOS split; decay is a
robustness arm only); `use_faiss = False` is governing truth (faiss is absent from this
environment); and a **new** `aggregate_path_stats` rather than `aggregate_top_k_stats`, whose
`win_rate` is defined as `rr >= 1.0` — a trade notion, not a path notion.

Lookahead controls: index built on the IS half only (split via `qualification._split_is_oos`);
**embargo** of `max(atr_period, sma_period, volume_window)` bars so the encoder's trailing windows
cannot leak across the boundary; self-exclusion.

**Validation is calibration, never accuracy** — accuracy on a ~50/50 target is uninformative and
invites the F-020 significance-saturation trap. Reliability curve with per-bin `n`, Brier, ECE, and
PIT histogram for magnitude targets.

**PASS rule (frozen):** Brier skill score `> 0` versus **both** baselines, on **OOS**, permutation
`p ≤ 0.05` (`qualification.permutation_p_value`), `n ≥ 30` per reported bin.

- **B1** unconditional IS base rate of `low_first`
- **B2** geometric baseline `P(SL first) = tp_dist / (sl_dist + tp_dist)`

Beating B1 but not B2 is a **first-class FAIL** named `GEOMETRY_REDUNDANT` — the analogue of
Program 9's `M15_REDUNDANT` and F-043's `REGIME_REDUNDANT`.

### Stated prior for 0C

`process_diagnostics` established `H_atr = 0.885` vs `H_returns = 0.527` (vol has memory, direction
does not); F-023 established that feature clusters separate shape, not expectancy. The registered
prior is therefore a **split**: the magnitude targets (`E[MFE_r]`, `E[MAE_r]`) show real skill; the
order target (`P(low_first)`) returns `GEOMETRY_REDUNDANT`. Registering the split means the likely
outcome cannot later be sold as "the path model works."

## 0D — Scope statement (verbatim, required in the finding)

> M5 does not *resolve* intrabar order. Each M5 bar carries the identical ambiguity recursively.
> Program 10 is a **bound-tightening** — the unresolvable window narrows from 15 minutes to 5
> minutes (~3×) — plus an **inference** layer. `RESOLVED_*` counts are observations at 5-minute
> granularity; `RESIDUAL_AMBIGUOUS` is the honest, irreducible floor at the finest data on disk.
> The path model's `P(low_first)` is an **estimate, not a measurement**; no number it produces may
> be reported without its calibration curve and its `RESIDUAL_AMBIGUOUS` rate alongside. There is
> no M1 corpus (`scripts/data/fetch_and_verify_binance.py:50` has no `1m` mapping), so this floor
> cannot be lowered with current data.

## E-001 six-question pre-registration ritual

1. **What artifact supports this?** `forward_walk.py:127` (tie-break), `:141` (the TP branch that
   proves signature exactness), `exit_grid.py:186-201` (the cancellation making the coupling exact).
2. **Could INSUFFICIENT explain the observation?** Yes for per-cell counts — cells with `n_p1 < 30`
   report `INSUFFICIENT` and are excluded from the pooled bias claim.
3. **Am I upgrading sign noise into meaning?** Guarded: `max_bias_R` is an explicit upper bound, and
   the 0A stop gate can only close the program, never establish harm.
4. **Is this statistical or economic?** Both, kept separate: 0A/0B are measurement (Level 1); the
   F-025 consequence is an economic restatement, capped by the pre-committed bound above.
5. **Is the parent stronger than the children?** The parent claim is "the convention is unmeasured,"
   which is weaker than any child measurement — satisfied.
6. **Would I phrase this differently after seeing raw counts?** The revision rule and the
   pre-committed bound are frozen above precisely so the answer is no.

## Closure rule

Program 10 closes when either (a) the 0A stop gate fires, or (b) 0B/0C complete and the F-025
revision rule is applied at its measured band. A closure requires: determinism proof (two runs,
identical SHA-256, no wall-clock in the body), the per-cell table, the `RESIDUAL_AMBIGUOUS` rate,
and a registered finding. Threshold changes require a **new** pre-registration, never an edit here.

## Authority

Research/governance only. Program 10 grants **no** ΔG001, no fusion weight, no promotion authority,
and no licence to re-open F-019…F-043. `EXPECTED_ENGINES`, `forward_walk.py`, and
`configs/production/*` are untouched.
