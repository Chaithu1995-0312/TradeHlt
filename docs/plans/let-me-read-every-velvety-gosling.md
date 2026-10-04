> Created: 2026-05-20 · Updated: 2026-05-20 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Feedback Loop Audit — Plan

## Context

Audit of the Tradelatest training-feedback loop: the chain that converts live/backtest outcomes back into newly-trained, promoted models. The CLAUDE.md describes Phases 0–5 as complete, but the loop's "outcomes → retrain → promote → take effect in-session" cycle has unverified seams. This plan separates what is actually wired from what isn't, and proposes targeted fixes — no broad refactor.

Verified against the codebase (not from memory): the previous turn's audit had three factual errors which are corrected below.

---

## What IS wired (verified, no action needed)

**Pipeline-B opportunities → training → promotion** (`scripts/auto_train_from_opportunities.py:180–271`):

1. `_scan_instrument()` → subprocess call to `scripts/research/opportunity_scanner.py` → writes `logs/{instr}/{run_id}/opportunities.jsonl`
2. `_train_instrument()` → subprocess call to `scripts/training/phase5_calibration.py` with `--train`
3. `phase5_calibration` builds a Gaussian via `TradeDataset.from_opportunities()` ([scripts/training/phase5_calibration.py:382–460](scripts/training/phase5_calibration.py:382)) — unbiased, CRT not consulted
4. `_maybe_promote()` → `core.model_registry.promote_gaussian(version)` writes active version to `models/gaussian_registry.json` atomically via `_save_atomic()` ([src/core/model_registry.py:86–95](src/core/model_registry.py:86))

**TradeDataset loaders** ([scripts/training/phase5_calibration.py:311–481](scripts/training/phase5_calibration.py:311)) — three paths exist:
- `from_backtest_results()` — reads `*_trades.csv` (full feature schema from BacktestRunner)
- `from_opportunities()` — reads Pipeline-B JSONL
- `from_trade_records()` — accepts in-memory TradeRecord-like dicts (delegates to `_build` → `build_gaussian_dataset`)

**Gate** ([src/training/phase5_calibration.py:120–122](src/training/phase5_calibration.py:120)) returns `APPROVED` or `REJECTED` (binary — no `UNSTABLE` tier, contrary to my earlier claim).

**Atomic registry writes + threading lock + cross-process file lock** — already correct.

---

## Real breaks (verified gaps)

### Break 1 — `discover_zones.py` is orphaned from the orchestrator

[scripts/research/discover_zones.py](scripts/research/discover_zones.py) reads `opportunities.jsonl`, clusters into a zone registry, and calls `register_zone_gate()` + `promote_zone_gate()` at lines 289–296 — but `auto_train_from_opportunities.py` never invokes it. Zone-gate refresh requires a manual second command after each training run. If a user runs the nightly auto-train and forgets the discover step, the Gaussian advances while ZoneGate stays stale on old opportunity geometry.

### Break 2 — live `TradeRecord` cannot reach training (no feature vector)

[src/journal/schema.py:7–37](src/journal/schema.py:7) — `TradeRecord` carries outcome fields (`rr`, `result`, `pnl`, `confidence`, `zone`, `duration_candles`) but NOT the 35-dim canonical feature vector that `build_gaussian_dataset` requires.

`from_trade_records()` does `t.__dict__.copy()` then passes to `_build()` → `build_gaussian_dataset` — which extracts features from the dict keys. With the current `TradeRecord` schema, those calls produce empty feature rows and the build raises `ValueError("dataset build failed... minimum required: MIN_GAUSSIAN_SAMPLES")`.

Net effect: a week of live trading produces no usable training data. The loop closes only via Pipeline-B opportunity scans (synthetic re-walk of history), never via real live outcomes.

### Break 3 — no in-session hot reload after promotion

`promote_gaussian()` updates `models/gaussian_registry.json`. Running engines hold their loaded model:

- `HeuristicGaussianEngine` — loads once via `_registry is None` guard at [src/engines/heuristic_gaussian_engine.py:236–237](src/engines/heuristic_gaussian_engine.py:236), never reloads
- `ReplayMemoryEngine` — `self._loaded = True` sentinel, never reloads
- `ZoneGateEngine` — loads on `run_zone_gate_engine()` call, no reload

Promotion mid-session takes effect only on full process restart. For a 24/5 live session this can mean a stale model runs an entire trading day after a successful promotion.

### Break 4 — promotion failure is silent in the audit log

