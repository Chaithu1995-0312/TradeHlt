# Pattern Timing Library — Measure-First (No New Model)

> Created: 2026-06-06 · Milestone: Trd-M6 on-ramp (measure-only) · Track: Trading-arch (research / Pipeline B)
> Verdict of the requested audit + the implementation plan + expected data coverage.

## Context (why this is being built)

The user reframed a fragile question ("predict how long a move lasts") into a robust one:
**"Historically, when this exact pattern appears, what happens next — and how fast?"** i.e. compute
empirical *conditional timing distributions* (`time_to_+0.25R / +0.5R / +1R / TP1 / TP2 / SL`) per
pattern cluster, then use them for ranking (throughput, F-003) and in-trade abnormality detection.

This is **exactly the repo's settled doctrine**: F-001 (intelligence is not the constraint — *consume
existing info*), F-002 (the edge is SELECTION), F-012 (sidecars unconsumed). It is also the missing
**empirical foundation for the parked Trd-M6** "dynamic invalidation exit" (roadmap §3) — Trd-M6 was
parked for lack of measured timing on a real sample; this produces precisely that, measure-only.

## Audit verdict: YES — computable today, no new model

A deterministic forward re-walk of candles between a trade's entry and its horizon recovers every
requested metric. All inputs already exist:

| Need | Where it lives | Status |
|---|---|---|
| entry / SL / TP1/TP2/TP3 prices | `TradeRecord` `entry_price_fill`,`sl_price`,`tp1_price`,`tp2_price`,`tp3_price` (`src/runtime/backtest_v2.py:225-231`) | ✅ persisted |
| direction, entry/exit candle idx + ts | `direction`,`candle_open`,`candle_close`,`opened_at`,`closed_at` (`backtest_v2.py:223,234-237`) | ✅ |
| outcome / R | `exit_reason`,`pnl_rr_net` (`backtest_v2.py:233,242`); **R = \|entry_price_fill − sl_price\|** | ✅ derivable |
| candle stream (forward walk) | `CandleLoader.stream()` (`backtest_v2.py:665-691`), M15 CSVs in `data/` | ✅ deterministic, no-lookahead |
| grouping keys | `session`,`bitnet_score_at_entry`,`pattern_hash`(regime embedded),`features`,`crt_path` (`backtest_v2.py:254,276,286,259,285`) | ✅ |

**What is ABSENT** (and why it does NOT block us): MFE/MAE and intermediate level-hit candle indices
are never stored (executor `update_trade` tests TP/SL per close only, `crt_engine_v2.py:2008-2101`).
The re-walk **computes them as a side-effect** — so we get them for free without touching the engine.

**Why no-lookahead is not violated:** we measure the *actual realized path of an already-closed
trade*. Nothing feeds back into a live decision in Phase 1. (Live consumption is gated to Phase 2.)

## Phase 1 — Timing reconstruction + pattern library (measure-only, additive)

Pipeline-B research artifact. **Zero engine change, zero live change, weight 0.0.** Mirrors the
`probability-surface-advisory` measure-first precedent.

**1a. Timing reconstructor** — new module `src/replay/timing_reconstructor.py` (replay-adjacent;
production logic stays out of `scripts/` per CLAUDE.md §3.3). Pure function:
`reconstruct_timing(record, candles) -> dict`. Given a trade/opportunity (entry price, SL, direction,
entry timestamp) and the candle slice forward to a fixed horizon, walk candle-by-candle and record
the **first candle index** where `high`(long)/`low`(short) crosses each level
`entry ± {0.25,0.5,1.0}·R`, `TP1`, `TP2`, plus first SL touch; also track running MFE/MAE. Emit
`{time_to_025R, time_to_05R, time_to_1R, time_to_tp1, time_to_tp2, time_to_sl, mfe_R, mae_R,
bars_to_first_favorable}` in candle counts (×15min = minutes). Same-candle TP-vs-SL ambiguity →
**conservative rule (assume adverse first)**, matching backtest convention. Reuse `CandleLoader` and
`Direction` enum; do not re-implement candle parsing.

