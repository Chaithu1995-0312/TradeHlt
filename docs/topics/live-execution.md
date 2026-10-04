# Topic: Live Execution (live order/data path)

> **Topic-visibility unit.** The live-only path: how candles come in, how an approved decision becomes
> an MT5 order + Telegram alert, and where the kill-switch / drift sit. This is the path behind
> finding **F-010** (live PnL is UNVERIFIED — ExecutionPlanner + Ultron are exercised only here).
>
> Created: 2026-06-05 · Updated: 2026-09-03 · Status: living

## In plain language
In replay, candles come from CSVs and nothing is ordered. **Live** is the other half: candle fetchers
pull fresh OHLCV, a hooked live engine runs the same engines→planner→risk-gate spine, and an approved
trade is sent to **MT5** with a **Telegram** alert, behind a **kill-switch** and a human override gate.
Because headline ROI is measured in backtests, and the planner + Ultron only run on this live path,
the live profit-and-loss is **not yet verified end to end** (F-010). The old INOUT execution pipeline
was archived 2026-05-02; what remains live are the fetchers, bridges, and the hook.

## Code covered
- [`src/runtime/live_engine_hook.py:582`](../../src/runtime/live_engine_hook.py) — `HookedLiveEngine` — orchestrates engines → ExecutionPlanner → UltronRiskGate → kill-switch → alert → MT5; `process()` at :590.
- [`src/runtime/live_engine_hook.py:507`](../../src/runtime/live_engine_hook.py) — `LiveEngineContext` — DI container (orchestrator, regime, kill_switch, telegram, mt5, feature_store, feature_monitor).
- [`src/live/mt5_bridge.py:53`](../../src/live/mt5_bridge.py) — `MT5Bridge` — MetaTrader-5 order execution (send/close, account info; dry-run + lot clamping).
- [`src/live/telegram_bridge.py:51`](../../src/live/telegram_bridge.py) — `TelegramBridge` — signal / kill-switch / daily-summary alerts.
- [`src/inout/alphavantage_candle_fetcher.py:129`](../../src/inout/alphavantage_candle_fetcher.py) — `AlphaVantageCandleFetcher` — FX M15 OHLCV → CSV.
- [`src/inout/hummingbot_candle_fetcher.py:206`](../../src/inout/hummingbot_candle_fetcher.py) — `HummingbotCandleFetcher` — crypto OHLCV (Binance/Bybit/…) → CSV.
- [`src/execution/loop.py:31`](../../src/execution/loop.py) — `ExecutionLoop` — continuous tick pipeline (scan→rank→regime→allocate→gate→alert→override); `AlertManager`/`OverrideHandler` alongside.

- **Spine inventory (2026-09-03 citation pass — path existence on the GCMC spine join; not a behavior claim, not G001, not a file:line citation. Source still wins.:**
- [`src/live/__init__.py`](../../src/live/__init__.py)
- [`src/live/order_manager.py`](../../src/live/order_manager.py)
- [`src/inout/live_rail/__init__.py`](../../src/inout/live_rail/__init__.py)
- [`src/inout/live_rail/bar_builder.py`](../../src/inout/live_rail/bar_builder.py)
- [`src/inout/live_rail/binance_ws_adapter.py`](../../src/inout/live_rail/binance_ws_adapter.py)
- [`src/inout/live_rail/config.py`](../../src/inout/live_rail/config.py)
- [`src/inout/live_rail/factory.py`](../../src/inout/live_rail/factory.py)
- [`src/inout/live_rail/longport_adapter.py`](../../src/inout/live_rail/longport_adapter.py)
- [`src/inout/live_rail/ohlcv_replay_port.py`](../../src/inout/live_rail/ohlcv_replay_port.py)
- [`src/inout/live_rail/resilience.py`](../../src/inout/live_rail/resilience.py)
- [`src/inout/live_rail/tickdb_adapter.py`](../../src/inout/live_rail/tickdb_adapter.py)
- [`src/inout/live_rail/types.py`](../../src/inout/live_rail/types.py)
- [`src/runtime/live_rail_feeder.py`](../../src/runtime/live_rail_feeder.py)
- [`src/runtime/live_rail_orchestrator.py`](../../src/runtime/live_rail_orchestrator.py)
- [`src/runtime/__init__.py`](../../src/runtime/__init__.py)

## Ins / Outs
- **Ins:** live OHLCV (fetchers) + per-tick features + portfolio state; config `get_prod_section("live_integration")` (mt5/telegram toggles, dry_run) and `get_prod_section("inout")`.
- **Outs:** MT5 orders, Telegram messages, and a per-tick `outcome` dict (incl. `drift_severity`, kill-switch block flags); trade outcomes feed `register_trade_outcome()` → kill-switch accounting.

## Entry points & validations
- **Reached via:** the live loop calling `HookedLiveEngine.process(...)` each tick; fetchers run as data-prep CLIs. (Distinct from `runtime.backtest_v2`, the replay path.)
- **Validated by:** kill-switch pre-check (blocks on tripped state), the human `OverrideHandler` gate (`AUTO_EXECUTE=False` default), dry-run modes on both bridges, and drift detection at [`src/runtime/live_engine_hook.py:676`](../../src/runtime/live_engine_hook.py) (`_drift_severity` — logged, per F-008). **Gap:** no end-to-end live-PnL replay yet (F-010 OPEN).

## Tests
- [`tests/test_live_integration.py`](../../tests/test_live_integration.py) — Telegram/MT5 bridge modes, lot clamping, `register_trade_outcome` + kill-switch trip, hook singletons.
- [`tests/test_execution_loop.py`](../../tests/test_execution_loop.py) — AlertManager routing, OverrideHandler decisions, ExecutionLoop guards (pause / allocator-reject / risk-block / override-skip / happy path).

## Fits in architecture
The live tail of the spine ([`signal-flow.md`](../architecture/signal-flow.md)): same
`EngineRunner → … → UltronRiskGate` core ([`ultron-risk-gate.md`](ultron-risk-gate.md),
[`execution-planning.md`](execution-planning.md)) but with real I/O. Findings: F-010 (live PnL
unverified) and F-008 (drift not acted on) both live here.

## Discussion (filled in-session)
- **Risks:** 2026-06-05 — live PnL unverified (F-010): the planner + Ultron arm is only exercised here, so backtest ROI does not yet imply live ROI.
- **Blockers:** 2026-06-05 — `live_engine_hook` uses module-level singletons (lazy `_get_*`), a known decoupling blocker (Trd-M3); complicates isolated testing.
- **Need more info:** 2026-06-05 — inout execution pipeline archived 2026-05-02 (`archive/inout_legacy/`); only fetchers remain live. Confirm no caller still imports the archived controllers.
- **2026-09-03 — spine citation pass:** named 15 previously unreferenced spine paths under Code covered (path existence on the GCMC spine join; not a behavior claim, not G001, not a file:line citation. Source still wins.).
