# Topic: Metrics Layer V2 (RR / distribution / concentration / survival / efficiency)

> **Topic-visibility unit.** One concept, narrated in human language, kept in sync with the
> code on every working response (`CLAUDE.md §6.1`). Read this to understand the topic — what
> code it covers, how it's reached, what tests it, what's still open — **without loading the
> rest of the codebase**. Link, don't inline.
>
> Created: 2026-06-14 · Updated: 2026-09-03 · Status: living

## In plain language
The Metrics Layer is the second-order measurement surface that lets us judge *whether a change
actually helps the goal* — turning "does P&F look interesting?" into "does it move Δexpectancy /
Δfrequency / ΔDD / ΔRR vs baseline?". Before it, the system knew entry / exit / PnL but not *how
far price moved, how much was left on the table, how quickly, how efficiently*. It closes the
Goal Layer's honest `avg_rr` SKIP and adds RR distribution, concentration, trade distribution,
survival (MFE/MAE), and trade-efficiency metrics.

It is built in **three layers that never mix** (owner doctrine): **A** raw per-trade observation
(`TradePathStats`), **B** aggregates (`BacktestMetrics.distribution["metrics_v2"]`), **C** goal
telemetry (`goal_report`). A→B→C only.

## Code covered
- [`src/runtime/backtest_v2.py`](../../src/runtime/backtest_v2.py) — `TradePathStats` (Layer A
  dataclass: mfe/mae/bars_to_peak + derived capture/giveback/efficiency); `TradeRecord.path`;
  `TradeJournal.observe_open_bar` (observation-only per-bar hook); `MetricsEngine._metrics_v2_block`
  (Layer B); `_planned_rr` / `_v2_percentile` / `_top_n_contribution_pct` helpers;
  `MultiInstrumentRunner._write_aggregate` (Phase 3 symbol attribution).
- [`src/analytics/metrics_oracle.py`](../../src/analytics/metrics_oracle.py) — Oracle V2:
  `percentile` / `median` / `planned_rr` / `avg_planned_rr` / `top_n_contribution` — independent
  recompute (imports nothing from the production metrics path).
- [`src/research/measurement/forward_walk.py`](../../src/research/measurement/forward_walk.py) —
  the **frozen MFE/MAE oracle** the live within-trade tracking must match (reused, never modified).

- **Spine inventory (2026-09-03 citation pass — path existence on the GCMC spine join; not a behavior claim, not G001, not a file:line citation. Source still wins.:**
- [`src/journal/__init__.py`](../../src/journal/__init__.py)
- [`src/journal/schema.py`](../../src/journal/schema.py)
- [`src/journal/trade_execution_link_v1_0.py`](../../src/journal/trade_execution_link_v1_0.py)
- [`src/journal/trade_identity_v1_0.py`](../../src/journal/trade_identity_v1_0.py)
- [`src/journal/trade_provenance_v1_0.py`](../../src/journal/trade_provenance_v1_0.py)

## Ins / Outs
- **Ins:** the closed-trade ledger (`TradeJournal.closed` → `TradeRecord` fields: `pnl_rr_net`,
  `entry_price_raw`/`sl_price`/`tp1_price`, `session`, `duration_candles`, and the per-bar-observed
  `TradeRecord.path`). No new config.
- **Outs:** `BacktestMetrics.distribution["metrics_v2"]` = `{rr, concentration, distribution,
  survival, efficiency}`; `BacktestMetrics.trades_per_week`; per-symbol `symbol_attribution` +
  `trades_per_symbol` in `aggregate_summary.json`; closed `goal_report.avg_rr_min` (no longer SKIP).

## Entry points & validations
- **Reached via:** every backtest (`MetricsEngine.compute`); multi-instrument aggregate
  (`MultiInstrumentRunner.run_all` → `_write_aggregate`).
- **Validated by:** the **hot-loop burden of proof** — (1) live MFE/MAE == frozen `forward_walk`
  recompute, (2) replay/runner determinism unchanged (observation-only), (3) Oracle V2 parity for
  every ledger family. Measure-only: nothing here gates a decision.

## Tests
- [`tests/test_metrics_v2.py`](../../tests/test_metrics_v2.py) — Phase 0 forward_walk cross-check
  (long/short/SL/TP/timeout); Layer B aggregates; efficiency triad; Oracle V2 parity; symbol
  attribution.
- [`tests/runtime/test_replay_determinism.py`](../../tests/runtime/test_replay_determinism.py) +
  [`tests/research/test_runner_determinism.py`](../../tests/research/test_runner_determinism.py) —
  the hot-loop change must not perturb the ledger.

## Fits in architecture
Level 3 (Metrics) in the owner's hierarchy: Truth → **Goal → Metrics** → Interpreters → Fusion →
Risk → Execution. Feeds the [Goal Layer](goal-layer.md) (Layer C) and sits on the Backtest Trust
Layer (`metrics_oracle` parity). The intended next step after this is **interpreter experiments**
measured against G001 — not before Oracle V2 parity is green.

## Discussion (filled in-session)
> Standing parallel-discussion surface. Append dated entries; never delete — supersede.

- **Risks:** 2026-06-14 — this is the FIRST change to touch the Trust-Layer hot loop. Mitigated by
  observation-only design (`observe_open_bar` writes only `TradeRecord.path`, draws no RNG) + the
  forward_walk oracle cross-check + determinism gate.
- **Challenges:** 2026-06-14 — keeping live MFE/MAE byte-equal to forward_walk: matched its exact
  definition (entry-relative, intrabar high/low, floor/cap 0, bars strictly after entry incl. exit
  bar). Cross-check compares price-unit MFE/MAE (basis-independent).
- **Blockers:** none.
- **Ambiguities:** 2026-06-14 — planned vs realized RR: goal bound = realized (`avg_rr_net`);
  `avg_planned_rr` is advisory telemetry only.
- **Enhancements:** 2026-06-14 — eventual `TradeRecord → {TradePathStats, TradeExecutionStats,
  TradeAttributionStats}` split; per-session RR attribution; survival metrics by win/loss subset.
- **Need more info:** none.
- **2026-09-03 — spine citation pass:** named 5 previously unreferenced spine paths under Code covered (path existence on the GCMC spine join; not a behavior claim, not G001, not a file:line citation. Source still wins.).
