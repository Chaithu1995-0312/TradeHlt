# Move to economic: measure the spine against G001 at scale

## Context

This session established a structural fact and then hit a wall. The Jul 30 XAUUSD LONG was
anchored to a directionally invalid displacement; F-074 rejects it; re-running confirmed the
trade disappears (`TRADE_OPENED 1 -> 0`). That is a *validity* result, on the "information
exists" rung of the §6.5 Authority Ladder.

Moving to economics runs immediately into the blocker: **on the ~1-month corpus the spine
produces 0 trades post-fix (1 pre-fix). Expectancy is not computable at n=0.**

So the honest first economic question is not "what is the edge" but "is there enough
throughput to have an edge at all" — which is F-001 ("intelligence is not the binding
constraint; throughput is") stated as a measurable gap rather than a belief.

**G001 is already machine-readable** in `configs/production/v2_multi_2026_04.json`:

| criterion | G001 | observed (XAUUSD, ~1 month) |
|---|---|---|
| `trades_per_month` | min 20, target 40 | **0–1** |
| `expectancy_r` | min 0.2 | not computable |
| `win_rate` | min 0.35 | not computable |
| `avg_rr` | min 2.0 | not computable |
| `max_drawdown_pct` | max 0.10 | not computable |

A 20–40x throughput miss against the system's own declared floor. Everything else is
downstream of it.

## Reuse — no new measurement code

This is already built and must not be re-implemented:

- `src/runtime/backtest_v2.py:1472` `_attach_goal_report()` — already calls
  `GoalValidator.evaluate()` and writes `m.distribution["goal_report"]` on every run.
  Measure-only; `goal.enforce` is `false`.
- `src/config_layer/goal_validator.py` — `GoalValidator` / `GoalReport`
- `src/config_layer/goal_schema.py` — `GoalSpec` / `load_goal_spec`
- `src/research/goal_alignment.py` — `corpus_span_months()` for the `trades_per_month`
  denominator, and the documented unit-honesty rules (`avg_rr` proxied by `expectancy_rr`;
  `max_drawdown_pct` deliberately OMITTED because EdgeReport's drawdown is an R-multiple,
  not an equity percentage — do not silently convert).

The work is running the existing instrument at scale and reading its output, not building one.

## Steps

1. **Baseline at scale.** Run the current engine (F-074 on) over the full 2-year XAUUSD
   corpus `data/mt5/XAUUSD_M15.csv` (47,275 bars, 2024-05-22 -> 2026-05-21). Capture
   `distribution["goal_report"]`.
   Note this corpus ends 2026-05-21 and therefore does **not** contain the Jul 2026 trade —
   it is a different, larger sample, not a superset of this session's slice.
2. **Funnel census.** From the same run, count the survivor cascade
   `bars -> SWEEP_DETECTED -> DISPLACEMENT_CONFIRMED -> EXPANSION_CONFIRMED ->
   RETEST_CONFIRMED -> TRADE_OPENED`, with the per-stage kill rate. On the 1-month slice this
   read 2116 / 85 / 19 / 6 / 2 / 0. Establishing it at n=47k says which stage is the binding
   constraint, which is the only actionable throughput lever.
3. **ΔG001 for F-074.** Re-run with the directional gate disabled and diff the two goal
   reports. This is informative, **not** gating: F-074 is a validity contract and per §6.5 a
   correctness fix does not need to earn its place economically. Record it so the contract's
   economic cost is known rather than assumed.
4. **Report the gap, not a verdict.** Produce one table: each G001 criterion, target,
   observed, PASS/FAIL/SKIP, and — where SKIP — the reason (insufficient n rather than a
   computed miss). SKIP is a real answer and must not be rendered as a failure.

## Expected outcome, stated in advance (pre-registration)

The prior is a **null with a hard throughput number**, not a discovered edge. F-019 through
F-045 falsified entry information, conditional pockets, selection, exit/cost, cross-sectional
dispersion, carry signal, carry harvest, FX generalization, the weekly-sweep ontology, and
regime conditioning — 0 PROMOTE in every case. Nothing here contradicts that, and this task is
not an attempt to relitigate it.

What this produces that those did not: a quantified distance to G001's own floor, and the
identification of which funnel stage costs the most candidates. Predicting the outcome up
front is the point — if trades/month lands near 20 that genuinely surprises me and is worth
more scrutiny, not less.

## Open scope conflict — for the user, not for me to settle

G001 declares `instruments: [BTCUSDT, ETHUSDT, BNBUSDT]`. This session, and a standing
instruction recorded 2026-07-24 ("probe only `data/mt5/XAUUSD_M15.csv`, never swap in crypto
to force events"), are XAUUSD. Both cannot be satisfied silently:

- measuring XAUUSD against G001 scores it against a goal that does not name it;
- measuring crypto respects G001's letter but violates the standing instruction, and would
  look exactly like swapping instruments until events appear.

The plan above runs **XAUUSD only** and reports the mismatch as a `TruthConflict` (§6.2 rule 3)
rather than resolving it. Crypto corpora exist at 70,080 bars each if the user redirects.

## Files

- `data/mt5/XAUUSD_M15.csv` — the 2-year corpus (read-only input)
- `src/runtime/backtest_v2.py` — existing entry point; `_attach_goal_report` needs no change
- `src/config_layer/goal_validator.py`, `src/config_layer/goal_schema.py` — read-only reference
- `src/research/goal_alignment.py` — `corpus_span_months()` for the month denominator
- `src/config_layer/crt_engine_v2.py:1140,1195` — the F-074 gate toggled for step 3 only
- output: a new `results/` run directory; nothing existing is overwritten

## Verification

The goal report is self-verifying — it is emitted by the production backtest path, not by a
bespoke script. Cross-check that the run's trade count and `corpus_span_months()` reproduce the
reported `trades_per_month` by hand for one instrument, so the headline number is not taken on
trust.

## Out of scope

No parameter tuning to raise trade count. Relaxing detection gates to manufacture throughput is
precisely what F-015 already falsified ("detection-gate relaxation is NOT quality-preserving").
No promotion, no config change, no re-enabling of `rr_fusion`/`use_bitnet`. Measurement only.
