> Created: 2026-06-01 · Updated: 2026-06-01 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Agent-Readable Execution Memory Layer

## Context

The system has 20+ log writers producing rich JSONL event data across
`logs/run_{RUN_ID}/{instrument}/`, `logs/fusion_trades_*.jsonl`,
`logs/agent_audit.jsonl`, and ~15 other files. None of these payloads
carry a consistent `{instrument, run_id, trade_id}` identity envelope.
An agent traversing history must currently grep files or do recursive
directory scans to correlate a trade to its run and instrument.

This plan adds:
- A `_ctx` key additively injected into the two primary trade-lifecycle
  JSONL writers (no existing key touched)
- A supplemental `logs/index/` layer for O(1) index lookups
- `src/agent/log_query.py` for structured agent queries

No existing writers, folder structures, or import paths are changed.

---

## PHASE 1 — Current Logging Matrix (Inventory)

| File | Writer | Output | Format | Hot Loop | run_id | instrument | trade_id |
|---|---|---|---|---|---|---|---|
| src/utils/logging_config.py | FileHandler | logs/run_{ID}/{sym}/flow_*.log | text | Y | in path | in path | N |
| **src/utils/trade_logger.py** | open+json | logs/run_{ID}/{sym}/{sym}_fusion.jsonl | JSONL | Y | **MISSING** | Y (per-call) | Y |
| **src/journal/trade_logger.py** | open+json | logs/trade_journal.jsonl | JSONL | Y | **MISSING** | Y (symbol) | Y |
| src/agent/audit.py | open+json | logs/agent_audit.jsonl | JSONL | N | N | N | N |
| src/core/signal_audit.py | open+json | logs/signal_audit.jsonl | JSONL | Y (debug) | N | N | N |
| src/core/collector.py | flow logger | flow_collector.log | JSON via logger | Y | in path | in path | Y (as "id") |
| src/utils/integrity_events.py | open+json | logs/integrity_events.jsonl | JSONL | N | N | N | N |
| src/utils/engine_telemetry.py | path.open+json | logs/engine_telemetry.jsonl | JSONL | Y | N | Y | N |
| src/replay/replay_drift_governor.py | open+json | logs/drift_audit.jsonl | JSONL | N | N | Y (via env) | N |
| src/cognitive/cognitive_bus.py | path.open+json | logs/cognitive_telemetry.jsonl | JSONL | Y (async) | N | N | N |
| src/governance/promotion_manager.py | open+json | configs/promotion_log.jsonl | JSONL | N | N | N | N |
| src/expansion/expansion_engine.py | open+json | logs/expansion_trace.jsonl | JSONL | N | N | N | N |
| src/engines/live_engine.py | open+json | logs/live_alerts.jsonl | JSONL | Y | N | Y | N |
| src/config_layer/llm_inference_client.py | _append_jsonl | logs/llm_audit.jsonl | JSONL | Y | N | N | N |
| src/agent/findings_synthesizer.py | open+json | logs/agent_findings.jsonl | JSONL | N | Y (run_id) | N | N |
| src/runtime/backtest_bitnet.py | open+json | logs/backtest_decisions_{sym}_{ts}.jsonl | JSONL | Y | N | in filename | N |
| src/governance/orchestrator.py | delegated | logs/governance_audit.jsonl | JSONL | N | N | N | N |

### Issues identified

| Issue | Files |
|---|---|
| **Missing run_id in hot-path writers** | trade_logger.py (utils), journal/trade_logger.py |
| **EXIT records have no instrument** | src/utils/trade_logger.py log_exit() |
| **Schema fragmentation** | "symbol" vs "instrument" vs "id" vs "trade_id" across files |
| **Orphan log** | logs/backtest_decisions_{sym}_{ts}.jsonl — timestamp in filename, no stable path |
| **Collector "id" ≠ trade_id** | collector.py uses "id" not "trade_id" |
| **Duplicate LLM audit** | logs/llm_audit.jsonl AND logs/agent_llm_requests.jsonl |
| **No log_query.py** | src/agent/log_query.py does not exist |
| **No index layer** | logs/index/ does not exist |

