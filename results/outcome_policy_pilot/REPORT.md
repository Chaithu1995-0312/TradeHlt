# Pilot: does the previous trade's outcome predict the next CRT trade's direction?

> **Pilot only. It cannot prove or disprove predictive information.** Direction-selection mode, XAUUSD, corrected engine. Nothing here is a trading result, a tuning, or a promotion.

## 1. Setup (all fixed before any policy result was seen)
- **Frozen baseline (Policy D):** trade lists from the corrected engine (spread sign + entry lookahead fixed; `results/fix_spread_lookahead/`). M15 production defaults: **9** opportunities. H1 `--htf 24`: **12** opportunities. Hashes: `frozen/SHA256SUMS`. Every policy only takes or skips these same opportunities.
- **Policies:** A reverse after loss, B continue after win, C opposite controls (reverse after win, retain after loss), D baseline. A branch a policy does not name takes any signal; the first opportunity is always taken.
- **Win/loss:** net R > 0 is a win. The previous opportunity is always completed before the next opens (checked: no overlaps), so a still-open trade is never classified.
- **Windows** (signal entry bar, file/UTC time): open = Monday, middle = Tuesday–Thursday, close = Friday.
- **Periods:** development = before 2025-05-22; hold-out = 2025-05-22 onward, opened only for the policy selected on development. Selection rule: among A/B/C with at least **3** development trades and a development expectancy above D's, pick the highest. The floor of 3 was set after seeing the opportunity counts (5 development trades per timeframe) but before any policy result.
- **Not run:** forced-direction mode (needs mirrored SL/TP and a bar-level simulation); combining A and B.
- Code: `scripts/analysis/outcome_policy_pilot.py`. Full per-window tables: `tables.md`, `result.json`.

## 2. Opportunity counts per cell
| | open (Mon) | middle (Tue–Thu) | close (Fri) |
|---|---|---|---|
| M15 (9) | 1 | 7 | 1 |
| H1 htf24 (12) | **0** | 10 | 2 |

Open and close windows have 0–2 opportunities, so any window-level number is anecdote. The H1 opening window has none.

## 3. Development period, all policies (pooled over windows)
| TF | Policy | n | Net expectancy R [95% CI] | WR | MaxDD (R) |
|---|---|---|---|---|---|
| M15 | D baseline | 5 | −0.561 [−1.72, +0.60] | 20% | 2.80 |
| M15 | A | 4 | −0.414 [−2.02, +1.20] | 25% | 1.66 |
| M15 | B | 5 | −0.561 [−1.72, +0.60] | 20% | 2.80 |
| M15 | C | 2 | −1.093 [−1.77, −0.42] | 0% | 2.19 |
| H1 | D baseline | 5 | +0.447 [−0.14, +1.04] | 80% | 0.03 |
| H1 | A | 5 | +0.447 (same trades as D) | 80% | 0.03 |
| H1 | B | 3 | +0.153 [−0.52, +0.83] | 67% | 0.03 |
| H1 | C | 3 | +0.747 [−0.09, +1.58] | 100% | 0.00 |

Selection: **M15 → A** (4 trades, −0.41R vs D −0.56R); **H1 → C** (3 trades, +0.75R vs D +0.45R). On M15, B equals D (it never removes a signal) and C fails the floor.

## 4. Hold-out (opened once, selected policy vs D)
| TF | Policy | n | Net expectancy R [95% CI] | WR | MaxDD (R) |
|---|---|---|---|---|---|
| M15 | A | 3 | +0.886 [+0.70, +1.07] | 100% | 0.0 |
| M15 | D | 4 | +0.872 [+0.77, +0.98] | 100% | 0.0 |
| H1 | C | 3 | +0.276 [−2.51, +3.06] | 67% | 1.02 |
| H1 | D | 7 | −0.326 [−1.15, +0.49] | 29% | 3.11 |

- **M15:** A removed one winning trade (the Monday one) and changed nothing meaningful. The hold-out is 4 for 4 winners with or without the policy.
- **H1:** C kept 3 of 7 trades and avoided losses that D took. That looks good (+0.28R vs −0.33R), but the interval for C spans −2.5R to +3.1R, and 3 trades cannot support a conclusion.

## 5. Descriptive check (all opportunities, not used for selection)
Next trade's win rate by previous outcome and direction relation:

| | M15 same dir | M15 reverse | H1 same dir | H1 reverse |
|---|---|---|---|---|
| After a loss | 1 of 2 | 1 of 2 | 1 of 2 | **0 of 3** |
| After a win | 2 of 3 | 1 of 1 | 1 of 3 | **3 of 3** |

Fisher exact p-values are 0.40–1.00 in every comparison. H1 hints at "reverse after a win" and "continue after a loss", the opposite of the hypotheses behind A and B. It is 6 trades per comparison, so treat it as noise until proven otherwise.

## 6. What this pilot says
- **Previous-trade outcome as a direction signal: no measurable information found, and the data cannot detect any.** With 9–12 opportunities per timeframe and 0–10 per window, the smallest effect that could reach significance is huge. Detecting a 0.3R expectancy difference at a trade standard deviation near 0.9R needs roughly 70–140 trades per cell; we have 0–10.
- The apparent H1 hold-out advantage for C comes from skipping 4 of 7 trades, which is how any filter looks good on a bad stretch.
- Costs are large: about 0.05–0.47R per trade, 80–180 pips (XAUUSD, 0.02% spread), and they matter more than any ordering effect.
- Corrected baseline D itself is near zero (M15 +0.08R/trade, H1 −0.004R/trade over the full period), so there is no edge for a policy to refine yet.

## 7. What would make this testable
1. More opportunities: longer history and more instruments, ideally a few hundred CRT signals, with the rules frozen first.
2. A window definition decided from market structure (e.g. the first N hours after the weekly open) instead of calendar days.
3. Forced-direction mode, only if direction selection shows a signal at that scale.
4. Resolve F3 (TP2/runner accounting) and F4 (feature scale) first if the next study uses features.

## 8. Caveats
- The conditioning chain uses each opportunity's as-if-taken outcome. An alternative (the last trade the policy actually took) can deadlock when no signal matches.
- Selection floor and windows are my pre-registered choices; your section 1 was not visible to me.
- M15 and H1 results share many underlying signals and are not independent evidence.