`_maybe_promote()` at [scripts/auto_train_from_opportunities.py:123–126](scripts/auto_train_from_opportunities.py:123):

```python
def _maybe_promote(version: str) -> None:
    from core.model_registry import promote_gaussian
    ok, reason = promote_gaussian(version)
    _LOG.info("Promotion attempt for %s: ok=%s reason=%s", version, ok, reason)
```

When `ok=False`, only a Python log entry is written. The `integrity_event` audit channel (already used by `ReplayMemoryEngine._parse_jsonl` for `JSONL_CORRUPTION` and by `bitnet_inference` for contract violations) is NOT called. Failed promotions don't appear in `logs/integrity_events.jsonl` — so post-hoc forensics on "why didn't model v5_auto_20260520 take effect" requires grepping Python logs instead of querying the canonical audit stream.

### Break 5 — no programmatic trigger

`auto_train_from_opportunities.py` is CLI-only. There's no callable `TrainingTrigger` an in-process consumer (backtest completion hook, live engine drift detector) can invoke. No minimum-N gate, no drift-driven trigger, no cooldown — only Task Scheduler / cron firing the script blindly on a clock.

---

## Proposed fixes (ordered by impact / cost ratio)

| # | Fix | Files touched | Effort |
|---|-----|---------------|--------|
| 1 | Emit `integrity_event("PROMOTION_FAILED", "CRITICAL", ...)` when `ok=False` in `_maybe_promote()` | `scripts/auto_train_from_opportunities.py` | 1 line + import |
| 2 | Chain `discover_zones.py` into the orchestrator after `_maybe_promote()`, gated by `--refresh-zones` flag | `scripts/auto_train_from_opportunities.py` | ~30 lines (mirror `_train_instrument` shape) |
| 3 | `ModelRefreshBus` — per-engine version-stamp check at start of compute cycle; reload if `registry.active != self._loaded_version` | `src/engines/heuristic_gaussian_engine.py`, `src/engines/replay_memory_engine.py`, `src/engines/zone_gate_engine.py` | ~50 lines total — small per-engine reload method + version compare in compute path |
| 4 | Feature-vector snapshot in `TradeRecord` — add `features: dict[str, float]` field; snapshot at trade open in the live hook | `src/journal/schema.py`, `src/runtime/live_engine_hook.py`, downstream journal-write site (TBD — see note) | ~20 lines schema + 2 sites |
| 5 | `TrainingTrigger` class with `_has_enough_samples()`, `_drift_gate_open()`, `_cooldown_elapsed()` — exposes a `.should_trigger() -> bool` for in-process callers | new file `src/training/training_trigger.py` | ~80 lines, no new deps |

**User-locked scope:** all 5 fixes. Feature snapshot populated at trade open in the live hook.

**Caveat on Fix 4 — discovery step required first.** `src/runtime/live_engine_hook.py` does NOT currently construct `TradeRecord` and does NOT import `TradeLogger`. The hook emits decisions; some downstream executor/order-manager finalizes the trade and writes the journal record. Before editing, locate that downstream site (grep for callers of `TradeLogger().log(` or `journal.trade_logger`). Two viable shapes:

- **(a)** Hook attaches `features` to its decision payload → downstream finalizer copies it into the new `TradeRecord.features` field. Cleanest separation.
- **(b)** Hook constructs a partial `TradeRecord` at open and threads it through to the finalizer for outcome fill. Couples hook to journal schema.

Pick (a) unless the downstream site can't accept payload extensions.

**Note on duplicate TradeRecord classes.** Two distinct `TradeRecord` types exist:
- `src/journal/schema.py:8` — outcome-level, no features (used by `TradeLogger` → `trade_journal.jsonl`)
- `src/runtime/backtest_v2.py:200` — has features + price levels (used by `BacktestRunner` → `*_trades.csv`)

Backtest CSVs already feed training via `from_backtest_results()` — that path is fine. Fix 4 is specifically about closing the journal-schema gap.

Fixes 1, 2, 3 are mechanical and tightly scoped. Fix 4 unlocks the live → training data path (the architectural gap). Fix 5 is the only one that adds a new abstraction.

---

## Critical files to read before any edit