---

## PHASE 2 — New File: `src/utils/log_identity.py`

**Purpose:** Pure, no-I/O helper that builds the `_ctx` envelope dict.
No side effects. Thread-safe. Zero runtime dependency.

```python
# src/utils/log_identity.py
from __future__ import annotations
from typing import Optional

def build_log_context(
    instrument: str,
    run_id: str,
    trade_id: Optional[str] = None,
    strategy: Optional[str] = None,
    phase: Optional[str] = None,
) -> dict:
    return {
        "instrument":     instrument,
        "run_id":         run_id,
        "trade_id":       trade_id,
        "strategy":       strategy,
        "phase":          phase,
        "schema_version": "v1",
    }
```

---

## PHASE 3 — Enhance Existing Writers (additive `_ctx` only)

### Scope decision

Only 2 files get `_ctx` in Phase 3 (primary trade-lifecycle JSONL):
- `src/utils/trade_logger.py` — the canonical ENTRY/EXIT/REJECT file
- `src/journal/trade_logger.py` — outcome-level trade journal

All other writers (collector, signal_audit, engine_telemetry, etc.) are
**deferred** — they lack one or more of the 3 identity fields at write
time or are not queried for trade lifecycle. Deferred writers are annotated
at the bottom of this plan.

---

### 3A. `src/utils/trade_logger.py`

**Exact changes (additive only):**

1. **New imports** (after existing imports at ~line 77):
   ```python
   from utils.log_identity import build_log_context
   from utils.logging_config import RUN_ID as _MODULE_RUN_ID
   ```

2. **`TradeLogger.__init__`** — add `run_id` param, store `_instrument`:
   ```python
   # BEFORE (line 88-96):
   def __init__(self, path: Path | str | None = None,
                instrument: str = "") -> None:
       if path is None:
           if instrument:
               path = Path(f"logs/fusion_trades_{instrument}.jsonl")
           else:
               path = DEFAULT_LOG_PATH
       self.path = Path(path)
       self.path.parent.mkdir(parents=True, exist_ok=True)

   # AFTER:
   def __init__(self, path: Path | str | None = None,
                instrument: str = "",
                run_id: str = "") -> None:
       if path is None:
           if instrument:
               path = Path(f"logs/fusion_trades_{instrument}.jsonl")
           else:
               path = DEFAULT_LOG_PATH
       self.path = Path(path)
       self.path.parent.mkdir(parents=True, exist_ok=True)
       self._instrument = instrument
       self._run_id = run_id or _MODULE_RUN_ID
       self._last_entry_offset: int = 0   # for trade index byte-seek
   ```
   All existing callers that don't pass `run_id` automatically fall back
   to the module-level `RUN_ID` singleton — zero breakage.

3. **`log_entry`** — capture offset before write, inject `_ctx` after
   record is built, before `_write()` (line 136):
   ```python
   # After record = {...} dict, before self._write(record):
   try:
       self._last_entry_offset = self.path.stat().st_size if self.path.exists() else 0
   except OSError:
       self._last_entry_offset = 0
   record["_ctx"] = build_log_context(
       instrument=instrument,   # per-call arg takes precedence
       run_id=self._run_id,
       trade_id=trade_id,
       phase="ENTRY",
   )
   self._write(record)
   ```

4. **`log_exit`** — inject `_ctx` after record dict, before `_write()` (line 161):
   ```python
   record["_ctx"] = build_log_context(
       instrument=self._instrument,   # from instance (set by backtest_v2)
       run_id=self._run_id,
       trade_id=trade_id,
       phase="EXIT",
   )
   self._write(record)
   ```
   Note: `self._instrument` will be non-empty after the backtest_v2.py
   change in Phase 3C. Legacy callers that don't pass `instrument` to
   `__init__` get `instrument=""` in EXIT `_ctx` — acceptable, ENTRY has it.

