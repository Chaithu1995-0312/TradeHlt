# Certify the live decision rail against deterministic historical replay

## Context

The paper TickDB run at 17:27 ended `closed_bars=80 process_calls=0`, with two `FEATURE_REJECT`
records in `logs/live_rail.jsonl`. The working hypothesis was that the feeder cannot construct the
canonical feature surface. **That hypothesis is wrong, and the real cause is located.**

What actually happened, traced through source:

1. The feeder worked. `FeaturePipeline` ran (`rows_before=80 rows_after=2 drop=78`), `ready()`
   returned True, `as_trade_data()` passed its own 48-key completeness check.
2. `hook.process(...)` **was called** — twice. `LiveRailOrchestrator.process_calls` increments
   *after* the call (`live_rail_orchestrator.py:213`), so an exception inside makes a real call
   invisible. `process_calls=0` under-reports; it does not mean "never reached".
3. The exception came from `filter_canonical_inputs` in
   [`src/engines/zone_gate_engine.py:164-166`](src/engines/zone_gate_engine.py:164) — ZoneGate got
   19 of the 48 canonical keys.
4. **Root cause:** [`live_engine_hook.py:279`](src/runtime/live_engine_hook.py:279) declares
   `global _ENGINE_CONFIG_CACHE, _feature_monitor` — **`_feature_store` is not in that list**, yet
   line 394 assigns `_feature_store = FeatureStore(...)` inside the same function. That assignment
   binds a function-local and is discarded. The module global (line 92) stays `None` forever, so the
   guard at line 817 never fires and `engine_input` remains the reduced `_build_engine_input()` dict.

The canonical ingestion boundary therefore **never runs on the live path**. The T-11 comment at
lines 809-816 ("a validation failure must REJECT the tick, never downgrade it") hardened the
exception path in 2026-07-19; the block it protects is unreachable. Skipped validation is
indistinguishable from absent validation — the same silent-gap class as F-079 / F-056 / F-083.

§6.8 classification: **CONFIRMED DEFECT** (violated contract: FeatureStore's documented role as the
canonical ingestion boundary + the T-11 fail-closed intent).

Scope guard: F-073 means there is no production live loop, so this bites the paper rail only. No
production-loss claim. Backtests use a different path and are unaffected.

Two corrections to carry into the work:
- The canonical surface is **48** features (schema v5.0, F-076), not 39. Two docstrings still say
  39 — `feature_pipeline.build_features` (:375) and `live_engine_hook` (:378). DOC_DRIFT, fix in the
  same turn as the code (§6.2 rule 6).
- The run log shows `pip_value_per_lot missing for XAUUSD → defaulting to 10.0 USD`. That is a
  silent config default on a capital-sizing input (§6.5 forbids it). Record it; do not fix here.

## Approach

A fail-forward certification, not a single bug fix: each replay run exposes the next seam. The
harness must make each seam legible and distinct, which is why instrumentation comes first.

### Phase 0 — Make the instrument honest (no behavior change)

Without this, the certification cannot tell "never called" from "called and threw".

- `live_rail_orchestrator.py`: split the two `_audit` sites that both emit `FEATURE_REJECT` —
  `:199` (feeder could not build features) becomes `FEEDER_REJECT`; `:215` (the engine raised)
  becomes `ENGINE_ERROR`, carrying the exception type and the raising module.
- Add `process_attempts` alongside `process_calls`; increment it *before* the call.
- Isolate run artifacts: `--report-dir results/live_rail_cert/<run_id>/` instead of appending to
  the shared `logs/live_rail.jsonl`. Confirm `UltronRiskGate` cannot write
  `logs/kill_switch_state.json` during a paper run; if it can, point it at the run dir.
- Update `tests/test_live_rail_orchestrator.py:242,268`, which assert on the old `FEATURE_REJECT`
  string.

### Phase 1 — Historical replay source, two arms

Reuse what exists rather than adding a venue. Use `data/mt5/XAUUSD_M15.csv` (XAUUSD only, per
standing instruction).

- **Arm A — bar injection.** `LiveRailOrchestrator.run_until_bar_queue_empty()` +
  `ingest_closed_bar()` already exist for exactly this. Feed `ClosedBar` objects straight from the
  CSV. This isolates the feature→decision seam with `BarBuilder` out of the picture.