- `scripts/auto_train_from_opportunities.py` (orchestrator)
- `src/core/model_registry.py` (promote_gaussian, _save_atomic, registry layout)
- `scripts/training/phase5_calibration.py` (TradeDataset class, _build path)
- `src/journal/schema.py` (journal TradeRecord — outcome-level, no features)
- `src/journal/trade_logger.py` (`TradeLogger.log()` — journal write site)
- `src/runtime/live_engine_hook.py` (live decision hook — does NOT currently build TradeRecord; downstream finalizer needs locating)
- `src/runtime/backtest_v2.py:200` (backtest TradeRecord — has features; for reference / shape parity)
- `src/engines/heuristic_gaussian_engine.py` (`_registry is None` reload guard at line 236)
- `src/engines/replay_memory_engine.py` (`_loaded` sentinel)
- `src/utils/integrity_events.py` (audit emit API used by existing CRITICAL paths)

## Verification (post-implementation)

- **Fix 1:** force a promotion failure (e.g., point `--checkpoint` at non-existent file), tail `logs/integrity_events.jsonl`, confirm `PROMOTION_FAILED` line.
- **Fix 2:** run `python scripts/auto_train_from_opportunities.py --instruments EURUSD --refresh-zones`, confirm new `zone_registry_EURUSD_<version>.json` written.
- **Fix 3:** start engine in a REPL, promote a new Gaussian version externally, run one compute cycle, assert `engine._loaded_version` advanced.
- **Fix 4:** end-to-end: backtest run → trade closes → `trade_journal.jsonl` line contains `features` dict → load journal → `TradeDataset.from_trade_records(records)` builds without `ValueError`.
- **Fix 5:** unit tests for each gate (N below threshold, cooldown unexpired, no drift) returning False; only all-true returning True.

## Implementation order (with user-locked scope)

1. **Fix 1** (integrity event on promotion failure) — single line, lowest risk, ship first
2. **Fix 2** (chain `discover_zones.py` into orchestrator) — pure addition behind `--refresh-zones` flag
3. **Fix 3** (ModelRefreshBus on the three engines) — version-stamp compare + `_reload()` method per engine; touch each engine's compute entry point
4. **Discovery for Fix 4** — locate the live downstream order finalizer (the caller of `TradeLogger().log()` in live mode, not backtest). Without this site, Fix 4 cannot be concrete.
5. **Fix 4** (TradeRecord.features field + snapshot wiring) — shape (a) by default: hook attaches features to decision payload; finalizer copies into TradeRecord
6. **Fix 5** (TrainingTrigger) — last, since it depends on the loop already being correct

---

# Phase 2 Plan — Follow-up wiring (Fixes 6 & 7)

## Context

Fixes 1–5 above are landed. `TrainingTrigger` exists in `src/training/training_trigger.py` but is dead code: no production config block (so it runs on hardcoded defaults), and nothing calls `.should_trigger()`. This phase closes both gaps.

User-locked scope:
- **Both** call sites wired: backtest completion + live RR-drift fallback
- **Action differentiated by site**: live → Telegram alert with pre-filled CLI command (humans pull the trigger); backtest → integrity event + log only (no Telegram spam per batch)
- **Both paths emit** `TRAINING_RECOMMENDED` integrity event for the audit trail

Verified during exploration:
- **No re-hash required for the new config section.** `_compute_config_hash` at `src/governance/promotion_manager.py:409–412` hashes only the `params` sub-dict. New top-level keys outside `params` are invisible to the hash. `ConfigValidator.validate()` (`src/config_layer/config_validator.py:296–421`) does not enforce a section whitelist. No test checks section completeness.
- **Backtest completion site is clean.** `src/runtime/backtest_v2.py:1807–1830` — at line 1822 (after `writer.write_all()`, before `return m`), `self.cfg.instrument` and `output_dir` are in scope. No constructor change needed.
- **RR drift site needs a prerequisite emit.** `src/config_layer/rr/rr_fusion.py:119–125` currently emits only `logger.warning()` on drift fallback — no integrity event. `TrainingTrigger._drift_gate_open()` consumes `RR_BYPASS` events from `logs/integrity_events.jsonl`, so the emit must be added or the gate has nothing to detect.
- **Per-candle trigger check is too expensive.** `rr_fusion.score()` runs per candle. `TrainingTrigger.should_trigger()` walks the integrity log + opportunity glob — disk-heavy. Throttle the check behind a counter so the heavy work runs once per N bypasses, not every candle.

---

## Fix 6 — `training_trigger` section in production config

**File:** `configs/production/v1_multi_2026_03.json`

Add as a new top-level key (peer of `engine_runner`, `fusion_engine`, etc.) — NOT under `params`:

```json
"training_trigger": {
    "min_new_samples":       500,
    "drift_window_hours":    24,
    "drift_event_threshold": 5,
    "cooldown_hours":        6.0,
    "marker_path":           "results/training_trigger.json",
    "opportunity_glob":      "logs/**/opportunities.jsonl",
    "integrity_log":         "logs/integrity_events.jsonl",
    "drift_event_kinds":     ["RR_BYPASS", "RR_LLM_FALLBACK", "PROMOTION_FAILED"]
}
```

**Rationale per key** (these are starting values; tune to your trade volume):
- `min_new_samples: 500` — population shift large enough to move the Gaussian without being noise. Below ~200 you retrain on rounding error; above ~2000 you respond too slowly to real regime change.
- `drift_window_hours: 24` — one trading session. Drift fired only inside the last session is what should drive retraining, not a stale event from last week.
- `drift_event_threshold: 5` — five `RR_BYPASS` events in a session is statistically meaningful; one or two are normal noise from boundary-case candles.
- `cooldown_hours: 6` — prevents rapid retrain churn after a fire. With promotion taking ~2–5 min, 6 h leaves headroom for the new model to actually express itself in the data before being reconsidered.

**No re-hash command needed.** The hash function (`_compute_config_hash` at `promotion_manager.py:409`) takes `params` as input — the new top-level key is invisible to it. Verify by reading the function before editing.

**No file edits to code.** This is a pure JSON addition.

---

## Fix 7 — Wire `TrainingTrigger` to both callers

### 7a. Prerequisite: emit `RR_BYPASS` integrity event

**File:** `src/config_layer/rr/rr_fusion.py:119–125`

After the existing `logger.warning(...)` at lines 120–124, add:

```python
try:
    from utils.integrity_events import emit_integrity_event
    emit_integrity_event(
        "RR_BYPASS", "WARNING", "rr_fusion",
        {"depth": depth, "body": body, "disp": disp,
         "threshold": _DRIFT_THRESHOLD},
    )
except Exception:
    pass
```

This makes the drift signal visible in `logs/integrity_events.jsonl` for the trigger to consume — and also for operator forensics.

### 7b. Backtest completion caller (log-only)

**File:** `src/runtime/backtest_v2.py` — between lines 1822 and 1823 (after `writer.write_all()`, before `return m`):

```python
try:
    from training.training_trigger import TrainingTrigger
    from utils.integrity_events import emit_integrity_event
    _trig = TrainingTrigger.from_prod_config()
    if _trig.should_trigger():
        emit_integrity_event(
            "TRAINING_RECOMMENDED", "INFO", "backtest_runner",
            {"instrument":     getattr(self.cfg, "instrument", ""),
             "results_dir":    str(output_dir),
             "trigger_source": "backtest_completion"},
        )
        log.info(
            "TrainingTrigger fired post-backtest for %s. "
            "Run: python scripts/auto_train_from_opportunities.py "
            "--instruments %s --refresh-zones --promote-if-approved",
            getattr(self.cfg, "instrument", ""), getattr(self.cfg, "instrument", ""),
        )
        _trig.mark_fired()
except Exception as exc:
    log.debug("TrainingTrigger check failed (non-fatal): %s", exc)
```

Backtest is offline / scripted — no Telegram. The operator reads the integrity log post-session and decides.

### 7c. Live RR-drift caller (Telegram alert with pre-filled CLI)

**Architecture choice:** Do **not** call `should_trigger()` from inside `rr_fusion.score()` (per-candle hot path, disk-heavy check). Instead, instrument `LiveEngine.process()` (`src/engines/live_engine.py:639`) — it has Telegram credentials in `self.config`, already handles alert dispatch, and runs at decision cadence (not per inference).

**Edit:** `src/engines/live_engine.py` — add a module-level counter + a post-decision check at the end of `LiveEngine.process()` (after `_log_alert(result)` on line 818):