5. **`log_rejection`** — inject `_ctx` after record dict (line 186):
   ```python
   record["_ctx"] = build_log_context(
       instrument=instrument,   # per-call arg
       run_id=self._run_id,
       phase="REJECT",
   )
   self._write(record)
   ```

---

### 3B. `src/journal/trade_logger.py`

**Exact changes:**

1. **New imports** (after line 8):
   ```python
   from utils.log_identity import build_log_context
   from utils.logging_config import RUN_ID as _MODULE_RUN_ID
   ```

2. **`TradeLogger.__init__`** — add `run_id` (line 42):
   ```python
   def __init__(self, log_path: Optional[str] = None, run_id: str = "") -> None:
       self._path = Path(log_path) if log_path else _DEFAULT_LOG
       self._run_id = run_id or _MODULE_RUN_ID
   ```

3. **`TradeLogger.log()`** — replace `record.to_json()` write with a
   dict write that includes `_ctx` (lines 48-52). This is the minimal
   additive change; `load_all()` still works (reads raw dicts, `_ctx`
   is an extra key):
   ```python
   self._path.parent.mkdir(parents=True, exist_ok=True)
   try:
       _rec_dict = json.loads(record.to_json())   # get the dict form
       _rec_dict["_ctx"] = build_log_context(
           instrument=record.symbol,
           run_id=self._run_id,
           trade_id=record.trade_id,
           phase=record.result or "TRADE",
       )
       with open(self._path, "a", encoding="utf-8") as f:
           f.write(json.dumps(_rec_dict) + "\n")
   except Exception as exc:
       log.warning("TradeLogger: write failed: %s", exc)
   ```

---

### 3C. `src/agent/audit.py`

**Exact changes — optional `_ctx` only:**

Add one optional param `_ctx: Optional[dict] = None` to `write_step`
and `write_session_summary`. No callers change. No existing field touched.

```python
# write_step — add after error: Optional[str] = None,
_ctx: Optional[dict] = None,
# Inside, after record dict is built, before _append():
if _ctx is not None:
    record["_ctx"] = _ctx
```

Same pattern for `write_session_summary`.

---

## PHASE 3C — `src/runtime/backtest_v2.py` (line 1341)

Pass `instrument` and `run_id` to `_TradeLogger` constructor so
the instance has both fields for EXIT `_ctx` and index writes:

```python
# BEFORE (line 1341):
self._trade_logger = _TradeLogger(_run_log_dir / f"{bt_config.instrument}_fusion.jsonl")

# AFTER:
self._trade_logger = _TradeLogger(
    _run_log_dir / f"{bt_config.instrument}_fusion.jsonl",
    instrument=bt_config.instrument,
    run_id=_RUN_ID,
)
```

Then immediately after (still in `__init__`), add fail-open index writes:
```python
# Supplemental index writes — additive, never block the run
try:
    from utils.log_index_writer import write_run_index, write_instrument_index
    write_run_index(_RUN_ID, bt_config.instrument, str(_run_log_dir))
    write_instrument_index(_RUN_ID, bt_config.instrument, str(_run_log_dir))
except Exception as _idx_err:
    self.log.debug("Index write skipped (non-fatal): %s", _idx_err)
```

Also add trade index write inside `src/utils/trade_logger.py` `log_exit()`,
after `self._write(record)`:
```python
try:
    from utils.log_index_writer import write_trade_index
    write_trade_index(
        instrument=self._instrument,
        run_id=self._run_id,
        trade_id=trade_id,
        log_path=str(self.path),
        offset=self._last_entry_offset,
    )
except Exception:
    pass
```

---

## PHASE 4 — New File: `src/utils/log_index_writer.py`

**Purpose:** Fail-open append helpers that populate `logs/index/`.
Never raises. Never a source of truth.

