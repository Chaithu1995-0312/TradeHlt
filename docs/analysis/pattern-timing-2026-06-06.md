# Pattern Timing Library — Validation Report (Phase 1c)

> Date: 2026-06-06 · Type: point-in-time analysis (not a living doc) · Track: Trading-arch (Pipeline B, measure-only)
> Plan: `~/.claude/plans/with-the-docs-gathered-optimized-kettle.md` · Code: `src/replay/timing_reconstructor.py`,
> `src/replay/timing_advisor.py`, `scripts/research/opportunity_scanner.py` (1a), `scripts/analysis/build_pattern_library.py` (1b).

## What this is

The empirical-validation half of the Pattern Timing Library. It answers the questions the falsification
gate left open before any live consumption is allowed. **No model trained; no live decision path changed.**

## 1. Falsification gate (recap) — PASSED

ETH OOS, 139,942 opportunity records. "Do winners reach +0.25R earlier than losers?"
- Coupled label (`rr_achieved>0`): reach +0.5R within 3 candles **87.9% (win) vs 7.1% (loss)**; median time-to-0.5R 1 vs 10 candles.
- Decoupled label (`TP_HIT` @ far 2R, independent of the 0.25R crossing): P(TP_HIT | +0.25R within 3c) **2.1% vs 0.3%** → **8.05× lift** (rare-event: TP_HIT base 1.7% under the 0.5R trail).

## 2. Incremental-edge test (MANDATORY) — does timing add edge BEYOND existing features?

Method (no new model): stratify the universe into the library's feature cells
`(direction × session × volatility_regime × geometry_bucket)` and measure the win-rate separation
between **fast** (+0.25R by candle 3) and **slow** *within* each cell. If timing only re-encoded the
features, within-cell separation would collapse to ~0.

| Instrument | Global coupled gap (fast−slow) | Within-cell n-wtd gap | Cells with fast>slow | Within-cell decoupled TP_HIT lift |
|---|---|---|---|---|
| ETHUSDT | +0.767 | **+0.768** | **54 / 54** | +0.0203 |
| BNBUSDT | +0.781 | **+0.781** | **54 / 54** | +0.0163 |

**Verdict.** The within-cell gap ≈ the unconditional gap (no shrinkage) and holds in **54/54 cells on
both instruments** → timing's discrimination is **orthogonal to (session, regime, geometry)**, not a
proxy for them. The decoupled TP_HIT lift stays positive but **modest** within cells.

## 3. Honest caveats (nothing hidden)

- **Coupled-label mechanical confound.** `rr_achieved>0` is produced by the same forward walk that
  yields the timing, and the 0.5R trailing stop ties "reached 0.25R early" to "ended positive." The
  within-cell test controls for *features*, not for this *label coupling*. The clean, decoupled
  evidence (TP_HIT lift) is positive but small in absolute terms.
- **Timing is fundamentally a POST-ENTRY signal.** Its strongest, cleanest use is observing a live
  trade's behavior — which is *why* early-invalidation (consumer A) is primary and ranking (B) is
  secondary. The pre-entry ranking edge is real but must clear a backtest A/B before enabling.
- **Universe ≠ CRT setups.** This is the raw both-directions geometry universe (CRT not consulted).
  The `--crt-filter` view (BOS/sweep present) is available for the "this exact CRT setup" framing.
- **Resolution/horizon.** ±1 candle (15 min); forward horizon censored at 40 candles (10h) — first-move
  (1–6 candles) well covered, deep 2R right-censored. Same-bar SL/TP uses the conservative tie-break.
- **Regime/session encodings** use the engine's persisted categorical `session`/`volatility_regime`
  codes ({0,1,2} each), faithful to scoring-time output.

## 4. The early-invalidation curve (consumer A contract)

Library overall `winrate_decay_on_025R` (ETH), the empirical abnormality rule:

| If NOT +0.25R by candle k | win-rate (slow) | win-rate (fast) |
|---|---|---|
| k=1 | 0.332 | 0.866 |
| k=2 | 0.180 | 0.865 |
| k=3 | 0.098 | 0.865 |
| k=5 | 0.032 | 0.864 |
| k=8 | 0.008 | 0.864 |

A live trade with no +0.25R by candle 3 sits at ~10% historical win-rate vs ~86% for those moving —
`TimingAdvisor.abnormality()` exposes exactly this (weight 0.0, advisory-only in Phase 1).

## 5. Capital efficiency (consumer B)

`expectancy_per_candle = expectancy_R / median_resolution_candles` is emitted per cell; `TimingAdvisor.rank_score()`
normalizes it to [0,1]. Wired DORMANT into `OpportunityRanker` via `timing_weight=0.0` (ordering
unchanged). Enabling is a Phase-2 weight flip, gated on a backtest A/B showing expectancy/maxDD lift.

## 6. Status & next

- **Consumer A (early-invalidation): GO to Phase-2 design** — feature-orthogonal post-entry signal,
  proven. Next: deterministic backtest A/B of "exit/scale if no +0.25R by cluster p_x" (weight-0 → on),
  success = cut losers early, lift expectancy and/or reduce maxDD at no material cost to winners.
- **Consumer B (ranking): HOLD** — positive but modest decoupled edge; needs the ranking backtest A/B.
- **Stability still to widen:** SOL/BTC cross-instrument + in-sample vs OOS windows (BNB/ETH shown here).

## Reproduce

```
python scripts/analysis/build_pattern_library.py --instrument ETHUSDT \
    --opportunities logs/ETHUSDT/oos_ETHUSDT/opportunities.jsonl --csv data/ETHUSDT_M15.csv
pytest tests/replay/test_timing_reconstructor.py -q
```
Zero diff to the live decision spine (engine_runner / fusion_engine / decision_engine /
execution_planner / ultron_risk_gate unchanged).