- **Arm B — tick replay.** A new `OhlcvTickReplayPort` implementing `MarketDataPort`, expanding each
  M15 bar into ticks in O→H→L→C order so `BarBuilder` reconstructs it. **Binding assertion:** the
  rebuilt bar must equal the source bar exactly; if it does not, the arm is testing a fiction and
  must fail, not warn.

Arm A is the primary certification path; Arm B additionally certifies `BarBuilder`.

### Phase 2 — Fix the singleton (the actual defect)

Add `_feature_store` to the `global` declaration at `live_engine_hook.py:279`. Then make the skip
impossible to reintroduce silently: when `_STORE_AVAILABLE` is true but `_feature_store` is `None`
at line 817, **raise** rather than falling through to the reduced dict.

This is behavior-changing on the live path by construction — it makes validation stricter, on a rail
with no production caller. It needs a BUILD_IMPACT_MANIFEST (`CH-live-rail-cert-replay`) per §3.3b,
and a grep proving no other module reads `_feature_store`.

### Phase 3 — Walk the remaining seams

Pre-registered prediction, to be recorded before the run: `_build_ohlcv_and_auxiliary` documents
auxiliary as "all remaining CANONICAL_FEATURES … every one is MANDATORY", and the feeder already
supplies all 48, so Phase 2 alone may carry a bar through to a decision. If a further seam raises,
record it as its own row and fix one at a time — never widen a contract to make a run pass.

### Phase 4 — Certification criteria

A run certifies only if all of these hold:

- `process_attempts == process_calls` and `process_calls > 0`
- every bar past warmup produces exactly one terminal record (`NO_ORDER`, `FILL`, `PREFLIGHT_REJECT`)
- `FEEDER_REJECT == 0` and `ENGINE_ERROR == 0`
- zero orders: `hook_submit_orders=false`, `dry_run=true`, MT5 `send_order` and Telegram send counts
  both 0
- **determinism**: the same corpus slice replayed twice yields byte-identical audit records once
  wall-clock `ts` is excluded

## Critical files

| File | Change |
|---|---|
| [`src/runtime/live_engine_hook.py`](src/runtime/live_engine_hook.py) | `:279` global fix · `:817` fail-closed on None · `:378` docstring 39→48 |
| [`src/runtime/live_rail_orchestrator.py`](src/runtime/live_rail_orchestrator.py) | split reject kinds, `process_attempts`, report-dir |
| `src/inout/live_rail/ohlcv_replay_port.py` | new — Arm B port, round-trip assertion |
| `scripts/live/run_live_rail.py` | `--corpus` / `--arm {bars,ticks}` / `--report-dir`; SITS-register |
| [`src/features/feature_pipeline.py`](src/features/feature_pipeline.py) | `:375` docstring 39→48 |
| `tests/test_live_rail_orchestrator.py` | update the two reject-kind assertions |
| `tests/test_live_rail_replay_cert.py` | new — Phase 4 criteria incl. the determinism pair |

Reuse, do not rebuild: `LiveRailFeeder` (the only feature builder — do not add a third),
`run_until_bar_queue_empty` / `ingest_closed_bar`, `CandleLoader` for the CSV, `BarBuilder`,
`PaperVenueExecutor`.

## Verification

```bash
venv/Scripts/python.exe -m pytest tests/test_live_rail_orchestrator.py tests/test_live_rail_feeder.py tests/test_live_rail_replay_cert.py -q
```

```bash
LIVE_ENGINE_ENABLED=1 venv/Scripts/python.exe scripts/live/run_live_rail.py --paper --arm bars --corpus data/mt5/XAUUSD_M15.csv --limit 500 --report-dir results/live_rail_cert/run1
```

Then re-run into `run2` and diff the two audit files with `ts` stripped — they must be identical.
Confirm `git status` shows no change to `configs/production/ACTIVE_VERSION`, and that the run wrote
nothing outside `results/live_rail_cert/`.

## Out of scope

No live venue, no `dry_run=false`, no `ACTIVE_VERSION` edit, no promotion, no G001 or economic
claim. This is replay/integration certification; F-073 stays OPEN until a production loop exists,
and F-010 stays OPEN because this rail still has no exit loop.
