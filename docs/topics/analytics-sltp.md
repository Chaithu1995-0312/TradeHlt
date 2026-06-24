# Topic: Analytics — SL/TP Comparator

> **Topic-visibility unit.** Offline post-backtest analysis: compares two stop-loss/take-profit
> placement methods on the *same* trade entries to see which structure actually wins. Tooling, not
> on the live path.
>
> Created: 2026-06-05 · Updated: 2026-06-05 · Status: living

## In plain language
Given a set of trades that already happened, this asks a clean what-if: if we'd placed stops/targets
the CRT way vs the legacy ATR way — on the *identical* entries — which would have made more money? It
re-simulates exits candle-by-candle for both methods and reports aggregate metrics (win rate,
expectancy, drawdown) plus a recommended winner. It's an analysis aid for tuning SL/TP structure, run
after a backtest — it never touches live trading.

## Code covered
- [`src/analytics/sl_tp_comparator.py:300`](../../src/analytics/sl_tp_comparator.py) — `SLTPComparator` — `compare()` at :327 → `ComparisonReport`.
- [`src/analytics/sl_tp_comparator.py:248`](../../src/analytics/sl_tp_comparator.py) — `ComparisonReport` — aggregate + per-trade result container.
- [`src/analytics/sl_tp_comparator.py:133`](../../src/analytics/sl_tp_comparator.py) — `simulate_exit` — forward-walk exit (TP2→SL→TP1) → realized RR.
- `src/analytics/clustering.py`, `performance.py` — trade clustering + performance helpers.

## Ins / Outs
- **Ins:** `trade_records` (with entry/SL/TP/features) + `candles`; `cfg` (legacy ATR mults, primary metric). Reads a trades CSV in the backtest wrapper.
- **Outs:** `ComparisonReport` (`.to_dict()` / `.save_json()` / `.print_summary()`) — CRT vs legacy aggregates, winner + delta, recommendation.

## Entry points & validations
- **Reached via:** CLI `python src/analytics/sl_tp_comparator.py --csv … --instrument …`, or library `SLTPComparator.from_prod_config().compare(...)`. The `run_comparison_from_backtest()` wrapper drives a full backtest first.
- **Validated by:** deterministic, replay-safe core (`compare()` takes pre-loaded data); `test_sl_tp_comparator.py` covers intent derivation, aggregation, end-to-end compare, winner logic.

## Tests
- [`tests/test_sl_tp_comparator.py`](../../tests/test_sl_tp_comparator.py) — intent derivation, aggregate metrics, end-to-end `compare()`, winner determination.

## Fits in architecture
Offline analysis tooling feeding the execution-planning discussion ([`execution-planning.md`](execution-planning.md))
— it informs SL/TP structure choices but is not a runtime component. Evidence-style output, like a
`docs/analysis/` study but code-driven.

## Discussion (filled in-session)
- **Challenges:** 2026-06-05 — `run_comparison_from_backtest()` imports `runtime.backtest_v2` (an upward dependency) — a known hidden-coupling decoupling blocker. The core `compare()` is decoupled; only the convenience wrapper couples.
- **Risks:** 2026-06-05 — offline tooling; results inform but don't gate anything live. Treat as advisory analysis.