```python
# Module-level (near _AlertState)
_BYPASS_CHECK_COUNTER:    int = 0
_BYPASS_CHECK_EVERY_N:    int = 50   # candles between disk-walks


def _maybe_telegram_training_alert(symbol: str, instrument: str,
                                   bot_token: str, chat_id: str) -> None:
    """Heavy gate check throttled to once per N candles. Telegram + emit on fire."""
    global _BYPASS_CHECK_COUNTER
    _BYPASS_CHECK_COUNTER += 1
    if _BYPASS_CHECK_COUNTER < _BYPASS_CHECK_EVERY_N:
        return
    _BYPASS_CHECK_COUNTER = 0
    try:
        from training.training_trigger import TrainingTrigger
        from utils.integrity_events import emit_integrity_event
        trig = TrainingTrigger.from_prod_config()
        if not trig.should_trigger():
            return
        run_id = time.strftime("%Y%m%d_%H%M%S")
        cli_cmd = (
            "python scripts/auto_train_from_opportunities.py "
            f"--instruments {instrument} --refresh-zones "
            f"--promote-if-approved --run-id {run_id}"
        )
        message = (
            "📊 *Training Recommended*\n"
            f"Symbol: {symbol}\n"
            "RR fusion bypass threshold exceeded.\n\n"
            "Run:\n"
            f"`{cli_cmd}`"
        )
        send_telegram_alert(message=message, bot_token=bot_token, chat_id=chat_id)
        emit_integrity_event(
            "TRAINING_RECOMMENDED", "WARNING", "live_engine",
            {"instrument":     instrument,
             "symbol":         symbol,
             "trigger_source": "live_rr_drift",
             "telegram_sent":  True,
             "cli_cmd":        cli_cmd,
             "run_id":         run_id},
        )
        trig.mark_fired()
    except Exception as exc:
        log.debug("TrainingTrigger live-check failed (non-fatal): %s", exc)
```

Then at the end of `LiveEngine.process()` (after line 818 `_log_alert(result)`), add:

```python
# Periodic training-trigger evaluation (cheap counter; full check ~1/50 candles)
_maybe_telegram_training_alert(
    symbol=symbol,
    instrument=symbol,  # symbol is the instrument here
    bot_token=self.config.bot_token,
    chat_id=self.config.chat_id,
)
```

This keeps `rr_fusion.score()` stateless and hot-path-clean. The trigger check piggybacks on `LiveEngine.process()` which already does per-decision I/O.

---

## Critical files to read before any edit

- `configs/production/v1_multi_2026_03.json` — confirm the top-level key ordering convention before splicing in `training_trigger`
- `src/governance/promotion_manager.py:409–412` — confirm hash function input is the `params` dict only
- `src/config_layer/rr/rr_fusion.py:100–140` — see the existing fallback paths so the emit lands in the right one
- `src/runtime/backtest_v2.py:1807–1830` — confirm exact line numbers for insertion in current state
- `src/engines/live_engine.py:33` (`send_telegram_alert` signature), `:639` (`LiveEngine.process` start), `:818` (post-`_log_alert` insertion point)
- `src/training/training_trigger.py` — confirm `TrainingTrigger.from_prod_config()` signature unchanged

## Verification (post-implementation)

- **Fix 6:** `python -c "from config_layer.production_config import get_prod_section; print(get_prod_section('training_trigger'))"` — prints the new section without raising.
- **Fix 7a:** force RR fusion drift in a backtest (e.g. corrupt a feature value), tail `logs/integrity_events.jsonl`, confirm `RR_BYPASS` line with depth/body/disp payload.
- **Fix 7b:** run any small backtest with `min_new_samples` lowered to 1 in the config, observe `TRAINING_RECOMMENDED` line in `logs/integrity_events.jsonl` and the "Run: ..." log line in stdout.
- **Fix 7c:** set a low `_BYPASS_CHECK_EVERY_N=2` temporarily, trigger 2 RR_BYPASS events in a live-replay harness, confirm Telegram message arrives with the pre-filled CLI command, confirm `TRAINING_RECOMMENDED` integrity event with `trigger_source=live_rr_drift`.
- **Marker file:** after first `mark_fired()`, `results/training_trigger.json` exists with `{last_fired_ts, last_sample_count}`. Subsequent `should_trigger()` returns False until cooldown passes.

## Open risks / notes

- `_BYPASS_CHECK_EVERY_N=50` is a guess. If `LiveEngine.process()` runs ~once per M15 candle per symbol, that's one trigger check per ~12.5 hours per symbol — coarse. Consider time-based throttle instead (e.g. check at most once per 30 min) if per-candle rate is high. The module-level counter is symbol-shared, which may be fine or may need per-symbol state — depends on whether you want global or per-instrument trigger semantics.
- `LiveEngine.process()` is called for every candle even when `decision=BLOCK`. The trigger check runs anyway, which is correct: drift can manifest in blocks just as in passes.
- Telegram credentials assumed configured in `LiveEngineConfig`. If they're empty, `send_telegram_alert` no-ops with a warning — the integrity event still fires, so the audit trail is preserved.
- `TRAINING_RECOMMENDED` events accumulate; with `cooldown_hours=6` and a noisy live session, expect ~4/day at most. Acceptable audit volume.