**1b. Aggregator + library** — new `scripts/analysis/build_pattern_library.py` (thin CLI wrapper).
Read historical trades (`logs/fusion_trades.jsonl` entry/exit pairs + backtest CSV), call 1a per
trade, group by composite key `(instrument, session, bitnet_bucket, pattern_hash)` with coarser
fallback keys for thin cells, and emit per-cluster distributions (N, win-rate, expectancy, median +
p10/p50/p90 of each `time_to_*`, MFE/MAE, and the **conditional** "if no +0.25R by candle k, win-rate
→ X"). Output `results/analysis/pattern_library_<instrument>.json`. Bitnet buckets via simple
discretization of the persisted `bitnet_score_at_entry`.

**1c. Validation report** answering the user's open questions (`docs/analysis/pattern-timing-<date>.md`):
Do CRT winners move fast? Does time-to-first-move differ by session/regime/instrument/bitnet bucket?
Is timing stable enough to rank on? Tests: `tests/replay/test_timing_reconstructor.py` (synthetic
candle paths with known crossings; conservative-rule + no-lookahead assertions).

## Phase 2 — Consume (GATED on Phase-1 showing stable, discriminating timing)

Only if 1c shows timing separates winners/losers and is stable OOS. Two consumption points, both
already-existing boundaries (no new spine), each shipped measure-only first:
- **Ranking signal** for the orphaned scanner/ranker path (F-013, `src/scanner/*`) — "fastest expected
  payoff / highest expectancy" ranking → directly serves the throughput goal (F-003).
- **In-trade abnormality / dynamic-invalidation exit** — the Trd-M6 surface (roadmap §3): "no +0.25R
  by the cluster's p90 ⇒ deteriorating ⇒ exit/scale." Replaces/augments the static bracket.

## Expected data coverage (the honest caveats — nothing hidden)

- **Executed trades are FEW** — BNBUSDT ~15→37 after gates (F-003). Per-cluster cells will be too
  thin for the 420–1000 the framing imagines; whole-population timing is fine, fine-grained clusters
  are not — from executed trades alone.
- **The real substrate is the OPPORTUNITY/SCANNER dataset**, not gated trades. Timing reconstruction
  needs only entry price + SL + direction + timestamp + candle stream — so it runs on **every detected
  RETEST/EXECUTION candidate**, decoupling sample size from the throughput gate. `ReplayMemoryEngine`
  already loads an `opportunities_dir`. **One open data question to confirm in 1a:** do scanner/
  opportunity records carry (or let us derive via ExecutionPlanner) entry+SL+direction? If yes, N
  jumps from tens to hundreds+. This is the single most important coverage lever.
- **Resolution = 1 candle (15 min)**; intra-candle ordering is unknown (standard backtest limit) →
  timing is ±1 candle and same-candle SL/TP uses the conservative rule. State this in 1c.
- **Grouping keys ready now:** instrument, session, bitnet bucket, pattern_hash (regime embedded),
  features. Zone_id and discrete regime are reconstructable post-hoc from the stored `features` dict
  (zone via `ReplayMemoryEngine._assign_cluster`, regime via `RegimeClassifier`) — Phase-1 optional.

## Verification

- `pytest tests/replay/test_timing_reconstructor.py` — synthetic candle paths with known first-crossings;
  conservative same-candle rule; determinism (same inputs → same timing); no-lookahead.
- Run `python scripts/analysis/build_pattern_library.py --instrument BNBUSDT --data-dir data/` →
  inspect `results/analysis/pattern_library_BNBUSDT.json` + the 1c report. Sanity: median
  `time_to_first_favorable` is small for winners, large/absent for losers (the testable hypothesis).
- Confirm zero diff to the live/backtest decision spine (measure-only): no change to `engine_runner`,
  `fusion_engine`, `decision_engine`, `execution_planner`, `ultron_risk_gate`.

## Out of scope / do-not

- No timing-*prediction* model (the user's own conclusion; <10% value per their estimate, and would
  reopen a KILLED-class "new intelligence" path against F-001). Distributions only.
- No live consumption until Phase-1 evidence clears (advisory-isolation + measure-first doctrine).
- Do not store MFE/MAE by mutating the live `Trade`/executor in Phase 1 — the re-walk yields them
  offline; live instrumentation is a separate, later decision if Phase 2 needs it online.