```python
# src/utils/log_index_writer.py
import json
import time
from pathlib import Path

_INDEX_DIR             = Path("logs/index")
_RUN_INDEX_PATH        = _INDEX_DIR / "run_index.jsonl"
_INSTRUMENT_INDEX_PATH = _INDEX_DIR / "instrument_index.jsonl"
_TRADE_INDEX_PATH      = _INDEX_DIR / "trade_index.jsonl"


def _append_index(path: Path, record: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception:
        pass


def write_run_index(run_id: str, instrument: str, log_dir: str) -> None:
    _append_index(_RUN_INDEX_PATH, {
        "run_id": run_id,
        "instrument": instrument,
        "start_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "log_dir": log_dir,
        "offset": 0,
    })


def write_instrument_index(run_id: str, instrument: str, log_dir: str) -> None:
    _append_index(_INSTRUMENT_INDEX_PATH, {
        "instrument": instrument,
        "run_id": run_id,
        "log_dir": log_dir,
        "trade_count": 0,
        "offset": 0,
    })


def write_trade_index(
    instrument: str, run_id: str, trade_id: str,
    log_path: str, offset: int = 0,
) -> None:
    _append_index(_TRADE_INDEX_PATH, {
        "instrument": instrument,
        "run_id": run_id,
        "trade_id": trade_id,
        "log_path": log_path,
        "offset": offset,
    })
```

### Index schemas

**`logs/index/run_index.jsonl`** — one line per run start:
```json
{"run_id": "20260523_120850", "instrument": "BTCUSDT", "start_ts": "2026-05-23T12:08:50Z", "log_dir": "logs/run_20260523_120850/BTCUSDT", "offset": 0}
```

**`logs/index/instrument_index.jsonl`** — one line per instrument per run:
```json
{"instrument": "BTCUSDT", "run_id": "20260523_120850", "log_dir": "logs/run_20260523_120850/BTCUSDT", "trade_count": 0, "offset": 0}
```

**`logs/index/trade_index.jsonl`** — one line per completed trade:
```json
{"instrument": "BTCUSDT", "run_id": "20260523_120850", "trade_id": "CRT-0001", "log_path": "logs/run_20260523_120850/BTCUSDT/BTCUSDT_fusion.jsonl", "offset": 12832}
```

---

## PHASE 5 — New File: `src/agent/log_query.py`

**API:**

```python
def get_run(run_id: str) -> dict | None
    # Index first: scan run_index.jsonl for matching run_id
    # Returns index record or None

def get_instrument(instrument: str, run_id: str | None = None) -> list[dict]
    # Index first: scan instrument_index.jsonl
    # Fallback: single-depth glob logs/run_*/{instrument}/{instrument}_fusion.jsonl
    # Returns list of index records

def get_trade(trade_id: str) -> dict | None
    # Index first: find trade in trade_index.jsonl → seek to offset in fusion JSONL
    # Fallback: one-level scan of logs/run_*/ without recursion
    # Returns ENTRY record dict (with _ctx if enhanced) or None

def query(
    instrument: str | None = None,
    run_id: str | None = None,
    trade_id: str | None = None,
    limit: int = 50,
) -> list[dict]
    # Hierarchy: trade_id → run_id → instrument → all
    # Returns ENTRY records sorted by timestamp desc, capped at limit
    # Never loads full file — streams line by line, stops at limit
```

**Internal rules:**
- `_iter_jsonl(path)` — generator, skips malformed lines, never raises
- `_iter_jsonl_from_offset(path, offset)` — seeks then streams; falls back to full scan on seek error
- `_scan_fusion_paths(instrument, run_id)` — single `glob("run_*")`, then one `iterdir()` inside — no recursion
- All public functions return `[]` or `None` on miss, never raise

---

## Exact Files

### New (3)
| File | Lines (est.) |
|---|---|
| `src/utils/log_identity.py` | ~25 |
| `src/utils/log_index_writer.py` | ~50 |
| `src/agent/log_query.py` | ~160 |

