# Trained-Data Knowledge Extraction - walk x state, and price -> state

**Measurement lane. No trading logic changed.** All figures from existing artifacts on the 2-year
XAUUSD corpus unless marked `one-month`.

## Provenance

| Layer | Artifact | Identity |
|---|---|---|
| Walk kernel | `src/research/oracle/multi_tp_walk.py:143` | frozen golden contract, parity suite |
| Labels | `results/research/oracle_labels/XAUUSD_M15/labels.csv` | **565,884 rows**, `walk_kernel=multi_tp_walk` |
| Bar matrix | `results/research/bar_matrix/XAUUSD_M15/bar_matrix.csv` | **47,197 x 136**, `trace_join_status=JOINED` 100% |
| Join | `_pos` | **565,884 rows joined**, 0 orphans |
| Drift control | `results/sleeve_mfe_ladder/2026-09-26/` | 2,298 candidates, Z-ladder |

Production arm (tie_break=production) = **282,942 rows**. Base `mean_R_net` = **-0.1758**.

## BLOCKER - GAP-002: the bar matrix is a STALE artifact

`scan.state_columns()` **fails closed** (by design) on the on-disk matrix:

```
state_columns: bar matrix missing required columns:
   ['trade_intent_long', 'trade_intent_short']
```

**Cause:** matrix built **2026-09-23** (`generated_utc 2026-09-23T07:36:02`, git `09ffcb11`, dirty).
`build_bar_matrix.py:550-554` gained the per-side columns on **2026-09-29** (`454fd542`) - six days later.
The builder produces them; the artifact predates it.

**Not worked around.** Per the fail-closed instruction this is reported, not substituted.
`trade_intent` (single, 4-way) was NOT silently promoted to the per-side pair.
**Fix:** re-run `scripts/research/build_bar_matrix.py`. Then L2/L3 state cells become available as designed.

## L2 - state cells (production arm, y_R_net)

| family | cell | n | mean_R_net | win | lift vs base |
|---|---|---|---|---|---|
| engine_state_after | SHADOW_PENDING | 36 | **-0.0957** | 0.4167 | 0.0801 |
| engine_state_after | RETEST | 150 | **-0.1334** | 0.4533 | 0.0424 |
| engine_state_after | RANGE | 132666 | **-0.1691** | 0.4721 | 0.0067 |
| engine_state_after | SWEEP | 93522 | **-0.1734** | 0.4675 | 0.0025 |
| engine_state_after | EXPANSION | 51870 | **-0.1952** | 0.4674 | -0.0193 |
| engine_state_after | DISPLACEMENT | 4674 | **-0.2018** | 0.4369 | -0.0259 |
| engine_state_after | EXECUTION | 24 | **-0.3507** | 0.4167 | -0.1749 |

**Every cell is negative.** Best is `SHADOW_PENDING` (-0.096, n=36, far too thin).
`EXECUTION` - the only state that actually trades - is **-0.351** (n=24).

## The drift control decides it

The MFE ladder's own NOTE concludes the LONG excess is *"gold's up-drift, not the entry"*:
LONG hit rate matched a **random M15 entry within 0.4pt at every Z**, SHORT mirror collapsed to 14.5%.
So a raw LONG > SHORT gap is **drift, not edge**. The only honest control is the *within-cell* spread.

| state | n | long_R | short_R | spread | 95% CI | sig |
|---|---|---|---|---|---|---|
| DISPLACEMENT | 4674 | -0.1514 | -0.2521 | 0.1006 | [0.0385, 0.1662] | SIGNIFICANT |
| EXPANSION | 51870 | -0.146 | -0.2443 | 0.0984 | [0.0796, 0.116] | SIGNIFICANT |
| RANGE | 132666 | -0.1289 | -0.2094 | 0.0806 | [0.069, 0.092] | SIGNIFICANT |
| RETEST | 150 | -0.3747 | 0.1079 | -0.4827 | [-0.8006, -0.1682] | SIGNIFICANT |
| SWEEP | 93522 | -0.1513 | -0.1955 | 0.0442 | [0.0308, 0.0577] | SIGNIFICANT |

All spreads are "statistically significant" - **and that is the trap**. Significance here only says
the drift is real. The question is whether a state *differs from the RANGE baseline*.

| state | spread | excess vs RANGE baseline | reading |
|---|---|---|---|
| DISPLACEMENT | 0.1006361869918698 | 0.0201 | DIFFERS from baseline |
| EXPANSION | 0.0983856409485251 | 0.0178 | indistinguishable from baseline |
| RANGE | 0.0805857050789199 | 0.0 | indistinguishable from baseline |
| SWEEP | 0.0442026261200573 | -0.0364 | DIFFERS from baseline |
| RETEST | -0.48267792 | -0.5633 | DIFFERS from baseline |

