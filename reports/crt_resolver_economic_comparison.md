# CRT Resolver vs Engine — Economic Comparison (XAUUSD M15)

> Research only (§6.5 Authority Ladder). Grants no authority to modify CRTStateResolver, the CRT engine, or any production config regardless of the numbers below.
> cert_version=1.0.0

## Methodology (read this before the numbers)

**Trigger rule — the two arms use DIFFERENT rules, not the same strategy:**

- **Engine arm**: the real production trigger — RETEST -> EXECUTION via `CRTEngine.try_retest_to_execution` (`src/config_layer/crt_engine_v2.py`).
- **Resolver arm**: EXPANSION-entry transition — a relaxed proxy. `CRTStateResolver`'s own EXECUTION branch is structurally unreachable (F-069): `_continuous_gates_pass` requires a `score`/`risk_score`/`crt_score` feature absent from `CANONICAL_FEATURES` (`src/features/feature_schema.py`) — confirmed 0 in every measurement this program has taken. A strict same-trigger comparison is therefore a foregone conclusion (0 trades) before any numbers are computed.

**SL/TP construction:** engine = `ExecutionEngine.build_trade()` (displacement-candle-anchored SL, per-intent TP1/TP2). Resolver arm mirrors the SL anchor formula (`sl_atr_buffer` read from the active config, not hardcoded) but uses a **single flat TP1 multiplier only** — no per-intent classification, no TP1-partial/breakeven-trail/TP2 two-leg structure. This is an illustrative single-leg proxy.

**Direction:** tried in order — resolver's own `CRTStateMemory.displacement_direction` (tracked at DISPLACEMENT/SWEEP entry), then its shadow-preserved fallback `pending_displacement_dir`, then `trend_bias` from the feature vector. **Empirical finding on this corpus:** every real EXPANSION-entry bar has BOTH memory fields empty — these entries fire via the declarative `displacement_flag` predicate match, a path that never touches direction-tracking memory — so `trend_bias` is the source actually used throughout, not memory. Bars where all three are empty are skipped and counted, never guessed. **SL anchor** similarly falls back from the displacement candle (never available here, same root cause) to the entry bar's own low/high — counted per-signal via `sl_anchor_source`.

**Cost model:** two columns, never blended — the engine's own native cost (`pnl_rr_net`, its stochastic ATR-slippage+spread simulation) and a flat 12bps `DEFAULT_COST_MODEL` applied identically to both arms.

**Provenance:** engine ledger = `D:\Tradelatest\results\run_20260805_105350_XAUUSD\XAUUSD_trades.csv` (mode: reuse). Corpus: `D:\Tradelatest\data\mt5\XAUUSD_M15.csv`. Resolver config: the current committed `market_crt_states.yaml`, untouched for this comparison.

## A finding about the cost model, before the table

This strategy's stops are ATR-buffer-anchored and genuinely tight relative to price (a property of the construction, not a measurement artifact). The flat 12bps-of-**price** research cost model (`src/research/costs.py`, designed for the Edge Discovery program's typically wider stops) converts to an enormous cost in **R** terms when the risk distance is this small: `cost_r(entry, risk_distance) = (12bps * entry) / risk_distance`. On the engine's real trade, `risk_distance` = 0.7534 price units (entry ~2318.21) — the flat-cost model alone contributes **+3.69R** of cost on a trade whose entire realized result was -0.0383R under the engine's OWN (correct) cost model. On the resolver arm, the same effect contributes an average of **+1.33R** per signal. **This is the 12bps model being the wrong tool for this geometry, not evidence either arm performed catastrophically** — the GROSS (pre-cost) row below is the more honest number to read for this strategy, with the flat-cost row kept only for the apples-to-apples formula comparison the methodology promised, not as the headline economic verdict.

## Comparison table

**GROSS (pre-cost) — the more honest number given the cost-model mismatch above:**

| Arm | n | mean gross R | 95% CI (gross) |
|---|---:|---:|---|
| Engine (native EXECUTION trigger) | 1 | +0.5028 | [+0.5028, +0.5028] |
| Resolver (EXPANSION-entry, relaxed) | 8 | +0.7500 | [+0.2500, +1.0000] |

Engine's own NATIVE cost model (real stochastic slippage+spread): `pnl_rr_net` = [-0.0383] — this, not either column below, is the engine arm's real, governing result.

**Flat-12bps-cost (apples-to-apples formula, degenerate here — see finding above):**

| Arm | n | wins | losses | win rate | PF | expectancy (flat-cost R) | max DD (R) | 95% CI (flat-cost) | CI degenerate | power |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| Engine (native EXECUTION trigger) | 1 | 0 | 1 | 0.0% | 0.000 | -3.1895 | 3.1895 | [-3.1895, -3.1895] | yes | INSUFFICIENT |
| Resolver (EXPANSION-entry, relaxed) | 8 | 3 | 5 | 37.5% | 0.134 | -0.5840 | 4.6723 | [-1.5089, +0.0638] | no | INSUFFICIENT |

### Resolver-arm counters (transparency on what got filtered out)

| Counter | Value |
|---|---:|
| entries_found | 8 |
| skipped_no_direction | 0 |
| rejected_inverted_sl | 0 |
| direction_source_memory | 0 |
| direction_source_pending_shadow | 0 |
| direction_source_trend_bias_fallback | 8 |
| sl_anchor_source_displacement_candle | 0 |
| sl_anchor_source_entry_bar_fallback | 8 |
| future_empty_near_corpus_end | 0 |

## Epistemic Integrity caveat (Program E-001)

Both arms are reported **INSUFFICIENT** for an economic conclusion (n=1 engine, n=8 resolver, both below `MIN_CELL_N=15` — precedent: `scripts/analysis/blind_label_score.py`). Neither win rate, profit factor, nor expectancy above should be read as evidence that either arm is economically 'better' — at these sample sizes a single trade dominates the entire result.

**The only decisive, non-statistical finding is structural**: `BacktestRunner` can produce a trade under its own native rule; `CRTStateResolver`'s own native EXECUTION rule structurally cannot (deductive, F-069, not a sample-size question). The numbers above exist only under an explicitly different, relaxed resolver-side trigger and should be read as illustrative, not as a finding in either direction.

## Correction to a concurrent document

`reports/crt_state_resolver_vs_backtest_runner_report.md` (a separate, descriptive doc, correctly cites this program's F-069 finding) contains a fabricated worked example (entry=2352.10, sl=2350.21) that does **not** match the real trade row this report reads directly from `D:\Tradelatest\results\run_20260805_105350_XAUUSD\XAUUSD_trades.csv` (entry_raw=2318.21, sl=2317.4565714285714). Do not cite that document's worked-example numbers as real.