### Modified (4)
| File | Change | Risk |
|---|---|---|
| `src/utils/trade_logger.py` | `__init__` + 3 write methods + offset tracking | LOW |
| `src/journal/trade_logger.py` | `__init__` + `log()` write path | LOW |
| `src/agent/audit.py` | optional `_ctx` param in 2 methods | VERY LOW |
| `src/runtime/backtest_v2.py` | line 1341 + 3-line index write block | LOW |

---

## Hot-Loop Impact

| Writer | Frequency | Added work | Cost |
|---|---|---|---|
| `trade_logger.log_entry` | Per trade (not per candle) | 1× `os.stat()` + dict build | Negligible |
| `trade_logger.log_exit` | Per trade close | 1× `_append_index` (open+write) | Same as existing `_write` |
| `trade_logger.log_rejection` | Per rejected signal | dict build only | Negligible |
| `journal/trade_logger.log` | Per trade close | `json.loads()` + 1 extra key | Negligible |

The `_ctx` dict construction is 5 assignments — cheaper than any existing
dict comprehension in the record builders. No new file handles are held open.

---

## No-Op Migration Path

No migration needed. Changes are purely additive:
- `_ctx` is a new key; all existing readers use `dict.get()` or ignore extras
- `logs/index/` is new; no existing code reads it
- All new constructor params have defaults maintaining backward compat
- New `log_identity.py` / `log_index_writer.py` are never imported by
  existing code unless explicitly called
- `audit.py` `_ctx` param is keyword-only with `None` default

---

## Rollback Plan

If any enhancement causes a regression:

1. Remove `_ctx` inject lines from `log_entry`, `log_exit`, `log_rejection`
   in `src/utils/trade_logger.py` (3 lines)
2. Remove `_ctx` inject from `src/journal/trade_logger.py` `log()` (5 lines)
3. Revert line 1341 in `src/runtime/backtest_v2.py` to original one-arg form
4. Delete the 3-line index-write block in `backtest_v2.py`
5. `logs/index/` directory is inert — leave or delete, no code reads it
6. The 3 new `src/utils/log_identity.py`, `src/utils/log_index_writer.py`,
   `src/agent/log_query.py` files can remain (nothing imports them)

Total rollback: ~10 line reversions. Git diff is surgically clean.

---

## Schema Examples

### ENTRY record with `_ctx` (fusion JSONL):
```json
{
  "event": "ENTRY",
  "trade_id": "CRT-0001",
  "timestamp": "2026-05-23T12:09:14.000000",
  "instrument": "BTCUSDT",
  "direction": "LONG",
  "session": "LONDON",
  "regime": "EXPANSION",
  "features": {"retest_depth": 0.22, "body_ratio": 0.71},
  "fusion": {"final_score": 0.68, "llm_fired": true},
  "entry_price": 67540.0,
  "sl_price": 67340.0,
  "tp1_price": 67740.0,
  "tp2_price": 67940.0,
  "_ctx": {
    "instrument": "BTCUSDT",
    "run_id": "20260523_120850",
    "trade_id": "CRT-0001",
    "strategy": null,
    "phase": "ENTRY",
    "schema_version": "v1"
  }
}
```

### EXIT record with `_ctx`:
```json
{
  "event": "EXIT",
  "trade_id": "CRT-0001",
  "timestamp": "2026-05-23T12:27:00.000000",
  "exit_reason": "TP1",
  "pnl_rr_net": 1.95,
  "win": true,
  "duration_candles": 18,
  "_ctx": {
    "instrument": "BTCUSDT",
    "run_id": "20260523_120850",
    "trade_id": "CRT-0001",
    "strategy": null,
    "phase": "EXIT",
    "schema_version": "v1"
  }
}
```

---

## Ingestion Examples