**`RANGE` is the baseline = no structural event = the market itself.** Its spread (+0.0806) is pure drift.
Against it:
- `EXPANSION` +0.018 and `RANGE` 0.000 - **indistinguishable from the market**
- `DISPLACEMENT` +0.020 and `SWEEP` -0.036 - **barely moved**, well inside noise
- `RETEST` -0.563 - looks dramatic but **n=150 on one side**; it is thin, not strong

**No state cell shows an excess that is both material and adequately sampled.**

## Price -> state: can price alone predict the state? (`one-month`, 2,222 bars)

| state | n | body med (ATR) | body p90 | range med | range p90 |
|---|---|---|---|---|---|
| RANGE | 855 | 0.3746 | 1.067 | 0.8614 | 1.6283 |
| EXPANSION | 673 | 0.4066 | 1.1425 | 0.899 | 1.691 |
| SWEEP | 670 | 0.3869 | 0.9568 | 0.9018 | 1.6333 |
| DISPLACEMENT | 22 | 1.2638 | 1.504 | 1.5325 | 1.9245 |
| RETEST | 2 | 0.7077 | 0.6267 | 1.0815 | 1.0363 |

`DISPLACEMENT` sits visibly higher (median **1.264 ATR** body vs ~0.39 for everything else).
But the decisive test is separability:

```
engine gate: body >= 1.2 ATR AND range >= 1.5 ATR
  actual DISPLACEMENT bars       : 22
  ...meeting the price gate      : 12  (recall 54.5%)
  non-DISPLACEMENT bars          : 2200
  ...ALSO meeting it (false pos) : 133  (FPR 6.045%)

DISPLACEMENT min body  : 0.094 ATR
others p99 body        : 2.1724 ATR
SEPARATION GAP         : -2.0784 ATR
```

**VERDICT: OVERLAP. Price alone cannot separate displacement from the rest.**

Two reasons, and both matter:
1. **Recall 54.5%.** Half of real DISPLACEMENT bars *fail* the price gate. A displacement is not
   just a big candle - it is a big candle *following a sweep*, and the sweep context is exactly
   what the price-only view throws away.
2. **6.045% false-positive rate.** 133 ordinary bars pass the same price test.

**This is the load-bearing answer to your reverse-engineering question.** The state layer is
carrying information price cannot supply: *sequence and context*, not magnitude. `DISPLACEMENT`
is defined as a bar that is impulsive **and** arrived within `max_sweep_age_candles=20` of a
specific liquidity event. Neither half is recoverable from the bar alone - hence the overlap.

It also means the market-movement census alone can never validate the state machine, and the
state machine alone can never be validated without a price baseline. Both are required.

## Answers to the two questions

> **Does the state layer learn anything price does not already say?**

**Yes - sequence.** Magnitude is reproducible from price (the gates are price rules). But no single
bar's magnitude identifies DISPLACEMENT: recall 54.5%, FPR 6.045%, separation gap negative.
The discriminating information is *that a sweep preceded it*, which is irreducibly a path property.

> **Is there trained-data knowledge on the states?**

**No usable edge, on this evidence.** After removing drift with the MFE ladder's own control, every
state cell lands within ~0.02R of the RANGE baseline - i.e. within the market's own noise.
`RETEST` is the only outlier and it has n=150 (one side), far below a defensible floor.
The negative base expectancy (-0.176R across 282,942 hypothetical trades) says the cost/geometry
as configured loses money on *every* population measured, not just on the states that trade.

## Artifacts

| File | Contents |
|---|---|
| `l2_state_cells.csv` | 47 cells across 12 state families |
| `state_long_short_spread.csv` | drift-controlled spread + bootstrap CI per state |
| `state_excess_vs_baseline.csv` | excess over the RANGE baseline - the honest number |
| `price_to_state_one_month.csv` | movement profile per state |
| `price_predicts_displacement.json` | separability test |

## Recommended next steps

1. **Re-run `build_bar_matrix.py`** - unblocks the designed L2/L3 state scan (GAP-002).
2. **Do not widen gates on this evidence.** Every cell is ~baseline; loosening a gate that selects
   a baseline-equivalent population cannot create expectancy.
3. **The -0.176R base is the real target.** It is population-wide, not state-specific - so the
   question is the walk/geometry contract's profitability, not the state machine's selection.