```python
from agent.log_query import get_run, get_instrument, get_trade, query

# Resolve a run
run = get_run("20260523_120850")
# → {"run_id": "20260523_120850", "instrument": "BTCUSDT", "log_dir": "...", ...}

# All runs for one instrument
runs = get_instrument("BTCUSDT")

# Look up a single trade
trade = get_trade("CRT-0001")
# → ENTRY record with _ctx envelope

# Latest 10 trades for BTCUSDT
trades = query(instrument="BTCUSDT", limit=10)

# All trades in a specific run
trades = query(run_id="20260523_120850", limit=100)

# Lifecycle join (agent side):
entry = get_trade("CRT-0001")
# then stream fusion JSONL for matching EXIT:
#   filter event=="EXIT" and trade_id==entry["trade_id"]
```

---

## Self-Review

| Rule | Compliant? |
|---|---|
| Did I replace anything? | No — additive only |
| Did I move folders? | No |
| Did I create duplicate truth? | No — index is supplemental, fusion JSONL is canonical |
| Did I introduce runtime dependency? | No — log_identity is a pure function, log_index_writer is fail-open |
| Can agents distinguish coin→run→trade→replay→training via metadata not folders? | **Yes** — `_ctx.instrument` / `_ctx.run_id` / `_ctx.trade_id` are in every ENTRY/EXIT record; index provides O(1) lookup |

---

## Deferred (out of scope for this plan)

| Writer | Reason for deferral |
|---|---|
| src/core/collector.py | Hot loop; `run_id` not in call signature — invasive change |
| src/core/signal_audit.py | Debug-mode only; low agent query value |
| src/utils/engine_telemetry.py | Lacks trade_id; not queried for trade lifecycle |
| src/cognitive/cognitive_bus.py | Async queue; has parent_event_id chain already |
| src/agent/modes/ | New `log_query` tool registrations — separate PR |
| src/governance/promotion_manager.py | Has no trade_id; governance-scoped only |

---

## Verification

```bash
# 1. Unit test log_identity
python -c "
from src.utils.log_identity import build_log_context
ctx = build_log_context('BTCUSDT', '20260523_120850', 'CRT-0001', 'S1', 'ENTRY')
assert ctx['schema_version'] == 'v1'
assert ctx['instrument'] == 'BTCUSDT'
print('log_identity OK')
"

# 2. Unit test log_index_writer
python -c "
from src.utils.log_index_writer import write_run_index, write_trade_index
write_run_index('TEST_RUN', 'BTCUSDT', 'logs/run_TEST_RUN/BTCUSDT')
import json; line = open('logs/index/run_index.jsonl').readlines()[-1]
assert json.loads(line)['run_id'] == 'TEST_RUN'
print('log_index_writer OK')
"

# 3. Backtest integration — verify _ctx present in fusion JSONL
python src/runtime/backtest_v2.py --instrument BTCUSDT --csv data/BTCUSDT_M15.csv
python -c "
import json, glob
files = glob.glob('logs/run_*/**/BTCUSDT_fusion.jsonl', recursive=False)
# check latest
for line in open(files[-1]):
    rec = json.loads(line)
    if rec.get('event') == 'ENTRY':
        assert '_ctx' in rec, 'missing _ctx'
        assert rec['_ctx']['run_id'], 'missing run_id'
        assert rec['_ctx']['trade_id'] == rec['trade_id']
        print('_ctx OK:', rec['_ctx'])
        break
"

# 4. Test log_query API
python -c "
from src.agent.log_query import get_run, get_instrument, get_trade, query
trades = query(instrument='BTCUSDT', limit=5)
assert all('_ctx' in t for t in trades)
print(f'query OK: {len(trades)} trades returned')
"

# 5. Backward-compat: old callers without run_id
python -c "
from src.utils.trade_logger import TradeLogger
tl = TradeLogger()     # no run_id
assert tl._run_id      # falls back to module-level RUN_ID
print('backward compat OK')
"
```
